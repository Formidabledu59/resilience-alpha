#!/usr/bin/env python3
"""Scénario de bout en bout : transaction, attaque, détection, remédiation, transaction de contrôle.

Prouve la boucle de reprise autonome. N'utilise que les points publiés sur le PC Hôte :
  - WAF        : http://127.0.0.1 (ou 192.168.137.1 en démo) -> login demo + transaction métier
  - Prometheus : http://127.0.0.1:9090 -> canary_up, ml_anomaly_score
  - dashboard  : http://127.0.0.1:5173 -> incidents de la remédiation, transaction de contrôle

Étapes :
  1. Transaction métier nominale (doit réussir).
  2. Lancement de l'attaque DoS (attack/dos/flood.py, cible contrôlée par le garde-fou).
  3. Attente de la boucle : un incident s'ouvre (détection ML), la remédiation agit, l'incident
     se clôture après une transaction de contrôle réussie.
  4. Transaction métier finale (doit réussir) : la plateforme est à nouveau utilisable.

Lancement sur le PC Hôte (Prometheus et dashboard ne sont publiés que sur 127.0.0.1), stack
complète démarrée, point d'accès RESILIENCE-G16 actif (le garde-fou de flood.py refuse toute
cible hors 192.168.137.0/24, donc 127.0.0.1 aussi), mot de passe demo dans ATTACK_PASSWORD :
  export ATTACK_PASSWORD='<mot de passe demo>'
  python tests/e2e/resilience_scenario.py --waf http://192.168.137.1

Code de sortie 0 si la boucle complète est prouvée, 1 sinon (avec le motif de l'échec).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
# Le ban posé par la remédiation (BAN_MINUTES, 5 min par défaut) touche aussi le client du
# scénario : derrière Docker Desktop, tout le trafic externe arrive au WAF avec la même IP.
DEFAULT_BAN_WAIT = 6 * 60


def step(number: int, text: str) -> None:
    print(f"\n[{number}] {text}")


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


def wait_for_recovery(args: argparse.Namespace, deadline: float,
                      ignore: set[str] = frozenset()) -> tuple[bool, str]:
    """Attend qu'un NOUVEL incident s'ouvre puis se clôture (CLOSED). Renvoie (succès, message).

    `ignore` contient les incidents déjà présents avant l'attaque : le journal est persistant,
    un incident clôturé lors d'un essai précédent ne doit pas faire croire à un succès.
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
        if opened and any(i["id"] == opened for i in closed):
            return True, f"incident {opened} clôturé (transaction de contrôle réussie)"
        if opened and any(i["id"] == opened for i in failed):
            return False, f"incident {opened} en échec (FAILED) : reprise non prouvée"
        score = prometheus_scalar(args.prometheus, "max(ml_anomaly_score)")
        canary = prometheus_scalar(args.prometheus, "canary_up")
        print(f"    score ML={score}  canary_up={canary}  incidents={len(current)}", flush=True)
        time.sleep(args.poll_seconds)
    if opened is None:
        return False, ("aucun incident déclenché : l'attaque n'a pas dégradé le service "
                       "(voir docs/test-results/calibrage-attaque-dos.md pour renforcer la charge)")
    return False, f"incident {opened} non clôturé avant la fin du délai"


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
                        help="Attente maximale de la levée du ban avant la transaction finale (s)")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    password = os.environ.get("ATTACK_PASSWORD")
    if not password:
        print("Variable ATTACK_PASSWORD manquante (mot de passe de l'utilisateur demo).", file=sys.stderr)
        return 1

    try:
        step(1, "Transaction métier nominale")
        token = login(args.waf, password)
        before = business_transaction(args.waf, token)
        print(f"    transaction {before.get('id')} : {before.get('status')}")
        if before.get("status") != "COMPLETED":
            print("    échec : la transaction initiale devrait être COMPLETED", file=sys.stderr)
            return 1
        print(f"    état initial : canary_up={prometheus_scalar(args.prometheus, 'canary_up')}")

        step(2, "Lancement de l'attaque DoS")
        known = {i["id"] for i in incidents(args.dashboard)}
        attack = launch_attack(args)
        if attack is None:
            print("    échec : attaque non lancée (cible hors 192.168.137.0/24 ? ATTACK_PASSWORD ?)",
                  file=sys.stderr)
            return 1

        step(3, "Attente de la boucle (détection, remédiation, vérification)")
        recovered, message = wait_for_recovery(args, time.monotonic() + args.timeout, known)
        attack.terminate()
        try:
            attack.wait(timeout=10)
        except subprocess.TimeoutExpired:
            attack.kill()
        print(f"    {message}")
        if not recovered:
            return 1

        step(4, "Transaction métier finale (plateforme à nouveau utilisable)")
        control = control_transaction(args.dashboard)
        print(f"    transaction de contrôle : ok={control.get('ok')} status={control.get('status')}")
        after = final_transaction(args.waf, password, args.ban_wait)
        print(f"    transaction {after.get('id')} : {after.get('status')}")
        if not control.get("ok") or after.get("status") != "COMPLETED":
            print("    échec : la plateforme ne traite pas de transaction après reprise", file=sys.stderr)
            return 1

        print("\nSUCCÈS : boucle de reprise autonome prouvée (transaction, attaque, remédiation, transaction).")
        return 0
    except httpx.HTTPError as exc:
        print(f"\nErreur réseau : {exc}. La stack complète est-elle démarrée (profiles app, ia, remediation) ?",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
