.PHONY: help install install-dev test lint format check clean

help:
	@echo "TaskMaster - Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  install      - Install package in production mode"
	@echo "  install-dev  - Install package with development dependencies"
	@echo "  test         - Run unit tests with coverage"
	@echo "  lint         - Run ruff linter"
	@echo "  format       - Format code with ruff"
	@echo "  check        - Run linter and tests (pre-commit check)"
	@echo "  clean        - Remove build artifacts and cache files"

install:
	pip install -e .

install-dev:
	pip install -e .[dev]

test:
	python -m pytest

lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix src tests

check: lint test
	@echo "✓ All checks passed!"

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
