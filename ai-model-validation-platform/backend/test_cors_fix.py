#!/usr/bin/env python3
"""
Standalone test for video validation CORS issue
"""
import sys
import traceback
import requests
import json
from datetime import datetime

def test_video_validation():
    base_url = "http://localhost:8000"
    video_id = "29833bc4-276f-4174-9842-aeca8a2ea025"
    
    headers = {
        'Origin': 'http://localhost:3000',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'validation_type': 'manual',
        'notes': 'CORS test'
    }
    
    print(f"Testing CORS for video validation endpoint...")
    print(f"Video ID: {video_id}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload}")
    print("-" * 50)
    
    try:
        # Test PATCH (working)
        print("1. Testing PATCH method (should work):")
        response = requests.patch(
            f"{base_url}/api/videos/{video_id}/validate",
            headers=headers,
            json=payload,
            timeout=10
        )
        print(f"PATCH Status: {response.status_code}")
        print(f"PATCH CORS: {response.headers.get('Access-Control-Allow-Origin', 'MISSING')}")
        print(f"PATCH Response: {response.text[:200]}")
        print()
        
        # Test POST (problematic)
        print("2. Testing POST method (having CORS issue):")
        response = requests.post(
            f"{base_url}/api/videos/{video_id}/validate",
            headers=headers,
            json=payload,
            timeout=10
        )
        print(f"POST Status: {response.status_code}")
        print(f"POST CORS: {response.headers.get('Access-Control-Allow-Origin', 'MISSING')}")
        print(f"POST Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ POST SUCCESS - CORS issue is fixed!")
        else:
            print(f"❌ POST FAILED - Status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_video_validation()