from __future__ import annotations

from app.decision_domain import (
    DecisionResult,
    DecisionSignals,
    DecisionThresholds,
    QADecision,
)


def _percent(value: float) -> str:
    return f"{value:.0%}"


def _explicit_blockers(signals: DecisionSignals) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    rules: list[str] = []
    if signals.blocking_risk_ids:
        reasons.append(f"{len(signals.blocking_risk_ids)} risque(s) bloquant(s) actif(s)")
        rules.append("NO_GO_BLOCKING_RISK")
    if signals.critical_risk_count:
        reasons.append(f"{signals.critical_risk_count} risque(s) critique(s) actif(s)")
        rules.append("NO_GO_CRITICAL_RISK")
    if signals.blocking_policy_ids:
        reasons.append(
            "politique(s) QA bloquante(s) violée(s) : " + ", ".join(signals.blocking_policy_ids)
        )
        rules.append("NO_GO_BLOCKING_POLICY")
    if signals.critical_ci_failure:
        reasons.append("le pipeline CI principal présente un échec critique")
        rules.append("NO_GO_CRITICAL_CI_FAILURE")
    if signals.open_critical_bug_count:
        reasons.append(f"{signals.open_critical_bug_count} bug(s) critique(s) reste(nt) ouvert(s)")
        rules.append("NO_GO_OPEN_CRITICAL_BUG")
    return reasons, rules


def _information_gaps(
    signals: DecisionSignals,
    thresholds: DecisionThresholds,
) -> tuple[list[str], list[str], list[str]]:
    reasons: list[str] = []
    rules: list[str] = []
    conditions: list[str] = []
    if signals.confidence_score < thresholds.minimum_confidence:
        reasons.append(
            f"confiance {_percent(signals.confidence_score)} sous le seuil "
            f"{_percent(thresholds.minimum_confidence)}"
        )
        rules.append("INSUFFICIENT_LOW_CONFIDENCE")
    if signals.evidence_coverage < thresholds.minimum_evidence_coverage:
        reasons.append(
            f"couverture des preuves {_percent(signals.evidence_coverage)} sous le seuil "
            f"{_percent(thresholds.minimum_evidence_coverage)}"
        )
        rules.append("INSUFFICIENT_EVIDENCE_COVERAGE")
    if signals.data_freshness < thresholds.minimum_data_freshness:
        reasons.append(
            f"fraîcheur des données {_percent(signals.data_freshness)} sous le seuil "
            f"{_percent(thresholds.minimum_data_freshness)}"
        )
        rules.append("INSUFFICIENT_DATA_FRESHNESS")
    if signals.test_coverage_percent is None:
        reasons.append("métrique de couverture de tests absente")
        rules.append("INSUFFICIENT_TEST_COVERAGE_MISSING")
    if signals.missing_information:
        reasons.append("informations manquantes : " + ", ".join(signals.missing_information))
        rules.append("INSUFFICIENT_MISSING_INFORMATION")
    if reasons:
        conditions.append("Compléter ou rafraîchir les données manquantes puis relancer l’analyse.")
    return reasons, rules, conditions


def evaluate_decision(
    signals: DecisionSignals,
    thresholds: DecisionThresholds | None = None,
) -> DecisionResult:
    """Return a deterministic advisory decision with an auditable rule trace."""

    selected = thresholds or DecisionThresholds()
    blockers, blocker_rules = _explicit_blockers(signals)
    if blockers:
        return DecisionResult(
            suggested_decision=QADecision.NO_GO,
            justification="NO-GO car " + ", ".join(blockers) + ".",
            triggered_rules=tuple(blocker_rules),
            blockers=tuple(blockers),
            conditions=(
                "Traiter les éléments bloquants et obtenir une nouvelle validation humaine.",
            ),
        )

    gaps, gap_rules, gap_conditions = _information_gaps(signals, selected)
    if gaps:
        return DecisionResult(
            suggested_decision=QADecision.INSUFFICIENT_INFORMATION,
            justification="Informations insuffisantes car " + ", ".join(gaps) + ".",
            triggered_rules=tuple(gap_rules),
            conditions=tuple(gap_conditions),
            missing_information=signals.missing_information,
        )

    if signals.risk_score > selected.conditional_max_risk_score:
        reason = (
            f"score de risque {signals.risk_score:.1f}/100 supérieur au seuil NO-GO "
            f"de {selected.conditional_max_risk_score:.1f}/100"
        )
        return DecisionResult(
            suggested_decision=QADecision.NO_GO,
            justification="NO-GO car " + reason + ".",
            triggered_rules=("NO_GO_HIGH_RISK_SCORE",),
            blockers=(reason,),
            conditions=("Réduire le score sous le seuil et soumettre un nouveau Decision Brief.",),
        )

    conditions: list[str] = []
    rules: list[str] = []
    if signals.risk_score > selected.go_max_risk_score:
        conditions.append(
            f"Réduire ou accepter explicitement le risque mesuré à {signals.risk_score:.1f}/100."
        )
        rules.append("CONDITIONAL_ELEVATED_RISK_SCORE")
    if signals.violated_policy_ids:
        conditions.append(
            "Traiter les politiques violées : " + ", ".join(signals.violated_policy_ids) + "."
        )
        rules.append("CONDITIONAL_POLICY_VIOLATIONS")
    if (
        signals.test_coverage_percent is not None
        and signals.test_coverage_percent < selected.minimum_test_coverage
    ):
        conditions.append(
            f"Porter la couverture de tests de {signals.test_coverage_percent:.1f}% à "
            f"au moins {selected.minimum_test_coverage:.1f}%."
        )
        rules.append("CONDITIONAL_LOW_TEST_COVERAGE")
    if signals.blocked_ticket_count:
        conditions.append(
            f"Résoudre ou faire accepter {signals.blocked_ticket_count} ticket(s) bloqué(s)."
        )
        rules.append("CONDITIONAL_BLOCKED_TICKETS")
    if signals.overdue_ticket_count:
        conditions.append(
            f"Replanifier ou clôturer {signals.overdue_ticket_count} ticket(s) en retard."
        )
        rules.append("CONDITIONAL_OVERDUE_TICKETS")
    if signals.stale_information:
        conditions.append(
            "Rafraîchir les informations anciennes : " + ", ".join(signals.stale_information) + "."
        )
        rules.append("CONDITIONAL_STALE_INFORMATION")
    if conditions:
        return DecisionResult(
            suggested_decision=QADecision.GO_WITH_CONDITIONS,
            justification=(
                "GO WITH CONDITIONS car des risques contrôlables nécessitent "
                f"{len(conditions)} condition(s) explicite(s)."
            ),
            triggered_rules=tuple(rules),
            conditions=tuple(conditions),
        )

    return DecisionResult(
        suggested_decision=QADecision.GO,
        justification=(
            f"GO car le score est de {signals.risk_score:.1f}/100, la confiance de "
            f"{_percent(signals.confidence_score)} et les preuves sont suffisantes."
        ),
        triggered_rules=("GO_LOW_CONTROLLED_RISK",),
    )
