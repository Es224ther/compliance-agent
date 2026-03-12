PYTHON ?= .venv/bin/python

.PHONY: dev test ingest models

dev:
	$(PYTHON) -m uvicorn app.main:app

test:
	$(PYTHON) -m pytest

ingest:
	$(PYTHON) -m app.rag.ingest
