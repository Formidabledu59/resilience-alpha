# Durcissement de la plateforme

Synthèse des mesures de sécurité de Resilience-Alpha, par couche. Chaque mesure est vérifiable dans le dépôt (docker-compose.yml, configs) ou au runtime.

## 1. Exposition réseau (moindre exposition)

- **Un seul port publié** : le WAF, sur `192.168.137.1:80` (jamais `0.0.0.0` : le PC Hôte est aussi sur le WiFi du campus).
- Interfaces d'administration liées à `127.0.0.1` uniquement (Grafana, Prometheus, dashboard, assistant).
- **7 réseaux Docker cloisonnés**, dont 5 `internal: true` (aucun accès Internet, aucun port publiable) : `app-net`, `data-net`, `obs-net`, `admin-net`, `logs-net`.
- La base, Vault, Loki, Alloy, le détecteur ML, le moteur de remédiation et les socket-proxy n'ont **aucun port publié**.
- Le moteur de remédiation n'est **jamais** sur `app-net` : il vérifie la reprise via la métrique du canari, sans accès direct aux services métier.

## 2. Durcissement des conteneurs

Bloc commun `x-hardening` appliqué partout :

- `security_opt: [no-new-privileges:true]` : un processus ne peut pas élever ses privilèges.
- `restart: unless-stopped`, rotation des journaux (10 Mo x 3).

Par service, quand l'image le permet :

- **Non-root** : uid dédié (10001 pour nos services Python, 101 pour nginx, 70 pour postgres, 65534 pour Prometheus/Alertmanager, 10001 pour Loki, 473 pour Alloy, `vault`/`grafana` pour leurs images).
- **`read_only: true`** : système de fichiers racine en lecture seule (sauf WAF et vault-init, qui écrivent leur config au démarrage, et Grafana sous tmpfs).
- **`cap_drop: [ALL]`** : toutes les capacités Linux retirées. Seules exceptions, minimales et justifiées : `IPC_LOCK` (Vault, verrouillage mémoire), `CHOWN` (vault-init, droits du token).
- **`tmpfs`** pour les répertoires temporaires, plutôt qu'un système de fichiers inscriptible.

## 3. Secrets

- **Aucun secret en clair dans le dépôt** (public) : uniquement des `${VAR}` lues depuis `.env` (ignoré par Git), documentées dans `.env.example` avec des valeurs factices.
- **HashiCorp Vault** stocke `jwt_secret` et `postgres_password`. auth-service et payment-api les lisent via un token de service en **lecture seule** (politique `app-ro`). Détails : [`vault/README.md`](vault/README.md).
- Clés d'unseal et root token hors du dépôt (volume Docker), jamais affichés par `init.sh`.
- **gitleaks** scanne tout l'historique Git à chaque push (CI).

## 4. Accès au socket Docker (moindre privilège)

- `/var/run/docker.sock` n'est monté que par deux proxies, en lecture seule, jamais par un service applicatif.
- **`socket-proxy-ro`** (pour Alloy) : lecture seule (`CONTAINERS=1`, `NETWORKS=1`, `POST=0`).
- **`socket-proxy-rw`** (pour la remédiation) : minimum pour recharger / relancer (`POST=1`, `ALLOW_RESTARTS=1`, `CONTAINERS=0` pour interdire la création de conteneurs).

## 5. Pare-feu applicatif (WAF)

- Nginx + ModSecurity v3 + OWASP Core Rule Set, point d'entrée unique.
- Blocage des injections SQL, XSS, accès fichiers, Log4Shell, scanners (vérifié, réponses 403).
- Rate-limit par client (réglable), liste de bannissement rechargeable à chaud.
- Journaux d'accès et d'audit en JSON vers Loki. Détails : [`waf/README.md`](waf/README.md).

## 6. Détection (SOC)

- Règles SOC ([`soc-rules/`](soc-rules/)) évaluées par le ruler de Loki sur les journaux WAF et auth-service : blocages ModSecurity, saturation du rate-limit, scanner détecté, échecs de connexion répétés.
- Les alertes partent vers Alertmanager (vérifié) et, à terme, vers le moteur de remédiation.
- Dashboards Grafana « Resilience - Vue globale » et « Resilience - Frontal et sécurité ».

## 7. Chaîne d'approvisionnement

- **Toutes les images sont épinglées** à une version exacte (jamais `latest`), au-delà de deux semaines d'ancienneté.
- Dépendances Python et npm épinglées (`requirements.txt`, `package-lock.json`).
- CI : gitleaks, yamllint, tests Python et front à chaque push ; revue de PR avant merge.

## 8. Assistant RAG

- Lecture seule : aucun accès à Docker, Vault ou au moteur de remédiation (à implémenter avec ce principe).

## Limites connues (démo)

- **Vault** : 1 part de clé d'unseal, TLS désactivé sur le réseau interne, auto-unseal par le conteneur d'init, repli des secrets sur l'environnement pour le profile `app` seul. En production : plusieurs parts, TLS, auto-unseal KMS/HSM, pas de repli.
- **WAF / IP source** : derrière Docker Desktop (Windows), le WAF voit l'IP de la passerelle Docker pour tout le trafic externe. Un ban coupe tout l'externe pendant sa durée ; le canari interne prouve la reprise. Limite de l'environnement, pas du WAF.
- **HTTPS** : hors périmètre du laboratoire (pas de nom de domaine ni de certificat). En production : TLS au WAF, HSTS.
- **`read_only` partiel** : le WAF et vault-init génèrent leur configuration au démarrage et ne sont donc pas en lecture seule intégrale (durcissement conservé par ailleurs).

Mesures encore à mettre en place : voir [`docs/etat-des-lieux.md`](../docs/etat-des-lieux.md).
