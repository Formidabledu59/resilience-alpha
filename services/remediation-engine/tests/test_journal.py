from journal import Journal


def incident(status="OPEN"):
    return {"id": "inc-2026-10-20-001", "status": status, "opened_at": "2026-10-20T14:00:05+00:00", "category": "dos"}


def test_ajout_relecture_et_chaine_intacte(tmp_path):
    path = tmp_path / "incidents.jsonl"
    journal = Journal(path, echo=False)
    journal.append("incident.opened", incident())
    journal.append("incident.closed", incident("CLOSED"))

    reread = Journal(path, echo=False)  # redémarrage du moteur
    assert reread.get("inc-2026-10-20-001")["status"] == "CLOSED"
    assert reread.seq == 2 and reread.last_hash == journal.last_hash
    assert reread.verify() == {"ok": True, "entries": 2, "last_hash": journal.last_hash}


def test_une_ligne_modifiee_casse_la_chaine(tmp_path):
    path = tmp_path / "incidents.jsonl"
    journal = Journal(path, echo=False)
    journal.append("incident.opened", incident())
    journal.append("incident.closed", incident("CLOSED"))
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"OPEN"', '"CLOSED"')  # falsification de l'historique
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert journal.verify() == {"ok": False, "entries": 0, "broken_at_line": 1}


def test_une_ligne_supprimee_casse_la_chaine(tmp_path):
    path = tmp_path / "incidents.jsonl"
    journal = Journal(path, echo=False)
    for status in ("OPEN", "VERIFYING", "CLOSED"):
        journal.append("maj", incident(status))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    assert journal.verify()["broken_at_line"] == 2
