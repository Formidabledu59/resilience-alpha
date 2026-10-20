"""auth-service : émission de JWT pour la plateforme de paiement fictive.

Contrat : docs/architecture/contracts.md (section auth-service).
Les utilisateurs sont fictifs, gardés en mémoire, mots de passe hashés au démarrage.
"""

import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from vault_client import load_secret

JWT_ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 15 * 60
PBKDF2_ITERATIONS = 200_000


def required_env(name: str) -> str:
    """Lit une variable obligatoire : le service refuse de démarrer sans elle."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)


def build_users() -> dict[str, tuple[bytes, bytes]]:
    """Crée les utilisateurs fictifs : nom -> (sel, hash). Aucun mot de passe en clair n'est conservé."""
    users = {}
    for username, env_name in (("demo", "AUTH_DEMO_PASSWORD"), ("canary", "AUTH_CANARY_PASSWORD")):
        salt = secrets.token_bytes(16)
        users[username] = (salt, hash_password(required_env(env_name), salt))
    return users


# Secret : depuis Vault si disponible, sinon l'environnement (voir vault_client.py)
JWT_SECRET = load_secret("payment", "jwt_secret", "JWT_SECRET")
USERS = build_users()

app = FastAPI(title="auth-service")
Instrumentator().instrument(app).expose(app, include_in_schema=False)


class Credentials(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_TTL_SECONDS


def verify_password(username: str, password: str) -> bool:
    user = USERS.get(username)
    if user is None:
        return False
    salt, expected = user
    # Comparaison en temps constant
    return hmac.compare_digest(hash_password(password, salt), expected)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/token", response_model=Token)
def issue_token(credentials: Credentials):
    if not verify_password(credentials.username, credentials.password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    now = int(time.time())
    claims = {"sub": credentials.username, "iat": now, "exp": now + TOKEN_TTL_SECONDS}
    return Token(access_token=jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM))
