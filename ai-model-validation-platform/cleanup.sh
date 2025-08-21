#!/bin/bash
echo "🧹 Cleaning up AI Model Validation Platform..."

# Save current directory
ORIGINAL_DIR=$(pwd)
cd "$(dirname "$0")"

echo "📊 Current total size:"
du -sh .

echo ""
echo "🗑️  Removing large unnecessary files..."

# Remove frontend node_modules (biggest space saver)
if [ -d "./frontend/node_modules" ]; then
    echo "  ❌ Removing frontend/node_modules (918MB)..."
    rm -rf ./frontend/node_modules
fi

# Remove Python cache files
echo "  ❌ Removing Python __pycache__ directories..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Remove duplicate virtual environment
if [ -d "./frontend/ai-model-validation-platform/backend/venv" ]; then
    echo "  ❌ Removing duplicate virtual environment..."
    rm -rf ./frontend/ai-model-validation-platform/backend/venv
fi

# Remove test database files
echo "  ❌ Removing test database files..."
rm -f ./backend/test_database.db 2>/dev/null || true
rm -f ./test_database.db 2>/dev/null || true

# Remove Claude Flow cache/memory files
echo "  ❌ Removing Claude Flow cache files..."
find . -name ".swarm" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".hive-mind" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove build artifacts
if [ -d "./frontend/build" ]; then
    echo "  ❌ Removing frontend build directory..."
    rm -rf ./frontend/build
fi

echo ""
echo "📊 New total size:"
du -sh .

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📝 To restore functionality:"
echo "   1. Reinstall frontend dependencies: cd frontend && npm install"
echo "   2. Rebuild if needed: npm run build"

# Return to original directory
cd "$ORIGINAL_DIR"