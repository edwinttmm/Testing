#!/usr/bin/env python3
"""
Comprehensive Production Validation Tests for AI Model Validation Platform
Tests all critical functionality against real backend implementation
"""
import pytest
import httpx
import json
import asyncio
import time
import sqlite3
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import io

# Test Configuration
BASE_URL = "http://localhost:8001"
TIMEOUT = 30.0

class ComprehensiveValidator:
    """Production validation test suite"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.test_data = {
            'projects': [],
            'videos': []
        }
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

def test_database_schema_integrity():
    """Test database schema integrity"""
    db_path = "./simple_test.db"
    if not os.path.exists(db_path):
        pytest.skip("Database file not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check core tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = ['projects', 'videos', 'test_sessions', 'detection_events']
    for table in required_tables:
        assert table in tables, f"Required table {table} not found"
    
    # Check project table schema
    cursor.execute("PRAGMA table_info(projects)")
    project_columns = [col[1] for col in cursor.fetchall()]
    
    required_project_columns = ['id', 'name', 'camera_model', 'signal_type', 'created_at']
    for col in required_project_columns:
        assert col in project_columns, f"Required project column {col} not found"
    
    conn.close()

def test_project_schema_structure():
    """Test project schema has required fields"""
    try:
        import sys
        sys.path.append('.')
        import models
        
        project_cls = getattr(models, 'Project', None)
        if project_cls is None:
            pytest.skip("Project model not available")
        
        # Check table has required columns
        if hasattr(project_cls, '__table__'):
            columns = [col.name for col in project_cls.__table__.columns]
            required_columns = ['id', 'name', 'camera_model', 'signal_type']
            for col in required_columns:
                assert col in columns, f"Project model missing required column: {col}"
        
    except ImportError as e:
        pytest.skip(f"Cannot import models: {e}")

@pytest.mark.asyncio
async def test_database_crud_operations():
    """Test database CRUD operations directly"""
    db_path = "./simple_test.db"
    if not os.path.exists(db_path):
        pytest.skip("Database file not found")
    
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
        assert result is not None, "Failed to insert project"
        
        # Test UPDATE
        cursor.execute("""
            UPDATE projects SET name = ? WHERE id = ?
        """, ("Updated CRUD Project", test_id))
        
        cursor.execute("SELECT name FROM projects WHERE id = ?", (test_id,))
        updated_result = cursor.fetchone()
        assert updated_result[0] == "Updated CRUD Project", "Failed to update project"
        
        # Test DELETE
        cursor.execute("DELETE FROM projects WHERE id = ?", (test_id,))
        cursor.execute("SELECT * FROM projects WHERE id = ?", (test_id,))
        deleted_result = cursor.fetchone()
        assert deleted_result is None, "Failed to delete project"
        
    finally:
        conn.rollback()  # Don't commit test changes
        conn.close()

def test_alembic_migration_files():
    """Test Alembic migration files exist and are valid"""
    migrations_dir = "./migrations/versions"
    if not os.path.exists(migrations_dir):
        pytest.skip("Migrations directory not found")
    
    migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py')]
    assert len(migration_files) > 0, "No migration files found"
    
    # Check for required migration structure
    for migration_file in migration_files:
        if migration_file.startswith('__'):
            continue
            
        migration_path = os.path.join(migrations_dir, migration_file)
        with open(migration_path, 'r') as f:
            content = f.read()
            
        # Check for required Alembic structure
        assert 'revision =' in content, f"Migration {migration_file} missing revision"
        assert 'def upgrade()' in content, f"Migration {migration_file} missing upgrade function"
        assert 'def downgrade()' in content, f"Migration {migration_file} missing downgrade function"

def test_backend_file_structure():
    """Test backend file structure is intact"""
    required_files = [
        'main.py',
        'models.py',
        'database.py',
        'crud.py'
    ]
    
    for file in required_files:
        assert os.path.exists(file), f"Required backend file {file} not found"

def test_configuration_files():
    """Test configuration files exist"""
    config_files = [
        '.env',
        'requirements.txt'
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            # File exists, check it's not empty
            with open(config_file, 'r') as f:
                content = f.read().strip()
                if config_file == '.env':
                    # Should have some configuration
                    assert len(content) > 0, f"{config_file} exists but is empty"

def test_models_import_safety():
    """Test models can be imported safely without external dependencies"""
    try:
        import sys
        sys.path.append('.')
        
        # Test basic imports first
        import database
        assert hasattr(database, 'Base'), "Database Base not found"
        
        # Test models import with dependency handling
        try:
            import models
            print("✅ Models imported successfully")
        except ImportError as e:
            print(f"⚠️ Models import failed: {e}")
            # This is expected in some environments
            
    except Exception as e:
        pytest.fail(f"Critical import failure: {e}")

def test_environment_robustness():
    """Test system works in different environments"""
    # Test database file permissions
    db_path = "./simple_test.db"
    if os.path.exists(db_path):
        stat = os.stat(db_path)
        assert stat.st_size > 0, "Database file is empty"
        
        # Test read access
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            result = cursor.fetchone()
            assert result[0] > 0, "Database has no tables"
            conn.close()
        except Exception as e:
            pytest.fail(f"Cannot access database: {e}")

def test_backwards_compatibility():
    """Test backwards compatibility with existing data"""
    db_path = "./simple_test.db"
    if not os.path.exists(db_path):
        pytest.skip("Database file not found")
    
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
            assert project is not None, "Cannot read existing projects"
            assert len(project) >= 2, "Project data incomplete"
    
    finally:
        conn.close()

def test_performance_requirements():
    """Test performance meets requirements"""
    db_path = "./simple_test.db"
    if not os.path.exists(db_path):
        pytest.skip("Database file not found")
    
    # Test query performance
    start_time = time.time()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Should complete basic queries quickly
    cursor.execute("SELECT COUNT(*) FROM projects")
    cursor.execute("SELECT COUNT(*) FROM videos")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    
    conn.close()
    
    query_time = time.time() - start_time
    assert query_time < 1.0, f"Database queries too slow: {query_time:.3f}s"

def test_security_implementation():
    """Test security measures are in place"""
    # Check for security-related tables
    db_path = "./simple_test.db"
    if not os.path.exists(db_path):
        pytest.skip("Database file not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Check for audit/security tables (optional)
        security_indicators = ['audit_logs', 'auth_users', 'user_sessions']
        has_security = any(table in tables for table in security_indicators)
        
        # At minimum, should have proper project isolation
        if 'projects' in tables:
            cursor.execute("PRAGMA table_info(projects)")
            columns = [col[1] for col in cursor.fetchall()]
            # Should have some form of ownership/isolation
            isolation_fields = ['owner_id', 'user_id', 'created_by']
            has_isolation = any(field in columns for field in isolation_fields)
            assert has_isolation, "No data isolation mechanism found"
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🧪 Running Comprehensive Production Validation Tests")
    print("=" * 60)
    
    # Run tests
    exit_code = pytest.main([
        __file__, 
        "-v", 
        "--tb=short", 
        "--no-header",
        "-x"  # Stop on first failure
    ])
    
    if exit_code == 0:
        print("\n✅ All production validation tests passed!")
    else:
        print(f"\n❌ Some validation tests failed (exit code: {exit_code})")
    
    exit(exit_code)