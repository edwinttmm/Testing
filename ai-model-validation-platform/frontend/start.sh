#!/bin/bash
set -e

echo "Starting React development server..."
echo "Environment: $NODE_ENV"
echo "Host: $HOST"
echo "Port: $PORT"

# Set Docker-specific environment variables
export SKIP_PREFLIGHT_CHECK=true
export GENERATE_SOURCEMAP=false
export DOCKER=true
export DISABLE_GPU_CHECK=true
export TSC_COMPILE_ON_ERROR=true

# Start React app
npm start