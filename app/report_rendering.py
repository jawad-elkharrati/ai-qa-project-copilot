from __future__ import annotations

from dataclasses import dataclass
from html import escape


class ReportRenderingError(ValueError):
    pass


@dataclass(frozen=True)
class ReportSection:
    title: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class ReportDocument:
    title: str
    metadata: tuple[tuple[str, str], ...]
    sections: tuple[ReportSection, ...]


def _value(value: object, default: str = "Aucune") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _items(values: list[object], *keys: str) -> tuple[str, ...]:
    rendered: list[str] = []
    for value in values:
        if isinstance(value, dict):
            parts = [
                f"{key}: {_value(value.get(key))}" for key in keys if value.get(key) is not None
            ]
            rendered.append(" · ".join(parts) if parts else _value(value))
        else:
            rendered.append(_value(value))
    return tuple(rendered) or ("Aucun",)


def _daily_document(report: dict[str, object]) -> ReportDocument:
    delta = report.get("risk_delta")
    if isinstance(delta, dict):
        delta = delta.get("delta")
    sections = (
        ReportSection(
            "Décision QA suggérée",
            (
                _value(report.get("suggested_decision")),
                _value(report.get("decision_justification")),
            ),
        ),
        ReportSection(
            "Conditions",
            _items(list(report.get("decision_conditions", []))),
        ),
        ReportSection(
            "Risques nouveaux",
            _items(list(report.get("new_risks", [])), "policy_id", "title", "severity"),
        ),
        ReportSection(
            "Risques aggravés",
            _items(list(report.get("aggravated_risks", [])), "policy_id", "title", "severity"),
        ),
        ReportSection(
            "Risques résolus",
            _items(list(report.get("resolved_risks", [])), "policy_id", "title", "severity"),
        ),
        ReportSection(
            "Politiques violées",
            _items(list(report.get("violated_policies", []))),
        ),
        ReportSection(
            "Contributions principales",
            _items(
                list(report.get("top_contributions", [])),
                "policy_id",
                "contribution",
                "explanation",
            ),
        ),
        ReportSection(
            "Informations manquantes",
            _items(list(report.get("missing_evidence", []))),
        ),
        ReportSection(
            "Recommandations prioritaires",
            _items(
                list(report.get("recommendations", [])),
                "priority",
                "title",
                "status",
            ),
        ),
    )
    return ReportDocument(
        title="Rapport QA quotidien",
        metadata=(
            ("Projet", _value(report.get("project_id"))),
            ("Date", _value(report.get("report_date"))),
            ("Snapshot", _value(report.get("snapshot_id"))),
            ("Score", f"{float(report.get('score', 0)):.1f}/100"),
            ("Niveau", _value(report.get("risk_level"))),
            ("Variation", _value(delta)),
            ("Confiance", f"{float(report.get('confidence_score', 0)):.0%}"),
        ),
        sections=sections,
    )


def _weekly_document(report: dict[str, object]) -> ReportDocument:
    frequencies = report.get("policy_violation_frequency", {})
    frequency_items = (
        tuple(
            f"{policy}: {count} occurrence(s)"
            for policy, count in sorted(
                dict(frequencies).items(), key=lambda item: (-item[1], item[0])
            )
        )
        if frequencies
        else ("Aucune",)
    )
    statuses = report.get("recommendation_statuses", {})
    status_items = (
        tuple(f"{status}: {count}" for status, count in sorted(dict(statuses).items()))
        if statuses
        else ("Aucune",)
    )
    sections = (
        ReportSection("Synthèse", (_value(report.get("summary")),)),
        ReportSection(
            "Décision QA suggérée",
            (
                _value(report.get("suggested_next_decision")),
                _value(report.get("decision_justification")),
            ),
        ),
        ReportSection(
            "Risques nouveaux",
            _items(list(report.get("new_risks", [])), "policy_id", "title", "severity"),
        ),
        ReportSection(
            "Risques persistants",
            _items(list(report.get("persistent_risks", [])), "policy_id", "title", "severity"),
        ),
        ReportSection(
            "Risques résolus",
            _items(list(report.get("resolved_risks", [])), "policy_id", "title", "severity"),
        ),
        ReportSection("Politiques les plus violées", frequency_items),
        ReportSection("Cycle des recommandations", status_items),
        ReportSection("Impact observé", (_value(report.get("observed_impact")),)),
    )
    return ReportDocument(
        title="Rapport QA hebdomadaire",
        metadata=(
            ("Projet", _value(report.get("project_id"))),
            ("Période", f"{report.get('period_start')} — {report.get('period_end')}"),
            ("Meilleur score", _value(report.get("best_score"))),
            ("Pire score", _value(report.get("worst_score"))),
            ("Variation", _value(report.get("score_change"))),
            ("Tendance", _value(report.get("trend"))),
            ("Snapshots", str(len(list(report.get("snapshot_ids", []))))),
        ),
        sections=sections,
    )


def build_report_document(report: dict[str, object]) -> ReportDocument:
    report_type = report.get("report_type")
    if report_type == "DAILY":
        return _daily_document(report)
    if report_type == "WEEKLY":
        return _weekly_document(report)
    raise ReportRenderingError("unsupported report type")


def render_report_markdown(report: dict[str, object]) -> str:
    document = build_report_document(report)
    lines = [f"# {document.title}", ""]
    lines.extend(f"- **{label}** : {value}" for label, value in document.metadata)
    for section in document.sections:
        lines.extend(("", f"## {section.title}", ""))
        lines.extend(f"- {item}" for item in section.items)
    lines.extend(
        (
            "",
            "---",
            "Validation humaine obligatoire.",
            "Aucune action externe n’a été exécutée.",
            "",
        )
    )
    return "\n".join(lines)


def render_report_html(report: dict[str, object]) -> str:
    document = build_report_document(report)
    metadata = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in document.metadata
    )
    sections = "".join(
        f"<section><h2>{escape(section.title)}</h2><ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in section.items)
        + "</ul></section>"
        for section in document.sections
    )
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        f"<title>{escape(document.title)}</title></head><body>"
        f"<main><h1>{escape(document.title)}</h1><dl>{metadata}</dl>{sections}"
        "<footer><p>Validation humaine obligatoire.</p>"
        "<p>Aucune action externe n’a été exécutée.</p></footer></main></body></html>"
    )
