#!/usr/bin/env python3
"""Calibrage du DoS : augmente la charge par paliers jusqu'à ce que la détection ML se déclenche.

Pour chaque palier (concurrence croissante), lance attack/dos/flood.py, relève toutes les 5 s
dans Prometheus le score ML, le canari et la latence, et regarde si une alerte ML part. On
s'arrête au premier palier qui déclenche une alerte ML : c'est le réglage à retenir pour la
démonstration. Un tableau Markdown résume les paliers.

Même contexte que resilience_scenario.py : PC Hôte, stack complète, point d'accès actif,
mot de passe demo dans ATTACK_PASSWORD.

  python tests/e2e/calibrate_dos.py --levels 100 200 400 --report docs/test-results/calibrage-attaque-dos.md

Si aucun palier ne déclenche, le WAF et le frontal absorbent l'attaque : relâcher
FRONTEND_API_RATE_LIMIT / FRONTEND_API_BURST dans .env, recréer le frontal
(docker compose --profile app up -d frontend) et relancer.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import resilience_scenario as sc

QUERIES = {
    "score": "max(ml_anomaly_score)",
    "canary_up": "canary_up",
    "canary_ratio": "canary_success_ratio",
    "latency_p95": "histogram_quantile(0.95, sum by (le) (rate(canary_latency_seconds_bucket[1m])))",
    "alerts": 'sum(ml_alerts_sent_total{result="ok"}) or vector(0)',
}


class AttackNotStarted(RuntimeError):
    """L'attaque n'a pas pu tourner : le palier n'est pas mesurable."""


def sample(prometheus: str) -> dict:
    return {name: sc.prometheus_scalar(prometheus, q) for name, q in QUERIES.items()}


def summarize(samples: list[dict], threshold: float) -> dict:
    """Résumé d'un palier : pires valeurs observées et alerte ML envoyée ou non."""
    def values(key):
        return [s[key] for s in samples if s.get(key) is not None]

    scores, ratios, latencies, alerts = values("score"), values("canary_ratio"), values("latency_p95"), values("alerts")
    return {
        "max_score": max(scores, default=None),
        "min_canary_ratio": min(ratios, default=None),
        "canary_down": any(s.get("canary_up") == 0 for s in samples),
        "max_latency_p95": max(latencies, default=None),
        "above_threshold": sum(1 for v in scores if v >= threshold),
        "ml_alert": len(alerts) >= 2 and alerts[-1] > alerts[0],
    }


def _num(value: float | None, pattern: str = "{:.2f}") -> str:
    return "-" if value is None else pattern.format(value)


def report_markdown(rows: list[dict], args: argparse.Namespace) -> str:
    lines = [
        f"## Calibrage automatique du {sc.now_utc():%d/%m/%Y %H:%M} UTC",
        "",
        f"Flood {'authentifié' if args.auth else 'anonyme'}, {args.seconds:.0f} s par palier, cible {args.waf}, "
        f"seuil ML {args.threshold}.",
        "",
        "| Concurrence | Score ML max | Relevés ≥ seuil | Canari (succès min) | Canari tombé | Latence p95 max | Alerte ML |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['concurrency']} | {_num(r['max_score'])} | {r['above_threshold']} | "
            f"{_num(r['min_canary_ratio'], '{:.0%}')} | {'oui' if r['canary_down'] else 'non'} | "
            f"{_num(r['max_latency_p95'], '{:.2f} s')} | {'**oui**' if r['ml_alert'] else 'non'} |")
    retained = next((r for r in rows if r["ml_alert"]), None)
    lines.append("")
    if retained:
        lines.append(f"**Réglage retenu : concurrence {retained['concurrency']}** (premier palier qui déclenche la détection ML).")
    else:
        lines.append("**Aucun palier n'a déclenché la détection ML** : relâcher les rate-limits du frontal "
                     "(`FRONTEND_API_RATE_LIMIT`, `FRONTEND_API_BURST`) ou monter la concurrence, puis relancer.")
    return "\n".join(lines) + "\n"


def run_level(args: argparse.Namespace, concurrency: int) -> dict:
    print(f"\n== Palier : concurrence {concurrency}, {args.seconds:.0f} s")
    if not sc.wait_nominal(args):
        print("    plateforme pas revenue au nominal, palier ignoré", file=sys.stderr)
    if args.auth:
        # Un palier précédent a pu faire bannir l'attaquant (SOC ou ML) : attendre la levée du ban.
        sc.final_transaction(args.waf, os.environ["ATTACK_PASSWORD"], args.ban_wait)
    attack_args = argparse.Namespace(**{**vars(args), "concurrency": concurrency, "attack_seconds": args.seconds})
    attack = sc.launch_attack(attack_args)
    if attack is None:
        raise AttackNotStarted("attaque non lancée (cible hors 192.168.137.0/24 ? ATTACK_PASSWORD ?)")
    samples = [sample(args.prometheus)]
    deadline = time.monotonic() + args.seconds + args.tail_seconds
    while time.monotonic() < deadline:
        time.sleep(args.poll_seconds)
        samples.append(sample(args.prometheus))
        s = samples[-1]
        print(f"    score={s['score']}  canary_up={s['canary_up']}  succès={s['canary_ratio']}  p95={s['latency_p95']}",
              flush=True)
        code = sc.attack_failed(attack)
        if code is not None:
            raise AttackNotStarted(f"l'attaque s'est arrêtée en erreur (code {code}) : WAF joignable sur {args.waf} ?")
        if summarize(samples, args.threshold)["ml_alert"]:
            print("    alerte ML envoyée au moteur de remédiation")
            break
    sc.stop_attack(attack)
    return {"concurrency": concurrency, **summarize(samples, args.threshold)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrage du DoS jusqu'au déclenchement de la détection ML")
    parser.add_argument("--waf", default="http://192.168.137.1")
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--levels", type=int, nargs="+", default=[100, 200, 400], help="Concurrences essayées")
    parser.add_argument("--seconds", type=float, default=60, help="Durée de l'attaque par palier")
    parser.add_argument("--tail-seconds", type=float, default=20, help="Observation après l'attaque")
    parser.add_argument("--threshold", type=float, default=0.7, help="Seuil ML (ML_ANOMALY_THRESHOLD)")
    parser.add_argument("--auth", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--ban-wait", type=float, default=sc.DEFAULT_BAN_WAIT,
                        help="Attente maximale de la levée d'un ban entre deux paliers (s)")
    parser.add_argument("--report", type=Path, help="Ajoute le tableau à ce fichier Markdown")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not os.environ.get("ATTACK_PASSWORD") and args.auth:
        print("Variable ATTACK_PASSWORD manquante (mot de passe de l'utilisateur demo).", file=sys.stderr)
        return 1
    rows = []
    for level in sorted(args.levels):
        try:
            rows.append(run_level(args, level))
        except AttackNotStarted as exc:
            print(f"    palier {level} interrompu : {exc}", file=sys.stderr)
            break  # on garde le rapport des paliers déjà mesurés
        if rows[-1]["ml_alert"]:
            break
    table = report_markdown(rows, args)
    print("\n" + table)
    if args.report:
        with args.report.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n" + table)
        print(f"Tableau ajouté à {args.report}")
    return 0 if rows and rows[-1]["ml_alert"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
