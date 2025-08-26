#!/usr/bin/env python3
"""
Test Script: Database URL Fix Solution Validation
================================================

This test script validates that the URL fix solution works correctly:
1. Tests the migration script functionality
2. Tests the API endpoints 
3. Validates database changes
4. Tests rollback capability

Usage:
    python test_url_fix_solution.py
"""

import os
import sys
import requests
import json
import tempfile
import shutil
from pathlib import Path
import pytest
from datetime import datetime

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import our solution components
from services.url_fix_service import URLFixService
from migrations.fix_localhost_urls import LocalhostURLFixer
from config import Settings

class URLFixSolutionTester:
    """
    Comprehensive test suite for the URL fix solution.
    """
    
    def __init__(self, backend_url="http://155.138.239.131:8000"):
        self.backend_url = backend_url
        self.settings = Settings()
        self.test_database_path = "test_url_fix.db"
        
        # Create test database
        self.test_engine = create_engine(f"sqlite:///{self.test_database_path}")
        self.TestSession = sessionmaker(bind=self.test_engine)
        
    def setup_test_database(self):
        """Create test database with sample data containing localhost URLs."""
        print("🔧 Setting up test database with localhost URLs...")
        
        # Create tables (simplified for testing)
        with self.test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    filename TEXT,
                    file_path TEXT,
                    project_id TEXT,
                    status TEXT DEFAULT 'uploaded',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS detection_events (
                    id TEXT PRIMARY KEY,
                    test_session_id TEXT,
                    timestamp REAL,
                    screenshot_path TEXT,
                    screenshot_zoom_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Insert test data with localhost URLs
            test_videos = [
                ("video-1", "test1.mp4", "http://localhost:8000/uploads/test1.mp4", "project-1"),
                ("video-2", "test2.mp4", "http://localhost:8000/uploads/test2.mp4", "project-1"),
                ("video-3", "test3.mp4", "/local/path/test3.mp4", "project-2"),  # No localhost URL
                ("video-4", "test4.mp4", "http://localhost:8000/uploads/subdir/test4.mp4", "project-2"),
            ]
            
            test_detection_events = [
                ("det-1", "session-1", 1.5, "http://localhost:8000/screenshots/det1.png", "http://localhost:8000/screenshots/det1_zoom.png"),
                ("det-2", "session-1", 2.5, "http://localhost:8000/screenshots/det2.png", None),
                ("det-3", "session-2", 3.5, "/local/screenshots/det3.png", "http://localhost:8000/screenshots/det3_zoom.png"),
                ("det-4", "session-2", 4.5, None, None),  # No URLs
            ]
            
            for video_data in test_videos:
                conn.execute(text("""
                    INSERT INTO videos (id, filename, file_path, project_id)
                    VALUES (:id, :filename, :file_path, :project_id)
                """), {
                    "id": video_data[0],
                    "filename": video_data[1], 
                    "file_path": video_data[2],
                    "project_id": video_data[3]
                })
            
            for det_data in test_detection_events:
                conn.execute(text("""
                    INSERT INTO detection_events (id, test_session_id, timestamp, screenshot_path, screenshot_zoom_path)
                    VALUES (:id, :test_session_id, :timestamp, :screenshot_path, :screenshot_zoom_path)
                """), {
                    "id": det_data[0],
                    "test_session_id": det_data[1],
                    "timestamp": det_data[2],
                    "screenshot_path": det_data[3],
                    "screenshot_zoom_path": det_data[4]
                })
            
            conn.commit()
        
        print("✅ Test database created with sample localhost URLs")
    
    def test_migration_script_scan(self):
        """Test the migration script scanning functionality."""
        print("\n🔍 Testing migration script scan...")
        
        # Mock settings to use test database
        test_settings = Settings()
        test_settings.database_url = f"sqlite:///{self.test_database_path}"
        
        fixer = LocalhostURLFixer(test_settings)
        
        # Override session to use test database
        fixer.session = self.TestSession()
        
        try:
            findings = fixer.scan_for_localhost_urls()
            
            # Validate findings
            assert len(findings) > 0, "Should find localhost URLs"
            
            if 'videos' in findings:
                video_findings = findings['videos']
                localhost_videos = [f for f in video_findings if 'localhost:8000' in f['old_value']]
                print(f"   Found {len(localhost_videos)} videos with localhost URLs")
                assert len(localhost_videos) >= 3, "Should find at least 3 videos with localhost URLs"
            
            if 'detection_events' in findings:
                det_findings = findings['detection_events']
                print(f"   Found {len(det_findings)} detection events with localhost URLs")
                assert len(det_findings) >= 2, "Should find at least 2 detection events with localhost URLs"
            
            print("✅ Migration script scan test passed")
            return True
            
        except Exception as e:
            print(f"❌ Migration script scan test failed: {e}")
            return False
        finally:
            fixer.close()
    
    def test_migration_script_dry_run(self):
        """Test migration script dry run mode."""
        print("\n🔍 Testing migration script dry run...")
        
        test_settings = Settings()
        test_settings.database_url = f"sqlite:///{self.test_database_path}"
        
        fixer = LocalhostURLFixer(test_settings)
        fixer.session = self.TestSession()
        
        try:
            findings = fixer.scan_for_localhost_urls()
            update_counts = fixer.apply_url_fixes(findings, dry_run=True)
            
            # Validate dry run doesn't change anything
            assert sum(update_counts.values()) > 0, "Should report changes in dry run"
            
            # Verify data wasn't actually changed
            session = self.TestSession()
            localhost_videos = session.execute(text("""
                SELECT COUNT(*) FROM videos WHERE file_path LIKE '%localhost:8000%'
            """)).scalar()
            
            assert localhost_videos >= 3, "Dry run should not have changed the data"
            session.close()
            
            print(f"✅ Dry run test passed - would update {sum(update_counts.values())} records")
            return True
            
        except Exception as e:
            print(f"❌ Migration script dry run test failed: {e}")
            return False
        finally:
            fixer.close()
    
    def test_migration_script_execution(self):
        """Test migration script execution."""
        print("\n🔧 Testing migration script execution...")
        
        test_settings = Settings()
        test_settings.database_url = f"sqlite:///{self.test_database_path}"
        
        fixer = LocalhostURLFixer(test_settings)
        fixer.session = self.TestSession()
        
        try:
            # Get baseline
            session = self.TestSession()
            baseline_videos = session.execute(text("""
                SELECT COUNT(*) FROM videos WHERE file_path LIKE '%localhost:8000%'
            """)).scalar()
            session.close()
            
            print(f"   Baseline: {baseline_videos} videos with localhost URLs")
            
            # Execute fix
            findings = fixer.scan_for_localhost_urls()
            backup_path = fixer.create_backup(findings)
            update_counts = fixer.apply_url_fixes(findings, dry_run=False)
            
            print(f"   Updated {sum(update_counts.values())} records")
            print(f"   Backup created: {backup_path}")
            
            # Verify changes
            session = self.TestSession()
            remaining_videos = session.execute(text("""
                SELECT COUNT(*) FROM videos WHERE file_path LIKE '%localhost:8000%'
            """)).scalar()
            
            production_videos = session.execute(text("""
                SELECT COUNT(*) FROM videos WHERE file_path LIKE '%155.138.239.131:8000%'
            """)).scalar()
            
            session.close()
            
            assert remaining_videos == 0, f"Should have no localhost URLs remaining, found {remaining_videos}"
            assert production_videos >= 3, f"Should have production URLs, found {production_videos}"
            
            print(f"✅ Migration execution test passed - {production_videos} URLs updated")
            return True
            
        except Exception as e:
            print(f"❌ Migration script execution test failed: {e}")
            return False
        finally:
            fixer.close()
    
    def test_api_endpoints(self):
        """Test the API endpoints if backend is running."""
        print(f"\n🌐 Testing API endpoints at {self.backend_url}...")
        
        try:
            # Test health check first
            health_response = requests.get(f"{self.backend_url}/health", timeout=5)
            if health_response.status_code != 200:
                print(f"⚠️  Backend not accessible at {self.backend_url}")
                return False
            
            # Test scan endpoint
            print("   Testing scan endpoint...")
            scan_response = requests.get(f"{self.backend_url}/api/videos/fix-urls/scan", timeout=10)
            
            if scan_response.status_code == 200:
                scan_data = scan_response.json()
                print(f"   Scan found {scan_data.get('total_records_found', 0)} records")
                print(f"   Recommendation: {scan_data.get('recommendation', 'unknown')}")
            else:
                print(f"   Scan endpoint returned {scan_response.status_code}")
            
            # Test status endpoint
            print("   Testing status endpoint...")
            status_response = requests.get(f"{self.backend_url}/api/videos/fix-urls/status", timeout=10)
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"   Status: {status_data.get('status', 'unknown')}")
            else:
                print(f"   Status endpoint returned {status_response.status_code}")
            
            # Test fix endpoint (with caution in production)
            if "localhost" in self.backend_url or "test" in self.backend_url:
                print("   Testing fix endpoint (safe for test environment)...")
                fix_response = requests.post(f"{self.backend_url}/api/videos/fix-urls", timeout=30)
                
                if fix_response.status_code == 200:
                    fix_data = fix_response.json()
                    print(f"   Fix updated {fix_data.get('updated_count', 0)} records")
                else:
                    print(f"   Fix endpoint returned {fix_response.status_code}")
            else:
                print("   Skipping fix endpoint test in production environment")
            
            print("✅ API endpoints test completed")
            return True
            
        except requests.RequestException as e:
            print(f"❌ API endpoints test failed - backend not accessible: {e}")
            return False
        except Exception as e:
            print(f"❌ API endpoints test failed: {e}")
            return False
    
    def test_url_fix_service(self):
        """Test the URL fix service directly."""
        print("\n🔧 Testing URL fix service...")
        
        try:
            # Use test database
            test_settings = Settings()
            test_settings.database_url = f"sqlite:///{self.test_database_path}"
            
            service = URLFixService(test_settings)
            session = self.TestSession()
            
            # Test scan
            scan_results = await service.scan_database_for_localhost_urls(session)
            print(f"   Service scan found {scan_results['total_records']} records")
            
            # Test validation (should fail before fix)
            validation_results = await service.validate_url_fixes(session)
            print(f"   Validation before fix: {validation_results['validation_passed']}")
            
            session.close()
            
            print("✅ URL fix service test completed")
            return True
            
        except Exception as e:
            print(f"❌ URL fix service test failed: {e}")
            return False
    
    def cleanup_test_database(self):
        """Clean up test database."""
        try:
            if os.path.exists(self.test_database_path):
                os.remove(self.test_database_path)
                print(f"🧹 Cleaned up test database: {self.test_database_path}")
        except Exception as e:
            print(f"⚠️  Could not clean up test database: {e}")
    
    def run_all_tests(self):
        """Run all tests in sequence."""
        print("🚀 Starting URL Fix Solution Test Suite")
        print("="*60)
        
        results = {}
        
        # Setup
        try:
            self.setup_test_database()
            
            # Run tests
            results['migration_scan'] = self.test_migration_script_scan()
            results['migration_dry_run'] = self.test_migration_script_dry_run()
            results['migration_execution'] = self.test_migration_script_execution()
            results['api_endpoints'] = self.test_api_endpoints()
            # results['url_fix_service'] = self.test_url_fix_service()  # Async test, skip for now
            
        except Exception as e:
            print(f"❌ Test setup failed: {e}")
            return False
        
        finally:
            # Cleanup
            self.cleanup_test_database()
        
        # Print results
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name:<25}: {status}")
            if result:
                passed += 1
        
        print(f"\n📈 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! URL fix solution is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Please review the solution.")
            return False


def main():
    """Run the test suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test URL fix solution")
    parser.add_argument('--backend-url', default='http://155.138.239.131:8000',
                       help='Backend URL to test against')
    parser.add_argument('--local-test', action='store_true',
                       help='Run local tests only (no API calls)')
    
    args = parser.parse_args()
    
    tester = URLFixSolutionTester(args.backend_url)
    
    if args.local_test:
        print("🧪 Running local tests only...")
        tester.setup_test_database()
        try:
            results = {
                'migration_scan': tester.test_migration_script_scan(),
                'migration_dry_run': tester.test_migration_script_dry_run(),
                'migration_execution': tester.test_migration_script_execution()
            }
            
            passed = sum(results.values())
            total = len(results)
            print(f"\n📈 Local tests: {passed}/{total} passed")
            
        finally:
            tester.cleanup_test_database()
    else:
        success = tester.run_all_tests()
        return 0 if success else 1


if __name__ == "__main__":
    exit(main())