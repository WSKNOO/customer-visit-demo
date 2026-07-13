# -*- coding: utf-8 -*-
"""FunASR 最小化安装 - 只装核心包"""
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def run(c, d):
    print(f'\n>>> [{d}]')
    print(f'    $ {c}')
    r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=300)
    for line in (r.stdout or '').strip().split('\n')[-3:]:
        if line.strip(): print(f'    {line}')
    if r.returncode != 0:
        err = (r.stderr or '').strip()[-200:]
        if err: print(f'    [ERR] {err}')
    return r.returncode == 0

print('='*55)
print('FunASR 轻量安装')
print('='*55)

# Step 1: 安装 funasr 核心包 (跳过需要编译的子依赖)
print('\n[1/2] 安装 FunASR...')
ok1 = run('pip install "funasr>=1.0" --no-deps --no-build-isolation --prefer-binary', 'funasr核心')

if ok1:
    # Step 2: 验证
    print('\n[2/2] 验证...')
    run('python -c "from funasr import AutoModel; m=AutoModel(model=\'paraformer-zh\', vad_model=\'fsmn-vad\', device=\'cpu\', disable_pbar=True); print(\'OK: FunASR就绪!\')"', '验证FunASR')

    print('\n' + '='*55)
    print('SUCCESS! 运行: python app.py --full')
    
else:
    print('\n[方案B] 尝试 conda 安装（更稳定）...')
    ok2 = run('conda install -y -c conda-forge "funasr>=1.0" --no-update-deps', 'Conda FunASR')
    
    if ok2:
        run('python -c "from funasr import AutoModel; print(\'OK\')"', '验证')
        print('='*55 + '\n成功! 运行: python app.py --full')
    else:
        # 最终：只装 modelscope，让用户手动处理
        print('\n[方案C] 安装 ModelScope Hub 客户端...')
        run('pip install modelscope --quiet', 'ModelScope')
        print('')
        print('='*55)
        print('自动安装均失败。请选择:')
        print()
        print('  A) 安装 Visual Studio Build Tools 后重试 pip install')
        print('     winget install Microsoft.VisualStudio.2022.BuildTools')
        print('     勾选 "C++桌面开发" 工作负载')
        print('')
        print('  B) 用 Conda (推荐):')
        print('     conda install -c conda-forge funasr')
        print('')
        print('  C) 先用轻量模式:')
        print('     python app.py')
        print('')
        print('='*55)
        input('按回车退出...')

input('\n按回车关闭...')
