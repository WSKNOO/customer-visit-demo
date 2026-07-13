@echo off
chcp 65001 >nul
echo ============================================
echo   FunASR 完整模式依赖安装脚本
echo ============================================

echo.
echo [1/5] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo.
echo [2/5] 安装 Cython (C编译器)...
pip install cython==3.0.10 --no-build-isolation
if errorlevel 1 (
    echo WARNING: Cython failed, continuing...
)

echo.
echo [3/5] 安装 PyTorch CPU (避免CUDA问题)...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu/stable.html

echo.
echo [4/5] 安装 ModelScope + FunASR...
pip install modelscope
pip install funasr --no-build-isolation
if errorlevel 1 (
    echo.
    echo ============================================
    echo   FunASR 安装失败！
    echo.
    echo   可能原因：
    echo   1. 缺少 C++ 编译工具
    echo      → 安装 Visual Studio 2022 "C++桌面开发" 工作负载
    echo      → 或运行: winget install Microsoft.VisualStudio.2022.BuildTools
    echo   2. 编辑距离库(editdistance)需要Cython编译
    echo.
    echo   建议: 使用 conda install -c conda-forge funasr
    echo ============================================
    pause
    exit /b 1
)

echo.
echo [5/5] 可选: pydub (音频转换)...
pip install pydub || echo [SKIP]

echo.
echo ============================================
echo   验证安装...
python -c "import funasr; print('FunASR OK!')" && (
    echo   SUCCESS!
) || (
    echo   FAILED - 请检查上方错误信息
)
echo ============================================
echo.
echo 现在可以运行完整模式了：
echo   python app.py --full
echo.
pause
