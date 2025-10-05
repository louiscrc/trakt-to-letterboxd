.PHONY: setup dev run scheduled logs stop clean

# Create necessary directories
setup:
	mkdir -p csv config

setup_dev:
	mkdir -p csv config && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Run once (export + auto-import)
run:
	docker compose up --remove-orphans --build

dev: 
	source venv/bin/activate && HEADLESS_IMPORT=false SCHEDULED=false python cli.py run

# Run on schedule (background)
scheduled:
	docker compose up -d

# View logs
logs:
	docker compose logs -f

# Stop all containers
stop:
	docker compose down
	docker compose -f docker-compose.dev.yml down

# Clean up everything
clean:
	docker compose down -v
	docker compose -f docker-compose.dev.yml down -v
	docker system prune -f