.PHONY: up down clean dev-up dev-down dev-clean migrate api worker deploy-local deploy-flows test test-unit test-integration lint test-e2e test-all test-e2e-clean

# ── Full Stack ──

up:
	docker compose up --build -d
	@echo "Full stack running: API on :8080, Prefect on :4200, PostgreSQL on :5432"

down:
	docker compose down

clean:
	docker compose down -v

# ── Infrastructure (dev) ──

dev-up:
	docker compose -f docker/docker-compose.dev.yml up -d
	@echo "Waiting for PostgreSQL..."
	@sleep 3
	@echo "Infrastructure ready: PostgreSQL on :5432, Prefect on :4200"

dev-down:
	docker compose -f docker/docker-compose.dev.yml down

dev-clean:
	docker compose -f docker/docker-compose.dev.yml down -v

# ── Database ──

migrate:
	cd .. && uv run alembic upgrade head

# ── Application ──

api:
	cd .. && uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload --loop asyncio

worker:
	cd .. && uv run prefect worker start --pool local-dev

# ── Deployment ──

deploy-local:
	@echo "Creating local-dev work pool..."
	-prefect work-pool create local-dev --type process 2>/dev/null || true
	@echo "Deploying flows..."
	cd .. && prefect deploy --all
	@echo "Local deployment complete. Start worker with: make worker"

deploy-flows:
	cd .. && prefect deploy --all

# ── Quality ──

test:
	cd .. && uv run pytest

test-unit:
	cd .. && uv run pytest tests/unit/

test-integration:
	cd .. && uv run pytest tests/integration/ -m integration

lint:
	cd .. && uv run ruff check src/ tests/

# ── E2E Tests ──

test-e2e:
	cd .. && uv run pytest tests/e2e/ -m e2e -x -v

test-all:
	cd .. && uv run pytest tests/

test-e2e-clean:
	docker ps -q --filter "label=testcontainers" | xargs -r docker rm -f
