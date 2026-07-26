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
        "/health": {
            "status": "healthy",
            "version": "0.4.0",
            "database": {"backend": "sqlite"},
        },
        "/sprints": [{"id": "SPR-003", "name": "Sprint 3 — critique", "status": "completed"}],
        "/overview": {
            "progress_percent": 34.4,
            "blocked_tickets": 1,
            "overdue_tickets": 2,
            "failed_builds": 2,
            "test_coverage": 54.0,
            "as_of": "2026-07-13",
        },
        "/risks": {
            "score": 83.3,
            "severity": "critical",
            "finding_count": 1,
            "agent": "qa-agent-v1",
            "ruleset_version": "qa-rules-v1.0",
            "reference_date": "2026-07-13",
            "confidence_score": 1.0,
            "evidence_coverage": 1.0,
            "analyzed_at": "2026-07-13T09:00:00Z",
            "confidence_details": {
                "components": {
                    "source_coverage": 1.0,
                    "freshness_coverage": 1.0,
                    "relation_coverage": 1.0,
                }
            },
            "missing_information": [],
            "stale_information": [],
            "contributions": [
                {
                    "policy_id": "QA-CRITICAL-BUG-OPEN",
                    "factor": "open_critical_bug",
                    "raw_value": True,
                    "normalized_value": 1.0,
                    "weight": 25.0,
                    "contribution": 25.0,
                    "finding_count": 1,
                }
            ],
            "findings": [
                {
                    "id": "RSK-CRITICAL",
                    "priority": 1,
                    "severity": "critical",
                    "rule_id": "QA-CRITICAL-BUG-OPEN",
                    "source_type": "ticket",
                    "source_id": "TKT-038",
                    "title": "Bug critique toujours ouvert",
                    "description": "TKT-038 est un bug critique.",
                    "evidence": {"priority": "critical", "status": "in_progress"},
                    "recommendation": "Valider le traitement prioritaire.",
                    "detected_at": "2026-07-13T09:00:00Z",
                    "status": "open",
                }
            ],
        },
        "/projects/PRJ-COPILOTE/risk-summary": {
            "delta": {
                "delta": None,
                "current_score": 83.3,
                "previous_score": None,
                "changes": [],
            },
            "pending_recommendation_count": 1,
            "decision_summary": {
                "decision": "NO-GO",
                "reasons": ["Un risque critique bloque la release."],
                "conditions": ["Traiter le risque critique."],
                "priority_actions": ["Valider le traitement prioritaire."],
            },
        },
        "/risks/RSK-CRITICAL/decisions": {
            "risk_id": "RSK-CRITICAL",
            "current_status": "pending",
            "current_decision": None,
            "items": [],
        },
        "/risks/RSK-CRITICAL/explanation": {
            "summary": "TKT-038 est un bug critique.",
            "recommendation": "Valider le traitement prioritaire.",
            "evidence_chain": {
                "nodes": [
                    {
                        "id": "ticket:TKT-038",
                        "type": "ticket",
                        "source_id": "TKT-038",
                        "label": "Ticket TKT-038",
                        "observed_at": "2026-07-09T00:00:00Z",
                        "metadata": {"status": "in_progress"},
                    },
                    {
                        "id": "risk:RSK-CRITICAL",
                        "type": "risk",
                        "source_id": "RSK-CRITICAL",
                        "label": "Risque critique",
                        "observed_at": "2026-07-13T09:00:00Z",
                        "metadata": {"severity": "critical"},
                    },
                ],
                "edges": [
                    {
                        "source": "ticket:TKT-038",
                        "target": "risk:RSK-CRITICAL",
                        "relation": "supports",
                        "label": "soutient le risque",
                    }
                ],
                "missing_links": [],
            },
        },
        "/projects/PRJ-COPILOTE/risk-history": {
            "project_id": "PRJ-COPILOTE",
            "sprint_id": "SPR-003",
            "items": [
                {
                    "snapshot_id": "QAA-1",
                    "calculated_at": "2026-07-13T09:00:00Z",
                    "score": 83.3,
                    "confidence_score": 1.0,
                }
            ],
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
    assert dashboard.title[0].value == "Copilote QA"
    metric_labels = [item.label for item in dashboard.metric]
    assert {
        "Score de risque",
        "Niveau",
        "Évolution du risque",
        "Confiance des données",
        "Travail terminé",
        "Tickets bloqués",
        "Tickets en retard",
        "Builds échoués",
        "Couverture des tests",
        "Risques détectés",
        "Politiques violées",
        "Décisions à valider",
        "Preuves disponibles",
    } <= set(metric_labels)
    selectbox_labels = {item.label for item in dashboard.selectbox}
    assert {"Projet", "Sprint", "Sévérité", "Décision humaine"} <= selectbox_labels
    assert any(item.label == "Analyser maintenant" for item in dashboard.sidebar.button)
    assert {
        "Vue d'ensemble",
        "Risques et décisions",
        "Preuves et évolution",
        "Données détaillées",
    } <= {item.label for item in dashboard.tabs}
    assert any("Livraison déconseillée" in item.value for item in dashboard.error)
    assert any(
        "validation" in item.value.lower() and "humaine" in item.value.lower()
        for item in dashboard.caption
    )
    assert any("TKT-038" in item.value for item in dashboard.markdown)


def test_dashboard_handles_unavailable_api_without_stack_trace(monkeypatch) -> None:
    def unavailable(url, **kwargs):
        raise httpx.ConnectError(
            "connection refused",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", unavailable)
    dashboard = AppTest.from_file("dashboard/app.py").run(timeout=10)

    assert not dashboard.exception
    assert any("indisponible" in item.value for item in dashboard.error)


def test_dashboard_rejects_invalid_project_response(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: FakeResponse({"unexpected": True}),
    )
    dashboard = AppTest.from_file("dashboard/app.py").run(timeout=10)

    assert not dashboard.exception
    assert any("inattendue" in item.value for item in dashboard.error)
