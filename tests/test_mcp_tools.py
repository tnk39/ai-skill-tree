from mcp_server import tools


def test_mcp_task_to_skill_direction(isolated_graph):
    created = tools.create_graph_task("MCP task", related_skill_id="skill-html-css-js")
    task_id = created["entity_id"]
    tools.claim_task(task_id)
    tools.record_skill_usage("skill-html-css-js", success=True)
    tools.complete_task(task_id, "done")
    task = next(task for task in tools.list_tasks() if task["id"] == task_id)
    assert task["status"] == "completed"
    assert tools.get_skill_graph()["events"]
