.PHONY: test run-sim report clean

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/python -m pytest

test:
	$(PYTEST)

run-sim:
	$(PYTHON) -m harness.runner --backend sim

report:
	$(PYTHON) -m harness.runner --backend sim --report

clean:
	rm -rf .pytest_cache __pycache__ harness/__pycache__ sim/__pycache__ tests/__pycache__
