#!/usr/bin/env python3
"""
Test Time-Based Ground Truth Matching
This script tests if our time-based matching fix is working correctly.
"""

import requests
import json
import sys

def test_time_based_matching():
    """Test if time-based ground truth matching is working"""
    print("🧪 Testing Time-Based Ground Truth Matching...")
    
    # Test with known session ID
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        print(f"📡 Making request to: {url}")
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        result = response.json()
        detection_events = result.get('detection_events', [])
        
        print(f"📊 Found {len(detection_events)} detection events")
        
        # Check for time-based matching
        matched_count = 0
        time_based_matches = 0
        video_timestamp_count = 0
        
        for event in detection_events:
            event_id = event.get('id')
            video_timestamp = event.get('video_relative_timestamp')
            matched_gt = event.get('matched_ground_truth')
            
            if video_timestamp is not None:
                video_timestamp_count += 1
                
            if matched_gt is not None:
                matched_count += 1
                
                # Check if this looks like a time-based match
                if video_timestamp is not None:
                    time_based_matches += 1
                    print(f"🎯 Time-based match: Event {event_id} at {video_timestamp:.3f}s matched to GT")
                else:
                    print(f"📄 Frame-based match: Event {event_id} (no video timestamp)")
        
        print(f"\n📈 MATCHING RESULTS:")
        print(f"   📹 Events with video timestamps: {video_timestamp_count}/{len(detection_events)}")
        print(f"   🎯 Total matched events: {matched_count}/{len(detection_events)}")
        print(f"   ⏱️ Time-based matches: {time_based_matches}/{matched_count} matched events")
        
        if matched_count > 0:
            print(f"✅ SUCCESS: Ground truth matching is working!")
            print(f"   Time-based matching rate: {time_based_matches/matched_count*100:.1f}%")
            return True
        else:
            print(f"❌ FAILURE: No ground truth matches found")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"🌐 Network error: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return False

def main():
    print("🚀 Time-Based Ground Truth Matching Test")
    print("=" * 50)
    
    success = test_time_based_matching()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Time-based matching test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Time-based matching test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()