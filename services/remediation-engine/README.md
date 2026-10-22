# remediation-engine

Moteur de remédiation (FastAPI, port `8000`, aucun port publié, réseaux `obs-net` et `admin-net`, jamais `app-net`).
Il reçoit les alertes, ouvre un incident, rassemble les preuves, lance la remédiation, vérifie la reprise par une transaction métier, puis clôture. **Chaque étape est écrite dans un journal d'audit** : pour chaque attaque, on sait ce qui s'est passé, quelles erreurs ont été observées, comment la plateforme s'est défendue et si la reprise est prouvée.

> État : journal, webhooks, collecte des preuves, **exécution des playbooks Ansible** et vérification de la reprise sont faits et testés. Boucle prouvée en conteneurs le 21/10 (arrêt de `payment-api`, `restart_api.yml`, transaction de contrôle `COMPLETED`, incident `CLOSED` en 67 s environ) : [`repetition-boucle-reprise.md`](../../docs/test-results/repetition-boucle-reprise.md).

## Fichiers

| Fichier | Rôle |
|---|---|
| `main.py` | API : webhooks authentifiés, lecture du journal, rapport, métriques |
| `engine.py` | Cycle de vie d'un incident, liste blanche des playbooks |
| `evidence.py` | Preuves en lecture seule : métriques dans Prometheus, blocages WAF et échecs de connexion dans Loki |
| `incidents.py` | Bilan : catégorie, types d'attaque, erreurs observées, défenses, résumé, rapport Markdown |
| `journal.py` | Journal JSON Lines en ajout seul, chaîné par SHA-256 |
| `playbooks.py` | Exécution des playbooks de la liste blanche (`AnsibleExecutor`), choix des IP à bannir et du service à relancer, levée automatique du ban |

## Cycle d'un incident

```
alerte (ML signée HMAC, ou Alertmanager avec bearer)
  -> OPEN         incident ouvert, ou alerte rattachée à l'incident actif de même catégorie
  -> preuves      Prometheus + Loki sur la fenêtre [première alerte - 5 min, maintenant]
  -> REMEDIATING  playbooks de la liste blanche selon la catégorie
  -> VERIFYING    attente canary_up = 1 sur 3 relevés consécutifs (~15 s) ou taux de succès >= 95 %
                  (180 s max), puis POST /probe au canary : seule cette transaction prouve la reprise
  -> CLOSED       si la transaction de contrôle réussit, FAILED sinon
  -> bilan        nouvelles preuves "après", résumé final
```

| Catégorie | Alertes | Playbooks (liste blanche) |
|---|---|---|
| Attaque applicative | `WafBlocagesModSecurity` | aucun : bloquée en amont par le WAF |
| Reconnaissance | `WafScannerDetecte` | aucun : bloquée en amont par le WAF |
| Déni de service | `WafRateLimitSature` | `ban_ip.yml` |
| Force brute | `EchecsConnexionRepetes` | `ban_ip.yml` |
| Anomalie ML | webhook `ml-detector` | `ban_ip.yml`, `restart_api.yml` |
| Indisponibilité | `TargetDown` | `restart_api.yml` |

Les types d'attaque sont déduits des règles OWASP CRS déclenchées (942 injection SQL, 941 XSS, 930 LFI, 932 RCE, 944 Log4Shell, 913 scanner, etc.).

## Ce que contient chaque incident

| Champ | Contenu |
|---|---|
| `category_label`, `trigger`, `severity`, `source` | Nature de l'incident et qui l'a détecté |
| `alerts` | Toutes les alertes reçues, avec leur authentification |
| `evidence.opening`, `evidence.closing` | Photographie avant / après : canari, latence p95, erreurs 5xx, débit, 403 et 429 du WAF, règles déclenchées, IP refusées, échecs de connexion |
| `attack_types` | Types d'attaque regroupés par famille de règles CRS |
| `errors` | Types d'erreurs observés (403, 429, 401, 5xx, échecs du canari), nombre et signification |
| `defenses` | Couches qui ont défendu : WAF ModSecurity, rate-limit, playbooks, vérification métier |
| `steps` | Chronologie horodatée (détection, analyse, action, vérification) |
| `summary` | Phrases prêtes à lire : ce qui s'est passé, impact, défense, issue, durées |

## Traçabilité

- **Journal** : `/journal/incidents.jsonl` (volume `remediation-journal`). Une ligne par changement d'un incident, avec son état complet. Rien n'est jamais réécrit.
- **Chaîne SHA-256** : chaque ligne contient l'empreinte de la précédente. Modifier ou supprimer une ligne casse la chaîne ; `GET /journal/verify` le détecte et le dashboard l'affiche.
- **Loki** : chaque écriture produit aussi une ligne JSON courte sur la sortie standard (`journal`, `incident`, `status`, `hash`), consultable dans Grafana avec `{service="remediation-engine"} | json`.
- **Redémarrage** : le journal est relu au démarrage. Un incident resté en cours est clôturé `FAILED` avec l'étape « Moteur redémarré pendant l'incident » : rien n'est perdu ni masqué.
- **Rapport** : `GET /incidents/{id}/report` produit un rapport Markdown (à joindre au dossier ou aux résultats d'essais).

## API

| Méthode | Chemin | Auth | Rôle |
|---|---|---|---|
| `POST` | `/webhook/ml` | HMAC-SHA256 | Alerte du détecteur ML |
| `POST` | `/webhook/alertmanager` | Bearer | Alertes SOC (Loki) et Prometheus |
| `GET` | `/incidents?limit=10` | aucune (réseau interne) | Incidents, du plus récent au plus ancien (100 max) |
| `GET` | `/incidents/{id}` | aucune | Un incident |
| `GET` | `/incidents/{id}/report` | aucune | Rapport Markdown |
| `GET` | `/journal/verify` | aucune | Intégrité de la chaîne |
| `GET` | `/health`, `/metrics` | aucune | Santé, métriques Prometheus |

Signature HMAC du détecteur ML (contrat détaillé dans [`contracts.md`](../../docs/architecture/contracts.md)) : en-têtes `X-Resilience-Timestamp` (secondes Unix) et `X-Resilience-Signature: sha256=<HMAC(REMEDIATION_HMAC_SECRET, "<timestamp>.<corps>")>`. Une signature de plus de 5 minutes est refusée (anti-rejeu).

Métriques : `remediation_incidents_total{category}`, `remediation_incidents_closed_total{category,status}`, `remediation_incidents_open`, `remediation_duration_seconds`, `remediation_alerts_total{source}`, `remediation_webhook_rejected_total{source}`, `remediation_journal_integrity`.

## Exécution des playbooks

`main.py` branche un `AnsibleExecutor` (`playbooks.py`) dans `Engine`. Ansible (`ansible-core`) est installé dans l'image, les playbooks sont montés depuis [`infra/ansible/`](../../infra/ansible/) sur `/ansible`, et toutes les actions Docker passent par `socket-proxy-rw`. Seuls les playbooks de `PLAYBOOKS` (`engine.py`) peuvent être lancés.

- **`ban_ip.yml`** : bannit les IP refusées au moins `BAN_MIN_REQUESTS` fois par le WAF pendant l'incident (le canary n'atteint jamais ce seuil), puis recharge le WAF. Le ban est **levé automatiquement** au bout de `BAN_MINUTES` par `unban_ip.yml`. S'il n'y a aucune IP au-dessus du seuil, le journal indique « pas de ban ».
- **`restart_api.yml`** : relance le service visé par l'alerte (label `job` de `TargetDown`, `payment-api` par défaut).

Chaque playbook se termine par une ligne `RESULT: <texte>` (par exemple « 172.23.0.1 bannie pour 5 minutes »), reprise dans le journal et dans la colonne « Défense » du dashboard. Un échec ou un dépassement de 90 s fait passer l'incident en `FAILED`.

> Derrière Docker Desktop, tout le trafic externe arrive au WAF avec l'IP de la passerelle Docker : un ban coupe tout l'externe pendant `BAN_MINUTES` (le canary, interne, n'est pas touché). Voir [`security/waf/README.md`](../../security/waf/README.md).

## Variables

| Variable | Rôle |
|---|---|
| `REMEDIATION_HMAC_SECRET`, `REMEDIATION_BEARER_TOKEN` | Authentification des webhooks (`.env`) |
| `PROMETHEUS_URL`, `LOKI_URL`, `CANARY_URL` | Sources des preuves et transaction de contrôle |
| `JOURNAL_PATH` | Fichier du journal (défaut `/journal/incidents.jsonl`) |
| `VERIFY_TIMEOUT_SECONDS` | Délai maximal de retour au nominal (défaut 180) |
| `VERIFY_STABLE_CHECKS` | Relevés consécutifs à `canary_up = 1` qui suffisent avant la transaction de contrôle (défaut 3). Le taux de succès, calculé sur 60 s, mettrait une minute à remonter |
| `PLAYBOOK_DIR` | Dossier des playbooks (défaut `/ansible/playbooks`) |
| `BAN_MINUTES` | Durée du ban avant levée automatique (défaut 5) |
| `BAN_MIN_REQUESTS` | Nombre de refus WAF à partir duquel une IP est bannie (défaut 100) |
| `DOCKER_HOST`, `ANSIBLE_CONFIG` | Accès Docker via `socket-proxy-rw` et configuration Ansible (fixés dans `docker-compose.yml`) |

## Tests

```powershell
cd services/remediation-engine
pip install -r requirements.txt pytest
python -m pytest
```

28 tests : chaîne SHA-256 (falsification et suppression détectées), classification, types d'attaque, erreurs, bilan, rapport, cycle complet (clôture, échec du canari, échec de la transaction de contrôle, playbooks, regroupement des alertes, redémarrage), webhooks (HMAC valide, mauvais secret, rejeu, bearer), playbooks (seuil des IP à bannir, service à relancer, ban puis levée automatique), reprise validée sans attendre la fenêtre de 60 s du taux de succès, canari instable refusé. Depuis la racine : `python tests/run_all.py --only remediation`.
