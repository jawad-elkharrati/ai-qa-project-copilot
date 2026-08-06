# ADR-004 — MVP de décision QA, recommandations et rapports

- Statut : accepté pour la semaine 4 P0
- Date : 2026-07-31
- Portée : décision QA déterministe, recommandations gouvernées, rapports, dashboard et Docker

## Contexte

La semaine 3 fournit des snapshots de risque explicables, des contributions, des preuves, un niveau de confiance et `RiskDecision`. La semaine 4 doit transformer ces analyses en support de décision utilisable sans introduire de LLM, RAG, LangGraph, connecteur réel ou action externe.

## Décisions

### Décision QA

`DecisionEngine` reste indépendant de FastAPI et de Streamlit. Il produit exactement une suggestion parmi `GO`, `GO_WITH_CONDITIONS`, `NO_GO` et `INSUFFICIENT_INFORMATION`, avec règles déclenchées, bloqueurs, conditions et justification déterministes. La validation humaine demeure obligatoire. `QADecisionReview` conserve l'état de revue associé au snapshot.

### Recommandations et compatibilité S3

`Recommendation` représente un épisode persistant d'un risque stable. Un risque encore actif sur un snapshot suivant réutilise la recommandation active et met à jour `last_seen_snapshot_id`. Une nouvelle recommandation n'est créée qu'à la première apparition ou après résolution puis réapparition.

`RecommendationTransition` est un journal append-only distinct. Il conserve proposition originale, valeur finale éventuelle, acteur, rôle, commentaire, justification, snapshot et `external_action_executed=false`. `RiskDecision` reste intact comme couche de compatibilité semaine 3 ; aucun backfill ambigu ne lui attribue artificiellement une recommandation S4.

### Rapports

Les rapports quotidien et hebdomadaire sont construits à partir des snapshots et services métier communs. Le quotidien décrit un état et son delta. L'hebdomadaire agrège plusieurs snapshots, contributions, risques et revues ; il n'est pas une copie du quotidien. Les réponses JSON sont calculées à la demande pour éviter de dupliquer les snapshots. Aucun LLM ne génère leur contenu.

### Mesure d'efficacité

`RecommendationOutcome` compare des observations avant/après. Le résultat est formulé comme amélioration observée, absence d'amélioration, données insuffisantes ou résultat non encore mesurable. Aucune causalité n'est affirmée.

### Dashboard

Streamlit consomme exclusivement l'API. Les six vues P0 sont synthèse, risques, décision, recommandations, rapports et évolution. Aucune règle de score, priorité ou décision n'est dupliquée dans l'interface.

### Exécution Docker

Une image commune exécute FastAPI et Streamlit sous UID/GID 10001. L'API applique `alembic upgrade head` avant Uvicorn. SQLite réside dans un volume nommé. Le dashboard attend une API healthy. Les systèmes externes restent en lecture seule et aucune action externe n'est exécutée.

## Conséquences

- les décisions et priorités sont explicables et testables ;
- l'historique humain est append-only et distinct de la compatibilité S3 ;
- les rapports réutilisent les snapshots sans duplication métier ;
- le MVP démarre avec `docker compose up --build` ;
- SQLite est le backend P0 validé ; PostgreSQL, PDF, connecteurs réels, RAG et LangGraph restent hors P0.