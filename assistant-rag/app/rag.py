"""Moteur RAG : embeddings + base vectorielle + génération via Ollama (LangChain).

Ollama tourne en natif, hors Docker (OLLAMA_BASE_URL). Ce module relie le corpus (corpus.py),
la base vectorielle (store.py) et le prompt (prompt.py) au modèle. Il n'est pas importé par les
tests : la logique pure est testée dans corpus.py, store.py et prompt.py.
"""

from __future__ import annotations

import os

import numpy as np
from langchain_ollama import ChatOllama, OllamaEmbeddings

from corpus import build_chunks
from prompt import NO_CONTEXT, SYSTEM_PROMPT, build_prompt, unique_sources
from store import VectorStore, corpus_signature

DOCS_DIR = os.environ.get("DOCS_DIR", "/docs")
INDEX_DIR = os.environ.get("INDEX_DIR", "/data")
BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
TOP_K = int(os.environ.get("RAG_TOP_K", "4"))
SCORE_FLOOR = float(os.environ.get("RAG_SCORE_FLOOR", "0.3"))  # en dessous : aucun extrait jugé pertinent


class RagEngine:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=BASE_URL)
        self.chat = ChatOllama(model=MODEL, base_url=BASE_URL, temperature=0.1)
        self.store: VectorStore | None = None

    def build_index(self, force: bool = False) -> VectorStore:
        """Charge l'index si le corpus n'a pas changé, sinon ré-embarque les fragments."""
        chunks = build_chunks(DOCS_DIR)
        if not chunks:
            raise RuntimeError(f"Aucun document Markdown trouvé dans {DOCS_DIR}")
        signature = corpus_signature(chunks)
        if not force:
            existing = VectorStore.load(INDEX_DIR)
            if existing is not None and existing.signature == signature:
                self.store = existing
                return existing
        vectors = np.array(self.embeddings.embed_documents([c["text"] for c in chunks]), dtype=np.float32)
        self.store = VectorStore(chunks, vectors, signature)
        self.store.save(INDEX_DIR)
        return self.store

    def ensure_index(self) -> VectorStore:
        return self.store or self.build_index()

    def answer(self, question: str, k: int = TOP_K) -> dict:
        """Répond à partir des extraits les plus proches. Renvoie {answer, sources, chunks}."""
        store = self.ensure_index()
        query_vector = self.embeddings.embed_query(question)
        chunks = store.search(query_vector, k=k)
        if not chunks or chunks[0]["score"] < SCORE_FLOOR:
            return {"answer": NO_CONTEXT, "sources": [], "chunks": chunks}
        messages = [("system", SYSTEM_PROMPT), ("human", build_prompt(question, chunks))]
        response = self.chat.invoke(messages)
        return {"answer": response.content, "sources": unique_sources(chunks), "chunks": chunks}
