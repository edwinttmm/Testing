#!/usr/bin/env python3
"""
API Connectivity Test for URL Configuration Fixes
Tests that frontend can properly communicate with backend using correct URLs
"""

import requests
import json
import time
from typing import Dict, Any
import traceback

def test_api_connectivity(base_url: str) -> Dict[str, Any]:
    """Test API connectivity to backend"""
    results = {
        'base_url': base_url,
        'health_check': False,
        'cors_check': False,
        'video_endpoint_check': False,
        'errors': [],
        'response_times': {}
    }
    
    try:
        # 1. Health Check
        print(f"🔍 Testing health endpoint: {base_url}/health")
        start_time = time.time()
        health_response = requests.get(f"{base_url}/health", timeout=10)
        health_time = (time.time() - start_time) * 1000
        
        results['response_times']['health'] = f"{health_time:.2f}ms"
        
        if health_response.status_code == 200:
            results['health_check'] = True
            print(f"✅ Health check passed ({health_time:.2f}ms)")
            print(f"   Response: {health_response.json()}")
        else:
            results['errors'].append(f"Health check failed: {health_response.status_code}")
            print(f"❌ Health check failed: {health_response.status_code}")
            
    except Exception as e:
        results['errors'].append(f"Health check error: {str(e)}")
        print(f"❌ Health check error: {str(e)}")
    
    try:
        # 2. CORS Check (preflight request)
        print(f"🔍 Testing CORS: OPTIONS {base_url}/api/projects")
        start_time = time.time()
        cors_response = requests.options(
            f"{base_url}/api/projects", 
            headers={
                'Origin': 'http://155.138.239.131:3000',
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type'
            },
            timeout=10
        )
        cors_time = (time.time() - start_time) * 1000
        
        results['response_times']['cors'] = f"{cors_time:.2f}ms"
        
        if cors_response.status_code in [200, 204]:
            cors_headers = cors_response.headers
            if 'Access-Control-Allow-Origin' in cors_headers:
                results['cors_check'] = True
                print(f"✅ CORS check passed ({cors_time:.2f}ms)")
                print(f"   Access-Control-Allow-Origin: {cors_headers.get('Access-Control-Allow-Origin')}")
            else:
                results['errors'].append("CORS headers missing")
                print("❌ CORS check failed: Access-Control-Allow-Origin header missing")
        else:
            results['errors'].append(f"CORS check failed: {cors_response.status_code}")
            print(f"❌ CORS check failed: {cors_response.status_code}")
            
    except Exception as e:
        results['errors'].append(f"CORS check error: {str(e)}")
        print(f"❌ CORS check error: {str(e)}")
    
    try:
        # 3. Video endpoint check (for URL conversion testing)
        print(f"🔍 Testing video/projects endpoint: {base_url}/api/projects")
        start_time = time.time()
        projects_response = requests.get(
            f"{base_url}/api/projects", 
            headers={'Origin': 'http://155.138.239.131:3000'},
            timeout=10
        )
        projects_time = (time.time() - start_time) * 1000
        
        results['response_times']['projects'] = f"{projects_time:.2f}ms"
        
        if projects_response.status_code == 200:
            results['video_endpoint_check'] = True
            projects_data = projects_response.json()
            print(f"✅ Projects endpoint check passed ({projects_time:.2f}ms)")
            print(f"   Found {len(projects_data)} projects")
            
            # Check if any projects have video URLs
            video_urls_found = []
            for project in projects_data:
                if isinstance(project, dict) and 'videos' in project:
                    for video in project['videos']:
                        if isinstance(video, dict) and 'url' in video:
                            video_urls_found.append(video['url'])
            
            if video_urls_found:
                print(f"   Video URLs found: {len(video_urls_found)}")
                for url in video_urls_found[:3]:  # Show first 3
                    print(f"     - {url}")
                    
                # Check if URLs use correct base URL
                correct_urls = [url for url in video_urls_found if '155.138.239.131:8000' in url]
                localhost_urls = [url for url in video_urls_found if 'localhost:8000' in url]
                
                print(f"   URLs using correct base (155.138.239.131:8000): {len(correct_urls)}")
                print(f"   URLs using localhost (need fixing): {len(localhost_urls)}")
                
        else:
            results['errors'].append(f"Projects endpoint failed: {projects_response.status_code}")
            print(f"❌ Projects endpoint failed: {projects_response.status_code}")
            
    except Exception as e:
        results['errors'].append(f"Projects endpoint error: {str(e)}")
        print(f"❌ Projects endpoint error: {str(e)}")
    
    return results

def main():
    """Main test function"""
    print("🚀 API Connectivity Test for URL Configuration Fixes")
    print("=" * 60)
    
    # Test both localhost and external IP configurations
    test_scenarios = [
        ("Localhost Backend", "http://localhost:8000"),
        ("External IP Backend", "http://155.138.239.131:8000")
    ]
    
    all_results = {}
    
    for scenario_name, base_url in test_scenarios:
        print(f"\n📋 Testing {scenario_name}: {base_url}")
        print("-" * 40)
        
        results = test_api_connectivity(base_url)
        all_results[scenario_name] = results
        
        # Summary for this scenario
        passed_checks = sum([
            results['health_check'],
            results['cors_check'], 
            results['video_endpoint_check']
        ])
        total_checks = 3
        
        print(f"\n📊 {scenario_name} Summary: {passed_checks}/{total_checks} checks passed")
        if results['errors']:
            print(f"   Errors: {len(results['errors'])}")
            for error in results['errors']:
                print(f"     - {error}")
    
    # Overall summary
    print(f"\n🏁 Overall Test Results")
    print("=" * 60)
    
    for scenario_name, results in all_results.items():
        passed_checks = sum([
            results['health_check'],
            results['cors_check'], 
            results['video_endpoint_check']
        ])
        total_checks = 3
        status = "✅ PASS" if passed_checks == total_checks else f"⚠️  {passed_checks}/{total_checks}"
        print(f"{scenario_name}: {status}")
        
        if results['response_times']:
            times = [f"{k}={v}" for k, v in results['response_times'].items()]
            print(f"  Response times: {', '.join(times)}")
    
    # Save results to file
    with open('/home/rigade/Testing/ai-model-validation-platform/tests/api-connectivity-results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n📁 Results saved to: tests/api-connectivity-results.json")
    
    # Return success if at least external IP backend works
    external_ip_results = all_results.get("External IP Backend", {})
    if external_ip_results.get('health_check') and external_ip_results.get('cors_check'):
        print(f"\n✅ SUCCESS: External IP backend connectivity working!")
        return 0
    else:
        print(f"\n❌ FAILURE: External IP backend connectivity issues detected!")
        return 1

if __name__ == "__main__":
    exit(main())