#!/bin/bash
# LabJack Hardware Mode Startup Script
# This script starts the backend with LabJack hardware detection enabled

set -e

echo "🚀 Starting AI Model Validation Backend with LabJack Hardware Mode"

# Set working directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Activate virtual environment
source .venv/bin/activate

# Set environment variables for hardware mode
export LABJACK_MOCK_MODE=false
export LABJACK_BRIDGE_HOST=10.255.255.254
export LABJACK_BRIDGE_PORT=8080
export LABJACK_FORCE_HARDWARE_MODE=true
export LABJACK_AUTO_DETECT=true
export PYTHONPATH=/home/rigade/Testing/ai-model-validation-platform/backend:$PYTHONPATH

# Log environment
echo "📋 Environment Configuration:"
echo "  LABJACK_MOCK_MODE=$LABJACK_MOCK_MODE"
echo "  LABJACK_BRIDGE_HOST=$LABJACK_BRIDGE_HOST"
echo "  LABJACK_BRIDGE_PORT=$LABJACK_BRIDGE_PORT"
echo "  LABJACK_FORCE_HARDWARE_MODE=$LABJACK_FORCE_HARDWARE_MODE"

# Check for LabJack hardware
echo "🔍 Hardware Detection:"
python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from services.labjack_service import LabJackService
    from config.labjack_env_config import detect_labjack_availability
    
    print('Checking LabJack availability...')
    availability = detect_labjack_availability()
    print(f'  LJM Library: {availability[\"ljm_library\"]}')
    print(f'  Hardware Connected: {availability[\"hardware_connected\"]}')
    print(f'  Mock Mode Required: {availability[\"mock_mode_required\"]}')
    
    if availability['errors']:
        print('⚠️  Detection Issues:')
        for error in availability['errors']:
            print(f'    - {error}')
            
except Exception as e:
    print(f'❌ Hardware detection failed: {e}')
"

echo ""
echo "🔧 Starting backend server..."
python main.py