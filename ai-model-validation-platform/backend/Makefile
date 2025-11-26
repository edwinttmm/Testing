.PHONY: install test lint typecheck format

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest tests/ -v --cov=src --cov-report=html

test-fast:
	pytest tests/ -v -x --ff

lint:
	flake8 src/ tests/
	pylint src/

typecheck:
	mypy src/ --strict

format:
	black src/ tests/
	isort src/ tests/

benchmark:
	pytest tests/benchmarks/ --benchmark-only
