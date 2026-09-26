.PHONY: install dev test lint run docker prod-check backup

install:
	pip install -r requirements-lock.txt

dev:
	pip install -r requirements-dev.txt

test:
	python3 -m pytest tests/ -q

lint:
	ruff check .

run:
	python3 -m streamlit run app.py

docker:
	docker build -t safesight-ai .

prod-check:
	python3 scripts/prod_readiness_check.py

backup:
	python3 scripts/backup_evidence.py --retention-days $${PPE_EVIDENCE_RETENTION_DAYS:-30}
