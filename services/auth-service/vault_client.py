"""Chargement des secrets : depuis Vault si un token de service est disponible, sinon l'env.

Aucune dépendance (urllib). Repli sur l'environnement pour que le profile `app` seul
(sans Vault) continue de fonctionner. En production, on retirerait le repli.
"""

import json
import os
import urllib.request

VAULT_TIMEOUT = 3


def read_vault_token() -> str | None:
    """Token de service : fichier (VAULT_TOKEN_FILE, écrit par vault-init) ou variable."""
    path = os.environ.get("VAULT_TOKEN_FILE", "/vault-token/service-token")
    try:
        with open(path, encoding="utf-8") as handle:
            token = handle.read().strip()
            if token:
                return token
    except OSError:
        pass
    return os.environ.get("VAULT_TOKEN") or None


def fetch_from_vault(addr: str, token: str, name: str, field: str) -> str:
    """Lit secret/data/<name> (KV v2) et renvoie le champ demandé."""
    request = urllib.request.Request(
        f"{addr.rstrip('/')}/v1/secret/data/{name}",
        headers={"X-Vault-Token": token},
    )
    with urllib.request.urlopen(request, timeout=VAULT_TIMEOUT) as response:
        payload = json.load(response)
    return payload["data"]["data"][field]


def load_secret(name: str, field: str, env_var: str) -> str:
    """secret/<name>:<field> depuis Vault si possible, sinon la variable d'env <env_var>."""
    addr = os.environ.get("VAULT_ADDR")
    token = read_vault_token()
    if addr and token:
        try:
            value = fetch_from_vault(addr, token, name, field)
            print(f"[secrets] {env_var} chargé depuis Vault (secret/{name}:{field})")
            return value
        except Exception as exc:  # repli sur l'env, sans bloquer le démarrage
            print(f"[secrets] Vault indisponible pour {env_var} ({type(exc).__name__}), repli sur l'environnement")
    value = os.environ.get(env_var)
    if not value:
        raise RuntimeError(f"Secret manquant : ni Vault ni la variable {env_var}")
    print(f"[secrets] {env_var} chargé depuis l'environnement")
    return value
