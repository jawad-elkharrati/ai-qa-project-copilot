# Cadrage fonctionnel

## Problème

Les informations utiles au suivi qualité d'un projet informatique sont souvent dispersées entre
les tickets, les dépôts Git, les pull requests, les pipelines, les tests et les métriques. Cette
dispersion rend les problèmes plus difficiles à détecter et les comptes rendus plus longs à
préparer.

## Objectif

Le produit doit réunir ces informations, calculer des indicateurs vérifiables et aider les équipes
à identifier les risques avec leurs preuves. Il propose des constats ; il ne prend jamais de
décision opérationnelle à la place d'une personne.

## Utilisateurs

| Utilisateur | Besoin principal |
|---|---|
| QA engineer | Contrôler la qualité et prioriser les anomalies |
| Chef de projet | Suivre l'avancement, les blocages et les risques |
| Tech lead | Relier le code, les builds, les tests et les métriques |

## Scénarios de référence

Le dataset NovaShop utilise trois sprints stables :

- un sprint sain, sans signal critique et avec une bonne couverture ;
- un sprint à risque, avec plusieurs signaux faibles ;
- un sprint critique, avec des retards, des échecs de build et une couverture faible.

Ces scénarios permettent de comparer les résultats du système de manière reproductible.

## Fonctions principales attendues

- importer des données structurées ;
- conserver les relations entre projets, sprints, tickets, code, builds et tests ;
- calculer des indicateurs depuis les données stockées ;
- détecter des anomalies avec des règles explicables ;
- relier chaque alerte à une preuve ;
- produire des synthèses traçables ;
- demander une validation humaine avant toute action ;
- fournir plus tard des réponses sourcées lorsque les composants d'intelligence artificielle
  seront disponibles.

## Principes de qualité

- installation reproductible ;
- tests automatiques et contrôle du style ;
- identifiants et sources conservés ;
- secrets exclus du dépôt Git ;
- aucun score sans explication de ses facteurs ;
- données fictives pour éviter la publication d'informations confidentielles.

## Limites actuelles

L'ingestion, l'API, le stockage, les indicateurs et le dashboard sont disponibles. Le moteur de
risque, les rapports automatiques, le RAG et le système multi-agents restent à implémenter.
