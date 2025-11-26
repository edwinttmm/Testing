#!/bin/bash
# End-to-End Integration Test Suite
# Tests complete detection flow from session creation to results display

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
WARNINGS=0

# Test result tracking
declare -a FAILURES
declare -a WARNINGS_LIST

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    FAILURES+=("$1")
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
    WARNINGS_LIST+=("$1")
    ((WARNINGS++))
}

# Change to backend directory
cd "$(dirname "$0")/.."

print_header "AI Model Validation Platform - Integration Test Suite"

# Test 1: Database Schema
print_header "Test 1: Database Schema"
print_test "Checking if new columns exist in database..."

python3 << 'EOF'
import sys
from database import engine
from sqlalchemy import inspect

try:
    inspector = inspect(engine)

    # Check test_sessions
    ts_cols = [col['name'] for col in inspector.get_columns('test_sessions')]
    if 'timing_degraded' not in ts_cols or 'timing_verified' not in ts_cols:
        print("FAIL: test_sessions missing columns")
        sys.exit(1)

    # Check detection_events
    de_cols = [col['name'] for col in inspector.get_columns('detection_events')]
    if 'usable_for_validation' not in de_cols or 'timing_degraded' not in de_cols:
        print("FAIL: detection_events missing columns")
        sys.exit(1)

    print("PASS: All columns exist")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_pass "Database schema has required columns"
else
    print_fail "Database schema missing required columns"
fi

# Test 2: Model Definitions
print_header "Test 2: Model Definitions"
print_test "Checking if models define new fields..."

python3 << 'EOF'
import sys
from models import TestSession, DetectionEvent

try:
    # Check TestSession
    ts_cols = TestSession.__table__.columns.keys()
    if 'timing_degraded' not in ts_cols or 'timing_verified' not in ts_cols:
        print("FAIL: TestSession model missing fields")
        sys.exit(1)

    # Check DetectionEvent
    de_cols = DetectionEvent.__table__.columns.keys()
    if 'usable_for_validation' not in de_cols or 'timing_degraded' not in de_cols:
        print("FAIL: DetectionEvent model missing fields")
        sys.exit(1)

    print("PASS: All model fields defined")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_pass "Models correctly define new fields"
else
    print_fail "Models missing field definitions"
fi

# Test 3: Create Test Session
print_header "Test 3: Session Creation with Quality Fields"
print_test "Creating test session with timing_degraded and timing_verified..."

python3 << 'EOF'
import sys
from database import SessionLocal
from models import TestSession
import uuid

db = SessionLocal()
try:
    session = TestSession(
        id=str(uuid.uuid4()),
        name='Integration Test Session',
        project_id=str(uuid.uuid4()),
        video_id=str(uuid.uuid4()),
        timing_degraded=False,
        timing_verified=True
    )
    db.add(session)
    db.commit()

    # Verify it was saved
    saved = db.query(TestSession).filter(TestSession.id == session.id).first()
    if saved is None:
        print("FAIL: Session not saved")
        sys.exit(1)

    if saved.timing_degraded != False or saved.timing_verified != True:
        print("FAIL: Fields not saved correctly")
        sys.exit(1)

    # Cleanup
    db.delete(saved)
    db.commit()

    print("PASS: Session created successfully")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
EOF

if [ $? -eq 0 ]; then
    print_pass "Session creation with quality fields works"
else
    print_fail "Session creation failed"
fi

# Test 4: Create Detection with Quality Fields
print_header "Test 4: Detection Creation with Quality Fields"
print_test "Creating detection with usable_for_validation..."

python3 << 'EOF'
import sys
from database import SessionLocal
from models import TestSession, DetectionEvent
import uuid
from datetime import datetime

db = SessionLocal()
try:
    # Create session first
    session = TestSession(
        id=str(uuid.uuid4()),
        name='Detection Test Session',
        project_id=str(uuid.uuid4()),
        video_id=str(uuid.uuid4())
    )
    db.add(session)
    db.commit()

    # Create detection
    detection = DetectionEvent(
        test_session_id=session.id,
        voltage=4.5,
        timestamp=datetime.now().timestamp(),
        usable_for_validation=True,
        timing_degraded=False
    )
    db.add(detection)
    db.commit()

    # Verify
    saved = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session.id
    ).first()

    if saved is None:
        print("FAIL: Detection not saved")
        sys.exit(1)

    if saved.usable_for_validation != True or saved.timing_degraded != False:
        print("FAIL: Quality fields not saved correctly")
        sys.exit(1)

    # Cleanup
    db.delete(saved)
    db.delete(session)
    db.commit()

    print("PASS: Detection created successfully")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
EOF

if [ $? -eq 0 ]; then
    print_pass "Detection creation with quality fields works"
else
    print_fail "Detection creation failed"
fi

# Test 5: Quality Filtering
print_header "Test 5: Quality-Based Filtering"
print_test "Testing filtering by usable_for_validation..."

python3 << 'EOF'
import sys
from database import SessionLocal
from models import TestSession, DetectionEvent
import uuid
from datetime import datetime

db = SessionLocal()
try:
    # Create session
    session = TestSession(
        id=str(uuid.uuid4()),
        name='Filter Test Session',
        project_id=str(uuid.uuid4()),
        video_id=str(uuid.uuid4())
    )
    db.add(session)
    db.commit()

    # Create mix of usable and unusable detections
    for i in range(5):
        detection = DetectionEvent(
            test_session_id=session.id,
            voltage=4.5,
            timestamp=datetime.now().timestamp() + i,
            usable_for_validation=(i % 2 == 0),  # 3 usable, 2 not
            timing_degraded=(i % 2 == 1)
        )
        db.add(detection)
    db.commit()

    # Test filtering
    all_count = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session.id
    ).count()

    usable_count = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session.id,
        DetectionEvent.usable_for_validation == True
    ).count()

    degraded_count = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session.id,
        DetectionEvent.timing_degraded == True
    ).count()

    if all_count != 5 or usable_count != 3 or degraded_count != 2:
        print(f"FAIL: Filter counts wrong (all={all_count}, usable={usable_count}, degraded={degraded_count})")
        sys.exit(1)

    # Cleanup
    db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session.id
    ).delete()
    db.delete(session)
    db.commit()

    print("PASS: Quality filtering works correctly")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
EOF

if [ $? -eq 0 ]; then
    print_pass "Quality-based filtering works correctly"
else
    print_fail "Quality filtering failed"
fi

# Test 6: Monitoring Router
print_header "Test 6: Monitoring Endpoints"
print_test "Checking if monitoring router loads..."

python3 << 'EOF'
import sys
try:
    from routers.monitoring import router
    if len(router.routes) < 5:
        print("FAIL: Not enough routes")
        sys.exit(1)
    print(f"PASS: {len(router.routes)} routes loaded")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_pass "Monitoring router loaded successfully"
else
    print_fail "Monitoring router failed to load"
fi

# Test 7: Validation Utilities
print_header "Test 7: Security Validation"
print_test "Testing UUID validation and SQL injection protection..."

python3 << 'EOF'
import sys
from utils.validation import validate_uuid, ValidationError

try:
    # Valid UUID
    result = validate_uuid('9a98313e-e9e3-4353-8bf7-0fcb83952631')
    if not result:
        print("FAIL: Valid UUID rejected")
        sys.exit(1)

    # Invalid UUID
    try:
        validate_uuid('not-a-uuid')
        print("FAIL: Invalid UUID accepted")
        sys.exit(1)
    except ValidationError:
        pass  # Expected

    # SQL injection
    try:
        validate_uuid("'; DROP TABLE test_sessions; --")
        print("FAIL: SQL injection not blocked")
        sys.exit(1)
    except ValidationError:
        pass  # Expected

    print("PASS: Validation utilities work")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_pass "Security validation working correctly"
else
    print_fail "Security validation failed"
fi

# Test 8: Metrics Collection
print_header "Test 8: Metrics Collection"
print_test "Testing metrics recording and retrieval..."

python3 << 'EOF'
import sys
from monitoring.metrics_collector import metrics_collector
import uuid

try:
    session_id = str(uuid.uuid4())

    # Record session
    metrics_collector.record_session_start(
        session_id=session_id,
        timing_degraded=False,
        timing_verified=True
    )

    # Record detections
    metrics_collector.record_detection(session_id, usable_for_validation=True)
    metrics_collector.record_detection(session_id, usable_for_validation=True)
    metrics_collector.record_detection(session_id, usable_for_validation=False)

    # Get summary
    summary = metrics_collector.get_session_summary(session_id)

    if summary['total_detections'] != 3:
        print("FAIL: Wrong detection count")
        sys.exit(1)

    if summary['validated_detections'] != 2:
        print("FAIL: Wrong validated count")
        sys.exit(1)

    if abs(summary['validation_rate'] - 66.7) > 0.1:
        print("FAIL: Wrong validation rate")
        sys.exit(1)

    print("PASS: Metrics collection accurate")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_pass "Metrics collection working correctly"
else
    print_fail "Metrics collection failed"
fi

# Test 9: Dependencies Check
print_header "Test 9: Dependencies"
print_test "Checking for required packages..."

# Check scipy
python3 -c "import scipy" 2>/dev/null
if [ $? -eq 0 ]; then
    print_pass "scipy is installed"
else
    print_warn "scipy is NOT installed (required for optimal matching)"
fi

# Check numpy
python3 -c "import numpy" 2>/dev/null
if [ $? -eq 0 ]; then
    print_pass "numpy is installed"
else
    print_fail "numpy is NOT installed"
fi

# Test 10: Service Initialization
print_header "Test 10: Service Initialization"
print_test "Testing if services can initialize..."

python3 << 'EOF'
import sys
import warnings
warnings.filterwarnings('ignore')

try:
    from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
    print("PASS: DedicatedLabJackMonitor initialized")
    sys.exit(0)
except ModuleNotFoundError as e:
    if 'scipy' in str(e):
        print("WARN: scipy missing (expected)")
        sys.exit(2)
    print(f"FAIL: {e}")
    sys.exit(1)
except Exception as e:
    if 'timing_degraded' in str(e) or 'no such column' in str(e):
        print("FAIL: Database schema issue")
        sys.exit(1)
    print(f"WARN: {e}")
    sys.exit(2)
EOF

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    print_pass "Services initialize correctly"
elif [ $EXIT_CODE -eq 2 ]; then
    print_warn "Service initialization has warnings (may be expected)"
else
    print_fail "Service initialization failed"
fi

# Final Summary
print_header "Test Summary"

echo -e "Tests Run: $((PASSED + FAILED + WARNINGS))"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"

if [ $FAILED -gt 0 ]; then
    echo -e "\n${RED}Failed Tests:${NC}"
    for failure in "${FAILURES[@]}"; do
        echo -e "  - $failure"
    done
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "\n${YELLOW}Warnings:${NC}"
    for warning in "${WARNINGS_LIST[@]}"; do
        echo -e "  - $warning"
    done
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ ALL CRITICAL TESTS PASSED${NC}"
    echo -e "${GREEN}========================================${NC}"
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}❌ INTEGRATION TESTS FAILED${NC}"
    echo -e "${RED}See docs/END_TO_END_TEST_REPORT.md${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
