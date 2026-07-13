from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
import paramiko, io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=8)

tests = [
    ('systemctl is-active voice_practice nginx', '服务状态'),
    ('ls /opt/voice_practice/knowcard/ 2>/dev/null | head -3', 'knowcard一级目录'),
    ('find /opt/voice_practice/knowcard -name "*.json" 2>/dev/null | wc -l', '知识卡片数'),
    ('find /opt/voice_practice/knowcard -type f 2>/dev/null | wc -l', '总文件数'),
    ('du -sh /opt/voice_practice/knowcard 2>/dev/null || echo "不存在"', 'knowcard大小'),
    ('curl -s -m 3 http://127.0.0.1:5000/api/scenes 2>&1', '场景API'),
]

for cmd, desc in tests:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    if not out:
        out = stderr.read().decode('utf-8', errors='ignore').strip()
    
    # Parse scene API
    if desc == '场景API' and out:
        try:
            d = json.loads(out)
            out = f"{d['total_groups']} groups, {d['total_scenes']} scenes"
        except:
            out = out[:80]
    
    print(f'{desc}: {out or "(empty)"}')
ssh.close()
