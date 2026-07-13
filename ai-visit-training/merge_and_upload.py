from deploy_env import DEPLOY_HOST, DEPLOY_PORT, DEPLOY_USER, DEPLOY_PASSWORD
"""合并 knowcard_output 到 knowcard，然后上传云端"""
import os, sys, shutil, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'd:/demo2'
output_dir = os.path.join(BASE, 'knowcard_output')
knowcard_dir = os.path.join(BASE, 'knowcard')

# Step 1: 合并知识卡片
print('[1] 合并卡片到 knowcard...')
merged = 0
# knowcard_output 结构: AI/场景名/xxx.json  或  标品/场景名/xxx.json  或  解决方案/场景名/xxx.json
# knowcard 结构:       AI/场景名/xxx.json  (同)
for root, dirs, files in os.walk(output_dir):
    for f in files:
        if f.endswith('.json'):
            src = os.path.join(root, f)
            rel = os.path.relpath(src, output_dir)
            dst = os.path.join(knowcard_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            merged += 1
print(f'  合并了 {merged} 个卡片文件')

# Step 2: 上传到云端
print('[2] 上传到云端...')
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(DEPLOY_HOST, username=DEPLOY_USER, password=DEPLOY_PASSWORD, port=DEPLOY_PORT, timeout=15)

REMOTE = '/opt/voice_practice'

# 创建目录
print('  创建目录...')
all_dirs = set()
for root, dirs, files in os.walk(knowcard_dir):
    for d in dirs:
        rel = os.path.relpath(os.path.join(root, d), knowcard_dir).replace('\\', '/')
        all_dirs.add(rel)
for d in sorted(all_dirs):
    stdin, stdout, stderr = ssh.exec_command(f'mkdir -p {REMOTE}/knowcard/{d}', timeout=5)
    stdout.read()

# 上传文件（限制总时间）
print('  上传文件...')
sftp = ssh.open_sftp()
count, skip = 0, 0
for root, dirs, files in os.walk(knowcard_dir):
    for f in files:
        local = os.path.join(root, f)
        rel = os.path.relpath(local, knowcard_dir).replace('\\', '/')
        remote = f'{REMOTE}/knowcard/{rel}'
        try:
            sftp.put(local, remote)
            count += 1
            if count % 100 == 0: print(f'    {count}...')
        except:
            skip += 1
sftp.close()
print(f'  上传: {count} 文件, 跳过: {skip}')

# 重启
print('[3] 重启服务...')
ssh.exec_command('systemctl restart voice_practice', timeout=5)
time.sleep(2)
ssh.exec_command('systemctl restart nginx', timeout=5)

ssh.close()
print('Done')
