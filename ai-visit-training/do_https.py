from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, sys, io, os, time, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print('[1] Connect', flush=True)
s.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=20)

# 2: 生成证书 + 上传 https_server.py
print('[2] Setup SSL', flush=True)
i,o,e = s.exec_command(f'openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout /root/voice-practice/server.key -out /root/voice-practice/server.crt -subj "/CN={DEPLOY_HOST}" 2>&1', timeout=30)
r = o.read().decode() + e.read().decode()
print('  cert:', ('OK' if not r else r[:80]), flush=True)

sf = s.open_sftp()
sf.put(r'd:\demo2\https_server.py', '/root/voice-practice/https_server.py')
sf.close()

# 3: 停旧进程，启动HTTPS
print('[3] Start HTTPS server (port 443)', flush=True)
s.exec_command('fuser -k 5000/tcp 2>/dev/null; fuser -k 443/tcp 2>/dev/null')
time.sleep(1)
s.exec_command('cd /root/voice-practice && nohup python3 https_server.py > https.log 2>&1 &')
time.sleep(4)

# 4: 验证
print('[4] Verify', flush=True)
i,o,e = s.exec_command('curl -sk https://127.0.0.1:443/api/health 2>&1')
h = o.read().decode().strip()
i,o,e = s.exec_command('curl -sI http://127.0.0.1:5000 2>&1 | head -5')
redir = o.read().decode().strip()

print('')
print('=' * 55)
print('HTTPS DEPLOY COMPLETE!')
print('=' * 55)
print(f'  HTTPS: https://{DEPLOY_HOST}:443')
print(f'  HTTP->HTTPS redirect: http://{DEPLOY_HOST}:5000')
print(f'')
print(f'  Health: {h[:80]}')
print(f'  Redirect: {("301 OK" if "301" in redir else redir[:60])}')
print(f'')
print(f'  ACTION:')
print(f'  1. Open port 443 in security group (TCP)')
print(f'  2. Open port 5000 in security group (for redirect)')
print(f'  3. Browser: Advanced -> Proceed to site (unsafe)')
print(f'     (self-signed cert, fully functional for mic!)')
print('=' * 55, flush=True)
s.close()
