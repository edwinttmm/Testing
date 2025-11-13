#!/bin/bash
# Rollback new database migrations
#
# This script rolls back the migrations to before the dual-evaluation changes.
# Use this if you need to revert the schema changes.
#
# Usage: ./rollback_migrations.sh [steps]
#   steps: Number of migrations to rollback (default: 2 for both new migrations)

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
STEPS="${1:-2}"  # Default to rolling back 2 migrations

echo "========================================"
echo "Database Migration Rollback"
echo "========================================"
echo ""
echo "Backend directory: $BACKEND_DIR"
echo "Rolling back: $STEPS migration(s)"
echo ""

cd "$BACKEND_DIR"

# Show current revision
echo "Current database revision:"
alembic current
echo ""

# Confirm rollback
read -p "Are you sure you want to rollback $STEPS migration(s)? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled."
    exit 1
fi

# Perform rollback
echo "Rolling back migrations..."

if [ "$STEPS" -eq 2 ]; then
    # Rollback both new migrations
    alembic downgrade -2
elif [ "$STEPS" -eq 1 ]; then
    # Rollback just the dual-evaluation migration
    alembic downgrade -1
else
    # Custom rollback
    alembic downgrade -"$STEPS"
fi

echo ""
echo "✅ Rollback complete!"
echo ""

# Show new revision
echo "Current database revision after rollback:"
alembic current
echo ""

# Run verification test
echo "========================================"
echo "Running verification tests..."
echo "========================================"
echo ""

python3 scripts/test_new_migrations.py

echo ""
echo "✅ Rollback verification complete!"
