# NEFAC Document Crawler - Makefile
# Provides convenient commands for common operations

.PHONY: help install test clean crawl youtube metadata setup

help:  ## Show this help message
	@echo "NEFAC Document Crawler - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt

setup:  ## Setup environment (install deps + create .env)
	python scripts/setup.py

test:  ## Test the modular crawler components
	python tests/test_crawler.py

crawl:  ## Run full crawl
	python run_crawler.py

youtube:  ## Run YouTube-only crawl
	python run_crawler.py --youtube-only

metadata:  ## Run metadata-only crawl (no downloads)
	python run_crawler.py --metadata-only

verbose:  ## Run full crawl with verbose logging
	python run_crawler.py --verbose

clean:  ## Clean output directories
	rm -rf nefac_documents/
	rm -f nefac_crawler.log

check-deps:  ## Check if dependencies are installed
	python -c "import requests, PyPDF2, yt_dlp, selenium; print('✅ All required dependencies are installed')"

lint:  ## Run basic Python syntax check
	python -m py_compile run_crawler.py scripts/cli.py core/main_crawler.py core/config.py core/types.py

status:  ## Show crawler status and configuration
	@echo "NEFAC Crawler Status:"
	@echo "  Python: $$(python --version)"
	@echo "  Working directory: $$(pwd)"
	@echo "  .env file: $$(if [ -f .env ]; then echo 'exists'; else echo 'missing'; fi)"
	@echo "  Output directory: $$(if [ -d nefac_documents ]; then echo 'exists'; else echo 'not created'; fi)"

# Development commands
dev-install:  ## Install development dependencies
	pip install -r requirements.txt
	pip install black flake8 mypy

format:  ## Format code with black
	black scripts/ core/ extractors/ downloaders/ utils/

check:  ## Run code quality checks
	flake8 --max-line-length=100 scripts/ core/ extractors/ downloaders/ utils/
	mypy --ignore-missing-imports scripts/ core/
