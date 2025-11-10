.PHONY: dev setup test clean demo services

dev: setup
	python -m pip install -e .

setup:
	python -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt

services:
	docker-compose up -d

test:
	python -m pytest tests/ -v

clean:
	docker-compose down
	rm -rf data/raw/* data/interim/* data/processed/*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

demo: services
	python scripts/demo_pipeline.py

query:
	python server/api.py

lint:
	black .
	flake8 .

all: dev services demo