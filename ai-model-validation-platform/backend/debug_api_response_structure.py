#!/usr/bin/env python3
"""
Debug API Response Structure
This script checks what ground truth data is actually returned by the enhanced HIL API.
"""

import requests
import json
import sys

def debug_api_response_structure():
    """Debug the structure of the enhanced HIL API response"""
    print("🔍 Analyzing Enhanced HIL API Response Structure...")
    
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
    url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ ERROR: HTTP {response.status_code}")
            return False
        
        result = response.json()
        
        print(f"📊 API Response Keys: {list(result.keys())}")
        
        # Check for ground truth specific fields
        gt_fields = [
            'ground_truth_events', 'ground_truth_count', 'ground_truth_comparison',
            'true_positives', 'false_positives', 'false_negatives',
            'precision', 'recall', 'f1_score'
        ]
        
        print(f"🎯 Ground Truth Fields in Response:")
        for field in gt_fields:
            if field in result:
                value = result[field]
                if isinstance(value, list):
                    print(f"   {field}: {len(value)} items")
                    if len(value) > 0:
                        print(f"     Sample: {value[0] if isinstance(value[0], dict) else value[0]}")
                else:
                    print(f"   {field}: {value}")
            else:
                print(f"   {field}: ❌ MISSING")
        
        # Check detection events for ground truth data
        detection_events = result.get('detection_events', [])
        print(f"📋 Detection Events: {len(detection_events)}")
        
        if detection_events:
            first_detection = detection_events[0]
            print(f"🔬 First Detection Event Keys: {list(first_detection.keys())}")
            
            # Check for ground truth related fields in detection events
            gt_detection_fields = [
                'matched_ground_truth', 'ground_truth_match', 'timing_quality',
                'confidence_score', 'ground_truth_comparison'
            ]
            
            print(f"🎯 Ground Truth Fields in Detection Events:")
            for field in gt_detection_fields:
                if field in first_detection:
                    value = first_detection[field]
                    print(f"   {field}: {value}")
                else:
                    print(f"   {field}: ❌ MISSING")
        
        # Check if there's a summary section
        if 'summary' in result:
            summary = result['summary']
            print(f"📈 Summary Keys: {list(summary.keys())}")
        
        # Save full response for detailed analysis
        with open('/home/rigade/Testing/ai-model-validation-platform/backend/debug_api_response.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"💾 Full response saved to debug_api_response.json")
        
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Enhanced HIL API Response Structure Debug")
    print("=" * 60)
    
    debug_api_response_structure()

if __name__ == "__main__":
    main()