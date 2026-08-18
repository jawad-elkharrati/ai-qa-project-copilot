# Backlog priorisé v0.1

La priorité suit MoSCoW. L'ordre est celui de réalisation recommandé ; les estimations servent à
la planification et devront être recalibrées après la première démonstration.

## User stories

### US-01 — Charger un dataset de démonstration

**En tant que** QA engineer, **je veux** charger un projet fictif versionné **afin de** reproduire
les mêmes analyses sans attendre de données internes.

- Priorité : MUST — rang 1 — S1/S2 — 5 points
- Acceptation : JSON valide accepté ; erreur explicite si référence inconnue ; deux chargements ne
  créent pas de doublons ; version et date de référence conservées.

### US-02 — Consulter la santé du service

**En tant que** tech lead, **je veux** vérifier l'état de l'API et de sa base **afin de** diagnostiquer
rapidement un problème de démarrage.

- Priorité : MUST — rang 2 — S1 — 2 points
- Acceptation : `/health` répond 200 si la base est joignable ; indique version, environnement et
  backend ; répond 503 sans exposer de secret lorsque la base est indisponible.

### US-03 — Voir la situation d'un projet

**En tant que** chef de projet, **je veux** une vue synthétique par projet et sprint **afin de**
comprendre avancement, blocages et santé CI.

- Priorité : MUST — rang 3 — S2 — 5 points
- Acceptation : filtres projet/sprint ; progression, retard, blocages, CI et couverture calculés
  depuis la base ; résultat identique au dataset de référence.

### US-04 — Détecter les anomalies QA

**En tant que** QA engineer, **je veux** détecter les anomalies par règles explicites **afin de**
prioriser mes investigations.

- Priorité : MUST — rang 4 — S3 — 8 points
- Acceptation : cinq règles minimales ; résultat déterministe ; sévérité et preuve ; tests sur les
  trois scénarios.

### US-05 — Comprendre le score de risque

**En tant que** chef de projet, **je veux** voir la contribution de chaque signal au score **afin de**
ne pas suivre une note opaque.

- Priorité : MUST — rang 5 — S3 — 5 points
- Acceptation : score 0–100 ; facteurs normalisés ; pondérations affichées ; changement de seuil
  testable ; données manquantes signalées.

### US-06 — Examiner la preuve d'un risque

**En tant que** tech lead, **je veux** ouvrir l'objet source d'un risque **afin de** vérifier le
constat avant d'agir.

- Priorité : MUST — rang 6 — S3 — 3 points
- Acceptation : lien vers ticket/build/test/métrique ; source existante ; date du constat ; niveau
  de confiance ; aucune recommandation présentée comme décision.

### US-07 — Produire un daily et un weekly report

**En tant que** chef de projet, **je veux** générer un rapport à partir des KPI et risques **afin de**
partager un état cohérent et traçable.

- Priorité : MUST — rang 7 — S4 — 8 points
- Acceptation : mode déterministe sans LLM ; sources citées ; historique ; export Markdown et
  HTML/PDF ; période explicite.

### US-08 — Valider une recommandation

**En tant que** responsable humain, **je veux** accepter, rejeter ou modifier une action proposée
**afin de** garder le contrôle de la décision.

- Priorité : MUST — rang 8 — S4/S6 — 5 points
- Acceptation : état initial « proposée » ; identité et date de validation ; commentaire ; absence
  d'exécution automatique.

### US-09 — Interroger les connaissances avec sources

**En tant que** membre du projet, **je veux** poser une question et voir les passages sources
**afin de** vérifier la réponse et limiter les hallucinations.

- Priorité : SHOULD — rang 9 — S5 — 8 points
- Acceptation : filtre projet/sprint ; citations obligatoires ; refus si preuve insuffisante ;
  campagne de 20 questions ; protection d'injection simple.

### US-10 — Orchestrer et tracer les agents

**En tant que** tech lead, **je veux** savoir quel agent a produit chaque constat **afin de** comparer
le workflow multi-agents au moteur simple.

- Priorité : SHOULD — rang 10 — S6 — 13 points
- Acceptation : rôles QA/Projet/Code/Report bornés ; format JSON commun ; journal d'exécution ;
  consolidation et validation ; comparaison qualité/latence/coût V1-V2.

## Carte de livraison

### État après la semaine 3

- US-04 — détection des anomalies : réalisée et testée sur les neuf preuves de l'oracle ;
- US-05 — score 0-100 expliqué : réalisé avec cinq contributions conservées ;
- US-06 — consultation de la preuve : réalisée dans l'API et le dashboard ;
- validation encadrant des seuils et poids : encore attendue.

| Semaine | Résultat démontrable | Stories dominantes |
|---|---|---|
| S1 | API saine + dataset chargé | US-01, US-02 |
| S2 | Vue projet et KPI | US-01, US-03 |
| S3 | Risques expliqués | US-04, US-05, US-06 |
| S4 | MVP et rapports | US-07, US-08 |
| S5 | Chat sourcé | US-09 |
| S6 | Multi-agents observable | US-10 |
| S7 | Sécurité, CI, connecteur | durcissement transversal |
| S8 | Évaluation et soutenance | validation de l'ensemble |

## Definition of Done commune

Une story est terminée si le comportement nominal et au moins une erreur sont testés, si les
données de sortie sont traçables, si la documentation est à jour, si aucun secret n'est ajouté au
dépôt et si la démonstration peut être rejouée depuis une installation propre.
## État après la semaine 4 P1-A

- US-07 : rapports JSON, Markdown et HTML déterministes livrés ; PDF reporté en P1-B ;
- US-08 : validation, historique, mise en cours, clôture et résultat observé livrés ;
- P1-B reporté : PDF, rapports persistés/versionnés, expiration/annulation, planification,
  notifications et analyses avancées ;
- US-09 reste intégralement réservée à la semaine 5 : aucun RAG n’a été anticipé.