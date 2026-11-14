PY := .venv/bin/python
COMPOSE := docker compose --env-file .env -f infra/compose/compose.yaml
.PHONY: setup seed serve test check evidence evaluate prepare core extended index stop reset clean-offline
setup:
	python3 -m venv .venv
	$(PY) -m pip install --disable-pip-version-check -r requirements.lock
seed:
	$(PY) -m p091.seed
serve:
	$(PY) -m uvicorn p091.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
test:
	$(PY) -m pytest tests -q
check:
	.venv/bin/ruff check p091 scripts tests
	.venv/bin/mypy p091 scripts --ignore-missing-imports
evidence:
	$(PY) scripts/run_evidence.py
evaluate:
	$(PY) scripts/run_promptfoo.py
prepare:
	$(PY) scripts/bootstrap_live.py prepare
core: prepare
	$(COMPOSE) --profile core up -d --wait postgres keycloak openfga qdrant vector-ready
	$(PY) scripts/bootstrap_live.py configure
	$(COMPOSE) --profile core up -d --build --wait api
	$(PY) scripts/bootstrap_live.py index
extended: core
	$(COMPOSE) --profile extended up -d --wait nextcloud
	$(PY) scripts/seed_nextcloud.py
	$(PY) scripts/enable_nextcloud.py
	$(COMPOSE) --profile extended up -d --force-recreate --wait api
	$(PY) scripts/bootstrap_live.py index
index:
	$(PY) scripts/bootstrap_live.py index
stop:
	$(COMPOSE) --profile core --profile extended down --remove-orphans
reset:
	$(COMPOSE) --profile core --profile extended down --volumes --remove-orphans
	$(PY) scripts/reset_ids.py
clean-offline:
	$(PY) scripts/reset_offline.py
