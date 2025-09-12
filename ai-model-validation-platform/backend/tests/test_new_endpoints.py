"""
Test New API Endpoints Implementation
====================================

Tests for the newly implemented dataset annotation and test session endpoints
to ensure they work correctly with the frontend.
"""

import sys
import os
sys.path.append('..')

from database import SessionLocal
from models import Video, Annotation, TestSession, DetectionEvent
from routers.datasets import get_video_annotations_for_dataset, get_video_ai_detections
from routers.test_sessions import list_test_sessions
import pytest
from unittest.mock import Mock

def test_dataset_annotation_endpoint():
    """Test the new dataset annotation endpoint format"""
    print("\n🧪 Testing Dataset Annotation Endpoint")
    
    db = SessionLocal()
    try:
        # Get a video with annotations
        video = db.query(Video).join(Annotation).first()
        if not video:
            print("❌ No video with annotations found")
            return False
        
        print(f"📹 Testing with video: {video.id} ({video.filename})")
        
        # Mock the dependency
        def mock_get_db():
            yield db
            
        # Test the endpoint function
        import asyncio
        result = asyncio.run(get_video_annotations_for_dataset(video.id, db))
        
        print(f"📊 Found {len(result)} annotations")
        
        if result:
            sample = result[0]
            print(f"📝 Sample annotation structure:")
            print(f"  - id: {sample.get('id')}")
            print(f"  - videoId: {sample.get('videoId')}")
            print(f"  - vruType: {sample.get('vruType')}")
            print(f"  - boundingBox: {sample.get('boundingBox', {}).keys()}")
            print(f"  - timestamp: {sample.get('timestamp')}")
            print(f"  - validated: {sample.get('validated')}")
            
            # Check required fields for frontend compatibility
            required_fields = ['id', 'videoId', 'vruType', 'boundingBox', 'timestamp', 'validated']
            missing_fields = [field for field in required_fields if field not in sample]
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
            
            print("✅ Dataset annotation endpoint format is correct")
            return True
        else:
            print("⚠️  No annotations returned")
            return True
            
    except Exception as e:
        print(f"❌ Error testing dataset annotations: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_ai_detections_endpoint():
    """Test the AI detections endpoint for datasets"""
    print("\n🤖 Testing AI Detections Endpoint")
    
    db = SessionLocal()
    try:
        # Get a video that has test sessions
        video = db.query(Video).join(TestSession).first()
        if not video:
            print("❌ No video with test sessions found")
            return False
        
        print(f"📹 Testing with video: {video.id}")
        
        # Test the endpoint function  
        import asyncio
        result = asyncio.run(get_video_ai_detections(video.id, 100, db))
        
        print(f"🤖 Found {len(result)} AI detections")
        
        if result:
            sample = result[0]
            print(f"📝 Sample AI detection structure:")
            print(f"  - id: {sample.get('id')}")
            print(f"  - detectionId: {sample.get('detectionId')}")
            print(f"  - timestamp: {sample.get('timestamp')}")
            print(f"  - vruType: {sample.get('vruType')}")
            print(f"  - confidence: {sample.get('confidence')}")
            print(f"  - boundingBox: {sample.get('boundingBox', {}).keys()}")
            print(f"  - screenshotPath: {sample.get('screenshotPath')}")
            
            # Check AIDetection interface compatibility
            required_fields = ['id', 'detectionId', 'timestamp', 'confidence', 'vruType', 'boundingBox']
            missing_fields = [field for field in required_fields if field not in sample]
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
                
            print("✅ AI detections endpoint format is correct")
            return True
        else:
            print("⚠️  No AI detections returned")
            return True
            
    except Exception as e:
        print(f"❌ Error testing AI detections: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_test_sessions_video_filter():
    """Test the updated test sessions endpoint with video_id filter"""
    print("\n📋 Testing Test Sessions Video Filter")
    
    db = SessionLocal()
    try:
        # Get a video that has test sessions
        video = db.query(Video).join(TestSession).first()
        if not video:
            print("❌ No video with test sessions found")
            return False
        
        print(f"📹 Testing video filter with video: {video.id}")
        
        # Test the endpoint function
        import asyncio
        result = asyncio.run(list_test_sessions(0, 100, None, video.id, None, db))
        
        print(f"📋 Found {len(result)} test sessions for video")
        
        # Verify all sessions are for the correct video
        for session in result:
            if session.get('video_id') != video.id:
                print(f"❌ Session {session.get('id')} has wrong video_id: {session.get('video_id')}")
                return False
        
        print("✅ Test sessions video filter works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Error testing test sessions filter: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_screenshot_paths():
    """Test screenshot path generation and accessibility"""
    print("\n📸 Testing Screenshot Paths")
    
    db = SessionLocal()
    try:
        # Find detection events with screenshot paths
        detection_with_screenshot = db.query(DetectionEvent).filter(
            DetectionEvent.screenshot_path.isnot(None)
        ).first()
        
        if detection_with_screenshot:
            print(f"📸 Found detection with screenshot: {detection_with_screenshot.screenshot_path}")
            
            # Test path normalization
            screenshot_path = detection_with_screenshot.screenshot_path
            if not screenshot_path.startswith('/screenshots/'):
                normalized_path = f"/screenshots/{os.path.basename(screenshot_path)}"
                print(f"🔄 Normalized path: {normalized_path}")
            else:
                normalized_path = screenshot_path
                print(f"✅ Path already normalized: {normalized_path}")
            
            # Check if file exists
            file_path = f"/home/rigade/Testing/ai-model-validation-platform/backend{normalized_path}"
            if os.path.exists(file_path):
                print(f"✅ Screenshot file exists: {file_path}")
                return True
            else:
                print(f"⚠️  Screenshot file not found: {file_path}")
                return False
        else:
            print("⚠️  No detections with screenshots found")
            return True
            
    except Exception as e:
        print(f"❌ Error testing screenshot paths: {e}")
        return False
    finally:
        db.close()

def run_all_tests():
    """Run all endpoint tests"""
    print("🚀 Starting New Endpoints Testing Suite")
    print("=" * 50)
    
    tests = [
        test_dataset_annotation_endpoint,
        test_ai_detections_endpoint, 
        test_test_sessions_video_filter,
        test_screenshot_paths
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    print(f"📈 Success Rate: {(sum(results)/len(results)*100):.1f}%")
    
    if all(results):
        print("\n🎉 All tests passed! New endpoints are ready for frontend integration.")
    else:
        print("\n⚠️  Some tests failed. Please review the issues above.")
    
    return all(results)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)