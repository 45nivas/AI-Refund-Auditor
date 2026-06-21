.PHONY: dev install test

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install

dev:
	python run_dev.py

test:
	python backend/test_agent.py
