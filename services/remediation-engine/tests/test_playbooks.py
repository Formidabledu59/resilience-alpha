import asyncio

from conftest import make_incident, sample_evidence
from playbooks import AnsibleExecutor, ips_to_ban, service_to_restart


def test_seules_les_ip_au_dela_du_seuil_sont_bannies():
    incident = make_incident(evidence=sample_evidence(blocked=500))
    incident["evidence"]["opening"]["waf"]["clients"].append({"ip": "172.24.0.9", "count": 3})  # canary
    assert ips_to_ban(incident, minimum=100) == ["172.23.0.1"]
    assert ips_to_ban(make_incident(evidence=sample_evidence(blocked=10)), minimum=100) == []


def test_service_a_redemarrer_selon_l_alerte():
    incident = make_incident()
    assert service_to_restart(incident) == "payment-api"
    incident["alerts"].append({"name": "TargetDown", "details": {"job": "auth-service"}})
    assert service_to_restart(incident) == "auth-service"
    incident["alerts"].append({"name": "TargetDown", "details": {"job": "postgres"}})  # hors liste blanche
    assert service_to_restart(incident) == "auth-service"


def test_ban_puis_levee_automatique_tracee():
    calls, notes = [], []

    async def runner(name, extra_vars):
        calls.append((name, extra_vars))
        return f"{name} ok"

    async def notify(incident_id, action, result):
        notes.append((incident_id, action, result))

    async def scenario():
        executor = AnsibleExecutor(notify=notify, runner=runner, ban_minutes=0.0001)
        result = await executor("ban_ip.yml", make_incident(evidence=sample_evidence(blocked=500)))
        await asyncio.gather(*executor.tasks)
        return result

    assert asyncio.run(scenario()) == "ban_ip.yml ok"
    assert calls[0] == ("ban_ip.yml", {"incident_id": "inc-2026-10-20-001", "ban_ips": ["172.23.0.1"], "ban_minutes": 0.0001})
    assert calls[1] == ("unban_ip.yml", {"incident_id": "inc-2026-10-20-001"})
    assert notes == [("inc-2026-10-20-001", "Levée du ban (unban_ip.yml)", "unban_ip.yml ok")]


def test_pas_de_ban_sans_ip_suspecte():
    async def runner(name, extra_vars):
        raise AssertionError("aucun playbook ne doit être lancé")

    executor = AnsibleExecutor(runner=runner)
    result = asyncio.run(executor("ban_ip.yml", make_incident(evidence=sample_evidence(blocked=5))))
    assert result.startswith("aucune IP")
