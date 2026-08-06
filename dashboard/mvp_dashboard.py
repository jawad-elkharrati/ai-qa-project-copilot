from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from dashboard.api_client import API_URL, DashboardAPIError, api_get, api_get_content, api_post
from dashboard.formatting import human_datetime, severity_label

DECISION_LABELS = {
    "GO": "GO",
    "GO_WITH_CONDITIONS": "GO avec conditions",
    "NO_GO": "NO-GO",
    "INSUFFICIENT_INFORMATION": "Information insuffisante",
}


def show_api_error(error: Exception) -> None:
    message = str(error) if isinstance(error, DashboardAPIError) else "Erreur API inattendue."
    st.error(message)
    detail = getattr(error, "technical_detail", "") or str(error)
    if detail:
        with st.expander("Detail technique"):
            st.code(detail)


def api_call(path: str, **params):
    with st.spinner("Chargement des donnees..."):
        return api_get(path, **params)


def decision_badge(decision: str) -> None:
    label = DECISION_LABELS.get(decision, decision)
    with st.container(border=True):
        st.markdown(f"**Décision proposée : {label}**")


def apply_dashboard_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1440px; padding-top: 1.4rem; padding-bottom: 3rem;}
        [data-testid="stSidebar"] {border-right: 1px solid rgba(120, 120, 120, .18);}
        div[data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, .25);
            border-radius: 14px;
            padding: .85rem 1rem;

        }
        div[data-testid="stMetricLabel"] {font-weight: 650;}
        div[data-testid="stMetricValue"] {font-weight: 750;}
        .qa-hero {
            padding: 1.15rem 1.35rem; border-radius: 16px; margin-bottom: 1rem;
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, .25);
        }
        .qa-hero h2 {margin: 0; color: inherit; font-size: 1.55rem;}
        .qa-hero p {margin: .35rem 0 0; opacity: .86;}
        .section-label {font-size: .78rem; text-transform: uppercase; letter-spacing: .08em;
            font-weight: 700; margin: 1.2rem 0 .45rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_operational_kpis(overview: dict | None, metrics: list) -> None:
    st.markdown(
        '<div class="section-label">Santé opérationnelle du projet</div>', unsafe_allow_html=True
    )
    if not overview:
        st.info("Les KPI opérationnels ne sont pas disponibles pour cette date.")
        return
    cards = st.columns(5)
    cards[0].metric("Travail terminé", f"{overview.get('progress_percent', 0):.1f} %")
    cards[1].metric("Tickets bloqués", overview.get("blocked_tickets", 0))
    cards[2].metric("Tickets en retard", overview.get("overdue_tickets", 0))
    cards[3].metric("Builds échoués", overview.get("failed_builds", 0))
    coverage = overview.get("test_coverage")
    cards[4].metric("Couverture tests", "N/A" if coverage is None else f"{coverage:.1f} %")
    if metrics:
        with st.expander("Voir les métriques sources"):
            st.dataframe(metrics, width="stretch", hide_index=True)


def render_summary(
    analysis: dict,
    summary: dict,
    brief: dict,
    recommendations: list,
    overview: dict | None,
    metrics: list,
) -> None:
    st.subheader("Synthese du perimetre")
    delta = summary.get("delta", {})
    cards = st.columns(5)
    cards[0].metric("Score actuel", f"{analysis['score']} / 100")
    cards[1].metric("Niveau de risque", severity_label(analysis["severity"]))
    cards[2].metric(
        "Risk Delta",
        "Premiere analyse" if delta.get("delta") is None else f"{delta['delta']:+.1f}",
    )
    cards[3].metric("Confiance", f"{analysis['confidence_score']:.0%}")
    cards[4].metric("Couverture des preuves", f"{analysis['evidence_coverage']:.0%}")

    decision_badge(brief["suggested_decision"])
    status_cards = st.columns(4)
    status_cards[0].metric("Validation humaine", brief["human_validation_status"])
    status_cards[1].metric("Risques", analysis["finding_count"])
    status_cards[2].metric("Recommandations", len(recommendations))
    status_cards[3].metric("Dernier snapshot", brief["snapshot_id"])
    st.caption(f"Analyse generee le {human_datetime(brief['generated_at'])}.")
    render_operational_kpis(overview, metrics)

    if brief["suggested_decision"] == "INSUFFICIENT_INFORMATION":
        st.warning("Les informations disponibles ne permettent pas encore une decision fiable.")
    if brief.get("missing_information"):
        st.markdown("**Informations manquantes**")
        for item in brief["missing_information"]:
            st.write(f"- {item}")
    if not analysis.get("findings"):
        st.info("Aucun risque actif dans le dernier snapshot.")


def render_risks(analysis: dict) -> None:
    st.subheader("Risques")
    risks = analysis.get("findings", [])
    if not risks:
        st.info("La liste des risques est vide pour ce perimetre.")
        return

    policies = ["Toutes", *sorted({item["rule_id"] for item in risks})]
    severity = st.selectbox(
        "Filtrer par severite",
        ["Toutes", "critical", "high", "medium", "low"],
        key="risk_severity_filter",
    )
    policy = st.selectbox("Filtrer par politique", policies, key="risk_policy_filter")
    visible = [
        item
        for item in risks
        if (severity == "Toutes" or item["severity"] == severity)
        and (policy == "Toutes" or item["rule_id"] == policy)
    ]
    if not visible:
        st.info("Aucun risque ne correspond aux filtres selectionnes.")
        return

    contribution_by_policy = {
        item["policy_id"]: item["contribution"] for item in analysis.get("contributions", [])
    }
    contribution_rows = [
        {
            "Politique": item["policy_id"],
            "Contribution au score": item["contribution"],
        }
        for item in analysis.get("contributions", [])
        if item.get("contribution", 0) > 0
    ]
    if contribution_rows:
        st.markdown("**Composition du score de risque**")
        st.bar_chart(contribution_rows, x="Politique", y="Contribution au score")
    st.dataframe(
        [
            {
                "Risque": item["title"],
                "Severite": severity_label(item["severity"]),
                "Politique": item["rule_id"],
                "Contribution": contribution_by_policy.get(item["rule_id"]),
                "Confiance": item["confidence"],
                "Statut": item["status"],
            }
            for item in visible
        ],
        width="stretch",
        hide_index=True,
    )
    labels = {f"{item['source_id']} - {item['title']}": item for item in visible}
    selected = labels[st.selectbox("Risque a examiner", list(labels), key="risk_detail")]
    with st.container(border=True):
        st.markdown(f"### {selected['title']}")
        st.write(selected["description"])
        st.write(f"**Politique :** {selected['rule_id']}")
        st.write(f"**Source :** {selected['source_type']} / {selected['source_id']}")
        st.write(f"**Recommandation source :** {selected['recommendation']}")
        if selected.get("evidence"):
            with st.expander("Preuves"):
                st.json(selected["evidence"])
        else:
            st.info("Aucune preuve detaillee n'est disponible pour ce risque.")
    missing = analysis.get("missing_information", [])
    if missing:
        st.warning("Certaines informations attendues sont absentes.")
        st.dataframe(missing, width="stretch", hide_index=True)


def render_decision(project_id: str, brief: dict) -> None:
    st.subheader("Decision Brief")
    decision_badge(brief["suggested_decision"])
    st.write(brief["justification"])

    blocker_column, condition_column = st.columns(2)
    with blocker_column:
        st.markdown("**Elements bloquants**")
        if brief.get("blockers"):
            for item in brief["blockers"]:
                st.write(f"- {item}")
        else:
            st.info("Aucun element bloquant signale par l'API.")
    with condition_column:
        st.markdown("**Conditions**")
        if brief.get("conditions"):
            for item in brief["conditions"]:
                st.write(f"- {item}")
        else:
            st.info("Aucune condition supplementaire.")

    st.markdown("**Politiques violees**")
    if brief.get("violated_policies"):
        st.write(", ".join(brief["violated_policies"]))
    else:
        st.info("Aucune politique violee.")

    latest = brief.get("latest_review")
    st.write(f"Statut de validation : **{brief['human_validation_status']}**")
    if latest:
        st.caption(
            f"Derniere validation par {latest['actor']} ({latest['actor_role']}) "
            f"le {human_datetime(latest['created_at'])}."
        )

    with st.form("decision_review_form"):
        status = st.radio(
            "Action humaine",
            ["CONFIRMED", "OVERRIDDEN", "REJECTED"],
            horizontal=True,
        )
        final_decision = st.selectbox(
            "Decision finale",
            list(DECISION_LABELS),
            index=list(DECISION_LABELS).index(brief["suggested_decision"]),
            format_func=lambda value: DECISION_LABELS[value],
            disabled=status == "CONFIRMED",
        )
        actor = st.text_input("Identite", key="decision_actor")
        actor_role = st.text_input("Role", key="decision_actor_role")
        justification = st.text_area("Justification", key="decision_justification")
        comment = st.text_area("Commentaire", key="decision_comment")
        confirm = st.checkbox("Je confirme qu'aucune action externe ne sera executee.")
        submitted = st.form_submit_button("Enregistrer la validation", type="primary")
        if submitted:
            if not confirm:
                st.error("La confirmation humaine est obligatoire.")
            else:
                payload = {
                    "snapshot_id": brief["snapshot_id"],
                    "status": status,
                    "final_decision": None if status == "CONFIRMED" else final_decision,
                    "actor": actor,
                    "actor_role": actor_role,
                    "justification": justification,
                    "comment": comment or None,
                }
                try:
                    api_post(f"/projects/{project_id}/decisions", payload=payload)
                    st.success("Validation humaine enregistree dans l'historique.")
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)


def _render_recommendation_outcome(recommendation_id: str) -> None:
    try:
        outcome = api_call(f"/recommendations/{recommendation_id}/outcome")
    except Exception as exc:
        show_api_error(exc)
        return

    st.markdown("**Efficacité observée**")
    status_labels = {
        "NOT_YET_MEASURABLE": "Résultat non encore mesurable",
        "IMPROVEMENT_OBSERVED": "Amélioration observée",
        "NO_IMPROVEMENT_OBSERVED": "Aucune amélioration observée",
        "INSUFFICIENT_DATA": "Données insuffisantes",
    }
    st.write(status_labels.get(outcome["status"], outcome["status"]))
    if outcome["status"] != "NOT_YET_MEASURABLE":
        cards = st.columns(3)
        cards[0].metric("Score avant", outcome["score_before"])
        cards[1].metric("Score après", outcome["score_after"])
        cards[2].metric("Variation observée", f"{outcome['score_delta']:+.1f}")
    st.caption(outcome["observation"])
    st.caption("Corrélation temporelle uniquement : aucune causalité n’est attribuée.")


def _recommendation_action_payload(
    actor: str,
    actor_role: str,
    justification: str,
    comment: str,
    changes: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "actor": actor,
        "actor_role": actor_role,
        "justification": justification,
        "comment": comment or None,
        "changes": changes or None,
    }


def render_recommendations(project_id: str, recommendations: list) -> None:
    st.subheader("Recommandations")
    status = st.selectbox(
        "Statut",
        [
            "Tous",
            "PROPOSED",
            "ACCEPTED",
            "MODIFIED",
            "IN_PROGRESS",
            "REJECTED",
            "COMPLETED",
        ],
        key="recommendation_status",
    )
    priority = st.selectbox(
        "Priorité",
        ["Toutes", "CRITICAL", "HIGH", "MEDIUM", "LOW"],
        key="recommendation_priority",
    )
    visible = [
        item
        for item in recommendations
        if (status == "Tous" or item["status"] == status)
        and (priority == "Toutes" or item["priority"] == priority)
    ]
    if not visible:
        st.info("Aucune recommandation ne correspond aux filtres sélectionnés.")
        return

    st.dataframe(
        [
            {
                "Titre": item["title"],
                "Politique": item["policy_id"],
                "Priorité": item["priority"],
                "Score de priorité": item["priority_score"],
                "Statut": item["status"],
                "Observations": item["observation_count"],
            }
            for item in visible
        ],
        width="stretch",
        hide_index=True,
    )
    labels = {f"{item['priority']} - {item['title']}": item for item in visible}
    selected = labels[
        st.selectbox("Recommandation à examiner", list(labels), key="recommendation_detail")
    ]
    st.info(selected["priority_justification"])
    st.write(selected["description"])

    try:
        history = api_call(f"/recommendations/{selected['id']}/history")
    except Exception as exc:
        show_api_error(exc)
    else:
        if history.get("items"):
            with st.expander("Historique append-only"):
                st.dataframe(history["items"], width="stretch", hide_index=True)

    selected_status = selected["status"]
    if selected_status in {"ACCEPTED", "MODIFIED", "IN_PROGRESS", "COMPLETED"}:
        _render_recommendation_outcome(selected["id"])

    if selected_status == "PROPOSED":
        with st.form("recommendation_action_form"):
            action = st.radio("Action", ["accept", "modify", "reject"], horizontal=True)
            actor = st.text_input("Identité", key="recommendation_actor")
            actor_role = st.text_input("Rôle", key="recommendation_actor_role")
            justification = st.text_area("Justification", key="recommendation_justification")
            comment = st.text_area("Commentaire", key="recommendation_comment")
            assigned_to = st.text_input(
                "Responsable proposé",
                value=selected.get("assigned_to") or "",
                disabled=action != "modify",
            )
            confirm = st.checkbox(
                "Je confirme que cette validation reste locale.",
                key="recommendation_confirm",
            )
            submitted = st.form_submit_button("Enregistrer l'action", type="primary")
            if submitted:
                if not confirm:
                    st.error("La confirmation humaine est obligatoire.")
                else:
                    changes = {"assigned_to": assigned_to} if action == "modify" else None
                    payload = _recommendation_action_payload(
                        actor, actor_role, justification, comment, changes
                    )
                    try:
                        api_post(f"/recommendations/{selected['id']}/{action}", payload=payload)
                        st.success("Action enregistrée dans l'historique.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
        return

    if selected_status in {"ACCEPTED", "MODIFIED"}:
        with st.form("recommendation_start_form"):
            st.markdown("**Démarrer le traitement**")
            actor = st.text_input("Identité", key="recommendation_start_actor")
            actor_role = st.text_input("Rôle", key="recommendation_start_role")
            justification = st.text_area("Justification", key="recommendation_start_justification")
            comment = st.text_area("Commentaire", key="recommendation_start_comment")
            assigned_to = st.text_input(
                "Responsable",
                value=selected.get("assigned_to") or "",
                key="recommendation_start_assignee",
            )
            due_date = st.text_input(
                "Date limite (AAAA-MM-JJ)",
                value=str(selected.get("due_date") or ""),
                key="recommendation_start_due_date",
            )
            confirm = st.checkbox(
                "Je confirme que ce suivi reste local.",
                key="recommendation_start_confirm",
            )
            submitted = st.form_submit_button("Passer en cours")
            if submitted:
                if not confirm:
                    st.error("La confirmation humaine est obligatoire.")
                else:
                    changes = {}
                    if assigned_to.strip():
                        changes["assigned_to"] = assigned_to.strip()
                    if due_date.strip():
                        changes["due_date"] = due_date.strip()
                    payload = _recommendation_action_payload(
                        actor, actor_role, justification, comment, changes
                    )
                    try:
                        api_post(
                            f"/recommendations/{selected['id']}/start",
                            payload=payload,
                        )
                        st.success("Traitement démarré et historisé.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
        return

    if selected_status == "IN_PROGRESS":
        with st.form("recommendation_complete_form"):
            st.markdown("**Clôturer le traitement**")
            actor = st.text_input("Identité", key="recommendation_complete_actor")
            actor_role = st.text_input("Rôle", key="recommendation_complete_role")
            justification = st.text_area(
                "Justification", key="recommendation_complete_justification"
            )
            comment = st.text_area(
                "Commentaire de clôture obligatoire",
                key="recommendation_complete_comment",
            )
            confirm = st.checkbox(
                "Je confirme que cette clôture reste locale.",
                key="recommendation_complete_confirm",
            )
            submitted = st.form_submit_button("Marquer comme terminée")
            if submitted:
                if not confirm:
                    st.error("La confirmation humaine est obligatoire.")
                else:
                    payload = _recommendation_action_payload(
                        actor, actor_role, justification, comment
                    )
                    try:
                        api_post(
                            f"/recommendations/{selected['id']}/complete",
                            payload=payload,
                        )
                        st.success("Traitement clôturé et historisé.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
        return

    st.caption("Aucune transition supplémentaire n’est disponible pour ce statut.")


def _render_report_exports(
    *,
    project_id: str,
    report_kind: str,
    params: dict[str, str],
    filename_prefix: str,
) -> None:
    state_key = f"report_exports_{report_kind}_{project_id}_{'_'.join(params.values())}"
    if st.button("Préparer les exports", key=f"prepare_{state_key}"):
        try:
            markdown, markdown_type = api_get_content(
                f"/projects/{project_id}/reports/{report_kind}/export",
                **params,
                format="markdown",
            )
            html, html_type = api_get_content(
                f"/projects/{project_id}/reports/{report_kind}/export",
                **params,
                format="html",
            )
        except Exception as exc:
            show_api_error(exc)
        else:
            st.session_state[state_key] = {
                "markdown": markdown,
                "markdown_type": markdown_type,
                "html": html,
                "html_type": html_type,
            }

    exports = st.session_state.get(state_key)
    if not exports:
        st.caption("Les exports sont générés à la demande par l’API.")
        return
    markdown_col, html_col = st.columns(2)
    markdown_col.download_button(
        "Télécharger Markdown",
        data=exports["markdown"],
        file_name=f"{filename_prefix}.md",
        mime=exports["markdown_type"],
        key=f"download_md_{state_key}",
    )
    html_col.download_button(
        "Télécharger HTML",
        data=exports["html"],
        file_name=f"{filename_prefix}.html",
        mime=exports["html_type"],
        key=f"download_html_{state_key}",
    )


def render_reports(project_id: str, reference_date: date) -> None:
    st.subheader("Rapports de pilotage")
    st.caption("Rapports calculés par l’API à partir des snapshots, sans contenu inventé.")
    daily_tab, weekly_tab = st.tabs(["Rapport quotidien", "Rapport hebdomadaire"])
    with daily_tab:
        selected_date = st.date_input("Date du rapport", value=reference_date)
        try:
            report = api_call(
                f"/projects/{project_id}/reports/daily", report_date=selected_date.isoformat()
            )
        except Exception as exc:
            show_api_error(exc)
        else:
            decision_badge(report["suggested_decision"])
            cards = st.columns(4)
            cards[0].metric("Score", report.get("risk_score", report.get("score", "N/A")))
            cards[1].metric("Niveau", severity_label(report.get("risk_level", "unknown")))
            cards[2].metric("Confiance", f"{report.get('confidence_score', 0):.0%}")
            risk_delta = report.get("risk_delta")
            if isinstance(risk_delta, dict):
                risk_delta = risk_delta.get("delta")
            delta_value = "N/A" if risk_delta is None else f"{risk_delta:+.1f}"
            cards[3].metric("Variation", delta_value)
            st.write(report.get("decision_justification", ""))

            conditions = report.get("decision_conditions", [])
            if conditions:
                st.markdown("**Conditions à satisfaire**")
                for condition in conditions:
                    st.markdown(f"- {condition}")

            left, right = st.columns(2)
            with left:
                st.markdown("**Risques nouveaux ou aggravés**")
                changed_risks = report.get("new_risks", []) + report.get("aggravated_risks", [])
                if changed_risks:
                    risk_rows = [
                        {
                            "Risque": item.get("title") or item.get("risk_key") or item.get("id"),
                            "Politique": item.get("policy_id", "—"),
                            "Sévérité": severity_label(item.get("severity", "unknown")),
                            "Contribution": item.get("contribution", "—"),
                        }
                        for item in changed_risks
                    ]
                    st.dataframe(risk_rows, width="stretch", hide_index=True)
                else:
                    st.caption("Aucun risque nouveau ou aggravé sur cette journée.")
            with right:
                st.markdown("**Preuves disponibles**")
                evidence = report.get("available_evidence", [])
                if evidence:
                    evidence_rows = [
                        {
                            "Politique": item.get("policy_id", "—"),
                            "Valeur observée": item.get("observed_value", "—"),
                            "Date": item.get("reference_date", "—"),
                        }
                        for item in evidence
                        if isinstance(item, dict)
                    ]
                    st.dataframe(evidence_rows, width="stretch", hide_index=True)
                else:
                    st.caption("Aucune preuve disponible.")

                missing = report.get("missing_evidence", [])
                st.markdown("**Informations manquantes**")
                if missing:
                    for item in missing:
                        st.markdown(f"- {item}")
                else:
                    st.caption("Aucune preuve manquante signalée.")
            with st.expander("Données techniques pour audit"):
                st.json(report)
            _render_report_exports(
                project_id=project_id,
                report_kind="daily",
                params={"report_date": selected_date.isoformat()},
                filename_prefix=f"rapport-quotidien-{project_id}-{selected_date.isoformat()}",
            )

    with weekly_tab:
        period = st.date_input(
            "Période",
            value=(reference_date - timedelta(days=6), reference_date),
            key="weekly_period",
        )
        if not isinstance(period, tuple) or len(period) != 2:
            st.caption("Sélectionnez une date de début et une date de fin.")
        else:
            try:
                report = api_call(
                    f"/projects/{project_id}/reports/weekly",
                    period_start=period[0].isoformat(),
                    period_end=period[1].isoformat(),
                )
            except Exception as exc:
                show_api_error(exc)
            else:
                decision_badge(report["suggested_next_decision"])
                trend_labels = {
                    "IMPROVING": "En amélioration",
                    "DEGRADING": "En dégradation",
                    "STABLE": "Stable",
                }
                trend = str(report.get("trend", "N/A"))
                cards = st.columns(4)
                cards[0].metric("Meilleur score", report.get("best_score", "N/A"))
                cards[1].metric("Pire score", report.get("worst_score", "N/A"))
                cards[2].metric("Tendance", trend_labels.get(trend.upper(), trend))
                cards[3].metric("Snapshots", len(report.get("score_evolution", [])))
                st.write(report.get("summary", ""))

                score_evolution = report.get("score_evolution", [])
                if score_evolution:
                    st.markdown("**Évolution du score**")
                    st.line_chart(score_evolution, x="date", y="score", height=220)

                status_col, policy_col = st.columns(2)
                with status_col:
                    st.markdown("**Cycle des recommandations**")
                    statuses = report.get("recommendation_statuses", {})
                    if statuses:
                        status_rows = [
                            {"Statut": status.replace("_", " "), "Nombre": count}
                            for status, count in sorted(statuses.items())
                        ]
                        st.dataframe(status_rows, width="stretch", hide_index=True)
                    else:
                        st.caption("Aucune recommandation sur la période.")
                with policy_col:
                    st.markdown("**Politiques les plus violées**")
                    frequencies = report.get("policy_violation_frequency", {})
                    if frequencies:
                        policy_rows = [
                            {"Politique": policy, "Occurrences": count}
                            for policy, count in sorted(
                                frequencies.items(), key=lambda item: (-item[1], item[0])
                            )
                        ]
                        st.dataframe(policy_rows, width="stretch", hide_index=True)
                    else:
                        st.caption("Aucune violation de politique sur la période.")

                st.markdown("**Lecture de l’impact observé**")
                st.caption(report.get("observed_impact", "Résultat non encore mesurable."))
                with st.expander("Données techniques pour audit"):
                    st.json(report)
                _render_report_exports(
                    project_id=project_id,
                    report_kind="weekly",
                    params={
                        "period_start": period[0].isoformat(),
                        "period_end": period[1].isoformat(),
                    },
                    filename_prefix=(
                        f"rapport-hebdomadaire-{project_id}-"
                        f"{period[0].isoformat()}-{period[1].isoformat()}"
                    ),
                )


def render_evolution(project_id: str, reference_date: date, history: dict) -> None:
    st.subheader("Évolution du risque")
    items = history.get("items", []) if isinstance(history, dict) else []
    timeline = sorted(
        [
            {
                "date": item.get("reference_date") or str(item.get("calculated_at", ""))[:10],
                "score": item.get("score", 0),
                "confiance": item.get("confidence_score", 0),
            }
            for item in items
        ],
        key=lambda item: item["date"],
    )
    if timeline:
        scores = [item["score"] for item in timeline]
        cards = st.columns(4)
        cards[0].metric("Dernier score", timeline[-1]["score"])
        cards[1].metric("Meilleur score", min(scores))
        cards[2].metric("Pire score", max(scores))
        cards[3].metric("Snapshots", len(timeline))
        st.line_chart(timeline, x="date", y="score")
        with st.expander("Historique des snapshots"):
            st.dataframe(timeline, width="stretch", hide_index=True)
    else:
        st.info("Aucune evolution de score disponible.")

    try:
        weekly = api_call(
            f"/projects/{project_id}/reports/weekly",
            period_start=(reference_date - timedelta(days=6)).isoformat(),
            period_end=reference_date.isoformat(),
        )
    except Exception:
        st.warning("L'agrégation hebdomadaire n'est pas disponible pour cette période.")
        return

    st.metric("Tendance hebdomadaire", weekly.get("trend", "N/A"))
    contributions = weekly.get("contribution_evolution", {})
    st.markdown("**Évolution des contributions**")
    if contributions:
        st.json(contributions)
    else:
        st.info("Aucune variation de contribution disponible.")
    appeared, persistent, resolved = st.columns(3)
    with appeared:
        st.markdown("**Risques apparus**")
        st.write(weekly.get("new_risks", []) or "Aucun")
    with persistent:
        st.markdown("**Risques persistants**")
        st.write(weekly.get("persistent_risks", []) or "Aucun")
    with resolved:
        st.markdown("**Risques résolus**")
        st.write(weekly.get("resolved_risks", []) or "Aucun")
    st.markdown("**Recommandations et décisions associées**")
    st.write(
        {
            "recommandations_emises": weekly.get("recommendations_emitted", 0),
            "statuts": weekly.get("recommendation_statuses", {}),
            "decisions_humaines": weekly.get("human_decisions", {}),
        }
    )


def run_dashboard() -> None:
    st.set_page_config(page_title="Copilote QA", page_icon="🧭", layout="wide")
    apply_dashboard_theme()
    st.title("Copilote QA - Tableau de decision")
    try:
        projects = api_call("/projects")
    except Exception as exc:
        show_api_error(exc)
        st.stop()
    if not isinstance(projects, list):
        show_api_error(ValueError("GET /projects n'a pas retourné une liste"))
        st.stop()
    if not projects:
        st.warning("Aucun projet disponible. Chargez les données NovaShop via l'API.")
        st.stop()

    labels = {f"{item['key']} · {item['name']}": item for item in projects}
    selected_project = labels[st.sidebar.selectbox("Projet", list(labels))]
    project_id = selected_project["id"]
    st.sidebar.caption("API connectée")
    st.sidebar.caption(f"Source : {API_URL}")
    st.sidebar.markdown("---")
    st.sidebar.caption("Lecture seule des sources externes · validation humaine obligatoire")

    try:
        analysis = api_call("/risks", project_id=project_id)
        summary = api_call(f"/projects/{project_id}/risk-summary")
        brief = api_call(f"/projects/{project_id}/decision-brief")
        recommendations = api_call(f"/projects/{project_id}/recommendations")
    except Exception as exc:
        show_api_error(exc)
        st.stop()
    if not analysis or not brief:
        st.info("Aucune analyse exploitable n'est disponible pour ce projet.")
        st.stop()
    if not isinstance(recommendations, list):
        show_api_error(ValueError("La liste des recommandations est invalide"))
        st.stop()

    try:
        history = api_call(f"/projects/{project_id}/risk-history")
    except Exception:
        history = {"items": []}
    available_dates = [date.fromisoformat(str(analysis["reference_date"]))]
    for item in history.get("items", []):
        value = item.get("reference_date")
        if value:
            available_dates.append(date.fromisoformat(str(value)))
    reference_date = max(available_dates)
    try:
        overview = api_call("/overview", project_id=project_id, as_of=reference_date.isoformat())
    except Exception:
        overview = None
    try:
        metrics = api_call("/metrics", project_id=project_id)
    except Exception:
        metrics = []

    st.markdown(
        f"""
        <div class="qa-hero">
          <h2>{selected_project["key"]} · {selected_project["name"]}</h2>
          <p>Tableau de décision QA · données au {reference_date.isoformat()} ·
          gouvernance humaine</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tabs = st.tabs(["Synthese", "Risques", "Decision", "Recommandations", "Rapports", "Evolution"])
    with tabs[0]:
        render_summary(analysis, summary, brief, recommendations, overview, metrics)
    with tabs[1]:
        render_risks(analysis)
    with tabs[2]:
        render_decision(project_id, brief)
    with tabs[3]:
        render_recommendations(project_id, recommendations)
    with tabs[4]:
        render_reports(project_id, reference_date)
    with tabs[5]:
        render_evolution(project_id, reference_date, history)
