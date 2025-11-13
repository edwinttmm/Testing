#!/bin/bash

# Quick Start Script for Frontend with Process Management
# Combines cleanup, recovery, and startup in one command

FRONTEND_DIR="/home/rigade/Testing/ai-model-validation-platform/frontend"
SCRIPTS_DIR="$FRONTEND_DIR/scripts"

echo "🚀 Quick Start - Frontend Development Server"
echo "============================================"

cd "$FRONTEND_DIR" || exit 1

echo "Step 1: Process cleanup..."
if "$SCRIPTS_DIR/process-cleanup.sh"; then
    echo "✅ Cleanup successful"
else
    echo "⚠️  Cleanup encountered issues, proceeding..."
fi

echo ""
echo "Step 2: Starting frontend with monitoring..."

# Set optimal environment variables
export ESLINT_NO_DEV_ERRORS=true
export TSC_COMPILE_ON_ERROR=true
export SKIP_PREFLIGHT_CHECK=true
export GENERATE_SOURCEMAP=false
export FAST_REFRESH=false
export NODE_OPTIONS="--max-old-space-size=2048"

# Start with process monitor
"$SCRIPTS_DIR/process-monitor.sh" start

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Frontend started successfully!"
    echo "   - Access at: http://localhost:3000"
    echo "   - Monitor with: $SCRIPTS_DIR/process-monitor.sh status"
    echo "   - Stop with: $SCRIPTS_DIR/process-monitor.sh stop"
    echo ""
    echo "Available commands:"
    echo "   ./scripts/process-monitor.sh {start|stop|restart|status|health|monitor|cleanup}"
    echo "   ./scripts/startup-recovery.sh  # For failed startups"
    echo "   ./scripts/process-cleanup.sh   # For manual cleanup"
else
    echo ""
    echo "❌ Frontend startup failed. Attempting recovery..."
    "$SCRIPTS_DIR/startup-recovery.sh"
fi