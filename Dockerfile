# syntax=docker/dockerfile:1
# Multi-arch build (amd64 + arm64) — see docs/devops/ghcr-publish-design.md
#
# Base pinned to python:3.14-slim by digest for supply-chain reproducibility
# (charter tech-decisions.md § Base Image Pinning, noorinalabs-main#735). The
# digest freezes the starting layer; the `apt-get -y upgrade` in the RUN below
# then pulls the latest Debian patches at build time so we don't ship known-fixed
# OS CVEs within the slim base (same two failure modes — floating-tag drift and
# within-tag package drift — the nginx pin in frontend/Dockerfile closes). The
# digest is the multi-arch OCI index (amd64 + arm64), so it resolves on both
# build platforms. Re-pin to a newer digest on each python minor bump.
FROM python:3.14-slim@sha256:44dd04494ee8f3b538294360e7c4b3acb87c8268e4d0a4828a6500b1eff50061 AS base

# Single RUN layer for OS deps + cleanup to minimize image size. `apt-get -y
# upgrade` keeps the pinned base's packages current within the slim lifecycle
# (the within-tag-drift half of § Base Image Pinning).
RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Two-step uv sync (see #1095): the first sync resolves/installs ONLY the locked
# dependencies (with just pyproject.toml + uv.lock present) so that layer stays
# cached across source-only changes. After `COPY . .` brings the source in, the
# second `uv sync --no-editable` installs the `isnad-graph` project itself as a
# real (non-editable) wheel — so `src` lands in the venv's site-packages. That
# makes the `isnad` console script (`[project.scripts] isnad = "src.cli:main"`)
# and `import src` resolve from the installed package with NO `PYTHONPATH=/app`
# / cwd-on-sys.path reliance (the #1093/#1094 trick this issue retires). Non-
# editable is deliberate: an editable install just re-adds the repo root to
# sys.path (same as the old PYTHONPATH trick, exposing data/docs/queries/… as
# importable), whereas a real wheel puts only `src` on the path.
FROM base AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev --no-editable

# --- Embed image (semantic re-embedding mechanism, #1057/#1088/#1071) ---------
# A SEPARATE, heavier image than the API: it installs the optional `ml` extra
# (torch + sentence-transformers) so `SentenceTransformerEmbedder` can load a real
# model and run `isnad embed-hadiths | reindex-embeddings | verify-recall` on the
# cluster. Kept out of the `runtime` (API) image so that one stays torch-free and
# lean. Built explicitly with `--target embed`; published as the distinct
# `…-isnad-graph-embed` image (see .github/workflows/ghcr-publish.yml).
FROM base AS embed-builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra ml --no-install-project
COPY . .
RUN uv sync --frozen --no-dev --extra ml --no-editable

FROM base AS embed
WORKDIR /app
COPY --from=embed-builder /app/.venv /app/.venv
COPY . .
# No PYTHONPATH: `src` is installed into the venv's site-packages as a real wheel
# (see the two-step uv sync above / #1095), so the generated /app/.venv/bin/isnad
# console script imports `src` directly even though the venv interpreter does not
# add cwd to sys.path.
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

# No PYTHONPATH: `src` is an installed wheel in the venv's site-packages (see the
# two-step uv sync above / #1095), so both `uvicorn src.api.app` and any direct
# `isnad` console-script exec resolve `import src` without relying on uvicorn's
# cwd insertion.
ENV PATH="/app/.venv/bin:$PATH"

# No CMD here — docker-compose.prod.yml `command:` is the single source of truth
# for the uvicorn invocation (includes --workers and other prod-specific flags).
# To run standalone: docker run ... uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
