"""Tests de la collecte et de l'entraînement (sans Prometheus : réponses simulées)."""

import csv

import pytest

import collect
import train
from anomaly import FEATURE_NAMES


def test_series_ignore_valeurs_illisibles_et_nan():
    payload = {"data": {"result": [{"values": [[100, "1"], [115, "NaN"], [130, "abc"], [145, "0.5"]]}]}}
    assert collect.series(payload) == {100: 1.0, 145: 0.5}


def test_series_sans_resultat():
    assert collect.series({"data": {"result": []}}) == {}


def _ecrire_csv(path, lignes, entete=FEATURE_NAMES):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(entete)
        w.writerows(lignes)


def test_load_csv(tmp_path):
    fichier = tmp_path / "nominal.csv"
    _ecrire_csv(fichier, [[1, 1, 0.02, 0.2, 0, 0.6]] * 120)
    data = train.load_csv(fichier)
    assert data.shape == (120, len(FEATURE_NAMES))


def test_load_csv_refuse_trop_peu_de_releves(tmp_path):
    fichier = tmp_path / "court.csv"
    _ecrire_csv(fichier, [[1, 1, 0.02, 0.2, 0, 0.6]] * 10)
    with pytest.raises(SystemExit, match="Trop peu"):
        train.load_csv(fichier)


def test_load_csv_refuse_mauvaises_colonnes(tmp_path):
    fichier = tmp_path / "faux.csv"
    _ecrire_csv(fichier, [[1, 2]] * 120, entete=["a", "b"])
    with pytest.raises(SystemExit, match="Colonnes attendues"):
        train.load_csv(fichier)


def test_entrainement_complet_sur_csv(tmp_path, monkeypatch):
    # Nominal "réel" avec colonnes constantes : le modèle écrit doit voir le canari tomber.
    fichier, modele = tmp_path / "nominal.csv", tmp_path / "model.joblib"
    lignes = [[1, 1, 0.02 + (i % 5) * 0.001, 0.2 + (i % 3) * 0.01, 0, 0.6 + (i % 4) * 0.05] for i in range(200)]
    _ecrire_csv(fichier, lignes)
    monkeypatch.setattr("sys.argv", ["train.py", "--data", str(fichier), "--out", str(modele)])
    train.main()
    assert modele.exists()

    from model_store import load
    from anomaly import score_one
    bundle = load(str(modele))
    model, normalizer = bundle["model"], bundle["normalizer"]
    assert bundle["source"].startswith("csv:")
    base = dict(zip(FEATURE_NAMES, lignes[0]))
    degrade = {**base, "canary_success_ratio": 0.5, "latency_p95": 2.0, "errors_5xx": 0.5, "request_rate": 11.0}
    assert score_one(model, normalizer, base) < 0.5
    assert score_one(model, normalizer, degrade) >= 0.7
