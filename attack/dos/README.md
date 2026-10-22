# attack/dos : test de charge applicatif

Attaque **principale** de la démonstration : un déni de service applicatif contrôlé contre l'API de paiement, pour provoquer un incident que le détecteur ML repère et que la remédiation corrige.

> Lire d'abord [`attack/README.md`](../README.md) (garde-fou, prérequis). Cible restreinte à `192.168.137.0/24`.

## Lancer

Depuis le PC Attaquant (point d'accès `RESILIENCE-G16` actif) :

```bash
python attack/dos/flood.py --target http://192.168.137.1 --duration 60 --concurrency 50
```

| Option | Rôle | Défaut |
|---|---|---|
| `--target` | URL de base (obligatoire) | - |
| `--duration` | Durée en secondes (plafond 300) | 60 |
| `--concurrency` | Requêtes en parallèle | 50 |
| `--rps` | Débit total visé en req/s (`0` = sans limite) | 0 |
| `--path` | Chemin visé | `/api/transactions` |
| `--method` | `GET` ou `POST` | `POST` |
| `--auth` | Flood authentifié : utilisateur fictif (ex. `demo`), mot de passe dans `ATTACK_PASSWORD` | désactivé |

### Flood authentifié (recommandé pour dégrader vraiment)

Sans jeton, le flood s'arrête au 401 de payment-api (qui vérifie le JWT lui-même). Avec `--auth`, le script fait **un seul** login
(la route de login est limitée à 10/min), puis envoie de **vraies transactions de 0,01 EUR** qui
traversent toute la chaîne jusqu'à la transaction SQL dans la base. Sens alterné d'un worker à
l'autre : les soldes des comptes de démo restent stables.

```bash
export ATTACK_PASSWORD='<mot de passe demo, voir .env du PC Hôte>'
python attack/dos/flood.py --target http://192.168.137.1 --auth demo --concurrency 200 --duration 90
```

Le mot de passe se lit dans la variable d'environnement `ATTACK_PASSWORD`, jamais sur la ligne de
commande (il n'apparaît pas dans l'historique du shell ni dans la liste des processus).

Par défaut, le script martèle `POST /api/transactions`, la route la plus coûteuse (elle traverse le WAF, le frontal puis payment-api, qui vérifie le jeton et écrit en base). Sans jeton valide, payment-api répond 401, mais la charge sur toute la chaîne est réelle : l'objectif est de saturer, pas de réussir des transactions.

## Ce qu'on doit observer

Sur le dashboard (http://127.0.0.1:5173) et Grafana, pendant et après :

1. **`canary_up` tombe à 0** (ou taux de succès du canari qui chute) - c'est le signal d'un vrai incident.
2. Latence p95 qui monte, erreurs qui apparaissent.
3. Au WAF : requêtes `429` (rate-limit) si le débit dépasse `WAF_RATE_LIMIT`.
4. Le détecteur ML dépasse son seuil, la remédiation se déclenche, puis la transaction de contrôle réussit : phase « Après ».

À la fin, le script affiche le nombre de requêtes, les codes HTTP et les latences p50/p95/p99.

## Calibrage (IMPORTANT)

Le rate-limit du WAF (`WAF_RATE_LIMIT`, défaut `50r/s` par client) et celui du frontal peuvent absorber l'attaque : beaucoup de `429`, mais **aucune dégradation réelle**, donc rien à détecter. Il faut régler l'attaque et les limites ensemble jusqu'à une panne visible et reproductible :

- augmenter `--concurrency` (ex. 100, 200) ;
- viser une route sans rate-limit strict côté frontal (le WAF a une limite globale, le frontal en a une sur `/api/auth/token` et `/api/transactions`) ;
- **relâcher la limite `/api` du frontal** : c'est elle qui plafonne à 10 r/s par client. Dans le `.env` du PC Hôte, mettre `FRONTEND_API_RATE_LIMIT=1000r/s` et `FRONTEND_API_BURST=2000`, puis `docker compose --profile app up -d` (le frontal relit le template au démarrage) ;
- si besoin, relâcher aussi `WAF_RATE_LIMIT` dans `.env` (ex. `500r/s`) ;
- préférer le **flood authentifié** (`--auth demo`) : il atteint payment-api et la base, là où le flood anonyme s'arrête au 401 ;
- documenter la valeur retenue dans `docs/test-results/`.

> Rappel (Docker Desktop) : tout le trafic externe partage un seul bucket de rate-limit (IP de la passerelle Docker). Les leviers ci-dessus valent pour la démo sur le réseau du groupe ; voir `docs/test-results/calibrage-attaque-dos.md`.

Objectif de calibrage atteint quand : **depuis le PC Attaquant, un lancement fait tomber `canary_up` de façon visible et reproductible.** Noter la commande exacte et les réglages dans `docs/test-results/`.

> À caler avec l'infra : le rate-limit qui bloque l'attaque est aussi ce qui protège le service. La bonne démo montre le WAF qui absorbe une partie (429) **et** une charge assez forte pour dégrader quand même, jusqu'à la remédiation.
