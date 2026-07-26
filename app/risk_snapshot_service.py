from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.fact_aggregator import collect_facts
from app.models import Risk, RiskAnalysis, RiskContribution
from app.policy_models import PolicySet
from app.qa_domain import Finding, RuleContext
from app.qa_scoring import finding_priority, finding_score
from app.risk_repository import (
    analysis_contributions,
    analysis_risks,
    latest_analysis,
)
from app.time_utils import ensure_utc_datetime


class SnapshotConsistencyError(RuntimeError):
    pass


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def input_fingerprint(
    context: RuleContext,
    policy_set: PolicySet,
    *,
    confidence_score: float = 1.0,
    evidence_coverage: float = 1.0,
    confidence_details: dict | None = None,
    missing_information: list | None = None,
    stale_information: list | None = None,
) -> str:
    facts = collect_facts(context)
    payload = {
        "project_id": context.project_id,
        "sprint_id": context.sprint_id,
        "reference_date": context.reference_date,
        "policy_hash": policy_set.content_hash,
        "data_quality": {
            "confidence_score": confidence_score,
            "evidence_coverage": evidence_coverage,
            "confidence_details": confidence_details or {},
            "missing_information": missing_information or [],
            "stale_information": stale_information or [],
        },
        "facts": sorted(
            (
                {
                    "metric": fact.metric,
                    "raw_value": fact.raw_value,
                    "source_type": fact.source_type,
                    "source_id": fact.source_id,
                    "sprint_id": fact.sprint_id,
                    "observed_at": fact.observed_at,
                    "evidence": fact.evidence,
                    "attributes": fact.attributes,
                }
                for fact in facts
            ),
            key=lambda item: (
                item["metric"],
                item["source_type"],
                item["source_id"],
            ),
        ),
    }
    return _fingerprint(payload)


def result_fingerprint(
    score: float,
    severity: str,
    breakdown: list[dict[str, object]],
    findings: list[Finding],
    confidence_score: float,
    evidence_coverage: float,
    confidence_details: dict,
    missing_information: list,
    stale_information: list,
) -> str:
    return _fingerprint(
        {
            "score": score,
            "severity": severity,
            "confidence_score": confidence_score,
            "evidence_coverage": evidence_coverage,
            "confidence_details": confidence_details,
            "breakdown": breakdown,
            "findings": [
                {
                    "rule_id": finding.rule_id,
                    "severity": finding.severity,
                    "source_type": finding.source_type,
                    "source_id": finding.source_id,
                    "raw_value": finding.raw_value,
                    "evidence": finding.evidence,
                    "recommendation": finding.recommendation,
                }
                for finding in findings
            ],
            "missing_information": missing_information,
            "stale_information": stale_information,
        }
    )


def snapshot_id(
    project_id: str,
    sprint_id: str | None,
    reference_date: date,
    policy_set: PolicySet,
    fingerprint: str,
) -> str:
    key = (
        f"{project_id}|{sprint_id or '*'}|{reference_date.isoformat()}|"
        f"{policy_set.ruleset_version}|{policy_set.content_hash}|{fingerprint}"
    )
    return f"QAA-{hashlib.sha256(key.encode()).hexdigest()[:20].upper()}"


def _risk_id(analysis_id: str, rule_id: str, source_id: str) -> str:
    key = f"{analysis_id}|{rule_id}|{source_id}"
    return f"RSK-{hashlib.sha256(key.encode()).hexdigest()[:20].upper()}"


def _contribution_id(analysis_id: str, policy_id: str) -> str:
    key = f"{analysis_id}|{policy_id}"
    return f"RCO-{hashlib.sha256(key.encode()).hexdigest()[:20].upper()}"


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if not isinstance(value, (datetime, str)):
        raise TypeError(f"unsupported datetime value: {type(value).__name__}")
    return ensure_utc_datetime(value)


def persist_snapshot(
    session: Session,
    *,
    context: RuleContext,
    policy_set: PolicySet,
    score: float,
    severity: str,
    breakdown: list[dict[str, object]],
    findings: list[Finding],
    agent_name: str,
    confidence_score: float = 1.0,
    evidence_coverage: float = 1.0,
    confidence_details: dict | None = None,
    missing_information: list | None = None,
    stale_information: list | None = None,
) -> tuple[RiskAnalysis, list[Risk], list[RiskContribution], bool]:
    missing = missing_information or []
    stale = stale_information or []
    details = confidence_details or {}
    input_hash = input_fingerprint(
        context,
        policy_set,
        confidence_score=confidence_score,
        evidence_coverage=evidence_coverage,
        confidence_details=details,
        missing_information=missing,
        stale_information=stale,
    )
    result_hash = result_fingerprint(
        score,
        severity,
        breakdown,
        findings,
        confidence_score,
        evidence_coverage,
        details,
        missing,
        stale,
    )
    scoped_sprint_id = context.sprint_id
    analysis_id = snapshot_id(
        context.project_id,
        scoped_sprint_id,
        context.reference_date,
        policy_set,
        input_hash,
    )
    existing = session.get(RiskAnalysis, analysis_id)
    if existing is not None:
        if existing.result_fingerprint != result_hash:
            raise SnapshotConsistencyError(
                "same snapshot input produced a different result fingerprint"
            )
        return (
            existing,
            analysis_risks(session, analysis_id),
            analysis_contributions(session, analysis_id),
            False,
        )

    previous = latest_analysis(session, context.project_id, scoped_sprint_id)
    analysis = RiskAnalysis(
        id=analysis_id,
        project_id=context.project_id,
        sprint_id=scoped_sprint_id,
        ruleset_version=policy_set.ruleset_version,
        reference_date=context.reference_date,
        score=score,
        severity=severity,
        breakdown=breakdown,
        finding_count=len(findings),
        agent_name=agent_name,
        analyzed_at=context.analyzed_at,
        policy_hash=policy_set.content_hash,
        input_fingerprint=input_hash,
        result_fingerprint=result_hash,
        previous_snapshot_id=previous.id if previous else None,
        confidence_score=confidence_score,
        evidence_coverage=evidence_coverage,
        missing_information=missing,
        stale_information=stale,
        confidence_details=details,
    )
    session.add(analysis)
    session.flush()

    contribution_rows = []
    for item in breakdown:
        contribution = RiskContribution(
            id=_contribution_id(analysis_id, str(item["policy_id"])),
            analysis_id=analysis_id,
            policy_id=str(item["policy_id"]),
            policy_version=int(item["policy_version"]),
            factor=str(item["factor"]),
            raw_value=item["raw_value"],
            normalized_value=float(item["normalized_value"]),
            weight=float(item["weight"]),
            contribution=float(item["contribution"]),
            finding_count=int(item["finding_count"]),
            explanation=str(item["explanation"]),
            source_type=(str(item["source_type"]) if item["source_type"] is not None else None),
            source_id=str(item["source_id"]) if item["source_id"] is not None else None,
            observed_at=_parse_datetime(item["observed_at"]),
        )
        session.add(contribution)
        contribution_rows.append(contribution)

    risks = []
    for finding in findings:
        risk = Risk(
            id=_risk_id(analysis_id, finding.rule_id, finding.source_id),
            analysis_id=analysis_id,
            project_id=context.project_id,
            sprint_id=finding.sprint_id,
            rule_id=finding.rule_id,
            title=finding.title,
            description=finding.description,
            severity=finding.severity,
            priority=finding_priority(finding),
            score=finding_score(finding),
            confidence=min(finding.confidence, confidence_score),
            source_type=finding.source_type,
            source_id=finding.source_id,
            evidence=finding.evidence,
            recommendation=finding.recommendation,
            requires_human_validation=True,
            status="open",
            detected_at=context.analyzed_at,
        )
        session.add(risk)
        risks.append(risk)
    session.flush()
    from app.dataset_validation import validate_snapshot_evidence
    from app.evidence_service import persist_risk_evidence

    evidence_rows = persist_risk_evidence(session, analysis, risks)
    validate_snapshot_evidence(
        analysis_id=analysis.id,
        reference_date=analysis.reference_date,
        evidence_rows=evidence_rows,
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        concurrent = session.get(RiskAnalysis, analysis_id)
        if concurrent is None:
            raise
        return (
            concurrent,
            analysis_risks(session, analysis_id),
            analysis_contributions(session, analysis_id),
            False,
        )
    return analysis, risks, contribution_rows, True
