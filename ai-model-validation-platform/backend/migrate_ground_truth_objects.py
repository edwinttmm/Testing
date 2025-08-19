#!/usr/bin/env python3
"""
Add new columns to ground_truth_objects table for better annotation support
"""
import sys
from database import engine
from sqlalchemy import text

def migrate_ground_truth_objects():
    """Add new columns to ground_truth_objects table"""
    try:
        with engine.connect() as connection:
            # List of new columns to add
            new_columns = [
                ("frame_number", "INTEGER"),
                ("x", "REAL DEFAULT 0"),
                ("y", "REAL DEFAULT 0"), 
                ("width", "REAL DEFAULT 0"),
                ("height", "REAL DEFAULT 0"),
                ("validated", "BOOLEAN DEFAULT 0"),
                ("difficult", "BOOLEAN DEFAULT 0")
            ]
            
            for column_name, column_type in new_columns:
                # Check if column already exists
                result = connection.execute(text(f"""
                    SELECT COUNT(*) as count 
                    FROM pragma_table_info('ground_truth_objects') 
                    WHERE name='{column_name}'
                """))
                
                count = result.fetchone()[0]
                
                if count == 0:
                    print(f"📝 Adding {column_name} column to ground_truth_objects table...")
                    connection.execute(text(f"""
                        ALTER TABLE ground_truth_objects 
                        ADD COLUMN {column_name} {column_type}
                    """))
                    connection.commit()
                    print(f"✅ Successfully added {column_name} column")
                else:
                    print(f"ℹ️  {column_name} column already exists")
            
            # Migrate existing bounding_box JSON data to individual columns
            print("📝 Migrating existing bounding box data...")
            connection.execute(text("""
                UPDATE ground_truth_objects 
                SET 
                    x = CAST(json_extract(bounding_box, '$.x') AS REAL),
                    y = CAST(json_extract(bounding_box, '$.y') AS REAL),
                    width = CAST(json_extract(bounding_box, '$.width') AS REAL),
                    height = CAST(json_extract(bounding_box, '$.height') AS REAL),
                    validated = 1  -- Mark existing detections as validated
                WHERE bounding_box IS NOT NULL 
                AND x IS NULL
            """))
            connection.commit()
            print("✅ Migrated existing bounding box data")
            
    except Exception as e:
        print(f"❌ Error migrating ground_truth_objects table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_ground_truth_objects()
    print("🎉 Ground truth objects migration completed successfully!")