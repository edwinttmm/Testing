#!/usr/bin/env bash
set -euo pipefail

# Create and populate a Python venv for ML (YOLO) on the backend
# Usage: bash scripts/setup_ml_venv.sh

cd "$(dirname "$0")/.."  # cd to backend/

echo "[1/6] Creating venv at backend/venv"
python3 -m venv venv

echo "[2/6] Activating venv"
source venv/bin/activate

echo "[3/6] Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

echo "[4/6] Installing CPU Torch stack"
python -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo "[5/6] Installing ultralytics + OpenCV headless"
python -m pip install --no-cache-dir ultralytics opencv-python-headless numpy

echo "[6/6] Verifying ML setup"
python scripts/verify_ml_setup.py

echo "✅ ML venv ready. To use it: source backend/venv/bin/activate"
echo "Then start the backend inside the venv so YOLO is available."

