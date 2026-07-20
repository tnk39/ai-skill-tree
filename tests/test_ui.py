from pathlib import Path

from fastapi.testclient import TestClient

from server.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_local_ui_has_no_external_script_or_api_reference():
    html = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app" / "app.js").read_text(encoding="utf-8")
    assert 'src="app.js"' in html
    assert "https://" not in html
    assert "https://" not in script
    assert "/api/graph" in script


def test_ui_includes_graph_filters_and_task_entry():
    html = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    assert 'data-filter="skill"' in html
    assert 'id="task-form"' in html
    assert 'id="activity-list"' in html


def test_local_server_serves_the_operations_ui(isolated_graph):
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Living AI Skill Graph" in response.text
