import os
import tempfile

os.environ["BIO_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

import app as gateway  # noqa: E402
from conftest import striped_face  # noqa: E402

client = TestClient(gateway.app)

ALICE_FACES = [striped_face("vertical", s) for s in range(5)]
BOB_FACE = striped_face("horizontal", 500)


def enroll_alice():
    gateway.app.state.capture_many = lambda n: ALICE_FACES
    return client.post("/enroll", json={"username": "alice", "password": "s3cret-alice"})


def test_health_and_led():
    assert client.get("/health").json() == {"status": "ok"}
    led = client.get("/led").json()
    assert led["state"] == "off" and "seq" in led


def test_full_flow_granted():
    enroll_alice()
    # Étape 1 : la caméra "voit" alice -> reconnu, LED vert clignotant
    gateway.app.state.capture_one = lambda: striped_face("vertical", 999)
    assert client.post("/identify", json={"username": "alice"}).json()["status"] == "recognized"
    assert client.get("/led").json()["state"] == "green_blink"
    # Étape 2 : bon mot de passe -> accordé, LED vert fixe
    assert client.post("/password", json={"username": "alice", "password": "s3cret-alice"}).json()["status"] == "granted"
    assert client.get("/led").json()["state"] == "green_solid"


def test_wrong_password_denied():
    enroll_alice()
    gateway.app.state.capture_one = lambda: striped_face("vertical", 1)
    client.post("/identify", json={"username": "alice"})
    assert client.post("/password", json={"username": "alice", "password": "faux"}).json()["status"] == "denied"
    assert client.get("/led").json()["state"] == "red_blink"


def test_not_recognized_then_lock():
    enroll_alice()
    # La caméra "voit" un autre visage -> non reconnu
    gateway.app.state.capture_one = lambda: BOB_FACE
    assert client.post("/identify", json={"username": "alice"}).json()["status"] == "not_recognized"
    assert client.get("/led").json()["state"] == "red_solid"
    # Deuxième échec -> blocage
    assert client.post("/identify", json={"username": "alice"}).json()["status"] == "locked"


def test_no_face_detected():
    gateway.app.state.capture_many = lambda n: []
    assert client.post("/enroll", json={"username": "ghost", "password": "x"}).json()["status"] == "no_face"


def test_revoke():
    enroll_alice()
    assert "alice" in client.get("/users").json()["users"]
    assert client.delete("/users/alice").json()["status"] == "revoked"
    assert "alice" not in client.get("/users").json()["users"]
