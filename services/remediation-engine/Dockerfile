FROM python:3.12.14-slim-bookworm

# Pas de .pyc (système de fichiers en lecture seule), logs non bufferisés
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py engine.py evidence.py incidents.py journal.py ./

# Utilisateur non-root (uid 10001, cohérent avec docker-compose.yml).
# /journal et /banlist appartiennent à 10001 : Docker recopie ce propriétaire dans un
# volume nommé vide au premier montage, les deux volumes restent donc inscriptibles.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /journal /banlist \
    && chown 10001:10001 /journal /banlist
USER 10001

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
