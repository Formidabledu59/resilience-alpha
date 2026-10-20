"""Habilitations : mots de passe des utilisateurs du back-office (hachés, jamais en clair).

Fichier JSON local sur le PC Hôte. Le visage enrôlé est géré par recognizer.py ;
ici on ne garde que le mot de passe haché (PBKDF2-SHA256), comme auth-service.
"""

import hashlib
import hmac
import json
import secrets
from pathlib import Path

ITERATIONS = 200_000


class UserStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._users: dict[str, dict] = {}
        if self.path.exists():
            self._users = json.loads(self.path.read_text())

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._users))

    def set_password(self, username: str, password: str) -> None:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
        self._users[username] = {"salt": salt, "hash": digest}
        self._save()

    def verify(self, username: str, password: str) -> bool:
        user = self._users.get(username)
        if not user:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(user["salt"]), ITERATIONS).hex()
        return hmac.compare_digest(digest, user["hash"])

    def remove(self, username: str) -> None:
        self._users.pop(username, None)
        self._save()

    def exists(self, username: str) -> bool:
        return username in self._users

    def usernames(self) -> list[str]:
        return sorted(self._users)
