.PHONY: dev api worker frontend test db-up db-down migrate

# Start PostgreSQL
db-up:
	docker compose -f infra/docker-compose.dev.yml up -d

db-down:
	docker compose -f infra/docker-compose.dev.yml down

# Run database migrations
migrate:
	.venv/bin/alembic upgrade head

# Start API server
api:
	.venv/bin/uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

# Start worker
worker:
	.venv/bin/python -m apps.worker

# Start frontend dev server
frontend:
	cd apps/frontend && npm run dev

# Run tests
test:
	.venv/bin/python -m pytest tests/ -q

# Install all dependencies
install:
	uv venv .venv
	uv pip install -e ".[dev]"
	cd apps/frontend && npm install
