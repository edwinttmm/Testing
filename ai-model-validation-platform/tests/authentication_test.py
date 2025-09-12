#!/usr/bin/env python3
"""
Authentication and Authorization System Test
"""

import requests
import json
import sys

def test_authentication_endpoints():
    """Test authentication-related endpoints"""
    base_url = "http://localhost:8000"
    results = []
    
    print("🔐 Authentication System Validation")
    print("=" * 40)
    
    # Test for common auth endpoints
    auth_endpoints = [
        "/auth/login",
        "/auth/register", 
        "/auth/logout",
        "/auth/token",
        "/auth/verify",
        "/api/auth/login",
        "/api/auth/register",
        "/login",
        "/register"
    ]
    
    print("🔍 Testing for authentication endpoints...")
    found_endpoints = []
    
    for endpoint in auth_endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=5)
            # Don't expect 200 for auth endpoints without credentials
            if response.status_code in [200, 401, 405, 422]:  # Valid auth responses
                found_endpoints.append(endpoint)
                print(f"✅ Found: {endpoint} (Status: {response.status_code})")
            elif response.status_code == 404:
                print(f"❌ Not found: {endpoint}")
            else:
                print(f"❓ Unexpected: {endpoint} (Status: {response.status_code})")
                
        except Exception as e:
            print(f"❌ Error testing {endpoint}: {e}")
    
    # Test API documentation for auth info
    print("\n📚 Checking API documentation for auth info...")
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        docs_content = response.text.lower()
        
        auth_keywords = ["authentication", "authorization", "login", "token", "bearer", "jwt", "oauth"]
        found_auth_features = []
        
        for keyword in auth_keywords:
            if keyword in docs_content:
                found_auth_features.append(keyword)
        
        if found_auth_features:
            print(f"✅ Auth features found in docs: {', '.join(found_auth_features)}")
        else:
            print("❓ No explicit auth features found in API docs")
            
    except Exception as e:
        print(f"❌ Error checking API docs: {e}")
    
    # Test security headers
    print("\n🛡️ Testing security headers...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        headers = response.headers
        
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'"
        }
        
        present_headers = []
        missing_headers = []
        
        for header, expected_value in security_headers.items():
            if header in headers:
                present_headers.append(header)
                print(f"✅ {header}: {headers[header]}")
            else:
                missing_headers.append(header)
                print(f"❌ Missing: {header}")
        
        print(f"\nSecurity headers summary: {len(present_headers)}/{len(security_headers)} present")
        
    except Exception as e:
        print(f"❌ Error checking security headers: {e}")
    
    # Test for CORS configuration
    print("\n🌐 Testing CORS configuration...")
    try:
        response = requests.options(f"{base_url}/api/projects", timeout=5)
        cors_headers = {
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods", 
            "Access-Control-Allow-Headers"
        }
        
        found_cors = []
        for header in cors_headers:
            if header in response.headers:
                found_cors.append(f"{header}: {response.headers[header]}")
        
        if found_cors:
            print("✅ CORS headers found:")
            for header in found_cors:
                print(f"   {header}")
        else:
            print("❓ No CORS headers found")
            
    except Exception as e:
        print(f"❌ Error testing CORS: {e}")
    
    # Summary
    print(f"\n📊 Authentication Test Summary")
    print("=" * 30)
    
    if found_endpoints:
        print(f"✅ Authentication endpoints found: {len(found_endpoints)}")
        print("   This indicates an authentication system is present")
        auth_status = "PRESENT"
    else:
        print("❓ No dedicated authentication endpoints found")
        print("   System may use implicit auth or be in development")
        auth_status = "NOT_DETECTED"
    
    return {
        "status": auth_status,
        "endpoints_found": found_endpoints,
        "security_headers": present_headers if 'present_headers' in locals() else [],
        "cors_enabled": len(found_cors) > 0 if 'found_cors' in locals() else False
    }

if __name__ == "__main__":
    result = test_authentication_endpoints()
    
    # Save results
    with open("authentication_test_results.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\n💾 Results saved to authentication_test_results.json")
    print(f"🔐 Authentication System Status: {result['status']}")