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
| Tests de résilience opérationnelle | Chaos (arrêt de service), scénario d'attaque, scénario e2e | Tests TLPT (red team avancée) encadrés par un prestataire agréé |
| Risque lié aux tiers TIC | Ollama local (pas de dépendance cloud), images maîtrisées | Registre des contrats, stratégie de sortie fournisseur |
| Partage d'informations sur les cyber-menaces | Règles SOC documentées, types d'attaque qualifiés | Participation à une communauté de partage (ISAC) |

---

## Ce que la démonstration met particulièrement en avant

- **Détection et réponse automatisées** (NIS2 gestion des incidents, DORA détection/réponse) :
  la boucle agit en moins de 3 minutes et **prouve** la reprise.
- **Traçabilité vérifiable** : le journal d'incidents chaîné SHA-256 fournit une preuve
  d'intégrité, utile pour une notification d'incident crédible.
- **Résilience testée** : la reprise a été rejouée en conteneurs réels (chaos), pas seulement
  décrite.

## Écarts assumés (cadre POC)

Les volets organisationnels et réglementaires (gouvernance d'entreprise, notification réelle aux
autorités, tests TLPT agréés, gestion contractuelle des tiers, haute disponibilité multi-site)
sortent du périmètre d'un démonstrateur de quatre jours sur un seul hôte. Ils sont identifiés ici
pour montrer la trajectoire vers une conformité réelle, détaillée dans le dossier d'ingénierie.
