#!/bin/bash

echo "🚀 Starting AI Model Validation Platform Backend..."
echo "=================================================="

# Check if Python and required modules are available
python -c "import fastapi, uvicorn, jwt, passlib" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Required dependencies not found. Please check installation."
    exit 1
fi

echo "✅ Dependencies verified"
echo "✅ Starting server on http://localhost:8000"
echo "✅ API documentation available at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================================="

# Start the server
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload