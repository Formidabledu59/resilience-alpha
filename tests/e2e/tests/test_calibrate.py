"""Tests du calibrage du DoS (fonctions pures, sans stack)."""

import argparse

import calibrate_dos as cal


def releve(score, up=1, ratio=1.0, p95=0.05, alerts=0.0):
    return {"score": score, "canary_up": up, "canary_ratio": ratio, "latency_p95": p95, "alerts": alerts}


def test_palier_absorbe_sans_alerte():
    r = cal.summarize([releve(0.05), releve(0.2), releve(0.3)], threshold=0.7)
    assert r["max_score"] == 0.3
    assert r["above_threshold"] == 0
    assert r["ml_alert"] is False
    assert r["canary_down"] is False


def test_palier_qui_declenche_l_alerte_ml():
    samples = [releve(0.1, alerts=2), releve(0.75, up=0, ratio=0.6, p95=2.1, alerts=2),
               releve(0.8, ratio=0.5, alerts=2), releve(0.85, ratio=0.4, alerts=3)]
    r = cal.summarize(samples, threshold=0.7)
    assert r["ml_alert"] is True          # le compteur ml_alerts_sent_total a augmenté
    assert r["above_threshold"] == 3
    assert r["canary_down"] is True
    assert r["min_canary_ratio"] == 0.4 and r["max_latency_p95"] == 2.1


def test_prometheus_muet():
    r = cal.summarize([releve(None, up=None, ratio=None, p95=None, alerts=None)], threshold=0.7)
    assert r["max_score"] is None and r["ml_alert"] is False


def test_rapport_retient_le_premier_palier_qui_declenche():
    args = argparse.Namespace(auth=True, seconds=60, waf="http://192.168.137.1", threshold=0.7)
    rows = [
        {"concurrency": 100, "max_score": 0.3, "above_threshold": 0, "min_canary_ratio": 1.0,
         "canary_down": False, "max_latency_p95": 0.08, "ml_alert": False},
        {"concurrency": 200, "max_score": 0.82, "above_threshold": 3, "min_canary_ratio": 0.5,
         "canary_down": True, "max_latency_p95": 2.4, "ml_alert": True},
    ]
    texte = cal.report_markdown(rows, args)
    assert "| 100 | 0.30 | 0 | 100% | non | 0.08 s | non |" in texte
    assert "| 200 | 0.82 | 3 | 50% | oui | 2.40 s | **oui** |" in texte
    assert "Réglage retenu : concurrence 200" in texte


def test_rapport_sans_declenchement():
    args = argparse.Namespace(auth=True, seconds=60, waf="http://192.168.137.1", threshold=0.7)
    rows = [{"concurrency": 400, "max_score": 0.4, "above_threshold": 0, "min_canary_ratio": 1.0,
             "canary_down": False, "max_latency_p95": 0.1, "ml_alert": False}]
    assert "Aucun palier n'a déclenché" in cal.report_markdown(rows, args)


def test_paliers_par_defaut_croissants():
    args = cal.build_parser().parse_args([])
    assert args.levels == sorted(args.levels)
    assert args.waf.startswith("http://192.168.137.")
