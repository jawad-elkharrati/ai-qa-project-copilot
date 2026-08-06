from datetime import date

import pytest

from app.dataset import load_dataset
from app.report_rendering import (
    ReportRenderingError,
    render_report_html,
    render_report_markdown,
)
from app.report_service import daily_report, weekly_report
from app.seed import seed_dataset


def _seed(db_session) -> None:
    seed_dataset(db_session, load_dataset("data/demo_dataset_v0.1.json"))


def test_daily_markdown_export_is_deterministic_and_governed(db_session) -> None:
    _seed(db_session)
    report = daily_report(db_session, "PRJ-COPILOTE", date(2026, 7, 20))

    first = render_report_markdown(report)
    second = render_report_markdown(report)

    assert first == second
    assert first.startswith("# Rapport QA quotidien")
    assert "**Score** : 12.0/100" in first
    assert "QA-TICKET-OVERDUE" in first
    assert "Validation humaine obligatoire" in first
    assert "Aucune action externe n’a été exécutée" in first


def test_weekly_html_export_contains_aggregates_and_escapes_content(db_session) -> None:
    _seed(db_session)
    report = weekly_report(
        db_session,
        "PRJ-COPILOTE",
        date(2026, 7, 14),
        date(2026, 7, 20),
    )
    report["summary"] = "Situation <contrôlée> & vérifiée"

    rendered = render_report_html(report)

    assert rendered.startswith("<!doctype html>")
    assert "Rapport QA hebdomadaire" in rendered
    assert "QA-TICKET-OVERDUE: 7 occurrence(s)" in rendered
    assert "Situation &lt;contrôlée&gt; &amp; vérifiée" in rendered
    assert "aucune causalité" in rendered
    assert "<script" not in rendered


def test_renderer_rejects_unknown_report_type() -> None:
    with pytest.raises(ReportRenderingError, match="unsupported report type"):
        render_report_markdown({"report_type": "MONTHLY"})
