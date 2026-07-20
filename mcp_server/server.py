from mcp.server.fastmcp import FastMCP

from . import tools

mcp = FastMCP("living-ai-skill-graph")


@mcp.tool()
def get_skill_graph() -> dict: return tools.get_skill_graph()
@mcp.tool()
def list_tasks(status: str | None = None) -> list[dict]: return tools.list_tasks(status)
@mcp.tool()
def claim_task(task_id: str) -> dict: return tools.claim_task(task_id)
@mcp.tool()
def complete_task(task_id: str, result: str) -> dict: return tools.complete_task(task_id, result)
@mcp.tool()
def fail_task(task_id: str, reason: str) -> dict: return tools.fail_task(task_id, reason)
@mcp.tool()
def record_skill_usage(skill_id: str, success: bool = True) -> dict: return tools.record_skill_usage(skill_id, success)
@mcp.tool()
def record_failure(skill_id: str, reason: str) -> dict: return tools.record_failure(skill_id, reason)
@mcp.tool()
def propose_skill(name: str, description: str = "") -> dict: return tools.propose_skill(name, description)
@mcp.tool()
def update_skill_status(skill_id: str, status: str) -> dict: return tools.update_skill_status(skill_id, status)
@mcp.tool()
def link_artifact(title: str, related_skill_ids: list[str]) -> dict: return tools.link_artifact(title, related_skill_ids)
@mcp.tool()
def get_goal_status() -> list[dict]: return tools.get_goal_status()
@mcp.tool()
def get_next_unlocks() -> list[dict]: return tools.get_next_unlocks()
@mcp.tool()
def publish_snapshot() -> dict: return tools.publish_snapshot()

if __name__ == "__main__":
    mcp.run(transport="stdio")
