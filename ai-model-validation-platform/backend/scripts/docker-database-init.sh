#!/bin/bash
set -e

echo "🔧 Docker Database Initialization Script"
echo "========================================"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Database configuration
DB_FILE="/app/dev_database.db"
DB_BACKUP="/app/dev_database.db.backup"
HOST_DB_FILE="/app/backend/dev_database.db"

log "Starting database connectivity fix..."

# 1. Create necessary directories
log "Creating directories..."
mkdir -p /app/data
mkdir -p /app/logs
chmod 755 /app/data /app/logs

# 2. Handle database file mounting and permissions
log "Checking database file accessibility..."

# Check if database file is properly mounted
if [ ! -f "$DB_FILE" ]; then
    log "❌ Database file not found at $DB_FILE"
    
    # Try to find database file in various locations
    if [ -f "$HOST_DB_FILE" ]; then
        log "📁 Found database at $HOST_DB_FILE, creating symlink..."
        ln -sf "$HOST_DB_FILE" "$DB_FILE"
    elif [ -f "/app/backend/dev_database.db" ]; then
        log "📁 Found database in backend directory, creating symlink..."
        ln -sf "/app/backend/dev_database.db" "$DB_FILE"
    else
        log "⚠️  No existing database found, will create new one..."
        # Create empty database file with proper permissions
        touch "$DB_FILE"
        chmod 664 "$DB_FILE"
    fi
else
    log "✅ Database file found at $DB_FILE"
fi

# 3. Fix file permissions
log "Setting file permissions..."
if [ -f "$DB_FILE" ]; then
    # Ensure database file has correct permissions
    chmod 664 "$DB_FILE"
    log "✅ Set database file permissions to 664"
    
    # Test database accessibility
    if sqlite3 "$DB_FILE" ".tables" > /dev/null 2>&1; then
        log "✅ Database file is readable and valid"
        
        # Show database info
        TABLE_COUNT=$(sqlite3 "$DB_FILE" "SELECT count(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
        log "📊 Database contains $TABLE_COUNT tables"
        
        if [ "$TABLE_COUNT" -gt 0 ]; then
            log "📋 Tables: $(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table';" | tr '\n' ' ')"
        fi
    else
        log "⚠️  Database file exists but may be corrupted"
    fi
else
    log "❌ Failed to create/access database file"
    exit 1
fi

# 4. Set up Python path and database connection
log "Setting up Python environment..."
cd /app
export PYTHONPATH="/app:$PYTHONPATH"

# Ensure config is available
if [ ! -f "/app/config.py" ]; then
    log "❌ config.py not found in /app"
    ls -la /app/ | head -20
    exit 1
fi

# 5. Test database connection with Python
log "Testing Python database connection..."
cat > /tmp/test_db_connection.py << 'EOF'
import os
import sys
import sqlite3
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, '/app')

def test_sqlite_direct():
    """Test direct SQLite connection"""
    try:
        db_path = "/app/dev_database.db"
        print(f"Testing direct SQLite connection to: {db_path}")
        print(f"File exists: {Path(db_path).exists()}")
        print(f"File size: {Path(db_path).stat().st_size if Path(db_path).exists() else 'N/A'} bytes")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"✅ Direct SQLite connection successful")
        print(f"📋 Tables: {[table[0] for table in tables]}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Direct SQLite connection failed: {e}")
        return False

def test_app_database():
    """Test application database connection"""
    try:
        from database import engine, get_db
        from sqlalchemy import text
        
        print("Testing application database connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            print(f"✅ Application database connection successful: {result}")
            
        # Test database session
        db_gen = get_db()
        db = next(db_gen)
        try:
            result = db.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")).scalar()
            print(f"✅ Database session test successful, table count: {result}")
        finally:
            db.close()
        
        return True
    except Exception as e:
        print(f"❌ Application database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Database Connectivity Test")
    print("=" * 40)
    
    # Test 1: Direct SQLite
    sqlite_ok = test_sqlite_direct()
    print()
    
    # Test 2: Application database
    app_db_ok = test_app_database()
    print()
    
    if sqlite_ok and app_db_ok:
        print("🎉 ALL DATABASE TESTS PASSED!")
        sys.exit(0)
    else:
        print("❌ Some database tests failed")
        sys.exit(1)
EOF

python /tmp/test_db_connection.py
DB_TEST_RESULT=$?

if [ $DB_TEST_RESULT -eq 0 ]; then
    log "🎉 Database connectivity test PASSED!"
else
    log "❌ Database connectivity test FAILED!"
    exit 1
fi

# 6. Final verification
log "Running final verification..."
log "✅ Database file: $(ls -la "$DB_FILE" 2>/dev/null || echo 'Not found')"
log "✅ Working directory: $(pwd)"
log "✅ Python path: $PYTHONPATH"
log "✅ Environment variables:"
env | grep -E "(DATABASE|AIVALIDATION)" | while read var; do
    log "   $var"
done

log "🎉 Docker database initialization completed successfully!"