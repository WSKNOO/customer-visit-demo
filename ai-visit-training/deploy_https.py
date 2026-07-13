from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
"""一键配置 HTTPS - 使用自签名证书 + Python ssl 模块"""
import paramiko, sys, io, os, time, re, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

H, U, PW = DEPLOY_HOST, DEPLOY_USER, DEPLOY_PASSWORD
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print('[1/5] Connecting...', flush=True)
s.connect(H, username=U, password=PW, port=22, timeout=20)

# Step 2: 安装 nginx + 生成自签名证书
print('[2/5] Installing nginx & generating SSL cert...', flush=True)
cmds = '''
apt-get update -qq && apt-get install -y -qq nginx 2>&1 | tail -1
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/voice-practice.key \
  -out /etc/nginx/ssl/voice-practice.crt \
  -subj "/CN=DEPLOY_HOST_PLACEHOLDER/O=VoicePractice/C=CN" 2>&1
echo "CERT_DONE"
'''.replace('DEPLOY_HOST_PLACEHOLDER', DEPLOY_HOST)
i,o,e = s.exec_command(cmds, timeout=120)
r = o.read().decode() + e.read().decode()
if 'CERT_DONE' in r or 'already exists' in r:
    print('  OK: Cert generated', flush=True)
else:
    print('  Output:', r[-100:], flush=True)

# Step 3: 写入 nginx 配置
print('[3/5] Writing nginx config...', flush=True)
nginx_conf = '''server {
    listen 80;
    server_name DEPLOY_HOST_PLACEHOLDER;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name DEPLOY_HOST_PLACEHOLDER;

    ssl_certificate /etc/nginx/ssl/voice-practice.crt;
    ssl_certificate_key /etc/nginx/ssl/voice-practice.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for future use)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
'''.replace('DEPLOY_HOST_PLACEHOLDER', DEPLOY_HOST)

# 用临时文件上传
tf = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False, encoding='utf-8')
tf.write(nginx_conf)
tf.close()
sf = s.open_sftp()
sf.put(tf.name, '/tmp/voice-practice-nginx.conf')
sf.close()
os.unlink(tf.name)

i,o,e = s.exec_command('cp /tmp/voice-practice-nginx.conf /etc/nginx/sites-available/voice-practice && ln -sf /etc/nginx/sites-available/voice-practice /etc/nginx/sites-enabled/voice-practice && rm -f /etc/nginx/sites-enabled/default && nginx -t 2>&1')
r = o.read().decode() + e.read().decode()
print('  Nginx test:', ('OK' if 'successful' in r or 'test is successful' in r else r[:150]), flush=True)

# Step 4: 重启服务
print('[4/5] Restarting services...', flush=True)
s.exec_command('fuser -k 5000/tcp 2>/dev/null')
time.sleep(1)
s.exec_command('cd /root/voice-practice && nohup python3 app.py > server.log 2>&1 &')
s.exec_command('systemctl restart nginx 2>&1 || service nginx restart 2>&1 || nginx 2>&1')
time.sleep(3)

# Step 5: 验证
print('[5/5] Verifying...', flush=True)
i,o,e = s.exec_command('curl -sk https://127.0.0.1:5000/api/health 2>&1')
https_result = o.read().decode().strip()
i,o,e = s.exec_command('curl -s http://127.0.0.1/api/health 2>&1')
http_redirect = o.read().decode().strip()

print('')
print('=' * 55)
print('HTTPS DEPLOY COMPLETE!')
print('=' * 55)
print('')
print(f'  HTTPS URL: https://{DEPLOY_HOST}')
print(f'  HTTP URL:  http://{DEPLOY_HOST}  (auto redirect to HTTPS)')
print('')
print('  Health check (HTTPS):', https_result[:80] if https_result else 'FAILED')
print('  HTTP redirect:', ('301 OK' if '301' in http_redirect or 'redirect' in http_redirect.lower() else http_redirect[:60]), flush=True)
print('')
print('  ACTION REQUIRED:')
print('  1. Open port 443 in security group (TCP)')
print('  2. Port 80 also needed for HTTP->HTTPS redirect')
print('  3. Browser will show certificate warning - click Advanced -> Proceed')
print('     (Self-signed cert, fully functional for voice input)')
print('=' * 55, flush=True)
s.close()
