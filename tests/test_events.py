import json

from server.database import create_task, record_event, rows


def test_event_is_projected_and_mirrored_to_jsonl(isolated_graph):
    created = create_task({"title": "Validate a graph", "related_skill_id": "skill-html-css-js"})
    task_id = created["entity_id"]
    record_event("task_claimed", "codex", "task", task_id, {}, source="test")
    record_event("task_completed", "codex", "task", task_id, {"result": "passed"}, source="test")
    task = next(item for item in rows("tasks") if item["id"] == task_id)
    assert task["status"] == "completed"
    events = [json.loads(line) for line in (isolated_graph / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == ["task_created", "relation_created", "task_claimed", "task_completed"]


def test_skill_usage_changes_only_its_projection(isolated_graph):
    before = next(item for item in rows("skills") if item["id"] == "skill-html-css-js")
    record_event("skill_used", "codex", "skill", "skill-html-css-js", {"success": True}, source="test")
    after = next(item for item in rows("skills") if item["id"] == "skill-html-css-js")
    assert after["usage_count"] == before["usage_count"] + 1
    assert after["confidence"] > before["confidence"]
