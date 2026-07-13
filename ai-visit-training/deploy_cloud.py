from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
#!/usr/bin/env python3
"""一键部署语音对练到云端 HTTPS 服务器"""
import paramiko, os, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SERVER = DEPLOY_HOST
USER = DEPLOY_USER
PASSWORD = DEPLOY_PASSWORD
REMOTE = "/opt/voice_practice"

def ssh_cmd(ssh, cmd, desc=""):
    """执行远程命令"""
    if desc: print(f"  {desc}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    status = stdout.channel.recv_exit_status()
    if err.strip():
        print(f"    [stderr] {err.strip()[:200]}")
    return status, out.strip()

def upload_file(sftp, local, remote):
    """上传文件"""
    try:
        sftp.put(local, remote)
        print(f"  [OK] {os.path.basename(local)}")
        return True
    except Exception as e:
        print(f"  [ERR] {os.path.basename(local)}: {e}")
        return False

def upload_dir(ssh, sftp, local_dir, remote_dir):
    """递归上传目录"""
    try:
        for root, dirs, files in os.walk(local_dir):
            rel = os.path.relpath(root, local_dir)
            rpath = os.path.join(remote_dir, rel).replace('\\', '/')
            try:
                sftp.stat(rpath)
            except:
                ssh.exec_command(f"mkdir -p '{rpath}'", timeout=10)
            for f in files:
                lf = os.path.join(root, f)
                rf = os.path.join(rpath, f).replace('\\', '/')
                try:
                    sftp.put(lf, rf)
                except Exception as e:
                    print(f"    [WARN] {f}: {e}")
        print(f"  [OK] {os.path.basename(local_dir)}/ 目录")
    except Exception as e:
        print(f"  [WARN] 目录上传: {e}")

def main():
    print(f"=== 部署语音对练到 {SERVER} ===\n")
    
    # 连接
    print("[1/7] 连接服务器...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=10)
        sftp = ssh.open_sftp()
        print("  [OK] 已连接")
    except Exception as e:
        print(f"  [ERR] 连接失败: {e}")
        return
    
    try:
        # 创建目录
        print("[2/7] 创建目录...")
        ssh_cmd(ssh, f"mkdir -p {REMOTE}/static {REMOTE}/doc", "创建目录")
        
        # 上传核心文件
        print("[3/7] 上传核心文件...")
        BASE = r"d:\demo2"
        files = ["app.py", "static/index.html", "static/index_v2.html"]
        for f in files:
            local = os.path.join(BASE, f)
            remote = f"{REMOTE}/{f}"
            if os.path.exists(local):
                upload_file(sftp, local, remote)
            else:
                print(f"  [WARN] 不存在: {local}")
        
        # 上传知识库
        print("[4/7] 上传知识库文档...")
        doc_local = os.path.join(BASE, "doc")
        if os.path.exists(doc_local):
            upload_dir(ssh, sftp, doc_local, f"{REMOTE}/doc")
        
        # 安装依赖
        print("[5/7] 安装 Python 依赖...")
        ssh_cmd(ssh, "pip3 install flask flask-cors python-dotenv requests python-docx PyPDF2 python-pptx openpyxl -q 2>&1 | tail -3", "安装 pip 包")
        
        # 安装 nginx
        print("[6/7] 安装配置 Nginx + HTTPS...")
        ssh_cmd(ssh, "which nginx || (apt-get update -qq 2>/dev/null && apt-get install -y -qq nginx 2>/dev/null)", "安装 nginx")
        
        # 生成自签 SSL 证书
        ssl_cmd = """mkdir -p /etc/nginx/ssl && [ -f /etc/nginx/ssl/voice.crt ] || openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/voice.key -out /etc/nginx/ssl/voice.crt -subj "/C=CN/ST=BJ/L=BJ/O=Voice/CN=DEPLOY_HOST_PLACEHOLDER" 2>/dev/null"""
        ssh_cmd(ssh, ssl_cmd.replace("DEPLOY_HOST_PLACEHOLDER", DEPLOY_HOST), "SSL 证书")
        
        # Nginx 配置
        nginx_conf = '''server {
    listen 80;
    server_name DEPLOY_HOST_PLACEHOLDER;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name DEPLOY_HOST_PLACEHOLDER;

    ssl_certificate /etc/nginx/ssl/voice.crt;
    ssl_certificate_key /etc/nginx/ssl/voice.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        client_max_body_size 50m;
    }
}'''.replace("DEPLOY_HOST_PLACEHOLDER", DEPLOY_HOST)
        cmd = f"cat > /etc/nginx/sites-available/voice_practice << 'NGXEOF'\n{nginx_conf}\nNGXEOF"
        ssh_cmd(ssh, cmd, "写入 nginx 配置")
        ssh_cmd(ssh, "ln -sf /etc/nginx/sites-available/voice_practice /etc/nginx/sites-enabled/ 2>/dev/null; rm -f /etc/nginx/sites-enabled/default", "启用站点")
        status, out = ssh_cmd(ssh, "nginx -t 2>&1 && systemctl reload nginx", "检查并重载 nginx")
        print(f"    Nginx: {out[:100] if out else 'OK'}")
        
        # systemd 服务
        print("[7/7] 启动应用服务...")
        svc = f"""[Unit]
Description=Voice Practice AI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE}
ExecStart=/usr/bin/python3 {REMOTE}/app.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target"""
        escaped_svc = svc.replace("\\", "\\\\").replace("'", "'\\''")
        ssh_cmd(ssh, f"cat > /etc/systemd/system/voice_practice.service << 'SVCEOF'\n{svc}\nSVCEOF", "创建服务")
        ssh_cmd(ssh, "systemctl daemon-reload && systemctl enable voice_practice && systemctl restart voice_practice", "启动服务")
        time.sleep(3)
        
        # 检查状态
        status, out = ssh_cmd(ssh, "systemctl is-active voice_practice && journalctl -u voice_practice --no-pager -n 5", "检查状态")
        print(f"    服务状态: {out}")
        
    finally:
        sftp.close()
        ssh.close()
    
    print("\n" + "="*60)
    print("  部署完成！")
    print(f"  HTTPS: https://{SERVER}")
    print("  首次访问点击「高级」->「继续前往」")
    print(f"  查看日志: ssh root@{SERVER} 'journalctl -u voice_practice -f'")
    print("="*60)

if __name__ == '__main__':
    main()
