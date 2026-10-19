# Contrats d'API — chaîne de paiement

Référence commune pour toute l'équipe : dev (services), infra (compose, Prometheus), ia (variables du détecteur), cyber (WAF), gouv (dossier).
Toute évolution d'un endpoint ou d'une métrique se fait **d'abord ici**, puis dans le code.

## Conventions communes

| Élément | Règle |
|---|---|
| Port | Tous les services FastAPI écoutent sur `8000` |
| Santé | `GET /health` → `200 {"status": "ok"}` : le processus est vivant (aucune dépendance testée) |
| Métriques | `GET /metrics` au format Prometheus, scrapé toutes les 5 s |
| Authentification | `Authorization: Bearer <JWT>` sur tous les endpoints métier de `payment-api` |
| Format | JSON, montants en chaîne ou nombre décimal à 2 décimales, devise `EUR` uniquement |
| Données | Exclusivement fictives |

Les services n'ont **aucun port publié** : ils sont joignables uniquement sur `app-net` (puis via le WAF, plus tard).

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

`200` : `{"id": "ACC-001", "balance": "989.50", "currency": "EUR"}` — `404` si le compte n'existe pas.

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

Cibles configurables : `AUTH_URL` et `PAYMENT_URL`. Pour le POC, elles pointent directement vers `auth-service` et `payment-api` ; elles passeront par le WAF quand celui-ci sera en place.

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
| `JWT_SECRET` | auth-service, payment-api | Clé de signature HS256 (Vault plus tard) |
| `AUTH_DEMO_PASSWORD` | auth-service | Mot de passe de `demo` |
| `AUTH_CANARY_PASSWORD` | auth-service, canary | Mot de passe de `canary` |
| `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | payment-api | Connexion à la base |
| `AUTH_URL`, `PAYMENT_URL` | canary | Cibles de la sonde |
| `CANARY_INTERVAL_SECONDS` | canary | Intervalle entre deux transactions |
