from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print('Connecting...', flush=True)
ssh.connect(DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD, timeout=20)
sftp = ssh.open_sftp()

count = 0
def up_doc(d, prefix):
    global count
    for item in os.listdir(d):
        if item.startswith('.'): continue
        lp = os.path.join(d, item)
        rp = '/root/voice-practice/' + prefix + '/' + item
        if os.path.isfile(lp):
            sftp.put(lp, rp)
            count += 1
            if count % 10 == 0:
                print('  Uploaded {} files...'.format(count), flush=True)
        elif os.path.isdir(lp):
            try: sftp.mkdir(rp)
            except: pass
            up_doc(lp, prefix + '/' + item)

print('Uploading doc/ folder...', flush=True)
up_doc(r'd:\demo2\doc', 'doc')
sftp.close()
ssh.close()
print('DONE! Total files: {}'.format(count), flush=True)
