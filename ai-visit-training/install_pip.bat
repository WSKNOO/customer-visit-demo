@echo off
chcp 65001 >nul
echo ============================================
echo   FunASR 快速安装 (Conda方式)
echo ============================================

echo.
echo [1/4] 检查 Conda 环境...
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo     ERROR: 未找到 conda!
    echo.
    echo   请先安装 Anaconda 或 Miniconda:
    echo     winget install Anaconda.Miniconda3
    pause
    exit /b 1
)
conda --version
python --version

echo.
echo [2/4] 安装 PyTorch (CPU版) + FunASR...
echo     这一步需要下载约500MB，请耐心等待...
conda install -y -c pytorch -c conda-forge funasr modelscope torchaudio 2>&1

echo.
echo ============================================
echo   验证...
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
try:
    import funasr
    print('SUCCESS! FunASR 已就绪')
    print('运行: python app.py --full')
except ImportError as e:
    print(f'FAILED: {e}')
"
echo ============================================
pause
