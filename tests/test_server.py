import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path):
    os.environ["JARVIS_API_KEY"] = "test-key-123"
    os.environ["JARVIS_DATA_DIR"] = str(tmp_path / "var")
    os.environ["JARVIS_LLM_PROVIDER"] = "echo"
    os.environ["JARVIS_LLM_FALLBACK"] = ""
    os.environ["JARVIS_VOICE_ENABLED"] = "false"
    os.environ["JARVIS_ALLOWED_TOOLS"] = "*"
    os.environ["CLAUDE_CODE_WORKSPACES"] = str(tmp_path / "ws")

    from jarvis.config import reload_settings

    reload_settings()

    from jarvis.server.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_requires_auth(client):
    r = client.get("/v1/runtime/info")
    assert r.status_code == 401


def test_runtime_info(client):
    r = client.get("/v1/runtime/info", headers={"Authorization": "Bearer test-key-123"})
    assert r.status_code == 200
    data = r.json()
    assert data["llm"]["provider"] == "echo"
    assert "filesystem_read" in data["tools"]


def test_chat_flow(client):
    r = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer test-key-123"},
        json={"message": "hello"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "hello" in data["reply"]


def test_session_crud(client):
    h = {"Authorization": "Bearer test-key-123"}
    create = client.post("/v1/sessions", headers=h, json={"title": "x"})
    assert create.status_code == 200
    sid = create.json()["id"]
    listed = client.get("/v1/sessions", headers=h)
    assert any(s["id"] == sid for s in listed.json()["sessions"])
    msgs = client.get(f"/v1/sessions/{sid}/messages", headers=h)
    assert msgs.status_code == 200
    assert msgs.json()["messages"] == []


def test_scheduler_crud(client):
    h = {"Authorization": "Bearer test-key-123"}
    import time

    job = client.post(
        "/v1/scheduler/jobs",
        headers=h,
        json={
            "kind": "reminder",
            "title": "test",
            "message": "m",
            "at_timestamp": time.time() + 600,
        },
    )
    assert job.status_code == 200, job.text
    jid = job.json()["id"]
    listing = client.get("/v1/scheduler/jobs", headers=h)
    assert any(j["id"] == jid for j in listing.json()["jobs"])
    rm = client.delete(f"/v1/scheduler/jobs/{jid}", headers=h)
    assert rm.status_code == 200
