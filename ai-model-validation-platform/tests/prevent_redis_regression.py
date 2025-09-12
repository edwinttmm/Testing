#!/usr/bin/env python3
"""
Redis Authentication Regression Prevention Script
Runs automated tests to ensure Redis authentication continues working
"""

import docker
import json
import sys
import time
from datetime import datetime

def test_cvat_redis_health():
    """
    Comprehensive CVAT Redis authentication health check
    Returns True if all tests pass, False otherwise
    """
    client = docker.from_env()
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "overall_success": True
    }
    
    def log_test(name, success, details, error=None):
        result = {
            "test": name,
            "success": success, 
            "details": details,
            "error": error
        }
        results["tests"].append(result)
        if not success:
            results["overall_success"] = False
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {name}: {details}")
        if error:
            print(f"    Error: {error}")
    
    try:
        # Test 1: CVAT container exists and is running
        try:
            cvat = client.containers.get("ai_validation_cvat")
            if cvat.status != "running":
                log_test("CVAT Container Status", False, f"Container status: {cvat.status}")
                return results
            log_test("CVAT Container Status", True, "Container running")
        except docker.errors.NotFound:
            log_test("CVAT Container Status", False, "CVAT container not found")
            return results
        
        # Test 2: Environment variables present
        env_result = cvat.exec_run("env | grep -E '(RQ_REDIS_|CVAT_REDIS_|REDIS_)' | wc -l")
        env_count = int(env_result.output.decode().strip())
        if env_count >= 8:  # Should have at least 8 Redis env vars
            log_test("Redis Environment Variables", True, f"{env_count} Redis env vars found")
        else:
            log_test("Redis Environment Variables", False, f"Only {env_count} Redis env vars found")
        
        # Test 3: rqscheduler process running with password
        ps_result = cvat.exec_run("ps aux | grep rqscheduler | grep -v grep")
        ps_output = ps_result.output.decode()
        if "--password" in ps_output:
            log_test("rqscheduler Password Auth", True, "rqscheduler using password authentication")
        else:
            log_test("rqscheduler Password Auth", False, "rqscheduler not using password authentication")
        
        # Test 4: Supervisord status for Redis processes
        status_result = cvat.exec_run("supervisorctl status | grep -E '(rqscheduler|rqworker)' | grep RUNNING | wc -l")
        running_count = int(status_result.output.decode().strip())
        if running_count >= 3:  # Should have at least rqscheduler + 2 workers running
            log_test("Redis Processes Running", True, f"{running_count} Redis processes running")
        else:
            log_test("Redis Processes Running", False, f"Only {running_count} Redis processes running")
        
        # Test 5: Direct Redis connection test
        redis_test_script = '''
import redis
import os
try:
    client = redis.Redis(
        host=os.getenv("RQ_REDIS_HOST", "redis"),
        port=6379, 
        password=os.getenv("RQ_REDIS_PASSWORD"),
        decode_responses=True
    )
    result = client.ping()
    print(f"SUCCESS:{result}")
except Exception as e:
    print(f"ERROR:{e}")
'''
        
        redis_result = cvat.exec_run(f"python -c \"{redis_test_script}\"")
        redis_output = redis_result.output.decode()
        if "SUCCESS:True" in redis_output:
            log_test("Direct Redis Connection", True, "Redis ping successful")
        else:
            log_test("Direct Redis Connection", False, f"Redis connection failed: {redis_output}")
        
        # Test 6: Check for authentication errors in logs
        log_result = cvat.exec_run("tail -100 /tmp/supervisor.log | grep -i 'authentication' || echo 'NO_AUTH_ERRORS'")
        log_output = log_result.output.decode()
        if "NO_AUTH_ERRORS" in log_output:
            log_test("Authentication Error Check", True, "No authentication errors in logs")
        else:
            log_test("Authentication Error Check", False, f"Authentication errors found: {log_output}")
        
        return results
        
    except Exception as e:
        log_test("Overall Health Check", False, "Unexpected error during testing", str(e))
        return results

def main():
    print("🔍 CVAT Redis Authentication Regression Test")
    print("=" * 60)
    
    results = test_cvat_redis_health()
    
    # Print summary
    passed_tests = sum(1 for test in results["tests"] if test["success"])
    total_tests = len(results["tests"])
    
    print(f"\n📊 SUMMARY:")
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(f"Success rate: {(passed_tests/total_tests*100):.1f}%")
    
    # Save results
    with open("redis_regression_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    if results["overall_success"]:
        print("✅ ALL TESTS PASSED - Redis authentication working correctly!")
        print("🛡️ No regression detected.")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Redis authentication regression detected!")
        print("🚨 Manual investigation required.")
        sys.exit(1)

if __name__ == "__main__":
    main()