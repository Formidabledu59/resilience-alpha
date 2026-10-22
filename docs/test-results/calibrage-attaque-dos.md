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
| `BAN_MIN_FLOOD_REQUESTS` | 1000 | Requêtes (toutes réponses) à partir desquelles une IP est bannie, même sans refus (ajouté le 22/10 : avec les limites relâchées, l'attaquant n'était pas banni) |
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

## Calibrage réel du 22 octobre 2026 (point d'accès actif)

PC Hôte, point d'accès `RESILIENCE-G16` actif, attaque envoyée sur `http://192.168.137.1` (WAF), stack complète, modèle ML entraîné sur 20 minutes de trafic nominal réel (121 relevés, `ml_model_fallback = 0`). Outil : `tests/e2e/calibrate_dos.py`, flood authentifié.

### Réglages par défaut (WAF 50 r/s, frontal 10 r/s par IP)

| Concurrence | Requêtes | Réponses | Score ML max | Canari | Ce qui s'est passé |
|---|---|---|---|---|---|
| 100 | 12 945 en 60 s | 620 × 201, 12 325 × **429** | 0,43 | intact (100 %) | La règle SOC `WafRateLimitSature` détecte la saturation : **ban en 5 s**, transaction de contrôle `COMPLETED`, incident `CLOSED` (inc-2026-10-22-001) |
| 200 | 11 169 | 51 × 201, 8 255 × 429, 2 861 × **403** | 0,43 | intact | L'attaquant est déjà banni : ses requêtes sont refusées en 403 |

**Lecture** : les limites de débit absorbent l'attaque, le service n'est jamais dégradé, le **ML ne déclenche pas** (comportement voulu : pas d'incident ML sur une attaque contenue). La défense passe par le **SOC** (Loki → Alertmanager → ban), en boucle fermée et sans intervention.

Défaut relevé : les 403 du ban ont ouvert un second incident classé « attaque applicative » (`WafBlocagesModSecurity`, inc-2026-10-22-002), alors qu'il s'agit de la suite du DoS. Sans conséquence (aucune action, clos en 1 s), mais à expliquer si le jury consulte le journal.

### Limites de débit relâchées (WAF et frontal à 2 000 r/s)

| Concurrence | Score ML max | Relevés ≥ 0,7 | Canari (succès min) | Latence p95 max | Alerte ML |
|---|---|---|---|---|---|
| 200 | **0,78** | 3 | 83 % | 0,36 s (×7) | **oui** |

Incident `inc-2026-10-22-003`, ouvert par le **détecteur ML** (alerte signée HMAC) :

```
09:03:24  Alerte reçue : AnomalieML (HMAC valide)   score 0,78 au-delà du seuil 0,70
09:03:28  Playbook ban_ip.yml                       172.23.0.1 bannie au WAF pour 5 minutes
09:03:32  Playbook restart_api.yml                  payment-api redémarré
09:03:47  Vérification canary_up                    1 sur 3 relevés (taux sur 60 s encore à 75 %)
09:03:47  Transaction de contrôle (POST /probe)     COMPLETED
09:03:47  Incident CLOSED                           23 s après l'alerte
```

**Le chemin attaque → détection ML → remédiation → transaction de contrôle est démontré.** Sans le nouveau critère de vérification (3 relevés consécutifs), le moteur aurait attendu environ une minute de plus que le taux de succès sur 60 s remonte à 95 %.

### Réglage proposé pour la démonstration (à valider par l'équipe)

Deux voies automatiques, toutes deux démontrées :

| Réglage | Détection | Intérêt pour le jury |
|---|---|---|
| Limites par défaut | SOC (`WafRateLimitSature`), ban en ~5 s | Défense en profondeur : le WAF tient, le SOC réagit |
| Limites relâchées (`WAF_RATE_LIMIT` et `FRONTEND_API_RATE_LIMIT` à 2000r/s, rafales à 4000) | **ML** (score 0,78), ban + relance, reprise prouvée en ~23 s | Montre le ML branché sur la remédiation (axe 2 de la grille) |

Pour la démonstration en direct et le Clip Chrono, nous proposons les **limites relâchées, concurrence 200** : c'est le scénario qui fait intervenir la détection par apprentissage. À annoncer au jury : les limites de débit sont volontairement relâchées pour laisser l'attaque atteindre le service ; en production, elles restent la première ligne de défense (premier tableau).

## Calibrage automatique du 22/10/2026 09:03 UTC

Flood authentifié, 60 s par palier, cible http://192.168.137.1, seuil ML 0.7.

| Concurrence | Score ML max | Relevés ≥ seuil | Canari (succès min) | Canari tombé | Latence p95 max | Alerte ML |
|---|---|---|---|---|---|---|
| 200 | 0.78 | 3 | 83% | non | 0.36 s | **oui** |

**Réglage retenu : concurrence 200** (premier palier qui déclenche la détection ML).
