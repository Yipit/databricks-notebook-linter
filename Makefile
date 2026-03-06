.PHONY: setup test clean format lint build publish all

setup:
	@test -d .venv || uv venv --seed
	@uv sync

lint:
	@uv run ruff check .

format:
	@uv run ruff format .
	@uv run ruff check --fix .

test:
	@uv run pytest

build: clean
	@echo "Building package..."
	@uv build
	@echo "Build complete!"

publish: build
	@echo "Publishing package..."
	@uv run uv-publish.py pypi
	@echo "Publish complete!"

clean:
	@echo "Cleaning up..."
	@rm -rf __pycache__/ .pytest_cache/
	@rm -rf dist/ build/
	@find . -name "*.pyc" -delete
	@find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Done."

all: setup test
