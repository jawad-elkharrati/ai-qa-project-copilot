# AI QA Project Copilot

AI QA Project Copilot est un prototype d’aide à la décision pour le suivi de la qualité
logicielle. Il consolide des données de projet, applique des politiques QA explicites et produit
un score de risque accompagné des éléments qui ont contribué au résultat.

Le projet complète un outil de suivi comme Jira. Il ne remplace pas la gestion des tickets et
n’exécute aucune action externe automatiquement.

## Objectif

Les informations utiles à une décision de livraison sont souvent réparties entre les tickets, le
code, les Pull Requests, la CI/CD et les résultats de tests. Le projet rassemble ces signaux dans
un modèle commun afin de rendre le diagnostic QA vérifiable et de conserver la décision humaine.

## Fonctionnalités

- ingestion et normalisation de datasets JSON ou CSV ;
- import idempotent et journalisation des ingestions ;
- cinq politiques QA versionnées et validées avec Pydantic ;
- score de risque déterministe de 0 à 100 ;
- contribution détaillée de chaque politique au score ;
- chaîne de preuves entre tickets, Pull Requests, commits, builds et tests ;
- signalement des relations manquantes ;
- snapshots idempotents identifiés par empreinte SHA-256 ;
- historique et Risk Delta par facteur ;
- indicateurs de confiance, de complétude et de fraîcheur des données ;
- proposition de décision `GO`, `GO WITH CONDITIONS`, `NO-GO` ou
  `INSUFFICIENT INFORMATION` ;
- acceptation, modification ou rejet d’une recommandation par une personne ;
- API FastAPI documentée avec OpenAPI ;
- dashboard Streamlit ;
- migrations Alembic et tests automatiques.

## Fonctionnement

```text
Tickets, Git, CI/CD, tests et métriques
    → ingestion et normalisation
    → politiques QA
    → score et contributions
    → preuves et données manquantes
    → snapshot et évolution
    → décision proposée
    → validation humaine
```

La version actuelle utilise le dataset fictif NovaShop. Les connecteurs Jira et GitHub réels ne
sont pas encore disponibles.

## Architecture du dépôt

```text
app/         API, modèles, ingestion et services QA
dashboard/   interface Streamlit
alembic/     migrations de la base de données
policies/    politiques QA JSON versionnées
data/        dataset fictif NovaShop
tests/       tests unitaires et d’intégration
.github/     intégration continue
```

Le moteur QA est déterministe. Il n’utilise pas de LLM dans cette version.

## Démarrage rapide

Prérequis : Python 3.11 ou une version plus récente.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dans un second terminal :

```powershell
.\.venv\Scripts\Activate.ps1
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/ingest/demo?reset=true"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/risks/analyze?project_id=PRJ-COPILOTE"
streamlit run dashboard/app.py
```

Adresses utiles :

- API : `http://127.0.0.1:8000` ;
- documentation OpenAPI : `http://127.0.0.1:8000/docs` ;
- dashboard : `http://127.0.0.1:8501`.

La démonstration locale validée utilise SQLite. PostgreSQL reste une cible prévue, mais son
exécution n’a pas été validée pour cette version publique.

## API

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/health` | vérifier l’API et la base |
| `POST` | `/ingest/demo` | charger NovaShop |
| `GET` | `/overview` | consulter les indicateurs du projet |
| `POST` | `/risks/analyze` | exécuter l’analyse QA |
| `GET` | `/risks` | consulter le dernier snapshot |
| `GET` | `/risks/{risk_id}` | consulter un risque |
| `GET` | `/risks/{risk_id}/explanation` | consulter ses preuves |
| `POST` | `/risks/{risk_id}/decisions` | enregistrer une décision humaine |
| `GET` | `/projects/{project_id}/risk-summary` | consulter la synthèse et la décision proposée |
| `GET` | `/projects/{project_id}/risk-history` | consulter l’historique |

## Tests

```powershell
ruff check .
ruff format --check .
pytest
```

La suite vérifie notamment les politiques, le score, les contributions, les snapshots,
l’idempotence, les deltas, les preuves, la confiance, les décisions humaines, les migrations,
l’API et le dashboard.

## Données de démonstration

NovaShop est entièrement fictif. Le dataset contient trois scénarios de sprint et des relations
entre tickets, commits, Pull Requests, builds, tests et métriques. Il ne contient aucune donnée de
SII, d’un client ou d’un dépôt réel.

## Limites actuelles

- les sources Jira, GitHub et CI/CD sont simulées par le dataset ;
- aucun connecteur externe réel n’est actif ;
- aucun RAG ni système multi-agents n’est intégré ;
- aucune prédiction Machine Learning n’est réalisée ;
- PostgreSQL et Docker ne sont pas validés dans cette livraison ;
- les recommandations ne déclenchent aucune action externe.

## Prochaines étapes

- ajouter des connecteurs externes en lecture seule ;
- renforcer la documentation des politiques ;
- valider PostgreSQL dans un environnement dédié ;
- préparer les fonctions multi-agents sur le socle QA existant.

## Auteur

Jawad Elkharrati
