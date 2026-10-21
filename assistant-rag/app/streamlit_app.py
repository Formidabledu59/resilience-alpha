"""Interface Streamlit de l'assistant opérateur (lecture seule), publiée sur 127.0.0.1:8501.

L'assistant répond aux questions des opérateurs à partir des documents de docs/ (runbooks,
architecture, PCA/PRA, gouvernance). Aucun accès à Docker, Vault ou au moteur de remédiation.
"""

import os

import streamlit as st

st.set_page_config(page_title="Assistant opérateur - Resilience Alpha", page_icon="🛟", layout="centered")


@st.cache_resource(show_spinner="Préparation de l'index de la documentation...")
def get_engine():
    """Moteur RAG partagé entre les sessions, index construit une fois."""
    from rag import RagEngine

    engine = RagEngine()
    engine.ensure_index()
    return engine


st.title("Assistant opérateur")
st.caption("Resilience Alpha - groupe 16. Réponses fondées sur la documentation du projet (lecture seule).")

with st.sidebar:
    st.subheader("À propos")
    st.write(
        "Cet assistant s'appuie sur les documents de `docs/` (runbooks, architecture, PCA/PRA, "
        "gouvernance) et un modèle local via Ollama. Il ne pilote rien : il aide à comprendre "
        "et à retrouver les procédures."
    )
    st.write(f"**Modèle :** `{os.environ.get('OLLAMA_MODEL', 'llama3.1:8b')}`")
    if st.button("Réindexer la documentation"):
        try:
            get_engine().build_index(force=True)
            st.success("Index reconstruit.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Réindexation impossible : {exc}")

try:
    engine = get_engine()
    ready, error = True, None
except Exception as exc:  # noqa: BLE001 - Ollama absent ou modèle non tiré : message clair, pas de crash
    ready, error = False, str(exc)

if not ready:
    st.error(
        "L'assistant n'a pas pu préparer son index. Vérifier qu'Ollama est démarré et joignable "
        f"(`OLLAMA_BASE_URL`) et que les modèles sont tirés.\n\nDétail : {error}"
    )
else:
    question = st.chat_input("Posez votre question sur la plateforme (ex. comment est prouvée la reprise ?)")
    if question:
        st.chat_message("user").write(question)
        with st.chat_message("assistant"):
            with st.spinner("Recherche dans la documentation..."):
                try:
                    result = engine.answer(question)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Le modèle n'a pas répondu : {exc}")
                else:
                    st.write(result["answer"])
                    if result["sources"]:
                        st.caption("Sources : " + ", ".join(result["sources"]))
