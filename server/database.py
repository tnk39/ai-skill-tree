"""Append-only event store with SQLite state projections."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("agents", "goals", "skills", "tasks", "artifacts", "events")
SKILL_STATUSES = {"locked", "candidate", "trial", "verified", "stable", "improve", "deprecated"}


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


def init_db() -> None:
    connection = connect()
    events_path().touch(exist_ok=True)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS agents (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
          model TEXT, role TEXT, status TEXT NOT NULL, last_active_at TEXT
        );
        CREATE TABLE IF NOT EXISTS goals (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
          priority INTEGER NOT NULL, status TEXT NOT NULL,
          success_criteria TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS skills (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT,
          description TEXT, status TEXT NOT NULL, confidence REAL NOT NULL,
          success_rate REAL NOT NULL, usage_count INTEGER NOT NULL,
          last_used_at TEXT, owner_agent_id TEXT, dependencies TEXT NOT NULL,
          unlock_conditions TEXT NOT NULL, next_validation TEXT, version TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
          assigned_agent_id TEXT, related_skill_id TEXT, related_goal_id TEXT,
          priority INTEGER NOT NULL, status TEXT NOT NULL, result TEXT,
          created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS artifacts (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT, url TEXT,
          local_path TEXT, repository TEXT, commit_sha TEXT,
          created_by_agent_id TEXT, related_goal_ids TEXT NOT NULL,
          related_skill_ids TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
          event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, timestamp TEXT NOT NULL,
          actor TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
          payload TEXT NOT NULL, source TEXT NOT NULL, correlation_id TEXT NOT NULL
        );
        """
    )
    if not connection.execute("SELECT 1 FROM agents LIMIT 1").fetchone():
        for agent in _seed("agents.json"):
            connection.execute(
                "INSERT INTO agents VALUES (:id,:name,:type,:model,:role,:status,:last_active_at)", agent
            )
        for goal in _seed("goals.json"):
            connection.execute(
                """INSERT INTO goals VALUES
                (:id,:title,:description,:priority,:status,:success_criteria,:created_at,:updated_at)""",
                goal,
            )
        for skill in _seed("skills.json"):
            connection.execute(
                """INSERT INTO skills VALUES
                (:id,:name,:category,:description,:status,:confidence,:success_rate,:usage_count,
                :last_used_at,:owner_agent_id,:dependencies,:unlock_conditions,:next_validation,
                :version,:created_at,:updated_at)""",
                skill,
            )
        connection.commit()
    connection.close()


def rows(table: str) -> list[dict[str, Any]]:
    if table not in TABLES:
        raise ValueError(f"unsupported table: {table}")
    init_db()
    connection = connect()
    result = [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid DESC")]
    connection.close()
    return result


def graph() -> dict[str, list[dict[str, Any]]]:
    return {table: rows(table) for table in TABLES}


def _project(connection: sqlite3.Connection, record: dict[str, Any]) -> None:
    event_type, entity_id, payload = record["event_type"], record["entity_id"], record["payload"]
    timestamp = record["timestamp"]
    if event_type == "task_created":
        connection.execute(
            """INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entity_id, payload["title"], payload.get("description", ""), payload.get("assigned_agent_id", "codex"),
             payload.get("related_skill_id"), payload.get("related_goal_id"), payload.get("priority", 3),
             "queued", "", timestamp, None, None),
        )
    elif event_type == "task_claimed":
        connection.execute("UPDATE tasks SET status='claimed', started_at=? WHERE id=? AND status='queued'", (timestamp, entity_id))
    elif event_type == "task_completed":
        connection.execute("UPDATE tasks SET status='completed', result=?, completed_at=? WHERE id=? AND status IN ('queued','claimed','running','blocked')", (payload.get("result", ""), timestamp, entity_id))
    elif event_type == "task_failed":
        connection.execute("UPDATE tasks SET status='failed', result=?, completed_at=? WHERE id=? AND status IN ('queued','claimed','running','blocked')", (payload.get("reason", ""), timestamp, entity_id))
    elif event_type == "skill_used":
        success = bool(payload.get("success", True))
        skill = connection.execute("SELECT usage_count, success_rate, confidence FROM skills WHERE id=?", (entity_id,)).fetchone()
        if skill:
            usage = skill["usage_count"] + 1
            rate = ((skill["success_rate"] * skill["usage_count"]) + int(success)) / usage
            confidence = min(1.0, max(0.0, skill["confidence"] + (0.04 if success else -0.08)))
            connection.execute("UPDATE skills SET usage_count=?, success_rate=?, confidence=?, last_used_at=?, updated_at=? WHERE id=?", (usage, rate, confidence, timestamp, timestamp, entity_id))
    elif event_type == "skill_proposed":
        connection.execute(
            """INSERT OR IGNORE INTO skills VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entity_id, payload["name"], payload.get("category", "candidate"), payload.get("description", ""),
             "candidate", 0.0, 0.0, 0, None, record["actor"], json.dumps(payload.get("dependencies", [])),
             json.dumps(payload.get("unlock_conditions", [])), payload.get("next_validation", "Validate with a task"),
             "0.1", timestamp, timestamp),
        )
    elif event_type == "skill_status_changed" and payload.get("status") in SKILL_STATUSES:
        connection.execute("UPDATE skills SET status=?, updated_at=? WHERE id=?", (payload["status"], timestamp, entity_id))
    elif event_type == "artifact_linked":
        connection.execute(
            """INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (entity_id, payload["title"], payload.get("type", "artifact"), payload.get("url"), payload.get("local_path"),
             payload.get("repository"), payload.get("commit_sha"), record["actor"],
             json.dumps(payload.get("related_goal_ids", [])), json.dumps(payload.get("related_skill_ids", [])), timestamp),
        )


def record_event(event_type: str, actor: str, entity_type: str, entity_id: str, payload: dict[str, Any] | None = None, source: str = "api", correlation_id: str | None = None) -> dict[str, Any]:
    init_db()
    record = {
        "event_id": str(uuid.uuid4()), "event_type": event_type, "timestamp": now(), "actor": actor,
        "entity_type": entity_type, "entity_id": entity_id, "payload": payload or {}, "source": source,
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)", (
            record["event_id"], record["event_type"], record["timestamp"], record["actor"], record["entity_type"],
            record["entity_id"], json.dumps(record["payload"], ensure_ascii=False), record["source"], record["correlation_id"],
        ))
        _project(connection, record)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    # SQLite is authoritative; JSONL is an append-only audit mirror written after commit.
    with events_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def create_task(payload: dict[str, Any], actor: str = "web", source: str = "api") -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    return record_event("task_created", actor, "task", task_id, payload, source)
