"""Build a privacy-filtered public projection; runtime details never leave SQLite."""

from __future__ import annotations

import json
from pathlib import Path

from .database import ROOT, graph

PUBLIC_FILE = ROOT / "public" / "public-snapshot.json"


def _keep(item: dict, names: tuple[str, ...]) -> dict:
    return {name: item.get(name) for name in names}


def build_snapshot(destination: Path = PUBLIC_FILE) -> Path:
    data = graph()
    snapshot = {
        "schema_version": 1,
        "agents": [_keep(x, ("id", "name", "type", "role", "status")) for x in data["agents"]],
        "goals": [_keep(x, ("id", "title", "priority", "status")) for x in data["goals"]],
        "skills": [_keep(x, ("id", "name", "category", "status", "confidence", "success_rate", "usage_count", "owner_agent_id")) for x in data["skills"]],
        "tasks": [_keep(x, ("id", "title", "related_skill_id", "related_goal_id", "priority", "status", "created_at", "completed_at")) for x in data["tasks"]],
        "artifacts": [_keep(x, ("id", "title", "type", "repository", "commit_sha", "related_goal_ids", "related_skill_ids", "created_at")) for x in data["artifacts"]],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
