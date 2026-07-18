from urllib.parse import urlparse

import httpx
from streamlit.testing.v1 import AppTest


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


def test_dashboard_displays_project_filters_and_kpis(monkeypatch) -> None:
    responses = {
        "/projects": [
            {"id": "PRJ-COPILOTE", "key": "COPQA", "name": "NovaShop", "description": ""}
        ],
        "/sprints": [
            {"id": "SPR-003", "name": "Sprint 3 — critique", "status": "completed"}
        ],
        "/overview": {
            "progress_percent": 34.4,
            "blocked_tickets": 1,
            "overdue_tickets": 2,
            "failed_builds": 2,
            "test_coverage": 54.0,
            "as_of": "2026-07-13",
        },
        "/tickets": [{"id": "TKT-038", "status": "blocked"}],
        "/metrics": [{"name": "test_coverage", "value": 54.0, "unit": "percent"}],
        "/ingestions": [{"id": "ING-001", "status": "success"}],
    }

    def fake_get(url, **kwargs):
        return FakeResponse(responses[urlparse(url).path])

    monkeypatch.setattr(httpx, "get", fake_get)
    dashboard = AppTest.from_file("dashboard/app.py").run(timeout=10)

    assert not dashboard.exception
    assert dashboard.title[0].value == "Copilote IA QA — Dashboard V0"
    assert [item.label for item in dashboard.metric] == [
        "Progression",
        "Tickets bloqués",
        "Tickets en retard",
        "Builds échoués",
        "Couverture",
    ]
    assert [item.value for item in dashboard.metric] == ["34.4 %", "1", "2", "2", "54.0 %"]
    assert [item.label for item in dashboard.selectbox] == ["Projet", "Sprint"]
