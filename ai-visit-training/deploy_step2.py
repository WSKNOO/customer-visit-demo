from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, os, sys, io, re, tempfile, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print('[1] Connecting...', flush=True)
ssh.connect(DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD, timeout=20)

print('[2] Installing deps...', flush=True)
i, o, e = ssh.exec_command('pip3 install flask flask-cors requests python-dotenv -q 2>&1', timeout=120)
r = o.read().decode() + e.read().decode()
print('  Done: ' + (r[-80:] if r else 'ok'), flush=True)

print('[3] Fixing host=0.0.0.0...', flush=True)
with open(r'd:\demo2\app.py', 'r', encoding='utf-8') as f:
    code = f.read()
if '0.0.0.0' not in code:
    code = re.sub(r'app\.run\([^)]*\)', "app.run(host='0.0.0.0', port=5000)", code)
    tf = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    tf.write(code)
    tf.close()
    sftp = ssh.open_sftp()
    sftp.put(tf.name, '/root/voice-practice/app.py')
    sftp.close()
    os.unlink(tf.name)
    print('  Fixed!', flush=True)
else:
    print('  Already 0.0.0.0', flush=True)

print('[4] Starting service...', flush=True)
i, o, e = ssh.exec_command("fuser -k 5000/tcp 2>/dev/null; sleep 1; cd /root/voice-practice && nohup python3 app.py > server.log 2>&1 &")
o.read()
time.sleep(4)

print('[5] Verifying...', flush=True)
i, o, e = ssh.exec_command('curl -s http://127.0.0.1:5000/api/health 2>&1')
health = o.read().decode()
if health.strip():
    print('  Health: ' + health.strip()[:200], flush=True)
else:
    i, o, e = ssh.exec_command('cat /root/voice-practice/server.log | head -15')
    log = o.read().decode()
    print('  Log: ' + (log[:400] if log else 'empty'), flush=True)

print('')
print('=' * 50)
print('DEPLOY COMPLETE!')
print(f'URL: http://{DEPLOY_HOST}:5000')
print('NOTE: Open port 5000 in security group!')
print('=' * 50, flush=True)
ssh.close()
