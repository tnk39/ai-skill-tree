import json

import pytest
from fastapi.testclient import TestClient

from mcp_server import tools
from server import database
from server.main import app
from server.snapshot import build_snapshot


def relation_kinds() -> set[str]:
    return {item["kind"] for item in database.list_relations()}


def test_migration_backfills_legacy_fields_idempotently_without_events(isolated_graph):
    database.init_db()
    connection = database.connect()
    try:
        assert "owns" in relation_kinds()
        assert "depends_on" in relation_kinds()
        connection.execute("DELETE FROM schema_migrations WHERE name=?", (database.RELATION_MIGRATION,))
        connection.execute("DELETE FROM relations")
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("task-legacy", "Legacy task", "", "codex", "skill-static-web", "goal-living-graph", 3, "queued", "", database.now(), None, None))
        connection.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("artifact-legacy", "Legacy artifact", "proof", None, None, None, None, "codex", json.dumps(["goal-living-graph"]), json.dumps(["skill-static-web"]), database.now()))
        connection.commit()
        database.migrate_relations(connection)
        first = database.list_relations()
        database.migrate_relations(connection)
        second = database.list_relations()
        assert len(first) == len(second)
        assert {"owns", "depends_on", "advances", "uses", "demonstrates", "contributes_to"}.issubset({item["kind"] for item in first})
        assert not database.rows("events")
    finally:
        connection.close()


def test_migration_rolls_back_before_marker_on_failure(isolated_graph, monkeypatch):
    database.init_db()
    connection = database.connect()
    try:
        connection.execute("DELETE FROM schema_migrations WHERE name=?", (database.RELATION_MIGRATION,))
        connection.execute("DELETE FROM relations")
        connection.commit()
        monkeypatch.setattr(database, "_legacy_relations", lambda _: (_ for _ in ()).throw(RuntimeError("migration failure")))
        with pytest.raises(RuntimeError, match="migration failure"):
            database.migrate_relations(connection)
        assert not connection.execute("SELECT 1 FROM schema_migrations WHERE name=?", (database.RELATION_MIGRATION,)).fetchone()
        assert not connection.execute("SELECT 1 FROM relations").fetchone()
    finally:
        connection.close()


def test_database_relation_validation_and_audit_events(isolated_graph):
    relation = database.create_relation("goal", "goal-living-graph", "skill", "skill-static-web", "requires", actor="test", source="test")
    assert relation["kind"] == "requires"
    with pytest.raises(database.RelationConflictError):
        database.create_relation("goal", "goal-living-graph", "skill", "skill-static-web", "requires")
    with pytest.raises(database.RelationNotFoundError):
        database.create_relation("goal", "missing", "skill", "skill-static-web", "requires")
    with pytest.raises(database.RelationValidationError):
        database.create_relation("goal", "goal-living-graph", "skill", "skill-static-web", "uses")
    with pytest.raises(database.RelationValidationError):
        database.create_relation("skill", "skill-static-web", "skill", "skill-static-web", "depends_on")
    removed = database.delete_relation(relation["id"], actor="test", source="test")
    assert removed["id"] == relation["id"]
    with pytest.raises(database.RelationNotFoundError):
        database.delete_relation(relation["id"])
    events = database.rows("events")
    assert [event["event_type"] for event in events[:2]] == ["relation_deleted", "relation_created"]
    payload = json.loads(events[0]["payload"])
    assert set(payload) == {"from_entity_type", "from_entity_id", "to_entity_type", "to_entity_id", "kind"}


def test_relation_api_lists_creates_and_deletes(isolated_graph):
    with TestClient(app) as client:
        payload = {"from_entity_type": "goal", "from_entity_id": "goal-living-graph", "to_entity_type": "skill", "to_entity_id": "skill-static-web", "kind": "requires"}
        created = client.post("/api/relations", json=payload)
        assert created.status_code == 201
        relation_id = created.json()["id"]
        assert client.post("/api/relations", json=payload).status_code == 409
        assert client.post("/api/relations", json={**payload, "to_entity_id": "missing"}).status_code == 404
        assert client.post("/api/relations", json={**payload, "kind": "uses"}).status_code == 422
        assert client.post("/api/relations", json={**payload, "from_entity_type": "not-an-entity"}).status_code == 422
        assert any(item["id"] == relation_id for item in client.get("/api/relations").json())
        assert client.delete(f"/api/relations/{relation_id}").status_code == 200
        assert client.delete(f"/api/relations/{relation_id}").status_code == 404


def test_mcp_relations_and_goal_to_artifact_graph(isolated_graph):
    requires = tools.create_graph_relation("goal", "goal-living-graph", "skill", "skill-static-web", "requires")
    task = tools.create_graph_task("Build evidence", related_skill_id="skill-static-web")
    task_id = task["entity_id"]
    tools.create_graph_relation("task", task_id, "goal", "goal-living-graph", "advances")
    artifact = database.create_artifact({"title": "Safe proof", "related_goal_ids": ["goal-living-graph"], "related_skill_ids": ["skill-static-web"]}, actor="test", source="test")
    artifact_id = artifact["entity_id"]
    tools.create_graph_relation("task", task_id, "artifact", artifact_id, "produces")
    graph = tools.get_skill_graph()
    assert {"requires", "advances", "uses", "produces", "demonstrates", "contributes_to"}.issubset({item["kind"] for item in graph["relations"]})
    assert any(item["id"] == requires["id"] for item in tools.list_graph_relations())
    assert tools.delete_graph_relation(requires["id"])["id"] == requires["id"]
    snapshot_path = build_snapshot(isolated_graph / "snapshot.json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == 3
    assert all(set(item) == {"from", "to", "kind"} for item in snapshot["relationships"])
    raw = snapshot_path.read_text(encoding="utf-8")
    assert task_id not in raw and artifact_id not in raw and "Safe proof" in raw
    assert all(item["kind"] in database.RELATION_RULES for item in snapshot["relationships"])
