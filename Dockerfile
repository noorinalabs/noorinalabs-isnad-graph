FROM python:3.14-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .
# No CMD here — docker-compose.prod.yml `command:` is the single source of truth
# for the uvicorn invocation (includes --workers and other prod-specific flags).
# To run standalone: docker run ... /app/.venv/bin/uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
