#!/bin/bash
# Quick Fix Script for Integration Issues
# Addresses critical problems found in end-to-end testing

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "$(dirname "$0")/.."

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Integration Issues Quick Fix${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Step 1: Check if virtual environment exists
echo -e "${BLUE}[1/5]${NC} Checking Python environment..."
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}No virtual environment found.${NC}"
    echo -e "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
fi

# Step 2: Install dependencies
echo -e "\n${BLUE}[2/5]${NC} Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}✅ Dependencies installed (including scipy)${NC}"

# Step 3: Fix migration chain
echo -e "\n${BLUE}[3/5]${NC} Fixing migration chain..."

# Find actual latest migration before our new one
LATEST_MIGRATION=$(ls -t alembic/versions/*.py 2>/dev/null | grep -v "add_usable_for_validation" | head -1)

if [ -z "$LATEST_MIGRATION" ]; then
    echo -e "${YELLOW}⚠️  No prior migrations found${NC}"
    echo -e "Setting down_revision to None (this will be the first migration)"
    # Migration already has down_revision = None, so we're good
else
    MIGRATION_ID=$(basename "$LATEST_MIGRATION" .py)
    echo -e "Found parent migration: ${GREEN}$MIGRATION_ID${NC}"

    # Update the migration file to reference correct parent
    sed -i "s/down_revision = None/down_revision = '$MIGRATION_ID'/" \
        alembic/versions/add_usable_for_validation_field.py

    echo -e "${GREEN}✅ Migration chain fixed${NC}"
fi

# Step 4: Apply migrations
echo -e "\n${BLUE}[4/5]${NC} Applying database migrations..."

# Check current state
CURRENT_MIGRATION=$(alembic current 2>/dev/null || echo "none")
echo -e "Current migration: $CURRENT_MIGRATION"

# Run upgrade
alembic upgrade head

echo -e "${GREEN}✅ Migrations applied${NC}"

# Step 5: Verify schema
echo -e "\n${BLUE}[5/5]${NC} Verifying database schema..."

python3 << 'EOF'
from database import engine
from sqlalchemy import inspect

inspector = inspect(engine)

# Check test_sessions
ts_cols = [col['name'] for col in inspector.get_columns('test_sessions')]
ts_ok = 'timing_degraded' in ts_cols and 'timing_verified' in ts_cols

# Check detection_events
de_cols = [col['name'] for col in inspector.get_columns('detection_events')]
de_ok = 'usable_for_validation' in de_cols and 'timing_degraded' in de_cols

if ts_ok and de_ok:
    print("✅ All required columns present")
    exit(0)
else:
    print("❌ Schema verification failed")
    if not ts_ok:
        print("  Missing in test_sessions:", set(['timing_degraded', 'timing_verified']) - set(ts_cols))
    if not de_ok:
        print("  Missing in detection_events:", set(['usable_for_validation', 'timing_degraded']) - set(de_cols))
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Schema verified successfully${NC}"
else
    echo -e "${RED}❌ Schema verification failed${NC}"
    exit 1
fi

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ All fixes applied successfully!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "Next steps:"
echo -e "1. Activate virtual environment: ${BLUE}source venv/bin/activate${NC}"
echo -e "2. Run integration tests: ${BLUE}./scripts/integration_test.sh${NC}"
echo -e "3. Start the server: ${BLUE}python main.py${NC}\n"

deactivate
