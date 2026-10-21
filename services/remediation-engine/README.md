# remediation-engine

Moteur de remédiation (FastAPI, port `8000`, aucun port publié, réseaux `obs-net` et `admin-net`, jamais `app-net`).
Il reçoit les alertes, ouvre un incident, rassemble les preuves, lance la remédiation, vérifie la reprise par une transaction métier, puis clôture. **Chaque étape est écrite dans un journal d'audit** : pour chaque attaque, on sait ce qui s'est passé, quelles erreurs ont été observées, comment la plateforme s'est défendue et si la reprise est prouvée.

> État : journal, webhooks, collecte des preuves et vérification de la reprise sont faits et testés. L'**exécution des playbooks Ansible** reste à brancher (voir « Brancher les playbooks »). En attendant, le journal indique « Playbooks prévus : ..., exécution pas encore branchée ».

## Fichiers

| Fichier | Rôle |
|---|---|
| `main.py` | API : webhooks authentifiés, lecture du journal, rapport, métriques |
| `engine.py` | Cycle de vie d'un incident, liste blanche des playbooks |
| `evidence.py` | Preuves en lecture seule : métriques dans Prometheus, blocages WAF et échecs de connexion dans Loki |
| `incidents.py` | Bilan : catégorie, types d'attaque, erreurs observées, défenses, résumé, rapport Markdown |
| `journal.py` | Journal JSON Lines en ajout seul, chaîné par SHA-256 |

## Cycle d'un incident

```
alerte (ML signée HMAC, ou Alertmanager avec bearer)
  -> OPEN         incident ouvert, ou alerte rattachée à l'incident actif de même catégorie
  -> preuves      Prometheus + Loki sur la fenêtre [première alerte - 5 min, maintenant]
  -> REMEDIATING  playbooks de la liste blanche selon la catégorie
  -> VERIFYING    attente canary_up = 1 et taux de succès >= 95 % (180 s max), puis POST /probe au canary
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

## Brancher les playbooks

`Engine` accepte un `executor` : une fonction `async (playbook, incident) -> str` qui exécute le playbook et renvoie un résultat lisible (par exemple « 172.23.0.1 bannie pour 5 minutes »), ou lève une exception en cas d'échec. Seuls les playbooks de `PLAYBOOKS` (`engine.py`) sont appelés. Le résultat est journalisé et apparaît dans la colonne « Défense » du dashboard. Il faudra ajouter Ansible à l'image et passer l'exécuteur dans `main.py`.

## Variables

| Variable | Rôle |
|---|---|
| `REMEDIATION_HMAC_SECRET`, `REMEDIATION_BEARER_TOKEN` | Authentification des webhooks (`.env`) |
| `PROMETHEUS_URL`, `LOKI_URL`, `CANARY_URL` | Sources des preuves et transaction de contrôle |
| `JOURNAL_PATH` | Fichier du journal (défaut `/journal/incidents.jsonl`) |
| `VERIFY_TIMEOUT_SECONDS` | Délai maximal de retour au nominal (défaut 180) |

## Tests

```powershell
cd services/remediation-engine
pip install -r requirements.txt pytest
python -m pytest
```

22 tests : chaîne SHA-256 (falsification et suppression détectées), classification, types d'attaque, erreurs, bilan, rapport, cycle complet (clôture, échec du canari, échec de la transaction de contrôle, playbooks, regroupement des alertes, redémarrage), webhooks (HMAC valide, mauvais secret, rejeu, bearer).
