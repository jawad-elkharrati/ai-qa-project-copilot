# Guide de démonstration — Semaine 4 P0 + P1-A

## Préparation Docker

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Attendre que `api` et `dashboard` soient `healthy`, puis ouvrir :

- Swagger : http://localhost:8000/docs
- Dashboard : http://localhost:8501
- Health API : http://localhost:8000/health

## Charger NovaShop

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/ingest/demo?reset=false"
Invoke-RestMethod -Method Post "http://localhost:8000/risks/analyze?project_id=PRJ-COPILOTE"
```

Le dataset crée un historique déterministe d'au moins sept jours. L'analyse produit un snapshot explicable, synchronise les recommandations actives et ne déclenche aucune action externe.

## Parcours de démonstration

1. **Synthèse** — montrer score, niveau, delta, confiance, couverture des preuves et décision suggérée.
2. **Risques** — montrer les contributions, politiques, preuves et informations manquantes.
3. **Décision** — ouvrir le Decision Brief, lire les bloqueurs, conditions et règles déclenchées.
4. **Recommandations** — filtrer, puis accepter, modifier ou rejeter une recommandation avec acteur, rôle et justification.
5. **Rapports** — sélectionner le 20 juillet 2026 pour le quotidien et la période du 14 au 20 juillet 2026 pour l'hebdomadaire.
6. **Évolution** — montrer les sept snapshots, les risques apparus/résolus/aggravés et la tendance.

## Appels API reproductibles

```powershell
Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/risk-summary"
Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/decision-brief"
Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/recommendations"
Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/reports/daily?report_date=2026-07-20"
Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/reports/weekly?period_start=2026-07-14&period_end=2026-07-20"
Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/risk-history"
```

## Vérifier la persistance

```powershell
docker compose down
docker compose up -d
docker compose ps
Invoke-RestMethod "http://localhost:8000/projects"
docker compose exec api alembic current
```

Ne pas utiliser `docker compose down -v` si la base doit être conservée.

## Vérifier l'absence d'action externe

```powershell
docker compose exec api python -c "import sqlite3; c=sqlite3.connect('/data/copilote_qa.db'); print(c.execute('select count(*) from recommendation_transitions where external_action_executed=1').fetchone()[0]); print(c.execute('select count(*) from qa_decision_reviews where external_action_executed=1').fetchone()[0])"
```

Les deux valeurs attendues sont `0`.

## Arrêt

```powershell
docker compose down
```
## Parcours P1-A

1. Dans Recommandations, accepter ou modifier une proposition avec acteur, rôle et justification.
2. Sélectionner cette recommandation, renseigner éventuellement responsable et date limite, puis
   utiliser Passer en cours.
3. Clôturer avec un commentaire obligatoire via Marquer comme terminée.
4. Consulter Efficacité observée. Si aucun snapshot ultérieur n’existe, le statut attendu est
   Résultat non encore mesurable ; aucune causalité n’est affirmée.
5. Dans Rapports, cliquer Préparer les exports, puis télécharger le Markdown ou le HTML.

### Appels API P1-A

~~~powershell
$recommendations = Invoke-RestMethod "http://localhost:8000/projects/PRJ-COPILOTE/recommendations"
$recommendationId = $recommendations[0].id
Invoke-RestMethod "http://localhost:8000/recommendations/$recommendationId/outcome"
Invoke-WebRequest "http://localhost:8000/projects/PRJ-COPILOTE/reports/daily/export?report_date=2026-07-20&format=markdown" -OutFile rapport-quotidien.md
Invoke-WebRequest "http://localhost:8000/projects/PRJ-COPILOTE/reports/weekly/export?period_start=2026-07-14&period_end=2026-07-20&format=html" -OutFile rapport-hebdomadaire.html
~~~

Les transitions start et complete exigent un corps JSON humain. Elles sont plus simplement
démontrées depuis le dashboard ou Swagger. Aucune action externe n’est déclenchée.