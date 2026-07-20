from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from .database import (
    ROOT,
    RelationConflictError,
    RelationNotFoundError,
    RelationValidationError,
    create_relation,
    create_task,
    delete_relation,
    graph,
    list_relations,
    record_event,
    rows,
)
from .snapshot import build_snapshot

@asynccontextmanager
async def lifespan(_: FastAPI):
    build_snapshot()
    yield


app = FastAPI(title="Living AI Skill Graph v2", version="2.0.0", lifespan=lifespan)
APP_DIR = ROOT / "app"


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    assigned_agent_id: str = "codex"
    related_skill_id: str | None = None
    related_goal_id: str | None = None
    priority: int = Field(default=3, ge=1, le=5)


class EventInput(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    actor: str = "web"
    entity_type: str = Field(min_length=1, max_length=40)
    entity_id: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)


class RelationInput(BaseModel):
    from_entity_type: Literal["agent", "goal", "skill", "task", "artifact"]
    from_entity_id: str = Field(min_length=1, max_length=120)
    to_entity_type: Literal["agent", "goal", "skill", "task", "artifact"]
    to_entity_id: str = Field(min_length=1, max_length=120)
    kind: Literal["owns", "requires", "depends_on", "advances", "uses", "produces", "demonstrates", "contributes_to"]


@app.get("/api/graph")
def get_graph() -> dict:
    return graph()


@app.get("/api/skills")
def list_skills() -> list[dict]:
    return rows("skills")


@app.get("/api/skills/{skill_id}")
def get_skill(skill_id: str) -> dict:
    for skill in rows("skills"):
        if skill["id"] == skill_id:
            return skill
    raise HTTPException(status_code=404, detail="skill not found")


@app.get("/api/goals")
def list_goals() -> list[dict]:
    return rows("goals")


@app.get("/api/tasks")
def list_tasks(status: str | None = None) -> list[dict]:
    tasks = rows("tasks")
    return [task for task in tasks if status is None or task["status"] == status]


@app.get("/api/relations")
def get_relations() -> list[dict]:
    return list_relations()


@app.post("/api/relations", status_code=201)
def post_relation(data: RelationInput) -> dict:
    try:
        return create_relation(**data.model_dump())
    except RelationConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RelationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RelationValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/relations/{relation_id}")
def remove_relation(relation_id: str) -> dict:
    try:
        return delete_relation(relation_id)
    except RelationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/tasks", status_code=201)
def post_task(data: TaskInput) -> dict:
    return create_task(data.model_dump())


@app.post("/api/events", status_code=201)
def post_event(data: EventInput) -> dict:
    return record_event(data.event_type, data.actor, data.entity_type, data.entity_id, data.payload)


@app.get("/api/activity")
def activity() -> list[dict]:
    return rows("events")[:50]


@app.post("/api/snapshot")
def make_snapshot() -> dict:
    record_event("snapshot_published", "web", "snapshot", "public-snapshot", {}, source="api")
    return {"path": str(build_snapshot().relative_to(ROOT))}


app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="app")
