.PHONY: setup ingest eval demo test backend frontend start test-pack

# On Windows prefer: .\scripts\setup.ps1 and .\scripts\start.ps1

PYTHON ?= python
VENV ?= .venv

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/Scripts/pip install -U pip
	$(VENV)/Scripts/pip install -r backend/requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@echo "Setup complete. Set GEMINI_API_KEY in .env before running demo/eval."

test:
	$(VENV)/Scripts/python -m pytest backend/tests -q

backend:
	cd backend && ../$(VENV)/Scripts/uvicorn app.main:app --reload --host $$(grep API_HOST ../.env 2>/dev/null | cut -d= -f2 || echo 0.0.0.0) --port $$(grep API_PORT ../.env 2>/dev/null | cut -d= -f2 || echo 8000)

ingest:
	$(VENV)/Scripts/python scripts/ingest_all.py

eval:
	$(VENV)/Scripts/python eval/run_eval.py

eval-fast:
	$(VENV)/Scripts/python eval/run_eval.py --fast

demo:
	$(VENV)/Scripts/python scripts/run_demo.py

test-pack:
	$(VENV)/Scripts/python scripts/make_test_pack.py

start:
	@echo "Use scripts/start.ps1 on Windows"
