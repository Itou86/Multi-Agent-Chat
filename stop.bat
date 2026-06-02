@echo off
chcp 65001 >nul
echo [*] 正在停止 Multi-Agent Chat 服务器...

:: 停止标题为 Chat Server 的窗口
taskkill /FI "WINDOWTITLE eq Chat Server" /F >nul 2>&1

:: 同时停止 python server.py 进程
for /f "tokens=2" %%a in ('tasklist ^| findstr python.exe') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr "server.py" >nul && (
        taskkill /PID %%a /F >nul 2>&1
        echo [*] 已停止进程 PID: %%a
    )
)

echo [*] 服务器已停止
timeout /t 2 >nul
