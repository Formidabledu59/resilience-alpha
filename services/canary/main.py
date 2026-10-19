"""canary : sonde métier qui exécute une transaction fictive à intervalle régulier.

Contrat : docs/architecture/contracts.md (section canary).
Une transaction n'est un succès que si payment-api répond 201 avec le statut COMPLETED.
"""

import asyncio
import os
import time
from collections import deque
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

AUTH_URL = os.environ.get("AUTH_URL", "http://auth-service:8000")
PAYMENT_URL = os.environ.get("PAYMENT_URL", "http://payment-api:8000")
INTERVAL_SECONDS = float(os.environ.get("CANARY_INTERVAL_SECONDS", "5"))
USERNAME = "canary"
WINDOW_SECONDS = 60
TOKEN_REFRESH_MARGIN = 30  # renouvelle le token 30 s avant son expiration

CANARY_UP = Gauge("canary_up", "1 si la dernière transaction a réussi, 0 sinon")
SUCCESS_RATIO = Gauge("canary_success_ratio", "Taux de succès sur les 60 dernières secondes")
LATENCY = Histogram("canary_latency_seconds", "Durée d'une transaction canari")
TRANSACTIONS = Counter("canary_transactions_total", "Transactions canari", ["result"])
for _result in ("success", "failure"):
    TRANSACTIONS.labels(result=_result)


def success_ratio(results: deque, now: float) -> float:
    """Purge les résultats plus vieux que la fenêtre et renvoie le taux de succès (0 si aucun)."""
    while results and results[0][0] < now - WINDOW_SECONDS:
        results.popleft()
    if not results:
        return 0.0
    return sum(1 for _, ok in results if ok) / len(results)


class Canary:
    def __init__(self, client: httpx.AsyncClient, password: str):
        self.client = client
        self.password = password
        self.token: str | None = None
        self.token_expiry = 0.0
        self.forward = True  # True : CANARY-A -> CANARY-B
        self.results: deque = deque()
        self.lock = asyncio.Lock()

    def accounts(self) -> tuple[str, str]:
        return ("CANARY-A", "CANARY-B") if self.forward else ("CANARY-B", "CANARY-A")

    async def get_token(self, force: bool = False) -> str:
        if force or self.token is None or time.time() >= self.token_expiry - TOKEN_REFRESH_MARGIN:
            response = await self.client.post(
                f"{AUTH_URL}/auth/token", json={"username": USERNAME, "password": self.password}
            )
            response.raise_for_status()
            body = response.json()
            self.token = body["access_token"]
            self.token_expiry = time.time() + body["expires_in"]
        return self.token

    async def pay(self, force_token: bool = False) -> httpx.Response:
        source, target = self.accounts()
        token = await self.get_token(force=force_token)
        return await self.client.post(
            f"{PAYMENT_URL}/transactions",
            json={"from_account": source, "to_account": target, "amount": "1.00", "currency": "EUR"},
            headers={"Authorization": f"Bearer {token}"},
        )

    async def run_once(self) -> dict:
        """Exécute une transaction, met à jour les métriques et renvoie le résultat."""
        async with self.lock:
            start = time.perf_counter()
            result = {"ok": False, "status": "ERROR", "transaction_id": None, "latency_seconds": None, "detail": None}
            try:
                response = await self.pay()
                if response.status_code == 401:  # token révoqué ou secret changé : un seul nouvel essai
                    response = await self.pay(force_token=True)
                if response.status_code == 201:
                    body = response.json()
                    result.update(status=body["status"], transaction_id=body["id"], ok=body["status"] == "COMPLETED")
                    if not result["ok"]:
                        result["detail"] = "Transaction refusée par payment-api"
                else:
                    result["detail"] = f"HTTP {response.status_code}"
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                result["detail"] = f"{type(exc).__name__}: {exc}"

            latency = time.perf_counter() - start
            result["latency_seconds"] = round(latency, 4)
            self.record(result["ok"], latency)
            if result["ok"]:
                self.forward = not self.forward  # n'alterne qu'après un débit réel : les soldes restent stables
            return result

    def record(self, ok: bool, latency: float) -> None:
        now = time.time()
        self.results.append((now, ok))
        CANARY_UP.set(1 if ok else 0)
        SUCCESS_RATIO.set(success_ratio(self.results, now))
        LATENCY.observe(latency)
        TRANSACTIONS.labels(result="success" if ok else "failure").inc()


async def loop(canary: Canary) -> None:
    while True:
        await canary.run_once()
        await asyncio.sleep(INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    password = os.environ.get("AUTH_CANARY_PASSWORD")
    if not password:
        raise RuntimeError("Variable d'environnement manquante : AUTH_CANARY_PASSWORD")
    async with httpx.AsyncClient(timeout=5) as client:
        app.state.canary = Canary(client, password)
        task = asyncio.create_task(loop(app.state.canary))
        yield
        task.cancel()


app = FastAPI(title="canary", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/probe")
async def probe():
    """Transaction de contrôle immédiate (utilisée par remediation-engine)."""
    return await app.state.canary.run_once()
