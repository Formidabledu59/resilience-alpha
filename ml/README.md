# ml/ : détection d'anomalies

Détection non supervisée par **Isolation Forest** (scikit-learn). Le service `ml-detector` lit les métriques de la plateforme dans Prometheus toutes les 5 secondes, en calcule un **score d'anomalie** entre 0 (normal) et 1 (anormal), l'expose dans Prometheus, et au-delà du seuil envoie une **alerte signée (HMAC)** au moteur de remédiation.

```
Prometheus  ──(6 features, 5 s)──►  ml-detector  ──score──►  /metrics (ml_anomaly_score)
                                          │
                                          └─ score ≥ seuil sur 3 relevés ─► webhook HMAC ─► remediation-engine
```

## Structure

| Chemin | Rôle |
|---|---|
| `detector/` | Service FastAPI (port 8000) : `anomaly.py` (modèle et score), `prometheus.py` (lecture des features), `model_store.py` (chargement / repli), `main.py` (boucle et webhook) |
| `training/collect.py` | Collecte des métriques nominales depuis Prometheus vers un CSV |
| `training/train.py` | Entraîne l'Isolation Forest et enregistre le modèle |
| `models/` | Modèle entraîné (`model.joblib`, non versionné : artefact binaire) |
| `data/` | Jeux de métriques collectés (non versionnés) |

## Features (6, toutes dans Prometheus)

`canary_success_ratio`, `canary_up`, `latency_p95` (canari), `throughput` (transactions/s), `errors_5xx`, `request_rate`.

> Le sujet cite aussi les blocages WAF et le CPU de payment-api. Ils ne sont **pas** dans Prometheus par choix d'architecture (le WAF n'a pas d'exporter, ses métriques sont dans Loki ; pas d'exporter CPU). La dégradation d'une attaque reste visible : le canari échoue, la latence et les erreurs montent. Les blocages WAF servent de leur côté aux règles SOC et au bilan d'incident.

## Score d'anomalie

Le brut de l'Isolation Forest est ramené dans [0, 1] par une sigmoïde calée sur le trafic nominal : environ 0,1 pour un point normal typique, 0,5 au 99e centile du nominal, proche de 1 hors distribution. Le seuil d'alerte est `ML_ANOMALY_THRESHOLD` (défaut **0,7**). Pour éviter les faux positifs, le service n'alerte qu'après **3 relevés consécutifs** au-dessus du seuil, avec un délai minimal entre deux alertes (`ML_ALERT_COOLDOWN_SECONDS`).

## Entraînement

1. **Collecter** du trafic nominal pendant que la plateforme tourne (sans attaque) :

   ```bash
   python ml/training/collect.py --minutes 30 --out ml/data/nominal.csv
   ```

2. **Entraîner** et enregistrer le modèle :

   ```bash
   python ml/training/train.py --data ml/data/nominal.csv        # sur données réelles
   python ml/training/train.py --synthetic                       # jeu nominal simulé (hors ligne)
   ```

Sans modèle dans `ml/models/`, **ml-detector entraîne un modèle de repli synthétique au démarrage** (reproductible) : la détection fonctionne toujours. Le métrique `ml_model_fallback` vaut alors 1. Pour une vraie démo, collecter puis entraîner, et redémarrer `ml-detector`.

## Résultats et limites

Scores du modèle de repli synthétique sur des situations types (détail et contexte : [`calibrage-attaque-dos.md`](../docs/test-results/calibrage-attaque-dos.md)) :

| Situation | Score | Alerte (seuil 0,7) |
|---|---|---|
| Trafic nominal | 0,03 | non |
| Flood absorbé par les rate-limits (seul le débit de requêtes monte) | 0,11 | non |
| Flood authentifié absorbé (débit de requêtes et de transactions) | 0,29 | non |
| Canari en échec seul | 0,63 | non |
| Service dégradé (succès 50 %, latence p95 2 s, erreurs 5xx) | 0,88 | **oui** |
| Arrêt de payment-api (répétition du 21/10, en conteneurs) | 0,05 → 0,70 en 54 s | `TargetDown` a déclenché avant le ML |

Ce que le modèle sait faire : repérer une **combinaison inhabituelle** de plusieurs indicateurs (succès du canari, latence, erreurs, débit). Ce n'est pas une règle codée en dur : le seuil porte sur un score appris à partir du trafic nominal.

Limites constatées :
- **Modèle de repli entraîné sur des données simulées** : à remplacer par un modèle entraîné sur 30 minutes de trafic nominal réel (étapes ci-dessus) avant la démonstration.
- **Une seule dégradation n'alerte pas toujours** : l'Isolation Forest isole mieux un point qui s'écarte sur plusieurs axes. Un canari en échec seul reste sous le seuil ; une panne franche est couverte par l'alerte Prometheus `TargetDown`.
- **Une attaque contenue ne déclenche rien** : si le WAF et le frontal absorbent le flood, le service n'est pas dégradé et aucun incident n'est ouvert. C'est voulu, mais le DoS de la démonstration doit être calibré pour dégrader réellement le service.
- **Délai de détection** : 3 relevés consécutifs × 5 s, plus le temps que les moyennes glissantes sur 1 minute (`rate[1m]`) réagissent. Réglable par `ML_ALERT_CONSECUTIVE` (2 = plus rapide, plus de faux positifs).
- **En industriel** : historique de plusieurs semaines (cycles jour / nuit, pics de fin de mois), réentraînement régulier, métriques supplémentaires (CPU, blocages WAF via un exporter), suivi des faux positifs avec les opérateurs.

## Métriques exposées

| Métrique | Signification |
|---|---|
| `ml_anomaly_score` | Score courant (0 à 1) |
| `ml_anomaly_threshold` | Seuil d'alerte |
| `ml_model_fallback` | 1 si modèle de repli synthétique |
| `ml_prometheus_reachable` | 1 si Prometheus a répondu au dernier relevé |
| `ml_feature_value{feature}` | Dernière valeur lue par feature |
| `ml_alerts_sent_total{result}` | Alertes envoyées (`ok` / `echec`) |

## Webhook

`POST` vers `REMEDIATION_WEBHOOK_URL`, corps `{score, threshold, detected_at, features}`, signé HMAC-SHA256 (en-têtes `X-Resilience-Timestamp` et `X-Resilience-Signature`). Format détaillé : [`docs/architecture/contracts.md`](../docs/architecture/contracts.md).

## Variables

| Variable | Rôle | Défaut |
|---|---|---|
| `PROMETHEUS_URL` | Source des features | `http://prometheus:9090` |
| `REMEDIATION_WEBHOOK_URL` | Destination des alertes | `http://remediation-engine:8000/webhook/ml` |
| `REMEDIATION_HMAC_SECRET` | Clé de signature (partagée avec le moteur) | `.env` |
| `ML_ANOMALY_THRESHOLD` | Seuil d'alerte | `0.7` |
| `MODEL_PATH` | Modèle à charger | `/models/model.joblib` |
| `ML_INTERVAL_SECONDS`, `ML_ALERT_CONSECUTIVE`, `ML_ALERT_COOLDOWN_SECONDS` | Cadence et anti-rebond | `5`, `3`, `60` |

## Tests

```bash
cd ml/detector && pip install -r requirements.txt pytest && python -m pytest
```

12 tests : score bas en nominal et haut en DoS, `canary_up` pris en compte, dégradation réaliste au-dessus du seuil et flood absorbé en dessous, moins de 5 % de faux positifs sur le nominal, score borné, reproductibilité, signature HMAC conforme au moteur, alerte après 3 relevés, pas d'alerte en nominal ni sur une séquence brève, robustesse si Prometheus est muet.
