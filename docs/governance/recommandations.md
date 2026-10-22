# Arbitrages et recommandations à la direction

> Note de conseil du consortium G16 au commanditaire (Direction Nationale de la Sûreté Numérique,
> fictive). Elle relie nos choix au démonstrateur réellement construit et aux essais menés.
> Analyse des risques : [EBIOS RM](ebios-rm/) · continuité : [PCA/PRA](pca-pra/) · cadre
> réglementaire : [NIS2 / DORA](nis2-dora/).

## 1. Ce que nous avons choisi de protéger

**La capacité à exécuter un paiement**, pas seulement la disponibilité des serveurs. Un service
« démarré » qui ne traite pas de paiement est en panne pour le client. D'où notre principe : la
reprise n'est déclarée que lorsqu'une **transaction de contrôle réussit** (canari, `POST /probe`).

Ordre de priorité retenu (événements redoutés EBIOS) :

1. **Disponibilité du paiement** (ER1, gravité 4) : c'est ce qui coûte le plus vite (PCA/PRA §2).
2. **Intégrité des transactions et des soldes** (ER2) : transactions SQL atomiques, aucun état à
   moitié écrit.
3. **Confidentialité des secrets** (ER3) : Vault, aucun secret dans le dépôt.
4. **Traçabilité** (ER5) : journal d'incidents chaîné, vérifiable.

## 2. Arbitrages faits sous contrainte (4 jours, un seul PC serveur)

| Arbitrage | Ce que nous avons choisi | Ce que nous avons sacrifié | Pourquoi c'est acceptable ici |
|---|---|---|---|
| Automatiser ou garder l'humain | Reprise **automatique** pour la disponibilité ; **humaine** pour une compromission | Rapidité de réponse à une fuite | Une machine peut relancer un service ; elle ne doit pas décider seule qu'une fuite est traitée |
| Pouvoir du moteur de remédiation | **Liste blanche** de 4 playbooks, Docker via un proxy limité (`socket-proxy-rw`), jamais sur le réseau applicatif | Souplesse (un incident imprévu finit en escalade) | Un automate à droits élevés est une cible : on réduit ce qu'il peut faire |
| Détection | Isolation Forest **plus** alertes classiques (`TargetDown`, règles SOC) | Simplicité d'un seul mécanisme | Le ML voit les dégradations combinées ; les règles couvrent les pannes franches |
| Données d'entraînement | Modèle de repli simulé, à remplacer par du trafic réel collecté | Précision du modèle | Délai : 4 jours. La procédure de collecte et d'entraînement est prête |
| Ban d'IP | Temporaire (5 min), sur l'IP vue par le WAF | Tout l'externe est coupé pendant le ban (IP partagée derrière Docker Desktop) | Le canari interne prouve que le service reste sain ; limite annoncée |
| Exposition | Un seul port réseau (WAF) ; consoles sur `127.0.0.1` | Administration à distance | Le PC est aussi sur le WiFi du campus |
| Chiffrement | Pas de TLS (pas de domaine ni de certificat en laboratoire) | Confidentialité en transit | Données fictives, réseau isolé ; prioritaire en production |
| Supervision de la base | Pas d'exporter PostgreSQL ni Vault ; santé vue par le canari | Diagnostic fin de la base | Le canari teste la base par une vraie transaction, ce qui compte pour le métier |

## 3. Recommandations, par priorité

| # | Recommandation | Gain attendu | Élément vérifiable pour décider et suivre |
|---|---|---|---|
| 1 | **Généraliser la preuve par transaction** (canari) à tous les services critiques et en faire l'indicateur de disponibilité contractuel | Mesure de la disponibilité vue du client, pas du serveur | `canary_success_ratio`, `canary_up` ; durée des incidents `remediation_duration_seconds` |
| 2 | **Haute disponibilité** : au moins deux hôtes, base répliquée, sauvegardes testées et restauration à un instant donné | Supprime le point unique de panne (risque résiduel n°1) | Test de restauration trimestriel chronométré (RTO / RPO mesurés, pas estimés) |
| 3 | **Voir l'IP réelle du client** (répartiteur ou TLS en bordure, en-têtes de confiance) | Un ban ne touche que l'attaquant | Nombre de clients légitimes bloqués par incident (doit tendre vers 0) |
| 4 | **Entraîner la détection sur l'historique réel** (plusieurs semaines) et suivre ses erreurs avec les opérateurs | Moins de faux positifs, détection plus tôt | Taux de faux positifs et délai de détection par incident (`ml_alerts_sent_total`, journal) |
| 5 | **Processus de notification DORA** : modèle de rapport alimenté par le journal d'incidents, responsable désigné | Délais réglementaires tenus | Rapport Markdown de chaque incident, intégrité du journal (`/journal/verify`) |
| 6 | **Tests de résilience réguliers** : chaos (arrêt de service) mensuel, puis TLPT encadré | Les plans restent vrais dans le temps | Fiches de [`../test-results/`](../test-results/) ; part d'incidents clos `CLOSED` sans intervention |

## 4. Ce que nous ferions différemment dans un contexte industriel

- **Orchestrateur** (Kubernetes ou équivalent) avec redémarrage et répartition natifs ; le moteur
  de remédiation garderait les décisions métier (ban, vérification par transaction).
- **TLS partout** et gestion des identités d'entreprise (MFA), rotation automatique des secrets.
- **Exporters** pour la base, Vault et le WAF, et un SIEM dimensionné pour la corrélation.
- **Revue humaine des playbooks** et tests automatiques de chaque action avant mise en service.
- **Organisation** : responsable d'incident, cellule de crise, astreinte, exercices réguliers
  (voir PCA/PRA §4).

## 5. Limites à connaître avant de décider

- Le chemin **DoS → détection ML → remédiation** est démontré (6 essais sur 6, [répétition du
  22/10](../test-results/repetition-generale.md)), mais avec des **limites de débit volontairement
  relâchées** : aux réglages par défaut, le WAF absorbe l'attaque et c'est la règle SOC qui bannit
  l'attaquant ([calibrage](../test-results/calibrage-attaque-dos.md)). Le chemin **panne de service
  → remédiation → transaction de contrôle** est démontré ([répétition du 21/10](../test-results/repetition-boucle-reprise.md)).
- La répétition a révélé et fait corriger trois défauts que les tests unitaires ne voyaient pas
  (vérification sur métriques périmées, réalertes en boucle, attaquant non banni) : argument pour
  la recommandation n°6 (tests de résilience réguliers en conditions réelles).
- Les montants d'impact (PCA/PRA §2) reposent sur des **hypothèses fictives** à valider avec le
  métier.
- Une reprise automatique ne prouve pas l'absence de compromission (PCA/PRA §3 ter).
