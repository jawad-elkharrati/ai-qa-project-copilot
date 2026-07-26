from __future__ import annotations

import streamlit as st

from dashboard.api_client import API_URL, DashboardAPIError, api_get, api_post
from dashboard.formatting import (
    decision_label,
    decision_payload,
    delta_label,
    global_message,
    human_datetime,
    ordered_evidence_nodes,
    readable_evidence_edges,
    readiness_label,
    risk_status_label,
    severity_label,
    source_label,
)


def show_api_error(error: Exception, *, stop: bool = False) -> None:
    if isinstance(error, DashboardAPIError):
        message = str(error)
        detail = error.technical_detail
    else:
        message = "Une réponse inattendue empêche l'affichage de cette section."
        detail = str(error)
    st.error(message)
    if detail:
        with st.expander("Détail technique"):
            st.code(detail)
    if stop:
        st.stop()


def optional_get(path: str, **params):
    try:
        return api_get(path, **params)
    except Exception:
        return None


def current_decision(risk_id: str) -> dict:
    history = optional_get(f"/risks/{risk_id}/decisions")
    if not history:
        return {"current_status": "pending", "items": []}
    return history


def show_global_status(severity: str, finding_count: int) -> None:
    message = global_message(severity, finding_count)
    if severity == "critical":
        st.error(message)
    elif severity in {"high", "medium"}:
        st.warning(message)
    else:
        st.success(message)


def render_project_health(overview: dict) -> None:
    cards = st.columns(5)
    cards[0].metric("Travail terminé", f"{overview['progress_percent']} %")
    cards[1].metric("Tickets bloqués", overview["blocked_tickets"])
    cards[2].metric("Tickets en retard", overview["overdue_tickets"])
    cards[3].metric("Builds échoués", overview["failed_builds"])
    coverage = overview["test_coverage"]
    cards[4].metric("Couverture des tests", "N/A" if coverage is None else f"{coverage} %")


def render_readiness(readiness: dict | None) -> None:
    st.subheader("Peut-on avancer ?")
    if not readiness:
        st.info("La synthèse de décision n'est pas encore disponible.")
        return

    decision = readiness["decision"]
    message = readiness_label(decision)
    if decision == "NO-GO":
        st.error(f"**{message}**")
    elif decision == "GO WITH CONDITIONS":
        st.warning(f"**{message}**")
    else:
        st.success(f"**{message}**")

    reasons = readiness.get("reasons", [])
    if reasons:
        st.markdown("**Pourquoi ?**")
        for reason in reasons:
            st.write(f"- {reason}")

    conditions = readiness.get("conditions", [])
    actions = readiness.get("priority_actions", [])
    if conditions or actions:
        condition_column, action_column = st.columns(2)
        with condition_column:
            st.markdown("**Conditions à respecter**")
            if conditions:
                for condition in conditions:
                    st.write(f"- {condition}")
            else:
                st.caption("Aucune condition supplémentaire.")
        with action_column:
            st.markdown("**Prochaines actions**")
            if actions:
                for index, action in enumerate(actions, start=1):
                    st.write(f"{index}. {action}")
            else:
                st.caption("Aucune action prioritaire.")

    st.caption(
        "Cette synthèse est une proposition déterministe. "
        "Une validation humaine est nécessaire avant toute décision."
    )


def render_human_decision(
    selected_risk: dict,
    decision_history: dict,
) -> None:
    st.subheader("Décision humaine")
    st.warning(
        "Cette décision reste locale : elle ne déclenche aucune action dans Jira, GitHub ou CI/CD."
    )
    current = decision_history.get("current_decision")
    st.write(
        f"Statut actuel : **{decision_label(decision_history.get('current_status', 'pending'))}**"
    )
    if current:
        st.write(
            f"Dernière décision par **{current['decided_by']}**, "
            f"le {human_datetime(current['decided_at'])}."
        )
        if current.get("comment"):
            st.write(f"Commentaire : {current['comment']}")

    with st.form("human_decision_form"):
        status = st.radio(
            "Votre décision",
            ["accepted", "modified", "rejected"],
            format_func=decision_label,
            horizontal=True,
        )
        actor = st.text_input("Votre nom")
        comment = st.text_area("Commentaire")
        modified = st.text_area(
            "Recommandation modifiée",
            value=selected_risk["recommendation"],
            disabled=status != "modified",
        )
        confirm = st.checkbox(
            "Je confirme que cette décision reste locale et ne lance aucune action automatique."
        )
        submitted = st.form_submit_button("Enregistrer la décision", type="primary")
        if submitted:
            if not confirm:
                st.error("La confirmation humaine est obligatoire.")
            else:
                payload = decision_payload(
                    status=status,
                    actor=actor,
                    comment=comment,
                    modified_recommendation=modified,
                )
                try:
                    api_post(
                        f"/risks/{selected_risk['id']}/decisions",
                        payload=payload,
                    )
                    st.session_state["decision_success"] = "Décision enregistrée dans l'historique."
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)

    if decision_history.get("items"):
        with st.expander("Voir l'historique des décisions"):
            st.dataframe(
                decision_history["items"],
                width="stretch",
                hide_index=True,
            )


def render_data_quality(analysis: dict) -> None:
    st.subheader("Peut-on faire confiance aux données ?")
    confidence = analysis["confidence_score"]
    evidence_coverage = analysis["evidence_coverage"]
    cards = st.columns(2)
    cards[0].metric("Confiance des données", f"{confidence:.0%}")
    cards[1].metric("Preuves disponibles", f"{evidence_coverage:.0%}")
    st.caption(
        "La confiance est une heuristique technique déterministe, pas une probabilité scientifique."
    )

    missing = analysis.get("missing_information", [])
    stale = analysis.get("stale_information", [])
    if not missing and not stale:
        st.success("Toutes les sources attendues sont disponibles et à jour.")
    if missing:
        st.warning("Certaines informations attendues sont absentes.")
        st.dataframe(missing, width="stretch", hide_index=True)
    if stale:
        st.warning("Certaines informations sont périmées.")
        st.dataframe(stale, width="stretch", hide_index=True)

    components = analysis.get("confidence_details", {}).get("components", {})
    if components:
        with st.expander("Comment la confiance est-elle calculée ?"):
            st.dataframe(
                [{"Composant": key, "Couverture": value} for key, value in components.items()],
                width="stretch",
                hide_index=True,
            )


st.set_page_config(page_title="Copilote QA", page_icon="🧭", layout="wide")
st.markdown(
    """
    <style>
    .block-container {max-width: 1280px; padding-top: 2rem;}
    div[data-testid="stMetric"] {
        background: color-mix(in srgb, var(--secondary-background-color) 82%, transparent);
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 0.75rem;
        padding: 0.8rem 1rem;
    }
    div[data-testid="stMetricLabel"] {font-weight: 600;}
    div[data-testid="stAlert"] {border-radius: 0.75rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Copilote QA")
st.caption("Une lecture simple des risques du projet, de leurs preuves et des décisions à prendre.")

decision_success = st.session_state.pop("decision_success", None)
if decision_success:
    st.success(decision_success)

try:
    projects = api_get("/projects")
except Exception as exc:
    show_api_error(exc, stop=True)

if not isinstance(projects, list):
    show_api_error(ValueError("GET /projects n'a pas retourné une liste"), stop=True)
if not projects:
    st.warning("Aucun projet chargé. Utilisez POST /ingest/demo dans la documentation API.")
    st.stop()

health = optional_get("/health") or {}
st.sidebar.header("Périmètre")
project_by_label = {f"{project['key']} — {project['name']}": project for project in projects}
project_label = st.sidebar.selectbox("Projet", list(project_by_label))
project = project_by_label[project_label]

try:
    sprints = api_get("/sprints", project_id=project["id"])
except Exception as exc:
    show_api_error(exc, stop=True)
sprint_by_label = {
    "Tous les sprints": None,
    **{sprint["name"]: sprint for sprint in sprints},
}
sprint_label = st.sidebar.selectbox("Sprint", list(sprint_by_label))
sprint = sprint_by_label[sprint_label]

params = {"project_id": project["id"]}
if sprint:
    params["sprint_id"] = sprint["id"]

st.sidebar.caption(
    "Choisissez le périmètre, puis lancez une analyse pour actualiser le diagnostic."
)
run_analysis = st.sidebar.button("Analyser maintenant", type="primary", use_container_width=True)
refresh = st.sidebar.button("Rafraîchir l'affichage", use_container_width=True)

with st.sidebar.expander("État du système"):
    api_healthy = health.get("status") == "healthy"
    st.write(f"API : **{'connectée' if api_healthy else 'état non vérifié'}**")
    st.caption(f"Adresse : {API_URL}")
    st.caption(f"Version : {health.get('version', '0.4.0')}")
    st.caption("Base de démonstration : SQLite")

try:
    overview = api_get("/overview", **params)
except Exception as exc:
    show_api_error(exc, stop=True)

analysis = None
if run_analysis:
    try:
        analysis = api_post("/risks/analyze", **params)
        st.success("Analyse QA actualisée.")
    except Exception as exc:
        show_api_error(exc)
elif refresh:
    st.rerun()

if analysis is None:
    analysis = optional_get("/risks", **params)

if not analysis:
    st.subheader(project["name"])
    render_project_health(overview)
    st.info(
        "Aucune analyse disponible. Cliquez sur « Analyser maintenant » dans la barre latérale."
    )
    st.stop()

findings = analysis.get("findings", [])
policies = sorted({item["rule_id"] for item in findings})
decisions_by_risk = {item["id"]: current_decision(item["id"]) for item in findings}

with st.sidebar.expander("Filtrer les risques"):
    severity_filter = st.selectbox(
        "Sévérité",
        ["Toutes", "critical", "high", "medium", "low"],
        format_func=lambda value: "Toutes" if value == "Toutes" else severity_label(value),
    )
    policy_filter = st.selectbox("Politique", ["Toutes", *policies])
    decision_filter = st.selectbox(
        "Décision humaine",
        ["Toutes", "pending", "accepted", "modified", "rejected"],
        format_func=lambda value: "Toutes" if value == "Toutes" else decision_label(value),
    )

visible_findings = [
    item
    for item in findings
    if (severity_filter == "Toutes" or item["severity"] == severity_filter)
    and (policy_filter == "Toutes" or item["rule_id"] == policy_filter)
    and (
        decision_filter == "Toutes"
        or decisions_by_risk[item["id"]]["current_status"] == decision_filter
    )
]
severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
contribution_by_policy = {
    item["policy_id"]: item["contribution"] for item in analysis.get("contributions", [])
}
visible_findings.sort(
    key=lambda item: (
        severity_rank.get(item["severity"], 99),
        -float(contribution_by_policy.get(item["rule_id"], 0)),
        str(item["detected_at"]),
    )
)

summary = optional_get(
    f"/projects/{project['id']}/risk-summary",
    **({"sprint_id": sprint["id"]} if sprint else {}),
)
delta = summary.get("delta", {}) if summary else {}
pending_count = (
    summary.get("pending_recommendation_count")
    if summary
    else sum(decision["current_status"] == "pending" for decision in decisions_by_risk.values())
)
scope_label = sprint["name"] if sprint else "Projet complet"

st.header(project["name"])
st.caption(f"{scope_label} · Analyse du {human_datetime(analysis['analyzed_at'])}")
show_global_status(analysis["severity"], analysis["finding_count"])

headline_cards = st.columns(4)
headline_cards[0].metric("Score de risque", f"{analysis['score']} / 100")
headline_cards[1].metric("Niveau", severity_label(analysis["severity"]))
headline_delta = delta.get("delta")
if headline_delta is None:
    headline_cards[2].metric("Évolution du risque", "Première analyse")
else:
    headline_direction = (
        "En hausse" if headline_delta > 0 else "En baisse" if headline_delta < 0 else "Stable"
    )
    headline_cards[2].metric(
        "Évolution du risque",
        headline_direction,
        f"{headline_delta:+.1f} point",
        delta_color="inverse",
    )
headline_cards[3].metric("Confiance des données", f"{analysis['confidence_score']:.0%}")
st.caption(
    "Plus le score est élevé, plus les contrôles QA demandent une attention immédiate. "
    "La confiance indique la qualité des données utilisées."
)

summary_tab, risks_tab, proof_history_tab, data_tab = st.tabs(
    [
        "Vue d'ensemble",
        "Risques et décisions",
        "Preuves et évolution",
        "Données détaillées",
    ]
)

with summary_tab:
    render_readiness(summary.get("decision_summary") if summary else None)

    st.divider()
    st.subheader("Où en est le projet ?")
    render_project_health(overview)

    st.divider()
    st.subheader("Qu'est-ce qui compose le score ?")
    contributions = analysis.get("contributions", [])
    policy_titles = {item["rule_id"]: item["title"] for item in findings}
    contribution_rows = [
        {
            "Facteur": policy_titles.get(item["policy_id"], item["factor"]),
            "Politique": item["policy_id"],
            "Valeur observée": item.get("raw_value"),
            "Signal": item["normalized_value"],
            "Poids maximal": item["weight"],
            "Contribution": item["contribution"],
            "Constats": item["finding_count"],
        }
        for item in contributions
    ]
    if contribution_rows:
        st.bar_chart(
            contribution_rows,
            x="Facteur",
            y="Contribution",
            horizontal=True,
        )
        displayed_total = round(
            sum(float(item["contribution"]) for item in contributions),
            1,
        )
        st.caption(
            f"Somme des contributions : {displayed_total} / 100 · "
            f"score calculé : {analysis['score']} / 100."
        )
        with st.expander("Voir le détail du calcul"):
            st.dataframe(contribution_rows, width="stretch", hide_index=True)
    else:
        st.success("Aucune politique n'ajoute de points au score.")

    st.divider()
    st.subheader("Repères utiles")
    context_cards = st.columns(4)
    context_cards[0].metric("Risques détectés", analysis["finding_count"])
    context_cards[1].metric("Politiques violées", len(policies))
    context_cards[2].metric("Décisions à valider", pending_count or 0)
    context_cards[3].metric("Preuves disponibles", f"{analysis['evidence_coverage']:.0%}")
    if analysis.get("missing_information") or analysis.get("stale_information"):
        st.warning(
            "Certaines données sont manquantes ou périmées. "
            "Le détail figure dans « Preuves et évolution »."
        )

with risks_tab:
    st.subheader("Que faut-il traiter ?")
    st.caption(
        "Les risques les plus sévères apparaissent en premier. "
        "Utilisez les filtres de la barre latérale pour réduire la liste."
    )
    if not visible_findings:
        st.info("Aucun risque ne correspond aux filtres sélectionnés.")
    else:
        st.dataframe(
            [
                {
                    "Risque": item["title"],
                    "Sévérité": severity_label(item["severity"]),
                    "Contribution": contribution_by_policy.get(item["rule_id"], 0),
                    "Source": f"{source_label(item['source_type'])} {item['source_id']}",
                    "Décision": decision_label(decisions_by_risk[item["id"]]["current_status"]),
                    "Recommandation": item["recommendation"],
                }
                for item in visible_findings
            ],
            width="stretch",
            hide_index=True,
        )

        risk_by_label = {
            f"{severity_label(item['severity'])} · {item['source_id']} · {item['title']}": item
            for item in visible_findings
        }
        selected_label = st.selectbox(
            "Risque à examiner",
            list(risk_by_label),
            key="risk_action_selection",
        )
        selected_risk = risk_by_label[selected_label]

        with st.container(border=True):
            st.markdown(f"### {selected_risk['title']}")
            st.write(selected_risk["description"])
            detail_columns = st.columns(4)
            detail_columns[0].metric(
                "Sévérité",
                severity_label(selected_risk["severity"]),
            )
            detail_columns[1].metric(
                "Contribution",
                contribution_by_policy.get(selected_risk["rule_id"], 0),
            )
            detail_columns[2].metric(
                "Source",
                f"{source_label(selected_risk['source_type'])} {selected_risk['source_id']}",
            )
            detail_columns[3].metric(
                "Statut",
                risk_status_label(selected_risk["status"]),
            )
            st.write(f"**Politique :** {selected_risk['rule_id']}")
            st.write(f"**Détecté le :** {human_datetime(selected_risk['detected_at'])}")
            st.info(f"**Recommandation proposée :** {selected_risk['recommendation']}")
            with st.expander("Voir les données observées"):
                st.json(selected_risk.get("evidence", {}))

        render_human_decision(
            selected_risk,
            decisions_by_risk[selected_risk["id"]],
        )

with proof_history_tab:
    evidence_tab, history_tab, quality_tab = st.tabs(
        ["Pourquoi ce risque ?", "Évolution du score", "Qualité des données"]
    )

    with evidence_tab:
        st.subheader("D'où vient ce constat ?")
        if not findings:
            st.info("Aucun risque ne nécessite une explication.")
        else:
            evidence_risk_by_label = {
                f"{severity_label(item['severity'])} · {item['source_id']} · {item['title']}": item
                for item in findings
            }
            evidence_label = st.selectbox(
                "Risque à expliquer",
                list(evidence_risk_by_label),
                key="evidence_selection",
            )
            evidence_risk = evidence_risk_by_label[evidence_label]
            explanation = optional_get(f"/risks/{evidence_risk['id']}/explanation")
            if not explanation:
                st.warning("L'explication de ce risque n'est pas disponible.")
            else:
                st.write(explanation["summary"])
                chain = explanation["evidence_chain"]
                nodes = ordered_evidence_nodes(chain.get("nodes", []))
                if nodes:
                    st.markdown("**Éléments vérifiés**")
                for node in nodes:
                    with st.container(border=True):
                        st.markdown(f"**{source_label(node['type'])} · {node['label']}**")
                        st.caption(
                            f"Identifiant : {node['source_id']} · "
                            f"Observé le : {human_datetime(node.get('observed_at'))}"
                        )
                        metadata = node.get("metadata", {})
                        details = " · ".join(
                            f"{key}: {value}"
                            for key, value in metadata.items()
                            if value is not None
                        )
                        if details:
                            st.write(details)

                relations = readable_evidence_edges(
                    chain.get("nodes", []),
                    chain.get("edges", []),
                )
                if relations:
                    st.markdown("**Comment ces éléments sont-ils reliés ?**")
                    for relation in relations:
                        st.write(f"- {relation}")
                if chain.get("missing_links"):
                    st.warning("La chaîne est partielle : certaines relations sont absentes.")
                    st.dataframe(
                        chain["missing_links"],
                        width="stretch",
                        hide_index=True,
                    )
                st.info(f"**Recommandation proposée :** {explanation['recommendation']}")
                with st.expander("Voir la réponse technique complète"):
                    st.json(explanation)

    with history_tab:
        st.subheader("Comment le risque évolue-t-il ?")
        history = optional_get(
            f"/projects/{project['id']}/risk-history",
            **({"sprint_id": sprint["id"]} if sprint else {}),
        )
        items = list(reversed(history.get("items", []))) if history else []
        if not items:
            st.info("Aucun historique disponible.")
        elif len(items) == 1:
            st.info("Il s'agit de la première analyse disponible.")
            st.dataframe(items, width="stretch", hide_index=True)
        else:
            st.line_chart(
                [
                    {
                        "Date": item["calculated_at"],
                        "Score": item["score"],
                        "Confiance": item["confidence_score"] * 100,
                    }
                    for item in items
                ],
                x="Date",
                y=["Score", "Confiance"],
            )

        if delta:
            delta_cards = st.columns(3)
            previous_score = delta.get("previous_score")
            delta_cards[0].metric(
                "Score précédent",
                "Non disponible" if previous_score is None else previous_score,
            )
            delta_cards[1].metric("Score actuel", delta.get("current_score"))
            delta_cards[2].metric("Évolution", delta_label(delta.get("delta")))
            changes = delta.get("changes", [])
            if changes:
                st.markdown("**Facteurs qui ont changé**")
                st.dataframe(changes, width="stretch", hide_index=True)

    with quality_tab:
        render_data_quality(analysis)

with data_tab:
    st.subheader("Données détaillées")
    st.caption(
        "Ces tables servent à vérifier les informations sources. "
        "Elles ne sont pas nécessaires pour la lecture quotidienne du diagnostic."
    )
    tickets_tab, metrics_tab, ingestion_tab = st.tabs(["Tickets", "Métriques", "Ingestion"])
    with tickets_tab:
        tickets = optional_get("/tickets", **params)
        if tickets is not None:
            st.dataframe(tickets, width="stretch", hide_index=True)
    with metrics_tab:
        metrics = optional_get("/metrics", **params)
        if metrics is not None:
            st.dataframe(metrics, width="stretch", hide_index=True)
    with ingestion_tab:
        logs = optional_get("/ingestions")
        if logs is not None:
            st.dataframe(logs, width="stretch", hide_index=True)
