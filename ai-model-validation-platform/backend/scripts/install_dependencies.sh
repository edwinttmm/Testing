#!/bin/bash
set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Installing production dependencies..."
pip install -r requirements.txt

if [ "$ENVIRONMENT" = "development" ]; then
    echo "Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

echo "Verifying installations..."
python -m pytest --version
python -m mypy --version
python -c "import tenacity; print(f'tenacity {tenacity.__version__}')"
python -c "import prometheus_client; print('prometheus_client OK')"

echo "✅ All dependencies installed successfully"
