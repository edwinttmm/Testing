#!/usr/bin/env python3
"""Test HIL API endpoints directly"""

import requests
import json
import sys

API_BASE = "http://localhost:8000"

def test_api_endpoint(endpoint, description):
    """Test a single API endpoint"""
    print(f"\n🔍 Testing: {description}")
    print(f"   Endpoint: {endpoint}")
    
    try:
        response = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response type: {type(data)}")
            
            if isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
                
                # Check for detection events
                if 'detection_events' in data:
                    events = data['detection_events']
                    print(f"   ✅ Detection events found: {len(events)}")
                    
                    if events:
                        first_event = events[0]
                        print(f"   First event keys: {list(first_event.keys())}")
                        
                        # Check voltage data
                        voltage_keys = [k for k in first_event.keys() if 'voltage' in k.lower()]
                        print(f"   Voltage-related keys: {voltage_keys}")
                        
                        for key in voltage_keys:
                            value = first_event.get(key)
                            print(f"   {key}: {value}")
                
                # Check summary data
                if 'summary' in data:
                    summary = data['summary']
                    print(f"   Summary: {summary}")
                
            print(f"   ✅ Success")
            
        else:
            print(f"   ❌ Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.text}")
                
    except Exception as e:
        print(f"   ❌ Exception: {e}")

def main():
    print("🚀 HIL API Test Suite")
    
    # Test different endpoints
    test_api_endpoint("/api/test-sessions", "List test sessions")
    
    # Test known session with events
    session_id = "b8a345a5-582a-4a55-a409-c7a8a06408f9"
    test_api_endpoint(f"/api/test-sessions/{session_id}/results", f"HIL results for session {session_id}")
    
    # Test events endpoint
    test_api_endpoint(f"/api/test-sessions/{session_id}/events", f"Events for session {session_id}")
    
    # Test the new latest-with-events endpoint
    test_api_endpoint("/api/test-sessions/latest-with-events", "Latest session with events")
    
    print("\n✅ API test suite completed")

if __name__ == "__main__":
    main()