"""Passerelle biométrique du back-office (service NATIF du PC Hôte, hors Docker).

Possède la caméra USB et la reconnaissance faciale (IA légère), gère les habilitations,
applique la logique d'essais / blocage, et expose l'état de la LED que l'ESP8266 interroge.

Flux : identifiant -> /identify (caméra + visage) -> /password -> accès back-office.
Démarrage : voir biometrics/gateway/README.md (tourne en natif sur le PC Hôte).
"""

import os

from fastapi import FastAPI
from pydantic import BaseModel

from auth_flow import AuthFlow
from recognizer import Recognizer
from store import UserStore

DATA_DIR = os.environ.get("BIO_DATA_DIR", "./data")
CAMERA_INDEX = int(os.environ.get("BIO_CAMERA_INDEX", "0"))
ENROLL_SAMPLES = int(os.environ.get("BIO_ENROLL_SAMPLES", "5"))
THRESHOLD = float(os.environ.get("BIO_THRESHOLD", "70"))

app = FastAPI(title="biometric-gateway")
app.state.flow = AuthFlow()
app.state.recognizer = Recognizer(os.path.join(DATA_DIR, "model"), threshold=THRESHOLD)
app.state.store = UserStore(os.path.join(DATA_DIR, "users.json"))


def _capture_one():
    """Capture un visage depuis la caméra. Importé paresseusement : pas d'OpenCV en test."""
    from faces import capture_face
    return capture_face(CAMERA_INDEX)


def _capture_many(count: int):
    from faces import capture_face
    faces = []
    for _ in range(count):
        face = capture_face(CAMERA_INDEX)
        if face is not None:
            faces.append(face)
    return faces


# Injectables (remplacés en test pour ne pas toucher la caméra)
app.state.capture_one = _capture_one
app.state.capture_many = _capture_many


class Identifier(BaseModel):
    username: str


class Password(BaseModel):
    username: str
    password: str


class Enrollment(BaseModel):
    username: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/led")
def led():
    """Interrogé par l'ESP8266 : état courant de la LED et numéro de séquence."""
    return app.state.flow.led()


@app.post("/identify")
def identify(body: Identifier):
    """Étape 1 : allume la caméra, reconnaît le visage pour cet identifiant."""
    start = app.state.flow.start_identification(body.username)
    if start["status"] == "locked":
        return start
    face = app.state.capture_one()
    recognized = face is not None and app.state.recognizer.recognize(body.username, face)
    return app.state.flow.on_recognition(body.username, recognized)


@app.post("/password")
def password(body: Password):
    """Étape 2 : vérifie le mot de passe (valable seulement après un visage reconnu)."""
    ok = app.state.store.verify(body.username, body.password)
    return app.state.flow.submit_password(body.username, ok)


@app.get("/users")
def users():
    """Habilitations : utilisateurs enrôlés (visage + mot de passe)."""
    return {"users": sorted(set(app.state.store.usernames()) & set(app.state.recognizer.enrolled_users()))}


@app.post("/enroll")
def enroll(body: Enrollment):
    """Habilitation : capture des visages depuis la caméra et fixe le mot de passe."""
    faces = app.state.capture_many(ENROLL_SAMPLES)
    if not faces:
        return {"status": "no_face", "detail": "Aucun visage détecté par la caméra."}
    count = app.state.recognizer.enroll(body.username, faces)
    app.state.store.set_password(body.username, body.password)
    return {"status": "enrolled", "username": body.username, "samples": count}


@app.delete("/users/{username}")
def revoke(username: str):
    """Retire une habilitation (visage + mot de passe)."""
    app.state.recognizer.revoke(username)
    app.state.store.remove(username)
    return {"status": "revoked", "username": username}
