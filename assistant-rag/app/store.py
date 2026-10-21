"""Petite base vectorielle (recherche cosinus en numpy) persistée sur disque.

Le corpus (docs/) est petit : une base vectorielle légère suffit, sans dépendance externe
de type FAISS. L'index est un .npz (matrice d'embeddings normalisés) + un .json (fragments).
La signature du corpus (empreinte des fragments) évite de ré-embarquer si rien n'a changé.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def corpus_signature(chunks: list[dict]) -> str:
    """Empreinte stable du corpus : si elle change, l'index doit être reconstruit."""
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk["source"].encode())
        digest.update(chunk["text"].encode())
    return digest.hexdigest()


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


class VectorStore:
    def __init__(self, chunks: list[dict], embeddings: np.ndarray, signature: str):
        self.chunks = chunks
        self.matrix = _normalize(np.asarray(embeddings, dtype=np.float32))
        self.signature = signature

    def search(self, query_embedding, k: int = 4) -> list[dict]:
        """k fragments les plus proches (cosinus), chacun avec son score dans [-1, 1]."""
        query = np.asarray(query_embedding, dtype=np.float32)
        query = query / max(float(np.linalg.norm(query)), 1e-12)
        scores = self.matrix @ query
        top = np.argsort(scores)[::-1][:k]
        return [{**self.chunks[i], "score": round(float(scores[i]), 4)} for i in top]

    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(directory / "index.npz", matrix=self.matrix)
        (directory / "chunks.json").write_text(
            json.dumps({"signature": self.signature, "chunks": self.chunks}, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: str | Path) -> "VectorStore | None":
        directory = Path(directory)
        npz, meta = directory / "index.npz", directory / "chunks.json"
        if not (npz.exists() and meta.exists()):
            return None
        data = json.loads(meta.read_text(encoding="utf-8"))
        matrix = np.load(npz)["matrix"]
        store = cls.__new__(cls)
        store.chunks, store.matrix, store.signature = data["chunks"], matrix, data["signature"]
        return store
