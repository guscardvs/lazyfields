.PHONY: format test

format:
	@poetry run black lazyfields tests
	@poetry run isort -ir lazyfields tests
	@poetry run autoflake --remove-all-unused-imports --remove-unused-variables --remove-duplicate-keys --expand-star-imports -ir lazyfields tests

test:
	@poetry run pytest
