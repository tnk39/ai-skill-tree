# Phase 1 — Vertical slice

## Scope

This branch introduces a local-only, event-sourced Living AI Skill Graph v2. It does not modify the legacy root `index.html`, `main`, GitHub Pages, or any remote.

## Architecture

- SQLite is the authoritative event store and read-model store (`data/skill_graph.sqlite3`, runtime-only).
- `data/events.jsonl` is an append-only audit mirror written after a successful SQLite transaction.
- `server/database.py` applies deterministic projections for task and skill events.
- FastAPI exposes local REST reads and writes; `mcp_server/server.py` exposes the approved stdio MCP write tools.
- `app/` is the local operations UI. It uses only browser SVG and local assets; no CDN or external request is used.
- `public/public-snapshot.json` is a privacy-filtered read-only projection. It excludes task descriptions/results, artifact local paths/URLs, event payloads, and model/runtime details.

## State direction

`Task created → Task claimed → skill_used → Task completed`

The state projection records task status and updates only the linked skill's use statistics. A missing or invalid entity is retained as an audit event but is not fabricated into a successful capability.

## Local run

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8765
.\.venv\Scripts\python.exe -m mcp_server.server
.\.venv\Scripts\python.exe -m pytest -q
```

No API keys, external LLMs, Codex launch, GitHub push, or automatic execution are part of this phase.
