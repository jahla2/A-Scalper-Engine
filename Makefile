.PHONY: test lint check

test:
	pytest

lint:
	ruff check src tests

check: lint test
