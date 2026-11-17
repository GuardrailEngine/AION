.PHONY: test coverage lint security ci clean

PYTEST := python -m pytest -q
RUFF := ruff check aion aion_core.py tests

test:
	$(PYTEST)

coverage:
	coverage run -m pytest -q
	coverage report --include="aion/*" --fail-under=90
	coverage report --include="aion_core.py,aion_core (1).py"

lint:
	$(RUFF)

security:
	bandit -r aion/ tests/ aion_core.py "aion_core (1).py" -ll

ci: test coverage lint security
	@echo "CI equivalent completed successfully"

clean:
	rm -rf .pytest_cache .coverage htmlcov __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
