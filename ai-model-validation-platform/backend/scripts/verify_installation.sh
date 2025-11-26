#!/bin/bash
# Dependency Installation Verification Script

set -e

echo "======================================"
echo "Dependency Installation Verification"
echo "======================================"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found"
    exit 1
fi

echo ""
echo "Verifying Core Dependencies:"
echo "----------------------------"

# Check pytest
if python -m pytest --version > /dev/null 2>&1; then
    VERSION=$(python -m pytest --version)
    echo "✅ pytest: $VERSION"
else
    echo "❌ pytest: NOT INSTALLED"
    exit 1
fi

# Check mypy
if python -m mypy --version > /dev/null 2>&1; then
    VERSION=$(python -m mypy --version)
    echo "✅ mypy: $VERSION"
else
    echo "❌ mypy: NOT INSTALLED"
    exit 1
fi

# Check tenacity
if python -c "import tenacity; print('OK')" 2>/dev/null; then
    echo "✅ tenacity: OK"
else
    echo "❌ tenacity: NOT INSTALLED"
    exit 1
fi

# Check prometheus_client
if python -c "import prometheus_client; print('OK')" 2>/dev/null; then
    echo "✅ prometheus_client: OK"
else
    echo "❌ prometheus_client: NOT INSTALLED"
    exit 1
fi

# Check psycopg2
if python -c "import psycopg2; print('OK')" 2>/dev/null; then
    echo "✅ psycopg2: OK"
else
    echo "❌ psycopg2: NOT INSTALLED"
    exit 1
fi

# Check FastAPI
if python -c "import fastapi; print('OK')" 2>/dev/null; then
    echo "✅ fastapi: OK"
else
    echo "❌ fastapi: NOT INSTALLED"
    exit 1
fi

# Check SQLAlchemy
if python -c "import sqlalchemy; print('OK')" 2>/dev/null; then
    echo "✅ sqlalchemy: OK"
else
    echo "❌ sqlalchemy: NOT INSTALLED"
    exit 1
fi

# Check labjack-ljm
if python -c "import labjack.ljm; print('OK')" 2>/dev/null; then
    echo "✅ labjack-ljm: OK"
else
    echo "⚠️  labjack-ljm: NOT INSTALLED (optional for hardware)"
fi

echo ""
echo "Testing Infrastructure:"
echo "----------------------"

# Check pytest plugins
PYTEST_PLUGINS=("pytest-asyncio" "pytest-cov" "pytest-benchmark" "pytest-mock")
for plugin in "${PYTEST_PLUGINS[@]}"; do
    if python -c "import ${plugin//-/_}" 2>/dev/null; then
        echo "✅ $plugin: OK"
    else
        echo "❌ $plugin: NOT INSTALLED"
    fi
done

echo ""
echo "Package Count:"
echo "-------------"
TOTAL=$(pip list | wc -l)
echo "Total packages installed: $TOTAL"

echo ""
echo "======================================"
echo "✅ ALL CRITICAL DEPENDENCIES VERIFIED"
echo "======================================"
echo ""
echo "Ready for:"
echo "  - Running tests: make test"
echo "  - Type checking: make typecheck"
echo "  - Development: uvicorn main:app --reload"
echo ""
