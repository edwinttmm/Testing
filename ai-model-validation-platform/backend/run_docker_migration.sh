#!/bin/bash
# Fix detection_events table schema in Docker container

echo "🔧 FIXING DATABASE SCHEMA IN DOCKER CONTAINER"
echo "=============================================="

# Method 1: Run migration directly in Docker container
echo "📝 Method 1: Direct Docker execution"
docker exec -i $(docker ps -q --filter ancestor=ai-model-validation-platform-backend) python - << 'EOF'
import os
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Use environment variables from container
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@db:5432/ai_validation')
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Add missing detection_id column
        conn.execute(text("""
            ALTER TABLE detection_events 
            ADD COLUMN IF NOT EXISTS detection_id VARCHAR(36);
        """))
        
        # Add index for performance
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_detection_events_detection_id 
            ON detection_events(detection_id);
        """))
        
        conn.commit()
        
        # Verify
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'detection_events' AND column_name = 'detection_id';
        """))
        
        if result.fetchone():
            logger.info("✅ SUCCESS: detection_id column added!")
        else:
            logger.error("❌ FAILED: detection_id column not found")
            
except Exception as e:
    logger.error(f"❌ Error: {e}")
EOF

echo ""
echo "📝 Method 2: Manual SQL execution (if Method 1 fails)"
echo "Run this command in your Docker environment:"
echo ""
echo "docker exec -i \$(docker ps -q --filter ancestor=ai-model-validation-platform-backend) psql \$DATABASE_URL << 'EOF'"
echo "ALTER TABLE detection_events ADD COLUMN IF NOT EXISTS detection_id VARCHAR(36);"
echo "CREATE INDEX IF NOT EXISTS idx_detection_events_detection_id ON detection_events(detection_id);"
echo "\\d detection_events"
echo "EOF"

echo ""
echo "📝 Method 3: Database container direct access"
echo "docker exec -it \$(docker ps -q --filter ancestor=postgres) psql -U postgres -d ai_validation"
echo "Then run:"
echo "ALTER TABLE detection_events ADD COLUMN IF NOT EXISTS detection_id VARCHAR(36);"

echo ""
echo "🚀 After running the migration, restart your backend container:"
echo "docker restart \$(docker ps -q --filter ancestor=ai-model-validation-platform-backend)"