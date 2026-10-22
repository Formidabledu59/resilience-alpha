# Contrats d'API - chaîne de paiement

Référence commune pour toute l'équipe : dev (services), infra (compose, Prometheus), ia (variables du détecteur), cyber (WAF), gouv (dossier).
Toute évolution d'un endpoint ou d'une métrique se fait **d'abord ici**, puis dans le code.

## Conventions communes

| Élément | Règle |
|---|---|
| Port | Tous les services FastAPI écoutent sur `8000` |
| Santé | `GET /health` : `200 {"status": "ok"}` : le processus est vivant (aucune dépendance testée) |
| Métriques | `GET /metrics` au format Prometheus, scrapé toutes les 5 s |
| Authentification | `Authorization: Bearer <JWT>` sur tous les endpoints métier de `payment-api` |
| Format | JSON, montants en chaîne ou nombre décimal à 2 décimales, devise `EUR` uniquement |
| Données | Exclusivement fictives |

Les services n'ont **aucun port publié** : ils sont joignables uniquement sur `app-net` et, depuis l'extérieur, via le WAF puis le frontal (relais `/api`).

---

## auth-service

### `POST /auth/token`

Requête :

```json
{ "username": "demo", "password": "..." }
```

Réponses :

| Code | Corps | Cas |
|---|---|---|
| `200` | `{"access_token": "<JWT>", "token_type": "bearer", "expires_in": 900}` | Identifiants valides |
| `401` | `{"detail": "Identifiants invalides"}` | Utilisateur inconnu ou mauvais mot de passe |
| `422` | erreur de validation FastAPI | Champ manquant |

JWT : algorithme `HS256`, signé avec `JWT_SECRET`, claims `sub` (nom d'utilisateur), `iat`, `exp` (15 minutes).

Utilisateurs fictifs créés au démarrage, en mémoire, mots de passe hashés (PBKDF2-SHA256) :

| Utilisateur | Mot de passe | Usage |
|---|---|---|
| `demo` | `AUTH_DEMO_PASSWORD` | Tests manuels, frontal |
| `canary` | `AUTH_CANARY_PASSWORD` | Sonde canari |

Métriques : latence et nombre de requêtes HTTP (`http_request_duration_seconds`, `http_requests_total`, via `prometheus-fastapi-instrumentator`).

---

## payment-api

### Comptes fictifs (créés au démarrage s'ils n'existent pas)

| Compte | Solde initial (EUR) | Usage |
|---|---|---|
| `ACC-001` | 1000.00 | Démo |
| `ACC-002` | 500.00 | Démo |
| `CANARY-A` | 100.00 | Sonde canari |
| `CANARY-B` | 100.00 | Sonde canari |

### `POST /transactions` (Bearer JWT)

Requête :

```json
{ "from_account": "ACC-001", "to_account": "ACC-002", "amount": 10.50, "currency": "EUR" }
```

| Code | Corps | Cas |
|---|---|---|
| `201` | `{"id": 42, "status": "COMPLETED"}` | Débit et crédit effectués dans une même transaction SQL |
| `201` | `{"id": 43, "status": "REJECTED"}` | Solde insuffisant : rien n'est débité, la tentative est tracée |
| `401` | `{"detail": "..."}` | Token absent, invalide ou expiré |
| `404` | `{"detail": "Compte inconnu : ..."}` | Compte source ou destination inexistant |
| `422` | erreur de validation | Montant ≤ 0, devise différente de `EUR`, comptes identiques |

### `GET /transactions/{id}` (Bearer JWT)

`200` :

```json
{ "id": 42, "from_account": "ACC-001", "to_account": "ACC-002", "amount": "10.50",
  "currency": "EUR", "status": "COMPLETED", "created_at": "2026-10-19T12:00:00+00:00" }
```

`404` si la transaction n'existe pas.

### `GET /accounts/{id}` (Bearer JWT)

`200` : `{"id": "ACC-001", "balance": "989.50", "currency": "EUR"}` - `404` si le compte n'existe pas.

### Métriques

| Métrique | Type | Labels |
|---|---|---|
| `payment_transactions_total` | counter | `status` = `COMPLETED` \| `REJECTED` |
| `http_request_duration_seconds` | histogram | `handler`, `method` |
| `http_requests_total` | counter | `handler`, `method`, `status` |

---

## canary

Sonde métier : toutes les `CANARY_INTERVAL_SECONDS` (5 s par défaut), elle obtient un token (mis en cache, renouvelé avant expiration) et exécute une transaction de **1 EUR** entre `CANARY-A` et `CANARY-B`, en **alternant le sens** pour ne jamais vider les comptes.

Une transaction est un **succès** uniquement si `payment-api` répond `201` avec `status = COMPLETED`. Tout le reste (erreur réseau, `401`, `5xx`, `REJECTED`) est un **échec**.

Cibles configurables : `AUTH_URL` et `PAYMENT_URL`, toutes deux `http://waf:8080/api`. Le canary passe par le WAF comme un vrai client (WAF, frontal, puis API) : il mesure aussi l'effet d'une attaque ou d'un blocage au WAF. Il arrive par le réseau interne `app-net`, avec sa propre IP : un ban du trafic externe ne le touche pas.

### `POST /probe`

Exécute immédiatement une transaction de contrôle (utilisé par `remediation-engine` pour clôturer un incident).

`200` :

```json
{ "ok": true, "status": "COMPLETED", "transaction_id": 128, "latency_seconds": 0.042, "detail": null }
```

En cas d'échec : `ok: false`, `status` vaut le statut métier ou `ERROR`, `detail` décrit la cause.

### Métriques

| Métrique | Type | Signification |
|---|---|---|
| `canary_up` | gauge | `1` si la dernière transaction a réussi, `0` sinon |
| `canary_success_ratio` | gauge | Taux de succès sur les 60 dernières secondes (0 à 1) |
| `canary_latency_seconds` | histogram | Durée d'une transaction (token compris si renouvelé) |
| `canary_transactions_total` | counter | `result` = `success` \| `failure` |

`remediation-engine` considère la reprise acquise quand `canary_up == 1` et `canary_success_ratio` est revenu à un niveau nominal, **puis** qu'un `POST /probe` renvoie `ok: true`.

---

## Variables d'environnement

| Variable | Services | Rôle |
|---|---|---|
| `JWT_SECRET` | auth-service, payment-api | Clé de signature HS256 (lue dans Vault, `secret/payment`, repli sur la variable) |
| `AUTH_DEMO_PASSWORD` | auth-service | Mot de passe de `demo` |
| `AUTH_CANARY_PASSWORD` | auth-service, canary | Mot de passe de `canary` |
| `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | payment-api | Connexion à la base |
| `AUTH_URL`, `PAYMENT_URL` | canary | Cibles de la sonde |
| `CANARY_INTERVAL_SECONDS` | canary | Intervalle entre deux transactions |

---

## frontend (relais nginx)

Le navigateur n'appelle que `/api/*` sur la même origine. Le nginx du frontal relaie :

| URL du navigateur | Cible | Limite |
|---|---|---|
| `POST /api/auth/token` | `auth-service:8000/auth/token` | 10 par minute par client (429 au-delà) |
| `/api/transactions`, `/api/transactions/{id}` | `payment-api:8000/transactions...` | 10 par seconde par client |
| `GET /api/accounts/{id}` | `payment-api:8000/accounts/{id}` | 10 par seconde par client |

Tout autre chemin `/api/` renvoie 404. Corps limité à 16 Ko (413 au-delà).

## dashboard (relais nginx, lecture seule)

| URL du navigateur | Cible | Méthode |
|---|---|---|
| `/api/prometheus/query` | `prometheus:9090/api/v1/query` | GET |
| `/api/prometheus/query_range` | `prometheus:9090/api/v1/query_range` | GET |
| `/api/canary/probe` | `canary:8000/probe` | POST (6 par minute) |
| `/api/remediation/incidents` | `remediation-engine:8000/incidents` | GET |
| `/api/remediation/journal/verify` | `remediation-engine:8000/journal/verify` | GET |
| `/api/remediation/incidents/inc-AAAA-MM-JJ-NNN/report` | `remediation-engine:8000/incidents/<id>/report` | GET (identifiant contrôlé par une expression régulière) |

---

## Interfaces prévues (attendues par le dashboard)

### remediation-engine : `GET /incidents?limit=10`

`200` : liste des incidents, du plus récent au plus ancien (`limit` de 1 à 100). Chaque incident est l'état complet tenu dans le journal d'audit (voir [`services/remediation-engine/README.md`](../../services/remediation-engine/README.md)). Champs minimaux :

```json
[
  {
    "id": "inc-2026-10-19-001",
    "trigger": "Anomalie ML sur payment-api",
    "source": "ml-detector",
    "status": "CLOSED",
    "opened_at": "2026-10-19T14:00:05+00:00",
    "closed_at": "2026-10-19T14:01:20+00:00",
    "steps": [
      { "at": "2026-10-19T14:00:05+00:00", "action": "Alerte reçue (HMAC valide)", "result": "score 0.91" },
      { "at": "2026-10-19T14:00:07+00:00", "action": "Playbook ban_ip.yml", "result": "192.168.137.42 bannie" },
      { "at": "2026-10-19T14:00:40+00:00", "action": "Vérification canary_up", "result": "1" },
      { "at": "2026-10-19T14:01:20+00:00", "action": "Transaction de contrôle (POST /probe)", "result": "COMPLETED" }
    ]
  }
]
```

`status` : `OPEN` | `REMEDIATING` | `VERIFYING` | `CLOSED` | `FAILED`. Un incident n'est `CLOSED` qu'après une transaction de contrôle réussie.

Champs du bilan (état des lieux de l'incident), ajoutés à chaque mise à jour :

| Champ | Contenu |
|---|---|
| `category`, `category_label`, `severity` | `attaque_applicative`, `dos`, `reconnaissance`, `force_brute`, `indisponibilite`, `anomalie`, `autre` |
| `alerts[]` | `name`, `source`, `auth`, `at`, `summary`, `fingerprint` (Alertmanager) |
| `evidence.opening`, `evidence.closing` | `metrics` (canari, latence p95, 5xx, débit, avec les pires valeurs de la fenêtre), `waf` (`blocked_403`, `rate_limited_429`, `rules[]`, `clients[]`), `auth_failures` |
| `attack_types[]` | `label`, `count`, `rules` : familles de règles OWASP CRS déclenchées |
| `errors[]` | `type` (`HTTP 403`, `HTTP 429`, `HTTP 401`, `HTTP 5xx`, `Échec canari`), `count`, `meaning`, `detail` |
| `defenses[]` | `layer`, `action`, `result` |
| `steps[].kind` | `detection`, `analysis`, `action`, `verification`, `info` |
| `summary` | `what_happened`, `impact`, `defense`, `outcome`, `durations` |

### remediation-engine : journal et rapport

| Endpoint | Réponse |
|---|---|
| `GET /incidents/{id}` | L'incident, `404` si inconnu |
| `GET /incidents/{id}/report` | Rapport Markdown (`text/markdown`), `404` si inconnu |
| `GET /journal/verify` | `{"ok": true, "entries": 42, "last_hash": "..."}` ou `{"ok": false, "entries": 12, "broken_at_line": 13}` |

### remediation-engine : `POST /webhook/ml` (envoyé par ml-detector)

```json
{ "score": 0.91, "threshold": 0.7, "detected_at": "2026-10-20T14:00:00+00:00", "features": { "latency_p95": 1.2 } }
```

| En-tête | Valeur |
|---|---|
| `X-Resilience-Timestamp` | Heure d'envoi, secondes Unix |
| `X-Resilience-Signature` | `sha256=` + HMAC-SHA256 hexadécimal de `"<timestamp>.<corps brut>"` avec `REMEDIATION_HMAC_SECRET` |

`202 {"incident": "inc-..."}` si la signature est valide et date de moins de 5 minutes, `401` sinon, `422` si `score` ou `threshold` manque.

### remediation-engine : `POST /webhook/alertmanager`

Format webhook standard d'Alertmanager, en-tête `Authorization: Bearer <REMEDIATION_BEARER_TOKEN>`. Une alerte `firing` ouvre un incident (ou rejoint l'incident actif de même catégorie), une alerte `resolved` ajoute une étape à l'incident concerné.

### ml-detector : métriques

| Métrique | Type | Signification |
|---|---|---|
| `ml_anomaly_score` | gauge | Score d'anomalie courant, de 0 (normal) à 1 (anormal) |
| `ml_anomaly_threshold` | gauge | Seuil au-delà duquel une alerte est envoyée à la remédiation |

### WAF : bannissement (utilisé par remediation-engine)

Détails et justification : [`security/waf/README.md`](../../security/waf/README.md).

| Étape | Action |
|---|---|
| Bannir | Écrire `/banlist/<nom>.conf` (volume `waf-banlist`), une ligne `deny <ip>;` par adresse, mode 644 |
| Appliquer | `POST http://socket-proxy-rw:2375/containers/resilience-alpha-waf-1/kill?signal=HUP` (rechargement à chaud, sans coupure) |
| Lever | Supprimer le fichier, puis renvoyer `HUP` |

Réponse du WAF à une adresse bannie : `403`. Les bans sont temporaires (5 minutes conseillées), l'expiration est gérée par remediation-engine.

### Vault : secrets (lus par auth-service et payment-api)

Détails : [`security/vault/README.md`](../../security/vault/README.md). Moteur KV v2, chemin `secret/`.

| Chemin | Champ | Service |
|---|---|---|
| `secret/payment` | `jwt_secret` | auth-service, payment-api |
| `secret/database` | `postgres_password` | payment-api |

Les services lisent le token de service dans `/vault-token/service-token` (politique `app-ro`, lecture seule), puis récupèrent leurs secrets depuis Vault. Repli sur les variables d'environnement si Vault est absent (profile `app` seul).
