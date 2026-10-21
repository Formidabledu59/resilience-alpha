import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import main

SECRET, TOKEN = "secret-de-test", "token-de-test"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REMEDIATION_HMAC_SECRET", SECRET)
    monkeypatch.setenv("REMEDIATION_BEARER_TOKEN", TOKEN)
    monkeypatch.setattr(main, "JOURNAL_PATH", str(tmp_path / "incidents.jsonl"))
    with TestClient(main.app) as test_client:
        async def no_lifecycle(incident_id):  # pas de Prometheus ni de canary pendant les tests
            return None

        main.app.state.engine.run = no_lifecycle
        yield test_client


def signed(body: bytes, secret=SECRET, timestamp=None):
    timestamp = str(int(timestamp if timestamp is not None else time.time()))
    signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-Resilience-Timestamp": timestamp, "X-Resilience-Signature": signature, "Content-Type": "application/json"}


ML_BODY = json.dumps({"score": 0.91, "threshold": 0.7, "features": {"latency_p95": 1.2}}).encode()


def test_health_et_metrics(client):
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/metrics").text
    for name in ("remediation_incidents_total", "remediation_incidents_open", "remediation_journal_integrity"):
        assert name in body


def test_webhook_ml_signe_ouvre_un_incident(client):
    response = client.post("/webhook/ml", content=ML_BODY, headers=signed(ML_BODY))
    assert response.status_code == 202
    incidents = client.get("/incidents").json()
    assert incidents[0]["id"] == response.json()["incident"]
    assert incidents[0]["category"] == "anomalie"
    assert incidents[0]["steps"][0]["action"] == "Alerte reçue : AnomalieML (HMAC valide)"


@pytest.mark.parametrize("headers", [
    signed(ML_BODY, secret="mauvais-secret"),
    signed(ML_BODY, timestamp=time.time() - 600),  # rejeu d'une vieille alerte
    {"Content-Type": "application/json"},
])
def test_webhook_ml_refuse_signature_invalide(client, headers):
    assert client.post("/webhook/ml", content=ML_BODY, headers=headers).status_code == 401
    assert client.get("/incidents").json() == []


def test_webhook_alertmanager_bearer(client):
    payload = {"status": "firing", "alerts": [{
        "status": "firing", "labels": {"alertname": "WafRateLimitSature", "severity": "warning"},
        "annotations": {"summary": "Rate-limit du WAF fortement sollicité"},
        "startsAt": "2026-10-20T14:00:00+00:00", "fingerprint": "abc"}]}
    assert client.post("/webhook/alertmanager", json=payload, headers={"Authorization": "Bearer faux"}).status_code == 401
    response = client.post("/webhook/alertmanager", json=payload, headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 202
    incident = client.get("/incidents").json()[0]
    assert incident["category"] == "dos" and incident["trigger"] == "Rate-limit du WAF fortement sollicité"

    payload["alerts"][0]["status"] = "resolved"
    client.post("/webhook/alertmanager", json=payload, headers={"Authorization": f"Bearer {TOKEN}"})
    assert client.get("/incidents").json()[0]["steps"][-1]["action"] == "Alerte levée : WafRateLimitSature"


def test_rapport_et_integrite(client):
    incident_id = client.post("/webhook/ml", content=ML_BODY, headers=signed(ML_BODY)).json()["incident"]
    report = client.get(f"/incidents/{incident_id}/report")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/markdown")
    assert f"# Rapport d'incident {incident_id}" in report.text
    assert client.get("/incidents/inc-2099-01-01-001/report").status_code == 404
    assert client.get("/incidents/..%2Fetc/report").status_code == 404
    assert client.get("/journal/verify").json()["ok"] is True
