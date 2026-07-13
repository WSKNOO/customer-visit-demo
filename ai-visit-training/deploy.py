from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
# -*- coding: utf-8 -*-
import paramiko, os, sys, io, time, json, re, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

H, P, U, PW = DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
LOCAL = os.path.dirname(os.path.abspath(__file__))
REMOTE = "/root/voice-practice"

def runcmd(ssh, c, t=60):
    i, o, e = ssh.exec_command(c, timeout=t)
    return o.read().decode('utf-8', errors='ignore'), e.read().decode('utf-8', errors='ignore')

print("[1/6] Connecting...", flush=True)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(H, port=P, username=U, password=PW, timeout=30)
print("  OK", flush=True)

print("[2/6] Setup server...", flush=True)
runcmd(ssh, "mkdir -p {}/static {}/doc".format(REMOTE, REMOTE))
o, e = runcmd(ssh, "python3 --version 2>&1 && pip3 install flask flask-cors requests python-dotenv -q 2>&1", t=120)
print("  {}".format(o.strip()[:100] if o.strip() else e.strip()[:100]), flush=True)

print("[3/6] Upload files...", flush=True)
sftp = ssh.open_sftp()
for f in ['app.py', '.env', 'requirements-lite.txt']:
    lp = os.path.join(LOCAL, f)
    if os.path.exists(lp):
        sftp.put(lp, "{}/{}".format(REMOTE, f))
        print("  UP: {}".format(f), flush=True)

sd = os.path.join(LOCAL, 'static')
if os.path.exists(sd):
    for item in os.listdir(sd):
        lp = os.path.join(sd, item)
        if os.path.isfile(lp):
            sftp.put(lp, "{}/static/{}".format(REMOTE, item))

def up_doc(d, prefix):
    for item in os.listdir(d):
        if item.startswith('.'): continue
        lp = os.path.join(d, item)
        rp = "{}/{}/{}".format(REMOTE, prefix, item)
        if os.path.isfile(lp):
            sftp.put(lp, rp)
        elif os.path.isdir(lp):
            try: sftp.mkdir(rp)
            except: pass
            up_doc(lp, "{}/{}".format(prefix, item))

dd = os.path.join(LOCAL, 'doc')
if os.path.exists(dd):
    print("  UP: doc/", flush=True)
    up_doc(dd, "doc")
sftp.close()

print("[4/6] Configure host=0.0.0.0...", flush=True)
with open(os.path.join(LOCAL, 'app.py'), 'r', encoding='utf-8') as f:
    code = f.read()
if '0.0.0.0' not in code:
    code = re.sub(r"app\.run\([^)]*\)", "app.run(host='0.0.0.0', port=5000)", code)

tf = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
tf.write(code)
tf.close()
sftp2 = ssh.open_sftp()
sftp2.put(tf.name, "{}/app.py".format(REMOTE))
sftp2.close()
os.unlink(tf.name)
print("  OK", flush=True)

print("[5/6] Start service...", flush=True)
runcmd(ssh, "fuser -k 5000/tcp 2>/dev/null; sleep 1")
runcmd(ssh, "cd {} && nohup python3 app.py > server.log 2>&1 &".format(REMOTE))
time.sleep(4)

print("[6/6] Verify...", flush=True)
o, _ = runcmd(ssh, "curl -s http://127.0.0.1:5000/api/health")
if o.strip():
    print("  Health: {}".format(o.strip()[:200]), flush=True)
else:
    o2, _ = runcmd(ssh, "cat {}/server.log | head -20".format(REMOTE))
    print("  Log: {}".format(o2[:300] if o2 else "empty"), flush=True)

print("\n" + "="*50)
print("DEPLOY COMPLETE!")
print("URL: http://{}:5000".format(H))
print("ACTION: Open port 5000 in security group (TCP)")
print("="*50, flush=True)
ssh.close()
