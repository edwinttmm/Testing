#!/usr/bin/env python3
"""Fix detection validation error by ensuring videoId is included in all detection payloads"""

import asyncio
import httpx
import json
from typing import Dict, Any

def fix_detection_payload(detection_data: Dict[str, Any], video_id: str) -> Dict[str, Any]:
    """Fix detection payload to include required videoId field"""
    
    # Ensure the detection data has the required videoId field
    if 'videoId' not in detection_data:
        detection_data['videoId'] = video_id
    
    # Map any alternate field names to expected schema
    if 'video_id' not in detection_data and 'videoId' in detection_data:
        detection_data['video_id'] = detection_data['videoId']
    
    return detection_data

def test_annotation_payload():
    """Test annotation payload with proper videoId"""
    
    # Sample detection data that was failing
    detection_data = {
        'detection_id': 'DET_PED_0001', 
        'frame_number': 30, 
        'timestamp': 1, 
        'vru_type': 'pedestrian', 
        'bounding_box': {
            'x': 320, 
            'y': 240, 
            'width': 80, 
            'height': 160, 
            'label': 'pedestrian', 
            'confidence': 0.85
        }, 
        'occluded': False, 
        'truncated': False, 
        'difficult': False, 
        'validated': False
    }
    
    # Fix: Add the missing videoId field
    video_id = "e7bc7641-fc0f-4208-8563-eb488c281e24"  # From the logs
    fixed_payload = fix_detection_payload(detection_data, video_id)
    
    print("🔧 ORIGINAL PAYLOAD (FAILING):")
    print(json.dumps(detection_data, indent=2))
    
    print("\n✅ FIXED PAYLOAD (WITH videoId):")
    print(json.dumps(fixed_payload, indent=2))
    
    # Verify the payload matches AnnotationCreate schema requirements
    required_fields = ['videoId', 'frameNumber', 'timestamp', 'vruType', 'boundingBox']
    missing_fields = []
    
    # Map detection fields to schema fields
    field_mapping = {
        'videoId': 'videoId',
        'frameNumber': 'frame_number', 
        'timestamp': 'timestamp',
        'vruType': 'vru_type',
        'boundingBox': 'bounding_box'
    }
    
    for schema_field, data_field in field_mapping.items():
        if data_field not in fixed_payload and schema_field not in fixed_payload:
            missing_fields.append(schema_field)
    
    if missing_fields:
        print(f"\n⚠️ STILL MISSING FIELDS: {missing_fields}")
        # Add missing fields with proper mapping
        if 'frameNumber' in missing_fields:
            fixed_payload['frameNumber'] = fixed_payload.get('frame_number', 30)
        if 'vruType' in missing_fields:
            fixed_payload['vruType'] = fixed_payload.get('vru_type', 'pedestrian')
        if 'boundingBox' in missing_fields:
            fixed_payload['boundingBox'] = fixed_payload.get('bounding_box', {})
    else:
        print("\n✅ ALL REQUIRED FIELDS PRESENT")
    
    print("\n🎯 FINAL PAYLOAD FOR ANNOTATION API:")
    final_payload = {
        'videoId': fixed_payload['videoId'],
        'detectionId': fixed_payload.get('detection_id'),
        'frameNumber': fixed_payload.get('frame_number', 30),
        'timestamp': fixed_payload.get('timestamp', 1.0),
        'vruType': fixed_payload.get('vru_type', 'pedestrian'),
        'boundingBox': fixed_payload.get('bounding_box', {}),
        'occluded': fixed_payload.get('occluded', False),
        'truncated': fixed_payload.get('truncated', False),
        'difficult': fixed_payload.get('difficult', False),
        'validated': fixed_payload.get('validated', False)
    }
    
    print(json.dumps(final_payload, indent=2))
    
    return final_payload

if __name__ == "__main__":
    print("🔧 FIXING DETECTION VALIDATION ERROR")
    print("="*50)
    
    test_annotation_payload()
    
    print("\n📝 SOLUTION SUMMARY:")
    print("1. Add 'videoId' field to all detection payloads")
    print("2. Map detection fields to annotation schema fields")
    print("3. Ensure proper field naming conventions")
    print("4. Include video ID from processing context")
    
    print("\n🚀 IMPLEMENTATION:")
    print("- Update detection pipeline to include video_id parameter")
    print("- Add videoId field to all API calls to annotation endpoints")
    print("- Map detection data to AnnotationCreate schema format")