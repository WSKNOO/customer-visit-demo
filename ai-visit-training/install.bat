@echo off
chcp 65001 >nul
echo ============================================
echo   安装 FFmpeg (FunASR音频转换必需)
echo ============================================
echo.
echo 正在下载 FFmpeg (约 80MB)...
echo.

powershell -Command "& { $url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'; $out = '%TEMP%\ffmpeg.zip'; Write-Host 'Downloading...'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri $url -OutFile $out; Write-Host 'Extracting...'; Expand-Archive -Path $out -DestinationPath 'C:\ffmpeg-temp' -Force; Move-Item 'C:\ffmpeg-temp\ffmpeg-*-essentials\bin' 'C:\ffmpeg' -Force; Remove-Item 'C:\ffmpeg-temp' -Recurse -Force; Remove-Item $out -Force; Write-Host 'Done!' }"

REM 添加到系统PATH
setx PATH "%PATH%;C:\ffmpeg" >nul

echo.
echo ============================================
echo   安装完成! 请重启终端后运行:
echo   D:\anaconda\envs\voice_practice\python.exe d:/demo2/app.py --full
echo ============================================
pause
