# CLAUDE.md — Contexte projet pour Claude Code

## Projet

PROJECT RESILIENCE-ALPHA, workshop EPSI Bac+5, **groupe 16**. Démonstrateur d'une plateforme de paiement fictive qui subit une attaque depuis un PC Attaquant, détecte l'anomalie par machine learning et se rétablit **sans intervention humaine**. La reprise est prouvée par une nouvelle transaction fictive réussie, pas par un simple redémarrage de conteneur.

La référence fonctionnelle complète est dans `README.md`. Le lire avant toute tâche importante.

## Organisation de l'équipe

- Pas de rôle attitré : chaque membre peut travailler sur tous les piliers (dev, infra, ia, cyber, gouv).
- Chacun commite avec son propre compte GitHub, pour que la contribution soit traçable dans l'historique.
- Les dossiers n'ont pas de « responsable » : ne pas en attribuer dans les README, la doc ou `CODEOWNERS`.

## Règles de travail sur les fichiers (IMPORTANT)

- Le dépôt est déjà cloné. La racine du dépôt est le dossier courant. **Ne jamais créer un sous-dossier `resilience-alpha/`** ni dupliquer l'arborescence.
- Avant de créer un fichier, vérifier s'il existe déjà. Si oui, le **modifier** au lieu d'en créer un nouveau.
- Respecter exactement l'arborescence décrite dans `README.md` section 3.
- Environnement : Windows + Docker Desktop (WSL2). Utiliser des fins de ligne LF pour les scripts shell, les Dockerfile et les fichiers YAML.
- Toujours indiquer la liste des fichiers créés ou modifiés à la fin d'une tâche.

## Stack imposée (ne pas en sortir)

| Domaine | Technologies |
|---|---|
| Services / API | Python FastAPI (Node.js ou Go uniquement si justifié) |
| Frontal et dashboard | React + Tailwind CSS |
| Orchestration | Docker Compose |
| Automatisation | Ansible (exécuté dans le conteneur `remediation-engine` ou via WSL2) |
| Observabilité | Prometheus, Grafana, Loki + Grafana Alloy, Alertmanager |
| Sécurité | Nginx + ModSecurity (OWASP CRS), HashiCorp Vault, docker-socket-proxy |
| IA | scikit-learn (Isolation Forest), Ollama natif hors Docker (modèle ≤ 8B), LangChain |
| Base de données | PostgreSQL |

Elastic Stack et Wazuh sont exclus (trop lourds pour le PC Hôte).

## Noms des services (à utiliser partout : compose, Prometheus, docs)

`waf`, `frontend`, `auth-service`, `payment-api`, `postgres`, `vault`, `canary`, `prometheus`, `alertmanager`, `loki`, `alloy`, `grafana`, `ml-detector`, `remediation-engine`, `socket-proxy-ro`, `socket-proxy-rw`, `dashboard`, `assistant-rag`.

Ollama n'est **pas** un service Docker : il tourne en natif (voir « Réseau et exposition »).

## Réseau et exposition

- PC Hôte : `192.168.137.1` (point d'accès Windows `RESILIENCE-G16`). Le point d'accès doit être actif **avant** le démarrage de Docker. **Ne jamais publier sur `0.0.0.0`** (le PC est aussi sur le WiFi du campus).
- `waf` : **seul port réseau**, `192.168.137.1:80` vers `8080` (image ModSecurity non-root).
- `grafana` `3000`, `prometheus` `9090`, `dashboard` `5173`, `assistant-rag` `8501` : publiés sur `127.0.0.1` uniquement, via `ui-net`.
- Réseaux Docker :

| Réseau | Type | Membres |
|---|---|---|
| `edge-net` | bridge | waf |
| `ui-net` | bridge | grafana, prometheus, dashboard, assistant-rag |
| `app-net` | internal | waf, frontend, auth-service, payment-api, canary, prometheus |
| `data-net` | internal | auth-service, payment-api, postgres, vault |
| `obs-net` | internal | prometheus, alertmanager, loki, alloy, grafana, ml-detector, canary, dashboard, remediation-engine |
| `admin-net` | internal | remediation-engine, socket-proxy-rw |
| `logs-net` | internal | alloy, socket-proxy-ro |

- Deux socket-proxy : `socket-proxy-ro` (`CONTAINERS=1`, `POST=0`) pour alloy ; `socket-proxy-rw` (minimum pour restart/reload) pour remediation-engine. **Seuls ces deux conteneurs montent `docker.sock`, en lecture seule.**
- `remediation-engine` n'est **jamais** sur `app-net` : il vérifie la reprise via la métrique canary dans Prometheus et demande au canary une transaction de contrôle.
- Ban IP : volume `waf-banlist`, rw pour remediation-engine, ro pour waf, puis reload du waf via `socket-proxy-rw`.
- Nom de projet Compose fixe (`name: resilience-alpha` dans `docker-compose.yml`) : les conteneurs s'appellent `resilience-alpha-<service>-1` (ex. `resilience-alpha-waf-1`), quel que soit le nom du dossier cloné. `remediation-engine` cible les conteneurs **par ces noms fixes** : `socket-proxy-rw` (`CONTAINERS=0`) ne lui permet pas de les lister. Ne pas renommer le projet ni utiliser `docker compose -p`.
- Webhook remediation : HMAC pour ml-detector, bearer token pour Alertmanager.
- Vault : `cap_add: [IPC_LOCK]` autorisé.
- Prometheus **ne scrape pas** `postgres` ni `vault` (pas d'exporter, pas d'accès à `data-net`). Choix assumé : la santé de la base est couverte par le canary, qui passe par une vraie transaction.
- Ollama tourne **en natif, hors Docker** : sur le PC Hôte via `http://host.docker.internal:11434`, ou sur le PC délestage IA via son IP `http://192.168.137.x:11434`. L'URL est fournie à `assistant-rag` par la variable `OLLAMA_BASE_URL` (`.env`), qui l'atteint via `ui-net` (bridge).

## Sécurité (non négociable)

- **Aucun secret en clair** dans le dépôt : pas de mot de passe, token, clé dans le code, le compose ou les configs. Utiliser des variables `${VAR}` lues depuis `.env` (ignoré par Git) et documentées dans `.env.example` avec des valeurs factices.
- Le dépôt est **public**.
- `remediation-engine` n'accède **jamais** directement à `/var/run/docker.sock` : uniquement via `socket-proxy-rw`, avec le minimum d'opérations autorisées.
- Webhook du moteur de remédiation authentifié (HMAC pour ml-detector, bearer token pour Alertmanager), liste blanche des playbooks exécutables.
- Conteneurs non-root quand c'est possible, `read_only` et `cap_drop: [ALL]` quand c'est compatible.
- L'assistant RAG est en lecture seule : aucun accès à Docker, Vault ou au moteur de remédiation.
- Les scripts de `attack/` prennent la cible en paramètre et refusent toute cible hors `192.168.137.0/24`.
- Données exclusivement fictives.

## Conventions Git

- Branches : `feat/<pilier>-<sujet>`, `fix/<pilier>-<sujet>`, `chore/<sujet>` (piliers : dev, infra, ia, cyber, gouv).
- Commits : Conventional Commits, en français. Exemple : `feat(infra): ajout du provisioning Grafana`.
- Ne jamais pousser directement sur `main`. Ne jamais faire de `git push --force`.
- Ne pas commiter sans que l'utilisateur l'ait demandé.

## Qualité attendue

- Chaque service : `Dockerfile`, `README.md`, healthcheck, endpoint `/metrics` Prometheus, tests `pytest` minimaux.
- Convention FastAPI : tous les services FastAPI écoutent sur le port **`8000`**, avec `/health` (healthcheck), `/metrics` (Prometheus) et `/webhook/...` (réception d'alertes, pour `remediation-engine`).
- Exceptions au scraping Prometheus (choix assumés) : `frontend`, `dashboard` et `assistant-rag` n'exposent pas de `/metrics` ; le `waf` n'a pas d'exporter, ses métriques de blocage viendront des logs ModSecurity dans Loki.
- Configs versionnées (dashboards Grafana en JSON provisionnés, règles Prometheus en fichiers).
- Code commenté sobrement, compréhensible par toute l'équipe : chaque membre doit pouvoir l'expliquer au jury.
