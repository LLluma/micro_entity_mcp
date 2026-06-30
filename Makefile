.PHONY: test lint fix

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run pyright

fix:
	uv run ruff check --fix .
	uv run ruff format .
