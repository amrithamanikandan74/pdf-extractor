FROM python:3.11-slim

WORKDIR /app

# Install OS dependencies:
#  - build-essential/gcc: compiling psycopg/pgvector native extensions
#  - libmagic1: required at runtime by python-magic for upload MIME checks
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better layer caching
COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --timeout 120 -r requirements.txt

COPY . ./

# Run as a non-root user rather than the container default (root)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

# No --reload in production — it costs a filesystem watcher and isn't meant
# for a built image. For local dev, run uvicorn directly on the host instead
# (see README), where --reload is genuinely useful.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]