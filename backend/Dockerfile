FROM python:3.10

WORKDIR /app

# Set PYTHONPATH for backend
ENV PYTHONPATH="/app"

# Install system dependencies including build tools and BLAS libraries
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    gcc \
    g++ \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    /root/.local/bin/poetry config virtualenvs.create false

# Copy poetry files first for better caching
COPY pyproject.toml poetry.lock ./

# Install dependencies using poetry
RUN /root/.local/bin/poetry install --no-interaction --no-ansi --only=main --no-root

# Copy backend code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

# Create a directory for mounted .env file and ensure proper permissions
RUN mkdir -p /app && chown -R app:app /app

USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["gunicorn", "app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--log-level", "info", "--access-logfile", "-", "--error-logfile", "-"] 