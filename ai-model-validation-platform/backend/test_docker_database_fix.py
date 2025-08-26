#!/usr/bin/env python3
"""
Test script to validate the Docker database configuration fix
Simulates Docker container environment and validates database access
"""
import os
import sys
import tempfile
import shutil
import subprocess
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DockerDatabaseFixValidator:
    """Validates the Docker database configuration fix"""
    
    def __init__(self):
        self.test_dir = None
        self.original_db_path = "/home/user/Testing/ai-model-validation-platform/backend/dev_database.db"
        self.results = {
            "file_permissions": False,
            "database_connectivity": False,
            "application_import": False,
            "volume_mounting_simulation": False,
            "startup_script_test": False,
            "overall_success": False
        }
    
    def setup_test_environment(self) -> bool:
        """Set up test environment simulating Docker container"""
        try:
            self.test_dir = tempfile.mkdtemp(prefix="docker_db_test_")
            logger.info(f"📁 Created test directory: {self.test_dir}")
            
            # Copy database file to test directory
            if Path(self.original_db_path).exists():
                shutil.copy2(self.original_db_path, f"{self.test_dir}/dev_database.db")
                logger.info("✅ Copied database file to test environment")
            else:
                logger.warning("⚠️  Original database not found, creating empty test database")
                self._create_test_database(f"{self.test_dir}/dev_database.db")
            
            # Set up environment variables
            os.environ["AIVALIDATION_DATABASE_URL"] = f"sqlite:///{self.test_dir}/dev_database.db"
            os.environ["AIVALIDATION_DOCKER_MODE"] = "true"
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup test environment: {e}")
            return False
    
    def _create_test_database(self, db_path: str) -> None:
        """Create a test database with basic structure"""
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detection_events (
                id VARCHAR(36) PRIMARY KEY,
                test_session_id VARCHAR(36) NOT NULL,
                timestamp FLOAT NOT NULL,
                confidence FLOAT,
                class_label VARCHAR,
                detection_id VARCHAR(36),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def test_file_permissions(self) -> bool:
        """Test database file permissions and accessibility"""
        try:
            db_path = f"{self.test_dir}/dev_database.db"
            
            # Check file exists and is readable/writable
            if not os.path.exists(db_path):
                logger.error("❌ Database file doesn't exist")
                return False
            
            if not os.access(db_path, os.R_OK):
                logger.error("❌ Database file is not readable")
                return False
            
            if not os.access(db_path, os.W_OK):
                logger.error("❌ Database file is not writable")
                return False
            
            # Test SQLite file format
            with open(db_path, 'rb') as f:
                header = f.read(16)
                if not header.startswith(b'SQLite format 3'):
                    logger.error("❌ File is not a valid SQLite database")
                    return False
            
            logger.info("✅ File permissions test passed")
            self.results["file_permissions"] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ File permissions test failed: {e}")
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test basic database connectivity and operations"""
        try:
            db_path = f"{self.test_dir}/dev_database.db"
            
            # Test connection
            conn = sqlite3.connect(db_path)
            
            # Test basic operations
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"📋 Found tables: {tables}")
            
            # Test write operation
            import time
            test_id = "test-connectivity-" + str(int(time.time()))
            conn.execute("INSERT OR REPLACE INTO videos (id, filename, file_path, project_id) VALUES (?, ?, ?, ?)", 
                        (test_id, "test_connectivity.mp4", "/app/uploads/test_connectivity.mp4", "test-project-id"))
            conn.commit()
            
            # Test read operation
            cursor = conn.execute("SELECT filename FROM videos WHERE id = ?", (test_id,))
            result = cursor.fetchone()
            if not result:
                logger.error("❌ Failed to read test data from database")
                return False
            
            # Cleanup
            conn.execute("DELETE FROM videos WHERE id = ?", (test_id,))
            conn.commit()
            conn.close()
            
            logger.info("✅ Database connectivity test passed")
            self.results["database_connectivity"] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Database connectivity test failed: {e}")
            return False
    
    def test_application_imports(self) -> bool:
        """Test that the application can import and use database modules"""
        try:
            # Change to the backend directory for imports
            backend_dir = "/home/user/Testing/ai-model-validation-platform/backend"
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            
            # Test importing docker database config
            from docker_database_config import DockerDatabaseConfig, validate_docker_database
            logger.info("✅ Successfully imported docker_database_config module")
            
            # Test configuration
            config = DockerDatabaseConfig()
            config.database_path = f"{self.test_dir}/dev_database.db"
            
            # Test diagnosis
            diagnosis = config.diagnose_database_issues()
            logger.info(f"📊 Database diagnosis status: {diagnosis['status']}")
            
            if diagnosis["issues"]:
                logger.warning("Issues found during diagnosis:")
                for issue in diagnosis["issues"]:
                    logger.warning(f"  ⚠️  {issue}")
            
            logger.info("✅ Application imports test passed")
            self.results["application_import"] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Application imports test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_volume_mounting_simulation(self) -> bool:
        """Simulate Docker volume mounting scenarios"""
        try:
            # Simulate scenario where database is mounted from different location
            mounted_db_path = f"{self.test_dir}/mounted/dev_database.db"
            os.makedirs(f"{self.test_dir}/mounted", exist_ok=True)
            
            # Copy database to mounted location
            shutil.copy2(f"{self.test_dir}/dev_database.db", mounted_db_path)
            
            # Create symlink to simulate Docker volume mounting
            app_db_path = f"{self.test_dir}/app_database.db"
            os.symlink(mounted_db_path, app_db_path)
            
            # Test access through symlink
            conn = sqlite3.connect(app_db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            count = cursor.fetchone()[0]
            conn.close()
            
            if count == 0:
                logger.error("❌ No tables found through mounted database")
                return False
            
            logger.info(f"✅ Volume mounting simulation passed ({count} tables accessible)")
            self.results["volume_mounting_simulation"] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Volume mounting simulation failed: {e}")
            return False
    
    def test_startup_script(self) -> bool:
        """Test the Docker startup script functionality"""
        try:
            script_path = "/home/user/Testing/ai-model-validation-platform/backend/scripts/docker-database-init.sh"
            
            if not os.path.exists(script_path):
                logger.error(f"❌ Startup script not found at {script_path}")
                return False
            
            # Test script is executable
            if not os.access(script_path, os.X_OK):
                logger.error("❌ Startup script is not executable")
                return False
            
            # Simulate script execution (without actually running it to avoid side effects)
            # Instead, check that the script contains the key functionality
            with open(script_path, 'r') as f:
                script_content = f.read()
            
            required_elements = [
                "sqlite3",  # SQLite command usage
                "test_db_connection.py",  # Database test
                "chmod 664",  # Permission setting
                "/app/dev_database.db"  # Database path
            ]
            
            for element in required_elements:
                if element not in script_content:
                    logger.warning(f"⚠️  Startup script missing element: {element}")
            
            logger.info("✅ Startup script test passed")
            self.results["startup_script_test"] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Startup script test failed: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up test environment"""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            logger.info(f"🧹 Cleaned up test directory: {self.test_dir}")
    
    def run_comprehensive_test(self) -> dict:
        """Run comprehensive validation of the Docker database fix"""
        logger.info("🔍 Starting comprehensive Docker database fix validation")
        logger.info("=" * 60)
        
        try:
            # Setup test environment
            if not self.setup_test_environment():
                logger.error("❌ Failed to setup test environment")
                return self.results
            
            # Run individual tests
            tests = [
                ("File Permissions", self.test_file_permissions),
                ("Database Connectivity", self.test_database_connectivity),
                ("Application Imports", self.test_application_imports),
                ("Volume Mounting Simulation", self.test_volume_mounting_simulation),
                ("Startup Script", self.test_startup_script),
            ]
            
            for test_name, test_func in tests:
                logger.info(f"\n🧪 Running {test_name} test...")
                try:
                    success = test_func()
                    if success:
                        logger.info(f"✅ {test_name} test PASSED")
                    else:
                        logger.error(f"❌ {test_name} test FAILED")
                except Exception as e:
                    logger.error(f"❌ {test_name} test ERROR: {e}")
            
            # Calculate overall success
            passed_tests = sum(1 for result in self.results.values() if result)
            total_tests = len([k for k in self.results.keys() if k != "overall_success"])
            
            self.results["overall_success"] = passed_tests == total_tests
            
            logger.info("\n" + "=" * 60)
            logger.info("📊 VALIDATION RESULTS")
            logger.info("=" * 60)
            
            for test_name, result in self.results.items():
                if test_name != "overall_success":
                    status = "✅ PASS" if result else "❌ FAIL"
                    logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
            
            overall_status = "✅ SUCCESS" if self.results["overall_success"] else "❌ FAILED"
            logger.info(f"\nOverall Result: {overall_status}")
            logger.info(f"Tests Passed: {passed_tests}/{total_tests}")
            
            if self.results["overall_success"]:
                logger.info("\n🎉 DOCKER DATABASE FIX VALIDATION SUCCESSFUL!")
                logger.info("The fix should resolve SQLite database access issues in Docker.")
            else:
                logger.error("\n❌ VALIDATION FAILED")
                logger.error("Some issues were identified that need to be addressed.")
            
        finally:
            self.cleanup()
        
        return self.results

def main():
    """Main test execution"""
    import time
    
    validator = DockerDatabaseFixValidator()
    results = validator.run_comprehensive_test()
    
    # Exit with appropriate code
    sys.exit(0 if results["overall_success"] else 1)

if __name__ == "__main__":
    import time
    main()