from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=20)
cmds = [
    'which nginx 2>/dev/null || echo NO_NGINX',
    'which certbot 2>/dev/null || echo NO_CERTBOT',
    'python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"',
    'ss -tlnp | grep -E ":80|:443" || echo PORTS_FREE',
    'apt list --installed 2>/dev/null | grep -i nginx || echo NGINX_NOT_INSTALLED',
]
for c in cmds:
    i,o,e = s.exec_command(c, timeout=10)
    r = (o.read().decode().strip() + e.read().decode().strip())[:120]
    print('=> ' + r)
s.close()
