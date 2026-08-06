# Cadrage fonctionnel — semaine 1

## 1. Problématique

Les informations nécessaires au suivi QA d'un projet IT sont dispersées entre tickets,
dépôt Git, pull requests, pipelines CI, résultats de tests et métriques. Cette fragmentation
retarde la détection des signaux faibles et rend le reporting manuel, variable et difficile à
tracer.

Le projet construit un copilote qui rassemble ces preuves, applique d'abord des règles
transparentes, puis ajoute progressivement RAG et agents spécialisés. Le copilote **propose et
explique** ; il ne prend jamais de décision opérationnelle à la place de l'utilisateur.

## 2. Objectif du produit

Permettre à un QA engineer, un chef de projet ou un tech lead de comprendre rapidement l'état
d'un projet, d'identifier les risques QA avec leurs sources, de produire un rapport et de valider
humainement les actions proposées.

Objectifs mesurables à huit semaines :

1. charger et analyser un projet de démonstration de bout en bout ;
2. détecter au moins cinq familles de risques avec preuve ;
3. générer daily brief et weekly report à partir des données stockées ;
4. répondre à des questions projet avec sources et refus en cas de preuve insuffisante ;
5. rendre l'installation, le seed, les tests et la démonstration reproductibles.

## 3. Utilisateurs

| Persona | Besoin principal | Décisions prises avec le système |
|---|---|---|
| QA engineer | Prioriser les anomalies et contrôler la qualité | Ouvrir une investigation, demander un correctif, valider/rejeter un signal |
| Chef de projet | Suivre délai, charge, blocages et risques | Replanifier, arbitrer, escalader, communiquer l'état du sprint |
| Tech lead | Relier code, CI, tests et dette technique | Prioriser une revue, stabiliser un pipeline, corriger une régression |

Acteurs systèmes futurs : GitHub ou simulateur, PostgreSQL, service LLM optionnel et base
vectorielle. Ils sont externes au cœur applicatif et remplaçables par des adaptateurs.

## 4. Scénarios de référence

La date de référence figée du dataset est le **2026-07-13**. Chaque scénario correspond à un
sprint et doit rester stable afin de comparer les règles, scores et évolutions du produit.

### SCN-01 — Sprint sain

- **But :** contrôler que le système ne déclenche pas d'alerte critique lorsqu'un sprint suit son
  plan.
- **Données :** 16 tickets, 41 points, aucun blocage ancien, aucune échéance dépassée ouverte,
  builds réussis, couverture à 86 %.
- **Résultat attendu en S3 :** score faible, aucune alerte critique, faits positifs traçables.
- **Valeur QA :** mesurer les faux positifs.

### SCN-02 — Sprint à risque

- **But :** détecter assez tôt une dégradation récupérable.
- **Données :** 17 tickets, deux tickets bloqués dont `TKT-024` depuis plus de 72 h, deux tickets
  ouverts après échéance, un build échoué puis corrigé, couverture à 71 %.
- **Résultat attendu en S3 :** alertes moyenne/haute, score intermédiaire, preuves liées aux
  tickets et au build.
- **Valeur QA :** vérifier la combinaison de plusieurs signaux faibles.

### SCN-03 — Sprint critique

- **But :** vérifier la détection de signaux qui exigent une action immédiate.
- **Données :** 17 tickets, bug critique `TKT-038` ouvert, blocage ancien `TKT-039`, tickets en
  retard, deux derniers pipelines échoués et couverture à 54 %.
- **Résultat attendu en S3 :** risque critique, priorité immédiate et recommandations soumises à
  validation humaine.
- **Valeur QA :** mesurer le rappel sur les anomalies critiques injectées.

La proposition complète est prête pour revue. La confirmation réelle par l'encadrant doit être
datée dans `docs/validation_encadrant.md`; elle ne peut pas être simulée par le système.

## 5. Cas d'usage principaux

| ID | Cas d'usage | Acteur | Entrée | Sortie attendue |
|---|---|---|---|---|
| UC-01 | Charger un dataset | QA engineer | JSON/CSV validé | Données normalisées et journal d'import |
| UC-02 | Consulter la vue projet | Tous | Projet/sprint | KPI, progression, CI, couverture |
| UC-03 | Analyser les risques | QA engineer | `project_id` | Constats, score, preuve, confiance |
| UC-04 | Examiner une preuve | Tous | Risque sélectionné | Ticket/build/test/métrique source |
| UC-05 | Générer un rapport | Chef de projet | Période et projet | Daily/weekly report exportable |
| UC-06 | Valider une action | Tous | Recommandation | Acceptation, rejet ou modification tracée |
| UC-07 | Interroger le projet | Tous | Question + filtres | Réponse sourcée ou refus explicite |
| UC-08 | Comparer V1 et V2 | Tech lead | Exécution de référence | Qualité, latence, coût, traçabilité |

## 6. Exigences

### Fonctionnelles

- **FR-01** — importer un projet de démonstration de façon reproductible ;
- **FR-02** — conserver projets, sprints, tickets, commits, PR, builds, tests et métriques ;
- **FR-03** — calculer des KPI à partir des données stockées ;
- **FR-04** — détecter cinq familles d'anomalies par règles transparentes ;
- **FR-05** — relier chaque alerte à au moins une preuve identifiable ;
- **FR-06** — générer et historiser daily brief et weekly report ;
- **FR-07** — demander une validation humaine pour toute recommandation ;
- **FR-08** — fournir des réponses RAG avec citations ou information insuffisante ;
- **FR-09** — tracer l'agent, les preuves, la confiance et la validation en V2.

### Non fonctionnelles

- **NFR-01 Reproductibilité** — installation documentée et seed déterministe ;
- **NFR-02 Qualité** — lint et tests automatiques, couverture backend ciblée >= 70 % ;
- **NFR-03 Traçabilité** — identifiants stables et sources conservées ;
- **NFR-04 Sécurité** — données fictives, secrets hors Git, lecture seule pour un connecteur réel ;
- **NFR-05 Explicabilité** — aucun score sans détail des facteurs ;
- **NFR-06 Résilience** — rapport déterministe si le LLM est indisponible ;
- **NFR-07 Performance** — API locale réactive sur le dataset de référence ;
- **NFR-08 Portabilité** — Python 3.11+, PostgreSQL et exécution conteneurisée à terme.

## 7. Périmètre

### Inclus dans le MVP

Dataset fictif, ingestion, PostgreSQL, API, dashboard, règles QA, score explicable, risques,
daily/weekly reports, tests, Docker et documentation.

### Extensions contrôlées

RAG sourcé, quatre rôles d'agents, analyse de métadonnées PR/code, connecteur GitHub en lecture
seule, authentification simple et CI complète.

### Hors périmètre

- correction ou décision automatique ;
- entraînement d'un LLM ;
- ingestion de données confidentielles non autorisées ;
- intégration simultanée de Jira, GitHub et GitLab ;
- promesse qu'un copilote remplace une revue QA ou code humaine.

## 8. Hypothèses et seuils initiaux

| Élément | Hypothèse S1 | À confirmer |
|---|---|---|
| Ticket bloqué trop longtemps | plus de 72 h | encadrant |
| Ticket en retard | ouvert et `due_date < reference_date` | encadrant |
| Couverture faible | moins de 70 % | encadrant |
| Bug critique | type `bug`, priorité `critical`, non fermé | encadrant |
| Pipeline préoccupant | dernier build échoué ; critique si échecs consécutifs | encadrant |
| Sprint sain | absence de signal majeur, couverture >= 80 % | encadrant |

Ces seuils sont des paramètres métier, pas des vérités universelles. Ils seront versionnés et
testés durant la semaine 3.

## 9. Critères de sortie de semaine 1

- [x] 3 scénarios documentés et injectés dans un dataset figé ;
- [x] 3 personas et 10 user stories priorisées ;
- [x] modèle des 10 entités demandé ;
- [x] 1 projet, 3 sprints et 50 tickets cohérents ;
- [x] API `/health`, migration et seed exécutable ;
- [x] README, tests et pipeline qualité ;
- [ ] validation formelle de l'encadrant, seule action externe au dépôt.
