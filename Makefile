BIN = $(VIRTUAL_ENV)/bin
PYTHON = $(BIN)/python3


.PHONY: install dev lint build clean docker-up docker-down

install:
	uv pip install -r server/requirements.txt
	cd client && npm install
	npm install

init-db:
	@echo "Initializing database..."
	@# This assumes you have a script or function to create tables
	@uv run python3 -c "import os; from server.trades_db import init_db; init_db()" || echo "Database already exists or init function not found."


dev:
	@echo "Starting backend and frontend..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@cd server && python3 -m uvicorn main:app --reload & \
	cd client && npm run dev & \
	wait

lint:
	${PYTHON} -m ruff check server/
	cd client && npx eslint .
	cd client && npx prettier --check .

build:
	cd client && npm run build

clean:
	rm -rf client/.next client/node_modules/.cache
	find server -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf server/.ruff_cache

docker-up:
	docker compose up --build

docker-down:
	docker compose down
