# --- Gemeinsame Basis ---
FROM python:3.11-slim AS base

WORKDIR /app

# Systemabhaengigkeiten fuer Pillow/Reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Python Optimierungen
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONMALLOC=malloc \
    PYTHONOPTIMIZE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/data/images /app/data/backups

EXPOSE 8000

# --- Test-Stufe: docker build --target test ---
# Wird vom normalen Bau nicht angefasst, weil die Laufzeit-Stufe unten steht und
# die letzte Stufe das Standardziel ist. Ausfuehren: siehe docker-compose.test.yml.
FROM base AS test

# PYTHONOPTIMIZE entfernt assert-Anweisungen aus dem Bytecode - und damit genau
# die Pruefungen, aus denen pytest besteht. In der Test-Stufe deshalb abschalten.
ENV PYTHONOPTIMIZE=0 \
    PYTHONPATH=/app

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pyproject.toml .
COPY tests ./tests

CMD ["pytest", "-v", "--cov=app", "--cov-report=term-missing"]

# --- Laufzeit-Stufe (Standardziel) ---
FROM base AS runtime


HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Gunicorn mit mehreren Workern fuer bessere CPU-Auslastung auf Raspberry Pi
# Worker-Anzahl: 2-4 je nach CPU-Kernen (Pi 4 hat 4 Kerne)
CMD ["gunicorn", "app.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--threads", "2", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--timeout", "60", \
     "--keep-alive", "5", \
     "--preload"]
