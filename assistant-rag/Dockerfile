FROM python:3.12.14-slim-bookworm

# Pas de .pyc (système de fichiers en lecture seule), logs non bufferisés.
# HOME et configuration Streamlit dans /tmp (tmpfs) : le reste est en lecture seule.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    STREAMLIT_HOME=/tmp \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY ingest.py ./

# Utilisateur non-root (uid 10001, cohérent avec docker-compose.yml). L'index est écrit
# dans /data (volume rag-index). docs/ est monté en lecture seule sur /docs.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001

EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
