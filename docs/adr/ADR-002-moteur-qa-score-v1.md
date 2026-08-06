# ADR-002 — Moteur QA et score de risque V1

- Statut : accepté, étendu par l'ADR-003
- Date : 2026-07-18
- Portée : règles déterministes, Agent QA et score explicable

## Contexte

Le dataset contient neuf anomalies connues réparties entre un sprint sain, un sprint à risque et
un sprint critique. La semaine 3 doit les détecter sans LLM, présenter leurs preuves et produire
un score comparable entre scénarios. Les résultats doivent rester reproductibles à partir de la
date de référence du dernier journal d'ingestion.

## Décision

1. Utiliser cinq règles déterministes regroupées dans le ruleset `qa-rules-v1.0`.
2. Ne signaler un échec CI que si le dernier build du sprint est en échec. Un échec historique
   suivi d'un succès est considéré comme rétabli.
3. Utiliser les seuils V1 suivants : blocage strictement supérieur à 72 heures et couverture
   strictement inférieure à 70 %.
4. Agréger cinq signaux normalisés avec des poids totalisant 100 : blocage 20, retard 15, bug
   critique 25, pipeline 25 et couverture 15.
5. Conserver chaque contribution dans `risk_analyses.breakdown` et chaque preuve dans
   `risks.evidence`.
6. Rendre l'analyse idempotente pour un projet, un sprint, une date et une version de ruleset.
7. Présenter les recommandations comme des propositions non exécutées, avec
   `requires_human_validation=true`.

## Interprétation du score

| Intervalle | Niveau |
|---|---|
| 0 à 19,9 | faible |
| 20 à 44,9 | moyen |
| 45 à 69,9 | élevé |
| 70 à 100 | critique |

Le score est une aide à la priorisation et non une probabilité d'incident. La confiance décrit la
qualité de la preuve ; elle ne remplace ni la sévérité ni la décision humaine.

## Conséquences

- les résultats peuvent être testés exactement et expliqués facteur par facteur ;
- le sprint sain sert de contrôle des faux positifs critiques ;
- un nouveau ruleset pourra changer les seuils sans altérer l'identité de la V1 ;
- la table d'analyse prépare l'historique nécessaire aux rapports de semaine 4 ;
- les poids restent des hypothèses à faire valider par l'encadrant et non un modèle statistique.

L'ADR-003 remplace le stockage exclusif des définitions dans Python et du détail uniquement en
JSON : les politiques sont maintenant versionnées dans un fichier validé, et les contributions
sont également normalisées dans une table dédiée.
