.PHONY: install dev test lint format clean docker-build docker-run

# Install dependencies
install:
	uv pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# Install dev dependencies
dev:
	uv pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
	pre-commit install

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=image_api --cov-report=html

# Lint code
lint:
	flake8 image_api/
	black --check image_api/

# Format code
format:
	black image_api/ tests/
	isort image_api/ tests/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build docker image
docker-build:
	docker build -t image-api:latest .

# Run docker container
docker-run:
	docker-compose up -d

# Stop docker container
docker-stop:
	docker-compose down

# Show help
help:
	@echo "Available targets:"
	@echo "  install      - Install dependencies"
	@echo "  dev          - Install dev dependencies and pre-commit hooks"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  lint         - Run linters"
	@echo "  format       - Format code"
	@echo "  clean        - Clean build artifacts"
	@echo "  docker-build - Build docker image"
	@echo "  docker-run   - Run docker container"
	@echo "  docker-stop  - Stop docker container"
