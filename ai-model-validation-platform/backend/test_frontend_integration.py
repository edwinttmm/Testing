#!/usr/bin/env python3
"""
Test Frontend Integration
This script simulates the frontend's API call to verify ground truth data integration.
"""

import requests
import json
import sys

def test_frontend_integration():
    """Test that the frontend can receive ground truth data"""
    print("🔍 Testing Frontend Integration...")
    
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ ERROR: HTTP {response.status_code}")
            return False
        
        result = response.json()
        
        # Test what the frontend should see
        print(f"🎯 Frontend Ground Truth Integration Test:")
        
        # Check main response structure
        if 'ground_truth_comparison' in result:
            gt_comparison = result['ground_truth_comparison']
            print(f"✅ ground_truth_comparison section found")
            
            # Check required fields for frontend UI
            required_fields = [
                'ground_truth_events_available',
                'total_detections', 
                'events_with_matches',
                'average_confidence_score'
            ]
            
            for field in required_fields:
                if field in gt_comparison:
                    value = gt_comparison[field]
                    print(f"   ✅ {field}: {value}")
                    
                    # Validate the key fix
                    if field == 'ground_truth_events_available' and value == 24:
                        print(f"   🎉 CRITICAL FIX CONFIRMED: Ground Truth Events = {value} (not 0!)")
                else:
                    print(f"   ❌ Missing {field}")
        else:
            print(f"❌ ground_truth_comparison section missing")
            return False
        
        # Check detection events for timing data
        detection_events = result.get('detection_events', [])
        if detection_events:
            first_event = detection_events[0]
            if 'timing_synchronization' in first_event:
                timing = first_event['timing_synchronization']
                print(f"✅ timing_synchronization found in detection events")
                print(f"   - timing_quality: {timing.get('timing_quality')}")
                print(f"   - confidence_score: {timing.get('confidence_score')}")
                print(f"   - ground_truth_available: {timing.get('ground_truth_available')}")
            else:
                print(f"❌ timing_synchronization missing from detection events")
        
        # Frontend display simulation
        gt_events_count = result.get('ground_truth_comparison', {}).get('ground_truth_events_available', 0)
        total_detections = result.get('ground_truth_comparison', {}).get('total_detections', 0)
        
        print(f"\n🖥️  Frontend UI will display:")
        print(f"   Ground Truth Events: {gt_events_count}")
        print(f"   Total Detections: {total_detections}")
        
        if gt_events_count > 0:
            print(f"   Status: ✅ SUCCESS - No 'No Ground Truth Events Available' message!")
        else:
            print(f"   Status: ❌ FAILURE - Will still show 'No Ground Truth Events Available'")
        
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Frontend Integration Test")
    print("=" * 50)
    
    test_frontend_integration()

if __name__ == "__main__":
    main()