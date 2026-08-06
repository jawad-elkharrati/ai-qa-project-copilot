from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Build,
    Commit,
    Metric,
    PullRequest,
    Risk,
    RiskAnalysis,
    RiskEvidence,
    TestResult,
    Ticket,
)
from app.risk_repository import analysis_contributions
from app.time_utils import ensure_utc_datetime


def _node_id(source_type: str, source_id: str) -> str:
    return f"{source_type}:{source_id}"


def _risk_node(risk: Risk) -> dict[str, object]:
    return {
        "id": _node_id("risk", risk.id),
        "type": "risk",
        "source_id": risk.id,
        "label": f"Risque {risk.rule_id} — {risk.title}",
        "observed_at": risk.detected_at,
        "metadata": {
            "severity": risk.severity,
            "status": risk.status,
        },
    }


def _entity_node(entity) -> dict[str, object]:
    if isinstance(entity, Ticket):
        return {
            "id": _node_id("ticket", entity.id),
            "type": "ticket",
            "source_id": entity.id,
            "label": f"Ticket {entity.id} — {entity.title}",
            "observed_at": entity.updated_at,
            "metadata": {
                "status": entity.status,
                "priority": entity.priority,
                "type": entity.type,
            },
        }
    if isinstance(entity, PullRequest):
        return {
            "id": _node_id("pull_request", entity.id),
            "type": "pull_request",
            "source_id": entity.id,
            "label": f"PR #{entity.number} — {entity.title}",
            "observed_at": entity.merged_at or entity.created_at,
            "metadata": {
                "status": entity.status,
                "author": entity.author,
            },
        }
    if isinstance(entity, Commit):
        return {
            "id": _node_id("commit", entity.id),
            "type": "commit",
            "source_id": entity.id,
            "label": f"Commit {entity.sha[:8]} — {entity.message}",
            "observed_at": entity.committed_at,
            "metadata": {"sha": entity.sha, "author": entity.author},
        }
    if isinstance(entity, Build):
        return {
            "id": _node_id("build", entity.id),
            "type": "build",
            "source_id": entity.id,
            "label": f"Build {entity.id} — {entity.pipeline_name} ({entity.status})",
            "observed_at": entity.finished_at or entity.started_at,
            "metadata": {
                "status": entity.status,
                "branch": entity.branch,
                "commit_sha": entity.commit_sha,
            },
        }
    if isinstance(entity, TestResult):
        return {
            "id": _node_id("test_result", entity.id),
            "type": "test_result",
            "source_id": entity.id,
            "label": f"Tests {entity.id} — {entity.suite_name} ({entity.status})",
            "observed_at": entity.executed_at,
            "metadata": {
                "status": entity.status,
                "total": entity.total,
                "failed": entity.failed,
            },
        }
    if isinstance(entity, Metric):
        return {
            "id": _node_id("metric", entity.id),
            "type": "metric",
            "source_id": entity.id,
            "label": f"Métrique {entity.name} — {entity.value} {entity.unit}",
            "observed_at": entity.measured_at,
            "metadata": {
                "name": entity.name,
                "value": entity.value,
                "unit": entity.unit,
                "source": entity.source,
            },
        }
    raise TypeError(f"unsupported evidence entity: {type(entity).__name__}")


def build_evidence_chain(session: Session, risk: Risk) -> dict[str, object]:
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, str]] = []
    edge_keys: set[tuple[str, str, str]] = set()
    missing_links: list[dict[str, str]] = []

    def add_node(node: dict[str, object]) -> str:
        nodes[str(node["id"])] = node
        return str(node["id"])

    def add_edge(source: str, target: str, relation: str, label: str) -> None:
        key = (source, target, relation)
        if key not in edge_keys:
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "label": label,
                }
            )
            edge_keys.add(key)

    risk_node_id = add_node(_risk_node(risk))

    def link_build(build: Build, direct: bool = False) -> str:
        build_id = add_node(_entity_node(build))
        if direct:
            add_edge(build_id, risk_node_id, "supports", "soutient le risque")
        pull_request = (
            session.get(PullRequest, build.pull_request_id) if build.pull_request_id else None
        )
        if pull_request:
            pr_id = add_node(_entity_node(pull_request))
            add_edge(pr_id, build_id, "triggered", "a déclenché")
            ticket = session.get(Ticket, pull_request.ticket_id) if pull_request.ticket_id else None
            if ticket:
                ticket_id = add_node(_entity_node(ticket))
                add_edge(ticket_id, pr_id, "implemented_by", "est implémenté par")
            elif pull_request.ticket_id:
                missing_links.append(
                    {
                        "relation": "pull_request_to_ticket",
                        "source_id": pull_request.id,
                        "target_id": pull_request.ticket_id,
                    }
                )
            else:
                missing_links.append(
                    {
                        "relation": "pull_request_to_ticket",
                        "source_id": pull_request.id,
                        "target_id": "missing",
                    }
                )
        elif build.pull_request_id:
            missing_links.append(
                {
                    "relation": "build_to_pull_request",
                    "source_id": build.id,
                    "target_id": build.pull_request_id,
                }
            )
        else:
            missing_links.append(
                {
                    "relation": "build_to_pull_request",
                    "source_id": build.id,
                    "target_id": "missing",
                }
            )

        commit = session.scalar(select(Commit).where(Commit.sha == build.commit_sha))
        if commit:
            commit_id = add_node(_entity_node(commit))
            if pull_request:
                add_edge(
                    pr_id,
                    commit_id,
                    "contains",
                    "contient le commit",
                )
            add_edge(commit_id, build_id, "triggered", "a déclenché")
        else:
            missing_links.append(
                {
                    "relation": "build_to_commit",
                    "source_id": build.id,
                    "target_id": build.commit_sha,
                }
            )
        test_results = list(
            session.scalars(
                select(TestResult).where(TestResult.build_id == build.id).order_by(TestResult.id)
            )
        )
        if not test_results:
            missing_links.append(
                {
                    "relation": "build_to_test_result",
                    "source_id": build.id,
                    "target_id": "missing",
                }
            )
        for result in test_results:
            result_id = add_node(_entity_node(result))
            add_edge(build_id, result_id, "contains", "contient")
        return build_id

    if risk.source_type == "ticket":
        ticket = session.get(Ticket, risk.source_id)
        if ticket:
            ticket_id = add_node(_entity_node(ticket))
            add_edge(ticket_id, risk_node_id, "supports", "soutient le risque")
            commits = list(
                session.scalars(
                    select(Commit)
                    .where(Commit.ticket_id == ticket.id)
                    .order_by(Commit.committed_at, Commit.id)
                )
            )
            for commit in commits:
                commit_id = add_node(_entity_node(commit))
                add_edge(ticket_id, commit_id, "implemented_by", "est implémenté par")
            pull_requests = list(
                session.scalars(
                    select(PullRequest)
                    .where(PullRequest.ticket_id == ticket.id)
                    .order_by(PullRequest.number)
                )
            )
            for pull_request in pull_requests:
                pr_id = add_node(_entity_node(pull_request))
                add_edge(ticket_id, pr_id, "implemented_by", "est implémenté par")
                builds = list(
                    session.scalars(
                        select(Build)
                        .where(Build.pull_request_id == pull_request.id)
                        .order_by(Build.started_at, Build.id)
                    )
                )
                for build in builds:
                    build_id = link_build(build)
                    add_edge(pr_id, build_id, "triggered", "a déclenché")
        else:
            missing_links.append(
                {
                    "relation": "risk_to_ticket",
                    "source_id": risk.id,
                    "target_id": risk.source_id,
                }
            )
    elif risk.source_type == "build":
        build = session.get(Build, risk.source_id)
        if build:
            link_build(build, direct=True)
        else:
            missing_links.append(
                {
                    "relation": "risk_to_build",
                    "source_id": risk.id,
                    "target_id": risk.source_id,
                }
            )
    elif risk.source_type == "metric":
        metric = session.get(Metric, risk.source_id)
        if metric:
            metric_id = add_node(_entity_node(metric))
            add_edge(metric_id, risk_node_id, "supports", "soutient le risque")
        else:
            missing_links.append(
                {
                    "relation": "risk_to_metric",
                    "source_id": risk.id,
                    "target_id": risk.source_id,
                }
            )
    else:
        missing_links.append(
            {
                "relation": "unsupported_source_type",
                "source_id": risk.id,
                "target_id": risk.source_type,
            }
        )
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "missing_links": missing_links,
    }


def _evidence_id(
    risk_id: str,
    source_type: str,
    source_id: str,
    relation: str,
) -> str:
    key = f"{risk_id}|{source_type}|{source_id}|{relation}"
    return f"EVD-{hashlib.sha256(key.encode()).hexdigest()[:20].upper()}"


def _as_datetime(value) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime | str):
        raise TypeError(f"unsupported datetime value: {type(value).__name__}")
    return ensure_utc_datetime(value)


def persist_risk_evidence(
    session: Session,
    analysis: RiskAnalysis,
    risks: list[Risk],
) -> list[RiskEvidence]:
    contribution_by_policy = {
        item.policy_id: item.contribution for item in analysis_contributions(session, analysis.id)
    }
    rows = []
    for risk in risks:
        chain = build_evidence_chain(session, risk)
        edge_by_target = {}
        for edge in chain["edges"]:
            edge_by_target.setdefault(edge["target"], edge)
        evidence_nodes = [node for node in chain["nodes"] if node["type"] != "risk"]
        for order, node in enumerate(evidence_nodes):
            edge = edge_by_target.get(
                node["id"],
                {
                    "relation": "related_to",
                    "label": "est lié à",
                },
            )
            row = RiskEvidence(
                id=_evidence_id(
                    risk.id,
                    str(node["type"]),
                    str(node["source_id"]),
                    str(edge["relation"]),
                ),
                risk_id=risk.id,
                analysis_id=analysis.id,
                source_type=str(node["type"]),
                source_id=str(node["source_id"]),
                relation=str(edge["relation"]),
                evidence_order=order,
                contribution=(contribution_by_policy.get(risk.rule_id) if order == 0 else None),
                explanation=str(edge["label"]),
                payload={
                    "label": node["label"],
                    "metadata": node["metadata"],
                },
                observed_at=_as_datetime(node["observed_at"]),
            )
            session.add(row)
            rows.append(row)
    return rows
