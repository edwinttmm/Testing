#!/usr/bin/env python3

"""Debug script to identify where the bounding_box attribute error is occurring."""

import sys
import os
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from database import get_db
from models import DetectionEvent, TestSession

def debug_detection_event():
    """Debug the DetectionEvent model and identify the source of bounding_box error."""
    print("🔍 Debugging DetectionEvent model...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get one DetectionEvent for testing
        detection = db.query(DetectionEvent).first()
        
        if not detection:
            print("❌ No DetectionEvent found in database")
            return
            
        print(f"✅ Found DetectionEvent: {detection.id}")
        print(f"📊 DetectionEvent attributes:")
        
        # Print all attributes
        for attr in dir(detection):
            if not attr.startswith('_'):
                try:
                    value = getattr(detection, attr)
                    print(f"  - {attr}: {type(value)} = {value}")
                except Exception as e:
                    print(f"  - {attr}: ERROR = {e}")
        
        # Test the specific access that's failing
        print(f"\n🧪 Testing bounding_box access...")
        try:
            bbox = detection.bounding_box
            print(f"✅ detection.bounding_box = {bbox}")
        except AttributeError as e:
            print(f"❌ AttributeError: {e}")
            print("🔧 Individual bounding box fields:")
            print(f"  - bounding_box_x: {getattr(detection, 'bounding_box_x', 'NOT_FOUND')}")
            print(f"  - bounding_box_y: {getattr(detection, 'bounding_box_y', 'NOT_FOUND')}")
            print(f"  - bounding_box_width: {getattr(detection, 'bounding_box_width', 'NOT_FOUND')}")
            print(f"  - bounding_box_height: {getattr(detection, 'bounding_box_height', 'NOT_FOUND')}")
        
        # Test building the bounding_box object manually
        print(f"\n🏗️ Testing manual bounding_box construction...")
        try:
            bbox_manual = {
                "x": detection.bounding_box_x,
                "y": detection.bounding_box_y,
                "width": detection.bounding_box_width,
                "height": detection.bounding_box_height
            } if detection.bounding_box_x is not None else None
            print(f"✅ Manual bounding_box construction: {bbox_manual}")
        except Exception as e:
            print(f"❌ Manual construction failed: {e}")
            
    except Exception as e:
        print(f"❌ Database query failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_detection_event()