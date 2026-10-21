"""Chargement et découpage des documents de `docs/` (Markdown). Fonctions pures, testables.

Aucune dépendance lourde : la logique de corpus ne dépend ni de LangChain, ni d'Ollama.
"""

from __future__ import annotations

import re
from pathlib import Path

CHUNK_SIZE = 1000       # caractères par fragment
CHUNK_OVERLAP = 150     # recouvrement entre fragments consécutifs (continuité du contexte)


def title_of(path: Path, text: str) -> str:
    """Titre du document : premier titre Markdown, sinon nom de fichier."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Découpe un texte en fragments avec recouvrement, en coupant de préférence sur un saut de ligne."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n", start + size - overlap, end)  # coupe nette si possible
            if cut > start:
                end = cut
        fragment = text[start:end].strip()
        if fragment:
            chunks.append(fragment)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_documents(root: str | Path) -> list[dict]:
    """Lit tous les .md sous `root` et renvoie [{source, title, text}] (source relative à root)."""
    root = Path(root)
    documents = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            documents.append({"source": str(path.relative_to(root)).replace("\\", "/"),
                              "title": title_of(path, text), "text": text})
    return documents


def build_chunks(root: str | Path, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Fragments prêts à indexer : [{source, title, text}], un par fragment."""
    chunks = []
    for document in load_documents(root):
        for fragment in chunk_text(document["text"], size, overlap):
            chunks.append({"source": document["source"], "title": document["title"], "text": fragment})
    return chunks
