# Deployment-optimized Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install minimal dependencies
COPY requirements-min.txt .
RUN pip install --no-cache-dir -r requirements-min.txt

# Copy application files
COPY main.py .

# Create non-root user
RUN addgroup --gid 1000 appuser \
    && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]