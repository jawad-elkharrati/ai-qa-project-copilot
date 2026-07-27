from __future__ import annotations

from app.models import Risk, RiskAnalysis

MINIMUM_CONFIDENCE = 0.7
ESSENTIAL_MISSING_CODES = {
    "tickets_missing",
    "builds_missing",
    "test_results_missing",
    "coverage_metric_missing",
}


def release_readiness(
    analysis: RiskAnalysis,
    risks: list[Risk],
    pending_recommendation_count: int,
) -> dict[str, object]:
    """Return a deterministic, advisory release-readiness proposal."""

    missing_codes = {
        str(item.get("code")) for item in analysis.missing_information if isinstance(item, dict)
    }
    essential_missing = sorted(missing_codes & ESSENTIAL_MISSING_CODES)
    critical = [risk for risk in risks if risk.severity == "critical"]
    top_risks = sorted(
        risks,
        key=lambda risk: (risk.priority, -risk.score, risk.rule_id, risk.source_id),
    )[:3]

    if analysis.confidence_score < MINIMUM_CONFIDENCE or essential_missing:
        decision = "INSUFFICIENT INFORMATION"
        reasons = [
            "La qualité des données ne permet pas une décision de release suffisamment étayée."
        ]
        if analysis.confidence_score < MINIMUM_CONFIDENCE:
            reasons.append(
                f"Confiance {analysis.confidence_score:.0%}, sous le seuil "
                f"documenté de {MINIMUM_CONFIDENCE:.0%}."
            )
        if essential_missing:
            reasons.append("Sources essentielles absentes : " + ", ".join(essential_missing) + ".")
        conditions = ["Compléter les sources essentielles puis relancer l'analyse."]
    elif critical:
        decision = "NO-GO"
        reasons = [f"{len(critical)} risque(s) critique(s) bloque(nt) actuellement la release."]
        conditions = [
            "Traiter les risques critiques et faire valider les recommandations associées."
        ]
    elif analysis.severity in {"medium", "high"} or pending_recommendation_count:
        decision = "GO WITH CONDITIONS"
        reasons = ["Le niveau de risque impose des conditions explicites avant la release."]
        conditions = [
            f"Statuer sur {pending_recommendation_count} recommandation(s) encore en attente."
        ]
    else:
        decision = "GO"
        reasons = ["Aucun contrôle QA bloquant n'est détecté avec les données disponibles."]
        conditions = ["Maintenir la surveillance QA jusqu'à la release."]

    return {
        "decision": decision,
        "advisory_only": True,
        "human_validation_required": True,
        "reasons": reasons,
        "conditions": conditions,
        "priority_actions": [risk.recommendation for risk in top_risks],
        "main_evidence": [
            {
                "risk_id": risk.id,
                "policy_id": risk.rule_id,
                "source_type": risk.source_type,
                "source_id": risk.source_id,
                "severity": risk.severity,
            }
            for risk in top_risks
        ],
    }
