"""Construction du prompt RAG. Fonctions pures, testables (aucun appel au modèle)."""

from __future__ import annotations

SYSTEM_PROMPT = (
    "Tu es l'assistant des opérateurs de la plateforme Resilience Alpha (groupe 16). "
    "Tu réponds en français, de façon concise et factuelle, en t'appuyant UNIQUEMENT sur les "
    "extraits de documentation fournis. Si la réponse ne s'y trouve pas, dis-le clairement "
    "(\"Je ne trouve pas cette information dans la documentation\") sans inventer. "
    "Cite les documents utilisés par leur nom. Tu es en lecture seule : tu ne pilotes rien, "
    "tu aides à comprendre et à retrouver les procédures."
)

NO_CONTEXT = "Je ne trouve pas d'information pertinente dans la documentation pour répondre à cette question."


def format_context(chunks: list[dict]) -> str:
    """Assemble les extraits numérotés avec leur source, pour le prompt."""
    blocs = []
    for i, chunk in enumerate(chunks, start=1):
        blocs.append(f"[Extrait {i} - {chunk['source']} ({chunk['title']})]\n{chunk['text']}")
    return "\n\n".join(blocs)


def build_prompt(question: str, chunks: list[dict]) -> str:
    """Prompt complet (contexte + question) envoyé au modèle après le message système."""
    return (
        "Documentation disponible :\n\n"
        f"{format_context(chunks)}\n\n"
        f"Question de l'opérateur : {question}\n\n"
        "Réponds en t'appuyant sur les extraits ci-dessus et cite les documents utilisés."
    )


def unique_sources(chunks: list[dict]) -> list[str]:
    """Sources distinctes des extraits retenus, dans l'ordre d'apparition (pour l'affichage)."""
    seen, sources = set(), []
    for chunk in chunks:
        if chunk["source"] not in seen:
            seen.add(chunk["source"])
            sources.append(chunk["source"])
    return sources
