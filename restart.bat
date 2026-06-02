@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [*] 正在重启 Multi-Agent Chat 服务器...
echo.

call stop.bat
echo.
timeout /t 1 >nul

call start.bat
