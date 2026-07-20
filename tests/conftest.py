from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def isolated_graph(monkeypatch: pytest.MonkeyPatch) -> Path:
    path = ROOT / ".test-runtime" / str(uuid.uuid4())
    monkeypatch.setenv("SKILL_GRAPH_DATA_DIR", str(path))
    return path
