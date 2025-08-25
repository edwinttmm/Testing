#!/usr/bin/env python3
"""
CORS and External IP Connectivity Test Script
Tests API accessibility from external IP 155.138.239.131
"""

import requests
import json
from typing import Dict, Any

def test_cors_headers(base_url: str) -> Dict[str, Any]:
    """Test CORS headers for external IP access"""
    print(f"🔍 Testing CORS configuration for {base_url}")
    
    # Test preflight OPTIONS request
    headers = {
        'Origin': 'http://155.138.239.131:3000',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'Content-Type,Authorization'
    }
    
    results = {}
    
    try:
        # Test OPTIONS request (preflight)
        response = requests.options(f"{base_url}/health", headers=headers, timeout=10)
        results['options_status'] = response.status_code
        results['cors_origin'] = response.headers.get('Access-Control-Allow-Origin', 'NOT SET')
        results['cors_methods'] = response.headers.get('Access-Control-Allow-Methods', 'NOT SET')
        results['cors_headers'] = response.headers.get('Access-Control-Allow-Headers', 'NOT SET')
        results['cors_credentials'] = response.headers.get('Access-Control-Allow-Credentials', 'NOT SET')
        
        print(f"  ✅ OPTIONS request: {response.status_code}")
        print(f"  🌐 CORS Origin: {results['cors_origin']}")
        print(f"  📋 CORS Methods: {results['cors_methods']}")
        print(f"  📝 CORS Headers: {results['cors_headers']}")
        print(f"  🔐 CORS Credentials: {results['cors_credentials']}")
        
        # Test actual GET request with origin
        get_response = requests.get(f"{base_url}/health", headers={'Origin': 'http://155.138.239.131:3000'}, timeout=10)
        results['get_status'] = get_response.status_code
        results['get_cors_origin'] = get_response.headers.get('Access-Control-Allow-Origin', 'NOT SET')
        
        print(f"  ✅ GET request: {get_response.status_code}")
        print(f"  🌐 GET CORS Origin: {results['get_cors_origin']}")
        
        # Check if CORS allows the external IP
        cors_valid = (
            results['cors_origin'] in ['*', 'http://155.138.239.131:3000'] or
            results['get_cors_origin'] in ['*', 'http://155.138.239.131:3000']
        )
        results['cors_valid_for_external_ip'] = cors_valid
        
        if cors_valid:
            print("  ✅ CORS configuration allows external IP access")
        else:
            print("  ❌ CORS configuration may block external IP access")
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Connection failed: {e}")
        results['error'] = str(e)
    
    return results

def test_api_endpoints(base_url: str) -> Dict[str, Any]:
    """Test key API endpoints for external access"""
    print(f"\n🔍 Testing API endpoints for {base_url}")
    
    endpoints = [
        ('/health', 'Health Check'),
        ('/docs', 'API Documentation'),
        ('/projects', 'Projects List'),
        ('/videos', 'Videos List'),
    ]
    
    results = {}
    
    for endpoint, description in endpoints:
        try:
            headers = {'Origin': 'http://155.138.239.131:3000'}
            response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
            
            status = "✅ ACCESSIBLE" if response.status_code < 400 else "⚠️  ERROR"
            print(f"  {status} {description}: {response.status_code}")
            
            results[endpoint] = {
                'status_code': response.status_code,
                'accessible': response.status_code < 400,
                'cors_origin': response.headers.get('Access-Control-Allow-Origin', 'NOT SET')
            }
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ FAILED {description}: {e}")
            results[endpoint] = {'error': str(e), 'accessible': False}
    
    return results

def test_websocket_accessibility(ws_url: str) -> Dict[str, Any]:
    """Test WebSocket endpoint accessibility"""
    print(f"\n🔍 Testing WebSocket accessibility for {ws_url}")
    
    try:
        # Test if the WebSocket endpoint responds to HTTP requests
        # (WebSocket endpoints typically return 400 or 426 for HTTP requests)
        response = requests.get(ws_url.replace('ws://', 'http://'), timeout=5)
        
        # 400 or 426 indicates WebSocket endpoint is accessible
        if response.status_code in [400, 426]:
            print("  ✅ WebSocket endpoint is accessible")
            return {'accessible': True, 'status_code': response.status_code}
        else:
            print(f"  ⚠️  WebSocket endpoint returned unexpected status: {response.status_code}")
            return {'accessible': True, 'status_code': response.status_code, 'note': 'Unexpected but accessible'}
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ WebSocket endpoint not accessible: {e}")
        return {'accessible': False, 'error': str(e)}

def main():
    print("🚀 AI Model Validation Platform - CORS & External IP Test")
    print("=" * 60)
    
    # Configuration
    backend_url = "http://155.138.239.131:8000"
    frontend_url = "http://155.138.239.131:3000"
    websocket_url = "ws://155.138.239.131:8000"
    
    # Run tests
    test_results = {}
    
    # Test backend CORS
    test_results['backend_cors'] = test_cors_headers(backend_url)
    
    # Test API endpoints
    test_results['api_endpoints'] = test_api_endpoints(backend_url)
    
    # Test WebSocket
    test_results['websocket'] = test_websocket_accessibility(websocket_url)
    
    # Test frontend accessibility
    print(f"\n🔍 Testing frontend accessibility for {frontend_url}")
    try:
        response = requests.get(frontend_url, timeout=10)
        frontend_accessible = response.status_code == 200
        print(f"  {'✅' if frontend_accessible else '❌'} Frontend: {response.status_code}")
        test_results['frontend'] = {'accessible': frontend_accessible, 'status_code': response.status_code}
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Frontend not accessible: {e}")
        test_results['frontend'] = {'accessible': False, 'error': str(e)}
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    # Check overall CORS status
    cors_working = False
    if 'backend_cors' in test_results and 'cors_valid_for_external_ip' in test_results['backend_cors']:
        cors_working = test_results['backend_cors']['cors_valid_for_external_ip']
    
    print(f"🌐 CORS Configuration: {'✅ WORKING' if cors_working else '❌ NEEDS FIX'}")
    print(f"🔗 Backend API: {'✅ ACCESSIBLE' if any(ep.get('accessible', False) for ep in test_results.get('api_endpoints', {}).values()) else '❌ NOT ACCESSIBLE'}")
    print(f"🔌 WebSocket: {'✅ ACCESSIBLE' if test_results.get('websocket', {}).get('accessible', False) else '❌ NOT ACCESSIBLE'}")
    print(f"🖥️  Frontend: {'✅ ACCESSIBLE' if test_results.get('frontend', {}).get('accessible', False) else '❌ NOT ACCESSIBLE'}")
    
    # Save detailed results
    with open('/home/user/Testing/ai-model-validation-platform/cors-test-results.json', 'w') as f:
        json.dump(test_results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: cors-test-results.json")
    
    if cors_working:
        print("\n🎉 CORS is properly configured for external IP access!")
    else:
        print("\n⚠️  CORS configuration needs attention for external IP access.")
        print("   Check backend CORS origins include: http://155.138.239.131:3000")

if __name__ == "__main__":
    main()