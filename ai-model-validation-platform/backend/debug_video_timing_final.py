#!/usr/bin/env python3
"""
Debug Video Timing Final Check
This script checks the final output to see why video timing isn't showing up.
"""

import requests
import json
import sys

def debug_video_timing_final():
    """Debug the final video timing in the API response"""
    print("🔍 Final Video Timing Debug...")
    
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ ERROR: HTTP {response.status_code}")
            return False
        
        result = response.json()
        detection_events = result.get('detection_events', [])
        
        print(f"📊 Found {len(detection_events)} detection events")
        
        if detection_events:
            first_event = detection_events[0]
            print(f"\n🔬 First Detection Event Analysis:")
            print(f"   event_id: {first_event.get('event_id')}")
            print(f"   frame_number: {first_event.get('frame_number')}")
            print(f"   video_relative_timestamp: {first_event.get('video_relative_timestamp')}")
            print(f"   video_frame_number: {first_event.get('video_frame_number')}")
            print(f"   detection_time: {first_event.get('detection_time')}")
            
            # Check if it has ground truth match info
            matched_gt = first_event.get('matched_ground_truth')
            print(f"   matched_ground_truth: {matched_gt}")
            
            # Check timing quality
            timing_sync = first_event.get('timing_synchronization', {})
            print(f"   timing_quality: {timing_sync.get('timing_quality')}")
            print(f"   confidence_score: {timing_sync.get('confidence_score')}")
            
            print(f"\n📈 All Detection Events Summary:")
            for i, event in enumerate(detection_events[:5]):  # First 5 events
                vrt = event.get('video_relative_timestamp')
                vfn = event.get('video_frame_number')
                fn = event.get('frame_number')
                print(f"   Event {i+1}: video_relative_timestamp={vrt}, video_frame_number={vfn}, frame_number={fn}")
        
        return True
            
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Final Video Timing Debug")
    print("=" * 50)
    
    debug_video_timing_final()

if __name__ == "__main__":
    main()