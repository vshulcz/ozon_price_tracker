PROJECT        ?= price-tracker-bot
IMAGE          ?= $(PROJECT):latest
DC             ?= docker compose
COMPOSE_FILE   ?= docker-compose.yml

PYTEST_FLAGS   ?= -q -ra --maxfail=1
COV_FLAGS      ?= --cov=app --cov-report=xml --cov-report=term-missing
JUNIT_FILE     ?= pytest.xml

.PHONY: build up down restart logs ps sh-bot sh-pg psql \
        format lint type test integration-test unit cov \
		cov-html test-junit precommit ci clean

build:
	$(DC) -f $(COMPOSE_FILE) build

up:
	$(DC) -f $(COMPOSE_FILE) up -d

down:
	$(DC) -f $(COMPOSE_FILE) down

restart:
	$(DC) -f $(COMPOSE_FILE) restart bot

logs:
	$(DC) -f $(COMPOSE_FILE) logs -f bot

ps:
	$(DC) -f $(COMPOSE_FILE) ps

sh-bot:
	$(DC) -f $(COMPOSE_FILE) exec bot bash -lc 'bash || sh'

sh-pg:
	$(DC) -f $(COMPOSE_FILE) exec postgres sh

psql:
	$(DC) -f $(COMPOSE_FILE) exec -e PGPASSWORD=$${POSTGRES_PASSWORD} postgres \
		psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

format:
	uv run ruff format .

lint:
	uv run ruff check .

type:
	uv run mypy -p app

test:
	PYTHONPATH=. uv run pytest $(PYTEST_FLAGS)

integration-test:
	RUN_INTEGRATION_TESTS=1 PYTHONPATH=. uv run pytest $(PYTEST_FLAGS)

cov:
	PYTHONPATH=. uv run pytest $(PYTEST_FLAGS) $(COV_FLAGS)

cov-html:
	PYTHONPATH=. uv run pytest $(PYTEST_FLAGS) $(COV_FLAGS) --cov-report=html

test-junit:
	PYTHONPATH=. uv run pytest $(PYTEST_FLAGS) $(COV_FLAGS) --junitxml=$(JUNIT_FILE)

precommit:
	uv run pre-commit run --all-files --show-diff-on-failure

ci: format lint type test-junit

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov pytest.xml .venv
