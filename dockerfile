# Dockerfile
FROM python:3.11-slim AS base

# Security hardening
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install IPFS client
RUN curl -LO https://dist.ipfs.tech/kubo/v0.25.0/kubo_v0.25.0_linux-amd64.tar.gz && \
    tar -xvzf kubo_v0.25.0_linux-amd64.tar.gz && \
    cd kubo && bash install.sh && \
    cd .. && rm -rf kubo kubo_v0.25.0_linux-amd64.tar.gz

# Create non-root user
RUN useradd -m -s /bin/bash vow && \
    mkdir -p /app /data /static /templates && \
    chown -R vow:vow /app /data /static /templates

WORKDIR /app

# ==================== DEVELOPMENT ====================
FROM base AS development

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --chown=vow:vow . .

USER vow
EXPOSE 8000 5678
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ==================== PRODUCTION ====================
FROM base AS production

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=vow:vow . .

# Security: Remove unnecessary packages
RUN apt-get purge -y curl gnupg && apt-get autoremove -y

USER vow
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-connections", "1000", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50"]

# ==================== WORKER ====================
FROM base AS worker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=vow:vow . .

USER vow

CMD ["python", "-m", "app.workers.start"]
