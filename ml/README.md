# ml/ : détection d'anomalies

Détection non supervisée par **Isolation Forest** (scikit-learn). Le service `ml-detector` lit les métriques de la plateforme dans Prometheus toutes les 5 secondes, en calcule un **score d'anomalie** entre 0 (normal) et 1 (anormal), l'expose dans Prometheus, et au-delà du seuil envoie une **alerte signée (HMAC)** au moteur de remédiation.

```
Prometheus  ──(6 features, 5 s)──►  ml-detector  ──score──►  /metrics (ml_anomaly_score)
                                          │
                                          └─ score > seuil sur 3 relevés ─► webhook HMAC ─► remediation-engine
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

9 tests : score bas en nominal et haut en DoS, moins de 5 % de faux positifs sur le nominal, score borné, reproductibilité, signature HMAC conforme au moteur, alerte après 3 relevés, pas d'alerte en nominal ni sur une séquence brève, robustesse si Prometheus est muet.
