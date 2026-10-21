# assistant-rag

Assistant des opérateurs (RAG), **en lecture seule**. Interface Streamlit publiée sur
**`http://127.0.0.1:8501`** (PC Hôte uniquement, réseau `ui-net`). Il répond aux questions en
s'appuyant sur les documents de [`docs/`](../../docs/) (runbooks, architecture, PCA/PRA,
gouvernance) et un modèle local servi par **Ollama** (natif, hors Docker, ≤ 8B).

> Lecture seule stricte : aucun accès à Docker, Vault ou au moteur de remédiation. Il aide à
> comprendre et à retrouver les procédures, il ne pilote pas la reprise. Pas de `/metrics`
> (choix assumé, voir CLAUDE.md).

## Fonctionnement

```
docs/*.md ──► corpus (découpage) ──► embeddings Ollama ──► base vectorielle (/data)
                                                                   │
question ──► embedding ──► recherche cosinus (top-k) ──► prompt ──► modèle Ollama ──► réponse + sources
```

| Fichier | Rôle |
|---|---|
| `app/corpus.py` | Chargement des `.md` de `docs/` et découpage en fragments (pur) |
| `app/store.py` | Base vectorielle légère (cosinus numpy), persistée dans `/data`, signée (pur) |
| `app/prompt.py` | Prompt système (lecture seule, pas d'invention, cite les sources) et assemblage (pur) |
| `app/rag.py` | Embeddings + génération via Ollama (LangChain), construit / charge l'index |
| `app/streamlit_app.py` | Interface de discussion |
| `ingest.py` | Construit l'index en ligne de commande |

L'index est reconstruit automatiquement au premier démarrage, et seulement si le corpus a
changé (une signature SHA-256 des fragments évite de ré-embarquer inutilement). Si aucun extrait
n'est assez proche de la question (score cosinus sous `RAG_SCORE_FLOOR`), l'assistant répond
qu'il ne trouve pas l'information plutôt que d'inventer.

## Prérequis : Ollama et les modèles

Ollama tourne **en natif** (PC Hôte ou PC délestage IA). Tirer le modèle de génération et le
modèle d'embeddings :

```bash
ollama pull llama3.1:8b        # OLLAMA_MODEL (génération, <= 8B)
ollama pull nomic-embed-text   # OLLAMA_EMBED_MODEL (embeddings)
```

## Lancer

```bash
docker compose --profile ia up -d --build assistant-rag
```

Puis ouvrir http://127.0.0.1:8501. Variables : `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (`.env`),
`OLLAMA_EMBED_MODEL`, `RAG_TOP_K`, `RAG_SCORE_FLOOR` (défauts dans `rag.py`).

## Tests

```bash
pip install numpy pytest
cd assistant-rag && python -m pytest
```

13 tests sur la logique pure (corpus, base vectorielle, prompt), sans Ollama : découpage avec
recouvrement, recherche cosinus et classement, signature du corpus, sauvegarde / rechargement
de l'index, prompt système (lecture seule, sources).
