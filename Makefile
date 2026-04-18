.PHONY: data report test

data:
	python3 scripts/build_dataset.py --fixtures --season 2026 --run-date 2026-02-17

report:
	python3 -B scripts/report_workflow.py

test:
	pytest
