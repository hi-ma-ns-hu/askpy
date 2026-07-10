.PHONY: install dev test ingest eval

# install dependencies
install:
	pip install -r requirements.txt

# run the API locally with autoreload
dev:
	uvicorn app:app --port 3000 --reload

# run the test suite
test:
	pytest -q

# build the vector index from the Stack Overflow dataset
ingest:
	python -m scripts.ingest

# run the LLM-as-judge eval harness and write evals/RESULTS.md
eval:
	python -m evals.run_evals --no-cache
	python -m evals.check_regression

eval-fast:
	python -m evals.run_evals --skip-judge

eval-fresh:
	python -m evals.run_evals --no-cache

# promote current results to baseline after manual review
eval-promote:
	python -m evals.check_regression --promote
