# syntax=docker/dockerfile:1
# Multi-arch build (amd64 + arm64) — see docs/devops/ghcr-publish-design.md
FROM python:3.14-slim AS base

# Single RUN layer for OS deps + cleanup to minimize image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

FROM base AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# --- Embed image (semantic re-embedding mechanism, #1057/#1088/#1071) ---------
# A SEPARATE, heavier image than the API: it installs the optional `ml` extra
# (torch + sentence-transformers) so `SentenceTransformerEmbedder` can load a real
# model and run `isnad embed-hadiths | reindex-embeddings | verify-recall` on the
# cluster. Kept out of the `runtime` (API) image so that one stays torch-free and
# lean. Built explicitly with `--target embed`; published as the distinct
# `…-isnad-graph-embed` image (see .github/workflows/ghcr-publish.yml).
FROM base AS embed-builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --extra ml

FROM base AS embed
WORKDIR /app
COPY --from=embed-builder /app/.venv /app/.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH"

# Default to the 384-dim multilingual model (matches EMBEDDING_DIM / the
# vector(384) column). Overridable by the deploy compose env. The build bakes the
# weights into the image so the deploy verification gate has no runtime
# HuggingFace dependency (and re-runs don't re-download).
ARG EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
ENV EMBEDDING_MODEL=${EMBED_MODEL} \
    HF_HOME=/opt/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache \
    HF_HUB_OFFLINE=0
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBED_MODEL}')"

# No CMD — the deploy one-shot job supplies the command, e.g.
#   isnad embed-hadiths --batch-size 256 && isnad reindex-embeddings && isnad verify-recall

FROM base AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

# No CMD here — docker-compose.prod.yml `command:` is the single source of truth
# for the uvicorn invocation (includes --workers and other prod-specific flags).
# To run standalone: docker run ... uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
