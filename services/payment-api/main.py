"""payment-api : création et consultation de transactions fictives.

Contrat : docs/architecture/contracts.md (section payment-api).
Postgres via psycopg 3, sans ORM. Une connexion par requête : simple et suffisant pour le POC.
"""

import os
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Literal

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field, model_validator
from vault_client import load_secret

JWT_ALGORITHM = "HS256"

# Comptes fictifs créés au démarrage s'ils n'existent pas : id -> solde initial
SEED_ACCOUNTS = {
    "ACC-001": Decimal("1000.00"),
    "ACC-002": Decimal("500.00"),
    "CANARY-A": Decimal("100.00"),
    "CANARY-B": Decimal("100.00"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id       TEXT PRIMARY KEY,
    balance  NUMERIC(12, 2) NOT NULL CHECK (balance >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'EUR'
);
CREATE TABLE IF NOT EXISTS transactions (
    id           BIGSERIAL PRIMARY KEY,
    from_account TEXT NOT NULL REFERENCES accounts (id),
    to_account   TEXT NOT NULL REFERENCES accounts (id),
    amount       NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency     CHAR(3) NOT NULL,
    status       TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

TRANSACTIONS = Counter("payment_transactions_total", "Transactions traitées", ["status"])
for _status in ("COMPLETED", "REJECTED"):
    TRANSACTIONS.labels(status=_status)  # séries visibles à 0 dès le démarrage


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


# Secrets : depuis Vault si disponible, sinon l'environnement (voir vault_client.py)
JWT_SECRET = load_secret("payment", "jwt_secret", "JWT_SECRET")
POSTGRES_PASSWORD = load_secret("database", "postgres_password", "POSTGRES_PASSWORD")


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        dbname=required_env("POSTGRES_DB"),
        user=required_env("POSTGRES_USER"),
        password=POSTGRES_PASSWORD,
        connect_timeout=3,
    )


def init_db(attempts: int = 10) -> None:
    """Crée les tables et les comptes fictifs. Réessaie le temps que Postgres soit prêt."""
    for attempt in range(1, attempts + 1):
        try:
            with connect() as conn:
                conn.execute(SCHEMA)
                for account_id, balance in SEED_ACCOUNTS.items():
                    conn.execute(
                        "INSERT INTO accounts (id, balance) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                        (account_id, balance),
                    )
            return
        except psycopg.OperationalError:
            if attempt == attempts:
                raise
            time.sleep(2)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="payment-api", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, include_in_schema=False)

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    """Vérifie le JWT émis par auth-service et renvoie le nom d'utilisateur."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token manquant")
    try:
        claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    return claims["sub"]


class TransactionIn(BaseModel):
    from_account: str = Field(min_length=1, max_length=32)
    to_account: str = Field(min_length=1, max_length=32)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["EUR"]

    @model_validator(mode="after")
    def distinct_accounts(self):
        if self.from_account == self.to_account:
            raise ValueError("Les comptes source et destination doivent être différents")
        return self


class TransactionCreated(BaseModel):
    id: int
    status: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transactions", status_code=201, response_model=TransactionCreated)
def create_transaction(tx: TransactionIn, _user: str = Depends(current_user)):
    with connect() as conn, conn.transaction():
        # Verrouille les deux comptes, toujours dans le même ordre (évite les interblocages)
        rows = conn.execute(
            "SELECT id, balance FROM accounts WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
            ([tx.from_account, tx.to_account],),
        ).fetchall()
        balances = dict(rows)
        for account_id in (tx.from_account, tx.to_account):
            if account_id not in balances:
                raise HTTPException(status_code=404, detail=f"Compte inconnu : {account_id}")

        if balances[tx.from_account] >= tx.amount:
            conn.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (tx.amount, tx.from_account))
            conn.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (tx.amount, tx.to_account))
            status = "COMPLETED"
        else:
            status = "REJECTED"  # rien n'est débité, mais la tentative est tracée

        tx_id = conn.execute(
            "INSERT INTO transactions (from_account, to_account, amount, currency, status) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (tx.from_account, tx.to_account, tx.amount, tx.currency, status),
        ).fetchone()[0]

    TRANSACTIONS.labels(status=status).inc()
    return TransactionCreated(id=tx_id, status=status)


@app.get("/transactions/{tx_id}")
def get_transaction(tx_id: int, _user: str = Depends(current_user)):
    with connect() as conn:
        row = conn.execute(
            "SELECT id, from_account, to_account, amount, currency, status, created_at "
            "FROM transactions WHERE id = %s",
            (tx_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Transaction inconnue")
    keys = ("id", "from_account", "to_account", "amount", "currency", "status", "created_at")
    result = dict(zip(keys, row))
    result["amount"] = str(result["amount"])
    result["created_at"] = result["created_at"].isoformat()
    return result


@app.get("/accounts/{account_id}")
def get_account(account_id: str, _user: str = Depends(current_user)):
    with connect() as conn:
        row = conn.execute("SELECT id, balance, currency FROM accounts WHERE id = %s", (account_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Compte inconnu")
    return {"id": row[0], "balance": str(row[1]), "currency": row[2]}
