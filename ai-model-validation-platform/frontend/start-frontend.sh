#!/bin/bash

# Frontend Startup Script with Proper Configuration
echo "🚀 Starting AI Model Validation Platform Frontend..."

# Set working directory
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Export environment variables
export REACT_APP_API_URL=http://localhost:8000
export REACT_APP_WS_URL=ws://localhost:8000
export REACT_APP_VIDEO_BASE_URL=http://localhost:8000
export REACT_APP_ENVIRONMENT=development
export REACT_APP_DEBUG=true
export GENERATE_SOURCEMAP=false
export SKIP_PREFLIGHT_CHECK=true
export TSC_COMPILE_ON_ERROR=true
export ESLINT_NO_DEV_ERRORS=true
export DISABLE_GPU_CHECK=true
export HOST=0.0.0.0
export PORT=3000

# Clear any cache
rm -rf node_modules/.cache 2>/dev/null

echo "✅ Environment configured for localhost development"
echo "📡 API URL: $REACT_APP_API_URL"
echo "🌐 Frontend URL: http://localhost:3000"

# Start the development server
echo "⏳ Starting development server (this may take 30-60 seconds)..."
npm start