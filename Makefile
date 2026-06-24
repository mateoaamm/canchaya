# Atajos de desarrollo. Uso: make <target>
.PHONY: help install db migrate run test lint type fmt check cov createdb

help:
	@echo "install   - instala dependencias (incluye dev)"
	@echo "db        - levanta Postgres con docker compose"
	@echo "createdb  - crea la base de datos de tests"
	@echo "migrate   - aplica migraciones (alembic upgrade head)"
	@echo "run       - arranca la API en modo desarrollo"
	@echo "test      - corre los tests"
	@echo "cov       - corre los tests con reporte de cobertura"
	@echo "lint      - ruff"
	@echo "type      - mypy"
	@echo "fmt       - formatea con ruff"
	@echo "check     - lint + type + cov (lo que corre el CI)"

install:
	pip install -e ".[dev]"

db:
	docker compose up -d

createdb:
	createdb -h localhost -U canchaya canchaya_test || true

migrate:
	alembic upgrade head

seed:
	python -m scripts.seed

run:
	uvicorn app.main:app --reload

test:
	pytest

cov:
	pytest --cov=app --cov-report=term-missing --cov-fail-under=80

lint:
	ruff check .

type:
	mypy app

fmt:
	ruff check --fix .
	ruff format .

check: lint type cov
