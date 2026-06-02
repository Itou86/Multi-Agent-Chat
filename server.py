"""Multi-Agent Chat Backend

提供 REST API 管理 Agent 配置、对话 Session 和设置。
每个 Session 存为 data/sessions/{id}.json，每个 Agent 存为 data/agents/{id}.json。
启动: python server.py
"""

import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
AGENTS_DIR = DATA_DIR / "agents"
SESSIONS_DIR = DATA_DIR / "sessions"
PIPELINES_DIR = DATA_DIR / "pipelines"
SETTINGS_FILE = DATA_DIR / "settings.json"

app = FastAPI(title="Multi-Agent Chat Backend")

# CORS — 允许前端开发环境访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- helpers ----------

def ensure_dirs():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    PIPELINES_DIR.mkdir(parents=True, exist_ok=True)

def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def list_json_files(directory: Path) -> list[dict]:
    items = []
    if directory.exists():
        for p in sorted(directory.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            data = read_json(p)
            if data:
                items.append(data)
    return items

# ---------- init ----------

ensure_dirs()
if not any(AGENTS_DIR.glob("*.json")):
    default_agent = {
        "id": "default",
        "name": "通用助手",
        "prompt": "You are a helpful assistant."
    }
    write_json(AGENTS_DIR / "default.json", default_agent)

# ---------- models ----------

class AgentCreate(BaseModel):
    name: str
    prompt: str

class AgentUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None

class SessionCreate(BaseModel):
    agentId: str | None = None
    title: str = "新对话"
    mode: str = "single"
    pipelineId: str | None = None

class SessionUpdate(BaseModel):
    title: str | None = None
    messages: list[dict] | None = None
    layers: list[dict] | None = None

class PipelineLayer(BaseModel):
    agentId: str | None = None
    label: str
    prompt: str = ""
    branches: int = 1

class PipelineCreate(BaseModel):
    name: str
    layers: list[PipelineLayer]

class PipelineUpdate(BaseModel):
    name: str | None = None
    layers: list[PipelineLayer] | None = None

class SettingsUpdate(BaseModel):
    apiUrl: str | None = None
    apiKey: str | None = None
    model: str | None = None
    stream: bool | None = None

# ---------- API: agents ----------

@app.get("/api/agents")
def get_agents():
    return list_json_files(AGENTS_DIR)

@app.post("/api/agents")
def create_agent(body: AgentCreate):
    agent = {
        "id": str(int(time.time() * 1000)),
        "name": body.name,
        "prompt": body.prompt
    }
    write_json(AGENTS_DIR / f"{agent['id']}.json", agent)
    return agent

@app.put("/api/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentUpdate):
    path = AGENTS_DIR / f"{agent_id}.json"
    agent = read_json(path)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if body.name is not None:
        agent["name"] = body.name
    if body.prompt is not None:
        agent["prompt"] = body.prompt
    write_json(path, agent)
    return agent

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str):
    path = AGENTS_DIR / f"{agent_id}.json"
    if path.exists():
        path.unlink()
    # 同时删除该 agent 关联的 sessions
    for p in SESSIONS_DIR.glob("*.json"):
        sess = read_json(p)
        if sess and sess.get("agentId") == agent_id:
            p.unlink()
    # 同时把引用该 agent 的 pipeline 层置空（保留结构）
    for p in PIPELINES_DIR.glob("*.json"):
        pl = read_json(p)
        if pl:
            changed = False
            for layer in pl.get("layers", []):
                if layer.get("agentId") == agent_id:
                    layer["agentId"] = None
                    changed = True
            if changed:
                write_json(p, pl)
    return {"ok": True}

# ---------- API: sessions ----------

@app.get("/api/sessions")
def get_sessions(agentId: str | None = None, pipelineId: str | None = None):
    sessions = list_json_files(SESSIONS_DIR)
    if agentId:
        sessions = [s for s in sessions if s.get("agentId") == agentId]
    if pipelineId:
        sessions = [s for s in sessions if s.get("pipelineId") == pipelineId]
    return sessions

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    sess = read_json(SESSIONS_DIR / f"{session_id}.json")
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

@app.post("/api/sessions")
def create_session(body: SessionCreate):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    sess = {
        "id": str(int(time.time() * 1000)),
        "mode": body.mode,
        "title": body.title,
        "messages": [],
        "createdAt": now,
        "updatedAt": now
    }
    if body.mode in ("pipeline", "tree") and body.pipelineId:
        pl = read_json(PIPELINES_DIR / f"{body.pipelineId}.json")
        if not pl:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        sess["pipelineId"] = body.pipelineId
        sess["layers"] = []
        for layer in pl.get("layers", []):
            branches = layer.get("branches", 1)
            if body.mode == "tree":
                sess["layers"].append({
                    "agentId": layer.get("agentId"),
                    "label": layer.get("label", ""),
                    "defaultPrompt": layer.get("prompt", ""),
                    "sessionPrompt": "",
                    "branches": branches,
                    "responses": [{"id": f"r{i}", "content": ""} for i in range(branches)],
                    "selectedResponseId": None
                })
            else:
                sess["layers"].append({
                    "agentId": layer.get("agentId"),
                    "label": layer.get("label", ""),
                    "defaultPrompt": layer.get("prompt", ""),
                    "sessionPrompt": "",
                    "response": ""
                })
    else:
        sess["agentId"] = body.agentId or "default"
    write_json(SESSIONS_DIR / f"{sess['id']}.json", sess)
    return sess

@app.put("/api/sessions/{session_id}")
def update_session(session_id: str, body: SessionUpdate):
    path = SESSIONS_DIR / f"{session_id}.json"
    sess = read_json(path)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if body.title is not None:
        sess["title"] = body.title
    if body.messages is not None:
        sess["messages"] = body.messages
    if body.layers is not None:
        sess["layers"] = body.layers
    sess["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json(path, sess)
    return sess

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}

# ---------- API: pipelines ----------

@app.get("/api/pipelines")
def get_pipelines():
    return list_json_files(PIPELINES_DIR)

@app.post("/api/pipelines")
def create_pipeline(body: PipelineCreate):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    pl = {
        "id": str(int(time.time() * 1000)),
        "name": body.name,
        "layers": [layer.model_dump() for layer in body.layers],
        "createdAt": now,
        "updatedAt": now
    }
    write_json(PIPELINES_DIR / f"{pl['id']}.json", pl)
    return pl

@app.put("/api/pipelines/{pipeline_id}")
def update_pipeline(pipeline_id: str, body: PipelineUpdate):
    path = PIPELINES_DIR / f"{pipeline_id}.json"
    pl = read_json(path)
    if not pl:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if body.name is not None:
        pl["name"] = body.name
    if body.layers is not None:
        pl["layers"] = [layer.model_dump() for layer in body.layers]
    pl["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json(path, pl)
    return pl

@app.delete("/api/pipelines/{pipeline_id}")
def delete_pipeline(pipeline_id: str):
    path = PIPELINES_DIR / f"{pipeline_id}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}

# ---------- API: settings ----------

@app.get("/api/settings")
def get_settings():
    settings = read_json(SETTINGS_FILE)
    if settings is None:
        settings = {"apiUrl": "", "apiKey": "", "model": "", "stream": True}
        write_json(SETTINGS_FILE, settings)
    return settings

@app.post("/api/settings")
def update_settings(body: SettingsUpdate):
    settings = read_json(SETTINGS_FILE) or {}
    if body.apiUrl is not None:
        settings["apiUrl"] = body.apiUrl
    if body.apiKey is not None:
        settings["apiKey"] = body.apiKey
    if body.model is not None:
        settings["model"] = body.model
    if body.stream is not None:
        settings["stream"] = body.stream
    write_json(SETTINGS_FILE, settings)
    return settings

# ---------- static files ----------

# 兜底：返回 index.html（支持前端路由刷新）
@app.get("/{full_path:path}")
def serve_index(full_path: str):
    file_path = BASE_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(BASE_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    import socket

    def find_free_port(start=8080, max_port=8100):
        for port in range(start, max_port + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("0.0.0.0", port)) != 0:
                    return port
        raise RuntimeError("No free port found")

    port = int(os.environ.get("PORT", 8088))
    # If default port is busy, auto-scan for free one
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("0.0.0.0", port)) == 0:
            port = find_free_port(start=port + 1)
            print(f"Port 8080 is occupied. Using port {port}")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
