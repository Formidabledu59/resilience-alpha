"""Tests du scénario de bout en bout, sans stack démarrée (réseau simulé)."""

import argparse
import sys

import httpx
import pytest

import resilience_scenario as sc


def make_args(**overrides) -> argparse.Namespace:
    values = dict(waf="http://192.168.137.1", prometheus="http://127.0.0.1:9090",
                  dashboard="http://127.0.0.1:5173", attack_seconds=90, concurrency=200,
                  auth=True, timeout=300, poll_seconds=0, ban_wait=0)
    values.update(overrides)
    return argparse.Namespace(**values)


def test_cible_par_defaut_dans_le_reseau_du_labo():
    # Une cible par défaut hors 192.168.137.0/24 serait refusée par le garde-fou de flood.py.
    args = sc.build_parser().parse_args([])
    assert args.waf.startswith("http://192.168.137.")
    assert args.auth is True
    assert sc.build_parser().parse_args(["--no-auth"]).auth is False


def test_commande_d_attaque():
    cmd = sc.attack_command(make_args())
    assert cmd[1].endswith("flood.py")
    assert cmd[cmd.index("--target") + 1] == "http://192.168.137.1"
    assert cmd[-2:] == ["--auth", "demo"]
    assert "--auth" not in sc.attack_command(make_args(auth=False))


def test_attaque_refusee_detectee_immediatement(monkeypatch):
    # flood.py refuse 127.0.0.1 et quitte avec le code 2 : le scénario doit s'arrêter tout de suite.
    monkeypatch.setattr(sc, "attack_command",
                        lambda args: [sys.executable, "-c", "raise SystemExit(2)"])
    assert sc.launch_attack(make_args(), startup_seconds=10) is None


def test_attaque_qui_tourne_est_renvoyee(monkeypatch):
    monkeypatch.setattr(sc, "attack_command",
                        lambda args: [sys.executable, "-c", "import time; time.sleep(30)"])
    attack = sc.launch_attack(make_args(), startup_seconds=0.5)
    assert attack is not None
    attack.kill()
    attack.wait()


def test_un_ancien_incident_clos_ne_donne_pas_un_faux_succes(monkeypatch):
    ancien = {"id": "inc-ancien", "status": "CLOSED"}
    monkeypatch.setattr(sc, "incidents", lambda dashboard: [ancien])
    monkeypatch.setattr(sc, "prometheus_scalar", lambda *a: None)
    ok, message, incident = sc.wait_for_recovery(make_args(), sc.time.monotonic() + 0.05, ignore={"inc-ancien"})
    assert not ok
    assert "aucun incident" in message
    assert incident is None


def test_nouvel_incident_ouvert_puis_clos(monkeypatch):
    etats = iter([[{"id": "inc-1", "status": "OPEN"}],
                  [{"id": "inc-1", "status": "VERIFYING"}],
                  [{"id": "inc-1", "status": "CLOSED"}]])
    monkeypatch.setattr(sc, "incidents", lambda dashboard: next(etats))
    monkeypatch.setattr(sc, "prometheus_scalar", lambda *a: None)
    ok, message, incident = sc.wait_for_recovery(make_args(), sc.time.monotonic() + 30)
    assert ok and "inc-1" in message
    assert incident["status"] == "CLOSED"


def test_incident_en_echec(monkeypatch):
    monkeypatch.setattr(sc, "incidents", lambda dashboard: [{"id": "inc-2", "status": "FAILED"}])
    ok, _, _ = sc.wait_for_recovery(make_args(), sc.time.monotonic() + 30)
    assert not ok


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://192.168.137.1/api/auth/token")
    return httpx.HTTPStatusError("erreur", request=request, response=httpx.Response(code, request=request))


def test_transaction_finale_attend_la_levee_du_ban(monkeypatch):
    appels = {"n": 0}

    def login(waf, password):
        appels["n"] += 1
        if appels["n"] < 3:
            raise _status_error(403)  # IP encore bannie
        return "jeton"
    monkeypatch.setattr(sc, "login", login)
    monkeypatch.setattr(sc, "business_transaction", lambda waf, token: {"status": "COMPLETED"})
    assert sc.final_transaction("http://192.168.137.1", "x", ban_wait=60, poll=0)["status"] == "COMPLETED"
    assert appels["n"] == 3


def test_transaction_finale_abandonne_apres_le_delai(monkeypatch):
    def login(waf, password):
        raise _status_error(403)
    monkeypatch.setattr(sc, "login", login)
    with pytest.raises(httpx.HTTPStatusError):
        sc.final_transaction("http://192.168.137.1", "x", ban_wait=0, poll=0)


def test_autre_erreur_http_non_masquee(monkeypatch):
    def login(waf, password):
        raise _status_error(500)
    monkeypatch.setattr(sc, "login", login)
    with pytest.raises(httpx.HTTPStatusError):
        sc.final_transaction("http://192.168.137.1", "x", ban_wait=60, poll=0)


def test_prometheus_scalar(monkeypatch):
    class Reponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data
    monkeypatch.setattr(httpx, "get", lambda *a, **k: Reponse({"data": {"result": [{"value": [0, "0.83"]}]}}))
    assert sc.prometheus_scalar("http://p", "q") == pytest.approx(0.83)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: Reponse({"data": {"result": []}}))
    assert sc.prometheus_scalar("http://p", "q") is None

    def injoignable(*a, **k):
        raise httpx.ConnectError("refusé")
    monkeypatch.setattr(httpx, "get", injoignable)
    assert sc.prometheus_scalar("http://p", "q") is None


def test_chronometrage_depuis_le_journal():
    debut = sc.datetime(2026, 10, 22, 9, 0, 0, tzinfo=sc.timezone.utc)
    incident = {"opened_at": "2026-10-22T09:00:25+00:00", "closed_at": "2026-10-22T09:00:52+00:00"}
    t = sc.timings(debut, incident)
    assert (t["detection"], t["recovery"], t["total"]) == (25, 27, 52)
    assert t["fits_clip"] is True
    lent = sc.timings(debut, {"opened_at": "2026-10-22T09:00:40+00:00", "closed_at": "2026-10-22T09:01:30+00:00"})
    assert lent["total"] == 90 and lent["fits_clip"] is False


def test_chronometrage_incident_non_clos():
    debut = sc.datetime(2026, 10, 22, 9, 0, 0, tzinfo=sc.timezone.utc)
    t = sc.timings(debut, {"opened_at": "2026-10-22T09:00:30+00:00", "closed_at": None})
    assert t["detection"] == 30 and t["recovery"] is None and t["fits_clip"] is False


def test_qui_a_detecte():
    assert sc.detected_by({"source": "ml-detector", "alerts": [{"source": "ml-detector"}]}) == "ML (Isolation Forest)"
    assert sc.detected_by({"source": "alertmanager", "alerts": [{"source": "alertmanager", "name": "TargetDown"}]}) == "TargetDown"


def test_rapport_markdown():
    resultats = [
        {"ok": True, "message": "ok", "incident": "inc-1", "detected_by": "ML (Isolation Forest)",
         "timings": {"detection": 25, "recovery": 27, "total": 52, "fits_clip": True}},
        {"ok": False, "message": "aucun incident déclenché", "incident": None},
    ]
    texte = sc.report_markdown(resultats, make_args())
    assert "| 1 | OK | ML (Isolation Forest) | 25 s | 27 s | 52 s | oui | inc-1 |" in texte
    assert "| 2 | ÉCHEC | - | - | - | - | non | - |" in texte
    assert "**1/2 essais réussis.**" in texte
    assert "Essai 2 : aucun incident déclenché" in texte
