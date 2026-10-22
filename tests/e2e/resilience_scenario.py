#!/usr/bin/env python3
"""Scénario de bout en bout : transaction, attaque, détection, remédiation, transaction de contrôle.

Prouve la boucle de reprise autonome et la chronomètre. N'utilise que les points publiés sur
le PC Hôte :
  - WAF        : http://192.168.137.1 -> login demo + transaction métier
  - Prometheus : http://127.0.0.1:9090 -> canary_up, ml_anomaly_score
  - dashboard  : http://127.0.0.1:5173 -> incidents de la remédiation, transaction de contrôle

Étapes d'un essai :
  1. Transaction métier nominale (doit réussir).
  2. Lancement de l'attaque DoS (attack/dos/flood.py, cible contrôlée par le garde-fou).
  3. Attente de la boucle : un incident s'ouvre (détection), la remédiation agit, l'incident
     se clôture après une transaction de contrôle réussie.
  4. Transaction métier finale (doit réussir) : la plateforme est à nouveau utilisable.

Lancement sur le PC Hôte (Prometheus et dashboard ne sont publiés que sur 127.0.0.1), stack
complète démarrée, point d'accès RESILIENCE-G16 actif (le garde-fou de flood.py refuse toute
cible hors 192.168.137.0/24, donc 127.0.0.1 aussi), mot de passe demo dans ATTACK_PASSWORD :
  export ATTACK_PASSWORD='<mot de passe demo>'
  python tests/e2e/resilience_scenario.py --runs 3 --report docs/test-results/repetition-generale.md

Code de sortie 0 si tous les essais prouvent la boucle, 1 sinon (avec le motif de l'échec).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
# Le ban posé par la remédiation (BAN_MINUTES, 5 min par défaut) touche aussi le client du
# scénario : derrière Docker Desktop, tout le trafic externe arrive au WAF avec la même IP.
DEFAULT_BAN_WAIT = 6 * 60
CLIP_SECONDS = 60  # durée maximale du Clip Chrono


def step(number: int, text: str) -> None:
    print(f"\n[{number}] {text}")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def prometheus_scalar(prometheus: str, promql: str) -> float | None:
    try:
        response = httpx.get(f"{prometheus}/api/v1/query", params={"query": promql}, timeout=5)
        result = response.json()["data"]["result"]
        return float(result[0]["value"][1]) if result else None
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


def login(waf: str, password: str) -> str:
    response = httpx.post(f"{waf}/api/auth/token", json={"username": "demo", "password": password}, timeout=10)
    response.raise_for_status()
    return response.json()["access_token"]


def business_transaction(waf: str, token: str) -> dict:
    response = httpx.post(
        f"{waf}/api/transactions",
        json={"from_account": "ACC-001", "to_account": "ACC-002", "amount": "12.50", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )
    response.raise_for_status()
    return response.json()


def incidents(dashboard: str) -> list[dict]:
    try:
        return httpx.get(f"{dashboard}/api/remediation/incidents?limit=10", timeout=5).json()
    except (httpx.HTTPError, ValueError):
        return []


def is_ban(exc: httpx.HTTPError) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 403


def final_transaction(waf: str, password: str, ban_wait: float, poll: float = 15) -> dict:
    """Transaction métier après reprise. Attend la levée du ban (403) si la remédiation en a posé un."""
    deadline = time.monotonic() + ban_wait
    while True:
        try:
            return business_transaction(waf, login(waf, password))
        except httpx.HTTPStatusError as exc:
            if not is_ban(exc) or time.monotonic() >= deadline:
                raise
            print(f"    403 : IP bannie par la remédiation, attente de la levée du ban ({poll:.0f} s)...", flush=True)
            time.sleep(poll)
        except httpx.TransportError as exc:
            # Coupure brève (point d'accès qui redémarre, WAF recréé) : on réessaie dans le même délai.
            if time.monotonic() >= deadline:
                raise
            print(f"    {type(exc).__name__} : WAF momentanément injoignable, nouvel essai ({poll:.0f} s)...", flush=True)
            time.sleep(poll)


def control_transaction(dashboard: str) -> dict:
    response = httpx.post(f"{dashboard}/api/canary/probe", timeout=20)
    response.raise_for_status()
    return response.json()


def attack_command(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, str(REPO / "attack" / "dos" / "flood.py"),
           "--target", args.waf, "--duration", str(args.attack_seconds),
           "--concurrency", str(args.concurrency)]
    if args.auth:
        cmd += ["--auth", "demo"]
    return cmd


def launch_attack(args: argparse.Namespace, startup_seconds: float = 3) -> subprocess.Popen | None:
    """Lance flood.py. Renvoie None s'il s'arrête aussitôt (cible refusée, mot de passe absent...)."""
    cmd = attack_command(args)
    print(f"    commande : {' '.join(cmd)}")
    attack = subprocess.Popen(cmd)  # noqa: S603 - cible protégée par le garde-fou de flood.py
    try:
        code = attack.wait(timeout=startup_seconds)
    except subprocess.TimeoutExpired:
        return attack  # l'attaque tourne
    print(f"    l'attaque s'est arrêtée immédiatement (code {code})", file=sys.stderr)
    return None


def attack_failed(attack: subprocess.Popen | None) -> int | None:
    """Code de sortie si l'attaque s'est arrêtée en erreur (login refusé, WAF injoignable...), sinon None."""
    if attack is None:
        return None
    code = attack.poll()
    return code if code not in (None, 0) else None


def stop_attack(attack: subprocess.Popen) -> None:
    attack.terminate()
    try:
        attack.wait(timeout=10)
    except subprocess.TimeoutExpired:
        attack.kill()


def wait_for_recovery(args: argparse.Namespace, deadline: float, ignore: set[str] = frozenset(),
                      attack: subprocess.Popen | None = None) -> tuple[bool, str, dict | None]:
    """Attend qu'un NOUVEL incident s'ouvre puis se clôture (CLOSED).

    Renvoie (succès, message, incident). `ignore` contient les incidents déjà présents avant
    l'attaque : le journal est persistant, un incident clôturé lors d'un essai précédent ne doit
    pas faire croire à un succès.
    """
    opened = None
    while time.monotonic() < deadline:
        current = [i for i in incidents(args.dashboard) if i["id"] not in ignore]
        active = [i for i in current if i["status"] in ("OPEN", "REMEDIATING", "VERIFYING")]
        closed = [i for i in current if i["status"] == "CLOSED"]
        failed = [i for i in current if i["status"] == "FAILED"]
        if opened is None and (active or closed or failed):
            opened = (active or closed or failed)[0]["id"]
            print(f"    incident ouvert : {opened}")
        for incident in closed:
            if incident["id"] == opened:
                return True, f"incident {opened} clôturé (transaction de contrôle réussie)", incident
        for incident in failed:
            if incident["id"] == opened:
                return False, f"incident {opened} en échec (FAILED) : reprise non prouvée", incident
        code = attack_failed(attack)
        if opened is None and code is not None:
            return False, f"l'attaque s'est arrêtée en erreur (code {code}) avant tout incident : WAF joignable ?", None
        score = prometheus_scalar(args.prometheus, "max(ml_anomaly_score)")
        canary = prometheus_scalar(args.prometheus, "canary_up")
        print(f"    score ML={score}  canary_up={canary}  incidents={len(current)}", flush=True)
        time.sleep(args.poll_seconds)
    if opened is None:
        return False, ("aucun incident déclenché : l'attaque n'a pas dégradé le service "
                       "(voir docs/test-results/calibrage-attaque-dos.md pour renforcer la charge)"), None
    return False, f"incident {opened} non clôturé avant la fin du délai", None


def wait_nominal(args: argparse.Namespace, timeout: float = 180) -> bool:
    """Avant un essai : canari OK et score ML redescendu, pour ne pas mesurer la fin de l'essai précédent."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        canary = prometheus_scalar(args.prometheus, "canary_up")
        score = prometheus_scalar(args.prometheus, "max(ml_anomaly_score)")
        if canary == 1 and (score is None or score < 0.5):
            return True
        print(f"    attente du retour au nominal : canary_up={canary}  score ML={score}", flush=True)
        time.sleep(args.poll_seconds)
    return False


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def timings(attack_start: datetime, incident: dict) -> dict:
    """Durées de la boucle (s) à partir des horodatages du journal d'incidents."""
    opened, closed = _parse(incident.get("opened_at")), _parse(incident.get("closed_at"))
    detection = (opened - attack_start).total_seconds() if opened else None
    recovery = (closed - opened).total_seconds() if opened and closed else None
    total = (closed - attack_start).total_seconds() if closed else None
    return {"detection": detection, "recovery": recovery, "total": total,
            "fits_clip": total is not None and total <= CLIP_SECONDS}


def detected_by(incident: dict) -> str:
    """Qui a ouvert l'incident : le détecteur ML ou une alerte Alertmanager (nommée)."""
    alerts = incident.get("alerts") or []
    first = alerts[0] if alerts else {}
    if incident.get("source") == "ml-detector" or first.get("source") == "ml-detector":
        return "ML (Isolation Forest)"
    return first.get("name") or incident.get("source") or "inconnu"


def _fmt(seconds: float | None) -> str:
    return "-" if seconds is None else f"{seconds:.0f} s"


def report_markdown(results: list[dict], args: argparse.Namespace) -> str:
    """Tableau Markdown des essais, à coller dans docs/test-results/."""
    ok = sum(1 for r in results if r["ok"])
    lines = [
        f"## Essais du {now_utc():%d/%m/%Y %H:%M} UTC",
        "",
        f"Réglages : attaque {args.attack_seconds:.0f} s, concurrence {args.concurrency}, "
        f"flood {'authentifié' if args.auth else 'anonyme'}, cible {args.waf}.",
        "",
        "| Essai | Résultat | Détecté par | Détection | Remédiation + vérification | Total | Clip (≤ 60 s) | Incident |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        t = r.get("timings") or {}
        lines.append(
            f"| {i} | {'OK' if r['ok'] else 'ÉCHEC'} | {r.get('detected_by', '-')} | {_fmt(t.get('detection'))} | "
            f"{_fmt(t.get('recovery'))} | {_fmt(t.get('total'))} | "
            f"{'oui' if t.get('fits_clip') else 'non'} | {r.get('incident') or '-'} |")
    lines += ["", f"**{ok}/{len(results)} essais réussis.**"]
    failures = [f"- Essai {i} : {r['message']}" for i, r in enumerate(results, 1) if not r["ok"]]
    if failures:
        lines += ["", *failures]
    return "\n".join(lines) + "\n"


def run_once(args: argparse.Namespace, password: str) -> dict:
    """Un essai complet. Renvoie {ok, message, incident, detected_by, timings}."""
    result = {"ok": False, "message": "", "incident": None}
    try:
        step(1, "Transaction métier nominale")
        before = final_transaction(args.waf, password, args.ban_wait)
        print(f"    transaction {before.get('id')} : {before.get('status')}")
        if before.get("status") != "COMPLETED":
            result["message"] = "la transaction initiale devrait être COMPLETED"
            return result

        step(2, "Lancement de l'attaque DoS")
        known = {i["id"] for i in incidents(args.dashboard)}
        attack_start = now_utc()
        attack = launch_attack(args)
        if attack is None:
            result["message"] = "attaque non lancée (cible hors 192.168.137.0/24 ? ATTACK_PASSWORD ?)"
            return result

        step(3, "Attente de la boucle (détection, remédiation, vérification)")
        recovered, message, incident = wait_for_recovery(args, time.monotonic() + args.timeout, known, attack)
        stop_attack(attack)
        print(f"    {message}")
        result["message"] = message
        if incident:
            result.update(incident=incident["id"], detected_by=detected_by(incident),
                          timings=timings(attack_start, incident))
            t = result["timings"]
            print(f"    détecté par {result['detected_by']} : détection {_fmt(t['detection'])}, "
                  f"remédiation + vérification {_fmt(t['recovery'])}, total {_fmt(t['total'])}")
        if not recovered:
            return result

        step(4, "Transaction métier finale (plateforme à nouveau utilisable)")
        control = control_transaction(args.dashboard)
        print(f"    transaction de contrôle : ok={control.get('ok')} status={control.get('status')}")
        after = final_transaction(args.waf, password, args.ban_wait)
        print(f"    transaction {after.get('id')} : {after.get('status')}")
        if not control.get("ok") or after.get("status") != "COMPLETED":
            result["message"] = "la plateforme ne traite pas de transaction après reprise"
            return result
        result["ok"] = True
        return result
    except httpx.HTTPError as exc:
        result["message"] = f"erreur réseau : {exc}. La stack complète est-elle démarrée (profiles app, ia, remediation) ?"
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scénario de résilience de bout en bout")
    parser.add_argument("--waf", default="http://192.168.137.1", help="URL du WAF (dans 192.168.137.0/24)")
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--dashboard", default="http://127.0.0.1:5173")
    parser.add_argument("--attack-seconds", type=float, default=90)
    parser.add_argument("--concurrency", type=int, default=200)
    parser.add_argument("--auth", action=argparse.BooleanOptionalAction, default=True,
                        help="Flood authentifié, par défaut (--no-auth : flood anonyme, sans charge base)")
    parser.add_argument("--timeout", type=float, default=300, help="Délai maximal pour la reprise (s)")
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--ban-wait", type=float, default=DEFAULT_BAN_WAIT,
                        help="Attente maximale de la levée du ban avant une transaction (s)")
    parser.add_argument("--runs", type=int, default=1, help="Nombre d'essais enchaînés (répétition : 3)")
    parser.add_argument("--report", type=Path, help="Ajoute le tableau des essais à ce fichier Markdown")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    password = os.environ.get("ATTACK_PASSWORD")
    if not password:
        print("Variable ATTACK_PASSWORD manquante (mot de passe de l'utilisateur demo).", file=sys.stderr)
        return 1

    results = []
    for run in range(1, args.runs + 1):
        print(f"\n===== Essai {run}/{args.runs} =====")
        if run > 1 and not wait_nominal(args):
            results.append({"ok": False, "message": "plateforme pas revenue au nominal entre deux essais"})
            break
        results.append(run_once(args, password))
        if not results[-1]["ok"]:
            print(f"\nÉCHEC : {results[-1]['message']}", file=sys.stderr)

    table = report_markdown(results, args)
    print("\n" + table)
    if args.report:
        with args.report.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n" + table)
        print(f"Tableau ajouté à {args.report}")
    ok = all(r["ok"] for r in results) and len(results) == args.runs
    if ok:
        print("SUCCÈS : boucle de reprise autonome prouvée (transaction, attaque, remédiation, transaction).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
