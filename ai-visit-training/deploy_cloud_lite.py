from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
#!/usr/bin/env python3
"""部署轻量版到云端"""
import paramiko, os, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = DEPLOY_HOST
USER = DEPLOY_USER
PASS = DEPLOY_PASSWORD
REMOTE = '/opt/voice_practice'

def ssh_cmd(ssh, cmd, desc=''):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    rc = stdout.channel.recv_exit_status()
    status = 'OK' if rc == 0 else f'FAIL({rc})'
    if desc: print(f'  [{desc}] {status}')
    if err and rc != 0: print(f'    {err[:200]}')
    return rc, out, err

print('=' * 60)
print('部署轻量版到云端')
print(f'  目标: {USER}@{HOST}')
print('=' * 60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print('连接成功\n')

# 停止旧服务
print('[1] 停止服务...')
ssh_cmd(ssh, 'systemctl stop voice_practice nginx 2>/dev/null; echo done')

# 上传文件
print('[2] 上传文件...')
sftp = ssh.open_sftp()
# 核心文件
for local in ['d:/demo2/app.py', 'd:/demo2/static/index_v2.html']:
    fname = os.path.basename(local)
    remote = f'{REMOTE}/{fname}' if fname == 'app.py' else f'{REMOTE}/static/index.html'
    sftp.put(local, remote)
    print(f'  {fname}')

# 上传 knowcard 知识库
knowcard = 'd:/demo2/knowcard'
# 先用 ssh 创建目录结构
dirs_cmd = f'cd /tmp && mkdir -p knowcard_tmp'
ssh_cmd(ssh, dirs_cmd)
# 构建目录树
all_dirs = set()
for root, dirs, files in os.walk(knowcard):
    for d in dirs:
        rel = os.path.relpath(os.path.join(root, d), knowcard).replace('\\', '/')
        all_dirs.add(rel)
for d in sorted(all_dirs):
    ssh_cmd(ssh, f'mkdir -p {REMOTE}/knowcard/{d}')
# 上传文件
count = 0
skip = 0
for root, dirs, files in os.walk(knowcard):
    for f in files:
        local = os.path.join(root, f)
        rel = os.path.relpath(local, knowcard).replace('\\', '/')
        remote = f'{REMOTE}/knowcard/{rel}'
        try:
            sftp.put(local, remote)
            count += 1
        except Exception as e:
            skip += 1
print(f'  knowcard: {count} files uploaded, {skip} skipped')
sftp.close()

# 创建 systemd 服务
print('[3] 配置服务...')
svc = f"""[Unit]
Description=Voice Practice Lite
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE}
ExecStart=/usr/bin/python3 {REMOTE}/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
cmd = f"cat > /etc/systemd/system/voice_practice.service << 'EOF'\n{svc}\nEOF"
ssh_cmd(ssh, cmd, 'systemd')

# Nginx
nginx = """server {
    listen 80;
    server_name _;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
    }
}
"""
cmd = f"cat > /etc/nginx/sites-available/voice_practice << 'EOF'\n{nginx}\nEOF"
ssh_cmd(ssh, cmd, 'nginx config')
ssh_cmd(ssh, 'ln -sf /etc/nginx/sites-available/voice_practice /etc/nginx/sites-enabled/')

# 安装依赖
print('[4] 安装依赖...')
deps = ['flask', 'flask-cors', 'requests', 'python-docx', 'PyPDF2', 'python-pptx', 'openpyxl', 'edge-tts']
for d in deps:
    ssh_cmd(ssh, f'pip3 install {d} -q 2>&1 | tail -1', d)

# 启动
print('[5] 启动...')
ssh_cmd(ssh, 'systemctl daemon-reload')
ssh_cmd(ssh, 'systemctl enable voice_practice')
ssh_cmd(ssh, 'fuser -k 5000/tcp 2>/dev/null; echo done')
ssh_cmd(ssh, 'systemctl restart voice_practice')
time.sleep(2)
ssh_cmd(ssh, 'systemctl restart nginx')

# 验证
print('[6] 验证...')
time.sleep(2)
rc, out, _ = ssh_cmd(ssh, 'systemctl is-active voice_practice')
rc2, out2, _ = ssh_cmd(ssh, 'curl -s -m 3 http://127.0.0.1:5000/api/health 2>&1')

ssh.close()

print(f'\n{"="*60}')
print(f'服务状态: {out}')
print(f'API测试: {"OK" if "ok" in out2.lower() else "请稍后刷新"}')
print(f'访问: http://{DEPLOY_HOST}')
print(f'{"="*60}')
