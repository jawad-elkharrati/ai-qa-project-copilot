from pathlib import Path
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


def empty_state_responses() -> dict[str, object]:
    return {
        "/projects": [
            {"id": "PRJ-COPILOTE", "key": "COPQA", "name": "NovaShop", "description": ""}
        ],
        "/risks": {
            "score": 10,
            "severity": "low",
            "finding_count": 0,
            "reference_date": "2026-07-20",
            "confidence_score": 0.5,
            "evidence_coverage": 0.4,
            "contributions": [],
            "findings": [],
            "missing_information": [{"code": "coverage_missing"}],
        },
        "/projects/PRJ-COPILOTE/risk-summary": {
            "delta": {"delta": 0},
        },
        "/projects/PRJ-COPILOTE/decision-brief": {
            "snapshot_id": "QAH-NS-20260720",
            "generated_at": "2026-07-20T09:00:00Z",
            "suggested_decision": "INSUFFICIENT_INFORMATION",
            "justification": "Informations insuffisantes.",
            "blockers": [],
            "conditions": ["Completer les preuves."],
            "violated_policies": [],
            "missing_information": ["coverage_missing"],
            "human_validation_status": "PENDING",
            "latest_review": None,
        },
        "/projects/PRJ-COPILOTE/recommendations": [],
        "/projects/PRJ-COPILOTE/reports/daily": {
            "suggested_decision": "INSUFFICIENT_INFORMATION",
            "decision_justification": "Informations insuffisantes.",
        },
        "/projects/PRJ-COPILOTE/reports/weekly": {
            "score_evolution": [],
            "trend": "STABLE",
            "suggested_next_decision": "INSUFFICIENT_INFORMATION",
            "summary": "Donnees insuffisantes.",
            "contribution_evolution": {},
            "new_risks": [],
            "resolved_risks": [],
            "recommendations_emitted": 0,
            "recommendation_statuses": {},
            "human_decisions": {},
        },
    }


def test_dashboard_has_clean_empty_and_insufficient_information_states(monkeypatch) -> None:
    responses = empty_state_responses()

    def fake_get(url, **kwargs):
        return FakeResponse(responses[urlparse(url).path])

    monkeypatch.setattr(httpx, "get", fake_get)
    dashboard = AppTest.from_file("dashboard/app.py").run(timeout=10)

    assert not dashboard.exception
    warnings = [item.value for item in dashboard.warning]
    information = [item.value for item in dashboard.info]
    assert any("ne permettent pas encore" in item for item in warnings)
    assert any("liste des risques est vide" in item for item in information)
    assert any("Aucune recommandation" in item for item in information)
    assert any("Aucune evolution" in item for item in information)


def test_dashboard_has_a_clean_no_project_state(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: FakeResponse([]))
    dashboard = AppTest.from_file("dashboard/app.py").run(timeout=10)

    assert not dashboard.exception
    assert any("Aucun projet disponible" in item.value for item in dashboard.warning)


def test_dashboard_reports_a_section_api_error_without_stack_trace(monkeypatch) -> None:
    responses = empty_state_responses()

    def fake_get(url, **kwargs):
        path = urlparse(url).path
        if path.endswith("/reports/daily"):
            request = httpx.Request("GET", url)
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("missing report", request=request, response=response)
        return FakeResponse(responses[path])

    monkeypatch.setattr(httpx, "get", fake_get)
    dashboard = AppTest.from_file("dashboard/app.py").run(timeout=10)

    assert not dashboard.exception
    assert any("HTTP 404" in item.value for item in dashboard.error)


def test_dashboard_module_is_api_only_and_contains_loading_state() -> None:
    source = Path("dashboard/mvp_dashboard.py").read_text(encoding="utf-8")

    assert "from app." not in source
    assert "import app." not in source
    assert "evaluate_decision" not in source
    assert "prioritize_recommendation" not in source
    assert "st.spinner" in source
    for label in ("Synthese", "Risques", "Decision", "Recommandations", "Rapports", "Evolution"):
        assert f'"{label}"' in source
    for api_path in (
        "/start",
        "/complete",
        "/outcome",
        "/reports/{report_kind}/export",
    ):
        assert api_path in source
    assert "api_get_content" in source
    assert ".download_button(" in source


def test_dashboard_api_client_downloads_api_rendered_content(monkeypatch) -> None:
    from dashboard.api_client import api_get_content

    class DownloadResponse:
        content = b"# Rapport QA"
        headers = {"content-type": "text/markdown; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return DownloadResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    content, media_type = api_get_content(
        "/projects/PRJ-COPILOTE/reports/daily/export",
        report_date="2026-07-20",
        format="markdown",
    )

    assert content == b"# Rapport QA"
    assert media_type == "text/markdown; charset=utf-8"
    assert captured["params"]["format"] == "markdown"
