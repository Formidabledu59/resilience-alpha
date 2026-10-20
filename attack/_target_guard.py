"""Garde-fou commun aux scripts offensifs : la cible DOIT être dans le réseau du labo.

Règle de CLAUDE.md : les scripts de attack/ prennent la cible en paramètre et refusent
toute cible hors 192.168.137.0/24. Ce module centralise cette vérification pour qu'elle
soit identique partout et impossible à oublier.
"""

import ipaddress
import socket
import sys
from urllib.parse import urlparse

LAB_NETWORK = ipaddress.ip_network("192.168.137.0/24")


class TargetRefused(Exception):
    """La cible n'est pas dans le réseau autorisé du groupe 16."""


def resolve_host(target: str) -> tuple[str, str]:
    """Retourne (hôte, ip) à partir d'une URL ou d'un hôte. Lève TargetRefused si besoin."""
    host = urlparse(target).hostname if "://" in target else target.split("/")[0].split(":")[0]
    if not host:
        raise TargetRefused(f"Cible illisible : {target!r}")
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as exc:
        raise TargetRefused(f"Hôte introuvable : {host} ({exc})") from exc
    return host, ip


def ensure_lab_target(target: str) -> tuple[str, str]:
    """Vérifie que la cible résout vers une IP du réseau du labo. Sinon, refuse."""
    host, ip = resolve_host(target)
    if ipaddress.ip_address(ip) not in LAB_NETWORK:
        raise TargetRefused(
            f"Cible interdite : {host} -> {ip} n'est pas dans {LAB_NETWORK}.\n"
            "Les scripts d'attaque ne visent QUE le SI du groupe 16 "
            "(point d'accès RESILIENCE-G16). Aborté."
        )
    return host, ip


def guard_or_exit(target: str) -> tuple[str, str]:
    """Version pour ligne de commande : affiche l'erreur et quitte avec le code 2 si refus."""
    try:
        host, ip = ensure_lab_target(target)
    except TargetRefused as exc:
        print(f"[REFUS] {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"[OK] Cible autorisée : {host} -> {ip} (dans {LAB_NETWORK})")
    return host, ip
