#!/usr/bin/env python3
"""
Test Enhanced HIL Results Endpoint Fix
This script tests the enhanced HIL results endpoint with our timing synchronization fix.
"""

import requests
import sys
import traceback

def test_enhanced_hil_endpoint():
    """Test the enhanced HIL results endpoint"""
    print("🧪 Testing Enhanced HIL Results Endpoint...")
    
    # Test with a known test session ID
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"  # From earlier curl test
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        print(f"📡 Making request to: {url}")
        response = requests.get(url, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📄 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Enhanced HIL results endpoint is working!")
            result = response.json()
            print(f"📋 Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            
            # Check for corrected results
            if isinstance(result, dict) and 'corrected_detection_results' in result:
                corrected_count = len(result['corrected_detection_results'])
                print(f"🎯 Found {corrected_count} corrected detection results")
                
                if corrected_count > 0:
                    first_result = result['corrected_detection_results'][0]
                    print(f"🔬 First result sample: {list(first_result.keys()) if isinstance(first_result, dict) else first_result}")
                    
                    # Check for timing data
                    if 'measured_breakdown' in first_result:
                        breakdown = first_result['measured_breakdown']
                        print(f"⏱️ Timing breakdown: {breakdown}")
                        
            return True
            
        elif response.status_code == 500:
            print("❌ ERROR: Server error (500) - our timing fix didn't work")
            try:
                error_detail = response.json()
                print(f"💥 Error details: {error_detail}")
            except:
                print(f"💥 Raw error response: {response.text}")
            return False
            
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"🌐 Network error: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        traceback.print_exc()
        return False

def main():
    print("🚀 Enhanced HIL Results Endpoint Test")
    print("=" * 50)
    
    success = test_enhanced_hil_endpoint()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed - timing synchronization fix needs more work")
        sys.exit(1)

if __name__ == "__main__":
    main()