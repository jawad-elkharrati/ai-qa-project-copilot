from __future__ import annotations

from datetime import datetime

SEVERITY_LABELS = {
    "low": "Faible",
    "medium": "Moyen",
    "high": "Élevé",
    "critical": "Critique",
}
DECISION_LABELS = {
    "pending": "À valider",
    "accepted": "Acceptée",
    "modified": "Modifiée",
    "rejected": "Rejetée",
}
READINESS_LABELS = {
    "GO": "Livraison envisageable",
    "GO WITH CONDITIONS": "Livraison sous conditions",
    "NO-GO": "Livraison déconseillée",
}
SOURCE_LABELS = {
    "ticket": "Ticket",
    "pull_request": "Pull Request",
    "commit": "Commit",
    "build": "Build",
    "test_result": "Résultat de test",
    "metric": "Métrique",
    "risk": "Risque",
}
RISK_STATUS_LABELS = {
    "open": "Ouvert",
    "closed": "Fermé",
    "mitigated": "Maîtrisé",
}
MONTH_LABELS = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
ENTITY_ORDER = {
    "ticket": 0,
    "pull_request": 1,
    "commit": 2,
    "build": 3,
    "test_result": 4,
    "metric": 5,
    "risk": 6,
}


def severity_label(value: str) -> str:
    return SEVERITY_LABELS.get(value, value.title())


def decision_label(value: str) -> str:
    return DECISION_LABELS.get(value, value.replace("_", " ").title())


def readiness_label(value: str) -> str:
    return READINESS_LABELS.get(value, value)


def source_label(value: str) -> str:
    return SOURCE_LABELS.get(value, value.replace("_", " ").title())


def risk_status_label(value: str) -> str:
    return RISK_STATUS_LABELS.get(value, value.replace("_", " ").title())


def human_datetime(value: str | None) -> str:
    if not value:
        return "Non renseigné"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return (
        f"{parsed.day} {MONTH_LABELS[parsed.month]} {parsed.year} "
        f"à {parsed.hour:02d}:{parsed.minute:02d}"
    )


def delta_label(value: float | None) -> str:
    if value is None:
        return "Première analyse"
    if value == 0:
        return "Stable"
    direction = "hausse" if value > 0 else "baisse"
    return f"{value:+.1f} ({direction})"


def global_message(severity: str, finding_count: int) -> str:
    if severity == "critical":
        return "Plusieurs contrôles QA bloquent actuellement la release."
    if severity == "high":
        return "Des risques élevés nécessitent un plan d'action avant la release."
    if severity == "medium":
        return "La release reste possible sous conditions et validation humaine."
    if finding_count:
        return "Quelques constats faibles restent à surveiller."
    return "Aucun contrôle QA bloquant n'est détecté sur le périmètre sélectionné."


def ordered_evidence_nodes(nodes: list[dict]) -> list[dict]:
    return sorted(
        nodes,
        key=lambda node: (
            ENTITY_ORDER.get(str(node.get("type")), 99),
            str(node.get("source_id")),
        ),
    )


def readable_evidence_edges(
    nodes: list[dict],
    edges: list[dict],
) -> list[str]:
    labels = {
        str(node.get("id")): str(node.get("label", node.get("source_id", "inconnu")))
        for node in nodes
    }
    return [
        f"{labels.get(str(edge.get('source')), str(edge.get('source')))} "
        f"— {edge.get('label', edge.get('relation', 'est relié à'))} → "
        f"{labels.get(str(edge.get('target')), str(edge.get('target')))}"
        for edge in edges
    ]


def decision_payload(
    *,
    status: str,
    actor: str,
    comment: str,
    modified_recommendation: str,
) -> dict[str, str | None]:
    return {
        "status": status,
        "decided_by": actor,
        "comment": comment or None,
        "modified_recommendation": (modified_recommendation if status == "modified" else None),
    }
