# Copilote IA pour le QA

MVP de suivi de projet IT qui transforme des données de projet en risques QA, décisions
explicables, recommandations priorisées et rapports de pilotage. Jira suit le travail ; ce
copilote ajoute une couche de décision QA mesurable, traçable et gouvernée par l’humain.

Le moteur est déterministe : il n’utilise pas de LLM pour calculer un score ou prendre une
décision. Les données NovaShop sont fictives et aucune action n’est exécutée sur un système
externe.

## Fonctionnalités

- ingestion JSON/CSV validée et idempotente ;
- cinq politiques QA versionnées dans `policies/qa-rules-v1.0.json` ;
- score de risque de 0 à 100 avec contributions détaillées ;
- preuves, données manquantes, fraîcheur et confiance ;
- snapshots idempotents, historique et Risk Delta ;
- Decision Brief avec `GO`, `GO_WITH_CONDITIONS`, `NO_GO` ou
  `INSUFFICIENT_INFORMATION` ;
- recommandations persistantes, priorisées et soumises à validation humaine ;
- historique append-only des acceptations, modifications et rejets ;
- suivi `IN_PROGRESS` et `COMPLETED`, avec évolution observée avant/après ;
- rapports quotidiens et hebdomadaires, exportables en Markdown ou HTML ;
- API FastAPI, dashboard Streamlit et exécution Docker avec SQLite persistant.

## Architecture

```text
app/         API FastAPI et services métier
dashboard/   interface Streamlit consommant uniquement l’API
alembic/     migrations de la base SQLite
policies/    politiques QA en JSON
data/        dataset fictif NovaShop
tests/       tests unitaires et d’intégration
docs/        cadrage, ADR, diagrammes et guide de démonstration
tools/       génération et conversion du dataset
```

La logique métier reste hors des routes FastAPI et du dashboard. Les décisions, scores,
priorités et rapports sont construits par des services testables dans `app/`.

## Démarrage rapide avec Docker

Prérequis : Docker Desktop démarré.

Dans PowerShell :

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Dans l’invite de commandes Windows (`cmd`) :

```bat
copy .env.example .env
docker compose up --build -d
docker compose ps
```

Accès :

- API : <http://localhost:8000> ;
- Swagger : <http://localhost:8000/docs> ;
- dashboard : <http://localhost:8501>.

La base SQLite est créée et migrée automatiquement. Charger les données NovaShop :

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/ingest/demo"
```

Pour arrêter sans perdre les données :

```powershell
docker compose down
```

Ne pas ajouter `-v` si le volume SQLite doit être conservé.

## Persistance et diagnostic Docker

Après un arrêt, redémarrer les conteneurs sans reconstruire l’image :

```powershell
docker compose up -d
```

Vérifier la migration active dans le conteneur API :

```powershell
docker compose exec api alembic current
```

Variables principales :

| Variable | Rôle |
|---|---|
| `DATABASE_URL` | chemin de la base SQLite persistante |
| `DASHBOARD_API_URL` | URL interne de l’API utilisée par Streamlit |
| `API_PORT` | port HTTP de FastAPI |
| `DASHBOARD_PORT` | port HTTP de Streamlit |

Les valeurs de développement sont documentées dans `.env.example`. Aucun secret n’est requis
pour le profil SQLite.
## Démarrage local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:DATABASE_URL="sqlite+pysqlite:///./copilote_qa.db"
alembic upgrade head
uvicorn app.main:app --reload
```

Dans un second terminal :

```powershell
.\.venv\Scripts\Activate.ps1
$env:API_URL="http://127.0.0.1:8000"
streamlit run dashboard/app.py
```

## Politiques QA

| Politique | Condition principale |
|---|---|
| `QA-BLOCKED-LONG` | ticket bloqué depuis plus de 72 heures |
| `QA-TICKET-OVERDUE` | échéance dépassée et ticket non terminé |
| `QA-CRITICAL-BUG-OPEN` | bug critique encore ouvert |
| `QA-PIPELINE-FAILED` | dernier build en échec |
| `QA-COVERAGE-LOW` | couverture de tests inférieure à 70 % |

Le score additionne les contributions `poids × signal normalisé`, puis borne le résultat entre
0 et 100. La confiance mesure la qualité des données : présence des sources, fraîcheur et qualité
des relations. Elle ne représente pas une probabilité d’incident.

## API principale

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/health` | vérifier l’API et la base |
| POST | `/ingest/demo` | charger les données NovaShop |
| POST | `/risks/analyze` | lancer une analyse QA |
| GET | `/projects/{project_id}/risk-summary` | consulter score, confiance et delta |
| GET | `/projects/{project_id}/decision-brief` | consulter la décision suggérée |
| GET | `/projects/{project_id}/recommendations` | filtrer les recommandations |
| POST | `/recommendations/{id}/accept` | accepter une recommandation |
| POST | `/recommendations/{id}/modify` | modifier une recommandation |
| POST | `/recommendations/{id}/reject` | rejeter une recommandation |
| POST | `/recommendations/{id}/start` | démarrer une recommandation validée |
| POST | `/recommendations/{id}/complete` | marquer une recommandation terminée |
| GET | `/recommendations/{id}/outcome` | observer l’évolution avant/après |
| GET | `/projects/{project_id}/reports/daily` | construire le rapport quotidien |
| GET | `/projects/{project_id}/reports/weekly` | construire le rapport hebdomadaire |

La documentation exhaustive et les schémas de réponse sont disponibles dans Swagger.

## Qualité

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
alembic heads
```

GitHub Actions exécute automatiquement Ruff et les tests à chaque push et Pull Request.

## Garde-fous

- décision finale humaine ;
- `external_action_executed=false` ;
- aucune écriture vers Jira, GitHub ou un pipeline externe ;
- aucune relation artificielle entre les décisions historiques et les recommandations ;
- aucune causalité attribuée à une amélioration seulement observée après une recommandation.

Le scénario complet est décrit dans
[`docs/guide-demonstration-semaine4.md`](docs/guide-demonstration-semaine4.md). Les choix
d’architecture sont documentés dans [`docs/adr/`](docs/adr/).