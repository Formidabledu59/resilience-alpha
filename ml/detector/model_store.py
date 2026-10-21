"""Chargement / sauvegarde du modèle (Isolation Forest + normaliseur) avec joblib.

Un modèle enregistré est un dict : {"model", "normalizer", "features", "trained_at", "source"}.
Au démarrage, le service charge /models/model.joblib s'il existe, sinon il entraîne un modèle
de repli synthétique (reproductible) : la détection fonctionne toujours, même sans collecte.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib

from anomaly import FEATURE_NAMES, Normalizer, fit, synthetic_nominal


def save(path: str | Path, model, normalizer: Normalizer, source: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "normalizer": normalizer.to_dict(), "features": FEATURE_NAMES,
         "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source},
        path,
    )


def load(path: str | Path) -> dict:
    bundle = joblib.load(path)
    bundle["normalizer"] = Normalizer.from_dict(bundle["normalizer"])
    return bundle


def load_or_fallback(path: str | Path) -> dict:
    """Modèle enregistré si présent, sinon modèle synthétique de repli."""
    path = Path(path)
    if path.exists():
        bundle = load(path)
        bundle["fallback"] = False
        return bundle
    model, normalizer = fit(synthetic_nominal())
    return {"model": model, "normalizer": normalizer, "features": FEATURE_NAMES,
            "trained_at": None, "source": "synthetique-repli", "fallback": True}
