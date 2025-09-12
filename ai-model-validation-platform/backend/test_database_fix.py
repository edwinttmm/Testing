#!/usr/bin/env python3
"""
Database connectivity fix and test
"""
import os
import sys

# Set environment variables
os.environ['DATABASE_URL'] = 'sqlite:///./dev_database.db'
os.environ['VRU_DATABASE_URL'] = 'sqlite:///./dev_database.db'
os.environ['AIVALIDATION_DATABASE_URL'] = 'sqlite:///./dev_database.db'

# Test database
from database import get_database_health, engine, Base
from models import Project, Video

print("=== Database Fix and Test ===")
print(f"Database URL: {os.environ.get('DATABASE_URL')}")

# Test connectivity
health = get_database_health()
print(f"Database Health: {health}")

if health.get('status') == 'healthy':
    print("✅ Database connection working!")
    
    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        
else:
    print("❌ Database connection failed!")
    sys.exit(1)