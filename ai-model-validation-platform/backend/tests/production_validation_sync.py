#!/usr/bin/env python3
"""
Synchronous Production Validation Tests for AI Model Validation Platform
Tests all critical functionality without async dependencies
"""
import os
import sys
import time
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any
import traceback

# Add backend to path
sys.path.append('.')

class ProductionValidator:
    """Comprehensive production validation test suite"""
    
    def __init__(self):
        self.test_results = []
        self.critical_failures = []
        self.warnings = []
        
    def run_test(self, test_name: str, test_func, critical: bool = False):
        """Run a test and record results"""
        print(f"🧪 Running: {test_name}")
        
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            self.test_results.append({
                'name': test_name,
                'status': 'passed',
                'duration': duration,
                'result': result
            })
            print(f"✅ {test_name}: PASSED ({duration:.3f}s)")
            return True
            
        except Exception as e:
            self.test_results.append({
                'name': test_name,
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            
            if critical:
                self.critical_failures.append(test_name)
                print(f"❌ {test_name}: CRITICAL FAILURE - {e}")
            else:
                self.warnings.append(test_name)
                print(f"⚠️  {test_name}: FAILED (non-critical) - {e}")
            return False
    
    def test_database_schema_integrity(self):
        """Test database schema integrity"""
        db_path = "./simple_test.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check core tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['projects', 'videos', 'test_sessions', 'detection_events']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                raise AssertionError(f"Missing required tables: {missing_tables}")
            
            # Check project table schema
            cursor.execute("PRAGMA table_info(projects)")
            project_columns = [col[1] for col in cursor.fetchall()]
            
            required_project_columns = ['id', 'name', 'camera_model', 'signal_type', 'created_at']
            missing_columns = [c for c in required_project_columns if c not in project_columns]
            
            if missing_columns:
                raise AssertionError(f"Missing required project columns: {missing_columns}")
            
            return f"Database schema valid with {len(tables)} tables"
            
        finally:
            conn.close()
    
    def test_project_model_structure(self):
        """Test project model has required fields"""
        try:
            import models
            
            project_cls = getattr(models, 'Project', None)
            if project_cls is None:
                raise ImportError("Project model not found")
            
            # Check table has required columns
            if hasattr(project_cls, '__table__'):
                columns = [col.name for col in project_cls.__table__.columns]
                required_columns = ['id', 'name', 'camera_model', 'signal_type']
                missing = [col for col in required_columns if col not in columns]
                
                if missing:
                    raise AssertionError(f"Project model missing columns: {missing}")
                
                # Check relationships exist
                relationships = list(project_cls.__mapper__.relationships.keys())
                expected_rels = ['videos', 'test_sessions']
                missing_rels = [rel for rel in expected_rels if rel not in relationships]
                
                if missing_rels:
                    raise AssertionError(f"Project model missing relationships: {missing_rels}")
                
                return f"Project model valid with {len(columns)} columns, {len(relationships)} relationships"
            else:
                raise AssertionError("Project model has no __table__ attribute")
                
        except ImportError as e:
            raise ImportError(f"Cannot import models: {e}")
    
    def test_database_crud_operations(self):
        """Test database CRUD operations"""
        db_path = "./simple_test.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Test INSERT
            test_id = f"test-crud-{int(time.time())}"
            cursor.execute("""
                INSERT INTO projects (id, name, camera_model, signal_type, status, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (test_id, "CRUD Test Project", "Test Camera", "GPIO", "active"))
            
            # Test SELECT
            cursor.execute("SELECT * FROM projects WHERE id = ?", (test_id,))
            result = cursor.fetchone()
            if result is None:
                raise AssertionError("Failed to insert project")
            
            # Test UPDATE
            cursor.execute("""
                UPDATE projects SET name = ? WHERE id = ?
            """, ("Updated CRUD Project", test_id))
            
            cursor.execute("SELECT name FROM projects WHERE id = ?", (test_id,))
            updated_result = cursor.fetchone()
            if updated_result[0] != "Updated CRUD Project":
                raise AssertionError("Failed to update project")
            
            # Test DELETE
            cursor.execute("DELETE FROM projects WHERE id = ?", (test_id,))
            cursor.execute("SELECT * FROM projects WHERE id = ?", (test_id,))
            deleted_result = cursor.fetchone()
            if deleted_result is not None:
                raise AssertionError("Failed to delete project")
            
            return "CRUD operations successful"
            
        finally:
            conn.rollback()  # Don't commit test changes
            conn.close()
    
    def test_alembic_migration_files(self):
        """Test Alembic migration files exist and are valid"""
        migrations_dir = "./migrations/versions"
        if not os.path.exists(migrations_dir):
            raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")
        
        migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py') and not f.startswith('__')]
        if len(migration_files) == 0:
            raise AssertionError("No migration files found")
        
        # Check for required migration structure
        valid_migrations = 0
        for migration_file in migration_files:
            migration_path = os.path.join(migrations_dir, migration_file)
            with open(migration_path, 'r') as f:
                content = f.read()
            
            # Check for required Alembic structure
            if 'revision =' in content and 'def upgrade()' in content and 'def downgrade()' in content:
                valid_migrations += 1
        
        if valid_migrations == 0:
            raise AssertionError("No valid migration files found")
        
        return f"{valid_migrations} valid migration files found"
    
    def test_backend_file_structure(self):
        """Test backend file structure is intact"""
        required_files = [
            'main.py',
            'models.py', 
            'database.py',
            'crud.py'
        ]
        
        missing_files = [f for f in required_files if not os.path.exists(f)]
        if missing_files:
            raise AssertionError(f"Missing required backend files: {missing_files}")
        
        return f"All {len(required_files)} required backend files present"
    
    def test_environment_robustness(self):
        """Test system works in different environments"""
        # Test database file permissions
        db_path = "./simple_test.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        stat = os.stat(db_path)
        if stat.st_size == 0:
            raise AssertionError("Database file is empty")
        
        # Test read access
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            result = cursor.fetchone()
            if result[0] == 0:
                raise AssertionError("Database has no tables")
            
            return f"Database accessible with {result[0]} tables"
            
        finally:
            conn.close()
    
    def test_backwards_compatibility(self):
        """Test backwards compatibility with existing data"""
        db_path = "./simple_test.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if existing projects can be read
            cursor.execute("SELECT COUNT(*) FROM projects")
            project_count = cursor.fetchone()[0]
            
            if project_count > 0:
                # Test reading existing projects
                cursor.execute("SELECT id, name FROM projects LIMIT 1")
                project = cursor.fetchone()
                if project is None:
                    raise AssertionError("Cannot read existing projects")
                if len(project) < 2:
                    raise AssertionError("Project data incomplete")
            
            # Test video table compatibility
            cursor.execute("SELECT COUNT(*) FROM videos")
            video_count = cursor.fetchone()[0]
            
            return f"Backwards compatibility verified: {project_count} projects, {video_count} videos"
            
        finally:
            conn.close()
    
    def test_performance_requirements(self):
        """Test performance meets requirements"""
        db_path = "./simple_test.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        # Test query performance
        start_time = time.time()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Should complete basic queries quickly
            cursor.execute("SELECT COUNT(*) FROM projects")
            cursor.execute("SELECT COUNT(*) FROM videos")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            
            query_time = time.time() - start_time
            if query_time > 1.0:
                raise AssertionError(f"Database queries too slow: {query_time:.3f}s")
            
            return f"Performance acceptable: {query_time:.3f}s for basic queries"
            
        finally:
            conn.close()
    
    def test_security_implementation(self):
        """Test security measures are in place"""
        db_path = "./simple_test.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Check for security-related tables (optional)
            security_indicators = ['audit_logs', 'auth_users', 'user_sessions']
            has_security = any(table in tables for table in security_indicators)
            
            # At minimum, should have proper project isolation
            if 'projects' in tables:
                cursor.execute("PRAGMA table_info(projects)")
                columns = [col[1] for col in cursor.fetchall()]
                # Should have some form of ownership/isolation
                isolation_fields = ['owner_id', 'user_id', 'created_by']
                has_isolation = any(field in columns for field in isolation_fields)
                if not has_isolation:
                    raise AssertionError("No data isolation mechanism found")
                
                security_level = "Advanced" if has_security else "Basic"
                return f"{security_level} security measures in place"
            else:
                raise AssertionError("Projects table not found")
        
        finally:
            conn.close()
    
    def validate_production_readiness(self) -> Dict[str, Any]:
        """Run complete production readiness validation"""
        print("🚀 Starting Production Readiness Validation...")
        print("=" * 60)
        
        # Critical tests that must pass for production
        critical_tests = [
            ("Database Schema Integrity", self.test_database_schema_integrity, True),
            ("Project Model Structure", self.test_project_model_structure, True),
            ("Database CRUD Operations", self.test_database_crud_operations, True),
            ("Backend File Structure", self.test_backend_file_structure, True),
        ]
        
        # Important tests that should pass but aren't deployment blockers
        important_tests = [
            ("Alembic Migration Files", self.test_alembic_migration_files, False),
            ("Environment Robustness", self.test_environment_robustness, False),
            ("Backwards Compatibility", self.test_backwards_compatibility, False),
            ("Performance Requirements", self.test_performance_requirements, False),
            ("Security Implementation", self.test_security_implementation, False),
        ]
        
        # Run all tests
        all_tests = critical_tests + important_tests
        for test_name, test_func, is_critical in all_tests:
            self.run_test(test_name, test_func, is_critical)
        
        # Generate report
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['status'] == 'passed')
        failed_tests = total_tests - passed_tests
        
        print("\n" + "=" * 60)
        print("📊 PRODUCTION READINESS REPORT")
        print("=" * 60)
        
        # Overall status
        if self.critical_failures:
            overall_status = "NOT READY"
            status_icon = "❌"
        elif self.warnings:
            overall_status = "READY WITH WARNINGS"
            status_icon = "⚠️"
        else:
            overall_status = "FULLY READY"
            status_icon = "✅"
        
        print(f"{status_icon} Overall Status: {overall_status}")
        print(f"📈 Test Results: {passed_tests}/{total_tests} passed")
        
        if self.critical_failures:
            print(f"🚨 Critical Failures: {len(self.critical_failures)}")
            for failure in self.critical_failures:
                print(f"   ❌ {failure}")
        
        if self.warnings:
            print(f"⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"   ⚠️  {warning}")
        
        # Deployment recommendations
        print("\n🎯 DEPLOYMENT RECOMMENDATIONS:")
        
        if not self.critical_failures and not self.warnings:
            print("✅ System is ready for production deployment")
            print("✅ All tests passed - no additional steps required")
        elif not self.critical_failures:
            print("✅ System is ready for production deployment with monitoring")
            print("⚠️  Address warnings for optimal performance:")
            for warning in self.warnings:
                print(f"   • Review {warning} results")
        else:
            print("❌ System is NOT ready for production deployment")
            print("🔧 Address these critical issues before deployment:")
            for failure in self.critical_failures:
                print(f"   • Fix {failure}")
        
        # Performance summary
        durations = [r.get('duration', 0) for r in self.test_results if r['status'] == 'passed']
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            print(f"\n⏱️  Performance: avg={avg_duration:.3f}s, max={max_duration:.3f}s")
        
        # Return detailed report
        return {
            'overall_status': overall_status,
            'ready_for_production': len(self.critical_failures) == 0,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'critical_failures': self.critical_failures,
            'warnings': self.warnings,
            'test_results': self.test_results,
            'performance': {
                'average_duration': sum(durations) / len(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0
            }
        }

if __name__ == "__main__":
    validator = ProductionValidator()
    report = validator.validate_production_readiness()
    
    # Save detailed report
    report_file = f"production_validation_report_{int(time.time())}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    # Exit with appropriate code
    if report['ready_for_production']:
        print("\n🎉 Production readiness validation completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Production readiness validation failed!")
        sys.exit(1)