from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print('[1/4] Connecting...', flush=True)
s.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=20)

# 2: 上传文件
print('[2/4] Uploading files...', flush=True)
sf = s.open_sftp()
sf.put(r'd:\demo2\app.py', '/root/voice-practice/app.py')
sf.put(r'd:\demo2\static\index.html', '/root/voice-practice/static/index.html')
sf.put(r'd:\demo2\requirements-lite.txt', '/root/voice-practice/requirements-lite.txt')
sf.close()
print('  Files uploaded', flush=True)

# 3: 安装edge-tts + 重启
print('[3/4] Installing edge-tts...', flush=True)
i,o,e = s.exec_command('pip3 install edge-tts -q 2>&1', timeout=120)
r = o.read().decode() + e.read().decode()
print('  ' + ('OK' if not r or 'already' in r.lower() else r[-80:]), flush=True)

# 4: 重启服务(HTTPS模式)
print('[4/4] Restarting HTTPS service...', flush=True)
s.exec_command('fuser -k 5000/tcp 2>/dev/null; fuser -k 443/tcp 2>/dev/null')
time.sleep(1)
s.exec_command('cd /root/voice-practice && nohup python3 https_server.py > https.log 2>&1 &')
time.sleep(4)

# 验证
i,o,e = s.exec_command('curl -sk https://127.0.0.1:443/api/health')
h = o.read().decode().strip()[:100]
i,o,e = s.exec_command('curl -sk https://127.0.0.1:443/api/tts/voices | head -c 200')
v = o.read().decode().strip()[:100]
i,o,e = s.exec_command('cat /root/voice-practice/https.log | tail -5')
log = o.read().decode().strip()[:150]

print('')
print('=' * 55)
print('DEPLOY COMPLETE!')
print('=' * 55)
print(f'  Health: {h}')
print(f'  TTS Voices: {("OK" if "voices" in v else v[:80])}')
print(f'  Log: {log}')
print(f'' )
print(f'  URL: https://{DEPLOY_HOST}:443')
print(f'  New feature: AI voice playback with male voice!')
print(f'=' * 55, flush=True)
s.close()
