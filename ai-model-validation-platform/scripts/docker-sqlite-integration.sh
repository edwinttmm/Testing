#!/bin/bash

# Docker SQLite Integration Script
# Ensures the working dev_database.db is properly integrated with Docker

set -e

echo "🔄 Docker SQLite Integration Starting..."

# Variables
BACKEND_DIR="/home/user/Testing/ai-model-validation-platform/backend"
DATABASE_FILE="$BACKEND_DIR/dev_database.db"
COMPOSE_FILE="/home/user/Testing/ai-model-validation-platform/docker-compose.yml"
SQLITE_OVERRIDE="/home/user/Testing/ai-model-validation-platform/docker-compose.sqlite.yml"

# Check if database exists
if [ ! -f "$DATABASE_FILE" ]; then
    echo "❌ Error: dev_database.db not found at $DATABASE_FILE"
    exit 1
fi

# Get database info
DB_SIZE=$(ls -lh "$DATABASE_FILE" | awk '{print $5}')
echo "📊 Found working database: $DB_SIZE"

# Check database contents
echo "🔍 Database contents:"
sqlite3 "$DATABASE_FILE" "SELECT 'Projects: ' || COUNT(*) FROM projects; SELECT 'Videos: ' || COUNT(*) FROM videos; SELECT 'Annotations: ' || COUNT(*) FROM ground_truth_objects;" 2>/dev/null || echo "Could not read database contents"

# Ensure proper permissions
echo "🔧 Setting database permissions..."
chmod 664 "$DATABASE_FILE"
chown ${USER}:${USER} "$DATABASE_FILE" 2>/dev/null || echo "Could not change ownership (this is normal in some environments)"

# Create backup before Docker operations
BACKUP_FILE="${DATABASE_FILE}.docker_backup_$(date +%Y%m%d_%H%M%S)"
echo "💾 Creating backup: $BACKUP_FILE"
cp "$DATABASE_FILE" "$BACKUP_FILE"

# Verify Docker compose files exist
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: docker-compose.yml not found"
    exit 1
fi

if [ ! -f "$SQLITE_OVERRIDE" ]; then
    echo "❌ Error: docker-compose.sqlite.yml not found"
    exit 1
fi

echo "✅ Files verified:"
echo "   - Database: $DATABASE_FILE ($DB_SIZE)"
echo "   - Backup: $BACKUP_FILE"
echo "   - Compose: $COMPOSE_FILE"
echo "   - SQLite Override: $SQLITE_OVERRIDE"

# Test database connection
echo "🧪 Testing database connection..."
cd "$BACKEND_DIR"
python3 -c "
import sqlite3
import sys
import os

db_path = './dev_database.db'
if not os.path.exists(db_path):
    print('❌ Database file not accessible')
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table list
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
    tables = [row[0] for row in cursor.fetchall()]
    print(f'📋 Tables found: {len(tables)}')
    
    # Check key tables
    for table in ['projects', 'videos', 'ground_truth_objects']:
        if table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f'   - {table}: {count} records')
        else:
            print(f'   - {table}: not found')
    
    conn.close()
    print('✅ Database connectivity test passed')
    
except Exception as e:
    print(f'❌ Database test failed: {e}')
    sys.exit(1)
" || exit 1

echo "🚀 Integration complete! Ready for Docker deployment."
echo ""
echo "📝 Usage Instructions:"
echo "   1. For development with SQLite (recommended):"
echo "      docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml up"
echo ""
echo "   2. For production with PostgreSQL:"
echo "      docker-compose up"
echo ""
echo "   3. To verify the integration:"
echo "      docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml exec backend python -c \"import database; print('Database OK')\""
echo ""
echo "⚠️  Important: The SQLite database is mounted as a volume, so all changes persist across container restarts."
echo "💾 Backup created at: $BACKUP_FILE"