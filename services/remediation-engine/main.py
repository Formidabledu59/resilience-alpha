"""remediation-engine : reçoit les alertes, traite les incidents et en tient le journal.

Contrat : docs/architecture/contracts.md (section remediation-engine).
- POST /webhook/ml            alertes du détecteur ML, signées HMAC-SHA256
- POST /webhook/alertmanager  alertes SOC et Prometheus, bearer token
- GET  /incidents            journal des incidents (lu par le dashboard)
- GET  /incidents/{id}/report rapport Markdown d'un incident
- GET  /journal/verify       contrôle d'intégrité de la chaîne SHA-256 du journal
"""

import hashlib
import hmac
import json
import os
import re
import shutil
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from engine import Engine
from evidence import Observer
from incidents import report_markdown
from journal import Journal, now_iso
from playbooks import AnsibleExecutor

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")
CANARY_URL = os.environ.get("CANARY_URL", "http://canary:8000")
JOURNAL_PATH = os.environ.get("JOURNAL_PATH", "/journal/incidents.jsonl")
VERIFY_TIMEOUT = float(os.environ.get("VERIFY_TIMEOUT_SECONDS", "180"))
SIGNATURE_MAX_AGE = 300  # une alerte ML signée il y a plus de 5 minutes est refusée (rejeu)
INCIDENT_ID = re.compile(r"^inc-\d{4}-\d{2}-\d{2}-\d{3}$")

REJECTED = Counter("remediation_webhook_rejected_total", "Alertes refusées (authentification)", ["source"])
ALERTS = Counter("remediation_alerts_total", "Alertes acceptées", ["source"])
JOURNAL_OK = Gauge("remediation_journal_integrity", "1 si la chaîne SHA-256 du journal est intacte")


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


def valid_hmac(secret: str, timestamp: str, body: bytes, signature: str, now: float) -> bool:
    """Signature attendue : sha256=HMAC(secret, "<timestamp>.<corps>"), horodatage de moins de 5 minutes."""
    try:
        if abs(now - int(timestamp)) > SIGNATURE_MAX_AGE:
            return False
    except ValueError:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.hmac_secret = required("REMEDIATION_HMAC_SECRET")
    app.state.bearer_token = required("REMEDIATION_BEARER_TOKEN")
    async with httpx.AsyncClient(timeout=10) as client:
        async def probe() -> dict:
            response = await client.post(f"{CANARY_URL}/probe")
            response.raise_for_status()
            return response.json()

        journal = Journal(JOURNAL_PATH)
        app.state.journal = journal
        app.state.engine = Engine(journal, Observer(client, PROMETHEUS_URL, LOKI_URL), probe, verify_timeout=VERIFY_TIMEOUT)
        # Playbooks exécutés seulement si Ansible est présent (image Docker) : en test, le
        # journal indique "exécution pas encore branchée".
        if shutil.which("ansible-playbook"):
            app.state.engine.executor = AnsibleExecutor(notify=app.state.engine.note,
                                                        refresh=app.state.engine.refresh_evidence)
        JOURNAL_OK.set(1 if journal.verify()["ok"] else 0)
        yield
        for task in list(app.state.engine.tasks):
            task.cancel()


app = FastAPI(title="remediation-engine", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook/ml", status_code=202)
async def webhook_ml(request: Request):
    body = await request.body()
    if not valid_hmac(app.state.hmac_secret, request.headers.get("X-Resilience-Timestamp", ""), body,
                      request.headers.get("X-Resilience-Signature", ""), time.time()):
        REJECTED.labels(source="ml-detector").inc()
        raise HTTPException(status_code=401, detail="Signature HMAC invalide ou expirée")
    try:
        payload = json.loads(body)
        score, threshold = float(payload["score"]), float(payload["threshold"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=422, detail="Corps attendu : score, threshold") from None
    ALERTS.labels(source="ml-detector").inc()
    alert = {
        "name": "AnomalieML",
        "source": "ml-detector",
        "auth": "HMAC valide",
        "at": payload.get("detected_at") or now_iso(),
        "severity": "critical",
        "summary": f"Score d'anomalie {score:.2f} au-delà du seuil {threshold:.2f}",
        "details": {"score": score, "threshold": threshold, "features": payload.get("features", {})},
    }
    return {"incident": await app.state.engine.receive(alert)}


@app.post("/webhook/alertmanager", status_code=202)
async def webhook_alertmanager(request: Request):
    expected = f"Bearer {app.state.bearer_token}"
    if not hmac.compare_digest(request.headers.get("Authorization", ""), expected):
        REJECTED.labels(source="alertmanager").inc()
        raise HTTPException(status_code=401, detail="Bearer token invalide")
    try:
        alerts = (await request.json())["alerts"]
    except (ValueError, KeyError):
        raise HTTPException(status_code=422, detail="Format Alertmanager attendu") from None

    incidents = []
    for item in alerts:
        labels, annotations = item.get("labels", {}), item.get("annotations", {})
        alert = {
            "name": labels.get("alertname", "inconnue"),
            "source": "alertmanager",
            "auth": "bearer valide",
            "at": item.get("startsAt") or now_iso(),
            "severity": labels.get("severity", "warning"),
            "summary": annotations.get("summary"),
            "description": annotations.get("description"),
            "fingerprint": item.get("fingerprint"),
            "details": labels,
        }
        if item.get("status") == "resolved":
            incident = await app.state.engine.resolved(alert)
        else:
            ALERTS.labels(source="alertmanager").inc()
            incident = await app.state.engine.receive(alert)
        if incident:
            incidents.append(incident)
    return {"incidents": sorted(set(incidents))}


@app.get("/incidents")
def list_incidents(limit: int = Query(10, ge=1, le=100)):
    return app.state.journal.latest(limit)


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    incident = app.state.journal.get(incident_id) if INCIDENT_ID.match(incident_id) else None
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident inconnu")
    return incident


@app.get("/incidents/{incident_id}/report", response_class=PlainTextResponse)
def incident_report(incident_id: str):
    incident = get_incident(incident_id)
    return PlainTextResponse(
        report_markdown(incident, app.state.journal.last_hash),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{incident_id}.md"'},
    )


@app.get("/journal/verify")
def journal_verify():
    result = app.state.journal.verify()
    JOURNAL_OK.set(1 if result["ok"] else 0)
    return result
