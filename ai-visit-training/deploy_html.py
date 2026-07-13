from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD, timeout=20)
sftp = ssh.open_sftp()
sftp.put(r'd:\demo2\static\index.html', '/root/voice-practice/static/index.html')
sftp.close()
ssh.exec_command('fuser -k 5000/tcp 2>/dev/null')
time.sleep(1)
ssh.exec_command('cd /root/voice-practice && nohup python3 app.py > server.log 2>&1 &')
time.sleep(3)
i,o,e=ssh.exec_command('curl -s http://127.0.0.1:5000/api/health')
print(o.read().decode().strip()[:100])
ssh.close()
