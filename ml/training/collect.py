"""Collecte des métriques de trafic nominal depuis Prometheus, vers un CSV d'entraînement.

À lancer pendant que la plateforme tourne en conditions normales (sans attaque), par exemple
avec le canary et un trafic de démonstration. Écrit une ligne par pas de temps.

Depuis le PC Hôte (Prometheus publié sur 127.0.0.1:9090) :
  python ml/training/collect.py --minutes 30 --out ml/data/nominal.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from anomaly import FEATURE_NAMES, QUERIES  # noqa: E402


def query_range(base_url: str, promql: str, start: float, end: float, step: int) -> dict:
    params = urllib.parse.urlencode({"query": promql, "start": int(start), "end": int(end), "step": step})
    with urllib.request.urlopen(f"{base_url}/api/v1/query_range?{params}", timeout=15) as response:  # noqa: S310
        import json
        return json.load(response)


def series(payload: dict) -> dict[int, float]:
    result = payload.get("data", {}).get("result", [])
    if not result:
        return {}
    points = {}
    for timestamp, value in result[0]["values"]:
        try:
            v = float(value)
        except ValueError:
            continue
        if v == v:  # pas NaN
            points[int(timestamp)] = v
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte de métriques nominales pour l'entraînement ML")
    parser.add_argument("--url", default="http://127.0.0.1:9090", help="URL de Prometheus")
    parser.add_argument("--minutes", type=float, default=30, help="Fenêtre passée à collecter (minutes)")
    parser.add_argument("--step", type=int, default=15, help="Pas d'échantillonnage (secondes)")
    parser.add_argument("--out", default="ml/data/nominal.csv", help="Fichier CSV de sortie")
    args = parser.parse_args()

    end = time.time()
    start = end - args.minutes * 60
    columns = {name: series(query_range(args.url.rstrip("/"), QUERIES[name], start, end, args.step))
               for name in FEATURE_NAMES}
    timestamps = sorted(set().union(*(c.keys() for c in columns.values())) if any(columns.values()) else [])
    if not timestamps:
        print("Aucune donnée collectée : la plateforme tourne-t-elle (canary, trafic) ?", file=sys.stderr)
        raise SystemExit(1)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(FEATURE_NAMES)
        for ts in timestamps:
            row = [columns[name].get(ts) for name in FEATURE_NAMES]
            if all(value is not None for value in row):  # ligne complète uniquement
                writer.writerow([round(v, 6) for v in row])
                kept += 1
    print(f"{kept} relevés nominaux écrits dans {out}")


if __name__ == "__main__":
    main()
