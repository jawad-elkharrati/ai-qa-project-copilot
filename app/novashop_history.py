from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from sqlalchemy.orm import Session

from app.models import Risk, RiskAnalysis, RiskContribution
from app.policy_loader import get_policy_set
from app.qa_scoring import SEVERITY_PRIORITY, SEVERITY_SCORES
from app.recommendation_service import sync_recommendations_for_snapshot

NOVASHOP_PROJECT_ID = "PRJ-COPILOTE"
HISTORY_START = date(2026, 7, 14)
HISTORY_END = date(2026, 7, 20)


@dataclass(frozen=True)
class HistoricalSignal:
    policy_id: str
    contribution: float
    severity: str
    source_type: str
    source_id: str
    raw_value: bool | float
    evidence: dict[str, object]


HISTORY: tuple[tuple[date, tuple[HistoricalSignal, ...]], ...] = (
    (
        date(2026, 7, 14),
        (
            HistoricalSignal("QA-TICKET-OVERDUE", 8, "high", "ticket", "TKT-042", 3.0, {}),
            HistoricalSignal("QA-COVERAGE-LOW", 10, "high", "metric", "MET-007", 64.0, {}),
        ),
    ),
    (
        date(2026, 7, 15),
        (
            HistoricalSignal("QA-TICKET-OVERDUE", 12, "high", "ticket", "TKT-042", 4.0, {}),
            HistoricalSignal("QA-BLOCKED-LONG", 14, "high", "ticket", "TKT-039", 96.0, {}),
            HistoricalSignal("QA-COVERAGE-LOW", 10, "high", "metric", "MET-007", 64.0, {}),
        ),
    ),
    (
        date(2026, 7, 16),
        (
            HistoricalSignal("QA-TICKET-OVERDUE", 12, "high", "ticket", "TKT-042", 5.0, {}),
            HistoricalSignal("QA-BLOCKED-LONG", 18, "critical", "ticket", "TKT-039", 120.0, {}),
            HistoricalSignal(
                "QA-PIPELINE-FAILED",
                21,
                "high",
                "build",
                "BLD-011",
                1.0,
                {"pipeline_name": "ci-main", "branch": "main"},
            ),
            HistoricalSignal("QA-COVERAGE-LOW", 10, "high", "metric", "MET-007", 64.0, {}),
        ),
    ),
    (
        date(2026, 7, 17),
        (
            HistoricalSignal("QA-TICKET-OVERDUE", 12, "high", "ticket", "TKT-042", 6.0, {}),
            HistoricalSignal("QA-BLOCKED-LONG", 20, "critical", "ticket", "TKT-039", 144.0, {}),
            HistoricalSignal(
                "QA-PIPELINE-FAILED",
                25,
                "critical",
                "build",
                "BLD-012",
                2.0,
                {"pipeline_name": "ci-main", "branch": "main"},
            ),
            HistoricalSignal("QA-CRITICAL-BUG-OPEN", 25, "critical", "ticket", "TKT-038", True, {}),
        ),
    ),
    (
        date(2026, 7, 18),
        (
            HistoricalSignal("QA-TICKET-OVERDUE", 12, "high", "ticket", "TKT-042", 7.0, {}),
            HistoricalSignal(
                "QA-PIPELINE-FAILED",
                20,
                "high",
                "build",
                "BLD-012",
                1.0,
                {"pipeline_name": "ci-main", "branch": "main"},
            ),
            HistoricalSignal("QA-CRITICAL-BUG-OPEN", 25, "critical", "ticket", "TKT-038", True, {}),
        ),
    ),
    (
        date(2026, 7, 19),
        (
            HistoricalSignal("QA-TICKET-OVERDUE", 12, "high", "ticket", "TKT-042", 8.0, {}),
            HistoricalSignal(
                "QA-PIPELINE-FAILED",
                20,
                "high",
                "build",
                "BLD-012",
                1.0,
                {"pipeline_name": "ci-main", "branch": "main"},
            ),
        ),
    ),
    (
        date(2026, 7, 20),
        (HistoricalSignal("QA-TICKET-OVERDUE", 12, "high", "ticket", "TKT-042", 9.0, {}),),
    ),
)


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_id(reference_date: date) -> str:
    return f"QAH-NS-{reference_date.strftime('%Y%m%d')}"


def _risk_id(snapshot_id: str, signal: HistoricalSignal) -> str:
    value = _digest([snapshot_id, signal.policy_id, signal.source_id])[:20].upper()
    return f"RSK-{value}"


def _source_evidence(signal: HistoricalSignal, reference_date: date) -> dict[str, object]:
    evidence = {
        "policy_id": signal.policy_id,
        "observed_value": signal.raw_value,
        "reference_date": reference_date.isoformat(),
        **signal.evidence,
    }
    if signal.policy_id == "QA-COVERAGE-LOW":
        evidence.update({"metric_name": "test_coverage", "unit": "percent"})
    return evidence


def seed_novashop_history(
    session: Session,
    project_id: str = NOVASHOP_PROJECT_ID,
) -> tuple[str, ...]:
    """Create the deterministic seven-day demonstration history idempotently."""

    policy_set = get_policy_set()
    previous_id: str | None = None
    snapshot_ids: list[str] = []
    for reference_date, signals in HISTORY:
        snapshot_id = _snapshot_id(reference_date)
        snapshot_ids.append(snapshot_id)
        existing = session.get(RiskAnalysis, snapshot_id)
        if existing is not None:
            previous_id = existing.id
            continue
        analyzed_at = datetime.combine(reference_date, time(hour=9), tzinfo=UTC)
        score = round(sum(item.contribution for item in signals), 1)
        severity = (
            "critical"
            if score >= 70
            else "high"
            if score >= 45
            else "medium"
            if score >= 20
            else "low"
        )
        breakdown = []
        by_policy = {item.policy_id: item for item in signals}
        for policy in policy_set.policies:
            signal = by_policy.get(policy.id)
            contribution = signal.contribution if signal else 0.0
            breakdown.append(
                {
                    "policy_id": policy.id,
                    "policy_version": policy.version,
                    "factor": policy.condition.metric,
                    "raw_value": signal.raw_value if signal else None,
                    "normalized_value": round(contribution / policy.weight, 3),
                    "weight": policy.weight,
                    "contribution": contribution,
                    "finding_count": 1 if signal else 0,
                    "explanation": (
                        f"Historique NovaShop {reference_date}: contribution "
                        f"{contribution:.1f}/{policy.weight:.1f}."
                    ),
                    "source_type": signal.source_type if signal else None,
                    "source_id": signal.source_id if signal else None,
                    "observed_at": analyzed_at.isoformat() if signal else None,
                }
            )
        fingerprint_payload = {
            "project_id": project_id,
            "reference_date": reference_date,
            "signals": [signal.__dict__ for signal in signals],
        }
        analysis = RiskAnalysis(
            id=snapshot_id,
            project_id=project_id,
            sprint_id=None,
            ruleset_version=policy_set.ruleset_version,
            reference_date=reference_date,
            score=score,
            severity=severity,
            breakdown=breakdown,
            finding_count=len(signals),
            agent_name="qa-history-fixture-v1",
            analyzed_at=analyzed_at,
            policy_hash=policy_set.content_hash,
            input_fingerprint=_digest(fingerprint_payload),
            result_fingerprint=_digest({"score": score, "breakdown": breakdown}),
            previous_snapshot_id=previous_id,
            confidence_score=0.9,
            evidence_coverage=0.9,
            missing_information=[],
            stale_information=[],
            confidence_details={
                "method": "deterministic-novashop-history-v1",
                "is_probability": False,
                "components": {
                    "source_coverage": 0.9,
                    "freshness_coverage": 1.0,
                    "relation_coverage": 0.8,
                },
            },
        )
        session.add(analysis)
        session.flush()
        for policy in policy_set.policies:
            item = next(row for row in breakdown if row["policy_id"] == policy.id)
            session.add(
                RiskContribution(
                    id=f"RCO-{_digest([snapshot_id, policy.id])[:20].upper()}",
                    analysis_id=snapshot_id,
                    policy_id=policy.id,
                    policy_version=policy.version,
                    factor=policy.condition.metric,
                    raw_value=item["raw_value"],
                    normalized_value=item["normalized_value"],
                    weight=policy.weight,
                    contribution=item["contribution"],
                    finding_count=item["finding_count"],
                    explanation=item["explanation"],
                    source_type=item["source_type"],
                    source_id=item["source_id"],
                    observed_at=analyzed_at if item["source_id"] else None,
                )
            )
        for signal in signals:
            policy = policy_set.by_id(signal.policy_id)
            evidence = _source_evidence(signal, reference_date)
            session.add(
                Risk(
                    id=_risk_id(snapshot_id, signal),
                    analysis_id=snapshot_id,
                    project_id=project_id,
                    sprint_id=None,
                    rule_id=signal.policy_id,
                    title=policy.name,
                    description=f"{policy.name} observ? le {reference_date.isoformat()}.",
                    severity=signal.severity,
                    priority=SEVERITY_PRIORITY[signal.severity],
                    score=SEVERITY_SCORES[signal.severity],
                    confidence=0.9,
                    source_type=signal.source_type,
                    source_id=signal.source_id,
                    evidence=evidence,
                    recommendation=policy.recommendation,
                    requires_human_validation=True,
                    status="open",
                    detected_at=analyzed_at,
                )
            )
        session.commit()
        sync_recommendations_for_snapshot(session, snapshot_id)
        previous_id = snapshot_id
    return tuple(snapshot_ids)
