"""Tests des fonctions pures du flood (aucune requête réseau)."""

import importlib.util
from pathlib import Path

import pytest

# flood.py est un script (dossier sans __init__) : on le charge par son chemin.
_spec = importlib.util.spec_from_file_location("flood", Path(__file__).resolve().parent.parent / "dos" / "flood.py")
flood = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flood)


def test_payload_anonyme_identique_pour_tous():
    assert flood.payload_for(0, authenticated=False) == flood.PAYLOAD
    assert flood.payload_for(1, authenticated=False) == flood.PAYLOAD


def test_payload_authentifie_alterne_le_sens_et_garde_les_soldes_stables():
    pair = flood.payload_for(0, authenticated=True)
    impair = flood.payload_for(1, authenticated=True)
    assert pair["amount"] == impair["amount"] == "0.01"
    # Un worker sur deux renvoie l'argent dans l'autre sens.
    assert (pair["from_account"], pair["to_account"]) == (impair["to_account"], impair["from_account"])


def test_percentile():
    assert flood.percentile([], 0.95) == 0.0
    valeurs = [float(i) for i in range(1, 101)]
    assert flood.percentile(valeurs, 0.5) == 51.0
    assert flood.percentile(valeurs, 0.99) == 100.0
    assert flood.percentile([3.0, 1.0, 2.0], 1.0) == 3.0


def test_stats_compte_codes_et_erreurs():
    stats = flood.Stats()
    stats.record(200, 0.01)
    stats.record(429, 0.02)
    stats.record(None, 1.0)
    assert stats.sent == 3
    assert stats.errors == 1
    assert stats.codes[200] == 1 and stats.codes[429] == 1


def test_duree_plafonnee():
    assert flood.MAX_DURATION == 300


@pytest.mark.parametrize("cible", ["http://127.0.0.1", "http://8.8.8.8"])
def test_main_refuse_une_cible_hors_labo(monkeypatch, cible):
    monkeypatch.setattr("sys.argv", ["flood.py", "--target", cible, "--duration", "1"])
    with pytest.raises(SystemExit) as exc:
        flood.main()
    assert exc.value.code == 2
