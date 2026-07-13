from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
"""快速部署到云端 - 只上传代码文件"""
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST, PORT, USER, PWD = DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
REMOTE = '/opt/voice_practice'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=10)
sftp = ssh.open_sftp()

print('1. 停止服务...')
ssh.exec_command('systemctl stop voice_practice')
import time; time.sleep(1)

print('2. 上传文件...')
for f in ['app.py', 'static/index.html']:
    remote_path = f'{REMOTE}/{f}'
    sftp.put(f'd:/demo2/{f}', remote_path)
    print(f'  ✅ {f}')

print('3. 重启服务...')
ssh.exec_command('systemctl start voice_practice')
time.sleep(2)

print('4. 验证...')
stdin, stdout, stderr = ssh.exec_command('systemctl is-active voice_practice')
print(f'  服务: {stdout.read().decode().strip()}')

stdin, stdout, stderr = ssh.exec_command('curl -s -m3 http://127.0.0.1:5000/api/scenes 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print(f\'{d[\"total_groups\"]} groups, {d[\"total_scenes\"]} scenes\')"')
out = stdout.read().decode().strip() or stderr.read().decode().strip()
print(f'  API: {out}')

sftp.close()
ssh.close()
print(f'\n✅ 部署完成！http://{DEPLOY_HOST}')
