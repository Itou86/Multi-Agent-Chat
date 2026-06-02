#!/usr/bin/env python3
"""启动器：启动后端并自动打开浏览器"""

import os
import re
import subprocess
import sys
import time
import webbrowser

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(PROJECT_DIR, "server.py")


def check_python():
    ver = sys.version_info
    if ver < (3, 10):
        print("[X] 需要 Python 3.10+，当前版本:", sys.version.split()[0])
        input("按回车退出...")
        sys.exit(1)
    print(f"[*] Python: {sys.version.split()[0]}")


def check_deps():
    try:
        import fastapi, uvicorn  # noqa
        print("[*] 依赖已就绪")
        return
    except ImportError:
        pass
    print("[*] 正在安装依赖 fastapi uvicorn...")
    rc = subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "-q"]).returncode
    if rc != 0:
        print("[X] 依赖安装失败，请检查网络连接")
        input("按回车退出...")
        sys.exit(1)
    print("[*] 依赖安装完成")


def start_server():
    print("[*] 启动后端服务器...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, SERVER_PY],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=PROJECT_DIR,
    )
    return proc


def wait_for_server(proc, timeout=30):
    """从 server.py 的输出中解析实际启动的端口"""
    port = None
    start_time = time.time()
    buffer = ""

    while time.time() - start_time < timeout:
        # 尝试读取输出
        import select
        if sys.platform == "win32":
            # Windows 没有 select on pipes，用轮询
            try:
                line = proc.stdout.readline()
                if line:
                    buffer += line
                    # 解析端口
                    m = re.search(r"Uvicorn running on http://[\d\.]+:(\d+)", line)
                    if m:
                        port = int(m.group(1))
                        print(f"[*] 服务器已就绪: http://localhost:{port}")
                        return port
                    m2 = re.search(r"Using port (\d+)", line)
                    if m2:
                        port = int(m2.group(1))
            except Exception:
                pass
            time.sleep(0.3)
        else:
            # Unix-like
            import select as sel
            ready, _, _ = sel.select([proc.stdout], [], [], 0.5)
            if ready:
                line = proc.stdout.readline()
                buffer += line
                m = re.search(r"Uvicorn running on http://[\d\.]+:(\d+)", line)
                if m:
                    port = int(m.group(1))
                    print(f"[*] 服务器已就绪: http://localhost:{port}")
                    return port
                m2 = re.search(r"Using port (\d+)", line)
                if m2:
                    port = int(m2.group(1))

    # 超时回退：尝试常见端口
    for p in [8088, 8089, 8090]:
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{p}/api/agents", timeout=1)
            print(f"[*] 服务器已就绪（检测）: http://localhost:{p}")
            return p
        except Exception:
            continue

    print("[X] 等待超时，服务器可能启动失败")
    print("    输出日志:\n", buffer[-500:] if len(buffer) > 500 else buffer)
    proc.terminate()
    input("按回车退出...")
    sys.exit(1)


def open_browser(port):
    url = f"http://localhost:{port}"
    print(f"[*] 正在打开浏览器: {url}")
    webbrowser.open(url, new=2)  # new=2 = new tab


def main():
    print("=" * 48)
    print("   Multi-Agent Chat 一键启动器")
    print("=" * 48)
    print()

    check_python()
    check_deps()
    proc = start_server()
    port = wait_for_server(proc)
    open_browser(port)

    print()
    print("=" * 48)
    print("   启动完成！浏览器已打开")
    print(f"   地址: http://localhost:{port}")
    print("=" * 48)
    print()
    print("[提示] 按 Ctrl+C 停止服务器")
    print()

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[*] 正在停止服务器...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[*] 已停止")


if __name__ == "__main__":
    main()
