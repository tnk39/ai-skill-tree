"""Shared vocabulary for event projections and graph relationships."""

ENTITY_TYPES = {"agent", "goal", "skill", "task", "artifact"}
ENTITY_TABLES = {"agent": "agents", "goal": "goals", "skill": "skills", "task": "tasks", "artifact": "artifacts"}
SKILL_STATUSES = {"locked", "candidate", "trial", "verified", "stable", "improve", "deprecated"}
TASK_STATUSES = {"queued", "claimed", "running", "blocked", "completed", "failed", "cancelled"}
RELATION_RULES = {
    "owns": ("agent", "skill"),
    "requires": ("goal", "skill"),
    "depends_on": ("skill", "skill"),
    "advances": ("task", "goal"),
    "uses": ("task", "skill"),
    "produces": ("task", "artifact"),
    "demonstrates": ("artifact", "skill"),
    "contributes_to": ("artifact", "goal"),
}
RELATION_KINDS = set(RELATION_RULES)
EVENT_TYPES = {
    "goal_created", "goal_updated", "skill_proposed", "skill_used", "skill_verified",
    "skill_status_changed", "task_created", "task_claimed", "task_completed", "task_failed",
    "artifact_created", "artifact_linked", "agent_activity", "failure_recorded", "snapshot_published",
    "relation_created", "relation_deleted",
}
