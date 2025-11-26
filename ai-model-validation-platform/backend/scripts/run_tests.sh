#!/bin/bash
# Script to run comprehensive test suite

set -e  # Exit on error

echo "======================================"
echo "AI Model Validation Platform Test Suite"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt
pip install -q -r tests/requirements-test.txt

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
if ! pg_isready -q; then
    echo -e "${RED}PostgreSQL is not running${NC}"
    exit 1
fi

# Create test database if not exists
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test_validation_db"
echo -e "${YELLOW}Setting up test database...${NC}"
dropdb --if-exists test_validation_db
createdb test_validation_db

# Run migrations (if applicable)
# alembic upgrade head

echo ""
echo "======================================"
echo "Running Test Suite"
echo "======================================"
echo ""

# 1. Unit Tests
echo -e "${GREEN}[1/6] Running Unit Tests...${NC}"
pytest tests/unit/ -v --tb=short || true

echo ""

# 2. Integration Tests
echo -e "${GREEN}[2/6] Running Integration Tests...${NC}"
pytest tests/integration/ -v --tb=short || true

echo ""

# 3. Security Tests
echo -e "${GREEN}[3/6] Running Security Tests...${NC}"
pytest tests/security/ -v --tb=short || true

echo ""

# 4. Regression Tests
echo -e "${GREEN}[4/6] Running Regression Tests...${NC}"
pytest tests/regression/ -v --tb=short || true

echo ""

# 5. Performance Tests
echo -e "${GREEN}[5/6] Running Performance Tests...${NC}"
pytest tests/performance/ -v --tb=short -s || true

echo ""

# 6. Full Test Suite with Coverage
echo -e "${GREEN}[6/6] Running Full Suite with Coverage...${NC}"
pytest --cov=. --cov-report=html --cov-report=term-missing --cov-report=xml \
       --tb=short -v

echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo ""

# Display coverage summary
echo -e "${YELLOW}Coverage Report:${NC}"
coverage report --skip-empty

echo ""
echo -e "${GREEN}HTML coverage report: htmlcov/index.html${NC}"
echo ""

# Run security checks
echo -e "${YELLOW}Running security checks...${NC}"
bandit -r . -ll -f txt || true

echo ""
echo "======================================"
echo "Test Suite Complete"
echo "======================================"
