#!/bin/bash

# Fast TypeScript React development server startup script
# Optimized for minimal compilation time and memory usage

set -e

echo "🚀 Starting Fast TypeScript React Development Server..."

# Kill any existing development servers
pkill -f "craco start" 2>/dev/null || true
pkill -f "webpack" 2>/dev/null || true
sleep 1

# Clear TypeScript build info
rm -f tsconfig.tsbuildinfo

# Set environment variables for maximum speed
export SKIP_PREFLIGHT_CHECK=true
export FAST_REFRESH=true
export TSC_COMPILE_ON_ERROR=true
export ESLINT_NO_DEV_ERRORS=true
export DISABLE_ESLINT_PLUGIN=true
export GENERATE_SOURCEMAP=false
export BROWSER=none
export HOST=localhost
export PORT=3000

# Memory optimization
export NODE_OPTIONS="--max-old-space-size=4096 --no-deprecation"

echo "✅ Environment configured for speed"
echo "🔧 TypeScript checking: DISABLED"
echo "🔧 ESLint: DISABLED"  
echo "🔧 Source maps: DISABLED"
echo "🔧 Build optimizations: ENABLED"

# Start the development server
echo "🎯 Starting development server on http://localhost:3000"

# Use node directly with craco for fastest startup
node --max-old-space-size=4096 node_modules/.bin/craco start