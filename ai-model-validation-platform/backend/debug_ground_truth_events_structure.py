#!/usr/bin/env python3
"""
Debug Ground Truth Events Structure
This script checks if the enhanced HIL API includes the actual ground truth event objects.
"""

import requests
import json
import sys

def debug_ground_truth_events_structure():
    """Check if ground truth events are included in the API response"""
    print("🔍 Debugging Ground Truth Events Structure...")
    
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ ERROR: HTTP {response.status_code}")
            return False
        
        result = response.json()
        
        # Check ground truth comparison structure
        gt_comparison = result.get('ground_truth_comparison', {})
        print(f"📊 Ground Truth Comparison Structure:")
        print(f"   ground_truth_events_available: {gt_comparison.get('ground_truth_events_available')}")
        print(f"   total_detections: {gt_comparison.get('total_detections')}")
        print(f"   events_with_matches: {gt_comparison.get('events_with_matches')}")
        
        # Check if there's a ground truth events array
        if 'ground_truth_events' in gt_comparison:
            gt_events = gt_comparison['ground_truth_events']
            print(f"✅ Found ground_truth_events array: {len(gt_events)} items")
            if gt_events:
                print(f"📋 First ground truth event: {gt_events[0]}")
        else:
            print(f"❌ No ground_truth_events array found")
            print(f"🔍 Available keys in ground_truth_comparison: {list(gt_comparison.keys())}")
        
        # Check if ground truth events are stored elsewhere in the response
        all_keys = result.keys()
        gt_related_keys = [key for key in all_keys if 'ground' in key.lower() or 'truth' in key.lower()]
        print(f"🔍 All ground truth related keys: {gt_related_keys}")
        
        # The issue might be that we're counting ground truth events but not returning them
        print(f"\n🎯 ISSUE ANALYSIS:")
        print(f"   - We have a count of {gt_comparison.get('ground_truth_events_available', 0)} events")
        print(f"   - But no actual ground truth event objects are returned")
        print(f"   - Frontend needs the actual event data for timeline display")
        
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Ground Truth Events Structure Debug")
    print("=" * 60)
    
    debug_ground_truth_events_structure()

if __name__ == "__main__":
    main()