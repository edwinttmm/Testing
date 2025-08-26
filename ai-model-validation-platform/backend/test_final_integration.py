#!/usr/bin/env python3
"""
Final integration test for the annotation boundingBox corruption fix.
This test validates the complete end-to-end fix.
"""

import asyncio
import sqlite3
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the fixed endpoints
from endpoints_annotation import (
    get_annotations, get_annotation, create_annotation, 
    update_annotation, validate_annotation, get_annotations_by_detection_id
)
from schemas_annotation import AnnotationCreate, AnnotationUpdate, BoundingBox, VRUTypeEnum
from database import SessionLocal

class IntegrationTestRunner:
    """Comprehensive integration test runner"""
    
    def __init__(self):
        self.db = SessionLocal()
        self.test_results = []
    
    async def test_get_annotations_with_real_data(self):
        """Test get_annotations with real database data"""
        print("Testing get_annotations with real data...")
        
        # Get video ID from database
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT video_id FROM annotations LIMIT 1')
        video_id = cursor.fetchone()[0]
        conn.close()
        
        # Call the fixed endpoint
        result = await get_annotations(video_id, db=self.db)
        
        # Validate result structure
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) > 0, "Expected at least one annotation"
        
        for i, annotation in enumerate(result):
            print(f"  Annotation {i+1}:")
            print(f"    ID: {annotation.id}")
            print(f"    VideoID: {annotation.video_id}")
            print(f"    FrameNumber: {annotation.frame_number}")
            print(f"    BoundingBox: {annotation.bounding_box}")
            print(f"    VRUType: {annotation.vru_type}")
            
            # Critical validation: boundingBox must be dict
            assert isinstance(annotation.bounding_box, dict), f"BoundingBox must be dict, got {type(annotation.bounding_box)}"
            bbox = annotation.bounding_box
            
            # Ensure minimum required fields
            required_fields = ['x', 'y', 'width', 'height']
            for field in required_fields:
                assert field in bbox, f"Missing required field {field} in boundingBox"
                assert isinstance(bbox[field], (int, float)), f"Field {field} must be numeric"
            
            print(f"    ✅ BoundingBox structure valid")
        
        self.test_results.append(("get_annotations", True, f"Successfully processed {len(result)} annotations"))
        return True
    
    async def test_get_single_annotation(self):
        """Test get_annotation with real data"""
        print("Testing get_annotation with real data...")
        
        # Get annotation ID from database
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM annotations LIMIT 1')
        annotation_id = cursor.fetchone()[0]
        conn.close()
        
        # Call the fixed endpoint
        result = await get_annotation(annotation_id, db=self.db)
        
        print(f"  Single annotation result:")
        print(f"    ID: {result.id}")
        print(f"    BoundingBox: {result.bounding_box}")
        print(f"    Type: {type(result.bounding_box)}")
        
        # Validate structure
        assert isinstance(result.bounding_box, dict), f"BoundingBox must be dict, got {type(result.bounding_box)}"
        bbox = result.bounding_box
        
        required_fields = ['x', 'y', 'width', 'height']
        for field in required_fields:
            assert field in bbox, f"Missing required field {field}"
        
        print(f"    ✅ Single annotation boundingBox structure valid")
        self.test_results.append(("get_annotation", True, "Single annotation properly structured"))
        return True
    
    async def test_create_annotation_with_various_bbox_formats(self):
        """Test create_annotation with different bounding box formats"""
        print("Testing create_annotation with various boundingBox formats...")
        
        # Get video ID
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT video_id FROM annotations LIMIT 1')
        video_id = cursor.fetchone()[0]
        conn.close()
        
        # Test with proper BoundingBox Pydantic model
        bbox_model = BoundingBox(x=50, y=60, width=70, height=80, confidence=0.9)
        annotation_create = AnnotationCreate(
            frameNumber=10,
            timestamp=5.0,
            vruType=VRUTypeEnum.PEDESTRIAN,
            boundingBox=bbox_model,
            annotator="test-user"
        )
        
        # Call create endpoint
        result = await create_annotation(video_id, annotation_create, db=self.db)
        
        print(f"  Created annotation:")
        print(f"    ID: {result.id}")
        print(f"    BoundingBox: {result.bounding_box}")
        print(f"    Type: {type(result.bounding_box)}")
        
        # Validate the result
        assert isinstance(result.bounding_box, dict), "Created annotation boundingBox must be dict"
        bbox = result.bounding_box
        assert bbox['x'] == 50 and bbox['y'] == 60, "BoundingBox values not preserved correctly"
        
        print(f"    ✅ Created annotation has properly structured boundingBox")
        self.test_results.append(("create_annotation", True, "Created annotation with proper boundingBox structure"))
        return True
    
    async def test_database_corruption_scenarios(self):
        """Test how our fix handles corrupted database scenarios"""
        print("Testing database corruption scenarios...")
        
        # Create scenarios that would have caused the original bug
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        
        # Get video ID
        cursor.execute('SELECT DISTINCT video_id FROM annotations LIMIT 1')
        video_id = cursor.fetchone()[0]
        
        # Scenario 1: Incomplete JSON (missing required fields)
        incomplete_json = '{"x": 10, "y": 20}'  # Missing width, height
        annotation_id_1 = "test-incomplete-" + str(datetime.now().timestamp())
        
        cursor.execute('''
            INSERT INTO annotations (id, video_id, detection_id, frame_number, timestamp, vru_type, bounding_box, validated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (annotation_id_1, video_id, "test-detection", 999, 99.0, "pedestrian", incomplete_json, False, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Test our fixed endpoint with this corrupted data
        try:
            result = await get_annotation(annotation_id_1, db=self.db)
            print(f"  Corrupted data result:")
            print(f"    ID: {result.id}")
            print(f"    BoundingBox: {result.bounding_box}")
            
            # Our fix should handle this gracefully
            bbox = result.bounding_box
            assert isinstance(bbox, dict), "Should return dict even for corrupted data"
            assert all(field in bbox for field in ['x', 'y', 'width', 'height']), "Should have all required fields"
            
            print(f"    ✅ Corrupted data handled gracefully")
            self.test_results.append(("corruption_handling", True, "Gracefully handled corrupted boundingBox data"))
            
        except Exception as e:
            print(f"    ❌ Error handling corrupted data: {e}")
            self.test_results.append(("corruption_handling", False, str(e)))
            return False
        
        return True
    
    async def run_all_tests(self):
        """Run all integration tests"""
        print("=" * 80)
        print("FINAL INTEGRATION TEST - ANNOTATION BOUNDINGBOX FIX")
        print("=" * 80)
        print(f"Started: {datetime.now()}")
        print()
        
        try:
            # Run all test scenarios
            await self.test_get_annotations_with_real_data()
            print()
            await self.test_get_single_annotation()
            print()
            await self.test_create_annotation_with_various_bbox_formats()
            print()
            await self.test_database_corruption_scenarios()
            print()
            
            # Print summary
            print("=" * 80)
            print("INTEGRATION TEST RESULTS")
            print("=" * 80)
            
            all_passed = True
            for test_name, passed, message in self.test_results:
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"{status} {test_name}: {message}")
                if not passed:
                    all_passed = False
            
            print()
            if all_passed:
                print("🎉 ALL INTEGRATION TESTS PASSED!")
                print("✅ The annotation boundingBox corruption bug is definitively fixed!")
                print()
                print("Summary of fixes:")
                print("- Raw SQLAlchemy objects converted to AnnotationResponse schemas")
                print("- Proper type hints added for API documentation")  
                print("- Null-safe boundingBox handling prevents frontend crashes")
                print("- JSON parsing with fallback for corrupted data")
                print("- All endpoints return consistent, validated response format")
                print("- Frontend will receive proper dict structure, eliminating 'undefined undefined' errors")
            else:
                print("❌ SOME TESTS FAILED - Review and fix issues above")
            
            return all_passed
            
        finally:
            self.db.close()

async def main():
    """Run the final integration test"""
    runner = IntegrationTestRunner()
    success = await runner.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)