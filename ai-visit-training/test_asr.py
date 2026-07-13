"""测试 FunASR 能否正确识别 WAV 文件"""
import sys, os, glob, time, wave

# 找最新的 debug wav 文件
debug_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'debug_asr_*.wav')))
if not debug_files:
    print("未找到 debug_asr_*.wav 文件，请先录音一次")
    sys.exit(1)

wav_path = debug_files[-1]
print(f"测试文件: {wav_path}")
print(f"文件大小: {os.path.getsize(wav_path)/1024:.1f}KB")

# 用 Python wave 检查 WAV 格式
print("\n=== WAV 文件信息 ===")
try:
    with wave.open(wav_path, 'rb') as wf:
        print(f"通道数: {wf.getnchannels()}")
        print(f"采样宽度: {wf.getsampwidth()*8} bit")
        print(f"采样率: {wf.getframerate()} Hz")
        print(f"帧数: {wf.getnframes()}")
        duration = wf.getnframes() / wf.getframerate()
        print(f"时长: {duration:.2f}s")
        
        # 读前100帧看看数据是否正常
        frames = wf.readframes(min(100, wf.getnframes()))
        import struct
        if wf.getsampwidth() == 2:
            samples = struct.unpack(f'<{len(frames)//2}h', frames)
            max_val = max(abs(s) for s in samples)
            print(f"前100帧最大振幅: {max_val} (0=静音, >100=有声音)")
except Exception as e:
    print(f"WAV解析错误: {e}")
    print("文件格式可能不合法！")

# 测试 FunASR 识别
print("\n=== FunASR 识别测试 ===")
sys.path.insert(0, os.path.dirname(__file__))
from app import get_asr_model

model = get_asr_model()
if model is None or model == 'error':
    print("FunASR 模型未就绪!")
    sys.exit(1)

print("模型已加载，开始识别...")
t0 = time.time()
result = model.generate(input=wav_path)
elapsed = time.time() - t0

text = ''
if result and len(result) > 0:
    item = result[0]
    if isinstance(item, dict):
        text = item.get("text", "")
    elif isinstance(item, str):
        text = item

print(f"识别耗时: {elapsed:.2f}s")
print(f"识别结果: '{text}'")
print(f"结果类型: {type(result)}, 长度: {len(result) if result else 0}")

if result:
    print(f"\n完整返回: {result[:3] if isinstance(result, list) else result}")
