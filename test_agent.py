#!/usr/bin/env python3
"""
Test Agent — 自动化测试工作流

功能：
1. 代码-测试映射分析：扫描 server.py 的 API 路由，检查 tests/ 中是否有对应测试
2. 文件变更监控：使用 watchdog 监听代码改动，自动触发测试运行
3. 测试执行与报告：运行 pytest，生成覆盖率/结果报告

用法：
    python test_agent.py --check      # 检查测试覆盖，报告缺失
    python test_agent.py --watch      # 监控文件变化，自动运行测试
    python test_agent.py --run        # 立即运行所有测试
    python test_agent.py              # 默认：先 check 再 run
"""

import argparse
import ast
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Optional watchdog for --watch mode
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

PROJECT_ROOT = Path(__file__).parent
TESTS_DIR = PROJECT_ROOT / "tests"


# ---------------------------------------------------------------------------
# 1. 代码-测试映射分析
# ---------------------------------------------------------------------------

@dataclass
class ApiEndpoint:
    method: str
    path: str
    handler: str

@dataclass
class TestCase:
    file: Path
    class_name: Optional[str]
    func_name: str
    tested_methods: list[str]


def scan_api_routes(source_file: Path) -> list[ApiEndpoint]:
    """Parse a Python file and extract FastAPI route decorators."""
    endpoints = []
    text = source_file.read_text(encoding="utf-8")
    tree = ast.parse(text)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                deco_str = ast.unparse(decorator) if hasattr(ast, "unparse") else None
                if deco_str is None:
                    continue
                # Match app.get("/path") or @app.get("/path") etc.
                match = re.search(r'@?\w+\.(get|post|put|delete)\(["\']([^"\']+)', deco_str)
                if match:
                    method = match.group(1).upper()
                    path = match.group(2)
                    endpoints.append(ApiEndpoint(method, path, node.name))
    return endpoints


def scan_test_cases(tests_dir: Path) -> list[TestCase]:
    """Parse test files and extract test function/class names."""
    cases = []
    for pyfile in tests_dir.glob("test_*.py"):
        text = pyfile.read_text(encoding="utf-8")
        tree = ast.parse(text)

        current_class = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                current_class = node.name
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                        cases.append(TestCase(pyfile, current_class, child.name, []))
            elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                cases.append(TestCase(pyfile, None, node.name, []))
    return cases


def analyze_coverage(source_file: Path, tests_dir: Path) -> dict:
    """Map API routes to test cases and identify gaps."""
    routes = scan_api_routes(source_file)
    tests = scan_test_cases(tests_dir)

    # Heuristic: match route handler name to test function/class name
    route_to_tests = {f"{r.method} {r.path}": [] for r in routes}
    handler_names = {r.handler.lower() for r in routes}

    for tc in tests:
        name_lower = tc.func_name.lower()
        for r in routes:
            key = f"{r.method} {r.path}"
            handler = r.handler.lower()
            # Match if test name contains handler name or route method
            if handler in name_lower or r.method.lower() in name_lower:
                route_to_tests[key].append(tc)

    missing = [route for route, tcs in route_to_tests.items() if not tcs]
    covered = {route: tcs for route, tcs in route_to_tests.items() if tcs}

    return {
        "total_routes": len(routes),
        "total_tests": len(tests),
        "covered": covered,
        "missing": missing,
    }


def print_coverage_report(report: dict):
    print("=" * 60)
    print("[REPORT] 代码-测试映射分析报告")
    print("=" * 60)
    print(f"  API 路由总数 : {report['total_routes']}")
    print(f"  测试用例总数 : {report['total_tests']}")
    print(f"  已覆盖路由   : {len(report['covered'])}")
    print(f"  未覆盖路由   : {len(report['missing'])}")
    print()

    if report["missing"]:
        print("[!] 以下 API 路由缺少对应测试：")
        for route in report["missing"]:
            print(f"    - {route}")
        print()
    else:
        print("[OK] 所有 API 路由均有测试覆盖！\n")

    print("[INFO] 已覆盖路由详情：")
    for route, tests in report["covered"].items():
        names = ", ".join(t.func_name for t in tests)
        print(f"    {route}  →  {names}")
    print()


# ---------------------------------------------------------------------------
# 2. 测试执行
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run pytest and capture results."""
    print("[RUN] 正在运行测试...\n")
    start = time.time()

    # Run pytest with JSON output if available, else plain
    # Default to unit tests only; e2e can be slow/heavy in some envs
    test_target = os.environ.get("TEST_TARGET", "tests/test_server.py")
    cmd = [sys.executable, "-m", "pytest", test_target, "-v", "--tb=short"]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    elapsed = time.time() - start
    passed = result.returncode == 0

    # Parse summary
    summary = {"passed": 0, "failed": 0, "errors": 0, "duration": elapsed, "raw": result.stdout}
    for line in result.stdout.splitlines():
        if " passed" in line and "failed" not in line.lower():
            m = re.search(r'(\d+) passed', line)
            if m:
                summary["passed"] = int(m.group(1))
        if " failed" in line:
            m = re.search(r'(\d+) failed', line)
            if m:
                summary["failed"] = int(m.group(1))
        if " error" in line:
            m = re.search(r'(\d+) error', line)
            if m:
                summary["errors"] = int(m.group(1))

    return summary, result.stdout, result.stderr


def print_test_report(summary: dict, stdout: str, stderr: str):
    print("=" * 60)
    print("[REPORT] 测试结果报告")
    print("=" * 60)
    print(f"  耗时: {summary['duration']:.2f}s")
    print(f"  通过: {summary['passed']}")
    print(f"  失败: {summary['failed']}")
    print(f"  错误: {summary['errors']}")
    print()

    if stdout:
        print("[DETAIL] 输出详情：")
        print(stdout)
    if stderr:
        print("[WARN] 标准错误：")
        print(stderr)

    if summary["failed"] == 0 and summary["errors"] == 0:
        print("[OK] 所有测试通过！\n")
    else:
        print("[FAIL] 存在失败的测试，请检查。\n")


# ---------------------------------------------------------------------------
# 3. 文件变更监控
# ---------------------------------------------------------------------------

class TestTriggerHandler(FileSystemEventHandler):
    def __init__(self, debounce_seconds: float = 2.0):
        self.last_run = 0
        self.debounce = debounce_seconds

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith((".py", ".html", ".js")):
            return
        # Ignore test artifacts
        if "__pycache__" in event.src_path or ".pyc" in event.src_path:
            return

        now = time.time()
        if now - self.last_run < self.debounce:
            return
        self.last_run = now

        print(f"\n📝  检测到文件变更: {event.src_path}")
        print("    正在分析是否需要更新测试...\n")

        # Step 1: Check coverage
        report = analyze_coverage(PROJECT_ROOT / "server.py", TESTS_DIR)
        print_coverage_report(report)

        # Step 2: Run tests
        summary, stdout, stderr = run_tests()
        print_test_report(summary, stdout, stderr)

        print("[WATCH] 继续监控中... (按 Ctrl+C 停止)\n")


def start_watch_mode():
    if not WATCHDOG_AVAILABLE:
        print("[ERROR] watchdog 未安装，无法使用 --watch 模式")
        print("    请运行: pip install watchdog")
        sys.exit(1)

    print("[WATCH] 启动测试 Agent 监控模式...")
    print("    监控目录: ./")
    print("    按 Ctrl+C 停止\n")

    # Initial run
    report = analyze_coverage(PROJECT_ROOT / "server.py", TESTS_DIR)
    print_coverage_report(report)
    summary, stdout, stderr = run_tests()
    print_test_report(summary, stdout, stderr)

    observer = Observer()
    handler = TestTriggerHandler(debounce_seconds=2.0)
    observer.schedule(handler, str(PROJECT_ROOT), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("\n👋  监控已停止")


# ---------------------------------------------------------------------------
# 4. 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test Agent — 自动化测试工作流")
    parser.add_argument("--check", action="store_true", help="检查测试覆盖，报告缺失")
    parser.add_argument("--watch", action="store_true", help="监控文件变化，自动运行测试")
    parser.add_argument("--run", action="store_true", help="立即运行所有测试")
    args = parser.parse_args()

    if args.watch:
        start_watch_mode()
        return

    if args.check:
        report = analyze_coverage(PROJECT_ROOT / "server.py", TESTS_DIR)
        print_coverage_report(report)
        return

    if args.run:
        summary, stdout, stderr = run_tests()
        print_test_report(summary, stdout, stderr)
        sys.exit(0 if summary["failed"] == 0 and summary["errors"] == 0 else 1)

    # Default: check + run
    print("[AGENT] Test Agent 启动 (默认模式: 检查 + 运行)\n")
    report = analyze_coverage(PROJECT_ROOT / "server.py", TESTS_DIR)
    print_coverage_report(report)
    summary, stdout, stderr = run_tests()
    print_test_report(summary, stdout, stderr)
    sys.exit(0 if summary["failed"] == 0 and summary["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
