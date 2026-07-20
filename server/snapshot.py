"""Build a privacy-filtered public projection; runtime details never leave SQLite."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from .database import ROOT, graph

PUBLIC_FILE = ROOT / "public" / "public-snapshot.json"


def _keep(item: dict, names: tuple[str, ...]) -> dict:
    return {name: item.get(name) for name in names}


def _public_id(value: str | None) -> str | None:
    if not value:
        return None
    return f"node-{sha256(value.encode('utf-8')).hexdigest()[:16]}"


def _public_record(item: dict, names: tuple[str, ...]) -> dict:
    record = _keep(item, names)
    record["id"] = _public_id(item.get("id"))
    return record


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


def _relationship(source: str | None, target: str | None, kind: str) -> dict | None:
    source_id, target_id = _public_id(source), _public_id(target)
    if not source_id or not target_id:
        return None
    return {"from": source_id, "to": target_id, "kind": kind}


def _relationships(data: dict) -> list[dict]:
    records: list[dict] = []

    def add(source: str | None, target: str | None, kind: str) -> None:
        relation = _relationship(source, target, kind)
        if relation:
            records.append(relation)

    for skill in data["skills"]:
        add(skill.get("owner_agent_id"), skill.get("id"), "owns")
        for dependency in _ids(skill.get("dependencies")):
            add(skill.get("id"), dependency, "depends_on")
    for task in data["tasks"]:
        add(task.get("id"), task.get("related_skill_id"), "task_relates_to_skill")
        add(task.get("id"), task.get("related_goal_id"), "task_relates_to_goal")
    for artifact in data["artifacts"]:
        for goal_id in _ids(artifact.get("related_goal_ids")):
            add(artifact.get("id"), goal_id, "artifact_relates_to_goal")
        for skill_id in _ids(artifact.get("related_skill_ids")):
            add(artifact.get("id"), skill_id, "artifact_relates_to_skill")
    return records


def build_snapshot(destination: Path = PUBLIC_FILE) -> Path:
    data = graph()
    snapshot = {
        "schema_version": 2,
        "agents": [_public_record(x, ("name", "type", "role", "status")) for x in data["agents"]],
        "goals": [_public_record(x, ("title", "priority", "status")) for x in data["goals"]],
        "skills": [_public_record(x, ("name", "category", "status", "confidence", "success_rate", "usage_count")) for x in data["skills"]],
        "tasks": [_public_record(x, ("title", "priority", "status")) for x in data["tasks"]],
        "artifacts": [_public_record(x, ("title", "type")) for x in data["artifacts"]],
        "relationships": _relationships(data),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
