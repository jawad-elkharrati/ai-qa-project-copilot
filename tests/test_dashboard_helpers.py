import pytest

from dashboard.formatting import (
    decision_label,
    decision_payload,
    delta_label,
    global_message,
    human_datetime,
    ordered_evidence_nodes,
    readable_evidence_edges,
    readiness_label,
    risk_status_label,
    source_label,
)


@pytest.mark.parametrize(
    ("status", "expected_modified"),
    [
        ("accepted", None),
        ("modified", "Nouvelle recommandation"),
        ("rejected", None),
    ],
)
def test_human_decision_payloads(status: str, expected_modified: str | None) -> None:
    payload = decision_payload(
        status=status,
        actor="Responsable QA",
        comment="Décision contrôlée",
        modified_recommendation="Nouvelle recommandation",
    )
    assert payload["status"] == status
    assert payload["decided_by"] == "Responsable QA"
    assert payload["modified_recommendation"] == expected_modified


def test_evidence_nodes_are_rendered_in_business_order() -> None:
    nodes = [
        {"type": "risk", "source_id": "RSK-1"},
        {"type": "build", "source_id": "BLD-1"},
        {"type": "ticket", "source_id": "TKT-1"},
        {"type": "commit", "source_id": "COM-1"},
        {"type": "pull_request", "source_id": "PR-1"},
        {"type": "test_result", "source_id": "TST-1"},
    ]
    assert [item["type"] for item in ordered_evidence_nodes(nodes)] == [
        "ticket",
        "pull_request",
        "commit",
        "build",
        "test_result",
        "risk",
    ]


def test_global_messages_are_data_driven() -> None:
    assert "bloquent" in global_message("critical", 3)
    assert "Aucun contrôle" in global_message("low", 0)


def test_technical_values_have_plain_language_labels() -> None:
    assert readiness_label("NO-GO") == "Livraison déconseillée"
    assert readiness_label("GO WITH CONDITIONS") == "Livraison sous conditions"
    assert decision_label("pending") == "À valider"
    assert decision_label("modified") == "Modifiée"
    assert source_label("test_result") == "Résultat de test"
    assert risk_status_label("open") == "Ouvert"


def test_delta_label_explains_the_direction() -> None:
    assert delta_label(None) == "Première analyse"
    assert delta_label(0) == "Stable"
    assert delta_label(12.5) == "+12.5 (hausse)"
    assert delta_label(-4.0) == "-4.0 (baisse)"


def test_iso_dates_are_rendered_for_humans() -> None:
    assert human_datetime("2026-07-23T22:28:28.472365") == "23 juillet 2026 à 22:28"
    assert human_datetime(None) == "Non renseigné"
    assert human_datetime("date inconnue") == "date inconnue"


def test_readable_edges_only_render_real_relations() -> None:
    nodes = [
        {"id": "ticket:TKT-1", "label": "Ticket TKT-1"},
        {"id": "commit:COM-1", "label": "Commit COM-1"},
        {"id": "commit:COM-2", "label": "Commit COM-2"},
    ]
    edges = [
        {
            "source": "ticket:TKT-1",
            "target": "commit:COM-1",
            "label": "est implémenté par",
        },
        {
            "source": "ticket:TKT-1",
            "target": "commit:COM-2",
            "label": "est implémenté par",
        },
    ]
    relations = readable_evidence_edges(nodes, edges)

    assert relations == [
        "Ticket TKT-1 — est implémenté par → Commit COM-1",
        "Ticket TKT-1 — est implémenté par → Commit COM-2",
    ]
