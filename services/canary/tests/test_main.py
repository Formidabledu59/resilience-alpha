import asyncio
from collections import deque

import httpx
from fastapi.testclient import TestClient

from main import Canary, app, success_ratio


def fake_platform(status: str):
    """Simule auth-service et payment-api, et note le sens de chaque transaction."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/token":
            return httpx.Response(200, json={"access_token": "t", "token_type": "bearer", "expires_in": 900})
        calls.append(request.read())
        return httpx.Response(201, json={"id": len(calls), "status": status})

    return httpx.MockTransport(handler), calls


async def run(status: str, times: int):
    transport, calls = fake_platform(status)
    async with httpx.AsyncClient(transport=transport) as client:
        canary = Canary(client, "secret")
        results = [await canary.run_once() for _ in range(times)]
    return canary, results, calls


def test_alterne_le_sens_apres_chaque_succes():
    canary, results, calls = asyncio.run(run("COMPLETED", 2))
    assert all(r["ok"] for r in results)
    assert b'"from_account":"CANARY-A"' in calls[0]
    assert b'"from_account":"CANARY-B"' in calls[1]
    assert canary.forward is True


def test_rejected_compte_comme_echec_sans_changer_de_sens():
    canary, results, _ = asyncio.run(run("REJECTED", 1))
    assert results[0]["ok"] is False
    assert results[0]["status"] == "REJECTED"
    assert canary.forward is True


def test_success_ratio_sur_60_secondes():
    results = deque([(0, False), (50, True), (100, True), (105, False)])
    # à t=110, seul ce qui date de moins de 60 s compte : (50, True), (100, True), (105, False)
    assert success_ratio(results, 110) == 2 / 3
    assert success_ratio(deque(), 110) == 0.0


def test_health_et_metrics():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/metrics").text
    for name in ("canary_up", "canary_success_ratio", "canary_latency_seconds", "canary_transactions_total"):
        assert name in body
