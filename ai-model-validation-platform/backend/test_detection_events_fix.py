#!/usr/bin/env python3
"""
Test DetectionEvent Database Operations
Validates that DetectionEvent records can be created and queried correctly
"""
import sys
import os
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
import logging
import uuid

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import engine, SessionLocal
from models import DetectionEvent, TestSession, Project, Video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionEventTest:
    def __init__(self):
        self.session = SessionLocal()
        self.test_data_created = []
    
    def cleanup(self):
        """Clean up test data"""
        try:
            for table, record_id in reversed(self.test_data_created):
                if table == "detection_events":
                    self.session.query(DetectionEvent).filter(DetectionEvent.id == record_id).delete()
                elif table == "test_sessions":
                    self.session.query(TestSession).filter(TestSession.id == record_id).delete()
                elif table == "videos":
                    self.session.query(Video).filter(Video.id == record_id).delete()
                elif table == "projects":
                    self.session.query(Project).filter(Project.id == record_id).delete()
            self.session.commit()
            logger.info("✅ Test data cleaned up")
        except Exception as e:
            logger.warning(f"⚠️  Cleanup warning: {e}")
            self.session.rollback()
        finally:
            self.session.close()
    
    def create_test_project(self):
        """Create a test project"""
        project_id = str(uuid.uuid4())
        project = Project(
            id=project_id,
            name="Test DetectionEvent Project",
            description="Test project for DetectionEvent validation",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        self.session.add(project)
        self.session.commit()
        self.test_data_created.append(("projects", project_id))
        logger.info(f"✅ Created test project: {project_id}")
        return project
    
    def create_test_video(self, project_id):
        """Create a test video"""
        video_id = str(uuid.uuid4())
        video = Video(
            id=video_id,
            filename="test_detection_video.mp4",
            file_path="/app/uploads/test_detection_video.mp4",
            project_id=project_id
        )
        self.session.add(video)
        self.session.commit()
        self.test_data_created.append(("videos", video_id))
        logger.info(f"✅ Created test video: {video_id}")
        return video
    
    def create_test_session(self, project_id, video_id):
        """Create a test session"""
        session_id = str(uuid.uuid4())
        test_session = TestSession(
            id=session_id,
            name="Test DetectionEvent Session",
            project_id=project_id,
            video_id=video_id
        )
        self.session.add(test_session)
        self.session.commit()
        self.test_data_created.append(("test_sessions", session_id))
        logger.info(f"✅ Created test session: {session_id}")
        return test_session
    
    def test_detection_event_creation(self, test_session_id):
        """Test creating DetectionEvent with correct field names"""
        
        logger.info("🧪 Testing DetectionEvent creation...")
        
        detection_event_id = str(uuid.uuid4())
        detection_id = "DET_PED_TEST_001"
        
        try:
            # Create DetectionEvent using the CORRECT field names
            detection_event = DetectionEvent(
                id=detection_event_id,
                test_session_id=test_session_id,
                timestamp=1.5,  # 1.5 seconds into video
                confidence=0.85,
                class_label="pedestrian",
                # Correct field names from the model:
                detection_id=detection_id,
                frame_number=30,
                vru_type="pedestrian",
                bounding_box_x=100.0,
                bounding_box_y=150.0,
                bounding_box_width=80.0,
                bounding_box_height=120.0,
                validation_result="VALIDATED",
                screenshot_path="/app/screenshots/detection_test_001.jpg",
                screenshot_zoom_path="/app/screenshots/detection_test_001_zoom.jpg",
                processing_time_ms=45.2,
                model_version="yolo11l"
            )
            
            self.session.add(detection_event)
            self.session.commit()
            self.test_data_created.append(("detection_events", detection_event_id))
            
            logger.info("✅ DetectionEvent created successfully!")
            logger.info(f"   Detection ID: {detection_id}")
            logger.info(f"   Frame: {detection_event.frame_number}")
            logger.info(f"   Bounding box: ({detection_event.bounding_box_x}, {detection_event.bounding_box_y}, {detection_event.bounding_box_width}, {detection_event.bounding_box_height})")
            logger.info(f"   Confidence: {detection_event.confidence}")
            
            return detection_event
            
        except Exception as e:
            logger.error(f"❌ DetectionEvent creation failed: {e}")
            self.session.rollback()
            raise
    
    def test_detection_event_query(self, test_session_id):
        """Test querying DetectionEvent records"""
        
        logger.info("🔍 Testing DetectionEvent queries...")
        
        try:
            # Query by test session
            detections = self.session.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == test_session_id
            ).all()
            
            logger.info(f"✅ Found {len(detections)} detection events")
            
            for detection in detections:
                logger.info(f"   Detection: {detection.detection_id}")
                logger.info(f"     Confidence: {detection.confidence}")
                logger.info(f"     Frame: {detection.frame_number}")
                logger.info(f"     Class: {detection.class_label}")
                logger.info(f"     VRU Type: {detection.vru_type}")
                logger.info(f"     Bbox: ({detection.bounding_box_x}, {detection.bounding_box_y}, {detection.bounding_box_width}, {detection.bounding_box_height})")
                
                # Verify all expected fields are accessible
                assert detection.detection_id is not None
                assert detection.frame_number is not None
                assert detection.bounding_box_x is not None
                assert detection.bounding_box_y is not None
                assert detection.bounding_box_width is not None
                assert detection.bounding_box_height is not None
            
            logger.info("✅ All DetectionEvent fields accessible!")
            return detections
            
        except Exception as e:
            logger.error(f"❌ DetectionEvent query failed: {e}")
            raise
    
    def test_detection_event_with_wrong_fields(self):
        """Test that using wrong field names fails as expected"""
        
        logger.info("🧪 Testing DetectionEvent with wrong field names (should fail)...")
        
        try:
            # This should fail because these fields don't exist
            detection_event = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id="fake-session-id",
                timestamp=1.0,
                video_id="fake-video-id",  # ❌ This field does not exist!
                x=100.0,  # ❌ Should be bounding_box_x
                y=150.0,  # ❌ Should be bounding_box_y
                width=80.0,  # ❌ Should be bounding_box_width
                height=120.0  # ❌ Should be bounding_box_height
            )
            
            # This should fail when we try to commit
            self.session.add(detection_event)
            self.session.commit()
            
            logger.error("❌ Wrong field test should have failed but didn't!")
            return False
            
        except Exception as e:
            logger.info(f"✅ Wrong field names correctly failed: {e}")
            self.session.rollback()
            return True
    
    def run_comprehensive_test(self):
        """Run all DetectionEvent tests"""
        
        logger.info("🧪 COMPREHENSIVE DETECTION EVENT TEST")
        logger.info("=" * 50)
        
        try:
            # Create test data hierarchy
            project = self.create_test_project()
            video = self.create_test_video(project.id)
            test_session = self.create_test_session(project.id, video.id)
            
            # Test 1: Create DetectionEvent with correct fields
            detection_event = self.test_detection_event_creation(test_session.id)
            
            # Test 2: Query DetectionEvent
            detections = self.test_detection_event_query(test_session.id)
            
            # Test 3: Wrong field names should fail
            wrong_fields_failed = self.test_detection_event_with_wrong_fields()
            
            # Verify the fix worked
            logger.info("\n📊 TEST RESULTS SUMMARY")
            logger.info("-" * 30)
            logger.info(f"✅ DetectionEvent creation: {'PASS' if detection_event else 'FAIL'}")
            logger.info(f"✅ DetectionEvent queries: {'PASS' if detections else 'FAIL'}")
            logger.info(f"✅ Wrong fields rejected: {'PASS' if wrong_fields_failed else 'FAIL'}")
            
            if detection_event and detections and wrong_fields_failed:
                logger.info("\n🎉 ALL TESTS PASSED!")
                logger.info("The DetectionEvent schema fix is working correctly!")
                return True
            else:
                logger.error("\n❌ Some tests failed")
                return False
            
        except Exception as e:
            logger.error(f"💥 Test failed with error: {e}")
            return False
        
        finally:
            self.cleanup()

def main():
    """Run DetectionEvent tests"""
    print("🧪 DetectionEvent Database Fix Validation")
    print("=" * 50)
    
    test = DetectionEventTest()
    
    try:
        success = test.run_comprehensive_test()
        
        if success:
            print("\n🎉 DetectionEvent fix validation PASSED!")
            print("The database schema mismatch has been resolved.")
            print("\nNext steps:")
            print("1. Deploy the fixed code to production")
            print("2. Test with real detection pipeline")
            print("3. Verify frontend can display detection data")
        else:
            print("\n❌ DetectionEvent fix validation FAILED!")
            print("Additional debugging may be needed.")
        
        return success
        
    except Exception as e:
        logger.error(f"💥 Test execution failed: {e}")
        return False
    finally:
        if test.session:
            test.session.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)