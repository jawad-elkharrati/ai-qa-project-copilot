import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")


def api_get(path: str, **params):
    response = httpx.get(f"{API_URL}{path}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Copilote IA QA", page_icon="🧭", layout="wide")
st.title("Copilote IA QA — Dashboard V0")
st.caption("Vue unifiée et indicateurs déterministes, sans intelligence artificielle active.")

try:
    projects = api_get("/projects")
except (httpx.HTTPError, ValueError) as exc:
    st.error(f"API indisponible sur {API_URL}. Démarrez FastAPI avant le dashboard. ({exc})")
    st.stop()

if not projects:
    st.warning("Aucun projet chargé. Appelez POST /ingest/demo dans la documentation API.")
    st.stop()

project_by_label = {f"{project['key']} — {project['name']}": project for project in projects}
project_label = st.sidebar.selectbox("Projet", list(project_by_label))
project = project_by_label[project_label]
sprints = api_get("/sprints", project_id=project["id"])
sprint_by_label = {"Tous les sprints": None, **{sprint["name"]: sprint for sprint in sprints}}
sprint_label = st.sidebar.selectbox("Sprint", list(sprint_by_label))
sprint = sprint_by_label[sprint_label]
params = {"project_id": project["id"]}
if sprint:
    params["sprint_id"] = sprint["id"]

overview = api_get("/overview", **params)
cards = st.columns(5)
cards[0].metric("Progression", f"{overview['progress_percent']} %")
cards[1].metric("Tickets bloqués", overview["blocked_tickets"])
cards[2].metric("Tickets en retard", overview["overdue_tickets"])
cards[3].metric("Builds échoués", overview["failed_builds"])
coverage = overview["test_coverage"]
cards[4].metric("Couverture", "N/A" if coverage is None else f"{coverage} %")

st.caption(f"Date de référence des KPI : {overview['as_of']}")
tickets_tab, metrics_tab, ingestion_tab = st.tabs(["Tickets", "Métriques", "Ingestion"])
with tickets_tab:
    tickets = api_get("/tickets", **params)
    st.dataframe(tickets, width="stretch", hide_index=True)
with metrics_tab:
    metrics = api_get("/metrics", **params)
    st.dataframe(metrics, width="stretch", hide_index=True)
with ingestion_tab:
    logs = api_get("/ingestions")
    st.dataframe(logs, width="stretch", hide_index=True)
