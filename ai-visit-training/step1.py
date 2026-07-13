from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=20)
i,o,e = s.exec_command("apt-get install -y nginx openssl 2>&1 | tail -3", timeout=180)
print(o.read().decode()[-200:] or e.read().decode()[-200:])
s.close()
