.PHONY: help setup setup-hooks hooks infra infra-down infra-reset test test-integration lint typecheck format clean clean-worktrees test-e2e test-e2e-headed check backup restore setup-frontend frontend-e2e frontend-e2e-headed frontend-e2e-ui frontend-e2e-live structural-ontology structural-ontology-check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies with uv
	uv sync

setup-hooks: ## Configure git hooks (legacy .githooks + pre-commit + merge driver)
	git config core.hooksPath .githooks
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
	@# Register the ontology-codegraph union merge-driver (#1128). The driver
	@# lives in the sibling noorinalabs-main; if it can't be located this is a
	@# soft warning (git falls back to a text merge for code-graph.json).
	@python3 scripts/structural_ontology.py register-merge-driver || \
		echo "warn: ontology-codegraph merge driver not registered (noorinalabs-main generator not found); see .gitattributes"
	@echo "Git hooks configured (branch-name via .githooks, pre-commit/commit-msg/pre-push via pre-commit framework)."

structural-ontology: ## Regenerate the committed structural ontology index (ontology/structural/)
	python3 scripts/structural_ontology.py emit

structural-ontology-check: ## Fail if the committed structural ontology index is stale vs source
	python3 scripts/structural_ontology.py check

hooks: ## Install pre-commit hooks (one-time setup after clone)
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
	@echo "Pre-commit hooks installed (pre-commit + commit-msg + pre-push). They run on every commit/push."

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

lint: ## Run ruff linter
	uv run ruff check src/ tests/

format: ## Run ruff formatter
	uv run ruff format src/ tests/

typecheck: ## Run mypy type checker
	uv run mypy src/

clean: ## Remove caches
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

test-e2e: ## Run Playwright browser tests (requires running app)
	uv run pytest tests/e2e/ -v -m e2e

test-e2e-headed: ## Run Playwright tests with visible browser
	uv run pytest tests/e2e/ -v -m e2e --headed

setup-frontend: ## Install frontend dependencies + Playwright browsers
	cd frontend && npm install && npx playwright install chromium

frontend-e2e: ## Run frontend Playwright E2E tests
	cd frontend && npx playwright test

frontend-e2e-headed: ## Run frontend Playwright E2E tests with visible browser
	cd frontend && npx playwright test --headed

frontend-e2e-ui: ## Run frontend Playwright E2E tests with interactive UI
	cd frontend && npx playwright test --ui

frontend-e2e-live: ## Run frontend E2E tests against live site (headed)
	cd frontend && BASE_URL=https://isnad-graph.noorinalabs.com npx playwright test --headed

clean-worktrees: ## Remove stale git worktrees
	git worktree prune
	@echo "Stale worktrees cleaned."

check:           ## Run all CI checks locally (lint + typecheck + test)
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy src/
	uv run pytest tests/ -v --tb=short -x -m "not integration and not e2e"
	@echo "All checks passed. Safe to push."

embed-hadiths: ## Compute hadith embeddings and load pgvector (semantic search; #1049)
	uv run isnad embed-hadiths $(ARGS)

backup: ## Run database backup to Backblaze B2
	bash scripts/backup.sh

restore: ## Restore databases from Backblaze B2 backup
	bash scripts/restore.sh $(ARGS)
