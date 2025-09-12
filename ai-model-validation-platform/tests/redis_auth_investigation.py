#!/usr/bin/env python3
"""
Redis Authentication Investigation Script
Tests Redis connection with different configurations to identify CVAT auth issues
"""

import redis
import os
import sys
import time
from typing import Dict, List, Optional

class RedisAuthTester:
    def __init__(self):
        self.redis_host = "redis"
        self.redis_port = 6379
        self.redis_password = "secure_redis_password"
        self.results = []
        
    def test_connection(self, description: str, **kwargs) -> Dict:
        """Test Redis connection with given parameters"""
        result = {
            "description": description,
            "success": False,
            "error": None,
            "config": kwargs
        }
        
        try:
            client = redis.Redis(**kwargs)
            response = client.ping()
            result["success"] = response is True
            result["response"] = str(response)
        except Exception as e:
            result["error"] = str(e)
            
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Run comprehensive Redis authentication tests"""
        print("🔍 Starting Redis Authentication Investigation")
        print("=" * 60)
        
        # Test 1: No authentication
        print("\n1. Testing Redis connection WITHOUT authentication...")
        self.test_connection(
            "No auth connection",
            host=self.redis_host,
            port=self.redis_port,
            decode_responses=True
        )
        
        # Test 2: With password
        print("\n2. Testing Redis connection WITH password...")
        self.test_connection(
            "Password auth connection",
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            decode_responses=True
        )
        
        # Test 3: URL-based connection (backend style)
        print("\n3. Testing Redis URL connection (backend style)...")
        redis_url = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        try:
            client = redis.from_url(redis_url, decode_responses=True)
            response = client.ping()
            result = {
                "description": "URL-based connection",
                "success": response is True,
                "error": None,
                "config": {"url": redis_url},
                "response": str(response)
            }
        except Exception as e:
            result = {
                "description": "URL-based connection",
                "success": False,
                "error": str(e),
                "config": {"url": redis_url}
            }
        self.results.append(result)
        
        # Test 4: Different auth methods for CVAT simulation
        print("\n4. Testing CVAT-style environment variables...")
        cvat_configs = [
            {
                "description": "CVAT env: CVAT_REDIS_HOST + CVAT_REDIS_PASSWORD",
                "host": os.getenv("CVAT_REDIS_HOST", self.redis_host),
                "port": self.redis_port,
                "password": os.getenv("CVAT_REDIS_PASSWORD", self.redis_password),
                "decode_responses": True
            },
            {
                "description": "CVAT env: Redis URL format",
                "url": f"redis://:{os.getenv('CVAT_REDIS_PASSWORD', self.redis_password)}@{os.getenv('CVAT_REDIS_HOST', self.redis_host)}:{self.redis_port}",
                "decode_responses": True
            }
        ]
        
        for config in cvat_configs:
            if "url" in config:
                try:
                    client = redis.from_url(config["url"], decode_responses=True)
                    response = client.ping()
                    result = {
                        "description": config["description"],
                        "success": response is True,
                        "error": None,
                        "config": config,
                        "response": str(response)
                    }
                except Exception as e:
                    result = {
                        "description": config["description"],
                        "success": False,
                        "error": str(e),
                        "config": config
                    }
            else:
                result = self.test_connection(config["description"], **{k: v for k, v in config.items() if k != "description"})
        
        self.print_results()
        
    def print_results(self):
        """Print test results in a formatted way"""
        print("\n" + "=" * 60)
        print("🔍 REDIS AUTHENTICATION TEST RESULTS")
        print("=" * 60)
        
        success_count = sum(1 for r in self.results if r["success"])
        total_count = len(self.results)
        
        for i, result in enumerate(self.results, 1):
            status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
            print(f"\n{i}. {result['description']}: {status}")
            
            if result["success"]:
                print(f"   Response: {result.get('response', 'PONG')}")
            else:
                print(f"   Error: {result['error']}")
                
            # Print config (redact password for security)
            config_str = str(result["config"]).replace(self.redis_password, "***REDACTED***")
            print(f"   Config: {config_str}")
        
        print(f"\n📊 SUMMARY: {success_count}/{total_count} tests passed")
        
        if success_count < total_count:
            print("\n🚨 AUTHENTICATION ISSUES DETECTED!")
            self.suggest_fixes()
        else:
            print("\n✅ All authentication methods working correctly!")
    
    def suggest_fixes(self):
        """Suggest fixes based on test results"""
        print("\n🔧 SUGGESTED FIXES:")
        
        failed_tests = [r for r in self.results if not r["success"]]
        
        for test in failed_tests:
            print(f"\nFailed: {test['description']}")
            if "Authentication required" in str(test.get("error", "")):
                print("  → Redis requires authentication but none was provided")
                print("  → Ensure REDIS_PASSWORD environment variable is set")
                print("  → Use redis://:{password}@host:port format for URLs")
            elif "Connection refused" in str(test.get("error", "")):
                print("  → Redis server not accessible")
                print("  → Check if Redis container is running")
                print("  → Verify network connectivity")
            elif "Name or service not known" in str(test.get("error", "")):
                print("  → Hostname resolution failed")
                print("  → Ensure containers are on same network")
                print("  → Check REDIS_HOST environment variable")

def main():
    """Main function to run the investigation"""
    print("🚀 Redis Authentication Investigation Tool")
    print("This tool will test various Redis connection methods")
    print("to identify authentication issues in the CVAT integration.")
    
    # Check if we're running in a container
    if os.path.exists("/.dockerenv"):
        print("✅ Running inside Docker container")
    else:
        print("⚠️  Running outside Docker - may not reflect container environment")
    
    # Print environment variables
    print("\n📋 Environment Variables:")
    redis_vars = {k: v for k, v in os.environ.items() if "REDIS" in k.upper()}
    if redis_vars:
        for key, value in redis_vars.items():
            # Redact password for security
            if "password" in key.lower():
                value = "***REDACTED***"
            print(f"   {key}={value}")
    else:
        print("   No Redis environment variables found")
    
    # Run tests
    tester = RedisAuthTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()