"""Cycle de vie d'un incident : ouverture, preuves, remédiation, vérification, clôture.

Chaque étape est ajoutée à l'incident puis écrite dans le journal (journal.py) :
la trace complète est consultable à tout moment, même si le moteur redémarre.

Statuts (contrat : docs/architecture/contracts.md) : OPEN, REMEDIATING, VERIFYING, CLOSED, FAILED.
Un incident n'est CLOSED qu'après une transaction de contrôle réussie (POST /probe du canary).
"""

import asyncio
import copy
import os
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from prometheus_client import Counter, Gauge, Histogram

from incidents import ACTIVE_STATUSES, CATEGORIES, assess, classify, fr_percent
from journal import Journal, now_iso

LOOKBACK_SECONDS = 300      # les preuves couvrent aussi les 5 minutes qui précèdent l'alerte
# Retour au nominal : canary_up = 1 sur N relevés consécutifs (~N x 5 s), tous postérieurs à
# l'action. On ne se fie pas au taux de succès sur 60 s : il met une minute à remonter après une
# panne et, à l'inverse, peut afficher 100 % juste après un redémarrage alors que le service
# n'est pas encore prêt (répétition du 22/10 : transaction de contrôle en HTTP 502).
STABLE_CHECKS = int(os.environ.get("VERIFY_STABLE_CHECKS", "3"))
# Transaction de contrôle : un échec passager juste après un redémarrage est réessayé. La
# reprise n'est prouvée que par une transaction COMPLETED.
PROBE_ATTEMPTS = int(os.environ.get("VERIFY_PROBE_ATTEMPTS", "3"))

# Liste blanche : seuls ces playbooks peuvent être exécutés, selon la catégorie d'incident.
# Les attaques applicatives et la reconnaissance sont déjà bloquées par le WAF : pas d'action.
PLAYBOOKS = {
    # unban_ip.yml (levée du ban à l'expiration) est appelé par playbooks.AnsibleExecutor
    "dos": ["ban_ip.yml"],
    "force_brute": ["ban_ip.yml"],
    "anomalie": ["ban_ip.yml", "restart_api.yml"],
    "indisponibilite": ["restart_api.yml"],
}

# Exécuteur de playbook : async (playbook, incident) -> texte du résultat. Lève une exception en cas d'échec.
Executor = Callable[[str, dict], Awaitable[str]]

INCIDENTS = Counter("remediation_incidents_total", "Incidents ouverts", ["category"])
OUTCOMES = Counter("remediation_incidents_closed_total", "Incidents terminés", ["category", "status"])
OPEN_INCIDENTS = Gauge("remediation_incidents_open", "Incidents en cours de traitement")
DURATION = Histogram("remediation_duration_seconds", "Durée entre ouverture et clôture d'un incident",
                     buckets=(15, 30, 60, 90, 120, 180, 300, 600))


class Engine:
    def __init__(self, journal: Journal, observer, probe: Callable[[], Awaitable[dict]],
                 executor: Executor | None = None, verify_timeout: float = 180, poll_interval: float = 5):
        self.journal = journal
        self.observer = observer
        self.probe = probe
        self.executor = executor
        self.verify_timeout = verify_timeout
        self.poll_interval = poll_interval
        self.tasks: set[asyncio.Task] = set()
        self.lock = asyncio.Lock()
        self._close_interrupted()

    def _close_interrupted(self) -> None:
        """Incidents restés actifs lors d'un arrêt du moteur : on le trace au lieu de les oublier."""
        for incident in list(self.journal.incidents.values()):
            if incident["status"] in ACTIVE_STATUSES:
                incident = copy.deepcopy(incident)
                self._step(incident, "Moteur redémarré pendant l'incident", "suivi interrompu, à vérifier par un opérateur", "info")
                self._finish(incident, "FAILED")

    # --- Journalisation ----------------------------------------------------------
    @staticmethod
    def _step(incident: dict, action: str, result: str | None = None, kind: str = "info") -> None:
        incident["steps"].append({"at": now_iso(), "action": action, "result": result, "kind": kind})

    def _save(self, incident: dict, event: str) -> None:
        assess(incident)
        self.journal.append(event, incident)

    def _finish(self, incident: dict, status: str) -> None:
        incident["status"] = status
        incident["closed_at"] = now_iso()
        self._save(incident, "incident.closed" if status == "CLOSED" else "incident.failed")
        OUTCOMES.labels(category=incident["category"], status=status).inc()
        opened = datetime.fromisoformat(incident["opened_at"])
        DURATION.observe((datetime.fromisoformat(incident["closed_at"]) - opened).total_seconds())
        self._update_gauge()

    def _update_gauge(self) -> None:
        OPEN_INCIDENTS.set(sum(1 for i in self.journal.incidents.values() if i["status"] in ACTIVE_STATUSES))

    def _new_id(self) -> str:
        prefix = f"inc-{datetime.now(timezone.utc):%Y-%m-%d}-"
        count = sum(1 for key in self.journal.incidents if key.startswith(prefix))
        return f"{prefix}{count + 1:03d}"

    # --- Réception des alertes ---------------------------------------------------
    async def receive(self, alert: dict) -> str:
        """Ouvre un incident, ou rattache l'alerte à un incident actif de même catégorie."""
        category = classify(alert["name"])
        async with self.lock:
            for current in self.journal.incidents.values():
                if current["status"] in ACTIVE_STATUSES and current["category"] == category:
                    incident = copy.deepcopy(current)
                    incident["alerts"].append(alert)
                    self._step(incident, f"Alerte complémentaire : {alert['name']}", alert.get("summary"), "detection")
                    self._save(incident, "alert.merged")
                    return incident["id"]

            incident = {
                "id": self._new_id(),
                "status": "OPEN",
                "trigger": alert.get("summary") or alert["name"],
                "source": alert["source"],
                "category": category,
                "category_label": CATEGORIES[category],
                "severity": alert.get("severity", "warning"),
                "opened_at": now_iso(),
                "closed_at": None,
                "alerts": [alert],
                "evidence": {},
                "steps": [],
            }
            self._step(incident, f"Alerte reçue : {alert['name']} ({alert['auth']})", alert.get("summary"), "detection")
            self._save(incident, "incident.opened")
            INCIDENTS.labels(category=category).inc()
            self._update_gauge()

        task = asyncio.create_task(self.run(incident["id"]))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return incident["id"]

    async def resolved(self, alert: dict) -> str | None:
        """Alertmanager signale qu'une alerte n'est plus active : simple trace sur l'incident concerné."""
        async with self.lock:
            for current in self.journal.latest(50):
                if any(a.get("fingerprint") and a.get("fingerprint") == alert.get("fingerprint") for a in current["alerts"]):
                    incident = copy.deepcopy(current)
                    self._step(incident, f"Alerte levée : {alert['name']}", "plus de déclenchement côté Alertmanager", "info")
                    self._save(incident, "alert.resolved")
                    return incident["id"]
        return None

    async def note(self, incident_id: str, action: str, result: str) -> None:
        """Action différée (ex. levée d'un ban), tracée même si l'incident est déjà clôturé."""
        async with self.lock:
            incident = self._current(incident_id)
            self._step(incident, action, result, "action")
            self._save(incident, "remediation.action")

    # --- Cycle de vie --------------------------------------------------------------
    def _current(self, incident_id: str) -> dict:
        return copy.deepcopy(self.journal.get(incident_id))

    async def _evidence(self, incident_id: str, moment: str) -> None:
        incident = self._current(incident_id)
        first = min(datetime.fromisoformat(a["at"]) for a in incident["alerts"])
        window = (datetime.now(timezone.utc) - first + timedelta(seconds=LOOKBACK_SECONDS)).total_seconds()
        evidence = await self.observer.collect(window)
        incident = self._current(incident_id)  # relu : une alerte a pu être rattachée entre-temps
        incident["evidence"][moment] = {"collected_at": now_iso(), **evidence}
        waf = evidence["waf"]
        detail = (f"fenêtre {evidence['window_seconds']} s, 403 : {waf['blocked_403'] if waf['blocked_403'] is not None else '-'}, "
                  f"429 : {waf['rate_limited_429'] if waf['rate_limited_429'] is not None else '-'}, "
                  f"canari au plus bas : {fr_percent(evidence['metrics']['canary_success_min'])}")
        label = "Collecte des preuves (Prometheus, Loki)" if moment == "opening" else "Bilan après reprise (Prometheus, Loki)"
        self._step(incident, label, detail, "analysis")
        self._save(incident, f"evidence.{moment}")

    async def _remediate(self, incident_id: str) -> None:
        incident = self._current(incident_id)
        incident["status"] = "REMEDIATING"
        playbooks = PLAYBOOKS.get(incident["category"], [])
        if not playbooks:
            self._step(incident, "Aucune action corrective nécessaire", "attaque bloquée en amont par le WAF", "info")
        elif self.executor is None:
            self._step(incident, f"Playbooks prévus : {', '.join(playbooks)}", "exécution pas encore branchée", "info")
        self._save(incident, "incident.remediating")
        if self.executor is None:
            return

        for playbook in playbooks:
            try:
                action, result = f"Playbook {playbook}", await self.executor(playbook, self._current(incident_id))
            except Exception as exc:  # noqa: BLE001 - toute erreur d'exécution est tracée, jamais masquée
                action, result = f"Playbook {playbook} en échec", f"{type(exc).__name__}: {exc}"
            incident = self._current(incident_id)  # relu après l'attente
            self._step(incident, action, result, "action")
            self._save(incident, "remediation.action")

    async def _verify(self, incident_id: str) -> bool:
        incident = self._current(incident_id)
        incident["status"] = "VERIFYING"
        self._step(incident, "Attente du retour nominal du canari",
                   f"canary_up = 1 sur {STABLE_CHECKS} relevés consécutifs", "info")
        self._save(incident, "incident.verifying")

        deadline = asyncio.get_running_loop().time() + self.verify_timeout
        up = ratio = None
        stable = 0
        while True:
            up, ratio = await self.observer.canary_state()
            stable = stable + 1 if up == 1 else 0
            if stable >= STABLE_CHECKS:
                break
            if asyncio.get_running_loop().time() >= deadline:
                incident = self._current(incident_id)
                self._step(incident, "Canari toujours dégradé", f"canary_up = {up}, taux de succès {fr_percent(ratio)} après {int(self.verify_timeout)} s", "verification")
                self._save(incident, "verification.timeout")
                return False
            await asyncio.sleep(self.poll_interval)

        incident = self._current(incident_id)
        self._step(incident, "Vérification canary_up", f"1 sur {stable} relevé(s), taux de succès {fr_percent(ratio)}", "verification")
        self._save(incident, "verification.canary")
        for attempt in range(1, PROBE_ATTEMPTS + 1):
            try:
                probe = await self.probe()
            except Exception as exc:  # noqa: BLE001
                probe = {"ok": False, "status": "ERROR", "detail": f"{type(exc).__name__}: {exc}"}
            if probe.get("ok") or attempt == PROBE_ATTEMPTS:
                break
            incident = self._current(incident_id)
            self._step(incident, f"Transaction de contrôle (essai {attempt}/{PROBE_ATTEMPTS})",
                       f"{probe.get('status', 'ERROR')} : {probe.get('detail') or 'échec'}, nouvel essai", "verification")
            self._save(incident, "verification.probe_retry")
            await asyncio.sleep(self.poll_interval)
        incident = self._current(incident_id)
        if probe.get("ok"):
            result = f"{probe['status']}, transaction n°{probe.get('transaction_id')} en {probe.get('latency_seconds')} s"
        else:
            result = f"{probe.get('status', 'ERROR')} : {probe.get('detail') or 'échec'}"
        self._step(incident, "Transaction de contrôle (POST /probe)", result, "verification")
        self._save(incident, "verification.probe")
        return bool(probe.get("ok"))

    async def run(self, incident_id: str) -> None:
        try:
            await self._evidence(incident_id, "opening")
            await self._remediate(incident_id)
            recovered = await self._verify(incident_id)
            await self._evidence(incident_id, "closing")
            self._finish(self._current(incident_id), "CLOSED" if recovered else "FAILED")
        except Exception as exc:  # noqa: BLE001 - l'incident ne doit jamais rester bloqué sans trace
            incident = self._current(incident_id)
            self._step(incident, "Erreur interne du moteur", f"{type(exc).__name__}: {exc}", "info")
            self._finish(incident, "FAILED")
