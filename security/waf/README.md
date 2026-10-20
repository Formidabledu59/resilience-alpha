# security/waf : pare-feu applicatif

Point d'entrée **unique** de la plateforme : nginx + ModSecurity v3 + OWASP Core Rule Set 4 (image `owasp/modsecurity-crs:4.29.0-nginx-alpine-202609301109`, utilisateur non-root `nginx`, port 8080 dans le conteneur).

```
Client ou canary -> WAF (192.168.137.1:80) -> frontend:8080 -> /api -> auth-service, payment-api
```

| Fichier | Rôle |
|---|---|
| `nginx.conf` | Configuration du `server` : relais vers le frontal, rate-limit, liste de bannissement, journal JSON. Monté comme template (les `${VAR}` sont remplacées au démarrage) |
| `crs-exclusions.conf` | Exclusions du Core Rule Set, chacune justifiée. Monté comme `RESPONSE-999-EXCLUSION-RULES-AFTER-CRS.conf` |

## Protections

| Protection | Réglage | Réponse |
|---|---|---|
| ModSecurity + OWASP CRS | Paranoïa 1, blocage à partir d'un score d'anomalie de 5 | 403 |
| Rate-limit par client | `WAF_RATE_LIMIT` (défaut `50r/s`), rafale `WAF_RATE_BURST` (défaut 100) | 429 |
| Liste de bannissement | Fichiers `*.conf` du volume `waf-banlist` | 403 |
| Taille des requêtes | 64 Ko maximum | 413 |
| Version de nginx masquée | `server_tokens off` | |

Attaques vérifiées (toutes bloquées) : injection SQL dans l'URL et dans le JSON (règle 942100), XSS (941100), accès à des fichiers système (930120), Log4Shell (944150), scanner Nikto (913100), traversée de répertoire (rejetée par nginx avant ModSecurity, 400).

Exclusion en place : **920350** « en-tête Host en adresse IP ». Le démonstrateur n'a pas de nom de domaine : sans cette exclusion, chaque requête légitime prendrait 3 points d'anomalie sur 5.

## Bannissement : contrat pour remediation-engine

1. **Écrire** un fichier dans le volume `waf-banlist` (monté sur `/banlist` dans remediation-engine), par exemple `/banlist/incident-<id>.conf` :

   ```nginx
   # Ban automatique, incident inc-2026-10-19-001, expire 2026-10-19T14:05:00Z
   deny 172.23.0.1;
   ```

   Une ligne `deny <ip>;` par adresse. Fichier lisible par tous (mode 644).

2. **Recharger** le WAF à chaud, sans coupure : signal `HUP` au conteneur, via `socket-proxy-rw` (seule opération Docker autorisée, `ALLOW_RESTARTS=1`) :

   ```
   POST http://socket-proxy-rw:2375/containers/resilience-alpha-waf-1/kill?signal=HUP
   ```

3. **Lever le ban** : supprimer le fichier, puis renvoyer `HUP`. Les bans sont **temporaires** (5 minutes conseillées) : c'est remediation-engine qui gère l'expiration.

Vérifié à la main : ban écrit puis `HUP`, le trafic externe reçoit 403, le canary continue de passer (201) et `canary_up` reste à 1. Ban levé, le trafic repasse. Le WAF ne redémarre pas.

Point à régler dans remediation-engine : le volume est créé par Docker avec le propriétaire `root`. L'utilisateur 10001 de remediation-engine devra pouvoir y écrire (par exemple un conteneur d'initialisation qui fait `chown 10001` sur le volume).

## Limite importante : l'IP réelle du client

Avec Docker Desktop sous Windows, le trafic qui arrive par un port publié passe par un proxy interne : **le WAF voit l'IP de la passerelle du réseau `edge-net`** (par exemple `172.23.0.1`), pas l'IP réelle du client. Vérifié depuis le PC Hôte ; à confirmer depuis le PC Attaquant sur le réseau `RESILIENCE-G16`.

Conséquences :

- Bannir « l'IP source » bannit **tout le trafic externe** pendant la durée du ban (attaquant et autres clients du réseau).
- Le canary passe par le réseau Docker interne avec sa propre IP : **il n'est pas touché par le ban**, ce qui permet de prouver la reprise.
- Le rate-limit par client s'applique en pratique à l'ensemble du trafic externe.

C'est une limite de l'environnement (Docker Desktop), pas du WAF : sur un hôte Linux avec Docker natif, l'IP réelle est conservée.

## Logs (Loki, dashboard Grafana « Resilience - Frontal et sécurité »)

- Journal d'accès JSON : `client`, `method`, `path`, `status`, `duration`, `upstream_status`. Le WAF journalise l'IP du client (journal de sécurité, conservé 7 jours).
- Journal d'audit ModSecurity en JSON (requêtes bloquées), avec la règle déclenchée.

Panneaux Grafana : requêtes refusées par code (403, 429), règles ModSecurity déclenchées, clients bloqués.

## Tester

Le point d'accès doit être actif avant Docker pour publier sur `192.168.137.1`. Sans lui, mettre `WAF_BIND_IP=127.0.0.1` dans `.env` (développement sur le PC Hôte).

```powershell
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1/                                   # 200
curl.exe -s -o NUL -w "%{http_code}" "http://127.0.0.1/?id=1%27%20OR%20%271%27=%271"     # 403 (injection SQL)
```
