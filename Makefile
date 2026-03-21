PYTHON ?= .venv/bin/python

.PHONY: dev test ingest models eval eval-parsing eval-retrieval eval-guardrail

dev:
	$(PYTHON) -m uvicorn app.main:app

test:
	$(PYTHON) -m pytest

ingest:
	$(PYTHON) scripts/ingest_regulations.py --skip-summary

eval:
	$(PYTHON) eval/run_eval.py --mode all --output-dir eval/results --verbose

eval-parsing:
	$(PYTHON) eval/run_eval.py --mode parsing --output-dir eval/results --verbose

eval-retrieval:
	$(PYTHON) eval/run_eval.py --mode retrieval --output-dir eval/results --verbose

eval-guardrail:
	$(PYTHON) eval/run_eval.py --mode guardrail --output-dir eval/results --verbose
