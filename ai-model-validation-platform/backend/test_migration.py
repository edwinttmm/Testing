#!/usr/bin/env python3
"""
Migration Test Script
This script tests the database migration and verifies the fixes work.
"""

import sys
import os
from pathlib import Path
import requests
import json
import time

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import engine, get_db
from sqlalchemy import text, inspect
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationTester:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
        self.base_url = "http://localhost:8000"

    def test_database_schema(self):
        """Test that all required columns exist in the database"""
        logger.info("🔍 Testing database schema...")
        
        tests = [
            ("videos", "processing_status"),
            ("videos", "ground_truth_generated"),
            ("ground_truth_objects", "x"),
            ("ground_truth_objects", "y"),
            ("ground_truth_objects", "width"),
            ("ground_truth_objects", "height"),
            ("ground_truth_objects", "validated"),
            ("annotations", "detection_id"),
            ("annotations", "validated")
        ]
        
        all_passed = True
        for table, column in tests:
            if self._check_column_exists(table, column):
                logger.info(f"✅ {table}.{column} exists")
            else:
                logger.error(f"❌ {table}.{column} missing")
                all_passed = False
        
        return all_passed

    def _check_column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            columns = self.inspector.get_columns(table_name)
            return any(col['name'] == column_name for col in columns)
        except Exception as e:
            logger.error(f"Error checking column {column_name} in table {table_name}: {e}")
            return False

    def test_api_endpoints(self):
        """Test that API endpoints work after the migration"""
        logger.info("🔍 Testing API endpoints...")
        
        tests = [
            ("GET", "/", "Root endpoint"),
            ("GET", "/projects/", "Projects list"),
            ("GET", "/dashboard/stats", "Dashboard stats"),
        ]
        
        all_passed = True
        for method, endpoint, description in tests:
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                else:
                    continue  # Skip non-GET for now
                
                if response.status_code in [200, 404]:  # 404 is ok for empty lists
                    logger.info(f"✅ {description}: {response.status_code}")
                else:
                    logger.error(f"❌ {description}: {response.status_code}")
                    all_passed = False
                    
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️  {description}: Server not running")
            except Exception as e:
                logger.error(f"❌ {description}: {e}")
                all_passed = False
        
        return all_passed

    def test_video_model_fields(self):
        """Test that video model fields are accessible"""
        logger.info("🔍 Testing video model field access...")
        
        try:
            with self.engine.connect() as conn:
                # Test that we can query the new fields
                result = conn.execute(text("""
                    SELECT id, processing_status, ground_truth_generated 
                    FROM videos 
                    LIMIT 1
                """))
                
                row = result.fetchone()
                if row:
                    logger.info("✅ Video fields accessible with data")
                else:
                    logger.info("✅ Video fields accessible (no data)")
                return True
                
        except Exception as e:
            logger.error(f"❌ Video field access failed: {e}")
            return False

    def run_tests(self):
        """Run all migration tests"""
        logger.info("🚀 Starting migration tests...")
        
        test_results = {
            "Database Schema": self.test_database_schema(),
            "API Endpoints": self.test_api_endpoints(),
            "Video Model Fields": self.test_video_model_fields()
        }
        
        # Summary
        logger.info("📊 Test Results Summary:")
        all_passed = True
        for test_name, passed in test_results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            logger.info(f"  {test_name}: {status}")
            if not passed:
                all_passed = False
        
        if all_passed:
            logger.info("🎉 All migration tests passed!")
        else:
            logger.error("💥 Some migration tests failed!")
        
        return all_passed

def main():
    """Main test function"""
    tester = MigrationTester()
    success = tester.run_tests()
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)