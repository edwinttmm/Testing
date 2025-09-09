#!/bin/bash

# Backend startup script for AI Model Validation Platform
echo "Starting AI Model Validation Platform Backend..."

# Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Activate virtual environment
source .venv/bin/activate

# Set database URL if not already set
export DATABASE_URL=${DATABASE_URL:-"sqlite:///./test_database.db"}
export VRU_DATABASE_URL=${VRU_DATABASE_URL:-"sqlite:///./test_database.db"}

# Kill any existing process on port 8000
echo "Checking for existing processes on port 8000..."
fuser -k 8000/tcp 2>/dev/null || true
sleep 2

# Start the backend server using uvicorn (NOT python main.py)
echo "Starting backend server on http://localhost:8000"
echo "Database: $DATABASE_URL"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
