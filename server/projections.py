"""Projection contract used by the SQLite event store.

The concrete dispatcher remains in ``database._project`` so the transaction and
the state update share one connection; this module exposes the invariants for
callers and tests without adding another persistence layer.
"""

from .models import ENTITY_TYPES, EVENT_TYPES, RELATION_KINDS, RELATION_RULES, SKILL_STATUSES, TASK_STATUSES


def is_allowed_event(event_type: str) -> bool:
    return event_type in EVENT_TYPES


def is_allowed_skill_status(status: str) -> bool:
    return status in SKILL_STATUSES


def is_allowed_entity_type(entity_type: str) -> bool:
    return entity_type in ENTITY_TYPES


def is_allowed_relation(kind: str, from_entity_type: str, to_entity_type: str) -> bool:
    return kind in RELATION_KINDS and RELATION_RULES[kind] == (from_entity_type, to_entity_type)
