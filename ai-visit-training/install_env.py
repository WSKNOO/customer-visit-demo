import subprocess, sys, os

def run(cmd, desc, timeout=600):
    print(f"\n>>> [{desc}]")
    print(f"    $ {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        err = r.stderr.strip()
        if out:
            lines = out.split('\n')
            for line in lines[-12:]:
                print(f"    {line}")
        if r.returncode != 0 and err:
            elines = err.split('\n')
            for line in elines[-5:]:
                print(f"    {line}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print("    TIMEOUT")
        return False

print("="*55)
print("  创建 voice-practice 环境 (Python 3.11)")
print("  所有依赖完全兼容，无编译问题")
print("="*55)

# Step 1: 创建新环境 Python 3.11
ok1 = run(
    "conda create -y -n voice_practice python=3.11",
    "创建conda环境 voice_practice (Python 3.11)"
)

if not ok1:
    # 环境可能已存在，继续
    print("  (环境可能已存在，继续...)")

# Step 2: 在新环境中安装所有依赖
print("\n" + "="*55)
print("  在新环境中安装依赖...")
print("="*55)

# 用 conda run 在目标环境中执行pip安装
ok2 = run(
    'conda run -n voice_practice pip install flask flask-cors requests python-dotenv edge-tts modelscope funasr onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn',
    "安装全部依赖 (清华镜像源加速)"
)

if ok2:
    # Step 3: 验证
    print("\n" + "="*55)
    ok3 = run(
        'conda run -n voice_practice python -c "import torch; print(\'torch:\',torch.__version__); import funasr; print(\'funasr: OK\'); import onnxruntime; print(\'onnxruntime:\',onnxruntime.__version__); import flask; print(\'flask: OK\')"',
        "验证所有包"
    )
    
    if ok3:
        print("\n" + "="*55)
        print("  SUCCESS! 全部安装完成!")
        print("="*55)
        print()
        print("  启动方式:")
        print("  1) 激活环境:  conda activate voice_practice")
        print("  2) 进入目录:  cd d:\\demo2")
        print("  3) 运行:      python app.py --full")
        print()
        print("  或者一键启动:")
        print("    conda run -n voice_practice python d:/demo2/app.py --full")

input("\n按回车键退出...")
