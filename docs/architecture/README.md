# Architecture

Vue d'ensemble technique de la plateforme. Le schéma complet et la liste des composants sont dans le [README principal, section 2](../../README.md#2-architecture) ; les contrats d'API et les métriques dans [`contracts.md`](contracts.md).

## Chemin d'une requête

```
client (PC Attaquant ou navigateur)
  -> waf (192.168.137.1:80, ModSecurity + OWASP CRS, rate-limit, liste de ban)
  -> frontend (nginx : pages React, relais /api avec son propre rate-limit)
       /api/auth/token  -> auth-service (JWT)
       /api/...         -> payment-api (vérifie le JWT, transaction atomique dans PostgreSQL)
```

Les secrets (`jwt_secret`, `postgres_password`) sont lus dans Vault au démarrage, avec repli sur les variables d'environnement si le profile `security` ne tourne pas.

Le `canary` passe par le même chemin (`http://waf:8080/api`) toutes les 5 secondes : une vraie transaction fictive, dont le résultat devient la métrique `canary_up` et `canary_success_ratio`.

## Boucle de reprise

```
Prometheus (métriques, 5 s) ──► ml-detector (Isolation Forest, score 0..1 toutes les 5 s)
                                   └─ score ≥ 0,7 sur 3 relevés ─► webhook HMAC ─┐
Prometheus (TargetDown) ─┐                                                       │
Loki (règles SOC) ───────┴─► Alertmanager ─► webhook bearer ─────────────────────┤
                                                                                 ▼
                                                                    remediation-engine
   1. ouvre un incident, rassemble les preuves (Prometheus + Loki)
   2. lance les playbooks Ansible de la liste blanche (ban_ip, restart_api) via socket-proxy-rw
   3. attend 3 relevés consécutifs canary_up = 1 (~15 s, tous après l'action), puis demande une transaction
      de contrôle au canary (réessayée jusqu'à 3 fois si un redémarrage est encore en cours)
   4. clôture (CLOSED) seulement si elle réussit, sinon FAILED ; tout est écrit dans un journal chaîné SHA-256
```

`remediation-engine` n'est jamais sur `app-net` : il ne parle aux services métier qu'à travers Prometheus et le canary.

## Réseaux

| Réseau | Rôle |
|---|---|
| `edge-net` | Exposition du WAF |
| `app-net` (interne) | WAF, frontal, API, canary, Prometheus |
| `data-net` (interne) | API, PostgreSQL, Vault |
| `obs-net` (interne) | Observabilité, détecteur, remédiation, dashboard |
| `admin-net` (interne) | remediation-engine et socket-proxy-rw |
| `logs-net` (interne) | Alloy et socket-proxy-ro |
| `ui-net` | Interfaces publiées sur `127.0.0.1` (Grafana, Prometheus, dashboard, assistant RAG) |

Seul le WAF est joignable depuis le réseau. Les interfaces d'exploitation ne sont publiées que sur `127.0.0.1` (PC Hôte).

## Hors Docker

- **Ollama** (modèle ≤ 8B) tourne en natif, sur le PC Hôte ou le PC délestage IA ; `assistant-rag` l'atteint par `OLLAMA_BASE_URL`.
- **Passerelle biométrique** (`biometrics/gateway`, port 8700), préparée mais **désactivée par défaut** (`BACKOFFICE_BIOMETRICS=false`) : quand elle est activée, elle tourne en natif pour accéder à la caméra ; le dashboard la joint par `host.docker.internal`, le boîtier ESP8266 par le point d'accès.
