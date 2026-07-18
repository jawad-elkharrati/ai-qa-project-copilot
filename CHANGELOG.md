# Changelog

Les changements importants du projet sont documentés dans ce fichier.

## 0.2.0

- ajout de l'import JSON et CSV ;
- validation et normalisation des données ;
- ingestion idempotente avec journal persistant ;
- ajout des routes de consultation des projets, sprints, tickets et métriques ;
- calcul de cinq indicateurs déterministes ;
- ajout du dashboard Streamlit et de ses filtres ;
- ajout des tests d'ingestion, d'API et de dashboard.

## 0.1.0

- création du modèle de données relationnel ;
- ajout du dataset fictif NovaShop ;
- configuration SQLAlchemy, Alembic, SQLite et PostgreSQL ;
- ajout des routes de base et du contrôle de santé ;
- ajout du seed idempotent, des tests, de Ruff et de GitHub Actions.
