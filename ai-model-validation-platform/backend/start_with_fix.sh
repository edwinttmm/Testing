#!/bin/bash
# Startup script with detection fix applied

echo "Starting with ultra-low detection thresholds..."

# Export environment variables to force low thresholds
export DETECTION_DEBUG_MODE=true
export MIN_CONFIDENCE_OVERRIDE=0.01
export YOLO_CONFIDENCE=0.001

# Start the application
if [ -f "main.py" ]; then
    echo "Starting backend with detection fix..."
    python main.py
elif [ -f "docker-compose.yml" ]; then
    echo "Starting with Docker..."
    docker-compose up -d
else
    echo "ERROR: No startup method found"
fi
