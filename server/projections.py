"""Projection contract used by the SQLite event store.

The concrete dispatcher remains in ``database._project`` so the transaction and
the state update share one connection; this module exposes the invariants for
callers and tests without adding another persistence layer.
"""

from .models import EVENT_TYPES, SKILL_STATUSES, TASK_STATUSES


def is_allowed_event(event_type: str) -> bool:
    return event_type in EVENT_TYPES


def is_allowed_skill_status(status: str) -> bool:
    return status in SKILL_STATUSES
