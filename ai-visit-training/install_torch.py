import subprocess, sys

def run(cmd, desc):
    print(f"\n>>> [{desc}]")
    print(f"    $ {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
        out = r.stdout.strip()
        err = r.stderr.strip()
        if out:
            # 只显示最后几行
            lines = out.split('\n')
            for line in lines[-15:]:
                print(f"    {line}")
        if r.returncode != 0 and err:
            elines = err.split('\n')
            for line in elines[-5:]:
                print(f"    {line}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print("    TIMEOUT (30min)")
        return False

print("="*50)
print("  安装 PyTorch (CPU) - 完整模式依赖")
print("  Python:", sys.version)
print("="*50)

ok = run(
    "conda install -y -c pytorch torch torchaudio cpuonly",
    "Conda安装PyTorch CPU版"
)

if ok:
    print("\n" + "="*50)
    print("  SUCCESS! PyTorch 安装成功")
    print("="*50)
    
    # 验证
    import importlib
    spec = importlib.util.find_spec("torch")
    if spec:
        print("  torch: OK (已找到)")
    else:
        print("  torch: 未找到 (可能需要重启终端)")
else:
    print("\n安装失败，请检查上方错误信息")

input("\n按回车键退出...")
