.PHONY: data test

data:
	python3 scripts/build_dataset.py --fixtures --season 2026 --run-date 2026-02-17

test:
	pytest
