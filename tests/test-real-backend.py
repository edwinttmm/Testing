#!/usr/bin/env python3
"""
Test the real backend application if available
"""

import sys
import os
import requests
import json
import sqlite3
import time
import subprocess
from pathlib import Path

def test_real_backend():
    """Test the real backend if it's available"""
    backend_path = "/home/rigade/Testing/ai-model-validation-platform/backend"
    
    print("=== Testing Real Backend Application ===")
    
    # Check if we can run the real backend
    os.chdir(backend_path)
    
    # Test database
    try:
        if os.path.exists("dev_database.db"):
            conn = sqlite3.connect("dev_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"✅ SQLite database: {len(tables)} tables found")
            conn.close()
        else:
            print("⚠️  SQLite database not found")
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
    
    # Test if uvicorn can be run
    try:
        # First try to activate virtual environment and run a simple test
        os.chdir(backend_path)
        
        # Check if config.py can be imported
        result = subprocess.run([
            "bash", "-c", 
            "source venv/bin/activate && python -c 'import config; print(\"Config loaded:\", config.settings.api_host)'"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Real backend configuration loaded successfully")
            print(f"Config output: {result.stdout.strip()}")
        else:
            print(f"❌ Config loading failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Real backend test failed: {e}")
        
    # Try to import main modules
    try:
        sys.path.insert(0, backend_path)
        
        # Test minimal imports
        print("Testing imports...")
        import config
        print("✅ Config imported")
        
        # Check database URL
        print(f"Database URL: {config.settings.database_url}")
        print(f"API Host: {config.settings.api_host}")
        print(f"API Port: {config.settings.api_port}")
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Backend test error: {e}")

def check_container_health():
    """Check Docker container health"""
    print("\n=== Docker Container Health Check ===")
    
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if result.returncode == 0:
            print("Docker containers status:")
            print(result.stdout)
            
            # Check specific containers
            containers = ['ai_validation_postgres', 'ai_validation_redis']
            for container in containers:
                health_result = subprocess.run([
                    'docker', 'inspect', '--format={{.State.Health.Status}}', container
                ], capture_output=True, text=True)
                
                if health_result.returncode == 0:
                    health = health_result.stdout.strip()
                    print(f"✅ {container}: {health}")
                else:
                    print(f"⚠️  {container}: not found or no health check")
        else:
            print("❌ Docker not available")
            
    except Exception as e:
        print(f"❌ Container health check failed: {e}")

def manual_api_tests():
    """Manual API endpoint tests using curl"""
    print("\n=== Manual API Tests ===")
    
    endpoints = [
        "http://localhost:8000/health",
        "http://localhost:8000/",
        "http://localhost:8000/api/projects",
        "http://localhost:8000/api/videos"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                print(f"✅ {endpoint}: {response.status_code}")
                if len(response.text) < 200:
                    print(f"   Response: {response.text}")
            else:
                print(f"⚠️  {endpoint}: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ {endpoint}: Connection refused")
        except Exception as e:
            print(f"❌ {endpoint}: {e}")

def main():
    print("🔍 Real Backend Testing Suite")
    print("=" * 50)
    
    check_container_health()
    manual_api_tests()  
    test_real_backend()
    
    print("\n" + "=" * 50)
    print("✅ Real backend testing completed")

if __name__ == "__main__":
    main()