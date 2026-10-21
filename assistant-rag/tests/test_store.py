import numpy as np

from store import VectorStore, corpus_signature


def chunks():
    return [
        {"source": "a.md", "title": "A", "text": "reprise prouvée par une transaction"},
        {"source": "b.md", "title": "B", "text": "le WAF bloque les injections SQL"},
        {"source": "c.md", "title": "C", "text": "Vault stocke les secrets"},
    ]


def embeddings():
    # Vecteurs orthogonaux : chaque requête identique à une ligne doit retrouver ce fragment
    return np.eye(3, dtype=np.float32)


def test_recherche_cosinus_classe_par_proximite():
    store = VectorStore(chunks(), embeddings(), "sig")
    top = store.search([0.0, 1.0, 0.0], k=2)
    assert top[0]["source"] == "b.md"
    assert top[0]["score"] == 1.0
    assert len(top) == 2
    assert top[1]["score"] < top[0]["score"]


def test_signature_change_si_le_corpus_change():
    base = corpus_signature(chunks())
    modifie = chunks()
    modifie[0]["text"] += " (ajout)"
    assert corpus_signature(modifie) != base
    assert corpus_signature(chunks()) == base  # stable


def test_sauvegarde_et_rechargement(tmp_path):
    store = VectorStore(chunks(), embeddings(), "sig-123")
    store.save(tmp_path)
    reloaded = VectorStore.load(tmp_path)
    assert reloaded is not None
    assert reloaded.signature == "sig-123"
    assert reloaded.chunks == chunks()
    # La recherche donne le même résultat après rechargement
    assert reloaded.search([1.0, 0.0, 0.0], k=1)[0]["source"] == "a.md"


def test_load_absent_renvoie_none(tmp_path):
    assert VectorStore.load(tmp_path) is None
