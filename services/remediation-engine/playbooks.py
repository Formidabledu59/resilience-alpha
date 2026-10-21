"""Exécution des playbooks Ansible de la liste blanche (engine.PLAYBOOKS).

Chaque playbook se termine par une tâche "Résultat" qui affiche "RESULT: <texte>" : ce texte
est repris tel quel dans le journal de l'incident. Toutes les actions Docker passent par
socket-proxy-rw (variables de infra/ansible/inventory/hosts.yml).
"""

import asyncio
import json
import os
import re
from typing import Awaitable, Callable

PLAYBOOK_DIR = os.environ.get("PLAYBOOK_DIR", "/ansible/playbooks")
BAN_MINUTES = float(os.environ.get("BAN_MINUTES", "5"))
# Seuil de refus (403/429) à partir duquel une IP est bannie : le canary (1 requête toutes les
# 5 s) n'y arrive jamais, un flood le dépasse en quelques secondes.
BAN_MIN_REQUESTS = int(os.environ.get("BAN_MIN_REQUESTS", "100"))
RESTARTABLE = {"payment-api", "auth-service", "frontend"}
TIMEOUT_SECONDS = 90
RESULT = re.compile(r"RESULT: ([^\"'\n]+)")

# Note dans le journal : (incident_id, action, résultat)
Notify = Callable[[str, str, str], Awaitable[None]]


class PlaybookError(RuntimeError):
    pass


def ips_to_ban(incident: dict, minimum: int = BAN_MIN_REQUESTS) -> list[str]:
    """IP les plus refusées par le WAF pendant l'incident, au-delà du seuil."""
    clients = ((incident.get("evidence") or {}).get("opening") or {}).get("waf", {}).get("clients") or []
    return [c["ip"] for c in clients if c["count"] >= minimum][:5]


def service_to_restart(incident: dict) -> str:
    """Service visé par l'alerte (label job de TargetDown), payment-api par défaut."""
    for alert in reversed(incident.get("alerts", [])):
        job = (alert.get("details") or {}).get("job")
        if job in RESTARTABLE:
            return job
    return "payment-api"


async def run_playbook(name: str, extra_vars: dict, timeout: float = TIMEOUT_SECONDS) -> str:
    """Lance ansible-playbook et renvoie le texte RESULT, ou lève PlaybookError."""
    process = await asyncio.create_subprocess_exec(
        "ansible-playbook", f"{PLAYBOOK_DIR}/{name}", "-e", json.dumps(extra_vars),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        process.kill()
        raise PlaybookError(f"délai de {int(timeout)} s dépassé") from None
    text = output.decode(errors="replace")
    print(json.dumps({"playbook": name, "returncode": process.returncode, "output": text[-2000:]}), flush=True)
    if process.returncode != 0:
        failed = re.findall(r"(?:fatal|FAILED).*?(?:msg|\"msg\")[\"']?:\s*[\"']?([^\n\"']+)", text)
        raise PlaybookError(failed[-1] if failed else f"code de sortie {process.returncode}")
    found = RESULT.findall(text)
    return found[-1].strip() if found else "terminé"


class AnsibleExecutor:
    """Exécuteur branché dans Engine : async (playbook, incident) -> résultat lisible."""

    def __init__(self, notify: Notify | None = None, runner=run_playbook, ban_minutes: float = BAN_MINUTES):
        self.notify = notify
        self.runner = runner
        self.ban_minutes = ban_minutes
        self.tasks: set[asyncio.Task] = set()

    async def __call__(self, playbook: str, incident: dict) -> str:
        if playbook == "ban_ip.yml":
            ips = ips_to_ban(incident)
            if not ips:
                return f"aucune IP au-delà de {BAN_MIN_REQUESTS} requêtes refusées : pas de ban"
            result = await self.runner(playbook, {"incident_id": incident["id"], "ban_ips": ips,
                                                  "ban_minutes": self.ban_minutes})
            task = asyncio.create_task(self._unban_later(incident["id"]))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return result
        if playbook == "restart_api.yml":
            return await self.runner(playbook, {"target_service": service_to_restart(incident)})
        return await self.runner(playbook, {"incident_id": incident["id"]})

    async def _unban_later(self, incident_id: str) -> None:
        """Ban temporaire : levé automatiquement après ban_minutes, et tracé dans le journal."""
        await asyncio.sleep(self.ban_minutes * 60)
        try:
            action, result = "Levée du ban (unban_ip.yml)", await self.runner("unban_ip.yml", {"incident_id": incident_id})
        except Exception as exc:  # noqa: BLE001 - un ban non levé doit être visible
            action, result = "Levée du ban en échec", f"{type(exc).__name__}: {exc}"
        if self.notify:
            await self.notify(incident_id, action, result)
