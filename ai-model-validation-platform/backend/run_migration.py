#!/usr/bin/env python3
"""
Migration Runner Script
This script runs the database migration to fix schema issues.
"""

import sys
import os
from pathlib import Path
import subprocess

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def main():
    """Run migration with proper error handling"""
    print("🚀 AI Model Validation Platform - Database Migration")
    print("=" * 50)
    
    try:
        # Run the migration script
        migration_script = backend_dir / "migrations" / "add_missing_columns.py"
        
        if not migration_script.exists():
            print("❌ Migration script not found!")
            return False
        
        print("🔄 Running database migration...")
        result = subprocess.run([sys.executable, str(migration_script)], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Migration completed successfully!")
            print(result.stdout)
            return True
        else:
            print("❌ Migration failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"💥 Error running migration: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)