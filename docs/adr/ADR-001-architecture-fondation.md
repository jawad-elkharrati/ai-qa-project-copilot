# ADR-001 — Architecture de fondation

- Statut : accepté
- Date : 2026-07-13

## Contexte

Le produit doit rester simple à démarrer tout en permettant l'ajout progressif de règles QA, de
recherche documentaire et de composants d'intelligence artificielle.

## Décisions

1. Utiliser un monolithe modulaire Python et FastAPI pour limiter la complexité d'intégration.
2. Utiliser PostgreSQL comme stockage cible des données structurées.
3. Conserver SQLite comme solution locale légère pour les tests et la démonstration.
4. Utiliser SQLAlchemy et Alembic pour séparer le modèle Python des migrations de la base.
5. Utiliser un dataset JSON fictif et stable avec des identifiants reproductibles.
6. Commencer par des règles déterministes avant d'ajouter un modèle de langage.
7. Isoler les futurs connecteurs GitHub, LLM et base vectorielle derrière des interfaces dédiées.

## Conséquences positives

- démarrage local rapide ;
- documentation OpenAPI automatique ;
- fonctionnement possible sans données internes ;
- relations entre les preuves faciles à interroger ;
- migrations et tests reproductibles.

## Compromis

- SQLite ne reproduit pas toutes les particularités de PostgreSQL ;
- un monolithe convient à ce produit, mais ne représente pas une architecture distribuée ;
- les seuils QA initiaux doivent être confirmés par les responsables métier.

## Alternatives non retenues

- une interface web complexe avant validation du parcours principal ;
- des microservices sans besoin opérationnel démontré ;
- MongoDB pour des données fortement relationnelles ;
- un LLM avant la création d'un référentiel de tests stable.
