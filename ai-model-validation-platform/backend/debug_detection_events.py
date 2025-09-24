#!/usr/bin/env python3
"""
Debug Detection Events Structure
This script examines the actual structure of detection events.
"""

import requests
import json
import sys

def debug_detection_events():
    """Debug the structure of detection events"""
    print("🔍 Debugging Detection Events Structure...")
    
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
            # Show structure of first event
            first_event = detection_events[0]
            print(f"\n🔬 First Detection Event Structure:")
            for key, value in first_event.items():
                print(f"   {key}: {value} ({type(value).__name__})")
            
            # Check for video timing fields specifically
            video_fields = [
                'video_relative_timestamp',
                'video_frame_number',
                'video_timestamp'
            ]
            
            print(f"\n📹 Video Timing Fields Check:")
            for field in video_fields:
                values = [event.get(field) for event in detection_events[:5]]
                non_null_count = sum(1 for v in values if v is not None)
                print(f"   {field}: {non_null_count}/{len(values)} non-null in first 5 events")
                if non_null_count > 0:
                    sample_values = [v for v in values if v is not None][:3]
                    print(f"      Sample values: {sample_values}")
        
        return True
            
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Detection Events Debug Tool")
    print("=" * 50)
    
    debug_detection_events()

if __name__ == "__main__":
    main()