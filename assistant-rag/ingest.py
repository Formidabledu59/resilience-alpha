#!/usr/bin/env python3
"""Construit (ou reconstruit) l'index vectoriel de l'assistant à partir de docs/.

Utile pour préparer l'index avant de lancer l'interface, ou après une mise à jour de la
documentation. L'assistant le construit aussi automatiquement au premier démarrage.

  python ingest.py            # reconstruit si le corpus a changé
  python ingest.py --force    # reconstruit toujours
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Indexation des documents pour l'assistant RAG")
    parser.add_argument("--force", action="store_true", help="Reconstruire même si le corpus n'a pas changé")
    args = parser.parse_args()

    from rag import DOCS_DIR, INDEX_DIR, RagEngine  # import tardif : évite de charger Ollama pour --help

    print(f"Indexation de {DOCS_DIR} vers {INDEX_DIR} ...")
    try:
        store = RagEngine().build_index(force=args.force)
    except Exception as exc:  # noqa: BLE001 - message clair plutôt qu'une trace
        print(f"Échec de l'indexation : {exc}", file=sys.stderr)
        print("Ollama est-il démarré et joignable (OLLAMA_BASE_URL) ? Le modèle d'embeddings est-il tiré ?",
              file=sys.stderr)
        return 1
    print(f"Index prêt : {len(store.chunks)} fragments, signature {store.signature[:12]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
