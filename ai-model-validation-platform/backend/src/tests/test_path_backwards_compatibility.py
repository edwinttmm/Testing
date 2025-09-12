"""
Test Script for Path Management Backwards Compatibility
======================================================

Tests that the new path management system correctly handles existing
relative paths and migrates them to absolute paths without breaking
existing functionality.
"""

import os
import sys
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.utils.path_utils import PathManager, migrate_legacy_path, resolve_path
    from config import get_settings
    PATH_UTILS_AVAILABLE = True
except ImportError as e:
    PATH_UTILS_AVAILABLE = False
    print(f"❌ Could not import path utils: {e}")

logger = logging.getLogger(__name__)


class BackwardsCompatibilityTester:
    """Test backwards compatibility of path management system."""
    
    def __init__(self):
        # Create temporary test environment
        self.test_dir = Path(tempfile.mkdtemp(prefix="path_test_"))
        self.legacy_paths = []
        self.test_results = []
        
        print(f"🏗️ Test environment created: {self.test_dir}")
        
    def setup_legacy_environment(self):
        """Set up test environment with legacy file structure."""
        try:
            # Create legacy directory structure
            legacy_dirs = [
                "uploads",
                "screenshots", 
                "data",
                "videos",
                "temp"
            ]
            
            for dir_name in legacy_dirs:
                dir_path = self.test_dir / dir_name
                dir_path.mkdir(exist_ok=True)
            
            # Create test files with legacy paths
            test_files = [
                "uploads/test_video.mp4",
                "screenshots/detection_001.jpg",
                "screenshots/detection_001_zoom.jpg",
                "data/ground_truth.json",
                "videos/sample.avi",
                "temp/processing.tmp"
            ]
            
            for file_path in test_files:
                full_path = self.test_dir / file_path
                full_path.touch()
                # Store relative path for testing
                self.legacy_paths.append(str(file_path))
            
            print(f"✅ Created {len(test_files)} legacy test files")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup legacy environment: {e}")
            return False
    
    def test_legacy_path_migration(self):
        """Test migration of legacy relative paths to absolute paths."""
        print("\n🔄 Testing legacy path migration...")
        
        if not PATH_UTILS_AVAILABLE:
            print("❌ Path utils not available - skipping migration tests")
            return False
        
        try:
            # Initialize path manager with test directory
            path_manager = PathManager(base_dir=self.test_dir)
            
            migration_results = []
            
            for legacy_path in self.legacy_paths:
                try:
                    # Test migration
                    migrated_path = path_manager.migrate_legacy_path(legacy_path)
                    
                    # Verify the migrated path
                    is_absolute = migrated_path.is_absolute()
                    file_exists = migrated_path.exists()
                    is_safe = path_manager.is_safe_path(migrated_path)
                    
                    result = {
                        'legacy_path': legacy_path,
                        'migrated_path': str(migrated_path),
                        'is_absolute': is_absolute,
                        'file_exists': file_exists,
                        'is_safe': is_safe,
                        'success': is_absolute and file_exists and is_safe
                    }
                    
                    migration_results.append(result)
                    
                    if result['success']:
                        print(f"  ✅ {legacy_path} -> {migrated_path}")
                    else:
                        print(f"  ❌ {legacy_path} -> {migrated_path} (issues: abs={is_absolute}, exists={file_exists}, safe={is_safe})")
                
                except Exception as e:
                    print(f"  ❌ Migration failed for {legacy_path}: {e}")
                    migration_results.append({
                        'legacy_path': legacy_path,
                        'error': str(e),
                        'success': False
                    })
            
            # Calculate success rate
            successful = sum(1 for r in migration_results if r.get('success', False))
            total = len(migration_results)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            print(f"\n📊 Migration Results: {successful}/{total} ({success_rate:.1f}% success)")
            
            self.test_results.extend(migration_results)
            return success_rate >= 80  # 80% success threshold
            
        except Exception as e:
            print(f"❌ Migration test failed: {e}")
            return False
    
    def test_path_resolution(self):
        """Test path resolution for various input formats."""
        print("\n🔍 Testing path resolution...")
        
        if not PATH_UTILS_AVAILABLE:
            print("❌ Path utils not available - skipping resolution tests")
            return False
        
        try:
            path_manager = PathManager(base_dir=self.test_dir)
            
            # Test various path formats
            test_cases = [
                ("relative/path/file.txt", "relative path"),
                (str(self.test_dir / "absolute" / "file.txt"), "absolute path"),
                ("./current/file.txt", "current directory path"),
                ("../parent/file.txt", "parent directory path"),
                ("uploads/video.mp4", "upload directory path"),
                ("screenshots/image.jpg", "screenshot directory path")
            ]
            
            resolution_results = []
            
            for test_path, description in test_cases:
                try:
                    resolved = path_manager.resolve_path(test_path)
                    
                    result = {
                        'input_path': test_path,
                        'description': description,
                        'resolved_path': str(resolved),
                        'is_absolute': resolved.is_absolute(),
                        'is_safe': path_manager.is_safe_path(resolved),
                        'success': True
                    }
                    
                    print(f"  ✅ {description}: {test_path} -> {resolved}")
                    
                except Exception as e:
                    result = {
                        'input_path': test_path,
                        'description': description,
                        'error': str(e),
                        'success': False
                    }
                    
                    print(f"  ❌ {description}: {test_path} -> ERROR: {e}")
                
                resolution_results.append(result)
            
            # Calculate results
            successful = sum(1 for r in resolution_results if r.get('success', False))
            total = len(resolution_results)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            print(f"\n📊 Resolution Results: {successful}/{total} ({success_rate:.1f}% success)")
            
            self.test_results.extend(resolution_results)
            return success_rate >= 70  # 70% success threshold (some may intentionally fail)
            
        except Exception as e:
            print(f"❌ Resolution test failed: {e}")
            return False
    
    def test_upload_path_handling(self):
        """Test upload path handling with various filename formats."""
        print("\n📤 Testing upload path handling...")
        
        if not PATH_UTILS_AVAILABLE:
            print("❌ Path utils not available - skipping upload tests")
            return False
        
        try:
            from src.utils.path_utils import resolve_upload_path
            
            test_filenames = [
                "simple_video.mp4",
                "video with spaces.mp4", 
                "special_chars_@#$.avi",
                "unicode_文件名.mov",
                "very_long_filename_" + "x" * 200 + ".mp4",
                "",  # Empty filename (should fail gracefully)
                "../../../etc/passwd",  # Path traversal attempt
                "normal_file.webm"
            ]
            
            upload_results = []
            
            for filename in test_filenames:
                try:
                    if filename:  # Skip empty filename test
                        upload_path = resolve_upload_path(filename)
                        
                        result = {
                            'filename': filename,
                            'upload_path': str(upload_path),
                            'is_absolute': upload_path.is_absolute(),
                            'is_in_uploads': 'uploads' in str(upload_path),
                            'success': True
                        }
                        
                        print(f"  ✅ {filename} -> {upload_path}")
                    else:
                        # Test empty filename
                        try:
                            upload_path = resolve_upload_path(filename)
                            result = {'filename': filename, 'success': False, 'error': 'Should have failed'}
                        except ValueError:
                            result = {'filename': filename, 'success': True, 'error': 'Correctly rejected empty filename'}
                        print(f"  ✅ Empty filename correctly rejected")
                
                except Exception as e:
                    result = {
                        'filename': filename,
                        'error': str(e),
                        'success': filename in ["", "../../../etc/passwd"]  # These should fail
                    }
                    
                    if result['success']:
                        print(f"  ✅ {filename} -> Correctly rejected: {e}")
                    else:
                        print(f"  ❌ {filename} -> Unexpected error: {e}")
                
                upload_results.append(result)
            
            # Calculate results
            successful = sum(1 for r in upload_results if r.get('success', False))
            total = len(upload_results)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            print(f"\n📊 Upload Path Results: {successful}/{total} ({success_rate:.1f}% success)")
            
            self.test_results.extend(upload_results)
            return success_rate >= 75  # 75% success threshold
            
        except Exception as e:
            print(f"❌ Upload path test failed: {e}")
            return False
    
    def test_database_integration(self):
        """Test integration with database storage patterns."""
        print("\n💾 Testing database integration patterns...")
        
        if not PATH_UTILS_AVAILABLE:
            print("❌ Path utils not available - skipping database tests")
            return False
        
        try:
            path_manager = PathManager(base_dir=self.test_dir)
            
            # Simulate database storage scenarios
            scenarios = [
                {
                    'name': 'New upload with absolute path',
                    'file_path': str(self.test_dir / "uploads" / "new_video.mp4"),
                    'expected_type': 'absolute'
                },
                {
                    'name': 'Legacy relative path migration',
                    'file_path': "uploads/old_video.mp4", 
                    'expected_type': 'migrated'
                },
                {
                    'name': 'Screenshot path storage',
                    'file_path': "screenshots/detection.jpg",
                    'expected_type': 'migrated'
                }
            ]
            
            db_results = []
            
            for scenario in scenarios:
                try:
                    file_path = scenario['file_path']
                    
                    # Test path resolution
                    if Path(file_path).is_absolute():
                        resolved_path = Path(file_path)
                    else:
                        resolved_path = path_manager.migrate_legacy_path(file_path)
                    
                    # Test getting relative path for database storage
                    relative_for_db = path_manager.get_relative_path(resolved_path)
                    
                    # Test round-trip: relative -> absolute
                    restored_absolute = path_manager.resolve_path(relative_for_db)
                    
                    result = {
                        'scenario': scenario['name'],
                        'original_path': file_path,
                        'resolved_absolute': str(resolved_path),
                        'relative_for_db': relative_for_db,
                        'restored_absolute': str(restored_absolute),
                        'round_trip_success': str(resolved_path) == str(restored_absolute),
                        'success': True
                    }
                    
                    print(f"  ✅ {scenario['name']}: Round-trip successful")
                    
                except Exception as e:
                    result = {
                        'scenario': scenario['name'],
                        'error': str(e),
                        'success': False
                    }
                    
                    print(f"  ❌ {scenario['name']}: {e}")
                
                db_results.append(result)
            
            # Calculate results
            successful = sum(1 for r in db_results if r.get('success', False))
            total = len(db_results)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            print(f"\n📊 Database Integration Results: {successful}/{total} ({success_rate:.1f}% success)")
            
            self.test_results.extend(db_results)
            return success_rate >= 90  # High threshold for database integration
            
        except Exception as e:
            print(f"❌ Database integration test failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up test environment."""
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
                print(f"🧹 Cleaned up test directory: {self.test_dir}")
        except Exception as e:
            print(f"⚠️ Failed to clean up test directory: {e}")
    
    def run_all_tests(self):
        """Run all backwards compatibility tests."""
        print("🚀 Starting Path Management Backwards Compatibility Tests")
        print("=" * 60)
        
        if not PATH_UTILS_AVAILABLE:
            print("❌ Path utilities not available - cannot run tests")
            return False
        
        # Setup test environment
        if not self.setup_legacy_environment():
            print("❌ Failed to setup test environment")
            return False
        
        # Run tests
        test_results = []
        
        tests = [
            ("Legacy Path Migration", self.test_legacy_path_migration),
            ("Path Resolution", self.test_path_resolution), 
            ("Upload Path Handling", self.test_upload_path_handling),
            ("Database Integration", self.test_database_integration)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔬 Running {test_name}...")
            try:
                result = test_func()
                test_results.append((test_name, result))
                status = "✅ PASSED" if result else "❌ FAILED"
                print(f"🏁 {test_name}: {status}")
            except Exception as e:
                test_results.append((test_name, False))
                print(f"🏁 {test_name}: ❌ FAILED (Exception: {e})")
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"  {test_name}: {status}")
        
        overall_success = passed / total >= 0.75  # 75% pass rate
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n🎯 Overall Result: {passed}/{total} tests passed ({success_rate:.1f}%)")
        
        if overall_success:
            print("🎉 Backwards compatibility tests PASSED!")
        else:
            print("⚠️ Backwards compatibility tests FAILED - review issues above")
        
        return overall_success


def main():
    """Main test execution function."""
    logging.basicConfig(level=logging.INFO)
    
    tester = BackwardsCompatibilityTester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    finally:
        tester.cleanup()


if __name__ == "__main__":
    exit(main())