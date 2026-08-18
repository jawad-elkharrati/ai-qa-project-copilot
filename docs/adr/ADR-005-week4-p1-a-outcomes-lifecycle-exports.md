# ADR-005 — P1-A : efficacité observée, cycle opérationnel et exports

- Statut : accepté
- Date : 2026-08-01
- Portée : extension P1-A de la semaine 4
- Dépend de : ADR-004

## Contexte

Le P0 fournit le Decision Brief, les recommandations par épisode, leur validation humaine, les
rapports JSON et le dashboard de décision. Le P1-A doit rendre ce MVP plus opérationnel sans
modifier le Decision Engine et sans anticiper le RAG, LangGraph, les connecteurs ou PostgreSQL.

## Décisions

### Résultat observé

RecommendationOutcome est calculé à partir du premier snapshot lié à une transition humaine
ACCEPTED ou MODIFIED et d’un snapshot ultérieur du même périmètre. Le couple
(recommendation_id, observed_snapshot_id) rend la persistance idempotente.

Les états sont NOT_YET_MEASURABLE, IMPROVEMENT_OBSERVED, NO_IMPROVEMENT_OBSERVED et
INSUFFICIENT_DATA. Un résultat sans snapshot ultérieur n’est pas persisté. Toute formulation
décrit une corrélation temporelle et n’attribue jamais l’évolution à la recommandation.

### Cycle opérationnel minimal

Les états P0 sont conservés. Une recommandation ACCEPTED ou MODIFIED peut passer à IN_PROGRESS,
puis à COMPLETED. Le passage direct à COMPLETED reste autorisé pour préserver la compatibilité
P0. La clôture exige un commentaire. Le démarrage peut seulement modifier assigned_to et
due_date. Chaque changement crée une RecommendationTransition append-only avec
external_action_executed=false.

RiskDecision reste inchangé et séparé. Aucun lien ambigu avec une décision S3 n’est créé.

### Exports

Les services de rapport restent la source unique. Une représentation intermédiaire commune est
rendue en Markdown ou HTML déterministe. Le HTML échappe les valeurs. Aucun PDF ni dépendance
lourde n’est ajouté au P1-A. Les réponses sont calculées à la demande et ne sont pas persistées.

### Dashboard

Streamlit consomme uniquement les nouveaux endpoints API. Il affiche les transitions, le résultat
observé et prépare les téléchargements à la demande. Il ne recalcule ni décision, ni priorité, ni
score, ni résultat d’efficacité.

## Compatibilité avec la semaine 5

Le P1-A n’ajoute ni index documentaire, ni embeddings, ni recherche, ni conversation, ni agent.
Les futurs composants RAG pourront lire les rapports et audits mais ne sont pas requis par ce
modèle. Les frontières du domaine S4 restent donc stables.

## P1-B reporté

- export PDF ;
- rapports persistés, versionnés ou mis en cache ;
- états EXPIRED et CANCELLED ;
- planification et notifications ;
- analyses avancées et exports groupés.

## Conséquences

- suivi opérationnel démontrable sans action externe ;
- historique humain complet et compatible avec le P0 ;
- mesure utile mais non causale ;
- exports légers et reproductibles ;
- une migration SQLite supplémentaire, révision 20260801_0009.