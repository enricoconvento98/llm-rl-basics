.PHONY: install lint format typecheck test check up down logs services-check

COMPOSE := docker compose -f docker/docker-compose.yml --env-file .env

install:  ## create the venv and install all dependencies
	uv sync
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint typecheck test  ## everything CI runs

up:  ## start Postgres and MLflow
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

services-check:  ## verify Postgres and MLflow are healthy
	$(COMPOSE) exec -T postgres pg_isready -U $${POSTGRES_USER:-rltrading}
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-rltrading} -d rltrading -tAc "select 'rltrading db ok'"
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-rltrading} -d mlflow -tAc "select 'mlflow db ok'"
	curl -fsS http://127.0.0.1:$${MLFLOW_PORT:-5000}/health && echo " <- mlflow ok"
