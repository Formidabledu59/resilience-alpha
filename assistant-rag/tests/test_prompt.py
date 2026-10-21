from prompt import NO_CONTEXT, SYSTEM_PROMPT, build_prompt, format_context, unique_sources


def chunks():
    return [
        {"source": "runbooks/reprise.md", "title": "Reprise", "text": "La reprise est prouvée par une transaction.", "score": 0.8},
        {"source": "architecture/README.md", "title": "Archi", "text": "Le canary passe par le WAF.", "score": 0.6},
        {"source": "runbooks/reprise.md", "title": "Reprise", "text": "Le moteur vérifie canary_up.", "score": 0.5},
    ]


def test_le_systeme_impose_lecture_seule_et_pas_d_invention():
    assert "lecture seule" in SYSTEM_PROMPT
    assert "UNIQUEMENT" in SYSTEM_PROMPT
    assert "Je ne trouve pas" in SYSTEM_PROMPT


def test_contexte_numerote_avec_sources():
    contexte = format_context(chunks())
    assert "[Extrait 1 - runbooks/reprise.md (Reprise)]" in contexte
    assert "[Extrait 2 - architecture/README.md (Archi)]" in contexte


def test_prompt_contient_question_et_contexte():
    prompt = build_prompt("Comment est prouvée la reprise ?", chunks())
    assert "Comment est prouvée la reprise ?" in prompt
    assert "La reprise est prouvée par une transaction." in prompt


def test_sources_uniques_dans_l_ordre():
    assert unique_sources(chunks()) == ["runbooks/reprise.md", "architecture/README.md"]


def test_message_sans_contexte_explicite():
    assert "documentation" in NO_CONTEXT.lower()
