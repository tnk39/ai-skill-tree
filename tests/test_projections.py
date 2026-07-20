from server.database import create_task, record_event, rows
from server.projections import is_allowed_event, is_allowed_skill_status


def test_projection_vocabulary_is_explicit():
    assert is_allowed_event("task_created")
    assert not is_allowed_event("invented")
    assert is_allowed_skill_status("verified")
    assert not is_allowed_skill_status("invented")


def test_completed_task_cannot_be_rewritten(isolated_graph):
    task_id = create_task({"title": "one way"})["entity_id"]
    record_event("task_completed", "test", "task", task_id, {"result": "ok"}, source="test")
    record_event("task_failed", "test", "task", task_id, {"reason": "late"}, source="test")
    task = next(task for task in rows("tasks") if task["id"] == task_id)
    assert task["status"] == "completed"
