# Analyse NIS2 / DORA

> Lecture du démonstrateur Resilience Alpha (groupe 16) au regard de deux cadres européens de
> cyber-résilience. Objectif : montrer quelles exigences le POC **illustre** et lesquelles ne
> sont **pas démontrables** dans un laboratoire. Ce n'est pas un audit de conformité ; c'est une
> mise en correspondance pédagogique, données fictives.

## Les deux cadres en bref

- **NIS2** (directive UE 2022/2555) : relève le niveau de cybersécurité des entités
  essentielles et importantes. Exigences clés : gouvernance et gestion des risques, mesures
  techniques et organisationnelles, notification des incidents, continuité d'activité.
- **DORA** (règlement UE 2022/2554) : résilience opérationnelle numérique du secteur financier.
  Piliers : gestion du risque TIC, gestion et notification des incidents, tests de résilience,
  gestion du risque lié aux tiers, partage d'informations.

Une plateforme de paiement relèverait des deux. Le POC se concentre sur les aspects
**techniques et opérationnels** (détection, réponse, continuité, traçabilité).

### Applicabilité à l'entreprise fictive

- **DORA** s'applique directement : un établissement de paiement est une **entité financière**
  au sens du règlement (art. 2). C'est le cadre principal.
- **NIS2** vise le secteur bancaire et les infrastructures des marchés financiers. Pour les
  entités financières, DORA est une **loi spéciale** (*lex specialis*) : ses exigences de gestion
  du risque TIC et de notification priment sur celles de NIS2. NIS2 reste utile pour la
  gouvernance générale et la chaîne d'approvisionnement.

### Classification d'un incident majeur (DORA) et données du journal

| Critère DORA de classification | Où le POC le mesure |
|---|---|
| Durée et indisponibilité du service | `opened_at` / `closed_at` de l'incident, `remediation_duration_seconds` |
| Clients et transactions touchés | Taux de succès du canari, débit de transactions (preuves de l'incident) |
| Services critiques touchés | Catégorie et cible de l'alerte (`job` de `TargetDown`, catégorie d'incident) |
| Pertes de données | Transactions atomiques ; RPO ~0 (voir PCA/PRA) |
| Étendue géographique, impact économique, réputation | Non mesurable dans le POC (hypothèses d'impact : PCA/PRA §2) |

---

## NIS2 - correspondance

| Exigence NIS2 (art. 21 sauf mention) | Ce que le POC illustre | Non démontrable en labo |
|---|---|---|
| Analyse de risques et politique de sécurité | EBIOS RM ([`../ebios-rm/`](../ebios-rm/)), socle de durcissement | Politique d'entreprise validée par la direction |
| Gestion des incidents | Détection ML + SOC, remédiation autonome, journal d'audit, rapports | Cellule de crise, astreinte 24/7 |
| Continuité d'activité et gestion de crise | PCA/PRA ([`../pca-pra/`](../pca-pra/)), reprise prouvée par transaction | Bascule multi-site, sauvegardes externalisées |
| Sécurité de la chaîne d'approvisionnement | Images épinglées par version, dépendances figées, CI `gitleaks` | Évaluation des fournisseurs, SBOM complet |
| Sécurité de l'acquisition et du développement | Conteneurs non-root, read-only, revues par PR, tests | Cycle SSDLC complet, tests d'intrusion externes |
| Cryptographie et gestion des secrets | Vault (KV v2), aucun secret en clair, JWT signés | HSM, rotation automatisée des clés |
| Contrôle d'accès et authentification | JWT, biométrie du back-office (consigne add. 1), moindre privilège | IAM d'entreprise, MFA généralisée |
| Notification d'incident (art. 23) : alerte précoce sous 24 h, rapport sous 72 h | Journal horodaté et rapport par incident = matière à notifier | Transmission réelle au CSIRT national |
| Mesures d'efficacité (art. 21.1) | Métriques Prometheus, dashboards, canari | Indicateurs suivis dans la durée |

---

## DORA - correspondance

| Pilier DORA | Ce que le POC illustre | Non démontrable en labo |
|---|---|---|
| Gestion du risque TIC | Cartographie des biens supports, segmentation réseau, moindre privilège | Cadre de gouvernance TIC, organe de direction |
| Détection des anomalies | Détecteur ML (Isolation Forest) sur métriques temps réel | Corrélation multi-sources à grande échelle |
| Réponse et rétablissement | Remédiation autonome + preuve par transaction métier | Plans de communication, continuité des opérations critiques |
| Gestion des incidents et notification | Classification des incidents, journal chaîné, rapports Markdown | Déclaration aux autorités (modèles DORA), délais réglementaires |
| Tests de résilience opérationnelle | Chaos (arrêt de service, fait le 21/10), injections bloquées (fait), DoS et scénario e2e (prévus) | Tests TLPT (red team avancée) encadrés par un prestataire agréé |
| Risque lié aux tiers TIC | Ollama local (pas de dépendance cloud), images maîtrisées | Registre des contrats, stratégie de sortie fournisseur |
| Partage d'informations sur les cyber-menaces | Règles SOC documentées, types d'attaque qualifiés | Participation à une communauté de partage (ISAC) |

---

## Ce que la démonstration met particulièrement en avant

- **Détection et réponse automatisées** (NIS2 gestion des incidents, DORA détection/réponse) :
  sur une panne de service (21/10, ~67 s) et sur une attaque DoS réelle détectée par le ML
  (22/10, 6 essais sur 6, 37 à 75 s), la boucle a agi seule et **prouvé** la reprise par une
  transaction.
- **Traçabilité vérifiable** : le journal d'incidents chaîné SHA-256 fournit une preuve
  d'intégrité, utile pour une notification d'incident crédible.
- **Résilience testée** : la reprise a été rejouée en conteneurs réels (chaos), pas seulement
  décrite.

## Écarts assumés (cadre POC)

Les volets organisationnels et réglementaires (gouvernance d'entreprise, notification réelle aux
autorités, tests TLPT agréés, gestion contractuelle des tiers, haute disponibilité multi-site)
sortent du périmètre d'un démonstrateur de quatre jours sur un seul hôte. Ils sont identifiés ici
pour montrer la trajectoire vers une conformité réelle, détaillée dans
[`../recommandations.md`](../recommandations.md).
