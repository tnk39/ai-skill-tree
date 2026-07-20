"""Append-only event store with SQLite state projections and safe relations."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ENTITY_TABLES, ENTITY_TYPES, RELATION_RULES, SKILL_STATUSES

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("agents", "goals", "skills", "tasks", "artifacts", "relations", "events")
RELATION_MIGRATION = "2026-07-20-backfill-entity-relations-v1"


class RelationValidationError(ValueError):
    pass


class RelationNotFoundError(LookupError):
    pass


class RelationConflictError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def data_dir() -> Path:
    configured = os.environ.get("SKILL_GRAPH_DATA_DIR")
    return Path(configured) if configured else ROOT / "data"


def db_path() -> Path:
    return data_dir() / "skill_graph.sqlite3"


def events_path() -> Path:
    return data_dir() / "events.jsonl"


def connect() -> sqlite3.Connection:
    data_dir().mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    return connection


def _seed(name: str) -> list[dict[str, Any]]:
    return json.loads((ROOT / "data" / "seed" / name).read_text(encoding="utf-8"))


def _ids(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []


def _schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL, model TEXT, role TEXT, status TEXT NOT NULL, last_active_at TEXT);
        CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT, priority INTEGER NOT NULL, status TEXT NOT NULL, success_criteria TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT, description TEXT, status TEXT NOT NULL, confidence REAL NOT NULL, success_rate REAL NOT NULL, usage_count INTEGER NOT NULL, last_used_at TEXT, owner_agent_id TEXT, dependencies TEXT NOT NULL, unlock_conditions TEXT NOT NULL, next_validation TEXT, version TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT, assigned_agent_id TEXT, related_skill_id TEXT, related_goal_id TEXT, priority INTEGER NOT NULL, status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT);
        CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT, url TEXT, local_path TEXT, repository TEXT, commit_sha TEXT, created_by_agent_id TEXT, related_goal_ids TEXT NOT NULL, related_skill_ids TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS relations (id TEXT PRIMARY KEY, from_entity_type TEXT NOT NULL, from_entity_id TEXT NOT NULL, to_entity_type TEXT NOT NULL, to_entity_id TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(from_entity_type, from_entity_id, to_entity_type, to_entity_id, kind));
        CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, timestamp TEXT NOT NULL, actor TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, payload TEXT NOT NULL, source TEXT NOT NULL, correlation_id TEXT NOT NULL);
        """
    )


def _seed_if_empty(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM agents LIMIT 1").fetchone():
        return
    for agent in _seed("agents.json"):
        connection.execute("INSERT INTO agents VALUES (:id,:name,:type,:model,:role,:status,:last_active_at)", agent)
    for goal in _seed("goals.json"):
        connection.execute("INSERT INTO goals VALUES (:id,:title,:description,:priority,:status,:success_criteria,:created_at,:updated_at)", goal)
    for skill in _seed("skills.json"):
        connection.execute("""INSERT INTO skills VALUES (:id,:name,:category,:description,:status,:confidence,:success_rate,:usage_count,:last_used_at,:owner_agent_id,:dependencies,:unlock_conditions,:next_validation,:version,:created_at,:updated_at)""", skill)


def _entity_exists(connection: sqlite3.Connection, entity_type: str, entity_id: str) -> bool:
    if entity_type not in ENTITY_TYPES:
        return False
    return connection.execute(f"SELECT 1 FROM {ENTITY_TABLES[entity_type]} WHERE id=?", (entity_id,)).fetchone() is not None


def _validate_relation(connection: sqlite3.Connection, from_type: str, from_id: str, to_type: str, to_id: str, kind: str, check_duplicate: bool = True) -> None:
    if kind not in RELATION_RULES or RELATION_RULES[kind] != (from_type, to_type):
        raise RelationValidationError("unsupported relation kind or entity direction")
    if from_type not in ENTITY_TYPES or to_type not in ENTITY_TYPES:
        raise RelationValidationError("unsupported entity type")
    if from_type == to_type and from_id == to_id:
        raise RelationValidationError("self relation is not allowed")
    if not _entity_exists(connection, from_type, from_id) or not _entity_exists(connection, to_type, to_id):
        raise RelationNotFoundError("relation endpoint does not exist")
    if check_duplicate and connection.execute("SELECT 1 FROM relations WHERE from_entity_type=? AND from_entity_id=? AND to_entity_type=? AND to_entity_id=? AND kind=?", (from_type, from_id, to_type, to_id, kind)).fetchone():
        raise RelationConflictError("relation already exists")


def _insert_relation(connection: sqlite3.Connection, relation_id: str, payload: dict[str, Any], created_at: str, legacy: bool = False) -> None:
    from_type, from_id = payload["from_entity_type"], payload["from_entity_id"]
    to_type, to_id, kind = payload["to_entity_type"], payload["to_entity_id"], payload["kind"]
    _validate_relation(connection, from_type, from_id, to_type, to_id, kind, check_duplicate=not legacy)
    statement = "INSERT OR IGNORE" if legacy else "INSERT"
    connection.execute(f"{statement} INTO relations VALUES (?,?,?,?,?,?,?)", (relation_id, from_type, from_id, to_type, to_id, kind, created_at))


def _legacy_relation_id(payload: dict[str, str]) -> str:
    key = ":".join((payload["from_entity_type"], payload["from_entity_id"], payload["to_entity_type"], payload["to_entity_id"], payload["kind"]))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"living-skill-graph:{key}"))


def _legacy_relations(connection: sqlite3.Connection) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for skill in connection.execute("SELECT id, dependencies FROM skills"):
        records.extend({"from_entity_type": "skill", "from_entity_id": skill["id"], "to_entity_type": "skill", "to_entity_id": dependency, "kind": "depends_on"} for dependency in _ids(skill["dependencies"]))
    for task in connection.execute("SELECT id, related_goal_id, related_skill_id FROM tasks"):
        if task["related_goal_id"]: records.append({"from_entity_type": "task", "from_entity_id": task["id"], "to_entity_type": "goal", "to_entity_id": task["related_goal_id"], "kind": "advances"})
        if task["related_skill_id"]: records.append({"from_entity_type": "task", "from_entity_id": task["id"], "to_entity_type": "skill", "to_entity_id": task["related_skill_id"], "kind": "uses"})
    for artifact in connection.execute("SELECT id, related_goal_ids, related_skill_ids FROM artifacts"):
        records.extend({"from_entity_type": "artifact", "from_entity_id": artifact["id"], "to_entity_type": "goal", "to_entity_id": goal_id, "kind": "contributes_to"} for goal_id in _ids(artifact["related_goal_ids"]))
        records.extend({"from_entity_type": "artifact", "from_entity_id": artifact["id"], "to_entity_type": "skill", "to_entity_id": skill_id, "kind": "demonstrates"} for skill_id in _ids(artifact["related_skill_ids"]))
    for skill in connection.execute("SELECT id, owner_agent_id FROM skills"):
        if skill["owner_agent_id"]: records.append({"from_entity_type": "agent", "from_entity_id": skill["owner_agent_id"], "to_entity_type": "skill", "to_entity_id": skill["id"], "kind": "owns"})
    return records


def migrate_relations(connection: sqlite3.Connection | None = None) -> None:
    owned = connection is None
    connection = connection or connect()
    if connection.execute("SELECT 1 FROM schema_migrations WHERE name=?", (RELATION_MIGRATION,)).fetchone():
        if owned: connection.close()
        return
    try:
        connection.execute("BEGIN IMMEDIATE")
        for payload in _legacy_relations(connection):
            try:
                _insert_relation(connection, _legacy_relation_id(payload), payload, now(), legacy=True)
            except (RelationNotFoundError, RelationValidationError):
                continue
        connection.execute("INSERT INTO schema_migrations VALUES (?,?)", (RELATION_MIGRATION, now()))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if owned: connection.close()


def init_db() -> None:
    connection = connect()
    try:
        _schema(connection)
        _seed_if_empty(connection)
        connection.commit()
        events_path().touch(exist_ok=True)
        migrate_relations(connection)
    finally:
        connection.close()


def rows(table: str) -> list[dict[str, Any]]:
    if table not in TABLES:
        raise ValueError(f"unsupported table: {table}")
    init_db()
    connection = connect()
    try:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid DESC")]
    finally:
        connection.close()


def graph() -> dict[str, list[dict[str, Any]]]:
    return {table: rows(table) for table in TABLES}


def list_relations() -> list[dict[str, Any]]:
    return rows("relations")


def get_relation(relation_id: str) -> dict[str, Any]:
    init_db()
    connection = connect()
    try:
        row = connection.execute("SELECT * FROM relations WHERE id=?", (relation_id,)).fetchone()
        if not row: raise RelationNotFoundError("relation does not exist")
        return dict(row)
    finally:
        connection.close()


def _project(connection: sqlite3.Connection, record: dict[str, Any]) -> None:
    event_type, entity_id, payload, timestamp = record["event_type"], record["entity_id"], record["payload"], record["timestamp"]
    if event_type == "task_created":
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (entity_id, payload["title"], payload.get("description", ""), payload.get("assigned_agent_id", "codex"), payload.get("related_skill_id"), payload.get("related_goal_id"), payload.get("priority", 3), "queued", "", timestamp, None, None))
    elif event_type == "task_claimed": connection.execute("UPDATE tasks SET status='claimed', started_at=? WHERE id=? AND status='queued'", (timestamp, entity_id))
    elif event_type == "task_completed": connection.execute("UPDATE tasks SET status='completed', result=?, completed_at=? WHERE id=? AND status IN ('queued','claimed','running','blocked')", (payload.get("result", ""), timestamp, entity_id))
    elif event_type == "task_failed": connection.execute("UPDATE tasks SET status='failed', result=?, completed_at=? WHERE id=? AND status IN ('queued','claimed','running','blocked')", (payload.get("reason", ""), timestamp, entity_id))
    elif event_type == "skill_used":
        skill = connection.execute("SELECT usage_count, success_rate, confidence FROM skills WHERE id=?", (entity_id,)).fetchone()
        if skill:
            usage = skill["usage_count"] + 1; success = bool(payload.get("success", True))
            connection.execute("UPDATE skills SET usage_count=?, success_rate=?, confidence=?, last_used_at=?, updated_at=? WHERE id=?", (usage, ((skill["success_rate"] * skill["usage_count"]) + int(success)) / usage, min(1.0, max(0.0, skill["confidence"] + (0.04 if success else -0.08))), timestamp, timestamp, entity_id))
    elif event_type == "skill_proposed":
        connection.execute("INSERT OR IGNORE INTO skills VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (entity_id, payload["name"], payload.get("category", "candidate"), payload.get("description", ""), "candidate", 0.0, 0.0, 0, None, record["actor"], json.dumps(payload.get("dependencies", [])), json.dumps(payload.get("unlock_conditions", [])), payload.get("next_validation", "Validate with a task"), "0.1", timestamp, timestamp))
    elif event_type == "skill_status_changed" and payload.get("status") in SKILL_STATUSES: connection.execute("UPDATE skills SET status=?, updated_at=? WHERE id=?", (payload["status"], timestamp, entity_id))
    elif event_type == "artifact_linked": connection.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?)", (entity_id, payload["title"], payload.get("type", "artifact"), payload.get("url"), payload.get("local_path"), payload.get("repository"), payload.get("commit_sha"), record["actor"], json.dumps(payload.get("related_goal_ids", [])), json.dumps(payload.get("related_skill_ids", [])), timestamp))
    elif event_type == "relation_created": _insert_relation(connection, entity_id, payload, timestamp)
    elif event_type == "relation_deleted":
        if not connection.execute("DELETE FROM relations WHERE id=?", (entity_id,)).rowcount: raise RelationNotFoundError("relation does not exist")


def record_event(event_type: str, actor: str, entity_type: str, entity_id: str, payload: dict[str, Any] | None = None, source: str = "api", correlation_id: str | None = None) -> dict[str, Any]:
    init_db()
    record = {"event_id": str(uuid.uuid4()), "event_type": event_type, "timestamp": now(), "actor": actor, "entity_type": entity_type, "entity_id": entity_id, "payload": payload or {}, "source": source, "correlation_id": correlation_id or str(uuid.uuid4())}
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)", (record["event_id"], record["event_type"], record["timestamp"], record["actor"], record["entity_type"], record["entity_id"], json.dumps(record["payload"], ensure_ascii=False), record["source"], record["correlation_id"]))
        _project(connection, record)
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()
    with events_path().open("a", encoding="utf-8") as handle: handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def create_relation(from_entity_type: str, from_entity_id: str, to_entity_type: str, to_entity_id: str, kind: str, actor: str = "web", source: str = "api") -> dict[str, Any]:
    init_db(); connection = connect()
    try: _validate_relation(connection, from_entity_type, from_entity_id, to_entity_type, to_entity_id, kind)
    finally: connection.close()
    relation_id = str(uuid.uuid4())
    payload = {"from_entity_type": from_entity_type, "from_entity_id": from_entity_id, "to_entity_type": to_entity_type, "to_entity_id": to_entity_id, "kind": kind}
    record_event("relation_created", actor, "relation", relation_id, payload, source)
    return get_relation(relation_id)


def delete_relation(relation_id: str, actor: str = "web", source: str = "api") -> dict[str, Any]:
    relation = get_relation(relation_id)
    payload = {key: relation[key] for key in ("from_entity_type", "from_entity_id", "to_entity_type", "to_entity_id", "kind")}
    record_event("relation_deleted", actor, "relation", relation_id, payload, source)
    return relation


def create_task(payload: dict[str, Any], actor: str = "web", source: str = "api") -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    record = record_event("task_created", actor, "task", task_id, payload, source)
    if payload.get("related_goal_id"): create_relation("task", task_id, "goal", payload["related_goal_id"], "advances", actor, source)
    if payload.get("related_skill_id"): create_relation("task", task_id, "skill", payload["related_skill_id"], "uses", actor, source)
    return record


def create_artifact(payload: dict[str, Any], actor: str = "web", source: str = "api") -> dict[str, Any]:
    artifact_id = str(uuid.uuid4())
    record = record_event("artifact_linked", actor, "artifact", artifact_id, payload, source)
    for goal_id in payload.get("related_goal_ids", []): create_relation("artifact", artifact_id, "goal", goal_id, "contributes_to", actor, source)
    for skill_id in payload.get("related_skill_ids", []): create_relation("artifact", artifact_id, "skill", skill_id, "demonstrates", actor, source)
    return record
