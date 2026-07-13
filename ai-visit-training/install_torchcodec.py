import subprocess
print("安装 torchcodec (让torchaudio能解码webm)...")
r = subprocess.run([
    r'D:\anaconda\envs\voice_practice\python.exe', '-m', 'pip', 'install', 'torchcodec',
    '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple',
    '--trusted-host', 'pypi.tuna.tsinghua.edu.cn'
], capture_output=True, text=True, timeout=120)
print(r.stdout[-500:] if r.stdout else '')
if r.stderr: print('STDERR:', r.stderr[-300:])
print("成功!" if r.returncode == 0 else f"失败: {r.returncode}")
input("\n按回车退出...")
