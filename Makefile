SHELL := bash
.DEFAULT_GOAL := help

# Targets for later phases fail loudly until built, so a green run never hides a missing feature.
define stub
	@echo "not implemented: $(1) (Phase $(2))" >&2; exit 1
endef

.PHONY: help install lint fmt typecheck test test-fast check \
	data-dev data-full dq crosscheck eval-retrieval eval e2e serve acceptance

help:
	@grep -E '^[a-z-]+:' Makefile | cut -d: -f1 | sort

install:
	uv sync
	uv run python -c "import duckdb; duckdb.install_extension('fts')"

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy --strict src

test:
	uv run pytest

test-fast:
	uv run pytest -m "not slow and not network" -x -q

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict src
	uv run pytest --cov --cov-fail-under=80

data-dev:
	uv run safetylens ingest --slice dev
	uv run safetylens build
	uv run safetylens index

data-full:
	uv run safetylens ingest --slice full
	uv run safetylens build
	uv run safetylens index

dq:
	uv run safetylens dq

crosscheck:
	uv run safetylens crosscheck

eval-retrieval:
	uv run safetylens eval-retrieval

eval:
	$(call stub,eval,4)

e2e:
	$(call stub,e2e,5)

serve:
	$(call stub,serve,5)

acceptance:
	$(call stub,acceptance,6)
