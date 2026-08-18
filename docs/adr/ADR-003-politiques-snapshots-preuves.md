# ADR-003 — Politiques, snapshots et chaîne de preuves

- Statut : accepté pour la semaine 3
- Date : 2026-07-23
- Portée : policies as code, historique du risque, explicabilité et qualité des données

## Contexte

Le score V1 était explicable dans sa réponse, mais les définitions des règles, les contributions
et l'évolution du risque devaient devenir auditables dans le temps. Le MVP doit également
distinguer une absence de risque d'une absence de données, sans introduire de moteur de règles
générique, de base graphe, de LLM ou d'écriture dans les outils externes.

## Décisions

### Politiques

Les cinq politiques sont définies dans `policies/qa-rules-v1.0.json`. Un modèle Pydantic strict
valide :

- l'identifiant et la version ;
- la métrique et l'opérateur parmi une liste autorisée ;
- le seuil, la normalisation et le poids ;
- la sévérité, la recommandation et l'état d'activation ;
- une somme des poids actifs inférieure ou égale à 100.

Le fichier exprime uniquement des comparaisons simples. L'agrégation des faits, l'évaluation et
le calcul du score restent trois responsabilités Python séparées.

Deux politiques actives ne peuvent pas exprimer la même logique de détection sous des
identifiants différents. Une empreinte canonique est calculée à partir du type d'entité, de la
condition, de la normalisation, de l'agrégation et des éventuelles substitutions de sévérité.
L'identifiant, le nom, la description, le poids et la recommandation n'en font pas partie. Le
chargement échoue explicitement si deux empreintes actives sont identiques. Une politique
désactivée peut rester versionnée comme brouillon ; son activation déclenche ce contrôle.

### Contributions et bornes du score

Chaque politique active produit exactement une `RiskContribution` par snapshot. La contribution
vaut `poids × signal normalisé`, avec un signal borné entre 0 et 1. Plusieurs constats d'une même
politique utilisent le maximum des signaux et un bonus de nombre plafonné, ce qui évite de
réappliquer plusieurs fois le poids complet. La somme finale est bornée entre 0 et 100.

Les contraintes de base interdisent les signaux hors plage, les contributions négatives ou
supérieures au poids et les doublons `(analysis_id, policy_id)`.

### Snapshots et delta

`RiskAnalysis` représente un snapshot immuable. Son identité dépend du projet, du sprint, de la
date de référence, de la version et du hash des politiques ainsi que d'une empreinte canonique
des faits et de la qualité des données.

Un appel identique retourne le snapshot existant. Une entrée différente crée un nouveau
snapshot relié au précédent par `previous_snapshot_id`. Le delta compare les contributions par
`policy_id` et classe chaque changement comme ajouté, retiré, augmenté ou diminué.

### Preuves

`RiskEvidence` matérialise une chaîne relationnelle minimale. Le service construit des nœuds et
relations lisibles à partir des tables existantes :

`Risk → Ticket → PullRequest → Build → TestResult`

et, quand elles existent :

`Ticket → Commit` et `Build → Commit`.

Les relations manquantes sont retournées explicitement. Une base graphe n'est pas justifiée au
stade du MVP.

### Confiance et informations manquantes

La confiance est un indicateur déterministe de qualité des données, pas une probabilité :

`0,60 × présence des sources + 0,20 × fraîcheur + 0,20 × couverture des relations`.

Le détail de chaque composant est persisté. Les données manquantes et périmées sont des listes
structurées exposées par l'API. Le seuil de fraîcheur V1 est de 14 jours.

### Validation humaine

Toutes les réponses conservent `human_validation_required=true` ou
`requires_human_validation=true`. Les recommandations ne déclenchent aucune modification dans
Jira, Git, GitHub ou la CI.

Les actions accepter, modifier et rejeter sont enregistrées dans `RiskDecision` sous forme
d'événements append-only. L'absence d'événement correspond à l'état `pending`. Chaque état final
conserve l'acteur, la date, le commentaire éventuel, la recommandation originale et, si
nécessaire, sa version modifiée. Une décision reste une trace humaine locale : aucun connecteur
d'écriture n'est appelé.

## Conséquences

- un score peut être reproduit et expliqué facteur par facteur ;
- deux calculs identiques ne polluent pas l'historique ;
- une variation du score est reliée à des contributions précises ;
- un diagnostic incomplet est présenté avec sa qualité de données ;
- les migrations restent compatibles avec SQLite et sont préparées pour PostgreSQL ;
- PostgreSQL n'est pas déclaré validé tant qu'une instance réelle n'a pas été testée ;
- l'architecture reste déterministe, sans LLM ni nouvelle dépendance d'exécution.
