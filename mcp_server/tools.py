from __future__ import annotations

from typing import Any

from server.database import create_artifact, create_relation, create_task, delete_relation, graph, list_relations, record_event, rows
from server.snapshot import build_snapshot


def get_skill_graph() -> dict[str, list[dict[str, Any]]]:
    return graph()


def list_tasks(status: str | None = None) -> list[dict[str, Any]]:
    return [task for task in rows("tasks") if status is None or task["status"] == status]


def claim_task(task_id: str, actor: str = "codex") -> dict[str, Any]:
    return record_event("task_claimed", actor, "task", task_id, {}, source="mcp")


def complete_task(task_id: str, result: str, actor: str = "codex") -> dict[str, Any]:
    return record_event("task_completed", actor, "task", task_id, {"result": result}, source="mcp")


def fail_task(task_id: str, reason: str, actor: str = "codex") -> dict[str, Any]:
    return record_event("task_failed", actor, "task", task_id, {"reason": reason}, source="mcp")


def record_skill_usage(skill_id: str, success: bool = True, actor: str = "codex") -> dict[str, Any]:
    return record_event("skill_used", actor, "skill", skill_id, {"success": success}, source="mcp")


def record_failure(skill_id: str, reason: str, actor: str = "codex") -> dict[str, Any]:
    return record_event("failure_recorded", actor, "skill", skill_id, {"reason": reason}, source="mcp")


def propose_skill(name: str, description: str = "", actor: str = "codex") -> dict[str, Any]:
    return record_event("skill_proposed", actor, "skill", f"candidate-{name.lower().replace(' ', '-')}", {"name": name, "description": description}, source="mcp")


def update_skill_status(skill_id: str, status: str, actor: str = "codex") -> dict[str, Any]:
    return record_event("skill_status_changed", actor, "skill", skill_id, {"status": status}, source="mcp")


def link_artifact(title: str, related_skill_ids: list[str], actor: str = "codex") -> dict[str, Any]:
    return create_artifact({"title": title, "related_skill_ids": related_skill_ids}, actor=actor, source="mcp")


def list_graph_relations() -> list[dict[str, Any]]:
    return list_relations()


def create_graph_relation(
    from_entity_type: str,
    from_entity_id: str,
    to_entity_type: str,
    to_entity_id: str,
    kind: str,
    actor: str = "codex",
) -> dict[str, Any]:
    return create_relation(from_entity_type, from_entity_id, to_entity_type, to_entity_id, kind, actor=actor, source="mcp")


def delete_graph_relation(relation_id: str, actor: str = "codex") -> dict[str, Any]:
    return delete_relation(relation_id, actor=actor, source="mcp")


def get_goal_status() -> list[dict[str, Any]]:
    return rows("goals")


def get_next_unlocks() -> list[dict[str, Any]]:
    return [skill for skill in rows("skills") if skill["status"] in {"candidate", "trial", "improve"}]


def publish_snapshot() -> dict[str, str]:
    record_event("snapshot_published", "codex", "snapshot", "public-snapshot", {}, source="mcp")
    return {"snapshot": str(build_snapshot().name)}


def create_graph_task(title: str, description: str = "", related_skill_id: str | None = None) -> dict[str, Any]:
    return create_task({"title": title, "description": description, "related_skill_id": related_skill_id}, actor="mcp", source="mcp")
