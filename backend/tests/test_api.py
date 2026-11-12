from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_without_messages_is_422():
    assert client.post("/api/chat", json={"messages": []}).status_code == 422


def test_chat_last_message_must_be_from_the_user():
    body = {"messages": [{"role": "assistant", "content": "hello"}]}
    assert client.post("/api/chat", json=body).status_code == 422


def test_chat_message_too_long_is_422():
    body = {"messages": [{"role": "user", "content": "a" * 2001}]}
    assert client.post("/api/chat", json=body).status_code == 422


def test_chat_without_api_key_returns_502(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr("app.agent.agent._client", None)
    body = {"messages": [{"role": "user", "content": "¿Qué ayudas hay?"}]}
    assert client.post("/api/chat", json=body).status_code == 502


def test_unknown_aid_is_404():
    assert client.get("/api/aids/nothing").status_code == 404
