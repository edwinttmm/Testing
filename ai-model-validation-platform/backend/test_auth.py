#!/usr/bin/env python3
"""
Authentication System Test Script
================================

Simple test script to verify that all authentication endpoints work correctly:
- User registration
- User login 
- JWT token validation
- User profile retrieval
- Token refresh
- User logout

Run this script after starting the FastAPI server to test the authentication system.
"""

import requests
import json
import sys
from datetime import datetime
import time

# Configuration
BASE_URL = "http://localhost:8000"
AUTH_BASE_URL = f"{BASE_URL}/auth"

# Test user data
TEST_USER = {
    "email": "test@example.com",
    "username": "testuser",
    "password": "TestPassword123!",
    "full_name": "Test User"
}

class AuthTester:
    """Authentication system tester"""
    
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def test_health_check(self):
        """Test authentication service health"""
        self.log("Testing authentication health endpoint...")
        try:
            response = self.session.get(f"{AUTH_BASE_URL}/health")
            if response.status_code == 200:
                health_data = response.json()
                self.log(f"✅ Auth health check passed: {health_data['status']}")
                return True
            else:
                self.log(f"❌ Auth health check failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Auth health check error: {e}", "ERROR")
            return False
    
    def test_register(self):
        """Test user registration"""
        self.log("Testing user registration...")
        try:
            response = self.session.post(
                f"{AUTH_BASE_URL}/register",
                json=TEST_USER,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.user_id = data["user"]["id"]
                
                self.log(f"✅ Registration successful for {data['user']['email']}")
                self.log(f"   User ID: {self.user_id}")
                self.log(f"   Token expires in: {data['expires_in']} seconds")
                return True
                
            elif response.status_code == 400:
                error_data = response.json()
                if "already registered" in error_data.get("detail", "").lower():
                    self.log("⚠️ User already exists, trying login instead...")
                    return self.test_login()
                else:
                    self.log(f"❌ Registration failed: {error_data['detail']}", "ERROR")
                    return False
            else:
                self.log(f"❌ Registration failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Registration error: {e}", "ERROR")
            return False
    
    def test_login(self):
        """Test user login"""
        self.log("Testing user login...")
        try:
            login_data = {
                "email": TEST_USER["email"],
                "password": TEST_USER["password"],
                "remember_me": False
            }
            
            response = self.session.post(
                f"{AUTH_BASE_URL}/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.user_id = data["user"]["id"]
                
                self.log(f"✅ Login successful for {data['user']['email']}")
                self.log(f"   User ID: {self.user_id}")
                self.log(f"   Token expires in: {data['expires_in']} seconds")
                return True
            else:
                error_data = response.json()
                self.log(f"❌ Login failed: {error_data['detail']}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Login error: {e}", "ERROR")
            return False
    
    def test_profile(self):
        """Test getting user profile"""
        self.log("Testing user profile retrieval...")
        if not self.access_token:
            self.log("❌ No access token available for profile test", "ERROR")
            return False
            
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.get(f"{AUTH_BASE_URL}/me", headers=headers)
            
            if response.status_code == 200:
                profile_data = response.json()
                self.log(f"✅ Profile retrieved successfully")
                self.log(f"   Email: {profile_data['email']}")
                self.log(f"   Username: {profile_data['username']}")
                self.log(f"   Full Name: {profile_data.get('full_name', 'Not set')}")
                self.log(f"   Active: {profile_data['is_active']}")
                self.log(f"   Verified: {profile_data['is_verified']}")
                return True
            else:
                error_data = response.json()
                self.log(f"❌ Profile retrieval failed: {error_data['detail']}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Profile retrieval error: {e}", "ERROR")
            return False
    
    def test_token_refresh(self):
        """Test JWT token refresh"""
        self.log("Testing token refresh...")
        if not self.refresh_token:
            self.log("❌ No refresh token available", "ERROR")
            return False
            
        try:
            refresh_data = {"refresh_token": self.refresh_token}
            
            response = self.session.post(
                f"{AUTH_BASE_URL}/refresh",
                json=refresh_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                old_access_token = self.access_token
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                
                self.log("✅ Token refresh successful")
                self.log(f"   New token expires in: {data['expires_in']} seconds")
                self.log(f"   Token changed: {old_access_token != self.access_token}")
                return True
            else:
                error_data = response.json()
                self.log(f"❌ Token refresh failed: {error_data['detail']}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Token refresh error: {e}", "ERROR")
            return False
    
    def test_logout(self):
        """Test user logout"""
        self.log("Testing user logout...")
        if not self.access_token:
            self.log("❌ No access token available for logout test", "ERROR")
            return False
            
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.post(f"{AUTH_BASE_URL}/logout", headers=headers)
            
            if response.status_code == 200:
                logout_data = response.json()
                self.log(f"✅ Logout successful: {logout_data['message']}")
                
                # Clear tokens
                self.access_token = None
                self.refresh_token = None
                return True
            else:
                error_data = response.json()
                self.log(f"❌ Logout failed: {error_data['detail']}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Logout error: {e}", "ERROR")
            return False
    
    def test_invalid_token(self):
        """Test behavior with invalid token"""
        self.log("Testing invalid token handling...")
        try:
            headers = {
                "Authorization": "Bearer invalid-token-12345",
                "Content-Type": "application/json"
            }
            
            response = self.session.get(f"{AUTH_BASE_URL}/me", headers=headers)
            
            if response.status_code == 401:
                self.log("✅ Invalid token properly rejected")
                return True
            else:
                self.log(f"❌ Invalid token not rejected properly: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Invalid token test error: {e}", "ERROR")
            return False
    
    def run_all_tests(self):
        """Run all authentication tests"""
        self.log("=" * 60)
        self.log("STARTING AUTHENTICATION SYSTEM TESTS")
        self.log("=" * 60)
        
        tests = [
            ("Health Check", self.test_health_check),
            ("User Registration/Login", self.test_register),
            ("User Profile Retrieval", self.test_profile),
            ("Token Refresh", self.test_token_refresh),
            ("User Logout", self.test_logout),
            ("Invalid Token Handling", self.test_invalid_token)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            self.log(f"\n--- Running: {test_name} ---")
            try:
                if test_func():
                    passed += 1
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                self.log(f"❌ Test {test_name} crashed: {e}", "ERROR")
        
        self.log("\n" + "=" * 60)
        self.log("AUTHENTICATION TEST RESULTS")
        self.log("=" * 60)
        self.log(f"Passed: {passed}/{total}")
        self.log(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            self.log("🎉 ALL TESTS PASSED! Authentication system is working correctly.")
            return True
        else:
            self.log("❌ Some tests failed. Check the errors above.")
            return False

def check_server_running():
    """Check if the FastAPI server is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Main test function"""
    print("🚀 AI Model Validation Platform - Authentication Test Suite")
    print(f"Testing server at: {BASE_URL}")
    
    # Check if server is running
    if not check_server_running():
        print(f"❌ Server is not running at {BASE_URL}")
        print("Please start the FastAPI server first:")
        print("   cd backend")
        print("   python main.py")
        sys.exit(1)
    
    # Run tests
    tester = AuthTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()