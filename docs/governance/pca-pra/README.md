# Plan de continuité et de reprise d'activité (PCA / PRA)

> Appliqué au démonstrateur Resilience Alpha (groupe 16). Cadre laboratoire, données fictives.
> Le POC illustre une **reprise autonome (Zero-Touch Recovery)** : la plateforme détecte un
> incident et revient à un état métier utilisable sans intervention humaine, la reprise étant
> prouvée par une transaction de paiement réussie.

---

## 1. Périmètre et objectifs

| Élément | Valeur |
|---|---|
| Activité couverte | Service de paiement fictif (authentification, transactions) |
| Objectif PCA | Maintenir ou rétablir le service malgré une attaque ou une panne |
| Objectif PRA | Revenir à un état nominal et le **prouver** par une transaction de contrôle |
| Mode nominal | Boucle de reprise automatique ; l'humain supervise (dashboard) et consulte (assistant RAG) |

Principe directeur : **un conteneur qui redémarre ne prouve pas la reprise ; seule une
transaction métier réussie la prouve** (sonde canari + `POST /probe`).

---

## 2. Ce que coûte un arrêt du paiement (impact métier)

Hypothèses **fictives**, à valider avec le métier dans un cadre réel : la plateforme traite en
moyenne **20 paiements par seconde** (pointe ×3), panier moyen **80 €**, commission de
l'entreprise **0,8 %**. Une partie des clients réessaie plus tard ; au-delà de quelques minutes,
les partenaires basculent vers un autre prestataire.

| Durée d'arrêt | Paiements non traités | Montant bloqué | Effets au-delà de la perte directe |
|---|---|---|---|
| 1 min | ~1 200 | ~96 000 € | Réessais clients, quasi invisible pour les partenaires |
| 15 min | ~18 000 | ~1,4 M€ | Réclamations, appels au support, image dégradée |
| 1 h | ~72 000 | ~5,8 M€ | Partenaires qui basculent, pénalités contractuelles (SLA) |
| 4 h | ~290 000 | ~23 M€ | **Incident majeur DORA** probable (notification), exposition médiatique |

Lecture pour la direction : la perte directe (commissions) reste modérée à court terme, mais la
**confiance des partenaires et l'exposition réglementaire** croissent très vite au-delà de
quelques minutes. C'est ce qui fixe l'objectif ci-dessous : rétablir **en moins de 3 minutes**,
avant que l'arrêt ne devienne visible pour les partenaires (gravité 4 de l'événement redouté
ER1, [`../ebios-rm/`](../ebios-rm/)).

---

## 2 bis. Objectifs de temps et de perte (RTO / RPO)

| Service | RTO visé (POC) | Mesuré | RPO | Justification |
|---|---|---|---|---|
| Chaîne complète (reprise prouvée) | **< 3 min** | **~67 s** le 21/10 (arrêt de payment-api) | ~0 | Détection `TargetDown` ~40 s, action ~2 s, vérification ~65 s puis transaction de contrôle |
| `payment-api` | < 2 min | inclus ci-dessus | ~0 | Redémarrage automatique + transaction atomique (aucune transaction à moitié écrite) |
| `auth-service` | < 2 min | non mesuré seul | sans objet | Comptes de démonstration recréés au démarrage à partir de la configuration ; aucun état à perdre |
| `postgres` | < 5 min | **non testé, non automatisé** | 0 à la dernière transaction validée | Volume persistant et transactions atomiques ; pas de chemin de reprise automatique (voir §3) |

> Repères du POC, pas des engagements contractuels. **Critère de vérification modifié le
> 22/10** : la remédiation n'attend plus que le taux de succès du canari sur 60 s remonte à
> 95 % (65 s sur les 67 mesurées), mais 3 relevés consécutifs `canary_up = 1` (~15 s), tous
> postérieurs à l'action, avant la transaction de contrôle (réessayée jusqu'à 3 fois).
> **Mesuré le 22/10 sur DoS réel, détection ML** ([répétition générale](../../test-results/repetition-generale.md)) :
> 6 essais réussis sur 6, total de **37 à 75 s** (détection 20 à 51 s, remédiation et vérification
> 15 à 46 s), très en dessous de l'objectif de 3 minutes.

---

## 3. Scénarios de sinistre et stratégie de reprise

| Scénario | Détection | Réponse automatique | Preuve de reprise |
|---|---|---|---|
| Déni de service applicatif | ml-detector (score ≥ 0,7 sur 3 relevés) | Catégorie « anomalie » : `ban_ip.yml` (IP à plus de 100 refus WAF ou plus de 1 000 requêtes sur la fenêtre) puis `restart_api.yml` | Canari nominal + `POST /probe`. **Démontré le 22/10** ([répétition générale](../../test-results/repetition-generale.md)) |
| Saturation du WAF | SOC `WafRateLimitSature` (429) | Catégorie « dos » : `ban_ip.yml` seul | Canari nominal + `POST /probe` |
| Indisponibilité d'un service | Prometheus `TargetDown` | `restart_api.yml` (via socket-proxy-rw) | Canari nominal + `POST /probe`. **Démontré le 21/10** |
| Attaque applicative (injection) | WAF (403) + SOC | Blocage en amont (aucune action requise) | Service jamais dégradé |
| Force brute | SOC (401 répétés) | `ban_ip.yml` (si 100 refus) | Canari nominal. **Non testé** |
| Panne de la base | Canari en échec (postgres n'est pas scrapé : pas de `TargetDown`) | Pas de chemin automatique. Le ML peut ouvrir un incident « anomalie » et relancer payment-api inutilement : l'incident finit `FAILED`, ce qui déclenche l'escalade humaine (runbook) | Transaction de contrôle |

Stratégie commune : **détecter → agir (playbook de la liste blanche) → vérifier le retour au
nominal → prouver par une transaction → clôturer**. Tout est tracé dans le journal d'incidents
(chaîné SHA-256), avec un rapport par incident.

### Choix de restauration (et pourquoi)

| Choix | Pourquoi | Ce qu'on accepte |
|---|---|---|
| **Relancer** le service plutôt que le reconstruire | Image saine et figée, état en base : un redémarrage suffit et prend quelques secondes | Ne corrige pas une compromission (voir §3 ter) |
| **Ban temporaire** (5 min) plutôt que permanent | Un déni de service s'arrête ; un ban permanent risquerait de bloquer un client légitime | L'attaquant peut revenir après 5 min (nouvel incident, nouveau ban) |
| Ban de l'IP vue par le WAF, même partagée | Derrière Docker Desktop, toutes les IP externes sont la même passerelle : c'est la seule action possible au WAF | Tout l'externe est coupé pendant le ban ; le canari interne prouve que le service tourne |
| Preuve par **transaction de contrôle** | Seule preuve métier ; un conteneur `running` ne dit rien du paiement | Une transaction fictive de plus en base |
| **Liste blanche** de playbooks | Le moteur ne peut rien faire d'autre que ce qui est prévu, même s'il est trompé | Un incident imprévu finit `FAILED` et passe à l'humain |

---

## 3 ter. Rétablir le service n'est pas traiter une compromission

La boucle automatique rétablit la **disponibilité**. Elle ne prouve **pas** l'absence de
compromission ou de fuite : une injection réussie, un vol de jeton ou une exfiltration ne font
pas forcément tomber le service. Ces cas suivent un autre chemin, **humain**, déclenché par le
SOC (blocages WAF, échecs de connexion, comportement anormal) :

1. **Isoler** : couper l'exposition (WAF), garder les conteneurs pour analyse.
2. **Préserver les preuves** : journaux Loki, journal d'incidents chaîné (`/journal/verify`).
3. **Vérifier l'intégrité des données** : soldes et transactions cohérents (événement redouté ER2).
4. **Reconstruire** depuis des images saines, **changer tous les secrets** (Vault : `jwt_secret`,
   `postgres_password`), invalider les jetons en cours.
5. **Évaluer les notifications** : RGPD (72 h si données personnelles), NIS2 / DORA (incident
   majeur). Runbooks [RB6 et RB7](../../runbooks/).

---

## 4. Rôles et responsabilités

Le projet n'attribue pas de rôle nominatif (chaque membre intervient sur tous les piliers). En
fonctionnement, les responsabilités sont **fonctionnelles** :

| Rôle | Porté par | Responsabilité |
|---|---|---|
| Détection | `ml-detector`, règles SOC, Prometheus | Lever l'alerte |
| Décision et action | `remediation-engine` + playbooks Ansible | Choisir et exécuter la remédiation |
| Vérification | `canary` + Prometheus | Confirmer la reprise par une vraie transaction |
| Supervision | Opérateur via le dashboard (`127.0.0.1:5173`) | Suivre les phases et les incidents |
| Aide à la décision | Assistant RAG (`127.0.0.1:8501`) | Retrouver les procédures (lecture seule) |
| Escalade | Opérateur humain | Reprendre la main si un incident passe en `FAILED` |

Dans un cadre industriel, il faudrait ajouter les rôles **organisationnels** que le POC ne
couvre pas : responsable de l'incident (décide et communique), cellule de crise (direction,
métier, juridique), délégué à la protection des données (RGPD), contact réglementaire
(notification NIS2 / DORA), astreinte 24/7.

---

## 5. Procédures de reprise

### 5.1 Reprise automatique (nominale)

Aucune action : la boucle détecte, agit, vérifie et clôture. L'opérateur observe les phases
Avant / Pendant / Remédiation / Après sur le dashboard.

### 5.2 Reprise manuelle (si un incident passe en `FAILED`)

1. Consulter le journal de l'incident (dashboard, section Journal) et son rapport Markdown.
2. Suivre le runbook correspondant ([`../../runbooks/`](../../runbooks/)).
3. Relancer le service si besoin, puis valider par une transaction de contrôle
   (bouton « Lancer une transaction de contrôle » du dashboard, ou `POST /probe`).
4. Vérifier `canary_up = 1` dans Prometheus.

### 5.3 Reprise complète de la plateforme (PC Hôte)

1. Activer le point d'accès `RESILIENCE-G16` **avant** Docker.
2. `docker compose up -d` puis `docker compose --profile app --profile security --profile ia --profile remediation up -d --build`.
3. Vérifier que les conteneurs sont `healthy` et `canary_up = 1`.

---

## 6. Tests du plan (chaos engineering)

| Test | Méthode | Résultat | Référence |
|---|---|---|---|
| Arrêt d'un service | `docker stop payment-api` | Reprise auto en ~67 s, transaction prouvée (critère de vérification raccourci le 22/10 : à re-mesurer) | `docs/test-results/repetition-boucle-reprise.md` |
| Attaque DoS | `attack/dos/flood.py` | WAF absorbe ; calibrage réseau à finaliser | `docs/test-results/calibrage-attaque-dos.md` |
| Injection SQL / XSS | `attack/sqli/inject.py` | Bloquée (403) par le CRS | `security/waf/README.md` |
| Ban puis levée au WAF | Écriture banlist + HUP | Trafic coupé puis rétabli, canari non touché | `security/waf/README.md` |

À compléter : rejouer le scénario de bout en bout `tests/e2e/resilience_scenario.py` (sur le PC
Hôte, attaque vers `192.168.137.1`), avec un DoS calibré pour déclencher le chemin ML.
Non testés à ce jour : force brute → ban, panne de la base.

---

## 7. Risques résiduels

- **Mono-hôte** : pas de haute disponibilité réelle ; une panne du PC Hôte arrête tout. En
  production : plusieurs hôtes, orchestrateur, bascule automatique.
- **Dépendance à Docker Desktop (Windows)** : IP client masquée, un ban coupe tout l'externe.
- **Modèle ML sur trafic simulé** : à ré-entraîner sur données réelles.
- **Pas de sauvegarde externalisée** de la base dans le POC (données fictives) : en production,
  sauvegardes régulières testées et réplication.

Ces limites sont assumées pour le démonstrateur. Les arbitrages et les recommandations à la
direction sont dans [`../recommandations.md`](../recommandations.md).
