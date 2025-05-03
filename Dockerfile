# ---- Frontend build stage ----
FROM node:18 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
RUN npm run build

# ---- Backend stage ----
FROM python:3.10
WORKDIR /app

# Set PYTHONPATH for backend
ENV PYTHONPATH="/app/backend"

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and built frontend
COPY backend ./backend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose and run
CMD ["gunicorn", "backend.app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-"]
