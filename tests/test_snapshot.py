import json

from server.database import create_task
from server.snapshot import build_snapshot


def test_public_snapshot_excludes_private_task_fields(isolated_graph):
    create_task({"title": "Safe task", "description": "private local detail", "related_skill_id": "skill-static-web"})
    output = build_snapshot(isolated_graph / "snapshot.json")
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    assert "description" not in snapshot["tasks"][0]
    assert "result" not in snapshot["tasks"][0]
    assert snapshot["tasks"][0]["related_skill_id"] == "skill-static-web"


def test_snapshot_endpoint_records_an_audit_event(isolated_graph):
    from fastapi.testclient import TestClient
    from server.main import app
    with TestClient(app) as client:
        assert client.post("/api/snapshot").status_code == 200
        assert any(event["event_type"] == "snapshot_published" for event in client.get("/api/activity").json())
