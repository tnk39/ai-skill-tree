"""Shared state vocabulary for the event projections."""

SKILL_STATUSES = {"locked", "candidate", "trial", "verified", "stable", "improve", "deprecated"}
TASK_STATUSES = {"queued", "claimed", "running", "blocked", "completed", "failed", "cancelled"}
EVENT_TYPES = {
    "goal_created", "goal_updated", "skill_proposed", "skill_used", "skill_verified",
    "skill_status_changed", "task_created", "task_claimed", "task_completed", "task_failed",
    "artifact_created", "artifact_linked", "agent_activity", "failure_recorded", "snapshot_published",
}
