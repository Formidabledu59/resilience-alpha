"""Tests du garde-fou de cible : aucune attaque hors 192.168.137.0/24 (règle CLAUDE.md)."""

import socket

import pytest

import _target_guard as guard


@pytest.mark.parametrize("target", [
    "http://192.168.137.1",
    "http://192.168.137.1:80/api/transactions",
    "192.168.137.42",
    "192.168.137.254:8080",
])
def test_cible_du_labo_acceptee(target):
    host, ip = guard.ensure_lab_target(target)
    assert ip.startswith("192.168.137.")


@pytest.mark.parametrize("target", [
    "http://127.0.0.1",          # le PC Hôte lui-même, hors réseau du labo
    "http://8.8.8.8",            # Internet
    "http://192.168.138.1",      # réseau voisin
    "10.0.0.1",
])
def test_cible_hors_labo_refusee(target):
    with pytest.raises(guard.TargetRefused):
        guard.ensure_lab_target(target)


def test_nom_d_hote_resolu_hors_labo_refuse(monkeypatch):
    # Un nom qui résout vers une IP extérieure doit être refusé, même s'il a l'air anodin.
    monkeypatch.setattr(socket, "gethostbyname", lambda host: "93.184.216.34")
    with pytest.raises(guard.TargetRefused):
        guard.ensure_lab_target("http://pc-hote.local")


def test_nom_d_hote_resolu_dans_le_labo_accepte(monkeypatch):
    monkeypatch.setattr(socket, "gethostbyname", lambda host: "192.168.137.1")
    assert guard.ensure_lab_target("http://pc-hote.local") == ("pc-hote.local", "192.168.137.1")


def test_hote_introuvable_refuse(monkeypatch):
    def introuvable(host):
        raise socket.gaierror("introuvable")
    monkeypatch.setattr(socket, "gethostbyname", introuvable)
    with pytest.raises(guard.TargetRefused):
        guard.ensure_lab_target("http://nexiste-pas.invalid")


def test_cible_illisible_refusee():
    with pytest.raises(guard.TargetRefused):
        guard.ensure_lab_target("http://")


def test_guard_or_exit_quitte_avec_le_code_2(capsys):
    with pytest.raises(SystemExit) as exc:
        guard.guard_or_exit("http://8.8.8.8")
    assert exc.value.code == 2
    assert "[REFUS]" in capsys.readouterr().err
