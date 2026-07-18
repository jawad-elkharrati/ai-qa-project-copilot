# AI QA Project Copilot

Application de suivi qualité pour les projets informatiques. Elle centralise des données de
projet, calcule des indicateurs simples et présente une vue synthétique dans un dashboard.

Le projet fournit actuellement une base technique complète pour l'ingestion et la consultation
des données. Les indicateurs sont calculés par des règles Python déterministes : aucun modèle de
langage ni agent d'intelligence artificielle n'est encore actif.

## Fonctionnalités disponibles

- import d'un dataset JSON ou CSV ;
- validation et normalisation des données ;
- import idempotent, sans création de doublons ;
- journalisation des imports réussis, échoués ou ignorés ;
- API FastAPI documentée avec OpenAPI ;
- consultation des projets, sprints, tickets et métriques ;
- calcul de cinq indicateurs : progression, blocages, retards, builds échoués et couverture ;
- dashboard Streamlit avec filtres par projet et sprint ;
- migrations de base de données avec Alembic ;
- tests automatiques avec Pytest et contrôle du code avec Ruff ;
- pipeline d'intégration continue avec GitHub Actions.

## Architecture

```text
JSON ou CSV
    → validation et normalisation
    → stockage SQLite ou PostgreSQL
    → API FastAPI
    → calcul des indicateurs
    → dashboard Streamlit
```

Les dossiers principaux sont :

```text
app/         API, modèles, validation, ingestion et calcul des indicateurs
alembic/     migrations de la base de données
dashboard/   interface Streamlit
data/        dataset fictif NovaShop et dictionnaire des données
docs/        cadrage, backlog et décisions d'architecture
tests/       tests automatiques
tools/       outils de création et de conversion du dataset
```

## Prérequis

- Python 3.11 ou une version plus récente ;
- PowerShell sous Windows ;
- Docker Desktop uniquement si PostgreSQL est utilisé.

## Installation sous Windows PowerShell

Depuis la racine du projet :

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Démarrage rapide avec SQLite

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///./copilote_qa.db"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Dans un deuxième terminal :

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run dashboard/app.py
```

Ouvrir ensuite :

- documentation de l'API : `http://127.0.0.1:8000/docs` ;
- état de l'API : `http://127.0.0.1:8000/health` ;
- dashboard : `http://127.0.0.1:8501`.

## Routes principales

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Informations générales du service |
| GET | `/health` | Vérification de l'accès à la base de données |
| POST | `/ingest/demo` | Import du dataset de démonstration |
| POST | `/ingest` | Import d'un objet JSON |
| POST | `/ingest/csv` | Import d'un fichier CSV envoyé par l'utilisateur |
| GET | `/projects` | Liste des projets |
| GET | `/sprints` | Liste des sprints d'un projet |
| GET | `/overview` | Synthèse et indicateurs d'un projet ou sprint |
| GET | `/tickets` | Liste filtrable des tickets |
| GET | `/metrics` | Liste filtrable des métriques |
| GET | `/ingestions` | Historique des imports |

Le fichier CSV doit être encodé en UTF-8, contenir les colonnes `entity` et `payload`, et ne pas
dépasser 5 Mo.

## Vérification de la qualité

```powershell
ruff check .
pytest
python -m app.inspect_dataset --dataset data/demo_dataset_v0.1.json
```

GitHub Actions exécute automatiquement Ruff et Pytest à chaque envoi de code et à chaque pull
request.

## PostgreSQL avec Docker

```powershell
Copy-Item .env.example .env
docker compose -f compose.db.yml up -d
alembic upgrade head
```

Pour arrêter PostgreSQL :

```powershell
docker compose -f compose.db.yml down
```

SQLite est adapté à une démonstration locale rapide. PostgreSQL est la base cible pour un usage
plus proche d'un environnement professionnel.

## Limites actuelles

- le score de risque et le moteur de règles QA ne sont pas encore disponibles ;
- aucun LLM, RAG ou système multi-agents n'est implémenté ;
- le dashboard affiche des indicateurs déterministes, pas des décisions intelligentes ;
- les recommandations et rapports automatiques restent à développer ;
- toute décision opérationnelle doit rester sous validation humaine.

## Données de démonstration

NovaShop est un projet fictif utilisé pour tester l'application sans publier de données
confidentielles. Le dataset contient un projet, trois sprints, cinquante tickets et des éléments
liés comme les commits, pull requests, builds, résultats de test et métriques.
