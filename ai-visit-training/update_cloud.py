from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
"""快速更新云端代码"""
import paramiko, time, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=10)

print('上传代码...')
sftp = ssh.open_sftp()
sftp.put('d:/demo2/app.py', '/opt/voice_practice/app.py')
sftp.put('d:/demo2/static/index_v2.html', '/opt/voice_practice/static/index.html')
sftp.close()
print('  app.py + index.html OK')

print('重启...')
ssh.exec_command('systemctl restart voice_practice', timeout=5)
ssh.exec_command('systemctl restart nginx', timeout=5)
time.sleep(2)

_, out, _ = ssh.exec_command('curl -s -m3 http://127.0.0.1:5000/api/health', timeout=5)
print('  状态:', out.read().decode('utf-8', errors='ignore')[:80])
ssh.close()
print(f'Done! http://{DEPLOY_HOST}')
