import json

from server.database import create_task
from server.snapshot import build_snapshot


def test_public_snapshot_excludes_private_task_fields(isolated_graph):
    create_task({"title": "Safe task", "description": "private local detail", "related_skill_id": "skill-static-web"})
    output = build_snapshot(isolated_graph / "snapshot.json")
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    raw = output.read_text(encoding="utf-8")
    assert snapshot["schema_version"] == 3
    assert "description" not in snapshot["tasks"][0]
    assert "result" not in snapshot["tasks"][0]
    assert "related_skill_id" not in snapshot["tasks"][0]
    assert "private local detail" not in raw
    assert "skill-static-web" not in raw
    assert all(set(relation) == {"from", "to", "kind"} for relation in snapshot["relationships"])
    assert all(relation["from"].startswith("node-") and relation["to"].startswith("node-") for relation in snapshot["relationships"])
    assert any(relation["kind"] == "uses" for relation in snapshot["relationships"])


def test_public_snapshot_keeps_only_safe_artifact_fields(isolated_graph):
    from server.database import record_event

    record_event(
        "artifact_linked",
        "test",
        "artifact",
        "artifact-private",
        {
            "title": "Safe artifact",
            "url": "https://private.example.test/secret",
            "local_path": "C:/private/path.txt",
            "repository": "private/repository",
            "commit_sha": "secret-commit",
            "related_goal_ids": ["goal-living-graph"],
            "related_skill_ids": ["skill-static-web"],
        },
        source="test",
    )
    output = build_snapshot(isolated_graph / "snapshot.json")
    raw = output.read_text(encoding="utf-8")
    artifact = json.loads(raw)["artifacts"][0]
    assert set(artifact) == {"id", "title", "type"}
    assert "private.example.test" not in raw
    assert "C:/private/path.txt" not in raw
    assert "private/repository" not in raw
    assert "secret-commit" not in raw


def test_snapshot_endpoint_records_an_audit_event(isolated_graph):
    from fastapi.testclient import TestClient
    from server.main import app
    with TestClient(app) as client:
        assert client.post("/api/snapshot").status_code == 200
        assert any(event["event_type"] == "snapshot_published" for event in client.get("/api/activity").json())
