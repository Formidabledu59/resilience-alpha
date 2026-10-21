# ml-detector

Service de détection d'anomalies (FastAPI, port `8000`, réseau `obs-net`, aucun port publié).
Lit 6 features dans Prometheus toutes les 5 s, calcule un score d'anomalie (Isolation Forest),
l'expose dans `/metrics`, et au-delà du seuil (sur 3 relevés consécutifs) envoie une alerte
signée HMAC à `remediation-engine`.

Vue d'ensemble, features, entraînement et contrat : [`../README.md`](../README.md) et
[`docs/architecture/contracts.md`](../../docs/architecture/contracts.md).

## Fichiers

| Fichier | Rôle |
|---|---|
| `anomaly.py` | Features, entraînement, score 0..1 (source partagée avec `ml/training`) |
| `prometheus.py` | Lecture des features dans Prometheus (lecture seule) |
| `model_store.py` | Chargement du modèle, repli synthétique si absent |
| `main.py` | API, boucle de détection, webhook signé |

Sans modèle dans `/models`, un modèle de repli synthétique est entraîné au démarrage
(`ml_model_fallback = 1`) : la détection fonctionne toujours.

## Lancer

```bash
docker compose --profile ia up -d --build ml-detector
```

## Tests

```bash
pip install -r requirements.txt pytest
python -m pytest
```
