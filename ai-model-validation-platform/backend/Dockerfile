FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgthread-2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for Docker SSL issues and install CA certificates
RUN apt-get update && apt-get install -y ca-certificates && \
    pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.python.org download.pytorch.org" && \
    pip config set global.cert /etc/ssl/certs/ca-certificates.crt || true

# Try minimal requirements first, fallback to docker-minimal if SSL issues
COPY requirements-minimal.txt requirements-docker-minimal.txt ./
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements-minimal.txt || \
    pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements-docker-minimal.txt

COPY . .

# Auto-detect GPU and install appropriate ML dependencies with SSL bypass
ENV PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org download.pytorch.org"
RUN python auto_install_ml.py || echo "Using CPU-only fallback mode"

EXPOSE 8000

CMD ["uvicorn", "main:socketio_app", "--host", "0.0.0.0", "--port", "8000"]