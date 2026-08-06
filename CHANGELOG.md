# Changelog

## v0.4-week4-p0 — 2026-07-31

- moteur de décision QA déterministe avec quatre issues, justifications, bloqueurs et conditions ;
- Decision Brief lié aux snapshots et soumis à validation humaine ;
- recommandations persistantes par épisode avec clé stable, priorité expliquée et réutilisation tant que le risque persiste ;
- `RecommendationTransition` append-only, séparé de `RiskDecision` conservé pour la compatibilité S3 ;
- acceptation, modification et rejet avec proposition originale, acteur, rôle, commentaire et justification ;
- rapports quotidiens et hebdomadaires déterministes fondés sur sept jours de snapshots NovaShop ;
- mesure d'évolution avant/après sans affirmation causale ;
- dashboard Streamlit à six vues consommant exclusivement l'API ;
- endpoints P0 typés pour décisions, recommandations, historique et rapports ;
- migrations Alembic `0007` et `0008`, compatibles SQLite et sans liaison S3 artificielle ;
- image Docker commune non-root, migrations automatiques, healthchecks et volume SQLite persistant ;
- 142 tests réussis et couverture backend finale de 90,73 %.
## v0.4-explainable-risk-history — 2026-07-23

- politiques QA externalisées dans un fichier JSON versionné, validé par Pydantic et limité à
  des métriques et opérateurs autorisés ;
- contributions de score persistées avec valeur brute, signal normalisé, poids, source et
  explication ;
- snapshots immuables identifiés par empreinte des entrées, sans duplication d'un calcul
  identique ;
- historique et delta déterministes, y compris les facteurs ajoutés, retirés, augmentés ou
  diminués ;
- chaînes de preuves lisibles reliant risque, ticket, pull request, commit, build, tests et
  métrique selon les données disponibles ;
- indicateurs explicites de confiance, couverture des preuves, données manquantes et données
  périmées ;
- endpoints de détail, d'explication, de synthèse et d'historique des risques ;
- dashboard enrichi avec confiance, delta, informations manquantes et composition du score ;
- deux migrations Alembic pour les snapshots, contributions et preuves ;
- tests de politiques, score, idempotence, historique, migrations, confiance et traçabilité.

## v0.3-qa-engine — 2026-07-18

- cinq règles QA déterministes et versionnées pour blocages, retards, bugs critiques, CI et couverture ;
- score de risque 0-100 avec signaux normalisés, pondérations et détail des contributions ;
- Agent QA simple, sans LLM, recevant un projet ou un sprint et produisant constats et priorités ;
- analyses persistantes et idempotentes, preuves structurées et actions soumises à validation humaine ;
- endpoints `POST /risks/analyze` et `GET /risks` avec filtre de sévérité ;
- vue risques du dashboard avec score, preuve et recommandation ;
- migration Alembic des analyses et champs d'explicabilité ;
- tests unitaires des cinq règles et intégration des trois scénarios de référence ;
- documentation et démonstration de la semaine 3.

## v0.2-ingestion-dashboard — 2026-07-14

- import du dataset NovaShop aux formats JSON et CSV ;
- envoi d'un fichier CSV choisi par l'utilisateur via `POST /ingest/csv` ;
- validation Pydantic, normalisation et messages d'erreur contrôlés ;
- ingestion idempotente et journal persistant des succès, échecs et imports ignorés ;
- migration Alembic du journal d'ingestion ;
- endpoints projets, sprints, synthèse, tickets, métriques et historique ;
- cinq KPI déterministes pour la vue projet ;
- dashboard Streamlit avec filtres projet et sprint ;
- tests d'ingestion valide/invalide et tests des endpoints métier ;
- test automatique du dashboard, de ses filtres et de ses cinq KPI ;
- documentation et démonstration de la semaine 2.

## v0.1-foundation — 2026-07-13

- cadrage des trois scénarios et des trois personas ;
- backlog priorisé de dix user stories ;
- diagrammes de contexte et de données ;
- dataset de démonstration v0.1 et dictionnaire ;
- modèles SQLAlchemy des dix entités et migration Alembic initiale ;
- API FastAPI avec `/` et `/health` ;
- seed idempotent et outil d'inspection ;
- configuration PostgreSQL et profil SQLite de secours ;
- tests, couverture, lint et workflow GitHub Actions ;
- README et script de démonstration.
