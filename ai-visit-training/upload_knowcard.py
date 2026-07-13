from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
"""仅上传 knowcard 到云端"""
import paramiko, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=15)

def cm(ssh, c):
    stdin, stdout, stderr = ssh.exec_command(c, timeout=30)
    rc = stdout.channel.recv_exit_status()
    return rc

REMOTE = '/opt/voice_practice'
knowcard = 'd:/demo2/knowcard'

# 创建所有目录
print('创建目录...')
all_dirs = set()
for root, dirs, files in os.walk(knowcard):
    for d in dirs:
        rel = os.path.relpath(os.path.join(root, d), knowcard).replace('\\', '/')
        all_dirs.add(rel)
for d in sorted(all_dirs):
    cm(ssh, f'mkdir -p {REMOTE}/knowcard/{d}')
print(f'  {len(all_dirs)} 个目录')

# 上传文件
print('上传文件...')
sftp = ssh.open_sftp()
count = 0
for root, dirs, files in os.walk(knowcard):
    for f in files:
        local = os.path.join(root, f)
        rel = os.path.relpath(local, knowcard).replace('\\', '/')
        remote = f'{REMOTE}/knowcard/{rel}'
        try:
            sftp.put(local, remote)
            count += 1
            if count % 50 == 0:
                print(f'  {count}...')
        except Exception as e:
            pass
sftp.close()
print(f'  完成: {count} 个文件')

# 重启
print('重启服务...')
cm(ssh, 'systemctl restart voice_practice')
import time; time.sleep(2)
cm(ssh, 'systemctl restart nginx')

# 验证
stdin, stdout, stderr = ssh.exec_command('curl -s http://127.0.0.1:5000/api/scenes 2>&1', timeout=10)
out = stdout.read().decode('utf-8', errors='ignore')
print(f'场景API: {out[:200]}')
ssh.close()
print('Done')
