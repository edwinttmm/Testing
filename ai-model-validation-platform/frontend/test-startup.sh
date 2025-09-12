#!/bin/bash

# Frontend startup test script
set -e

echo "🔧 Frontend Startup Testing Script"
echo "=================================="

# Set environment variables
export SKIP_PREFLIGHT_CHECK=true
export DISABLE_GPU_CHECK=true
export TSC_COMPILE_ON_ERROR=true
export GENERATE_SOURCEMAP=false
export NODE_OPTIONS="--max-old-space-size=4096"

# Check port 3000
echo "📡 Checking port 3000 availability..."
if lsof -i :3000 >/dev/null 2>&1; then
    echo "⚠️  Port 3000 is in use. Killing processes..."
    pkill -f "port.*3000" || true
    sleep 3
fi

# Clean any hanging webpack processes
echo "🧹 Cleaning hanging processes..."
pkill -f "webpack\|craco" || true
sleep 2

# Check dependencies
echo "📦 Checking React dependencies..."
npm list react react-dom @craco/craco --depth=0

# Run TypeScript check
echo "🔍 Running TypeScript check..."
npm run typecheck

# Quick lint check (non-blocking)
echo "🧹 Running lint check..."
npm run lint:dev --max-warnings=100 || echo "⚠️  Linting warnings exist but continuing..."

# Try to start the server with timeout
echo "🚀 Starting frontend server..."
echo "Logs will appear below (press Ctrl+C to stop):"

# Start server and capture output
timeout 60s npm start &
SERVER_PID=$!

# Wait for server to be ready or timeout
echo "⏱️  Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:3000/health >/dev/null 2>&1; then
        echo "✅ Server is responding on port 3000!"
        break
    fi
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "❌ Server process died"
        exit 1
    fi
    echo "⏳ Waiting... ($i/30)"
    sleep 2
done

# Check if server is responding
if curl -s http://localhost:3000/health >/dev/null 2>&1; then
    echo "✅ Frontend startup successful!"
    echo "📊 Health check response:"
    curl -s http://localhost:3000/health | jq '.' || echo "JSON parse failed"
    
    # Cleanup
    echo "🧹 Cleaning up test server..."
    kill $SERVER_PID 2>/dev/null || true
    sleep 2
    
    echo "✅ All tests passed! Frontend is ready for development."
    exit 0
else
    echo "❌ Server failed to respond after 60 seconds"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi