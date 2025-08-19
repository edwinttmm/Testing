#!/usr/bin/env python3
"""
Add processing_status column to videos table
"""
import sys
from database import engine
from sqlalchemy import text

def add_processing_status_column():
    """Add processing_status column to videos table"""
    try:
        with engine.connect() as connection:
            # Check if column already exists
            result = connection.execute(text("""
                SELECT COUNT(*) as count 
                FROM pragma_table_info('videos') 
                WHERE name='processing_status'
            """))
            
            count = result.fetchone()[0]
            
            if count == 0:
                print("📝 Adding processing_status column to videos table...")
                connection.execute(text("""
                    ALTER TABLE videos 
                    ADD COLUMN processing_status VARCHAR DEFAULT 'pending'
                """))
                connection.commit()
                print("✅ Successfully added processing_status column")
            else:
                print("ℹ️  processing_status column already exists")
                
            # Update existing videos to have proper status
            print("📝 Updating existing videos...")
            connection.execute(text("""
                UPDATE videos 
                SET processing_status = CASE 
                    WHEN ground_truth_generated = 1 THEN 'completed'
                    WHEN status = 'processing' THEN 'processing'
                    ELSE 'pending'
                END
                WHERE processing_status = 'pending'
            """))
            connection.commit()
            print("✅ Updated existing video processing statuses")
            
    except Exception as e:
        print(f"❌ Error adding processing_status column: {e}")
        sys.exit(1)

if __name__ == "__main__":
    add_processing_status_column()
    print("🎉 Migration completed successfully!")