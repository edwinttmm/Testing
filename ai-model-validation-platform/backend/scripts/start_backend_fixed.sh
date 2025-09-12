#!/bin/bash

# AI Model Validation Platform - Fixed Backend Startup Script
# This script ensures proper database connection and backend startup

set -e  # Exit on any error

echo "🚀 Starting AI Model Validation Platform Backend with Database Connection Fix"
echo "============================================================================"

# Change to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Load environment variables
source .env 2>/dev/null || echo "⚠️  No .env file found, using defaults"

# Set critical environment variables
export DATABASE_URL="postgresql://postgres:password@localhost:5432/aivalidation"
export AIVALIDATION_DATABASE_URL="postgresql://postgres:password@localhost:5432/aivalidation"
export CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
export LOG_LEVEL="DEBUG"

echo "📊 Environment Configuration:"
echo "   - Database: $DATABASE_URL"
echo "   - CORS Origins: $CORS_ORIGINS"
echo "   - Log Level: $LOG_LEVEL"

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Test database connection
echo "🔍 Testing database connection..."
python3 -c "
from database import get_database_health
import json
health = get_database_health()
if health['status'] == 'healthy':
    print('✅ Database connection successful!')
    print(f'   - Status: {health[\"status\"]}')
    print(f'   - Pool size: {health.get(\"pool_size\", \"N/A\")}')
else:
    print('❌ Database connection failed!')
    print(json.dumps(health, indent=2))
    exit(1)
"

# Initialize database tables if needed
echo "🗄️  Initializing database schema..."
python3 -c "
from database import engine, Base
from models import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info('Database schema initialization complete!')
except Exception as e:
    logger.error(f'Database schema error: {e}')
    exit(1)
"

# Kill existing server if running
echo "🔄 Stopping any existing backend servers..."
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 2

# Start the backend server
echo "🌟 Starting backend server on http://localhost:8000"
echo "   - Health check: http://localhost:8000/health"
echo "   - API docs: http://localhost:8000/docs"
echo "   - Projects API: http://localhost:8000/api/projects"
echo ""

# Run the server with proper configuration
python3 -m uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir . \
    --log-level debug \
    --access-log

echo "Backend startup complete!"