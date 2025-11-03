PROJECT        ?= price-tracker-bot
IMAGE          ?= $(PROJECT):latest
DC             ?= docker compose
COMPOSE_FILE   ?= docker-compose.yml

.PHONY: build
build:
	$(DC) -f $(COMPOSE_FILE) build

.PHONY: up
up:
	$(DC) -f $(COMPOSE_FILE) up -d

.PHONY: down
down:
	$(DC) -f $(COMPOSE_FILE) down

.PHONY: restart
restart:
	$(DC) -f $(COMPOSE_FILE) restart bot

.PHONY: logs
logs:
	$(DC) -f $(COMPOSE_FILE) logs -f bot

.PHONY: ps
ps:
	$(DC) -f $(COMPOSE_FILE) ps

.PHONY: sh-bot
sh-bot:
	$(DC) -f $(COMPOSE_FILE) exec bot bash -lc 'bash || sh'

.PHONY: sh-pg
sh-pg:
	$(DC) -f $(COMPOSE_FILE) exec postgres sh

.PHONY: psql
psql: 
	$(DC) -f $(COMPOSE_FILE) exec -e PGPASSWORD=$${POSTGRES_PASSWORD} postgres \
		psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}