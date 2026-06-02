@echo off
chcp 65001 >nul
title Multi-Agent Chat Debug Launcher
cd /d "%~dp0"
cls

echo ========================================
echo   Multi-Agent Chat Debug 启动器
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] 未找到 Python
    pause
    exit /b 1
)

:: 检查依赖
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [*] 安装依赖...
    pip install fastapi uvicorn -q
)

:: 启动服务器（在新窗口显示完整日志）
echo [*] 启动后端服务器（Debug 模式，显示完整日志）...
start "Debug Server" cmd /k "cd /d "%~dp0" && echo [Server] 正在启动... && python server.py"

:: 等待服务器就绪
echo [*] 等待服务器就绪...
set /a attempts=0
:wait_loop
set /a attempts+=1
if %attempts% gtr 30 (
    echo [X] 等待超时
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul

:: 检测端口（8088 为主，兼容自动切换）
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/', timeout=1)" >nul 2>&1
if not errorlevel 1 (
    set PORT=8088
    goto :ready
)
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8089/', timeout=1)" >nul 2>&1
if not errorlevel 1 (
    set PORT=8089
    goto :ready
)
goto :wait_loop

:ready
echo [*] 服务器已就绪: http://localhost:%PORT%
echo [*] 正在打开浏览器...
start http://localhost:%PORT%

echo.
echo ========================================
echo   启动完成！
echo   地址: http://localhost:%PORT%
echo ========================================
echo.
echo [Debug 说明]
echo   - 服务器在标题为 [Debug Server] 的窗口中运行
echo   - 该窗口显示完整的 Uvicorn 日志输出
echo   - 关闭 [Debug Server] 窗口即可停止服务
echo   - 本窗口可以安全关闭，不影响服务器运行
echo.
pause
