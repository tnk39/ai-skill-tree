from __future__ import annotations

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .database import ROOT, create_task, graph, record_event, rows

app = FastAPI(title="Living AI Skill Graph v2", version="2.0.0")
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


@app.post("/api/tasks", status_code=201)
def post_task(data: TaskInput) -> dict:
    return create_task(data.model_dump())


@app.post("/api/events", status_code=201)
def post_event(data: EventInput) -> dict:
    return record_event(data.event_type, data.actor, data.entity_type, data.entity_id, data.payload)


@app.get("/api/activity")
def activity() -> list[dict]:
    return rows("events")[:50]


app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="app")
