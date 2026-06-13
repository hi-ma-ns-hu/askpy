.PHONY: install dev test ingest

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
