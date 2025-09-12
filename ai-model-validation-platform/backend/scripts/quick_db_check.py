#!/usr/bin/env python3
"""
Quick Database Schema Check
Direct inspection of actual database schema vs model definitions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from database import get_database_url

def check_database_schema():
    """Check actual database schema"""
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    print(f"Database URL: {database_url}")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print(f"\nTables found: {tables}")
    
    for table in ['videos', 'detection_events', 'test_sessions']:
        if table in tables:
            print(f"\n=== {table.upper()} TABLE SCHEMA ===")
            columns = inspector.get_columns(table)
            for col in columns:
                print(f"  {col['name']}: {col['type']} (nullable: {col['nullable']})")
        else:
            print(f"\n❌ Table '{table}' NOT FOUND")
    
    # Check if there's data
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"\n{table}: {count} records")
            except Exception as e:
                print(f"\n{table}: Error counting - {e}")

if __name__ == "__main__":
    check_database_schema()