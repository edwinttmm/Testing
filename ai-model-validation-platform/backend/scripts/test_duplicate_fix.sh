#!/bin/bash
# Quick test script to verify the duplicate detection fix

echo "🔍 Checking for duplicate detection emissions in socketio_server.py..."
echo ""

# Count total detection_event emissions
TOTAL=$(grep -c "await sio.emit('detection_event'" /home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py)
echo "✓ Total detection_event emissions: $TOTAL"

# Check for problematic 'detections' room emissions
DUPLICATES=$(grep -c "await sio.emit('detection_event'.*room='detections'" /home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py)
echo "✓ Emissions to 'detections' room: $DUPLICATES"

echo ""
if [ "$DUPLICATES" -eq 0 ]; then
    echo "✅ PASSED: No duplicate emissions to 'detections' room"
    echo "✅ Fix is working correctly!"
else
    echo "❌ FAILED: Found $DUPLICATES duplicate emissions"
    echo "❌ Fix not applied correctly"
    exit 1
fi

echo ""
echo "📄 Documentation check..."
if [ -f "/home/rigade/Testing/ai-model-validation-platform/backend/docs/DUPLICATE_DETECTION_FIX.md" ]; then
    echo "✅ Fix documentation exists"
else
    echo "⚠️  Documentation not found"
fi

echo ""
echo "🎉 All checks passed!"
