import subprocess, sys

def run(cmd, desc):
    print(f"\n>>> [{desc}]")
    print(f"    $ {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        out = r.stdout.strip()
        err = r.stderr.strip()
        if out:
            lines = out.split('\n')
            for line in lines[-10:]:
                print(f"    {line}")
        if r.returncode != 0 and err:
            elines = err.split('\n')
            for line in elines[-5:]:
                print(f"    {line}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print("    TIMEOUT")
        return False

print("="*50)
print("  安装 ONNX Runtime (FunASR轻量运行时)")
print("  不需要 PyTorch，仅约 50MB")
print("  Python:", sys.version)
print("="*50)

# Step 1: 安装 onnxruntime
ok1 = run(
    "pip install onnxruntime",
    "安装 ONNX Runtime"
)

# Step 2: 验证
print("\n" + "="*50)
if ok1:
    try:
        import onnxruntime as ort
        print(f"  onnxruntime: {ort.__version__} OK")
        
        # 验证 funasr 能否导入
        try:
            from funasr import AutoModel
            print("  funasr: OK (可导入)")
            
            # 测试模型加载（会下载约200MB）
            print("\n  正在测试 FunASR 模型加载（首次需下载）...")
            model = AutoModel(model="paraformer-zh", device="cpu", disable_pbar=True)
            print("  FunASR 模型加载成功!")
            print("\n" + "="*50)
            print("  全部完成! 运行 python app.py --full 即可")
            print("="*50)
            
        except Exception as e2:
            print(f"  FunASR 加载测试: {e2}")
            print("  但基础依赖已就绪，启动 app.py 时会自动处理")
            
    except ImportError:
        print("  onnxruntime: 导入失败")
else:
    print("  安装失败")

input("\n按回车键退出...")
