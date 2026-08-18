# ADR-001 — Architecture de fondation

- Statut : accepté pour v0.1, à revoir après le MVP
- Date : 2026-07-13
- Décideur technique : équipe PFA ; validation encadrant attendue

## Contexte

Le produit doit devenir démontrable en quatre semaines tout en préparant RAG, multi-agents et
industrialisation. Il faut éviter qu'une dépendance LLM ou une donnée interne bloque le MVP.

## Décision

1. **Monolithe modulaire Python/FastAPI** pour réduire le coût d'intégration pendant huit semaines.
2. **PostgreSQL comme stockage cible** pour les données structurées et leurs relations.
3. **SQLite comme profil local de secours** pour tests et première prise en main sans Docker.
4. **SQLAlchemy + Alembic** pour séparer le modèle Python des migrations versionnées.
5. **Dataset JSON fictif et figé** avec date de référence, identifiants stables et anomalies
   documentées.
6. **Règles déterministes avant LLM** : l'intelligence de S3 reste explicable et testable.
7. **Interfaces futures séparées** pour GitHub, LLM et vector store afin de conserver un mode mock.

## Conséquences positives

- démarrage rapide et OpenAPI automatique ;
- reproductibilité sans accès SII ;
- preuves relationnelles faciles à requêter ;
- migration progressive vers le dashboard, le RAG et LangGraph ;
- tests rapides sur SQLite et comportement cible vérifiable sur PostgreSQL en CI future.

## Compromis

- SQLite ne reproduit pas toutes les particularités PostgreSQL ; les migrations devront aussi être
  testées sur PostgreSQL à partir de S2/S7 ;
- un monolithe convient au PFA mais n'est pas une décision de microservices pour la production ;
- les seuils QA initiaux sont des hypothèses à faire valider.

## Alternatives écartées

- React/Next.js en S1 : coût trop élevé avant validation du parcours ;
- microservices : complexité opérationnelle sans valeur démontrée à ce stade ;
- MongoDB : modèle fortement relationnel et besoin de traçabilité ;
- agents/LLM dès S1 : résultats moins contrôlables avant création du référentiel de test.
