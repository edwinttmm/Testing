#!/usr/bin/env python3
"""
Main Server Validation Tests - Tests the full main.py implementation
"""
import sys
import pytest
import httpx
import json
import os
import subprocess
import time
import signal
import asyncio
from pathlib import Path

# Configuration for main server testing
MAIN_SERVER_URL = "http://localhost:8000"
MAIN_SERVER_PORT = 8000
TIMEOUT = 30.0

class MainServerValidator:
    """Test suite for main.py server validation"""
    
    @pytest.fixture(scope="session")
    def server_process(self):
        """Start main server for testing"""
        # Change to backend directory
        backend_dir = Path(__file__).parent.parent
        os.chdir(backend_dir)
        
        # Start the main server
        print("🚀 Starting main.py server for validation...")
        env = os.environ.copy()
        env['PYTHONPATH'] = str(backend_dir)
        
        process = subprocess.Popen([
            "python", "-m", "uvicorn", "main:app", 
            "--host", "0.0.0.0",
            "--port", str(MAIN_SERVER_PORT),
            "--log-level", "info"
        ], env=env, cwd=backend_dir)
        
        # Wait for server to start
        time.sleep(5)
        
        yield process
        
        # Cleanup
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)

class TestMainServerStartup:
    """Test main server startup and basic functionality"""
    
    def test_server_can_start(self, server_process):
        """Test that main.py can start without errors"""
        # Check if process is running
        assert server_process.poll() is None, "Main server process died on startup"
        
    @pytest.mark.asyncio
    async def test_main_server_health(self, server_process):
        """Test main server health endpoint"""
        # Wait a bit more for server to be ready
        await asyncio.sleep(2)
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.get(f"{MAIN_SERVER_URL}/health")
                assert response.status_code == 200
                data = response.json()
                
                # Check health response structure
                assert "status" in data
                assert "timestamp" in data or "message" in data
                
            except httpx.ConnectError:
                pytest.fail("Cannot connect to main server - check if it started correctly")
            except Exception as e:
                pytest.fail(f"Health check failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_main_server_docs(self, server_process):
        """Test main server API documentation"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                # Test OpenAPI docs
                response = await client.get(f"{MAIN_SERVER_URL}/docs")
                assert response.status_code == 200
                
                # Test OpenAPI JSON
                openapi_response = await client.get(f"{MAIN_SERVER_URL}/openapi.json")
                assert openapi_response.status_code == 200
                openapi_data = openapi_response.json()
                assert "openapi" in openapi_data
                assert "info" in openapi_data
                
            except httpx.ConnectError:
                pytest.fail("Cannot connect to main server for docs")
            except Exception as e:
                pytest.fail(f"Docs check failed: {str(e)}")

class TestMainServerEndpoints:
    """Test main server API endpoints"""
    
    @pytest.mark.asyncio
    async def test_cors_configuration(self, server_process):
        """Test CORS configuration on main server"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.options(f"{MAIN_SERVER_URL}/health")
                # Should not fail with CORS error
                assert response.status_code in [200, 405]  # OPTIONS might not be explicitly handled
                
            except Exception as e:
                pytest.fail(f"CORS test failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_available_endpoints(self, server_process):
        """Test that expected endpoints are available"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                # Get OpenAPI spec to check available endpoints
                response = await client.get(f"{MAIN_SERVER_URL}/openapi.json")
                assert response.status_code == 200
                
                openapi_spec = response.json()
                paths = openapi_spec.get("paths", {})
                
                # Check for expected endpoint patterns
                endpoint_patterns = [
                    "/health",
                    "/api/"  # Should have some API endpoints
                ]
                
                available_paths = list(paths.keys())
                
                for pattern in endpoint_patterns:
                    matching_paths = [path for path in available_paths if pattern in path]
                    assert len(matching_paths) > 0, f"No endpoints matching pattern '{pattern}' found"
                
            except Exception as e:
                pytest.fail(f"Endpoint availability test failed: {str(e)}")

class TestMainServerDatabaseIntegration:
    """Test main server database integration"""
    
    @pytest.mark.asyncio
    async def test_database_connection(self, server_process):
        """Test that main server can connect to database"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                # Try to hit an endpoint that would require database
                response = await client.get(f"{MAIN_SERVER_URL}/health")
                assert response.status_code == 200
                
                # If there's a database health endpoint, test it
                try:
                    db_health_response = await client.get(f"{MAIN_SERVER_URL}/api/health/database")
                    if db_health_response.status_code == 200:
                        db_health_data = db_health_response.json()
                        assert "database" in db_health_data or "status" in db_health_data
                except httpx.HTTPStatusError:
                    # Database health endpoint might not exist, that's okay
                    pass
                
            except Exception as e:
                pytest.fail(f"Database connection test failed: {str(e)}")

class TestMainServerSecurity:
    """Test main server security features"""
    
    @pytest.mark.asyncio
    async def test_security_headers(self, server_process):
        """Test security headers on main server"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.get(f"{MAIN_SERVER_URL}/health")
                assert response.status_code == 200
                
                headers = response.headers
                
                # Check for basic security practices
                # Note: Specific headers depend on implementation
                assert "server" not in headers or "FastAPI" not in headers.get("server", "")
                
            except Exception as e:
                pytest.fail(f"Security headers test failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, server_process):
        """Test error handling on main server"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                # Test 404 handling
                response = await client.get(f"{MAIN_SERVER_URL}/nonexistent/endpoint")
                assert response.status_code == 404
                
                # Should return JSON error, not expose internal details
                try:
                    error_data = response.json()
                    assert "detail" in error_data
                except:
                    # HTML response is also acceptable for 404s
                    pass
                
            except Exception as e:
                pytest.fail(f"Error handling test failed: {str(e)}")

class TestMainServerPerformance:
    """Test main server performance"""
    
    @pytest.mark.asyncio
    async def test_response_times(self, server_process):
        """Test main server response times"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                # Test health endpoint response time
                start_time = time.time()
                response = await client.get(f"{MAIN_SERVER_URL}/health")
                end_time = time.time()
                
                assert response.status_code == 200
                response_time = end_time - start_time
                
                # Health check should be fast (under 2 seconds)
                assert response_time < 2.0, f"Health check took {response_time:.2f}s, too slow"
                
            except Exception as e:
                pytest.fail(f"Performance test failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, server_process):
        """Test main server handles concurrent requests"""
        async def make_request():
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{MAIN_SERVER_URL}/health")
                return response.status_code == 200
        
        try:
            # Make 5 concurrent requests
            tasks = [make_request() for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            assert all(results), "Not all concurrent requests succeeded"
            
        except Exception as e:
            pytest.fail(f"Concurrent requests test failed: {str(e)}")

# Main server startup validation 
def test_main_server_imports():
    """Test that main.py can be imported without errors"""
    backend_dir = Path(__file__).parent.parent
    
    try:
        # Try to import main module
        import sys
        sys.path.insert(0, str(backend_dir))
        
        import main
        
        # Check that FastAPI app exists
        assert hasattr(main, 'app'), "main.py should have 'app' attribute"
        
        from fastapi import FastAPI
        assert isinstance(main.app, FastAPI), "app should be a FastAPI instance"
        
    except ImportError as e:
        pytest.fail(f"Cannot import main.py: {str(e)}")
    except Exception as e:
        pytest.fail(f"Error validating main.py: {str(e)}")

if __name__ == "__main__":
    print("🧪 Running Main Server Validation Tests")
    print("=" * 60)
    
    # Run pytest with verbose output
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", __file__, 
        "-v", "--tb=short", "--no-header", "-s"
    ], cwd=os.path.dirname(__file__) or ".")
    
    exit_code = result.returncode
    if exit_code == 0:
        print("\n✅ All main server validation tests passed!")
    else:
        print(f"\n❌ Some main server tests failed (exit code: {exit_code})")
    
    exit(exit_code)