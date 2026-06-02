"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def temp_data_dir(monkeypatch):
    """Create a temporary data directory and patch server paths."""
    tmp = tempfile.mkdtemp(prefix="chat_test_")
    tmp_path = Path(tmp)

    # Import server after patching to pick up new paths
    import server as srv

    monkeypatch.setattr(srv, "DATA_DIR", tmp_path)
    monkeypatch.setattr(srv, "AGENTS_DIR", tmp_path / "agents")
    monkeypatch.setattr(srv, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(srv, "PIPELINES_DIR", tmp_path / "pipelines")
    monkeypatch.setattr(srv, "SETTINGS_FILE", tmp_path / "settings.json")

    # Re-run ensure_dirs with new paths
    srv.ensure_dirs()

    # Re-init default agent if empty
    if not any(srv.AGENTS_DIR.glob("*.json")):
        srv.write_json(
            srv.AGENTS_DIR / "default.json",
            {"id": "default", "name": "通用助手", "prompt": "You are a helpful assistant."},
        )

    yield tmp_path

    # Cleanup
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="function")
def client(temp_data_dir):
    """Return a TestClient with isolated data directory."""
    import server as srv

    # Re-create app with fresh state by re-importing routes
    from fastapi.testclient import TestClient

    return TestClient(srv.app)
