"""Generate the deterministic v0.1 dataset used throughout the eight-week PFA."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PROJECT_ID = "PRJ-COPILOTE"
REFERENCE_DATE = date(2026, 7, 13)
GENERATED_AT = datetime(2026, 7, 13, 9, 0, tzinfo=UTC)
OUTPUT = Path("data/demo_dataset_v0.1.json")
ASSIGNEES = ["Amal QA", "Yassine Dev", "Sara Dev", "Nora DevOps", "Omar Lead"]
TYPES = ["story", "task", "bug", "story", "task"]
POINTS = [2, 3, 5, 3, 1, 5, 2, 8]
SPRINT_STARTS = {
    1: date(2026, 6, 8),
    2: date(2026, 6, 22),
    3: date(2026, 7, 6),
}
CHAIN_TICKETS = (3, 6, 10, 14, 18, 22, 27, 32, 36, 38, 42, 47)


def iso_datetime(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def sprint_record(number: int, start: date, end: date, status: str, scenario: str) -> dict:
    goals = {
        "sain": "Livrer la gestion des profils et stabiliser les tests de non-régression.",
        "à risque": "Intégrer le catalogue et réduire les temps de réponse de recherche.",
        "critique": "Déployer le paiement et sécuriser le parcours de commande.",
    }
    return {
        "id": f"SPR-{number:03d}",
        "project_id": PROJECT_ID,
        "name": f"Sprint {number} — {scenario}",
        "goal": goals[scenario],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "status": status,
        "capacity_points": [50, 52, 50][number - 1],
        "created_at": iso_datetime(
            datetime.combine(start - timedelta(days=5), datetime.min.time(), tzinfo=UTC)
        ),
    }


def ticket_title(number: int, ticket_type: str) -> str:
    subjects = [
        "Authentification utilisateur",
        "Gestion du profil",
        "Recherche du catalogue",
        "Mise en cache API",
        "Validation du panier",
        "Paiement sécurisé",
        "Notifications de commande",
        "Journalisation applicative",
        "Tests de non-régression",
        "Accessibilité du formulaire",
    ]
    prefix = {"story": "Implémenter", "task": "Configurer", "bug": "Corriger"}[ticket_type]
    return f"{prefix} {subjects[(number - 1) % len(subjects)]}"


def base_ticket(number: int, sprint_number: int, status: str) -> dict:
    start = SPRINT_STARTS[sprint_number]
    ticket_type = TYPES[(number - 1) % len(TYPES)]
    created = datetime.combine(start - timedelta(days=3), datetime.min.time(), tzinfo=UTC)
    updated = datetime.combine(
        start + timedelta(days=(number % 9) + 1), datetime.min.time(), tzinfo=UTC
    )
    due = start + timedelta(days=7 + number % 6)
    closed_at = updated if status == "done" else None
    priority = ["low", "medium", "medium", "high"][number % 4]
    return {
        "id": f"TKT-{number:03d}",
        "project_id": PROJECT_ID,
        "sprint_id": f"SPR-{sprint_number:03d}",
        "title": ticket_title(number, ticket_type),
        "description": (
            f"Ticket fictif {number} du scénario de référence. "
            "Les critères d'acceptation sont documentés et vérifiables."
        ),
        "type": ticket_type,
        "status": status,
        "priority": priority,
        "assignee": ASSIGNEES[(number - 1) % len(ASSIGNEES)],
        "story_points": POINTS[(number - 1) % len(POINTS)],
        "created_at": iso_datetime(created),
        "updated_at": iso_datetime(updated),
        "due_date": due.isoformat(),
        "blocked_since": None,
        "closed_at": iso_datetime(closed_at) if closed_at else None,
        "labels": [ticket_type, f"sprint-{sprint_number}"],
    }


def build_tickets() -> list[dict]:
    tickets: list[dict] = []
    for number in range(1, 17):
        tickets.append(base_ticket(number, 1, "done"))

    risk_status = {
        17: "done",
        18: "done",
        19: "done",
        20: "done",
        21: "done",
        22: "done",
        23: "in_progress",
        24: "blocked",
        25: "done",
        26: "done",
        27: "in_progress",
        28: "done",
        29: "blocked",
        30: "done",
        31: "done",
        32: "review",
        33: "done",
    }
    for number, status in risk_status.items():
        tickets.append(base_ticket(number, 2, status))

    critical_status = {
        34: "done",
        35: "done",
        36: "in_progress",
        37: "review",
        38: "in_progress",
        39: "blocked",
        40: "done",
        41: "in_progress",
        42: "in_progress",
        43: "todo",
        44: "review",
        45: "todo",
        46: "done",
        47: "in_progress",
        48: "todo",
        49: "review",
        50: "todo",
    }
    for number, status in critical_status.items():
        tickets.append(base_ticket(number, 3, status))

    overrides = {
        "TKT-023": {
            "due_date": "2026-07-15",
            "labels": ["in-progress", "scenario-risk"],
        },
        "TKT-024": {
            "blocked_since": "2026-07-08T08:00:00Z",
            "due_date": "2026-07-16",
            "labels": ["blocked", "dependency", "scenario-risk"],
            "description": "Bloqué par une API fournisseur indisponible depuis plus de 72 heures.",
        },
        "TKT-027": {
            "due_date": "2026-07-10",
            "labels": ["performance", "overdue", "scenario-risk"],
        },
        "TKT-029": {
            "blocked_since": "2026-07-11T16:00:00Z",
            "due_date": "2026-07-12",
            "labels": ["blocked", "recent", "scenario-risk"],
        },
        "TKT-032": {
            "due_date": "2026-07-15",
            "labels": ["review", "scenario-risk"],
        },
        "TKT-038": {
            "type": "bug",
            "priority": "critical",
            "title": "Corriger le double débit lors d'une reprise de paiement",
            "description": "Bug critique fictif : un retry peut provoquer un double débit.",
            "labels": ["bug", "payment", "critical", "scenario-critical"],
            "due_date": "2026-07-14",
        },
        "TKT-039": {
            "blocked_since": "2026-07-07T09:00:00Z",
            "priority": "high",
            "description": "Déploiement bloqué par un certificat de sandbox expiré.",
            "labels": ["blocked", "certificate", "scenario-critical"],
            "due_date": "2026-07-16",
        },
        "TKT-042": {
            "due_date": "2026-07-11",
            "priority": "high",
            "labels": ["overdue", "payment", "scenario-critical"],
        },
        "TKT-045": {
            "due_date": "2026-07-12",
            "priority": "high",
            "labels": ["overdue", "security", "scenario-critical"],
        },
    }
    for ticket in tickets:
        ticket.update(overrides.get(ticket["id"], {}))
    return tickets


def chain_timing(number: int) -> tuple[int, datetime, datetime, datetime]:
    sprint_number = (number - 1) // 4 + 1
    offset = (number - 1) % 4
    build_at = datetime.combine(
        SPRINT_STARTS[sprint_number] + timedelta(days=4 + offset),
        datetime.min.time(),
        tzinfo=UTC,
    ).replace(hour=14)
    return (
        sprint_number,
        build_at - timedelta(days=2),
        build_at - timedelta(days=1),
        build_at,
    )


def build_commits() -> list[dict]:
    commits = []
    chain_by_commit_number = {
        chain_number * 2: (chain_number, ticket_number)
        for chain_number, ticket_number in enumerate(CHAIN_TICKETS, start=1)
    }
    for number in range(1, 31):
        sprint_number = min(3, (number - 1) // 10 + 1)
        ticket_number = {
            1: number,
            2: number + 6,
            3: number + 13,
        }[sprint_number]
        committed = datetime.combine(
            SPRINT_STARTS[sprint_number] + timedelta(days=1 + (number - 1) % 6),
            datetime.min.time(),
            tzinfo=UTC,
        ).replace(hour=10)
        if number in chain_by_commit_number:
            chain_number, ticket_number = chain_by_commit_number[number]
            sprint_number, committed, _, _ = chain_timing(chain_number)
        digest = hashlib.sha1(f"copilote-demo-commit-{number}".encode()).hexdigest()
        commits.append(
            {
                "id": f"COM-{number:03d}",
                "project_id": PROJECT_ID,
                "ticket_id": f"TKT-{ticket_number:03d}",
                "sha": digest,
                "author": ASSIGNEES[number % len(ASSIGNEES)],
                "message": f"TKT-{ticket_number:03d} implémentation de démonstration",
                "committed_at": iso_datetime(committed),
                "additions": 20 + number * 3,
                "deletions": 4 + number % 17,
            }
        )
    return commits


def build_pull_requests() -> list[dict]:
    pull_requests = []
    for number, ticket_number in enumerate(CHAIN_TICKETS, start=1):
        sprint_number, _, created, _ = chain_timing(number)
        status = "merged"
        if number in {7, 10, 11, 12}:
            status = "open"
        pull_requests.append(
            {
                "id": f"PR-{number:03d}",
                "project_id": PROJECT_ID,
                "ticket_id": f"TKT-{ticket_number:03d}",
                "number": number,
                "title": f"TKT-{ticket_number:03d} livraison sprint {sprint_number}",
                "author": ASSIGNEES[number % len(ASSIGNEES)],
                "status": status,
                "source_branch": f"feature/TKT-{ticket_number:03d}",
                "target_branch": "main",
                "created_at": iso_datetime(created),
                "merged_at": (
                    iso_datetime(created + timedelta(hours=12)) if status == "merged" else None
                ),
                "review_count": 2 if status == "merged" else number % 2,
                "changed_files": 3 + number,
            }
        )
    return pull_requests


def build_builds(commits: list[dict]) -> list[dict]:
    statuses = [
        "success",
        "success",
        "success",
        "success",
        "success",
        "failed",
        "success",
        "success",
        "success",
        "success",
        "failed",
        "failed",
    ]
    builds = []
    for number, status in enumerate(statuses, start=1):
        sprint_number, _, _, started = chain_timing(number)
        duration = 180 + number * 7
        ticket_number = CHAIN_TICKETS[number - 1]
        builds.append(
            {
                "id": f"BLD-{number:03d}",
                "project_id": PROJECT_ID,
                "sprint_id": f"SPR-{sprint_number:03d}",
                "pull_request_id": f"PR-{number:03d}",
                "pipeline_name": "ci-main",
                "branch": f"feature/TKT-{ticket_number:03d}",
                "commit_sha": commits[min(len(commits), number * 2) - 1]["sha"],
                "status": status,
                "started_at": iso_datetime(started),
                "finished_at": iso_datetime(started + timedelta(seconds=duration)),
                "duration_seconds": duration,
            }
        )
    return builds


def build_test_results(builds: list[dict]) -> list[dict]:
    results = []
    for number, build in enumerate(builds, start=1):
        failed = 0 if build["status"] == "success" else 2 + number % 4
        total = 110 + number * 3
        skipped = number % 3
        passed = total - failed - skipped
        results.append(
            {
                "id": f"TST-{number:03d}",
                "project_id": PROJECT_ID,
                "build_id": build["id"],
                "suite_name": "backend-unit-and-integration",
                "status": "passed" if failed == 0 else "failed",
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "duration_seconds": 42.0 + number * 1.75,
                "executed_at": build["finished_at"],
            }
        )
    return results


def build_metrics() -> list[dict]:
    values = {
        1: [
            ("test_coverage", 86.0, "percent"),
            ("code_smells", 5.0, "count"),
            ("defect_density", 0.6, "per_kloc"),
        ],
        2: [
            ("test_coverage", 71.0, "percent"),
            ("code_smells", 11.0, "count"),
            ("defect_density", 1.4, "per_kloc"),
        ],
        3: [
            ("test_coverage", 54.0, "percent"),
            ("code_smells", 24.0, "count"),
            ("defect_density", 3.2, "per_kloc"),
        ],
    }
    measured_at = {
        1: "2026-06-21T18:00:00Z",
        2: "2026-07-05T18:00:00Z",
        3: "2026-07-13T08:00:00Z",
    }
    metrics = []
    number = 1
    for sprint_number, sprint_metrics in values.items():
        for name, value, unit in sprint_metrics:
            metrics.append(
                {
                    "id": f"MET-{number:03d}",
                    "project_id": PROJECT_ID,
                    "sprint_id": f"SPR-{sprint_number:03d}",
                    "name": name,
                    "value": value,
                    "unit": unit,
                    "source": "demo-sonarqube-adapter",
                    "measured_at": measured_at[sprint_number],
                }
            )
            number += 1
    return metrics


def expected_anomalies() -> list[dict]:
    return [
        {
            "rule_id": "QA-BLOCKED-LONG",
            "scenario": "SCN-02",
            "severity": "high",
            "source_type": "ticket",
            "source_id": "TKT-024",
            "description": "Ticket bloqué depuis plus de 72 heures.",
            "expected_signal": "blocked_duration_hours > 72",
        },
        {
            "rule_id": "QA-TICKET-OVERDUE",
            "scenario": "SCN-02",
            "severity": "medium",
            "source_type": "ticket",
            "source_id": "TKT-027",
            "description": "Ticket ouvert après sa date d'échéance.",
            "expected_signal": "due_date < reference_date and status != done",
        },
        {
            "rule_id": "QA-TICKET-OVERDUE",
            "scenario": "SCN-02",
            "severity": "medium",
            "source_type": "ticket",
            "source_id": "TKT-029",
            "description": "Ticket bloqué et arrivé à échéance.",
            "expected_signal": "due_date < reference_date and status != done",
        },
        {
            "rule_id": "QA-CRITICAL-BUG-OPEN",
            "scenario": "SCN-03",
            "severity": "critical",
            "source_type": "ticket",
            "source_id": "TKT-038",
            "description": "Bug critique de double débit toujours ouvert.",
            "expected_signal": "type == bug and priority == critical and status != done",
        },
        {
            "rule_id": "QA-BLOCKED-LONG",
            "scenario": "SCN-03",
            "severity": "critical",
            "source_type": "ticket",
            "source_id": "TKT-039",
            "description": "Déploiement bloqué depuis plus de 72 heures.",
            "expected_signal": "blocked_duration_hours > 72",
        },
        {
            "rule_id": "QA-TICKET-OVERDUE",
            "scenario": "SCN-03",
            "severity": "high",
            "source_type": "ticket",
            "source_id": "TKT-042",
            "description": "Ticket de paiement en retard.",
            "expected_signal": "due_date < reference_date and status != done",
        },
        {
            "rule_id": "QA-TICKET-OVERDUE",
            "scenario": "SCN-03",
            "severity": "high",
            "source_type": "ticket",
            "source_id": "TKT-045",
            "description": "Ticket de sécurité en retard.",
            "expected_signal": "due_date < reference_date and status != done",
        },
        {
            "rule_id": "QA-PIPELINE-FAILED",
            "scenario": "SCN-03",
            "severity": "critical",
            "source_type": "build",
            "source_id": "BLD-012",
            "description": "Deux pipelines consécutifs se terminent en échec.",
            "expected_signal": "latest_builds[-2:] == [failed, failed]",
        },
        {
            "rule_id": "QA-COVERAGE-LOW",
            "scenario": "SCN-03",
            "severity": "high",
            "source_type": "metric",
            "source_id": "MET-007",
            "description": "Couverture de tests à 54 %, sous le seuil de 70 %.",
            "expected_signal": "test_coverage < 70",
        },
    ]


def main() -> None:
    commits = build_commits()
    pull_requests = build_pull_requests()
    builds = build_builds(commits)
    dataset = {
        "version": "0.1",
        "generated_at": iso_datetime(GENERATED_AT),
        "reference_date": REFERENCE_DATE.isoformat(),
        "project": {
            "id": PROJECT_ID,
            "key": "COPQA",
            "name": "NovaShop — projet de démonstration QA",
            "description": (
                "Projet e-commerce entièrement fictif conçu pour tester trois états de sprint "
                "et les futures règles du Copilote IA QA."
            ),
            "repository_url": "https://example.invalid/novashop-demo",
            "created_at": "2026-06-01T09:00:00Z",
        },
        "sprints": [
            sprint_record(1, date(2026, 6, 8), date(2026, 6, 21), "completed", "sain"),
            sprint_record(2, date(2026, 6, 22), date(2026, 7, 5), "completed", "à risque"),
            sprint_record(3, date(2026, 7, 6), date(2026, 7, 19), "active", "critique"),
        ],
        "tickets": build_tickets(),
        "commits": commits,
        "pull_requests": pull_requests,
        "builds": builds,
        "test_results": build_test_results(builds),
        "metrics": build_metrics(),
        "risks": [],
        "reports": [],
        "expected_anomalies": expected_anomalies(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(dataset['tickets'])} tickets")


if __name__ == "__main__":
    main()
