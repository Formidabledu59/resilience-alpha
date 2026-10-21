#!/usr/bin/env python3
"""Test de résilience : charge HTTP applicative contre l'API de paiement du labo.

Objectif pédagogique : saturer payment-api derrière le WAF pour que le détecteur ML
voie l'anomalie et que la remédiation se déclenche. On observe sur Grafana : canary_up
qui tombe, latence p95 qui explose, taux d'erreurs qui monte.

Garde-fous (CLAUDE.md) :
  - la cible DOIT résoudre vers une IP de 192.168.137.0/24, sinon refus (code 2) ;
  - durée bornée (--duration, défaut 60 s, plafond 300 s) ;
  - débit et concurrence réglables, pour calibrer une vraie dégradation sans plus.

À lancer depuis le PC Attaquant connecté à RESILIENCE-G16. Données fictives uniquement.

Usage :
  python flood.py --target http://192.168.137.1 --duration 60 --concurrency 50 --rps 0
  (--rps 0 = aucune limite de débit : chaque worker enchaîne les requêtes)

Flood authentifié (--auth demo) : un seul login, puis de vraies transactions de 0,01 EUR
qui touchent la base (sens alterné d'un worker à l'autre, soldes stables). Le mot de passe
est lu dans la variable d'environnement ATTACK_PASSWORD, jamais sur la ligne de commande.
"""

import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _target_guard import guard_or_exit  # noqa: E402

MAX_DURATION = 300  # plafond dur : un test de labo, pas une attaque prolongée

# Chemins sollicités. Par défaut une route applicative "chère" (crée une transaction) :
# c'est ce qui met vraiment payment-api sous pression, pas une page statique.
DEFAULT_PATH = "/api/transactions"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test de charge applicatif (labo RESILIENCE-G16)")
    p.add_argument("--target", required=True, help="URL de base, ex. http://192.168.137.1")
    p.add_argument("--duration", type=float, default=60, help="Durée en secondes (défaut 60, max 300)")
    p.add_argument("--concurrency", type=int, default=50, help="Nombre de requêtes en parallèle (défaut 50)")
    p.add_argument("--rps", type=float, default=0, help="Débit cible total en req/s (0 = sans limite)")
    p.add_argument("--path", default=DEFAULT_PATH, help=f"Chemin visé (défaut {DEFAULT_PATH})")
    p.add_argument("--method", default="POST", choices=["GET", "POST"], help="Méthode HTTP")
    p.add_argument("--auth", metavar="UTILISATEUR",
                   help="Flood authentifié : utilisateur fictif (ex. demo), mot de passe dans ATTACK_PASSWORD")
    return p.parse_args()


class Stats:
    def __init__(self) -> None:
        self.codes: Counter = Counter()
        self.errors = 0
        self.latencies: list[float] = []
        self.sent = 0

    def record(self, code: int | None, latency: float) -> None:
        self.sent += 1
        self.latencies.append(latency)
        if code is None:
            self.errors += 1
        else:
            self.codes[code] += 1


# Corps envoyé pour POST /api/transactions. Sans jeton valide, payment-api répond 401,
# mais la requête traverse quand même le WAF et le frontal : la charge est réelle. Le but
# est de saturer, pas de réussir des transactions.
PAYLOAD = {"from_account": "ACC-001", "to_account": "ACC-002", "amount": "1.00", "currency": "EUR"}


def payload_for(index: int, authenticated: bool) -> dict:
    """Corps de la transaction. Authentifié : 0,01 EUR, sens alterné selon le worker."""
    if not authenticated:
        return PAYLOAD
    source, target = ("ACC-001", "ACC-002") if index % 2 == 0 else ("ACC-002", "ACC-001")
    return {"from_account": source, "to_account": target, "amount": "0.01", "currency": "EUR"}


async def login(client: httpx.AsyncClient, base_url: str, username: str, password: str) -> str:
    """Un seul jeton pour toute l'attaque (la route de login est limitée à 10 par minute)."""
    response = await client.post(f"{base_url}/api/auth/token", json={"username": username, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


async def worker(client: httpx.AsyncClient, url: str, method: str, deadline: float,
                 stats: Stats, delay: float, payload: dict = PAYLOAD) -> None:
    while time.monotonic() < deadline:
        start = time.monotonic()
        try:
            if method == "POST":
                r = await client.post(url, json=payload)
            else:
                r = await client.get(url)
            stats.record(r.status_code, time.monotonic() - start)
        except httpx.HTTPError:
            stats.record(None, time.monotonic() - start)
        if delay:
            await asyncio.sleep(delay)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * pct))]


async def run(args: argparse.Namespace, url: str) -> Stats:
    stats = Stats()
    # Si --rps est fixé, on répartit le débit entre les workers par une pause par requête.
    delay = (args.concurrency / args.rps) if args.rps > 0 else 0.0
    deadline = time.monotonic() + min(args.duration, MAX_DURATION)
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(timeout=10, limits=limits, verify=False) as client:
        if args.auth:
            token = await login(client, args.target.rstrip("/"), args.auth, os.environ["ATTACK_PASSWORD"])
            client.headers["Authorization"] = f"Bearer {token}"
            print(f"[AUTH] Jeton obtenu pour {args.auth} : transactions réelles de 0,01 EUR")
        tasks = [worker(client, url, args.method, deadline, stats, delay, payload_for(i, bool(args.auth)))
                 for i in range(args.concurrency)]
        await asyncio.gather(*tasks)
    return stats


def main() -> None:
    args = parse_args()
    if args.duration > MAX_DURATION:
        print(f"[INFO] Durée plafonnée à {MAX_DURATION} s.", file=sys.stderr)
    # BARRIÈRE : refuse toute cible hors du réseau du labo avant d'émettre quoi que ce soit.
    guard_or_exit(args.target)
    if args.auth and not os.environ.get("ATTACK_PASSWORD"):
        print("[REFUS] --auth demande la variable d'environnement ATTACK_PASSWORD.", file=sys.stderr)
        raise SystemExit(2)
    url = args.target.rstrip("/") + args.path

    print(f"[LANCEMENT] {args.method} {url} | {args.concurrency} en parallèle | "
          f"{min(args.duration, MAX_DURATION):.0f} s | débit cible {args.rps or 'illimité'} req/s")
    started = time.monotonic()
    stats = asyncio.run(run(args, url))
    elapsed = time.monotonic() - started

    print("\n===== Résultat =====")
    print(f"Durée réelle      : {elapsed:.1f} s")
    print(f"Requêtes envoyées : {stats.sent}  (~{stats.sent / elapsed:.0f} req/s)")
    print(f"Codes HTTP        : {dict(sorted(stats.codes.items()))}")
    print(f"Erreurs réseau    : {stats.errors}")
    print(f"Latence p50 / p95 / p99 : "
          f"{percentile(stats.latencies, 0.50) * 1000:.0f} / "
          f"{percentile(stats.latencies, 0.95) * 1000:.0f} / "
          f"{percentile(stats.latencies, 0.99) * 1000:.0f} ms")
    print("\nObserver sur le dashboard (http://127.0.0.1:5173) et Grafana : "
          "canary_up, latence p95, taux d'erreurs, requêtes 429 du WAF.")


if __name__ == "__main__":
    main()
