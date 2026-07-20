from fastapi.testclient import TestClient

from server.main import app


def test_api_vertical_slice(isolated_graph):
    with TestClient(app) as client:
        assert client.get("/api/graph").status_code == 200
        created = client.post("/api/tasks", json={"title": "Ship graph view", "related_skill_id": "skill-static-web"})
        assert created.status_code == 201
        task_id = created.json()["entity_id"]
        assert client.post("/api/events", json={"event_type": "skill_used", "entity_type": "skill", "entity_id": "skill-static-web", "payload": {"success": True}}).status_code == 201
        tasks = client.get("/api/tasks").json()
        assert any(task["id"] == task_id and task["status"] == "queued" for task in tasks)


def test_unknown_skill_is_not_success(isolated_graph):
    with TestClient(app) as client:
        assert client.get("/api/skills/not-real").status_code == 404
