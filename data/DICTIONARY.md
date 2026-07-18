# Dictionnaire des données — dataset v0.1

## Conventions globales

- Encodage : UTF-8 ; format principal : JSON.
- Identifiants : chaînes stables préfixées (`PRJ-`, `SPR-`, `TKT-`, etc.).
- Dates : `YYYY-MM-DD` ; horodatages : ISO 8601 en UTC (`Z`).
- Date de référence : `2026-07-13`, utilisée pour rendre les règles temporelles reproductibles.
- Valeurs absentes : `null`, jamais chaîne vide.
- Données : 100 % fictives ; noms de personnes, projet et dépôt ne désignent pas des actifs SII.

## Enveloppe du dataset

| Champ | Type | Obligatoire | Description |
|---|---|---:|---|
| `version` | string | oui | Version sémantique du dataset (`0.1`) |
| `generated_at` | datetime | oui | Date de génération figée |
| `reference_date` | date | oui | Date utilisée pour retard et durée de blocage |
| `project` | object | oui | Projet unique de la version 0.1 |
| `sprints` | array | oui | Trois scénarios de référence |
| `tickets` | array | oui | Cinquante tickets |
| `commits` | array | oui | Commits liés à des tickets |
| `pull_requests` | array | oui | PR liées à des tickets |
| `builds` | array | oui | Exécutions CI liées aux PR/sprints |
| `test_results` | array | oui | Résultats agrégés par build |
| `metrics` | array | oui | Couverture, code smells et densité de défauts |
| `risks` | array | oui | Vide actuellement, réservé au futur moteur QA |
| `reports` | array | oui | Vide actuellement, réservé au futur module de synthèse |
| `expected_anomalies` | array | oui | Oracle de test : anomalies volontairement injectées |

## Project

| Champ | Type | Règle |
|---|---|---|
| `id` | string | clé primaire stable |
| `key` | string | code court unique du projet |
| `name` | string | nom affiché |
| `description` | text | contexte fonctionnel |
| `repository_url` | string/null | URL fictive ou connecteur autorisé |
| `created_at` | datetime | création du projet |

## Sprint

| Champ | Type | Règle |
|---|---|---|
| `id` | string | clé primaire |
| `project_id` | string | FK vers Project |
| `name` | string | nom incluant le scénario de référence |
| `goal` | text | objectif du sprint |
| `start_date`, `end_date` | date | intervalle inclusif |
| `status` | enum | `planned`, `active`, `completed` |
| `capacity_points` | integer | capacité >= 0 |
| `created_at` | datetime | création du sprint |

## Ticket

| Champ | Type | Règle |
|---|---|---|
| `id` | string | clé primaire et preuve affichable |
| `project_id` | string | FK obligatoire |
| `sprint_id` | string/null | FK ; null pour backlog non planifié |
| `title`, `description` | string/text | contenu fictif du ticket |
| `type` | enum | `story`, `task`, `bug` |
| `status` | enum | `todo`, `in_progress`, `review`, `blocked`, `done` |
| `priority` | enum | `low`, `medium`, `high`, `critical` |
| `assignee` | string/null | personne fictive |
| `story_points` | integer | estimation >= 0 |
| `created_at`, `updated_at` | datetime | cycle de vie |
| `due_date` | date/null | échéance métier |
| `blocked_since` | datetime/null | présent uniquement si blocage connu |
| `closed_at` | datetime/null | présent si terminé |
| `labels` | array[string] | catégories et marqueurs de scénario |

## Commit

| Champ | Type | Règle |
|---|---|---|
| `id` | string | clé primaire interne |
| `project_id` | string | FK obligatoire |
| `ticket_id` | string/null | ticket référencé par le message |
| `sha` | string | empreinte SHA-1 unique de démonstration |
| `author` | string | auteur fictif |
| `message` | string | message traçable vers le ticket |
| `committed_at` | datetime | date du commit |
| `additions`, `deletions` | integer | volumes >= 0 |

## PullRequest

| Champ | Type | Règle |
|---|---|---|
| `id`, `project_id`, `ticket_id` | string | identifiants et relations |
| `number` | integer | numéro positif dans le dépôt |
| `title`, `author` | string | métadonnées de revue |
| `status` | enum | `open`, `merged`, `closed` |
| `source_branch`, `target_branch` | string | branches Git |
| `created_at`, `merged_at` | datetime/null | cycle de vie |
| `review_count` | integer | nombre de revues >= 0 |
| `changed_files` | integer | fichiers changés >= 0 |

## Build

| Champ | Type | Règle |
|---|---|---|
| `id`, `project_id` | string | identifiants |
| `sprint_id`, `pull_request_id` | string/null | contexte fonctionnel et déclencheur |
| `pipeline_name`, `branch`, `commit_sha` | string | preuve CI |
| `status` | enum | `queued`, `running`, `success`, `failed`, `cancelled` |
| `started_at`, `finished_at` | datetime/null | intervalle d'exécution |
| `duration_seconds` | integer/null | durée >= 0 |

## TestResult

| Champ | Type | Règle |
|---|---|---|
| `id`, `project_id`, `build_id` | string | résultat lié à un build existant |
| `suite_name` | string | suite exécutée |
| `status` | enum | `passed`, `failed` |
| `total`, `passed`, `failed`, `skipped` | integer | somme des trois résultats = total |
| `duration_seconds` | float | durée >= 0 |
| `executed_at` | datetime | fin de la suite |

## Metric

| Champ | Type | Règle |
|---|---|---|
| `id`, `project_id`, `sprint_id` | string | identifiants et contexte |
| `name` | enum ouvert | `test_coverage`, `code_smells`, `defect_density` en v0.1 |
| `value` | float | valeur brute, non transformée |
| `unit` | string | `percent`, `count`, `per_kloc` |
| `source` | string | adaptateur ayant produit la mesure |
| `measured_at` | datetime | date de mesure |

## Risk

| Champ | Type | Règle |
|---|---|---|
| `id`, `project_id`, `sprint_id` | string | identifiants |
| `rule_id` | string | règle versionnée |
| `title`, `description` | string/text | constat compréhensible |
| `severity` | enum | `low`, `medium`, `high`, `critical` |
| `score` | float | 0 à 100 |
| `confidence` | float | 0 à 1, distinct du score |
| `source_type`, `source_id` | string | preuve d'origine |
| `status` | enum | `open`, `acknowledged`, `resolved`, `dismissed` |
| `detected_at` | datetime | date de calcul |

## Report

| Champ | Type | Règle |
|---|---|---|
| `id`, `project_id`, `sprint_id` | string | identifiants |
| `type` | enum | `daily`, `weekly` |
| `status` | enum | `draft`, `validated`, `rejected` |
| `period_start`, `period_end` | date | période couverte |
| `content_markdown` | text | contenu déterministe ou synthétisé |
| `generated_at` | datetime | génération |
| `validated_by`, `validated_at` | string/datetime/null | boucle humaine |

## ExpectedAnomaly

Cette structure n'est pas une table métier. Elle constitue la vérité terrain contrôlée pour les
tests du futur moteur de règles QA.

| Champ | Description |
|---|---|
| `rule_id` | règle qui devra déclencher |
| `scenario` | `SCN-01`, `SCN-02` ou `SCN-03` |
| `severity` | niveau attendu |
| `source_type`, `source_id` | preuve exacte |
| `description` | explication humaine |
| `expected_signal` | condition logique vérifiable |

## Volumétrie v0.1

| Entité | Nombre |
|---|---:|
| Projet | 1 |
| Sprints | 3 |
| Tickets | 50 (16 sain, 17 à risque, 17 critique) |
| Commits | 30 |
| Pull requests | 12 |
| Builds | 12 |
| Résultats de tests | 12 |
| Métriques | 9 |
| Risques / rapports | 0 / 0 dans la version actuelle |
| Anomalies attendues | 9 |
