.PHONY: install up clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo
	@echo "Done. Edit .env to set GITHUB_TOKEN, then 'make up'."

up:
	@test -f .env || (echo "no .env yet — run 'make install' first" && exit 1)
	$(VENV)/bin/uvicorn app:app --host $${HOST:-127.0.0.1} --port $${PORT:-8000} --reload

clean:
	rm -rf $(VENV) __pycache__ *.pyc
