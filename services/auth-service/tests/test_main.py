import os

import jwt
from fastapi.testclient import TestClient

# Valeurs de test, définies avant l'import de main (lues au démarrage du module)
os.environ.setdefault("JWT_SECRET", "cle-de-test-hs256-de-plus-de-32-octets")
os.environ.setdefault("AUTH_DEMO_PASSWORD", "demo-pass")
os.environ.setdefault("AUTH_CANARY_PASSWORD", "canary-pass")

from main import JWT_ALGORITHM, app  # noqa: E402

client = TestClient(app)


def test_token_ok_et_decodable():
    response = client.post("/auth/token", json={"username": "demo", "password": "demo-pass"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    claims = jwt.decode(body["access_token"], os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == "demo"
    assert claims["exp"] - claims["iat"] == 900


def test_mauvais_mot_de_passe_refuse():
    response = client.post("/auth/token", json={"username": "demo", "password": "faux"})
    assert response.status_code == 401


def test_utilisateur_inconnu_refuse():
    response = client.post("/auth/token", json={"username": "inconnu", "password": "demo-pass"})
    assert response.status_code == 401


def test_health_et_metrics():
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/metrics").status_code == 200
