"""Cœur du détecteur d'anomalies : features, entraînement Isolation Forest, score 0..1.

Source unique partagée par le service (`main.py`, repli synthétique au démarrage) et par
l'entraînement (`ml/training/train.py`, vrai modèle à partir de métriques collectées).

Le score d'anomalie est ramené dans [0, 1] par une sigmoïde calée sur la distribution du
trafic nominal : ~0,1 pour un point typiquement normal, 0,5 au 99e centile du nominal, proche
de 1 pour un point franchement hors distribution (DoS : canari en échec, latence et erreurs
qui montent). Le seuil d'alerte (ML_ANOMALY_THRESHOLD, défaut 0,7) se compare à ce score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Features, dans l'ordre. Chaque entrée : nom, requête PromQL, valeur nominale, écart-type nominal.
# Toutes sont disponibles dans Prometheus (le WAF et le CPU ne le sont pas : voir ml/README.md).
FEATURES = [
    ("canary_success_ratio", "canary_success_ratio", 1.0, 0.02),
    # Écart-type non nul : une feature constante à l'entraînement est ignorée par l'Isolation
    # Forest (aucune coupe possible), canary_up = 0 ne changerait alors rien au score.
    ("canary_up", "canary_up", 1.0, 0.01),
    ("latency_p95", "histogram_quantile(0.95, sum by (le) (rate(canary_latency_seconds_bucket[1m])))", 0.05, 0.02),
    ("throughput", "sum(rate(payment_transactions_total[1m]))", 0.25, 0.08),
    ("errors_5xx", 'sum(rate(http_requests_total{status="5xx"}[1m])) or vector(0)', 0.0, 0.01),
    ("request_rate", "sum(rate(http_requests_total[1m]))", 1.0, 0.3),
]
FEATURE_NAMES = [name for name, *_ in FEATURES]
QUERIES = {name: query for name, query, *_ in FEATURES}

LOW_SIGMOID = math.log(0.1 / 0.9)   # cible : score 0,1 pour un point nominal médian (raw = p50)


@dataclass
class Normalizer:
    """Transforme le score brut de l'Isolation Forest (plus haut = plus anormal) en score 0..1."""

    center: float   # 99e centile du brut nominal -> score 0,5
    scale: float    # pente de la sigmoïde

    def score(self, raw: float) -> float:
        return 1.0 / (1.0 + math.exp(-self.scale * (raw - self.center)))

    def to_dict(self) -> dict:
        return {"center": self.center, "scale": self.scale}

    @classmethod
    def from_dict(cls, data: dict) -> "Normalizer":
        return cls(center=float(data["center"]), scale=float(data["scale"]))


def synthetic_nominal(n: int = 4000, seed: int = 42) -> np.ndarray:
    """Jeu de trafic nominal simulé, pour entraîner un modèle de repli reproductible."""
    rng = np.random.default_rng(seed)
    columns = []
    for _name, _query, mean, std in FEATURES:
        values = rng.normal(mean, std, n) if std > 0 else np.full(n, mean)
        columns.append(values)
    data = np.column_stack(columns)
    # Bornes physiques : ratio et canary_up dans [0,1], le reste positif
    data[:, :2] = np.clip(data[:, :2], 0.0, 1.0)
    data[:, 2:] = np.clip(data[:, 2:], 0.0, None)
    return data


def _raw_scores(model, data: np.ndarray) -> np.ndarray:
    # score_samples : plus haut = plus normal. On inverse pour que "plus haut = plus anormal".
    return -model.score_samples(data)


def fit(data: np.ndarray, seed: int = 42):
    """Entraîne l'Isolation Forest sur du trafic nominal et cale la sigmoïde. Renvoie (model, normalizer)."""
    from sklearn.ensemble import IsolationForest

    model = IsolationForest(n_estimators=200, contamination=0.01, random_state=seed)
    model.fit(data)
    raw = _raw_scores(model, data)
    p50, p99 = float(np.percentile(raw, 50)), float(np.percentile(raw, 99))
    spread = max(p99 - p50, 1e-6)
    normalizer = Normalizer(center=p99, scale=-LOW_SIGMOID / spread)  # raw=p50 -> ~0,1 ; raw=p99 -> 0,5
    return model, normalizer


def score_one(model, normalizer: Normalizer, features: dict) -> float:
    """Score d'anomalie 0..1 d'un relevé {nom: valeur}."""
    row = np.array([[features.get(name, mean) for name, _q, mean, _s in FEATURES]])
    return normalizer.score(float(_raw_scores(model, row)[0]))
