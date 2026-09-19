.PHONY: help install dev test lint format type-check security clean examples doc-coverage mutate docs check

# Mutation score floor for the tool handlers: 98.6% (479 of 486 checked
# mutants) on 2026-09-19. The floor sits under the measurement so one
# flaky mutant cannot block a release. The 73 verify_bic_online mutants
# crash mutmut's forked worker on macOS (respx under fork) and are only
# checked on Linux, which is where CI runs. Raise the floor when the
# score rises.
MUTATION_FLOOR ?= 90

PYTHON ?= python3
POETRY ?= poetry

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	$(POETRY) install --only main

dev: ## Install all dependencies (including dev)
	$(POETRY) install

test: ## Run tests
	$(POETRY) run pytest tests/ -v

lint: ## Run linters (ruff + black check)
	$(POETRY) run ruff check pacs008_mcp/ tests/
	$(POETRY) run black --check pacs008_mcp/ tests/

format: ## Auto-format code (ruff fix + black)
	$(POETRY) run ruff check --fix pacs008_mcp/ tests/
	$(POETRY) run black pacs008_mcp/ tests/

type-check: ## Run mypy type checking
	$(POETRY) run mypy pacs008_mcp/

security: ## Run security scan (bandit)
	$(POETRY) run bandit -r pacs008_mcp/ -c pyproject.toml 2>/dev/null || \
		$(POETRY) run bandit -r pacs008_mcp/ -ll

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/
	rm -rf coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

examples: ## Verify example scripts run
	$(POETRY) run python examples/mcp_tools.py

doc-coverage: ## Enforce the 100% docstring coverage gate
	$(POETRY) run interrogate -c pyproject.toml -v pacs008_mcp

mutate: ## Mutation testing over the tool handlers (mutmut 3, config in pyproject)
	rm -rf mutants
	# mutmut forks its workers; on macOS the Objective-C runtime aborts a
	# forked child that touches ssl/httpx (the verify_bic_online tests)
	# unless fork safety is disabled. Harmless on Linux.
	HYPOTHESIS_PROFILE=mutation OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES \
		$(POETRY) run mutmut run
	$(POETRY) run mutmut export-cicd-stats
	$(POETRY) run python scripts/mutation_gate.py --floor $(MUTATION_FLOOR)

docs: ## Build the Sphinx site, warnings are errors (poetry install --with docs)
	$(POETRY) run sphinx-build -W --keep-going -b html docs docs/_build/html

check: lint type-check test doc-coverage examples ## Run all checks
