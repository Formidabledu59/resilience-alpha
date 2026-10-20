"""Tests sans base de données : TestClient sans "with" ne déclenche pas le lifespan (init_db)."""

import os
import time

import jwt
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "cle-de-test-hs256-de-plus-de-32-octets")
os.environ.setdefault("POSTGRES_PASSWORD", "mot-de-passe-bdd-de-test")

from main import JWT_ALGORITHM, app  # noqa: E402

client = TestClient(app)


def auth_header() -> dict:
    now = int(time.time())
    token = jwt.encode({"sub": "demo", "iat": now, "exp": now + 60}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


VALID = {"from_account": "ACC-001", "to_account": "ACC-002", "amount": 10, "currency": "EUR"}


def test_transaction_sans_token_refusee():
    assert client.post("/transactions", json=VALID).status_code == 401
    assert client.post("/transactions", json=VALID, headers={"Authorization": "Bearer faux"}).status_code == 401


def test_validation_du_payload():
    headers = auth_header()
    assert client.post("/transactions", json={**VALID, "currency": "USD"}, headers=headers).status_code == 422
    assert client.post("/transactions", json={**VALID, "amount": 0}, headers=headers).status_code == 422
    assert client.post("/transactions", json={**VALID, "to_account": "ACC-001"}, headers=headers).status_code == 422


def test_health_et_metrics():
    assert client.get("/health").json() == {"status": "ok"}
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'payment_transactions_total{status="COMPLETED"}' in metrics.text
