"""Backend API unit tests for server.py"""

import json


# ---------- Agents ----------

class TestAgents:
    def test_list_agents_default(self, client):
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "default"
        assert data[0]["name"] == "通用助手"

    def test_create_agent(self, client):
        resp = client.post("/api/agents", json={"name": "Coder", "prompt": "Code expert."})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Coder"
        assert data["prompt"] == "Code expert."
        assert "id" in data

    def test_update_agent(self, client):
        # create first
        create_resp = client.post("/api/agents", json={"name": "Old", "prompt": "Old prompt."})
        agent_id = create_resp.json()["id"]

        resp = client.put(f"/api/agents/{agent_id}", json={"name": "New", "prompt": "New prompt."})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New"
        assert data["prompt"] == "New prompt."

    def test_delete_agent(self, client):
        create_resp = client.post("/api/agents", json={"name": "Temp", "prompt": "Temp."})
        agent_id = create_resp.json()["id"]

        resp = client.delete(f"/api/agents/{agent_id}")
        assert resp.status_code == 200

        list_resp = client.get("/api/agents")
        ids = [a["id"] for a in list_resp.json()]
        assert agent_id not in ids

    def test_delete_agent_cleans_sessions(self, client):
        # create agent + session
        agent_resp = client.post("/api/agents", json={"name": "Cleaner", "prompt": "Clean."})
        agent_id = agent_resp.json()["id"]

        sess_resp = client.post("/api/sessions", json={"agentId": agent_id, "title": "ToDelete"})
        sess_id = sess_resp.json()["id"]

        # delete agent
        client.delete(f"/api/agents/{agent_id}")

        # session should be gone
        get_sess = client.get(f"/api/sessions/{sess_id}")
        assert get_sess.status_code == 404


# ---------- Sessions ----------

class TestSessions:
    def test_create_session(self, client):
        resp = client.post("/api/sessions", json={"agentId": "default", "title": "Test Chat"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["agentId"] == "default"
        assert data["title"] == "Test Chat"
        assert data["messages"] == []
        assert "id" in data
        assert "createdAt" in data

    def test_list_sessions(self, client):
        client.post("/api/sessions", json={"agentId": "default", "title": "S1"})
        client.post("/api/sessions", json={"agentId": "default", "title": "S2"})

        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_sessions_filter_by_agent(self, client):
        # create second agent
        agent2 = client.post("/api/agents", json={"name": "A2", "prompt": "P2"}).json()

        client.post("/api/sessions", json={"agentId": "default", "title": "ForDefault"})
        client.post("/api/sessions", json={"agentId": agent2["id"], "title": "ForA2"})

        resp = client.get(f"/api/sessions?agentId={agent2['id']}")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "ForA2"

    def test_get_session(self, client):
        create = client.post("/api/sessions", json={"agentId": "default", "title": "G1"})
        sess_id = create.json()["id"]

        resp = client.get(f"/api/sessions/{sess_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "G1"

    def test_get_session_not_found(self, client):
        resp = client.get("/api/sessions/nonexistent")
        assert resp.status_code == 404

    def test_update_session_messages(self, client):
        create = client.post("/api/sessions", json={"agentId": "default", "title": "U1"})
        sess_id = create.json()["id"]

        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        resp = client.put(f"/api/sessions/{sess_id}", json={"messages": msgs})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "hello"
        assert "updatedAt" in data

    def test_update_session_title(self, client):
        create = client.post("/api/sessions", json={"agentId": "default", "title": "OldTitle"})
        sess_id = create.json()["id"]

        resp = client.put(f"/api/sessions/{sess_id}", json={"title": "NewTitle"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "NewTitle"

    def test_delete_session(self, client):
        create = client.post("/api/sessions", json={"agentId": "default", "title": "Del"})
        sess_id = create.json()["id"]

        resp = client.delete(f"/api/sessions/{sess_id}")
        assert resp.status_code == 200

        get_resp = client.get(f"/api/sessions/{sess_id}")
        assert get_resp.status_code == 404


# ---------- Settings ----------

class TestSettings:
    def test_get_settings_default(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["apiUrl"] == ""
        assert data["apiKey"] == ""
        assert data["model"] == ""
        assert data["stream"] is True

    def test_update_settings(self, client):
        payload = {"apiUrl": "http://test.com", "apiKey": "sk-test", "model": "gpt-4", "stream": False}
        resp = client.post("/api/settings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["apiUrl"] == "http://test.com"
        assert data["apiKey"] == "sk-test"
        assert data["model"] == "gpt-4"
        assert data["stream"] is False

    def test_settings_persistence(self, client):
        client.post("/api/settings", json={"apiUrl": "persist", "apiKey": "", "model": "", "stream": True})
        resp = client.get("/api/settings")
        assert resp.json()["apiUrl"] == "persist"


# ---------- Static Files ----------

class TestStaticFiles:
    def test_index_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Multi-Agent Chat" in resp.text

    def test_spa_fallback(self, client):
        resp = client.get("/some/random/path")
        assert resp.status_code == 200
        assert "Multi-Agent Chat" in resp.text


# ---------- Pipelines ----------

class TestPipelines:
    def test_list_pipelines_empty(self, client):
        resp = client.get("/api/pipelines")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_pipeline(self, client):
        layers = [
            {"agentId": "default", "label": "Layer1", "prompt": "p1"},
            {"agentId": "default", "label": "Layer2", "prompt": "p2"},
        ]
        resp = client.post("/api/pipelines", json={"name": "TestPipe", "layers": layers})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestPipe"
        assert len(data["layers"]) == 2
        assert data["layers"][0]["label"] == "Layer1"

    def test_get_pipelines(self, client):
        client.post("/api/pipelines", json={"name": "A", "layers": [{"agentId": "default", "label": "L1", "prompt": ""}]})
        client.post("/api/pipelines", json={"name": "B", "layers": [{"agentId": "default", "label": "L1", "prompt": ""}]})
        resp = client.get("/api/pipelines")
        assert len(resp.json()) == 2

    def test_update_pipeline(self, client):
        create = client.post("/api/pipelines", json={"name": "Old", "layers": [{"agentId": "default", "label": "L1", "prompt": ""}]})
        pid = create.json()["id"]

        resp = client.put(f"/api/pipelines/{pid}", json={"name": "New", "layers": [{"agentId": "default", "label": "L2", "prompt": "updated"}]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New"
        assert data["layers"][0]["label"] == "L2"

    def test_delete_pipeline(self, client):
        create = client.post("/api/pipelines", json={"name": "Del", "layers": [{"agentId": "default", "label": "L1", "prompt": ""}]})
        pid = create.json()["id"]

        resp = client.delete(f"/api/pipelines/{pid}")
        assert resp.status_code == 200

        list_resp = client.get("/api/pipelines")
        ids = [p["id"] for p in list_resp.json()]
        assert pid not in ids


class TestPipelineSessions:
    def test_create_pipeline_session(self, client):
        # create pipeline first
        pl = client.post("/api/pipelines", json={
            "name": "Review",
            "layers": [
                {"agentId": "default", "label": "收集", "prompt": "collect"},
                {"agentId": "default", "label": "分析", "prompt": "analyze"},
            ]
        }).json()

        resp = client.post("/api/sessions", json={"mode": "pipeline", "pipelineId": pl["id"], "title": "PipeChat"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "pipeline"
        assert data["pipelineId"] == pl["id"]
        assert len(data["layers"]) == 2
        assert data["layers"][0]["label"] == "收集"
        assert data["layers"][0]["defaultPrompt"] == "collect"
        assert data["layers"][0]["sessionPrompt"] == ""
        assert data["layers"][0]["response"] == ""

    def test_create_pipeline_session_not_found(self, client):
        resp = client.post("/api/sessions", json={"mode": "pipeline", "pipelineId": "nonexistent", "title": "X"})
        assert resp.status_code == 404

    def test_create_tree_session(self, client):
        pl = client.post("/api/pipelines", json={
            "name": "Tree",
            "layers": [
                {"agentId": "default", "label": "收集", "prompt": "collect", "branches": 3},
                {"agentId": "default", "label": "分析", "prompt": "analyze", "branches": 2},
            ]
        }).json()

        resp = client.post("/api/sessions", json={"mode": "tree", "pipelineId": pl["id"], "title": "TreeChat"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "tree"
        assert data["pipelineId"] == pl["id"]
        assert len(data["layers"]) == 2
        assert data["layers"][0]["branches"] == 3
        assert len(data["layers"][0]["responses"]) == 3
        assert data["layers"][0]["selectedResponseId"] is None
        assert data["layers"][1]["branches"] == 2
        assert len(data["layers"][1]["responses"]) == 2

    def test_create_pipeline_session_no_branches(self, client):
        pl = client.post("/api/pipelines", json={
            "name": "Normal",
            "layers": [
                {"agentId": "default", "label": "L1", "prompt": "", "branches": 1},
            ]
        }).json()

        resp = client.post("/api/sessions", json={"mode": "pipeline", "pipelineId": pl["id"], "title": "NormalChat"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "pipeline"
        assert "responses" not in data["layers"][0]
        assert "response" in data["layers"][0]

    def test_list_sessions_by_pipeline(self, client):
        pl = client.post("/api/pipelines", json={"name": "P", "layers": [{"agentId": "default", "label": "L1", "prompt": ""}]}).json()
        client.post("/api/sessions", json={"mode": "pipeline", "pipelineId": pl["id"], "title": "S1"})
        client.post("/api/sessions", json={"mode": "pipeline", "pipelineId": pl["id"], "title": "S2"})

        resp = client.get(f"/api/sessions?pipelineId={pl['id']}")
        assert len(resp.json()) == 2

    def test_update_session_layers(self, client):
        pl = client.post("/api/pipelines", json={"name": "P", "layers": [{"agentId": "default", "label": "L1", "prompt": ""}]}).json()
        sess = client.post("/api/sessions", json={"mode": "pipeline", "pipelineId": pl["id"], "title": "S"}).json()

        new_layers = [
            {"agentId": "default", "label": "L1", "defaultPrompt": "", "sessionPrompt": "override", "response": "hello"}
        ]
        resp = client.put(f"/api/sessions/{sess['id']}", json={"layers": new_layers})
        assert resp.status_code == 200
        assert resp.json()["layers"][0]["sessionPrompt"] == "override"
        assert resp.json()["layers"][0]["response"] == "hello"

    def test_update_tree_session_responses(self, client):
        pl = client.post("/api/pipelines", json={"name": "P", "layers": [{"agentId": "default", "label": "L1", "prompt": "", "branches": 3}]}).json()
        sess = client.post("/api/sessions", json={"mode": "tree", "pipelineId": pl["id"], "title": "T"}).json()

        new_layers = [
            {"agentId": "default", "label": "L1", "defaultPrompt": "", "sessionPrompt": "", "branches": 3,
             "responses": [{"id": "r0", "content": "A"}, {"id": "r1", "content": "B"}, {"id": "r2", "content": "C"}],
             "selectedResponseId": "r1"}
        ]
        resp = client.put(f"/api/sessions/{sess['id']}", json={"layers": new_layers})
        assert resp.status_code == 200
        data = resp.json()
        assert data["layers"][0]["selectedResponseId"] == "r1"
        assert data["layers"][0]["responses"][1]["content"] == "B"

    def test_single_session_unchanged(self, client):
        resp = client.post("/api/sessions", json={"mode": "single", "agentId": "default", "title": "Single"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "single"
        assert data["agentId"] == "default"
        assert "pipelineId" not in data or data["pipelineId"] is None
