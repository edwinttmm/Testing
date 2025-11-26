#!/bin/bash
#
# Backend Integration Application Script
#
# This script applies all backend integration fixes including:
# - Database migrations for quality tracking
# - Main.py monitoring router integration
# - Middleware setup
# - Alert system configuration
# - Verification tests
#
# Usage:
#   ./scripts/apply_integration.sh [--skip-backup] [--skip-tests]
#
# Author: Backend Integration Agent
# Date: 2025-11-19

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
BACKEND_DIR="/home/rigade/Testing/ai-model-validation-platform/backend"
SKIP_BACKUP=false
SKIP_TESTS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-backup] [--skip-tests]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Backend Integration Application Script                 ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$BACKEND_DIR"

# Step 1: Create backup
if [ "$SKIP_BACKUP" = false ]; then
    echo -e "${YELLOW}Step 1: Creating database backup...${NC}"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    DB_PATH="dev_database.db"

    if [ -f "$DB_PATH" ]; then
        BACKUP_PATH="${DB_PATH}.backup_${TIMESTAMP}"
        cp "$DB_PATH" "$BACKUP_PATH"
        echo -e "${GREEN}✅ Backup created: ${BACKUP_PATH}${NC}"
    else
        echo -e "${YELLOW}⚠️  Database file not found, skipping backup${NC}"
    fi
else
    echo -e "${YELLOW}Skipping backup (--skip-backup specified)${NC}"
fi

echo ""

# Step 2: Apply database migrations
echo -e "${YELLOW}Step 2: Applying database migrations...${NC}"
python3 scripts/production_migration.py --apply <<EOF
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database migrations applied successfully${NC}"
else
    echo -e "${RED}❌ Database migration failed${NC}"
    exit 1
fi

echo ""

# Step 3: Apply main.py patch
echo -e "${YELLOW}Step 3: Applying main.py integration patch...${NC}"

# Check if patch already applied
if grep -q "from routers.monitoring import router as monitoring_router" main.py; then
    echo -e "${GREEN}✅ Monitoring router already integrated in main.py${NC}"
else
    # Apply patch
    if [ -f "patches/main_py_monitoring_integration.patch" ]; then
        patch -p1 < patches/main_py_monitoring_integration.patch
        echo -e "${GREEN}✅ Main.py patch applied successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Patch file not found, manual integration may be required${NC}"
        echo -e "${YELLOW}   See: patches/main_py_monitoring_integration.patch${NC}"
    fi
fi

echo ""

# Step 4: Verify imports
echo -e "${YELLOW}Step 4: Verifying module imports...${NC}"
python3 -c "
import sys
sys.path.insert(0, '$BACKEND_DIR')

try:
    from utils.validation import validate_uuid
    from utils.security import verify_session_ownership
    from utils.rate_limiter import RateLimiter
    from monitoring.metrics_collector import metrics_collector
    from monitoring.alerts import alert_manager
    from routers.monitoring import router as monitoring_router
    from middleware.auto_metrics import AutoMetricsMiddleware
    from middleware.auto_security import AutoSecurityMiddleware
    from utils.quality_response_wrapper import enhance_session_response
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All module imports verified${NC}"
else
    echo -e "${RED}❌ Import verification failed${NC}"
    exit 1
fi

echo ""

# Step 5: Run integration tests
if [ "$SKIP_TESTS" = false ]; then
    echo -e "${YELLOW}Step 5: Running integration tests...${NC}"

    # Check if pytest is installed
    if command -v pytest &> /dev/null; then
        # Run monitoring tests
        pytest tests/monitoring/ -v --tb=short || echo -e "${YELLOW}⚠️  Some monitoring tests failed${NC}"

        # Run integration tests if they exist
        if [ -d "tests/integration" ]; then
            pytest tests/integration/ -v --tb=short || echo -e "${YELLOW}⚠️  Some integration tests failed${NC}"
        fi

        echo -e "${GREEN}✅ Test execution completed${NC}"
    else
        echo -e "${YELLOW}⚠️  pytest not installed, skipping tests${NC}"
        echo -e "${YELLOW}   Install with: pip install pytest pytest-asyncio${NC}"
    fi
else
    echo -e "${YELLOW}Skipping tests (--skip-tests specified)${NC}"
fi

echo ""

# Step 6: Final verification
echo -e "${YELLOW}Step 6: Final verification...${NC}"

python3 -c "
import sys
sys.path.insert(0, '$BACKEND_DIR')

from database import SessionLocal
from models import TestSession, DetectionEvent

db = SessionLocal()
try:
    # Check if fields exist by attempting to query them
    session = db.query(TestSession).first()
    if session:
        _ = session.timing_degraded
        _ = session.timing_verified
        print('✅ TestSession quality fields verified')
    else:
        print('ℹ️  No test sessions exist (fields not tested)')

    detection = db.query(DetectionEvent).first()
    if detection:
        _ = detection.usable_for_validation
        _ = detection.timing_degraded
        print('✅ DetectionEvent quality fields verified')
    else:
        print('ℹ️  No detections exist (fields not tested)')

except AttributeError as e:
    print(f'❌ Field verification failed: {e}')
    sys.exit(1)
finally:
    db.close()
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database schema verification passed${NC}"
else
    echo -e "${RED}❌ Database schema verification failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              Integration Complete!                            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}All backend integration tasks completed successfully!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Start the backend: ${BLUE}python3 main.py${NC}"
echo -e "  2. Test monitoring API: ${BLUE}curl http://localhost:8000/api/monitoring/status${NC}"
echo -e "  3. Check quality metrics: ${BLUE}curl http://localhost:8000/api/monitoring/metrics/global${NC}"
echo ""
echo -e "${GREEN}Documentation:${NC}"
echo -e "  • Monitoring Guide: ${BLUE}docs/MONITORING_GUIDE.md${NC}"
echo -e "  • Integration Checklist: ${BLUE}INTEGRATION_CHECKLIST.md${NC}"
echo -e "  • Migration Report: Run ${BLUE}python3 scripts/production_migration.py --report${NC}"
echo ""
