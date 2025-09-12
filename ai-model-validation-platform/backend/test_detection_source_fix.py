#!/usr/bin/env python3
"""
Quick test to verify detection source field fix works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import DetectionEvent

def test_detection_source():
    """Test that detection events have proper source field values"""
    print("🔍 Testing detection source field fix...")
    
    db = SessionLocal()
    try:
        # Query recent detection events
        detections = db.query(DetectionEvent).limit(5).all()
        
        print(f"\n📊 Found {len(detections)} detection events:")
        for i, detection in enumerate(detections, 1):
            source = getattr(detection, 'source', 'MISSING')
            detection_type = getattr(detection, 'detection_type', 'MISSING')
            
            print(f"  {i}. ID: {detection.id}")
            print(f"     Class: {detection.class_label}")
            print(f"     Confidence: {detection.confidence:.1f}%")
            print(f"     Source: '{source}' ← {'✅ AI' if source == 'ai' else '❌ Manual/Missing'}")
            print(f"     Detection Type: '{detection_type}' ← {'✅ Automatic' if detection_type == 'automatic' else '❌ Manual/Missing'}")
            print(f"     Bounding Box: ({detection.bounding_box_x}, {detection.bounding_box_y}, {detection.bounding_box_width}, {detection.bounding_box_height})")
            print()
        
        # Check if any detections have ai source
        ai_detections = db.query(DetectionEvent).filter(DetectionEvent.source == 'ai').count()
        manual_detections = db.query(DetectionEvent).filter(DetectionEvent.source == 'manual').count()
        null_detections = db.query(DetectionEvent).filter(DetectionEvent.source == None).count()
        
        print(f"📈 Detection Source Summary:")
        print(f"  AI detections: {ai_detections}")
        print(f"  Manual detections: {manual_detections}")
        print(f"  NULL/Missing source: {null_detections}")
        
        if ai_detections > 0:
            print("\n✅ SUCCESS: Found AI-labeled detections! Fix is working.")
        else:
            print("\n⚠️  INFO: No AI-labeled detections found. This may be expected if no new detections have been created since the fix.")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_detection_source()