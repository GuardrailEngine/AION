.PHONY: test coverage security ci clean

test:
	python -m pytest tests/ -v

coverage:
	coverage run -m pytest tests/
	coverage report --include="aion/*" --fail-under=90

security:
	bandit -r aion/ tests/ -ll

ci: test coverage security
	@echo "CI equivalent completed successfully"

clean:
	rm -rf .pytest_cache .coverage htmlcov __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
