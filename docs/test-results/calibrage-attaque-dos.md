# Calibrage de l'attaque DoS

> Mesures du 20 octobre 2026, sur le PC Hôte (stack de dev, `127.0.0.1`), rate-limit du WAF par défaut sauf mention.
> ⚠️ Localhost est le **cas le plus favorable au défenseur** (requêtes très rapides, pool de workers libéré vite). Le calibrage **réel** doit se refaire sur le réseau `RESILIENCE-G16` depuis le PC Attaquant (voir « Conséquences »).

## Question

L'attaque `attack/dos/flood.py` dégrade-t-elle vraiment le service (`canary_up` qui tombe), ou le rate-limit absorbe-t-il tout ?

## Mesures

| Essai | Charge | WAF rate-limit | Résultat | `canary_up` |
|---|---|---|---|---|
| 1 | 200 workers, 30 s, `POST /api/transactions` | 50 r/s (défaut) | 2219/2546 en **429**, 327 en 401 | **reste à 1** |
| 2 | 300 workers, 40 s, `POST /api/transactions` | 10000 r/s | 2595/3002 en **429**, 407 en 401 | **reste à 1** |

Dans les deux cas, latence de l'attaquant très élevée (p95 7 à 12 s : file d'attente du rate-limit), mais **le service métier n'est pas dégradé**.

## Pourquoi le service ne tombe pas

1. **Deux rate-limits en série**, chacun **par IP source** :
   - WAF : `WAF_RATE_LIMIT` (défaut 50 r/s) ;
   - frontal : zone `/api` à **10 r/s** par IP (codée dans `services/frontend/nginx.conf`), zone `/api/auth/token` à 10 r/min.
2. **Docker Desktop masque l'IP réelle** : tout le trafic externe arrive avec l'IP de la passerelle Docker, donc **partage un seul bucket** de rate-limit. L'attaquant se limite lui-même.
3. **Le canary est interne** (`app-net`, sa propre IP) : son bucket est distinct, il n'est jamais en concurrence avec le flood. D'où `canary_up` qui reste à 1.

Autrement dit : relâcher le WAF ne suffit pas (essai 2), car le frontal plafonne `/api` à 10 r/s ; et même sans aucune limite, le flood en 401 ne touche ni la base ni un traitement coûteux.

## Conséquences (à traiter avec l'infra et le dev, sur le réseau du groupe)

Le calibrage réel se fait sur `RESILIENCE-G16`. En WiFi, la latence (5 à 50 ms contre ~0,1 ms en localhost) immobilise chaque worker uvicorn bien plus longtemps : **le pool de workers peut s'épuiser et faire échouer le canary** là où localhost tient. À mesurer sur place.

Si, sur le réseau, `canary_up` ne tombe toujours pas, leviers par ordre de préférence :

1. **Rendre la limite `/api` du frontal réglable** (variable d'env) et la relâcher pour la démo, pour que le flood atteigne payment-api.
2. **Flood authentifié** : obtenir un jeton valide (login `demo`) et marteler `POST /api/transactions` avec, pour toucher la base (transaction SQL réelle) plutôt que de s'arrêter au 401.
3. **Monter la concurrence** (`--concurrency 300`+) et la durée, pour épuiser le pool de workers.
4. **Réduire le nombre de workers** d'auth-service / payment-api (uvicorn) pour un pool plus facile à saturer en démo.

## Ce qui marche déjà

- Le garde-fou refuse toute cible hors `192.168.137.0/24` (code de sortie 2). Vérifié.
- Le générateur produit une vraie charge concurrente et agrège codes HTTP et latences. Vérifié (2376 requêtes en 0,3 s avec 8 workers, transport simulé).
- Le WAF absorbe l'attaque (beaucoup de 429), ce qui est **visible dans Grafana** et constitue déjà une partie de la démonstration (le WAF tient).
- L'injection SQL/XSS (`attack/sqli/inject.py`) est bloquée en 403 par le WAF.

## Prochaine étape

Points 1 et 2 de la liste de Papa à refaire **sur le réseau du groupe** : vérifier l'IP vue par le WAF depuis le PC Attaquant, puis calibrer jusqu'à une chute de `canary_up` reproductible. Noter ici la commande et les réglages retenus.
