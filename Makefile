.PHONY: help setup setup-hooks hooks infra infra-down infra-reset acquire parse resolve load enrich test test-integration sample-data lint typecheck format clean clean-worktrees pipeline pipeline-ci pipeline-full pipeline-bootstrap pipeline-load validate validate-staging validate-pipeline profile-data test-e2e test-e2e-headed check backup restore

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies with uv (includes ML group for dedup)
	uv sync --group ml

setup-hooks: ## Configure git hooks (legacy .githooks + pre-commit)
	git config core.hooksPath .githooks
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
	@echo "Git hooks configured (branch-name via .githooks, pre-commit via pre-commit framework)."

hooks: ## Install pre-commit hooks (one-time setup after clone)
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
	@echo "Pre-commit hooks installed (pre-commit + commit-msg). They will run on every commit."

infra: ## Start Docker services
	docker compose up -d

infra-down: ## Stop Docker services
	docker compose down

infra-reset: ## Stop services and destroy volumes
	docker compose down -v

test: ## Run pytest suite
	uv run pytest

test-integration: ## Run integration tests (requires Docker)
	uv run pytest tests/integration/ -v -m integration

sample-data: ## Download sample data for integration testing
	uv run python scripts/sample_real_data.py

lint: ## Run ruff linter
	uv run ruff check src/ tests/

format: ## Run ruff formatter
	uv run ruff format src/ tests/

typecheck: ## Run mypy type checker
	uv run mypy src/

acquire: ## Phase 1: Download all data sources
	uv run isnad acquire

parse: ## Phase 1: Parse raw data into staging Parquet files
	uv run isnad parse

resolve: ## Phase 2: Entity resolution (NER + disambiguation + dedup)
	uv run isnad resolve

load: ## Phase 3: Load graph into Neo4j
	uv run isnad load

enrich: ## Phase 4: Compute metrics, topics, historical overlay
	uv run isnad enrich

clean: ## Remove staging data and caches
	rm -rf data/staging/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

validate: ## Run data quality validation (strict mode, JSON report)
	uv run isnad validate-staging --strict --output-json data/reports/validation_report.json

validate-staging: ## Validate staging Parquet files (warn mode)
	uv run isnad validate-staging

validate-pipeline: ## Run full pipeline validation against real data
	bash scripts/validate_pipeline.sh

profile-data: ## Profile staging Parquet files
	uv run python scripts/data_profile.py

test-e2e: ## Run Playwright browser tests (requires running app)
	uv run pytest tests/e2e/ -v -m e2e

test-e2e-headed: ## Run Playwright tests with visible browser
	uv run pytest tests/e2e/ -v -m e2e --headed

clean-worktrees: ## Remove stale git worktrees
	git worktree prune
	@echo "Stale worktrees cleaned."

check:           ## Run all CI checks locally (lint + typecheck + test)
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy src/
	uv run pytest tests/ -v --tb=short -x -m "not integration and not e2e"
	@echo "All checks passed. Safe to push."

pipeline: ## Run full pipeline
	$(MAKE) acquire
	$(MAKE) parse
	$(MAKE) resolve
	$(MAKE) load
	$(MAKE) enrich

pipeline-full: ## Run full pipeline with orchestration, logging, and error handling
	bash scripts/run_full_pipeline.sh --generate-manifest

pipeline-bootstrap: ## One-time VPS bootstrap: full pipeline with manifest generation
	ENVIRONMENT=production bash scripts/run_full_pipeline.sh --generate-manifest

pipeline-ci: ## Run CI pipeline stages (acquire, parse, validate-staging, resolve)
	$(MAKE) acquire
	$(MAKE) parse
	$(MAKE) validate-staging
	$(MAKE) resolve

pipeline-load: ## VPS-side only: load + enrich from existing staging/curated data
	ENVIRONMENT=production bash scripts/run_full_pipeline.sh --only-load --generate-manifest

backup: ## Run database backup to Backblaze B2
	bash scripts/backup.sh

restore: ## Restore databases from Backblaze B2 backup
	bash scripts/restore.sh $(ARGS)
