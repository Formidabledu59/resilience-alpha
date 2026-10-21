from pathlib import Path

from corpus import build_chunks, chunk_text, load_documents, title_of


def test_titre_depuis_le_premier_h1(tmp_path):
    assert title_of(Path("x.md"), "# Mon titre\n\ntexte") == "Mon titre"
    assert title_of(Path("runbook.md"), "pas de titre") == "runbook"


def test_decoupage_avec_recouvrement():
    text = "\n".join(f"ligne {i} " * 10 for i in range(60))
    chunks = chunk_text(text, size=500, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # Le recouvrement garantit une continuité : la fin d'un fragment réapparaît au suivant
    fin = chunks[0][-40:].strip()
    assert fin and fin in chunks[1]


def test_texte_court_un_seul_fragment():
    assert chunk_text("court", size=1000) == ["court"]
    assert chunk_text("   ", size=1000) == []


def test_chargement_et_fragments(tmp_path):
    (tmp_path / "sous").mkdir()
    (tmp_path / "a.md").write_text("# Doc A\n\nContenu A", encoding="utf-8")
    (tmp_path / "sous" / "b.md").write_text("# Doc B\n\nContenu B", encoding="utf-8")
    (tmp_path / "vide.md").write_text("   ", encoding="utf-8")  # ignoré
    (tmp_path / "note.txt").write_text("pas du markdown", encoding="utf-8")  # ignoré

    docs = load_documents(tmp_path)
    assert [d["source"] for d in docs] == ["a.md", "sous/b.md"]
    assert docs[1]["title"] == "Doc B"

    chunks = build_chunks(tmp_path)
    assert {c["source"] for c in chunks} == {"a.md", "sous/b.md"}
    assert all({"source", "title", "text"} <= c.keys() for c in chunks)
