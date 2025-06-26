# Backend Code Style & Linting

This project uses [Black](https://black.readthedocs.io/en/stable/) for code formatting and [Ruff](https://docs.astral.sh/ruff/) for linting (including unused import removal). Both are enforced automatically with [pre-commit](https://pre-commit.com/) hooks.

## Setup

1. **Install dependencies:**
   ```bash
   poetry install --with dev
   ```
2. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

## Running the server

- To start the backend server (using Gunicorn and Uvicorn):
  ```bash
  poetry run gunicorn backend.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --log-level debug --access-logfile - --error-logfile -
  ```
- Or, for development (using Uvicorn directly):
  ```bash
  poetry run uvicorn backend.app:app --reload
  ```

## Linting and Formatting

- **Lint with Ruff:**
  ```bash
  poetry run ruff check .
  ```
- **Auto-fix lint issues:**
  ```bash
  poetry run ruff check . --fix
  ```
- **Format with Black:**
  ```bash
  poetry run black .
  ```

## Cleaning unused imports

- `ruff` will automatically remove unused imports and apply other autofixes.

---
