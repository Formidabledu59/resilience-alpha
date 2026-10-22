#!/usr/bin/env python3
"""Lance tous les tests du dépôt, sur n'importe quel PC qui a cloné le projet.

Même logique que la CI (.github/workflows/ci.yml) :
  - chaque dossier Python qui contient tests/ est testé séparément, avec ses dépendances ;
  - le frontend et le dashboard (React) sont testés avec npm (vitest).

Les dépendances Python sont installées dans un environnement virtuel dédié, .venv-tests/
à la racine (ignoré par Git) : rien n'est installé dans le Python du système. Aucun
conteneur ni service ne doit tourner : ce sont des tests unitaires.

Usage (Windows, Linux, macOS, Python 3.11 ou plus) :
  python tests/run_all.py                 # tout
  python tests/run_all.py --python-only   # sans le front (pas besoin de Node)
  python tests/run_all.py --only canary   # une suite dont le chemin contient « canary »
  python tests/run_all.py --no-install    # relance rapide, dépendances déjà installées
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENV = REPO / ".venv-tests"
# Dossiers parcourus pour trouver les suites Python (comme la CI).
PY_ROOTS = ["services", "ml", "assistant-rag", "biometrics", "attack", "tests"]
FRONT_APPS = ["services/frontend", "services/dashboard"]
NPM = "npm@11.21.0"  # npm 10 plante sur les dépendances de vitest (voir docs/etat-des-lieux.md)


def python_suites() -> list[Path]:
    """Dossiers contenant un sous-dossier tests/ (hors applications JavaScript)."""
    suites = set()
    for root in PY_ROOTS:
        for tests_dir in (REPO / root).rglob("tests"):
            if not tests_dir.is_dir() or "node_modules" in tests_dir.parts:
                continue
            if (tests_dir.parent / "package.json").exists():
                continue
            suites.add(tests_dir.parent)
    return sorted(suites)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd: list[str], cwd: Path) -> int:
    print(f"    $ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=cwd)


def prepare_venv(suites: list[Path], install: bool) -> Path:
    py = venv_python()
    if not py.exists():
        print(f"== Création de l'environnement de test {VENV.name}/")
        venv.create(VENV, with_pip=True)
    if install:
        print("== Installation des dépendances Python (première fois : quelques minutes)")
        run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "pytest"], REPO)
        for suite in suites:
            req = suite / "requirements.txt"
            if req.exists() and req.stat().st_size:
                if run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(req)], REPO):
                    print(f"    [ATTENTION] installation incomplète pour {suite.relative_to(REPO)}")
    return py


def run_front(app: Path, install: bool) -> int:
    npx = shutil.which("npx")
    if not npx:
        return -1
    # npx lance la version de npm épinglée, sans toucher au npm installé sur le PC.
    if install or not (app / "node_modules").exists():
        rc = run([npx, "--yes", NPM, "ci", "--no-audit", "--no-fund"], app)
        if rc:
            return rc
    return run([npx, "--yes", NPM, "test"], app)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lance tous les tests du dépôt")
    parser.add_argument("--python-only", action="store_true", help="Ne pas lancer les tests du front")
    parser.add_argument("--front-only", action="store_true", help="Ne lancer que les tests du front")
    parser.add_argument("--only", help="Ne lancer que les suites dont le chemin contient ce texte")
    parser.add_argument("--no-install", action="store_true", help="Ne pas réinstaller les dépendances")
    args = parser.parse_args()

    if sys.version_info < (3, 11):
        print("Python 3.11 ou plus est requis (les services tournent en 3.12).")
        return 2

    install = not args.no_install
    results: list[tuple[str, str]] = []

    suites = [] if args.front_only else python_suites()
    fronts = [] if args.python_only else [REPO / a for a in FRONT_APPS]
    if args.only:
        suites = [s for s in suites if args.only in s.relative_to(REPO).as_posix()]
        fronts = [f for f in fronts if args.only in f.relative_to(REPO).as_posix()]

    if suites:
        py = prepare_venv(suites, install)
        for suite in suites:
            name = suite.relative_to(REPO).as_posix()
            print(f"\n== pytest {name}")
            rc = run([str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider"], suite)
            # Code 5 = aucun test collecté : toléré, comme en CI.
            results.append((name, "OK" if rc in (0, 5) else f"ÉCHEC (code {rc})"))

    for app in fronts:
        name = app.relative_to(REPO).as_posix()
        print(f"\n== npm test {name}")
        rc = run_front(app, install)
        results.append((name, "IGNORÉ (Node.js absent)" if rc == -1 else "OK" if rc == 0 else f"ÉCHEC (code {rc})"))

    print("\n== Bilan")
    for name, verdict in results:
        print(f"    {name:32} {verdict}")
    failed = [r for r in results if r[1].startswith("ÉCHEC")]
    print(f"\n{len(results) - len(failed)}/{len(results)} suites OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
