"""End-to-end tests using Playwright.

Requires: playwright, pytest-asyncio
Run: pytest tests/test_e2e.py --headed (to see browser)
"""

import shutil
import subprocess
import tempfile
import time

import pytest

BASE_URL = "http://localhost:8787"


@pytest.fixture(scope="module")
def server():
    """Start the backend server on a free port for E2E tests."""
    import os

    # Use a temp data directory to avoid polluting real data/
    temp_dir = tempfile.mkdtemp()
    # Use a unique port to avoid conflicts
    env = os.environ.copy()
    env["PORT"] = "8787"
    env["DATA_DIR"] = temp_dir
    proc = subprocess.Popen(
        ["python", "server.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            import urllib.request

            urllib.request.urlopen(f"{BASE_URL}/api/agents", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        shutil.rmtree(temp_dir)
        raise RuntimeError("Server failed to start")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def page(server, playwright):
    """Provide a fresh browser page."""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = context.new_page()
    yield pg
    context.close()
    browser.close()


class TestPageLoad:
    def test_title_and_layout(self, page):
        page.goto(BASE_URL)
        assert "Multi-Agent Chat" in page.title()
        # Sidebar should have Agents heading
        assert page.locator("text=Agents").first.is_visible()


class TestAgentManagement:
    def test_create_agent(self, page):
        page.goto(BASE_URL)
        page.click("text=+ 新建 Agent")
        page.fill("#editName", "TestBot")
        page.fill("#editPrompt", "You are a test bot.")
        page.click("text=保存")

        # Should appear in agent list
        page.wait_for_selector("text=TestBot")
        assert page.locator("text=TestBot").is_visible()

    def test_edit_agent(self, page):
        page.goto(BASE_URL)
        # Create agent first
        page.click("text=+ 新建 Agent")
        page.fill("#editName", "EditMe")
        page.fill("#editPrompt", "Original.")
        page.click("text=保存")
        page.wait_for_selector("text=EditMe")

        # Edit
        page.locator("text=EditMe").hover()
        page.locator("button[title='编辑']").first.click()
        page.fill("#editName", "EditedBot")
        page.click("text=保存")

        page.wait_for_selector("text=EditedBot")
        assert page.locator("text=EditedBot").is_visible()

    def test_delete_agent(self, page):
        page.goto(BASE_URL)
        page.click("text=+ 新建 Agent")
        page.fill("#editName", "DeleteMe")
        page.click("text=保存")
        page.wait_for_selector("text=DeleteMe")

        page.locator("text=DeleteMe").hover()
        page.locator("button[title='删除']").first.click()
        page.once("dialog", lambda dialog: dialog.accept())

        page.wait_for_selector("text=DeleteMe", state="hidden")
        assert page.locator("text=DeleteMe").count() == 0


class TestSessionManagement:
    def test_create_session(self, page):
        page.goto(BASE_URL)
        # There is a default agent, click "+ 新建" in sessions area
        page.click("text=+ 新建")
        page.wait_for_timeout(300)

        # A new session should appear with title "新对话"
        assert page.locator("text=新对话").first.is_visible()

    def test_session_persists_after_reload(self, page):
        page.goto(BASE_URL)
        page.click("text=+ 新建")
        page.wait_for_timeout(300)

        # Reload
        page.reload()
        page.wait_for_load_state("networkidle")

        # Session should still exist
        assert page.locator("text=新对话").first.is_visible()


class TestSettings:
    def test_save_settings(self, page):
        page.goto(BASE_URL)
        page.click("button[title='API 设置']")
        page.fill("#apiUrl", "https://test.api.com/v1")
        page.fill("#apiKey", "sk-test123")
        page.fill("#model", "gpt-test")
        page.uncheck("#streamToggle")
        page.click("text=保存设置")

        # Accept alert
        page.once("dialog", lambda dialog: dialog.accept())

        # Reload and verify persistence
        page.reload()
        page.wait_for_load_state("networkidle")
        page.click("button[title='API 设置']")

        assert page.input_value("#apiUrl") == "https://test.api.com/v1"
        assert page.input_value("#apiKey") == "sk-test123"
        assert page.input_value("#model") == "gpt-test"
        assert page.is_checked("#streamToggle") is False
