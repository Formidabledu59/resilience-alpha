import asyncio

from conftest import FakeObserver, sample_evidence
from engine import Engine
from journal import Journal


def alert(name="WafBlocagesModSecurity", fingerprint="f1"):
    return {"name": name, "source": "alertmanager", "auth": "bearer valide", "at": "2026-10-20T14:00:00+00:00",
            "severity": "warning", "summary": "test", "fingerprint": fingerprint}


async def run_incident(tmp_path, observer, probe_result, executor=None, name="WafBlocagesModSecurity"):
    async def probe():
        return probe_result

    engine = Engine(Journal(tmp_path / "j.jsonl", echo=False), observer, probe, executor=executor,
                    verify_timeout=1.0, poll_interval=0.01)
    incident_id = await engine.receive(alert(name))
    await asyncio.gather(*engine.tasks)
    return engine, engine.journal.get(incident_id)


def test_incident_cloture_apres_transaction_de_controle(tmp_path, observer):
    ok = {"ok": True, "status": "COMPLETED", "transaction_id": 7, "latency_seconds": 0.04}
    engine, incident = asyncio.run(run_incident(tmp_path, observer, ok))
    assert incident["status"] == "CLOSED"
    assert incident["closed_at"]
    assert set(incident["evidence"]) == {"opening", "closing"}
    actions = [s["action"] for s in incident["steps"]]
    assert actions[0].startswith("Alerte reçue : WafBlocagesModSecurity")
    assert "Aucune action corrective nécessaire" in actions  # attaque déjà bloquée par le WAF
    assert "Transaction de contrôle (POST /probe)" in actions
    assert engine.journal.verify()["ok"]


def test_echec_si_la_transaction_de_controle_echoue(tmp_path, observer):
    ko = {"ok": False, "status": "ERROR", "detail": "HTTP 503"}
    _, incident = asyncio.run(run_incident(tmp_path, observer, ko))
    assert incident["status"] == "FAILED"
    assert "Intervention humaine requise" in incident["summary"]["outcome"]


def test_echec_si_le_canari_ne_revient_pas(tmp_path):
    observer = FakeObserver(evidence=sample_evidence(canary_min=0.2), canary=(0, 0.2))
    _, incident = asyncio.run(run_incident(tmp_path, observer, {"ok": True, "status": "COMPLETED"}))
    assert incident["status"] == "FAILED"
    assert any(s["action"] == "Canari toujours dégradé" for s in incident["steps"])


def test_playbooks_de_la_liste_blanche_executes_et_traces(tmp_path, observer):
    executed = []

    async def executor(playbook, incident):
        executed.append(playbook)
        return "172.23.0.1 bannie pour 5 minutes"

    ok = {"ok": True, "status": "COMPLETED", "transaction_id": 9, "latency_seconds": 0.05}
    _, incident = asyncio.run(run_incident(tmp_path, observer, ok, executor, name="WafRateLimitSature"))
    assert executed == ["ban_ip.yml"]
    assert {"layer": "Moteur de remédiation", "action": "Playbook ban_ip.yml",
            "result": "172.23.0.1 bannie pour 5 minutes"} in incident["defenses"]


def test_alerte_de_meme_categorie_rattachee_a_l_incident_actif(tmp_path, observer):
    async def scenario():
        async def probe():
            return {"ok": True, "status": "COMPLETED"}

        engine = Engine(Journal(tmp_path / "j.jsonl", echo=False), observer, probe, verify_timeout=1.0, poll_interval=0.01)
        first = await engine.receive(alert(fingerprint="a"))
        second = await engine.receive(alert(fingerprint="b"))
        other = await engine.receive(alert("WafRateLimitSature", fingerprint="c"))
        await asyncio.gather(*engine.tasks)
        return engine, first, second, other

    engine, first, second, other = asyncio.run(scenario())
    assert first == second != other
    assert len(engine.journal.get(first)["alerts"]) == 2


def test_incident_interrompu_par_un_redemarrage_est_trace(tmp_path, observer):
    journal = Journal(tmp_path / "j.jsonl", echo=False)
    journal.append("incident.opened", {"id": "inc-2026-10-20-001", "status": "REMEDIATING", "category": "dos",
                                       "category_label": "DoS", "source": "ml-detector",
                                       "opened_at": "2026-10-20T14:00:05+00:00", "alerts": [], "steps": [], "evidence": {}})

    async def probe():
        return {}

    engine = Engine(Journal(tmp_path / "j.jsonl", echo=False), observer, probe)
    incident = engine.journal.get("inc-2026-10-20-001")
    assert incident["status"] == "FAILED"
    assert incident["steps"][-1]["action"] == "Moteur redémarré pendant l'incident"


class SequenceObserver(FakeObserver):
    """Canari qui évolue relevé après relevé (le dernier état se répète)."""

    def __init__(self, states):
        super().__init__()
        self.states = list(states)

    async def canary_state(self):
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


def test_reprise_validee_sans_attendre_la_fenetre_de_60_s(tmp_path):
    # Après une panne, le taux sur 60 s reste bas alors que le canari réussit à nouveau :
    # 3 relevés consécutifs à canary_up = 1 suffisent avant la transaction de contrôle.
    observer = SequenceObserver([(0, 0.2), (1, 0.4), (1, 0.5), (1, 0.6)])
    ok = {"ok": True, "status": "COMPLETED", "transaction_id": 11, "latency_seconds": 0.05}
    _, incident = asyncio.run(run_incident(tmp_path, observer, ok))
    assert incident["status"] == "CLOSED"
    assert any(s["action"] == "Vérification canary_up" and s["result"].startswith("1 sur 3")
               for s in incident["steps"])


def test_canari_instable_ne_valide_pas_la_reprise(tmp_path):
    # canary_up qui oscille ne compte jamais 3 succès d'affilée : échec, intervention humaine.
    states = [(1, 0.5), (0, 0.5)] * 50
    observer = SequenceObserver(states)
    _, incident = asyncio.run(run_incident(tmp_path, observer, {"ok": True, "status": "COMPLETED"}))
    assert incident["status"] == "FAILED"


def test_metriques_anterieures_au_redemarrage_ne_valident_pas_la_reprise(tmp_path):
    # Répétition du 22/10 (inc-2026-10-22-005) : juste après restart_api.yml, Prometheus montrait
    # encore canary_up = 1 et 100 % de succès sur 60 s ; la vérification passait au 1er relevé et
    # la transaction de contrôle tombait sur payment-api en cours de redémarrage (HTTP 502).
    observer = SequenceObserver([(1, 1.0), (0, 0.9), (1, 0.9), (1, 0.9), (1, 0.9)])
    ok = {"ok": True, "status": "COMPLETED", "transaction_id": 12, "latency_seconds": 0.03}
    _, incident = asyncio.run(run_incident(tmp_path, observer, ok))
    assert incident["status"] == "CLOSED"
    verification = next(s for s in incident["steps"] if s["action"] == "Vérification canary_up")
    assert verification["result"].startswith("1 sur 3")   # pas validé sur la mesure périmée


def test_transaction_de_controle_reessayee_apres_un_echec_passager(tmp_path, observer):
    reponses = iter([{"ok": False, "status": "ERROR", "detail": "HTTP 502"},
                     {"ok": True, "status": "COMPLETED", "transaction_id": 13, "latency_seconds": 0.03}])

    async def scenario():
        async def probe():
            return next(reponses)
        engine = Engine(Journal(tmp_path / "j.jsonl", echo=False), observer, probe,
                        verify_timeout=1.0, poll_interval=0.01)
        incident_id = await engine.receive(alert())
        await asyncio.gather(*engine.tasks)
        return engine.journal.get(incident_id)

    incident = asyncio.run(scenario())
    assert incident["status"] == "CLOSED"
    actions = [s["action"] for s in incident["steps"]]
    assert "Transaction de contrôle (essai 1/3)" in actions          # l'échec reste tracé
    assert actions.count("Transaction de contrôle (POST /probe)") == 1


def test_transaction_de_controle_toujours_en_echec(tmp_path, observer):
    ko = {"ok": False, "status": "ERROR", "detail": "HTTP 502"}
    _, incident = asyncio.run(run_incident(tmp_path, observer, ko))
    assert incident["status"] == "FAILED"
    assert [s["action"] for s in incident["steps"]].count("Transaction de contrôle (essai 2/3)") == 1


def test_relecture_des_preuves_avant_le_ban(tmp_path, observer):
    async def scenario():
        async def probe():
            return {"ok": True, "status": "COMPLETED"}
        engine = Engine(Journal(tmp_path / "j.jsonl", echo=False), observer, probe,
                        verify_timeout=1.0, poll_interval=0.01)
        incident_id = await engine.receive(alert())
        await asyncio.gather(*engine.tasks)
        refreshed = await engine.refresh_evidence(incident_id)
        return refreshed, len(observer.windows)

    refreshed, collections = asyncio.run(scenario())
    assert refreshed["evidence"]["opening"]["collected_at"]
    assert collections == 3   # ouverture, bilan, puis la relecture demandée
