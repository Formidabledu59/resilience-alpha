# infra/ : démarrage et vérification de la stack

Ce dossier contient la configuration de l'infrastructure : Docker Compose (à la racine), observabilité et Ansible.
Ce guide explique pas à pas comment démarrer la plateforme sous **Windows** et vérifier qu'elle fonctionne, sans connaissance préalable du projet.

> Référence des règles (réseaux, ports, noms de services, sécurité) : [`CLAUDE.md`](../CLAUDE.md).

## Contenu

```
infra/
├── alertmanager/alertmanager.yml     Routage des alertes vers remediation-engine (bearer token)
├── alloy/config.alloy                Collecte des logs Docker (via socket-proxy-ro) vers Loki
├── ansible/
│   ├── ansible.cfg                   Configuration Ansible (voir « Ansible » plus bas)
│   ├── inventory/hosts.yml           localhost, connexion locale
│   └── playbooks/                    Playbooks de remédiation
├── grafana/
│   ├── dashboards/                   Dashboards JSON (« Resilience - Vue globale »)
│   └── provisioning/                 Datasources Prometheus + Loki, provider de dashboards
├── loki/loki-config.yml              Stockage des logs (7 jours)
└── prometheus/
    ├── prometheus.yml                Cibles scrapées toutes les 5 s
    └── alerts.yml                    Règle TargetDown
```

## Ce qui démarre

`docker compose up -d` **sans profile** démarre uniquement la stack d'observabilité (6 conteneurs) :

| Service | Rôle | Accès depuis le PC Hôte |
|---|---|---|
| `prometheus` | Métriques | http://127.0.0.1:9090 |
| `grafana` | Dashboards, exploration des logs | http://127.0.0.1:3000 |
| `alertmanager` | Routage des alertes | aucun port publié |
| `loki` | Stockage des logs | aucun port publié |
| `alloy` | Collecte des logs des conteneurs | aucun port publié |
| `socket-proxy-ro` | Accès Docker en lecture seule pour Alloy | aucun port publié |

Les autres services sont rangés dans des **profiles** et ne démarrent que si on les demande (voir « Démarrer les autres services »). Grafana provisionne deux dashboards : « Resilience - Vue globale » et « Resilience - Frontal et sécurité ».

---

## 1. Prérequis

1. **Docker Desktop** installé, backend **WSL2**, et **démarré** : l'icône de la baleine doit être stable dans la barre des tâches.
2. Un terminal **PowerShell**, ouvert à la racine du dépôt (le dossier qui contient `docker-compose.yml`).
3. Vérifier que Docker répond :

   ```powershell
   docker info --format "{{.ServerVersion}}"
   ```

   Si la commande affiche `error during connect ... dockerDesktopLinuxEngine`, Docker Desktop n'est pas démarré.

> Le point d'accès mobile `RESILIENCE-G16` n'est **pas** nécessaire pour la stack d'observabilité. Il ne le devient que pour le WAF (profile `security`), et doit alors être actif **avant** de démarrer Docker.

## 2. Créer le fichier `.env` avec des secrets aléatoires

Le fichier `.env` contient les mots de passe locaux. Il est ignoré par Git et **ne doit jamais être commité**.

Copier-coller ce bloc dans PowerShell, depuis la racine du dépôt. Il lit `.env.example`, remplace chaque valeur `changeme_*` par un secret aléatoire de 64 caractères et écrit `.env` (UTF-8 sans BOM, fins de ligne LF) :

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
function New-Secret {
    $octets = New-Object byte[] 32
    $rng.GetBytes($octets)
    -join ($octets | ForEach-Object { $_.ToString('x2') })
}
$lignes = Get-Content .env.example -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=changeme_') { "$($Matches[1])=$(New-Secret)" } else { $_ }
}
[System.IO.File]::WriteAllText("$PWD\.env", ($lignes -join "`n") + "`n", (New-Object System.Text.UTF8Encoding $false))
```

Vérifier qu'il ne reste aucune valeur factice (la commande ne doit rien afficher) :

```powershell
Select-String -Path .env -Pattern '^[A-Z_]+=changeme_'
```

Pour retrouver le mot de passe Grafana plus tard :

```powershell
Select-String -Path .env -Pattern '^GRAFANA_ADMIN_(USER|PASSWORD)='
```

> Ne pas relancer ce bloc une fois la stack démarrée : Grafana garde le mot de passe défini au premier démarrage (il est stocké dans le volume `grafana-data`). Pour repartir de zéro, voir « Remise à zéro ».

## 3. Valider puis lancer la stack

```powershell
docker compose config -q      # n'affiche rien si la configuration est valide
docker compose up -d          # le premier lancement télécharge les images (quelques minutes)
```

## 4. Vérifier que les 6 conteneurs sont `healthy`

```powershell
docker compose ps
```

Attendre environ une minute : la colonne `STATUS` doit afficher `(healthy)` pour les 6 services. Loki met souvent 20 à 30 secondes à être prêt, et Alloy attend Loki et `socket-proxy-ro` avant de démarrer.

Vérifier aussi l'exposition : seuls `127.0.0.1:3000` (Grafana) et `127.0.0.1:9090` (Prometheus) doivent apparaître dans la colonne `PORTS`. Aucun port ne doit être publié sur `0.0.0.0`.

## 5. Vérifier Prometheus : http://127.0.0.1:9090

**Status → Target health** (`/targets`) :

| Cible | État attendu |
|---|---|
| `prometheus`, `alertmanager`, `loki`, `alloy`, `grafana` | **UP** |
| `auth-service`, `payment-api`, `canary`, `ml-detector`, `remediation-engine` | **DOWN**, normal : ces services ne sont pas encore développés |

**Alerts** (`/alerts`) : l'alerte `TargetDown` est `FIRING` pour les 5 cibles DOWN. C'est attendu pour l'instant.

> Ne sont volontairement pas scrapés : `postgres` et `vault` (la santé de la base est couverte par le canary), `frontend`, `dashboard` et `assistant-rag` (pas de `/metrics` natif), ainsi que le `waf` (les métriques de blocage viendront des logs ModSecurity dans Loki).

## 6. Vérifier Grafana : http://127.0.0.1:3000

1. Se connecter avec `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` (valeurs du `.env`, voir étape 2).
2. La page d'accueil est le dashboard **Resilience - Vue globale** (dossier *Resilience*) :
   - **Cibles UP** : 5 sur 10 ;
   - **État des cibles** : 5 tuiles vertes (UP) et 5 rouges (DOWN) ;
   - **Journaux des conteneurs** : des lignes de logs défilent. La liste *Service* en haut permet de filtrer.
3. **Connections → Data sources** : ouvrir *Prometheus*, cliquer sur **Test** en bas de page. Le message doit être `Successfully queried the Prometheus API`. Faire de même pour *Loki* (message de succès attendu).
4. **Explore** : choisir la datasource *Loki* et lancer la requête `{project="resilience-alpha"}`. Des logs de `loki`, `grafana`, `prometheus`, etc. doivent apparaître.

Si tout est conforme, la stack d'observabilité fonctionne.

---

## 7. Si un conteneur n'est pas `healthy`

Toujours commencer par regarder l'état et les logs du service concerné (remplacer `<service>` par son nom, par exemple `loki`) :

```powershell
docker compose ps -a
docker compose logs --tail 100 <service>
docker inspect --format '{{json .State.Health}}' resilience-alpha-<service>-1
```

| Symptôme | Cause probable | Que faire |
|---|---|---|
| `required variable ... manquant dans .env` | `.env` absent ou incomplet | Refaire l'étape 2 |
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop arrêté | Démarrer Docker Desktop et attendre qu'il soit prêt |
| `port is already allocated` (3000 ou 9090) | Une autre application utilise le port | `Get-NetTCPConnection -LocalPort 3000` pour trouver le processus, puis l'arrêter |
| `loki` en `starting` plus d'une minute | Démarrage de Loki (« Ingester not ready ») | Attendre ; si ça dure, lire `docker compose logs loki` |
| `permission denied` dans les logs | Volume créé avec un mauvais propriétaire, ou dossier non inscriptible en `read_only` | `docker compose down -v` puis `docker compose up -d` (efface les données de la stack). Si l'erreur persiste, noter le service et le chemin cités et le signaler à l'équipe : il faudra ajouter un `tmpfs` ou ajuster le durcissement |
| `alloy` ou `grafana` en `waiting` | Ils attendent qu'une dépendance soit `healthy` | Corriger d'abord `loki`, `socket-proxy-ro` ou `prometheus` |
| `container rootfs is marked read-only` pendant `docker compose up -d`, puis `alertmanager`, `alloy` ou `grafana` bloqués en `Created` | Un secret Compose (`secrets:`) ne peut pas être écrit dans un conteneur `read_only` | C'est pourquoi `alertmanager` n'a **pas** `read_only` (il reçoit le secret `remediation_bearer_token`). Ne pas remettre `read_only` sur un service qui utilise `secrets:`. Relancer `docker compose up -d` après correction |
| Aucun log dans Grafana | Alloy ne lit pas Docker | `docker compose logs socket-proxy-ro` : un code `403` indique un appel refusé par le proxy. Alloy a besoin de `GET /containers` **et** de `GET /networks` : `socket-proxy-ro` doit avoir `CONTAINERS=1` et `NETWORKS=1` (toujours en lecture seule grâce à `POST=0`). Vérifier aussi que la cible `alloy` est UP dans Prometheus |
| Datasource en erreur dans Grafana | Prometheus ou Loki indisponible | Vérifier que `prometheus` et `loki` sont `healthy` |
| Erreur de syntaxe sur un fichier de config modifié sous Windows | Fins de ligne CRLF | `git add --renormalize .` puis recréer le conteneur (le dépôt impose LF via `.gitattributes`) |

Après une correction de configuration, recréer le service :

```powershell
docker compose up -d --force-recreate <service>
```

## 8. Arrêt et remise à zéro

```powershell
docker compose down        # arrêt, données conservées
docker compose down -v     # arrêt et suppression des volumes (métriques, logs, compte Grafana)
```

---

## Démarrer les autres services

Les services applicatifs sont rangés dans des profiles :

| Profile | Services | État |
|---|---|---|
| `app` | waf, frontend, auth-service, payment-api, canary, dashboard, postgres | **Prêt** : démarrable et vérifié |
| `security` | vault, vault-init | **Prêt** : Vault initialisé et seedé par `vault-init`, secrets lus par auth-service et payment-api (voir `security/vault/README.md`) |
| `ia` | ml-detector, assistant-rag | Code à écrire |
| `remediation` | remediation-engine, socket-proxy-rw | Code à écrire |

Le WAF est dans `app` : il fait partie du chemin applicatif (client ou canary, WAF, frontal, API). Aujourd'hui, seul le profile `app` est utilisable :

```powershell
docker compose --profile app up -d --build
```

Le WAF publie le port 80 sur `WAF_BIND_IP` (`.env`). Si le point d'accès `RESILIENCE-G16` n'est pas actif, `192.168.137.1` n'existe pas : le WAF reste à l'état `Created` et le canary aussi. Dans ce cas, mettre `WAF_BIND_IP=127.0.0.1` (développement sur le PC Hôte seul).

Résultat attendu : 13 conteneurs `healthy` (les 6 de l'observabilité et les 7 du profile `app`). Le frontal est sur http://127.0.0.1 (ou http://192.168.137.1), le dashboard sur http://127.0.0.1:5173. Utilisation pas à pas : [README, section 7](../README.md#7-utiliser-et-vérifier-la-plateforme). Détails du WAF : [`security/waf/README.md`](../security/waf/README.md).

Quand tous les profiles seront prêts :

```powershell
docker compose --profile app --profile security --profile ia --profile remediation up -d --build
```

Le profile `security` publie le WAF sur `192.168.137.1:80` : le point d'accès `RESILIENCE-G16` doit être actif **avant** le démarrage de Docker Desktop.

## Ansible

Ansible s'exécute dans le conteneur `remediation-engine` (qui reçoit `ANSIBLE_CONFIG=/ansible/ansible.cfg`), ou depuis WSL2 pour le déploiement initial.

Sous WSL, le disque Windows (`/mnt/d`) est accessible en écriture à tous : Ansible **ignore** alors le `ansible.cfg` du dossier courant. Il faut le désigner explicitement :

```bash
export ANSIBLE_CONFIG=infra/ansible/ansible.cfg
ansible-inventory --list      # doit afficher localhost
```
