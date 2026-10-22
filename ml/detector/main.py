"""ml-detector : score d'anomalie toutes les 5 s et alerte signée vers remediation-engine.

Contrat : docs/architecture/contracts.md (ml-detector, webhook /webhook/ml).
- GET /health, GET /metrics (ml_anomaly_score, ml_anomaly_threshold, ...)
- boucle : lit les features dans Prometheus, calcule le score, et au-delà du seuil (sur
  plusieurs relevés consécutifs) envoie une alerte HMAC au moteur de remédiation.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from anomaly import score_one
from model_store import load_or_fallback
from prometheus import read_features

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
WEBHOOK_URL = os.environ.get("REMEDIATION_WEBHOOK_URL", "http://remediation-engine:8000/webhook/ml")
MODEL_PATH = os.environ.get("MODEL_PATH", "/models/model.joblib")
THRESHOLD = float(os.environ.get("ML_ANOMALY_THRESHOLD", "0.7"))
INTERVAL = float(os.environ.get("ML_INTERVAL_SECONDS", "5"))
CONSECUTIVE = int(os.environ.get("ML_ALERT_CONSECUTIVE", "3"))  # relevés consécutifs avant d'alerter
COOLDOWN = float(os.environ.get("ML_ALERT_COOLDOWN_SECONDS", "60"))  # délai minimal entre deux alertes
# Réarmement : après une alerte, la suivante n'est possible qu'une fois le score redescendu sous
# le seuil pendant N relevés. Sans cela, la traîne d'une attaque déjà traitée (moyennes sur 1 min)
# relançait une remédiation inutile chaque minute (répétition du 22/10).
REARM = int(os.environ.get("ML_ALERT_REARM", "3"))

ANOMALY_SCORE = Gauge("ml_anomaly_score", "Score d'anomalie courant, de 0 (normal) à 1 (anormal)")
ANOMALY_THRESHOLD = Gauge("ml_anomaly_threshold", "Seuil au-delà duquel une alerte est envoyée")
MODEL_FALLBACK = Gauge("ml_model_fallback", "1 si le modèle de repli synthétique est utilisé")
PROM_UP = Gauge("ml_prometheus_reachable", "1 si Prometheus a répondu au dernier relevé")
FEATURE_VALUE = Gauge("ml_feature_value", "Dernière valeur lue par feature", ["feature"])
ALERTS_SENT = Counter("ml_alerts_sent_total", "Alertes envoyées au moteur de remédiation", ["result"])


def sign(secret: str, body: bytes, now: float | None = None) -> dict:
    """En-têtes HMAC attendus par remediation-engine : timestamp + sha256(timestamp.corps)."""
    timestamp = str(int(now if now is not None else time.time()))
    signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-Resilience-Timestamp": timestamp, "X-Resilience-Signature": signature, "Content-Type": "application/json"}


class Detector:
    def __init__(self, bundle: dict, client: httpx.AsyncClient, secret: str):
        self.model = bundle["model"]
        self.normalizer = bundle["normalizer"]
        self.client = client
        self.secret = secret
        self.breaches = 0        # relevés consécutifs au-dessus du seuil
        self.calm = 0            # relevés consécutifs sous le seuil
        self.armed = True        # faux après une alerte, jusqu'au retour au calme
        self.last_alert = 0.0

    async def tick(self, now: float | None = None) -> dict:
        """Un relevé : lit les features, calcule le score, alerte si nécessaire. Renvoie l'état."""
        now = now if now is not None else time.time()
        features, prometheus_ok = await read_features(self.client, PROMETHEUS_URL)
        PROM_UP.set(1 if prometheus_ok else 0)
        for name, value in features.items():
            FEATURE_VALUE.labels(feature=name).set(value)
        if not prometheus_ok:
            return {"prometheus_ok": False, "score": None, "alert": False}

        score = score_one(self.model, self.normalizer, features)
        ANOMALY_SCORE.set(score)
        self.breaches = self.breaches + 1 if score >= THRESHOLD else 0
        self.calm = self.calm + 1 if score < THRESHOLD else 0
        if self.calm >= REARM:
            self.armed = True

        alert = False
        if self.armed and self.breaches >= CONSECUTIVE and now - self.last_alert >= COOLDOWN:
            alert = await self.send_alert(score, features, now)
            if alert:
                self.last_alert = now
                self.armed = False
        return {"prometheus_ok": True, "score": score, "breaches": self.breaches, "armed": self.armed, "alert": alert}

    async def send_alert(self, score: float, features: dict, now: float) -> bool:
        body = json.dumps({
            "score": round(score, 4), "threshold": THRESHOLD,
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now)),
            "features": {k: round(v, 4) for k, v in features.items()},
        }).encode()
        try:
            response = await self.client.post(WEBHOOK_URL, content=body, headers=sign(self.secret, body, now))
            ok = response.status_code in (200, 202)
        except httpx.HTTPError:
            ok = False
        ALERTS_SENT.labels(result="ok" if ok else "echec").inc()
        return ok


async def loop(detector: Detector) -> None:
    while True:
        try:
            await detector.tick()
        except Exception as exc:  # noqa: BLE001 - la boucle ne doit jamais s'arrêter silencieusement
            print(json.dumps({"ml_detector_error": f"{type(exc).__name__}: {exc}"}), flush=True)
        await asyncio.sleep(INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    secret = os.environ.get("REMEDIATION_HMAC_SECRET")
    if not secret:
        raise RuntimeError("Variable d'environnement manquante : REMEDIATION_HMAC_SECRET")
    bundle = load_or_fallback(MODEL_PATH)
    ANOMALY_THRESHOLD.set(THRESHOLD)
    MODEL_FALLBACK.set(1 if bundle.get("fallback") else 0)
    print(json.dumps({"ml_detector": "démarré", "source": bundle["source"],
                      "fallback": bundle.get("fallback", False), "trained_at": bundle.get("trained_at")}), flush=True)
    async with httpx.AsyncClient(timeout=5) as client:
        app.state.detector = Detector(bundle, client, secret)
        task = asyncio.create_task(loop(app.state.detector))
        yield
        task.cancel()


app = FastAPI(title="ml-detector", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
