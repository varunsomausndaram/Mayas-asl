.PHONY: help install install-dev install-all run dev test lint format typecheck clean docker docker-run tunnel
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

help:
	@echo "Jarvis — boil-the-ocean assistant"
	@echo ""
	@echo "  make install          Create venv + core deps"
	@echo "  make install-dev      Add dev tooling"
	@echo "  make install-all      Install every optional extra"
	@echo "  make run              Start the server (prod-ish)"
	@echo "  make dev              Start the server with reload"
	@echo "  make repl             Interactive CLI"
	@echo "  make test             Run the test suite"
	@echo "  make lint             ruff"
	@echo "  make format           ruff format"
	@echo "  make typecheck        mypy"
	@echo "  make docker           Build image"
	@echo "  make docker-run       Run container"
	@echo "  make clean            Remove caches"

$(VENV)/bin/python:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip wheel setuptools

install: $(VENV)/bin/python
	$(BIN)/pip install -e .

install-dev: $(VENV)/bin/python
	$(BIN)/pip install -e ".[dev]"

install-all: $(VENV)/bin/python
	$(BIN)/pip install -e ".[all,dev]"

run:
	$(BIN)/jarvisd

dev:
	JARVIS_RELOAD=1 $(BIN)/jarvisd

repl:
	$(BIN)/jarvis chat

test:
	$(BIN)/pytest -q

lint:
	$(BIN)/ruff check jarvis tests

format:
	$(BIN)/ruff format jarvis tests

typecheck:
	$(BIN)/mypy jarvis

docker:
	docker build -f docker/Dockerfile -t jarvis:latest .

docker-run:
	docker compose -f docker/docker-compose.yml up --build

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
