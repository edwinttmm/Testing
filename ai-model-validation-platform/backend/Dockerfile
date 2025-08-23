FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including LabJack support)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    wget \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgthread-2.0-0 \
    ffmpeg \
    build-essential \
    libusb-1.0-0-dev \
    libudev-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for better reliability
RUN pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.python.org download.pytorch.org" && \
    pip config set global.timeout 600 && \
    pip config set global.retries 5

# Upgrade pip and install basic tools
RUN pip install --upgrade pip setuptools wheel

# Copy requirements first for better Docker layer caching
COPY requirements-minimal.txt requirements-docker-minimal.txt ./

# Install basic requirements with extended timeout
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    --timeout 600 \
    --retries 3 \
    -r requirements-minimal.txt || \
    pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    --timeout 600 \
    --retries 3 \
    -r requirements-docker-minimal.txt

# Copy application code
COPY . .

# Install ML dependencies with extended timeout and better error handling
ENV PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org download.pytorch.org"
ENV PIP_DEFAULT_TIMEOUT=600
ENV PIP_RETRIES=3

# Try auto installer first, fallback to static requirements
RUN python auto_install_ml.py || \
    (echo "⚠️ Auto-installer failed, using fallback requirements..." && \
     pip install --no-cache-dir \
     --trusted-host pypi.org \
     --trusted-host pypi.python.org \
     --trusted-host files.pythonhosted.org \
     --timeout 600 \
     --retries 3 \
     torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
     pip install --no-cache-dir \
     --trusted-host pypi.org \
     --trusted-host pypi.python.org \
     --trusted-host files.pythonhosted.org \
     --timeout 600 \
     ultralytics opencv-python-headless pillow numpy)

EXPOSE 8000

CMD ["uvicorn", "main:socketio_app", "--host", "0.0.0.0", "--port", "8000"]