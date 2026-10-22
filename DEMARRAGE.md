# Démarrer le projet — guide pas à pas

Tout ce qu'il faut installer et toutes les commandes pour lancer RESILIENCE-ALPHA, du PC vierge à la démonstration. Les commandes sont pour **PowerShell** (Windows), lancées **à la racine du dépôt** sauf mention contraire.

> Pour comprendre le projet : [README](README.md). Pour savoir où il en est : [état des lieux](docs/etat-des-lieux.md).

| Je veux… | Aller à |
|---|---|
| Juste lancer les tests (n'importe quel PC, sans Docker) | [1](#1-installer-les-outils), [2](#2-récupérer-le-dépôt), [3](#3-lancer-les-tests-sans-docker) |
| Faire tourner la plateforme sur mon PC | [1](#1-installer-les-outils) à [6](#6-vérifier-que-tout-marche) |
| Utiliser la plateforme (frontal, dashboard, Grafana) | [guide d'utilisation, README §7](README.md#7-utiliser-et-vérifier-la-plateforme) |
| Préparer et jouer la démonstration | [9](#9-lancer-la-démonstration-attaque-et-reprise-autonome) et [12](#12-jour-j--check-list-de-la-démonstration-et-du-clip-chrono) |

### Les adresses à connaître

| Quoi | Adresse | Depuis |
|---|---|---|
| Frontal de paiement (via le WAF) | <http://192.168.137.1> en démonstration, <http://127.0.0.1> en développement | PC Hôte, PC Attaquant (démo) |
| Dashboard de supervision | <http://127.0.0.1:5173> | PC Hôte uniquement |
| Grafana | <http://127.0.0.1:3000> | PC Hôte uniquement |
| Prometheus | <http://127.0.0.1:9090> (cibles : <http://127.0.0.1:9090/targets>) | PC Hôte uniquement |
| Assistant RAG | <http://127.0.0.1:8501> | PC Hôte uniquement |
| Ollama (natif) | `http://host.docker.internal:11434` vu des conteneurs, <http://127.0.0.1:11434> sur le PC Hôte | PC Hôte |
| Dépôt GitHub | <https://github.com/Formidabledu59/resilience-alpha> | partout |

Seul le WAF est publié sur le réseau (`192.168.137.1:80`). Tout le reste est lié à `127.0.0.1` : ces adresses ne s'ouvrent **que sur le PC Hôte**, jamais depuis le PC Attaquant.

---

## 1. Installer les outils

### Sur chaque PC (tests et développement)

| Outil | Version | À quoi il sert | Installation (PowerShell) |
|---|---|---|---|
| Git | récente | Récupérer le dépôt, commiter | `winget install --id Git.Git` |
| Python | **3.11 ou plus** (3.12 conseillé) | Tests, scripts d'attaque, scénario de bout en bout | `winget install --id Python.Python.3.12` |
| Node.js | **22** | Tests du frontal et du dashboard (facultatif) | installeur « 22.x LTS » sur <https://nodejs.org> |
| GitHub CLI | récente | Ouvrir et fusionner les PR (facultatif) | `winget install --id GitHub.cli` puis `gh auth login` |

> Après une installation par `winget`, **fermer et rouvrir** le terminal (et VS Code s'il est ouvert) : sinon la nouvelle commande n'est pas trouvée (« le terme n'est pas reconnu »). En dépannage, on peut recharger le PATH sans fermer :
> ```powershell
> $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
> ```

Vérifier :

```powershell
git --version
python --version      # 3.11 ou plus
node --version        # v22.x (seulement pour les tests du front)
```

### En plus sur le PC Hôte (celui qui fait tourner la plateforme)

| Outil | À quoi il sert | Installation |
|---|---|---|
| Docker Desktop (backend **WSL2**) | Tous les services de la plateforme | `winget install --id Docker.DockerDesktop`, redémarrer, puis lancer Docker Desktop une première fois |
| Ollama (natif, hors Docker) | Modèle de langage de l'assistant RAG | `winget install --id Ollama.Ollama` |

Configuration minimale : 16 Go de RAM (32 Go conseillés), virtualisation activée dans le BIOS, 50 Go libres.

```powershell
docker info --format "{{.ServerVersion}}"   # affiche une version si Docker Desktop est prêt
wsl --status                                  # « Version par défaut : 2 »
```

Ansible n'est **pas** à installer : il tourne dans le conteneur `remediation-engine`.

### Sur le PC Attaquant

Seulement **Git** et **Python 3.11+**. Aucun composant défensif.

### Sur le PC délestage IA (facultatif)

Seulement **Ollama**, si la RAM du PC Hôte ne suffit pas pour le modèle (voir [étape 7](#7-assistant-rag-et-ollama)).

---

## 2. Récupérer le dépôt

```powershell
git clone https://github.com/Formidabledu59/resilience-alpha.git
cd resilience-alpha
```

Déjà cloné : `git checkout main` puis `git pull`.

---

## 3. Lancer les tests (sans Docker)

Une seule commande, sur n'importe quel PC qui a Python (et Node.js pour le front) :

```powershell
python tests/run_all.py                 # tout : 12 suites (la première fois : quelques minutes d'installation)
python tests/run_all.py --python-only   # sans Node.js
python tests/run_all.py --only canary   # une seule suite
python tests/run_all.py --no-install    # relance rapide
```

Les dépendances sont installées dans `.venv-tests/` (ignoré par Git) : rien n'est installé dans le Python du PC. Résultat attendu : `12/12 suites OK` (183 tests le 22/10). Détail des suites : [README, section 14](README.md#14-tests).

---

## 4. Préparer le PC Hôte (une seule fois)

### 4.1 Créer le fichier `.env` avec des secrets aléatoires

`.env` contient les mots de passe locaux. Il est ignoré par Git et **ne doit jamais être commité**. Ce bloc lit `.env.example` et remplace chaque `changeme_*` par un secret aléatoire :

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

Vérifier qu'il ne reste aucune valeur factice (la commande ne doit **rien** afficher) :

```powershell
Select-String -Path .env -Pattern '^[A-Z_]+=changeme_'
```

> Ne pas relancer ce bloc une fois la stack démarrée : Grafana et PostgreSQL gardent les mots de passe du premier démarrage. Pour repartir de zéro, voir [étape 10](#10-arrêter-et-remettre-à-zéro).

Retrouver un mot de passe plus tard :

```powershell
Select-String -Path .env -Pattern '^GRAFANA_ADMIN_(USER|PASSWORD)='   # Grafana
Select-String -Path .env -Pattern '^AUTH_DEMO_PASSWORD='              # utilisateur « demo » du frontal
```

### 4.2 Choisir le mode : démonstration ou développement

Le WAF est le seul service joignable depuis le réseau. Son adresse se règle dans `.env` :

| Mode | `WAF_BIND_IP` | Point d'accès `RESILIENCE-G16` | Frontal |
|---|---|---|---|
| **Démonstration** (PC Attaquant, scénario complet) | `192.168.137.1` | **obligatoire, activé AVANT Docker Desktop** | <http://192.168.137.1> |
| **Développement** (PC Hôte seul) | `127.0.0.1` | inutile | <http://127.0.0.1> |

> Ne **jamais** mettre `0.0.0.0` : le PC Hôte est aussi sur le WiFi du campus.

**Activer le point d'accès (mode démonstration)** : Paramètres Windows → Réseau et Internet → Point d'accès sans fil mobile.
- Nom du réseau : **`RESILIENCE-G16`** (Windows propose un nom par défaut, à remplacer), mot de passe choisi par l'équipe ;
- **Économie d'énergie : désactivé**, sinon Windows éteint le point d'accès après ~5 minutes sans appareil connecté et le WAF devient injoignable ;
- activer, puis **seulement ensuite** démarrer (ou redémarrer) Docker Desktop.

Vérifier que l'adresse existe :

```powershell
Get-NetIPAddress -IPAddress 192.168.137.1
```

---

## 5. Démarrer la plateforme

Docker Desktop doit être lancé et prêt (`docker info` répond).

```powershell
docker compose config -q     # n'affiche rien si la configuration est valide
```

Les services sont rangés par **profiles**. On peut tout lancer d'un coup, ou monter par étapes :

| Profile | Services | Commande |
|---|---|---|
| (aucun) | Observabilité : prometheus, alertmanager, loki, alloy, grafana, socket-proxy-ro | `docker compose up -d` |
| `app` | waf, frontend, auth-service, payment-api, postgres, canary, dashboard (sans biométrie par défaut) | `docker compose --profile app up -d --build` |
| `security` | vault, vault-init (secrets dans Vault) | `docker compose --profile app --profile security up -d --build` |
| `ia` | ml-detector, assistant-rag | ajouter `--profile ia` |
| `remediation` | remediation-engine, socket-proxy-rw | ajouter `--profile remediation` |

**Stack complète (démonstration)** :

```powershell
docker compose --profile app --profile security --profile ia --profile remediation up -d --build
```

Le premier lancement télécharge les images et construit les services : compter 5 à 15 minutes. Puis, après une minute environ :

```powershell
docker compose ps -a
```

19 conteneurs : les 18 services doivent être `(healthy)`, et `vault-init` s'arrête normalement après avoir initialisé Vault (`Exited (0)`). Dans la colonne `PORTS`, seuls doivent apparaître `192.168.137.1:80->8080` (ou `127.0.0.1:80->8080`) et `127.0.0.1:3000`, `127.0.0.1:5173`, `127.0.0.1:8501`, `127.0.0.1:9090`. Jamais `0.0.0.0`.

> Après un `git pull` qui modifie un service, reconstruire : relancer la même commande avec `--build`. Pour être sûr que le front et le dashboard reprennent les modifications : `docker compose --profile app build --no-cache frontend dashboard`.

> Le profile `ia` exige `OLLAMA_BASE_URL` et `OLLAMA_MODEL` dans `.env` (déjà présents via `.env.example`). Le conteneur démarre même si Ollama est éteint ; l'assistant indique alors qu'il ne peut pas répondre.

---

## 6. Vérifier que tout marche

### Les interfaces (sur le PC Hôte)

| Interface | Adresse | Ce qu'on doit voir |
|---|---|---|
| Frontal de paiement | <http://192.168.137.1> (ou <http://127.0.0.1>) | Connexion avec `demo` / `AUTH_DEMO_PASSWORD`, puis un virement `COMPLETED` |
| Dashboard de supervision | <http://127.0.0.1:5173> | La supervision s'affiche directement (pas d'écran de connexion : biométrie désactivée), phase « Avant », canari à 100 % |
| Grafana | <http://127.0.0.1:3000> | Dashboards « Resilience - Vue globale » et « Frontal et sécurité » |
| Prometheus | <http://127.0.0.1:9090/targets> | Toutes les cibles **UP** ; la requête `canary_up` vaut `1` et `ml_model_fallback` vaut `0` une fois le modèle entraîné (étape 12) |
| Assistant RAG | <http://127.0.0.1:8501> | Interface de discussion (voir étape 7) |

Utilisation détaillée de chaque interface : [guide d'utilisation, README §7](README.md#7-utiliser-et-vérifier-la-plateforme).

### Une transaction en ligne de commande

Les API n'ont aucun port publié : le script tourne dans un conteneur `curl` jetable branché sur le réseau interne.

```powershell
$pass = (Select-String -Path .env -Pattern '^AUTH_DEMO_PASSWORD=(.*)').Matches[0].Groups[1].Value
docker run --rm --network resilience-alpha_app-net -e PASS=$pass -v "${PWD}/tests/e2e:/e2e:ro" curlimages/curl:8.22.0 sh /e2e/transaction_curl.sh
```

Attendu : `Résultat : COMPLETED`.

Pas à pas détaillé et dépannage de chaque service : [`infra/README.md`](infra/README.md).

---

## 7. Assistant RAG et Ollama

Sur la machine qui héberge Ollama (PC Hôte ou PC délestage IA), tirer les deux modèles :

```powershell
ollama pull llama3.1:8b         # génération (8B maximum)
ollama pull nomic-embed-text    # embeddings de l'assistant
ollama list                     # les deux modèles apparaissent
```

Vérifier qu'Ollama répond sur le PC Hôte : <http://127.0.0.1:11434> affiche « Ollama is running ».

Dans `.env` du PC Hôte :

| Ollama tourne sur | `OLLAMA_BASE_URL` |
|---|---|
| le PC Hôte | `http://host.docker.internal:11434` |
| le PC délestage IA | `http://192.168.137.x:11434` (IP de ce PC sur le point d'accès) |

Sur le **PC délestage IA**, Ollama n'écoute par défaut que sur lui-même. Le lier à son adresse sur le point d'accès (pas `0.0.0.0`), puis redémarrer Ollama :

```powershell
setx OLLAMA_HOST "192.168.137.x:11434"
```

Après un changement de `.env` : `docker compose --profile ia up -d assistant-rag`.

---

## 8. Back-office biométrique (consigne additionnelle 1) — optionnel, désactivé par défaut

La biométrie est **préparée mais pas activée** pour la démonstration. Par défaut
(`BACKOFFICE_BIOMETRICS=false` dans `.env`), le dashboard affiche directement la supervision, sans
appel à la passerelle : **rien à lancer pour la démo**.

Pour l'activer (caméra USB et ESP8266 branchés) : mettre `BACKOFFICE_BIOMETRICS=true` dans `.env`,
puis `docker compose --profile app up -d dashboard`. Le dashboard demande alors identifiant, visage
et mot de passe.

La passerelle tourne **en natif sur le PC Hôte** (accès à la caméra USB), dans un terminal à part :

```powershell
cd biometrics/gateway
py -m venv .venv
.\.venv\Scripts\Activate.ps1          # si refusé : Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
$env:BIO_DATA_DIR = "$PWD\data"
python -m uvicorn app:app --host 0.0.0.0 --port 8700
```

Puis dans le dashboard (<http://127.0.0.1:5173>), back-office → onglet **Habilitations** pour enrôler un visage. Le firmware de l'ESP8266 se flashe avec PlatformIO : [`biometrics/esp8266/README.md`](biometrics/esp8266/README.md). Détails et limites : [`biometrics/README.md`](biometrics/README.md).

---

## 9. Lancer la démonstration (attaque et reprise autonome)

Prérequis : **mode démonstration** (point d'accès actif avant Docker, `WAF_BIND_IP=192.168.137.1`), **stack complète** démarrée, **modèle ML entraîné** et **réglages de démonstration** appliqués (étape 12, points 2 et 3). Les scripts d'attaque refusent toute cible hors `192.168.137.0/24`.

### Depuis le PC Attaquant (connecté au WiFi `RESILIENCE-G16`)

```powershell
git clone https://github.com/Formidabledu59/resilience-alpha.git
cd resilience-alpha
pip install -r attack/requirements.txt

# Injections SQL / XSS : toutes doivent être BLOQUÉES par le WAF (403)
python attack/sqli/inject.py --target http://192.168.137.1

# Déni de service authentifié (mot de passe demo : le demander au PC Hôte, jamais en argument)
$env:ATTACK_PASSWORD = '<mot de passe demo>'
python attack/dos/flood.py --target http://192.168.137.1 --auth demo --duration 90 --concurrency 200
```

Vérifier d'abord, depuis le PC Attaquant, que le frontal s'ouvre : <http://192.168.137.1>.

Sur le PC Hôte, suivre le dashboard (<http://127.0.0.1:5173>) **sans rien toucher** : Avant → Pendant (score ML au-dessus de 0,7) → Remédiation (ban + relance) → Après (transaction de contrôle `COMPLETED`, incident clos). Mesuré le 22/10 : 37 à 75 s ([répétition générale](docs/test-results/repetition-generale.md)).

### Scénario de bout en bout automatisé (sur le PC Hôte)

Il enchaîne transaction, attaque, détection, remédiation et transaction finale, et vérifie chaque étape. Il doit tourner **sur le PC Hôte** (Prometheus et le dashboard ne sont publiés que sur `127.0.0.1`) :

```powershell
pip install -r tests/e2e/requirements.txt
$env:ATTACK_PASSWORD = (Select-String -Path .env -Pattern '^AUTH_DEMO_PASSWORD=(.*)').Matches[0].Groups[1].Value
python tests/e2e/resilience_scenario.py --runs 3 --concurrency 200
```

Code de sortie 0 = boucle de reprise prouvée à chaque essai ; un tableau chronométré s'affiche (ajouter `--report docs/test-results/repetition-generale.md` pour le garder). Si aucun incident ne se déclenche, l'attaque n'a pas assez dégradé le service : vérifier les réglages de démonstration (étape 12, point 2) et monter `--concurrency`. Réglages et mesures : [`docs/test-results/calibrage-attaque-dos.md`](docs/test-results/calibrage-attaque-dos.md).

> La remédiation peut bannir l'IP de l'attaquant pendant 5 minutes. Derrière Docker Desktop, tout le trafic externe partage la même IP : le frontal est alors inaccessible depuis l'extérieur pendant le ban, le canary (interne) continue. C'est attendu.

---

## 10. Arrêter et remettre à zéro

```powershell
docker compose --profile app --profile security --profile ia --profile remediation down      # arrêt, données conservées
docker compose --profile app --profile security --profile ia --profile remediation down -v   # arrêt ET suppression des données (remise à zéro)
```

Après un `down -v`, on peut régénérer `.env` (étape 4.1) : bases, Vault et Grafana repartent de zéro.

---

## 11. Problèmes fréquents

| Symptôme | Cause | Solution |
|---|---|---|
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop n'est pas démarré | Lancer Docker Desktop, attendre « Engine running » |
| Le WAF reste `Created`, le frontal ne répond pas | `192.168.137.1` n'existe pas (point d'accès inactif ou activé après Docker) | Activer le point d'accès, puis `docker compose --profile app up -d --force-recreate waf` (ou passer `WAF_BIND_IP=127.0.0.1`) |
| Le frontal ne répond plus au bout de quelques minutes | Point d'accès éteint par l'économie d'énergie de Windows | Désactiver l'économie d'énergie (étape 4.2), rallumer le point d'accès, recréer le WAF (ligne ci-dessus) |
| `403` sur le frontal après une attaque | IP bannie par la remédiation (5 min, levée automatique) | Attendre ; le journal de l'incident dans le dashboard indique la levée du ban |
| Dashboard : « La passerelle biométrique ne répond pas » | `BACKOFFICE_BIOMETRICS=true` dans `.env` sans passerelle lancée | Remettre `false`, puis `docker compose --profile app up -d dashboard` |
| Score ML élevé sans attaque, `ml_model_fallback = 1` | Modèle de repli synthétique (aucun modèle entraîné) | Entraîner le modèle (étape 12, point 3) |
| `gh`, `python`, `node`… « n'est pas reconnu » | Terminal ouvert avant l'installation | Fermer et rouvrir le terminal (et VS Code), ou recharger le PATH (étape 1) |
| `npm ci` plante dans le front | npm 10 (fourni avec Node 22) | Utiliser `python tests/run_all.py` qui lance npm 11.21.0 ; dans les Dockerfile c'est déjà épinglé |
| `Activate.ps1 ne peut pas être chargé` | Politique d'exécution PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Mot de passe Grafana refusé | `.env` régénéré après le premier démarrage | Remise à zéro (étape 10) |
| `[REFUS] Cible interdite` | Cible hors `192.168.137.0/24` (dont `127.0.0.1`) | Normal : les attaques ne visent que le WAF sur le point d'accès |
| L'assistant RAG ne répond pas | Ollama éteint ou modèles absents | `ollama list`, `ollama pull` (étape 7), vérifier `OLLAMA_BASE_URL` |
| Commandes avec guillemets imbriqués qui échouent | PowerShell 5.1 abîme les guillemets passés aux programmes | Utiliser les scripts versionnés (`tests/e2e/transaction_curl.sh`) |

---

## 12. Jour J : check-list de la démonstration et du Clip Chrono

Le jury note surtout l'**axe 1** (5 points) : attaque depuis le PC Attaquant, détection, reprise **sans intervention**, nouvelle transaction réussie. Si un humain doit corriger pendant le live, l'axe vaut **0/5**. Tout se prépare donc la veille, à l'identique.

### La veille (répétition générale, à refaire jusqu'à 3 succès d'affilée)

1. Point d'accès `RESILIENCE-G16` actif, **puis** Docker Desktop. `.env` : `WAF_BIND_IP=192.168.137.1`.
   - **Désactiver l'économie d'énergie du point d'accès** (Paramètres → Réseau et Internet → Point d'accès sans fil mobile → Économie d'énergie : désactivé). Sinon Windows l'éteint après ~5 minutes sans appareil connecté : `192.168.137.1` disparaît et le WAF ne répond plus (il faut alors le recréer : `docker compose --profile app up -d --force-recreate waf`).
   - Vérifier que le nom du réseau est bien `RESILIENCE-G16` (Windows propose un nom par défaut).
   - **`.env` à jour** : un `.env` créé avant les dernières versions peut manquer de variables. Cette commande liste celles qui manquent (elle ne doit rien afficher) :
     ```powershell
     $env_ = (Get-Content .env) -replace '=.*',''; (Get-Content .env.example | Where-Object { $_ -match '^[A-Z_]+=' }) -replace '=.*','' | Where-Object { $_ -notin $env_ }
     ```
2. Réglages de démonstration dans `.env`, mesurés le 22/10 ([`calibrage-attaque-dos.md`](docs/test-results/calibrage-attaque-dos.md)) :
   - **pour montrer la détection ML** (proposé) : `WAF_RATE_LIMIT=2000r/s`, `WAF_RATE_BURST=4000`, `FRONTEND_API_RATE_LIMIT=2000r/s`, `FRONTEND_API_BURST=4000`, attaque à concurrence 200 → alerte ML (score 0,78), ban + relance, reprise prouvée en ~23 s ;
   - limites par défaut (50 r/s et 10 r/s) : l'attaque est absorbée, la règle SOC bannit l'attaquant en ~5 s, le ML ne déclenche pas.

   Après un changement : `docker compose --profile app up -d waf frontend`.
3. Stack complète (étape 5), puis **modèle ML entraîné sur du vrai trafic** : laisser tourner la plateforme **30 minutes sans attaque**, puis :
   ```powershell
   pip install -r ml/detector/requirements.txt
   python ml/training/collect.py --minutes 30 --out ml/data/nominal.csv
   python ml/training/train.py --data ml/data/nominal.csv
   docker compose --profile ia restart ml-detector
   ```
   Dans Prometheus (<http://127.0.0.1:9090>), `ml_model_fallback` doit valoir `0`. Le modèle (`ml/models/model.joblib`) n'est **pas** versionné : à refaire sur chaque PC qui sert à la démonstration, ou copier le fichier.
4. **Calibrer le DoS** (trouve la charge qui déclenche la détection ML) :
   ```powershell
   pip install -r tests/e2e/requirements.txt
   $env:ATTACK_PASSWORD = (Select-String -Path .env -Pattern '^AUTH_DEMO_PASSWORD=(.*)').Matches[0].Groups[1].Value
   python tests/e2e/calibrate_dos.py --report docs/test-results/calibrage-attaque-dos.md
   ```
   Si aucun palier ne déclenche : relâcher `FRONTEND_API_RATE_LIMIT` / `FRONTEND_API_BURST` dans `.env`, `docker compose --profile app up -d frontend`, relancer.
5. **Trois essais chronométrés d'affilée**, avec la concurrence retenue :
   ```powershell
   python tests/e2e/resilience_scenario.py --runs 3 --concurrency <retenue> --report docs/test-results/repetition-generale.md
   ```
   Le tableau indique qui a détecté (ML attendu), les durées et si la boucle tient dans les 60 s du clip.
6. Depuis le PC Attaquant, rejouer l'attaque seule en filmant l'écran du PC Hôte : c'est la prise du Clip Chrono.

### Budget de temps du Clip Chrono (60 s, plan continu, sans coupe)

| Moment | Ce qu'on voit (dashboard + terminal de l'attaquant) | Temps visé |
|---|---|---|
| Avant | Phase « Avant », canari 100 %, transaction OK | 0-5 s |
| Attaque | Lancement de `flood.py` sur le PC Attaquant | 5 s |
| Pendant | Latence et erreurs qui montent, score ML qui franchit 0,7 | 10-30 s |
| Remédiation | Incident ouvert, playbooks (ban, relance) affichés en direct | 30-35 s |
| Après | 3 relevés du canari OK (~15 s), transaction de contrôle `COMPLETED`, incident `CLOSED` | 35-55 s |

Si la boucle dépasse 60 s en répétition, mettre `ML_ALERT_CONSECUTIVE=2` dans `.env` puis `docker compose --profile ia up -d ml-detector` (détection ~5 s plus tôt), ou durcir l'attaque pour que la dégradation soit plus nette ; ne **jamais** accélérer ni couper la vidéo. Mesuré le 22/10 : 3 essais sur 6 sous 60 s, les plus lents ayant subi une coupure du point d'accès.

### Le matin du jury

- Tout allumer 30 minutes avant : point d'accès (économie d'énergie désactivée), Docker, stack, Ollama. Pas de passerelle biométrique (désactivée).
- Connecter le PC Attaquant à `RESILIENCE-G16` et ouvrir <http://192.168.137.1> depuis ce poste.
- `docker compose ps -a` : tout `healthy`. Dashboard (<http://127.0.0.1:5173>) en phase « Avant ». `ml_model_fallback = 0` dans Prometheus. Une transaction manuelle `COMPLETED` depuis le frontal.
- Prévoir l'annonce au jury : après la remédiation, l'IP de l'attaquant est bannie 5 minutes (comportement voulu), le service reste disponible pour les clients internes et le canari.
- Plan B, annoncé comme tel : si le DoS ne dégrade pas assez le service en direct, montrer la seconde voie automatique (arrêt de `payment-api` → `TargetDown` → relance Ansible → transaction de contrôle), puis le Clip Chrono pour la détection ML. Ce plan B prouve la reprise autonome mais **pas** une attaque menée depuis le PC Attaquant : il ne remplace pas un DoS calibré.
