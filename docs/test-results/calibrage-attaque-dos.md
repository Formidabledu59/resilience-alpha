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
   - frontal : zone `/api` à **10 r/s** par IP (`FRONTEND_API_RATE_LIMIT`, rafale `FRONTEND_API_BURST` = 20, réglables dans `.env`), zone `/api/auth/token` à 10 r/min.
2. **Docker Desktop masque l'IP réelle** : tout le trafic externe arrive avec l'IP de la passerelle Docker, donc **partage un seul bucket** de rate-limit. L'attaquant se limite lui-même.
3. **Le canary est interne** (`app-net`, sa propre IP) : son bucket est distinct, il n'est jamais en concurrence avec le flood. D'où `canary_up` qui reste à 1.

Autrement dit : relâcher le WAF ne suffit pas (essai 2), car le frontal plafonne `/api` à 10 r/s ; et même sans aucune limite, le flood en 401 ne touche ni la base ni un traitement coûteux.

## Conséquences (à traiter avec l'infra et le dev, sur le réseau du groupe)

Le calibrage réel se fait sur `RESILIENCE-G16`. En WiFi, la latence (5 à 50 ms contre ~0,1 ms en localhost) immobilise chaque worker uvicorn bien plus longtemps : **le pool de workers peut s'épuiser et faire échouer le canary** là où localhost tient. À mesurer sur place.

Si, sur le réseau, `canary_up` ne tombe toujours pas, leviers par ordre de préférence :

1. **Relâcher la limite `/api` du frontal** (fait : `FRONTEND_API_RATE_LIMIT` et `FRONTEND_API_BURST` dans `.env`), pour que le flood atteigne payment-api.
2. **Flood authentifié** (fait : `flood.py --auth demo`, par défaut dans `resilience_scenario.py`) : un login, puis de vraies transactions qui touchent la base plutôt que de s'arrêter au 401.
3. **Monter la concurrence** (`--concurrency 300`+) et la durée, pour épuiser le pool de workers.
4. **Réduire le nombre de workers** d'auth-service / payment-api (uvicorn) pour un pool plus facile à saturer en démo.

## Ce qui marche déjà

- Le garde-fou refuse toute cible hors `192.168.137.0/24` (code de sortie 2). Vérifié.
- Le générateur produit une vraie charge concurrente et agrège codes HTTP et latences. Vérifié (2376 requêtes en 0,3 s avec 8 workers, transport simulé).
- Le WAF absorbe l'attaque (beaucoup de 429), ce qui est **visible dans Grafana** et constitue déjà une partie de la démonstration (le WAF tient).
- L'injection SQL/XSS (`attack/sqli/inject.py`) est bloquée en 403 par le WAF.

## Prochaine étape

Leviers 1 et 2 de la liste ci-dessus à essayer **sur le réseau du groupe** : vérifier l'IP vue par le WAF depuis le PC Attaquant, puis calibrer jusqu'à une chute de `canary_up` reproductible. Noter ici la commande et les réglages retenus.

## Revue de la chaîne de détection (22 octobre 2026)

Revue du code, sans Docker. Les scores ci-dessous sont calculés avec le modèle de repli synthétique du détecteur, qui est celui utilisé tant qu'aucun modèle n'est entraîné dans `ml/models/`.

| Situation simulée | Score ML | Alerte (seuil 0,7) |
|---|---|---|
| Nominal | 0,03 | non |
| Flood **absorbé** par les rate-limits (seul `request_rate` monte, environ 11 r/s) | 0,11 | **non** |
| Flood authentifié absorbé (`request_rate` 11, débit de transactions 5/s) | 0,29 | **non** |
| Canari en échec seul (`canary_up` 0, taux de succès 0) | 0,63 | non |
| **Service dégradé** (taux de succès 50 %, latence p95 2 s, erreurs 5xx) | **0,88** | **oui** |

**Conclusion** : le détecteur ne lève une alerte que si le service est **réellement dégradé** (plusieurs indicateurs bougent ensemble). Un flood absorbé par le WAF et le frontal ne déclenche rien. Ce comportement est voulu (pas de faux positif sur une attaque déjà contenue) : le calibrage doit viser une vraie dégradation. Ces trois cas sont figés dans `ml/detector/tests/test_anomaly.py`.

**Corrigé le 22/10** :
- `canary_up` était constant dans les données d'entraînement synthétiques, donc ignoré par l'Isolation Forest. Il a maintenant un léger écart-type (`ml/detector/anomaly.py`).
- `resilience_scenario.py` visait par défaut `127.0.0.1`, cible refusée par le garde-fou : le scénario attendait 5 minutes pour rien. Il vise maintenant `192.168.137.1`, s'arrête aussitôt si l'attaque ne démarre pas, ignore les incidents antérieurs et attend la levée du ban avant la transaction finale.

**Paramètres côté remédiation** (valeurs par défaut du code, absentes de `.env`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `ML_ANOMALY_THRESHOLD` | 0,7 | Seuil d'alerte du détecteur |
| `BAN_MIN_REQUESTS` | 100 | Refus WAF (403/429) à partir desquels une IP est bannie |
| `BAN_MINUTES` | 5 | Durée du ban avant levée automatique |
| `VERIFY_TIMEOUT_SECONDS` | 180 | Délai maximal de retour au nominal avant la transaction de contrôle |

**Point d'attention** : derrière Docker Desktop, le PC Hôte et le PC Attaquant arrivent au WAF avec la même IP. Si le flood produit au moins 100 refus, la remédiation bannit cette IP : tout l'externe est coupé pendant 5 minutes (le canary, interne, continue). C'est attendu pendant la démonstration : il faut l'annoncer au jury.

**Réglages à essayer sur `RESILIENCE-G16`** (PC Hôte, point d'accès actif, stack complète) :

```bash
# .env du PC Hôte : relâcher le frontal pour que le flood atteigne payment-api, puis redémarrer le frontal
FRONTEND_API_RATE_LIMIT=200r/s
FRONTEND_API_BURST=400

ATTACK_PASSWORD='<mot de passe demo>' python tests/e2e/resilience_scenario.py --concurrency 300 --attack-seconds 120
```

Noter ici les réglages retenus et le résultat (score ML maximal, `canary_up`, identifiant et durée de l'incident).
