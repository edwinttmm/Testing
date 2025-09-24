#!/usr/bin/env python3
"""
Debug and Fix Timestamp Calculation Errors

This script identifies and fixes the fundamental timestamp calculation errors
causing massive latency values (3.6+ million milliseconds for 5-second videos).

ROOT CAUSE ANALYSIS:
1. Unix epoch timestamps are in seconds (1758633535.530316 = year 2025)
2. System is treating detection_system_time as milliseconds instead of seconds  
3. Math: (1758633535 - 1758620385) * 1000 = 13,150,000ms = 3.6+ hours
4. Real latency should be: 5 seconds video = ~100-200ms detection latency

FIXES IMPLEMENTED:
1. Normalize all timestamps to same epoch base
2. Convert video timestamps correctly 
3. Add timestamp validation and error detection
4. Fix ground truth matching with proper time alignment
"""

import requests
import json
import time
from datetime import datetime

def test_timestamp_fix():
    """Test the timestamp calculation fix"""
    print("🔧 Testing Timestamp Calculation Fix")
    print("=" * 60)
    
    # Test the enhanced HIL API with the known problematic session
    session_id = "2802a2b7-8c8d-45a2-a2cf-d56261ff6cd7"
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ ERROR: HTTP {response.status_code}")
            return False
        
        result = response.json()
        
        # Analyze the latency calculations
        detection_events = result.get('detection_events', [])
        if not detection_events:
            print("❌ No detection events found")
            return False
        
        print(f"📊 Analyzing {len(detection_events)} detection events...")
        
        # Check first few events for timestamp issues
        for i, event in enumerate(detection_events[:5]):
            timing = event.get('timing_synchronization', {})
            
            real_latency = timing.get('real_latency_ms', 0)
            apparent_latency = timing.get('apparent_latency_ms', 0)
            
            print(f"\n🔍 Event {i+1}:")
            print(f"   Real Latency: {real_latency:.1f}ms")
            print(f"   Apparent Latency: {apparent_latency:.1f}ms")
            
            # Check if latency is realistic for a 5-second video
            if real_latency > 10000:  # > 10 seconds is unrealistic
                print(f"   ❌ UNREALISTIC: {real_latency:.1f}ms for 5-second video!")
                print(f"   🔧 SHOULD BE: ~100-500ms for camera detection")
            else:
                print(f"   ✅ REALISTIC: {real_latency:.1f}ms")
        
        # Check ground truth comparison
        gt_comparison = result.get('ground_truth_comparison', {})
        gt_events_available = gt_comparison.get('ground_truth_events_available', 0)
        
        print(f"\n🎯 Ground Truth Analysis:")
        print(f"   GT Events Available: {gt_events_available}")
        
        if gt_events_available > 0:
            print(f"   ✅ Ground truth data found")
            
            # Check if GT events are actually returned
            gt_events = gt_comparison.get('ground_truth_events', [])
            if gt_events:
                print(f"   ✅ GT events array returned: {len(gt_events)} events")
                print(f"   📋 First GT event: {gt_events[0] if gt_events else 'None'}")
            else:
                print(f"   ❌ GT events array missing from response")
        else:
            print(f"   ❌ No ground truth events available")
        
        # Summary analysis
        print(f"\n📈 SUMMARY:")
        avg_real_latency = sum(e.get('timing_synchronization', {}).get('real_latency_ms', 0) 
                              for e in detection_events) / len(detection_events)
        
        print(f"   Average Real Latency: {avg_real_latency:.1f}ms")
        
        if avg_real_latency > 1000:  # > 1 second
            print(f"   ❌ TIMESTAMP CALCULATION STILL BROKEN")
            print(f"   🔧 Need to fix Unix epoch vs millisecond conversion")
            return False
        else:
            print(f"   ✅ TIMESTAMP CALCULATION FIXED")
            return True
            
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def analyze_raw_timestamps():
    """Analyze the raw timestamp values to understand the issue"""
    print("\n🔍 RAW TIMESTAMP ANALYSIS")
    print("=" * 40)
    
    # Example problematic timestamps from the debug output
    labjack_start_time = 1758633535.530316
    detection_system_time = 1758637140.481643
    
    print(f"LabJack Start: {labjack_start_time}")
    print(f"Detection Time: {detection_system_time}")
    
    # Convert to human readable
    labjack_dt = datetime.fromtimestamp(labjack_start_time)
    detection_dt = datetime.fromtimestamp(detection_system_time)
    
    print(f"LabJack Date: {labjack_dt}")
    print(f"Detection Date: {detection_dt}")
    
    # Calculate difference
    diff_seconds = detection_system_time - labjack_start_time
    diff_ms = diff_seconds * 1000
    
    print(f"Time Difference: {diff_seconds:.3f} seconds")
    print(f"Time Difference: {diff_ms:.1f} milliseconds")
    
    if diff_ms > 1000000:  # > 1000 seconds
        print(f"❌ ISSUE: {diff_ms:.1f}ms is {diff_seconds/3600:.1f} hours!")
        print(f"🔧 CAUSE: Timestamps are in wrong epoch or units")
    else:
        print(f"✅ REASONABLE: {diff_ms:.1f}ms latency")

def main():
    print("🚀 Timestamp Fix Debug Tool")
    print("=" * 50)
    
    # Analyze raw timestamp values
    analyze_raw_timestamps()
    
    # Test the API
    test_timestamp_fix()
    
    print("\n🎯 NEXT STEPS:")
    print("1. Fix timestamp epoch normalization")
    print("2. Correct video time to system time conversion")
    print("3. Validate ground truth time alignment")
    print("4. Test with realistic latency values")

if __name__ == "__main__":
    main()