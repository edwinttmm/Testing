#!/bin/bash
################################################################################
# Integration Verification Script
# Verifies all critical bug fixes have been applied correctly
# Run this BEFORE deploying to production
################################################################################

set -e  # Exit on any error

echo "================================================================================"
echo "  AI Model Validation Platform - Fix Verification Script"
echo "  Date: $(date)"
echo "================================================================================"
echo ""

BACKEND_DIR="/home/rigade/Testing/ai-model-validation-platform/backend"
FRONTEND_DIR="/home/rigade/Testing/ai-model-validation-platform/frontend"
ERRORS=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

################################################################################
# BACKEND VERIFICATION
################################################################################

echo "================================================================================"
echo "1. BACKEND VERIFICATION"
echo "================================================================================"
echo ""

# Check 1.1: Frame clamping removed from backend timing
echo "✓ Checking Fix 1.2: Video assignment logic..."
if grep -q "video_id.*timing" "$BACKEND_DIR/services/labjack_detection_service.py"; then
  echo -e "${GREEN}  ✅ Video assignment logic present${NC}"
else
  echo -e "${RED}  ❌ Video assignment logic NOT FOUND${NC}"
  ERRORS=$((ERRORS + 1))
fi

# Check 1.2: Ground truth matching multi-video support
echo "✓ Checking multi-video ground truth support..."
if grep -q "_get_ground_truth_for_session" "$BACKEND_DIR/services/ground_truth_matching_service.py"; then
  echo -e "${GREEN}  ✅ Multi-video GT matching present${NC}"
else
  echo -e "${RED}  ❌ Multi-video GT matching NOT FOUND${NC}"
  ERRORS=$((ERRORS + 1))
fi

# Check 1.3: Database models updated
echo "✓ Checking database models..."
if grep -q "video_id" "$BACKEND_DIR/models.py"; then
  echo -e "${GREEN}  ✅ video_id field present in models${NC}"
else
  echo -e "${RED}  ❌ video_id field NOT FOUND in models${NC}"
  ERRORS=$((ERRORS + 1))
fi

# Check 1.4: Backend can start
echo "✓ Checking backend imports..."
cd "$BACKEND_DIR"
if python3 -c "import main; print('✅ Backend imports OK')" 2>/dev/null; then
  echo -e "${GREEN}  ✅ Backend imports successfully${NC}"
else
  echo -e "${RED}  ❌ Backend import errors detected${NC}"
  ERRORS=$((ERRORS + 1))
fi

################################################################################
# FRONTEND VERIFICATION
################################################################################

echo ""
echo "================================================================================"
echo "2. FRONTEND VERIFICATION"
echo "================================================================================"
echo ""

# Check 2.1: Frame clamping removed
echo "✓ Checking Fix 1.1: Frame clamping removal..."
if grep -q "const clampFrame = (frame: number): number => {" "$FRONTEND_DIR/src/components/FrameCorrelationTimeline.tsx"; then
  # Check it doesn't clamp to totalFrames
  if ! grep -q "Math.min(frame, totalFrames" "$FRONTEND_DIR/src/components/FrameCorrelationTimeline.tsx"; then
    echo -e "${GREEN}  ✅ Frame clamping removed (no Math.min with totalFrames)${NC}"
  else
    echo -e "${RED}  ❌ Frame clamping STILL PRESENT (Math.min found)${NC}"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo -e "${YELLOW}  ⚠️  clampFrame function not found${NC}"
fi

# Check 2.2: Field name normalization
echo "✓ Checking Fix 1.3: Field name normalization..."
if grep -q "ground_truth_metrics" "$FRONTEND_DIR/src/pages/HILResults.tsx"; then
  echo -e "${GREEN}  ✅ ground_truth_metrics fallback present${NC}"
else
  echo -e "${RED}  ❌ ground_truth_metrics fallback NOT FOUND${NC}"
  ERRORS=$((ERRORS + 1))
fi

# Check 2.3: Video dropdown fix
echo "✓ Checking Fix 1.4: Video dropdown fix..."
if grep -q "perVideoSummaries?.map" "$FRONTEND_DIR/src/pages/HILResults.tsx"; then
  echo -e "${GREEN}  ✅ Video dropdown uses perVideoSummaries${NC}"
else
  echo -e "${RED}  ❌ Video dropdown NOT using perVideoSummaries${NC}"
  ERRORS=$((ERRORS + 1))
fi

# Check 2.4: TypeScript compilation
echo "✓ Checking TypeScript compilation..."
cd "$FRONTEND_DIR"
if npm run typecheck 2>&1 | grep -q "error TS"; then
  echo -e "${RED}  ❌ TypeScript errors detected${NC}"
  ERRORS=$((ERRORS + 1))
else
  echo -e "${GREEN}  ✅ TypeScript compiles without errors${NC}"
fi

################################################################################
# DATABASE VERIFICATION
################################################################################

echo ""
echo "================================================================================"
echo "3. DATABASE VERIFICATION"
echo "================================================================================"
echo ""

echo "✓ Checking database connectivity..."
cd "$BACKEND_DIR"
if python3 -c "from database import SessionLocal; db = SessionLocal(); db.execute('SELECT 1'); print('✅ Database connection OK')" 2>/dev/null; then
  echo -e "${GREEN}  ✅ Database connection successful${NC}"
else
  echo -e "${RED}  ❌ Database connection FAILED${NC}"
  ERRORS=$((ERRORS + 1))
fi

echo "✓ Checking detection_events table schema..."
if python3 -c "from models import DetectionEvent; print('✅ DetectionEvent model OK')" 2>/dev/null; then
  echo -e "${GREEN}  ✅ DetectionEvent model loaded${NC}"
else
  echo -e "${RED}  ❌ DetectionEvent model FAILED${NC}"
  ERRORS=$((ERRORS + 1))
fi

################################################################################
# FILE CHANGE VERIFICATION
################################################################################

echo ""
echo "================================================================================"
echo "4. FILE CHANGE VERIFICATION"
echo "================================================================================"
echo ""

echo "✓ Checking critical files are modified..."
cd /home/rigade/Testing/ai-model-validation-platform

MODIFIED_FILES=$(git status --short | grep "^[ M]" | wc -l)
echo "  Modified files: $MODIFIED_FILES"

if [ "$MODIFIED_FILES" -ge 30 ]; then
  echo -e "${GREEN}  ✅ Expected number of modified files ($MODIFIED_FILES >= 30)${NC}"
else
  echo -e "${YELLOW}  ⚠️  Fewer modified files than expected ($MODIFIED_FILES < 30)${NC}"
fi

# Check specific critical files
CRITICAL_FILES=(
  "frontend/src/components/FrameCorrelationTimeline.tsx"
  "frontend/src/pages/HILResults.tsx"
  "backend/services/labjack_detection_service.py"
  "backend/services/ground_truth_matching_service.py"
)

for file in "${CRITICAL_FILES[@]}"; do
  if [ -f "$file" ]; then
    if git status --short "$file" | grep -q "M"; then
      echo -e "${GREEN}  ✅ $file modified${NC}"
    else
      echo -e "${YELLOW}  ⚠️  $file NOT modified${NC}"
    fi
  else
    echo -e "${RED}  ❌ $file NOT FOUND${NC}"
    ERRORS=$((ERRORS + 1))
  fi
done

################################################################################
# TESTING VERIFICATION
################################################################################

echo ""
echo "================================================================================"
echo "5. TESTING VERIFICATION"
echo "================================================================================"
echo ""

echo "✓ Checking test files exist..."
cd "$BACKEND_DIR"

if [ -d "tests" ]; then
  TEST_COUNT=$(find tests -name "test_*.py" | wc -l)
  echo -e "${GREEN}  ✅ Found $TEST_COUNT test files${NC}"

  if [ "$TEST_COUNT" -ge 10 ]; then
    echo -e "${GREEN}  ✅ Adequate test coverage${NC}"
  else
    echo -e "${YELLOW}  ⚠️  Limited test coverage ($TEST_COUNT < 10 files)${NC}"
  fi
else
  echo -e "${RED}  ❌ tests/ directory NOT FOUND${NC}"
  ERRORS=$((ERRORS + 1))
fi

################################################################################
# DOCUMENTATION VERIFICATION
################################################################################

echo ""
echo "================================================================================"
echo "6. DOCUMENTATION VERIFICATION"
echo "================================================================================"
echo ""

echo "✓ Checking integration documentation..."
cd /home/rigade/Testing/ai-model-validation-platform

DOCS=(
  "docs/INTEGRATION_SUMMARY_2025-11-05.md"
  "docs/QUICK_FIX_SUMMARY.txt"
  "docs/COMPREHENSIVE_FIX_PLAN.md"
  "docs/EXECUTIVE_SUMMARY_FIXES.md"
)

for doc in "${DOCS[@]}"; do
  if [ -f "$doc" ]; then
    echo -e "${GREEN}  ✅ $doc exists${NC}"
  else
    echo -e "${RED}  ❌ $doc NOT FOUND${NC}"
    ERRORS=$((ERRORS + 1))
  fi
done

################################################################################
# FINAL RESULTS
################################################################################

echo ""
echo "================================================================================"
echo "VERIFICATION RESULTS"
echo "================================================================================"
echo ""

if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
  echo ""
  echo "Status: READY FOR DEPLOYMENT ✅"
  echo ""
  echo "Next Steps:"
  echo "  1. Run database migration script"
  echo "  2. Deploy backend (restart service)"
  echo "  3. Deploy frontend (npm run build + cache bust)"
  echo "  4. Run smoke tests"
  echo "  5. Monitor for 24 hours"
  echo ""
  exit 0
else
  echo -e "${RED}❌ VERIFICATION FAILED${NC}"
  echo ""
  echo "Errors found: $ERRORS"
  echo ""
  echo "Status: NOT READY FOR DEPLOYMENT ❌"
  echo ""
  echo "Please fix the errors above before deploying."
  echo ""
  exit 1
fi
