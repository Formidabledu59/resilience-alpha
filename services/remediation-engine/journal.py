"""Journal des incidents : fichier JSON Lines en ajout seul, chaîné par SHA-256.

Chaque modification d'un incident ajoute une ligne contenant l'état complet de l'incident,
l'empreinte de la ligne précédente (prev) et sa propre empreinte (hash). Modifier ou supprimer
une ligne après coup casse la chaîne : verify() le détecte. C'est la trace d'audit de la plateforme.

Chaque ligne est aussi écrite sur la sortie standard : Alloy l'envoie dans Loki.
"""

import hashlib
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64  # empreinte "précédente" de la toute première ligne


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(prev: str, body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


class Journal:
    def __init__(self, path: str | Path, echo: bool = True):
        self.path = Path(path)
        self.echo = echo
        self.lock = threading.Lock()
        self.seq = 0
        self.last_hash = GENESIS
        self.incidents: dict[str, dict] = {}  # dernier état connu de chaque incident
        self._replay()

    def _replay(self) -> None:
        """Relit le fichier au démarrage pour reconstruire l'état des incidents."""
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            self.seq = entry["seq"]
            self.last_hash = entry["hash"]
            self.incidents[entry["incident"]["id"]] = entry["incident"]

    def append(self, event: str, incident: dict) -> dict:
        """Ajoute une ligne (événement + état complet de l'incident) et renvoie l'entrée écrite."""
        with self.lock:
            body = {"seq": self.seq + 1, "at": now_iso(), "event": event, "incident": incident, "prev": self.last_hash}
            entry = {**body, "hash": _digest(self.last_hash, body)}
            line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            self.seq = entry["seq"]
            self.last_hash = entry["hash"]
            self.incidents[incident["id"]] = json.loads(json.dumps(incident))  # copie figée
        if self.echo:
            # Version courte pour Loki : la ligne complète reste dans le fichier
            print(json.dumps({"journal": event, "seq": entry["seq"], "incident": incident["id"],
                              "status": incident["status"], "category": incident.get("category"),
                              "hash": entry["hash"]}, ensure_ascii=False), file=sys.stdout, flush=True)
        return entry

    def latest(self, limit: int) -> list[dict]:
        """Incidents du plus récent au plus ancien."""
        items = sorted(self.incidents.values(), key=lambda i: i["opened_at"], reverse=True)
        return items[:limit]

    def get(self, incident_id: str) -> dict | None:
        return self.incidents.get(incident_id)

    def verify(self) -> dict:
        """Recalcule toute la chaîne. ok=False et la ligne fautive si une entrée a été altérée."""
        prev = GENESIS
        count = 0
        if self.path.exists():
            for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    body = {k: v for k, v in entry.items() if k != "hash"}
                    valid = entry["prev"] == prev and entry["hash"] == _digest(prev, body)
                except (ValueError, KeyError):
                    valid = False
                if not valid:
                    return {"ok": False, "entries": count, "broken_at_line": number}
                prev = entry["hash"]
                count += 1
        return {"ok": True, "entries": count, "last_hash": prev}
