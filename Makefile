.PHONY: install dev lint build clean docker-up docker-down

install:
	pip3 install -r server/requirements.txt
	cd client && npm install
	npm install

dev:
	@echo "Starting backend and frontend..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@cd server && python3 -m uvicorn main:app --reload & \
	cd client && npm run dev & \
	wait

lint:
	python3 -m ruff check server/
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
