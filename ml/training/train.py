"""Entraîne l'Isolation Forest sur du trafic nominal et enregistre le modèle pour ml-detector.

Deux sources de données :
  - un CSV collecté sur la plateforme (ml/training/collect.py), recommandé pour la démo ;
  - à défaut, un jeu nominal simulé reproductible (--synthetic), utile hors ligne.

Le modèle est écrit dans ml/models/model.joblib (monté en lecture seule par le conteneur).
Sans modèle, ml-detector entraîne de toute façon un modèle de repli synthétique au démarrage.

Exemples :
  python ml/training/train.py --data ml/data/nominal.csv
  python ml/training/train.py --synthetic
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from anomaly import FEATURE_NAMES, fit, synthetic_nominal  # noqa: E402
from model_store import save  # noqa: E402


def load_csv(path: Path) -> np.ndarray:
    with path.open(encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != FEATURE_NAMES:
            raise SystemExit(f"Colonnes attendues {FEATURE_NAMES}, trouvées {header}")
        rows = [[float(value) for value in row] for row in reader if row]
    if len(rows) < 100:
        raise SystemExit(f"Trop peu de relevés ({len(rows)}) : collecter plus longtemps (viser >= 100).")
    return np.array(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraînement du détecteur d'anomalies (Isolation Forest)")
    parser.add_argument("--data", help="CSV de métriques nominales (colonnes = features)")
    parser.add_argument("--synthetic", action="store_true", help="Jeu nominal simulé au lieu d'un CSV")
    parser.add_argument("--out", default="ml/models/model.joblib", help="Fichier modèle de sortie")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.data and not args.synthetic:
        data = load_csv(Path(args.data))
        source = f"csv:{args.data}:{len(data)}releves"
    else:
        data = synthetic_nominal(seed=args.seed)
        source = "synthetique"

    model, normalizer = fit(data, seed=args.seed)
    save(args.out, model, normalizer, source)
    print(f"Modèle entraîné sur {len(data)} relevés ({source}) -> {args.out}")
    print(f"Normaliseur : centre={normalizer.center:.4f}, pente={normalizer.scale:.4f}")


if __name__ == "__main__":
    main()
