#!/bin/bash
# Option C Import Path Fix Script
# This script fixes the import error preventing temporal expansion from working

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_FILE="$BACKEND_DIR/src/services/ground_truth_matching_service.py"

echo "=========================================="
echo "Option C Import Path Fix"
echo "=========================================="
echo ""
echo "Backend directory: $BACKEND_DIR"
echo "Target file: $SERVICE_FILE"
echo ""

# Check if file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ ERROR: File not found: $SERVICE_FILE"
    exit 1
fi

# Backup original file
BACKUP_FILE="${SERVICE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "📦 Creating backup: $BACKUP_FILE"
cp "$SERVICE_FILE" "$BACKUP_FILE"

# Fix import statement (Line 31)
echo "🔧 Fixing import statement..."
sed -i 's/^from services\.temporal_expansion import/from src.services.temporal_expansion import/' "$SERVICE_FILE"

# Verify change
if grep -q "from src.services.temporal_expansion import" "$SERVICE_FILE"; then
    echo "✅ Import statement fixed successfully"
else
    echo "❌ ERROR: Import fix failed, restoring backup"
    mv "$BACKUP_FILE" "$SERVICE_FILE"
    exit 1
fi

# Clear Python cache
echo "🧹 Clearing Python cache..."
cd "$BACKEND_DIR"
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Verify import works
echo "🧪 Testing import..."
cd "$BACKEND_DIR"
if python3 -c "from src.services.ground_truth_matching_service import GroundTruthMatchingService; from src.services.temporal_expansion import expand_detections_temporally; print('✅ Import test passed')" 2>&1; then
    echo ""
    echo "=========================================="
    echo "✅ FIX APPLIED SUCCESSFULLY"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Restart backend service:"
    echo "   sudo systemctl restart ai-model-validation-backend"
    echo "   (or your deployment method)"
    echo ""
    echo "2. Monitor logs for temporal expansion activity:"
    echo "   tail -f /var/log/ai-model-validation/backend.log | grep -i 'temporal expansion'"
    echo ""
    echo "3. Verify recall improves from 0% to >50%"
    echo ""
    echo "Backup saved to: $BACKUP_FILE"
    echo ""
else
    echo "❌ ERROR: Import test failed"
    echo "Restoring backup..."
    mv "$BACKUP_FILE" "$SERVICE_FILE"
    exit 1
fi
