#!/usr/bin/env python3
"""
CVAT Redis Authentication Verification Script
Comprehensive test to verify Redis authentication works for all CVAT components
"""

import docker
import time
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class CVATRedisAuthVerifier:
    def __init__(self):
        self.client = docker.from_env()
        self.test_results = []
        self.compose_project = "ai-model-validation-platform"
        
    def log_result(self, test_name: str, success: bool, details: str, error: str = None):
        """Log test result"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "test": test_name,
            "success": success,
            "details": details,
            "error": error
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        if error:
            print(f"    Error: {error}")
    
    def get_container(self, service_name: str) -> Optional[docker.models.containers.Container]:
        """Get container by service name"""
        try:
            container_name = f"ai_validation_{service_name}"
            return self.client.containers.get(container_name)
        except docker.errors.NotFound:
            return None
    
    def wait_for_container_health(self, container, timeout: int = 120) -> bool:
        """Wait for container to become healthy"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            container.reload()
            if container.status == "running":
                # Check health status if available
                if container.attrs.get("State", {}).get("Health"):
                    health_status = container.attrs["State"]["Health"]["Status"]
                    if health_status == "healthy":
                        return True
                    elif health_status == "unhealthy":
                        return False
                else:
                    # If no health check, assume healthy if running
                    return True
            elif container.status == "exited":
                return False
            time.sleep(2)
        return False
    
    def test_redis_baseline(self) -> bool:
        """Test Redis container is working"""
        print("\n🔍 Testing Redis Baseline...")
        
        redis_container = self.get_container("redis")
        if not redis_container:
            self.log_result("Redis Container Check", False, "Redis container not found")
            return False
        
        if redis_container.status != "running":
            self.log_result("Redis Container Status", False, f"Redis status: {redis_container.status}")
            return False
        
        self.log_result("Redis Container Status", True, "Redis container running")
        
        # Test Redis auth from backend
        backend_container = self.get_container("backend")
        if not backend_container:
            self.log_result("Backend Container Check", False, "Backend container not found")
            return False
        
        try:
            result = backend_container.exec_run(
                "python -c \"import redis; import os; "
                "client = redis.from_url(os.getenv('AIVALIDATION_REDIS_URL')); "
                "print(client.ping())\"",
                tty=True
            )
            if result.exit_code == 0 and b"True" in result.output:
                self.log_result("Backend Redis Auth", True, "Backend can authenticate to Redis")
                return True
            else:
                self.log_result("Backend Redis Auth", False, f"Backend Redis test failed: {result.output.decode()}")
                return False
        except Exception as e:
            self.log_result("Backend Redis Auth", False, "Backend Redis test error", str(e))
            return False
    
    def test_cvat_environment_variables(self) -> bool:
        """Test CVAT container has correct environment variables"""
        print("\n🔍 Testing CVAT Environment Variables...")
        
        cvat_container = self.get_container("cvat")
        if not cvat_container:
            self.log_result("CVAT Container Check", False, "CVAT container not found")
            return False
        
        try:
            # Check environment variables
            result = cvat_container.exec_run("env | grep REDIS", tty=True)
            env_output = result.output.decode()
            
            required_vars = [
                "CVAT_REDIS_HOST",
                "CVAT_REDIS_PASSWORD", 
                "RQ_REDIS_HOST",
                "RQ_REDIS_PASSWORD",
                "REDIS_HOST",
                "REDIS_PASSWORD"
            ]
            
            missing_vars = []
            for var in required_vars:
                if var not in env_output:
                    missing_vars.append(var)
            
            if missing_vars:
                self.log_result("CVAT Environment Variables", False, 
                              f"Missing variables: {', '.join(missing_vars)}")
                return False
            else:
                self.log_result("CVAT Environment Variables", True, 
                              "All required Redis environment variables present")
                return True
                
        except Exception as e:
            self.log_result("CVAT Environment Variables", False, "Error checking environment", str(e))
            return False
    
    def test_cvat_redis_connection(self) -> bool:
        """Test CVAT can connect to Redis"""
        print("\n🔍 Testing CVAT Redis Connection...")
        
        cvat_container = self.get_container("cvat")
        if not cvat_container:
            self.log_result("CVAT Redis Connection", False, "CVAT container not available")
            return False
        
        try:
            # Test Redis connection from CVAT container
            redis_test_script = '''
import redis
import os
import sys

try:
    # Test 1: CVAT variables
    cvat_host = os.getenv("CVAT_REDIS_HOST", "redis")
    cvat_password = os.getenv("CVAT_REDIS_PASSWORD", "")
    client1 = redis.Redis(host=cvat_host, port=6379, password=cvat_password, decode_responses=True)
    result1 = client1.ping()
    print(f"CVAT_REDIS connection: {result1}")
    
    # Test 2: RQ variables  
    rq_host = os.getenv("RQ_REDIS_HOST", "redis")
    rq_password = os.getenv("RQ_REDIS_PASSWORD", "")
    client2 = redis.Redis(host=rq_host, port=6379, password=rq_password, decode_responses=True)
    result2 = client2.ping()
    print(f"RQ_REDIS connection: {result2}")
    
    # Test 3: Generic variables
    redis_host = os.getenv("REDIS_HOST", "redis") 
    redis_password = os.getenv("REDIS_PASSWORD", "")
    client3 = redis.Redis(host=redis_host, port=6379, password=redis_password, decode_responses=True)
    result3 = client3.ping()
    print(f"REDIS connection: {result3}")
    
    if result1 and result2 and result3:
        print("SUCCESS: All Redis connections working")
    else:
        print("FAILURE: Some Redis connections failed")
        sys.exit(1)
        
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
'''
            
            # Install redis-py and run test
            install_result = cvat_container.exec_run(
                "pip install redis --quiet", tty=True
            )
            
            if install_result.exit_code != 0:
                self.log_result("CVAT Redis Connection", False, 
                              "Failed to install redis-py in CVAT container")
                return False
            
            result = cvat_container.exec_run(
                f"python -c \"{redis_test_script}\"", tty=True
            )
            
            output = result.output.decode()
            if result.exit_code == 0 and "SUCCESS" in output:
                self.log_result("CVAT Redis Connection", True, 
                              "All CVAT Redis connections successful")
                return True
            else:
                self.log_result("CVAT Redis Connection", False, 
                              f"CVAT Redis test failed: {output}")
                return False
                
        except Exception as e:
            self.log_result("CVAT Redis Connection", False, "Error testing CVAT Redis", str(e))
            return False
    
    def test_cvat_rqscheduler_process(self) -> bool:
        """Test that rqscheduler process starts successfully"""
        print("\n🔍 Testing CVAT rqscheduler Process...")
        
        cvat_container = self.get_container("cvat")
        if not cvat_container:
            self.log_result("rqscheduler Process", False, "CVAT container not available")
            return False
        
        try:
            # Check if rqscheduler process is running
            result = cvat_container.exec_run("ps aux | grep rqscheduler | grep -v grep", tty=True)
            output = result.output.decode().strip()
            
            if output:
                self.log_result("rqscheduler Process", True, f"rqscheduler running: {output}")
                return True
            else:
                # Try to check logs for rqscheduler errors
                log_result = cvat_container.exec_run("tail -50 /home/django/logs/rqscheduler.log 2>/dev/null || echo 'No rqscheduler log found'", tty=True)
                log_output = log_result.output.decode()
                
                self.log_result("rqscheduler Process", False, f"rqscheduler not running. Logs: {log_output}")
                return False
                
        except Exception as e:
            self.log_result("rqscheduler Process", False, "Error checking rqscheduler", str(e))
            return False
    
    def test_cvat_health_endpoint(self) -> bool:
        """Test CVAT health endpoint"""
        print("\n🔍 Testing CVAT Health Endpoint...")
        
        cvat_container = self.get_container("cvat")
        if not cvat_container:
            self.log_result("CVAT Health Check", False, "CVAT container not available")
            return False
        
        try:
            result = cvat_container.exec_run(
                "curl -f http://localhost:8080/api/server/about", tty=True
            )
            
            if result.exit_code == 0:
                self.log_result("CVAT Health Check", True, "CVAT health endpoint responding")
                return True
            else:
                error_output = result.output.decode()
                self.log_result("CVAT Health Check", False, f"Health check failed: {error_output}")
                return False
                
        except Exception as e:
            self.log_result("CVAT Health Check", False, "Error testing CVAT health", str(e))
            return False
    
    def run_full_verification(self) -> bool:
        """Run complete verification suite"""
        print("🚀 CVAT Redis Authentication Verification Suite")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all tests
        tests = [
            ("Redis Baseline", self.test_redis_baseline),
            ("CVAT Environment", self.test_cvat_environment_variables),
            ("CVAT Redis Connection", self.test_cvat_redis_connection),
            ("rqscheduler Process", self.test_cvat_rqscheduler_process),
            ("CVAT Health Check", self.test_cvat_health_endpoint)
        ]
        
        passed_tests = 0
        for test_name, test_func in tests:
            try:
                success = test_func()
                if success:
                    passed_tests += 1
            except Exception as e:
                self.log_result(f"{test_name} (Exception)", False, "Unexpected error", str(e))
        
        # Print summary
        elapsed_time = time.time() - start_time
        print(f"\n" + "=" * 60)
        print(f"🔍 VERIFICATION SUMMARY")
        print(f"=" * 60)
        print(f"Tests passed: {passed_tests}/{len(tests)}")
        print(f"Success rate: {(passed_tests/len(tests)*100):.1f}%")
        print(f"Execution time: {elapsed_time:.1f} seconds")
        
        if passed_tests == len(tests):
            print("✅ ALL TESTS PASSED - CVAT Redis authentication working correctly!")
            return True
        else:
            print("❌ SOME TESTS FAILED - Redis authentication issues remain")
            return False
    
    def save_results(self, filename: str = "cvat_redis_auth_results.json"):
        """Save test results to file"""
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": len(self.test_results),
                "passed_tests": sum(1 for r in self.test_results if r["success"]),
                "success_rate": sum(1 for r in self.test_results if r["success"]) / len(self.test_results) * 100
            },
            "results": self.test_results
        }
        
        with open(filename, "w") as f:
            json.dump(results_data, f, indent=2)
        
        print(f"📊 Results saved to {filename}")

def main():
    """Main function"""
    print("🚀 CVAT Redis Authentication Verification")
    print("This script will verify that the Redis authentication fix works correctly.")
    
    verifier = CVATRedisAuthVerifier()
    
    try:
        success = verifier.run_full_verification()
        verifier.save_results()
        
        if success:
            print("\n🎉 Redis authentication fix verified successfully!")
            sys.exit(0)
        else:
            print("\n💥 Redis authentication issues detected!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during verification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()