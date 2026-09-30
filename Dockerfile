# Use official lightweight Python image
FROM python:3.11-slim

# Set environment configurations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application source and showcase frontend
COPY backend/ ./backend/
COPY showcase/ ./showcase/

# Working directory for running the backend
WORKDIR /app/backend

# Expose server port
EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/api/v1/health" >/dev/null || exit 1

# Seed demo dataset and start Uvicorn server
CMD ["sh", "-c", "python scripts/seed_demo.py || true; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
