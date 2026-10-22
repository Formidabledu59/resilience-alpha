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

## 2. Objectifs de temps et de perte (RTO / RPO)

| Service | RTO visé (POC) | RPO | Justification |
|---|---|---|---|
| `payment-api` | < 2 min | ~0 | Redémarrage automatique + transaction atomique (aucune transaction à moitié écrite) |
| `auth-service` | < 2 min | 0 (comptes en mémoire) | Redémarrage ; émission de JWT reprise immédiatement |
| `postgres` | < 5 min | 0 à la dernière transaction validée | Volume persistant ; transactions SQL atomiques |
| Chaîne complète (reprise prouvée) | **< 3 min** | ~0 | Mesuré en répétition : ~67 s (voir `docs/test-results/repetition-boucle-reprise.md`) |

> Repères du POC, pas des engagements contractuels. En répétition, un arrêt de `payment-api`
> a été détecté et réparé (redémarrage, canari nominal, transaction de contrôle COMPLETED) en
> environ une minute.

---

## 3. Scénarios de sinistre et stratégie de reprise

| Scénario | Détection | Réponse automatique | Preuve de reprise |
|---|---|---|---|
| Déni de service applicatif | ml-detector (score) / SOC (429) | Ban de la source au WAF, vérification | Canari nominal + `POST /probe` |
| Indisponibilité d'un service | Prometheus `TargetDown` | `restart_api.yml` (via socket-proxy-rw) | Canari nominal + `POST /probe` |
| Attaque applicative (injection) | WAF (403) + SOC | Blocage en amont (aucune action requise) | Service jamais dégradé |
| Force brute | SOC (401 répétés) | Ban de la source | Canari nominal |
| Panne de la base | Canari en échec | (hors périmètre auto : restart manuel) | Transaction de contrôle |

Stratégie commune : **détecter → agir (playbook de la liste blanche) → vérifier le retour au
nominal → prouver par une transaction → clôturer**. Tout est tracé dans le journal d'incidents
(chaîné SHA-256), avec un rapport par incident.

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
| Arrêt d'un service | `docker stop payment-api` | Reprise auto en ~67 s, transaction prouvée | `docs/test-results/repetition-boucle-reprise.md` |
| Attaque DoS | `attack/dos/flood.py` | WAF absorbe ; calibrage réseau à finaliser | `docs/test-results/calibrage-attaque-dos.md` |
| Injection SQL / XSS | `attack/sqli/inject.py` | Bloquée (403) par le CRS | `security/waf/README.md` |
| Ban puis levée au WAF | Écriture banlist + HUP | Trafic coupé puis rétabli, canari non touché | `security/waf/README.md` |

À compléter : rejouer le scénario de bout en bout `tests/e2e/resilience_scenario.py` depuis le
PC Attaquant, avec un DoS calibré pour déclencher le chemin ML.

---

## 7. Risques résiduels

- **Mono-hôte** : pas de haute disponibilité réelle ; une panne du PC Hôte arrête tout. En
  production : plusieurs hôtes, orchestrateur, bascule automatique.
- **Dépendance à Docker Desktop (Windows)** : IP client masquée, un ban coupe tout l'externe.
- **Modèle ML sur trafic simulé** : à ré-entraîner sur données réelles.
- **Pas de sauvegarde externalisée** de la base dans le POC (données fictives) : en production,
  sauvegardes régulières testées et réplication.

Ces limites sont assumées pour le démonstrateur et listées comme axes d'industrialisation.
