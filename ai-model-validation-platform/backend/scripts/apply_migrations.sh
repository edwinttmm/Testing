#!/bin/bash
# Apply new database migrations
#
# This script applies the new migrations for:
# 1. frontend_playing_delay_ms field
# 2. evaluation_details dual-evaluation field
#
# Usage: ./apply_migrations.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "Database Migration Application"
echo "========================================"
echo ""
echo "Backend directory: $BACKEND_DIR"
echo ""

cd "$BACKEND_DIR"

# Check if alembic is available
if ! command -v alembic &> /dev/null; then
    echo "❌ Alembic not found. Installing..."
    pip install alembic
fi

# Show current revision
echo "Current database revision:"
alembic current || echo "⚠️  No current revision (database not initialized)"
echo ""

# Show available migrations
echo "Available migrations:"
alembic history | head -20
echo ""

# Apply migrations
echo "Applying migrations..."
alembic upgrade head

echo ""
echo "✅ Migrations applied successfully!"
echo ""

# Show new revision
echo "New database revision:"
alembic current
echo ""

# Run verification test
echo "========================================"
echo "Running verification tests..."
echo "========================================"
echo ""

python3 scripts/test_new_migrations.py

echo ""
echo "✅ Migration application complete!"
