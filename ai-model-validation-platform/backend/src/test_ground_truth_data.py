#!/usr/bin/env python3
"""
Test Ground Truth Data Generator
Creates sample data to test the enhanced ground truth matching API
"""

import logging
import sys
import os
from datetime import datetime, timedelta
import uuid

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Project, Video, TestSession, GroundTruthObject, DetectionEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sample_ground_truth_data():
    """Create sample data to test ground truth matching functionality"""
    
    db = SessionLocal()
    
    try:
        # Create a test project
        project = Project(
            id=str(uuid.uuid4()),
            name="Ground Truth Test Project",
            description="Test project for ground truth matching validation",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db.add(project)
        db.flush()
        
        # Create a test video
        video = Video(
            id=str(uuid.uuid4()),
            project_id=project.id,
            filename="test_video_with_ground_truth.mp4",
            file_path="/test/videos/test_video_with_ground_truth.mp4",
            status="completed",
            ground_truth_generated=True,
            duration=30.0,
            fps=30.0,
            resolution="1920x1080",
            validation_status="completed",
            ground_truth_count=24
        )
        db.add(video)
        db.flush()
        
        # Create a test session
        session = TestSession(
            id=str(uuid.uuid4()),
            name="Ground Truth Validation Test",
            project_id=project.id,
            video_id=video.id,
            status="completed",
            started_at=datetime.utcnow() - timedelta(minutes=30),
            completed_at=datetime.utcnow() - timedelta(minutes=25),
            tolerance_ms=100,
            latency_threshold_ms=50,
            video_start_timestamp=0.0,
            precision_timing_enabled=True
        )
        db.add(session)
        db.flush()
        
        # Create ground truth objects (24 total as mentioned in the frontend issue)
        ground_truth_objects = []
        timestamps = [
            0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0,
            2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0,
            4.2, 4.4, 4.6, 4.8
        ]
        
        vru_types = ["pedestrian", "cyclist", "motorcyclist"]
        
        for i, timestamp in enumerate(timestamps):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                timestamp=timestamp,
                frame_number=int(timestamp * 30),  # 30 FPS
                class_label=vru_types[i % len(vru_types)],
                x=100 + (i * 10),
                y=150 + (i * 5),
                width=80,
                height=160,
                confidence=0.95,
                validated=True,
                difficult=False
            )
            ground_truth_objects.append(gt)
            db.add(gt)
        
        db.flush()
        
        # Create detection events to simulate real detections
        # 18 True Positives (matches with ground truth)
        # 4 False Positives (extra detections)
        # 6 False Negatives (missed ground truth - represented by missing detections)
        
        detection_events = []
        
        # True Positives - 18 detections that match ground truth (with some latency)
        for i in range(18):
            gt = ground_truth_objects[i]
            
            # Add realistic latency (15-45ms)
            latency_ms = 15 + (i * 2)  # Varying latency from 15ms to 49ms
            detection_timestamp = gt.timestamp + (latency_ms / 1000.0)
            
            detection = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id=session.id,
                video_id=video.id,
                timestamp=detection_timestamp,
                validation_result="Pass",
                latency_ms=latency_ms,
                latency_ns=str(latency_ms * 1_000_000),  # Convert to nanoseconds
                labjack_timestamp=detection_timestamp,
                video_start_time=0.0,
                confidence=0.85 + (i * 0.005),  # Varying confidence
                class_label=gt.class_label,
                detection_id=f"DET_{gt.class_label.upper()}_{i:04d}",
                frame_number=gt.frame_number + 1,  # Detection comes 1 frame after GT
                vru_type=gt.class_label,
                source="ai",
                detection_type="automatic",
                ground_truth_match_id=gt.id
            )
            detection_events.append(detection)
            db.add(detection)
        
        # False Positives - 4 extra detections with no ground truth match
        false_positive_times = [5.2, 6.8, 8.1, 9.5]
        for i, fp_time in enumerate(false_positive_times):
            detection = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id=session.id,
                video_id=video.id,
                timestamp=fp_time,
                validation_result="Fail",  # No ground truth to match
                latency_ms=25.0,  # Fixed latency for false positives
                latency_ns=str(25_000_000),
                labjack_timestamp=fp_time,
                video_start_time=0.0,
                confidence=0.45 + (i * 0.1),  # Lower confidence for false positives
                class_label="pedestrian",  # Default classification
                detection_id=f"DET_FP_{i:04d}",
                frame_number=int(fp_time * 30),
                vru_type="pedestrian",
                source="ai",
                detection_type="automatic",
                ground_truth_match_id=None  # No ground truth match
            )
            detection_events.append(detection)
            db.add(detection)
        
        # Note: False Negatives are represented by ground truth objects that don't have 
        # corresponding detection events (ground_truth_objects[18:24])
        
        db.commit()
        
        logger.info(f"✅ Created sample ground truth data:")
        logger.info(f"  📁 Project: {project.name} ({project.id})")
        logger.info(f"  🎥 Video: {video.filename} ({video.id})")
        logger.info(f"  🧪 Session: {session.name} ({session.id})")
        logger.info(f"  🎯 Ground Truth Objects: {len(ground_truth_objects)}")
        logger.info(f"  🔍 Detection Events: {len(detection_events)}")
        logger.info(f"  ✅ True Positives: 18")
        logger.info(f"  ❌ False Positives: 4") 
        logger.info(f"  📉 False Negatives: 6")
        logger.info(f"")
        logger.info(f"Expected metrics:")
        logger.info(f"  Precision: 18/(18+4) = 81.8%")
        logger.info(f"  Recall: 18/(18+6) = 75.0%")
        logger.info(f"  F1-Score: 2*(0.818*0.75)/(0.818+0.75) = 78.3%")
        logger.info(f"  Avg Latency: ~31ms (15-49ms range)")
        
        logger.info(f"")
        logger.info(f"🧪 Test API endpoints:")
        logger.info(f"  GET /api/results/{session.id}/results")
        logger.info(f"  GET /api/results/{session.id}/detection-events")
        logger.info(f"  GET /api/results/sessions/{session.id}/detailed")
        
        return {
            "project_id": project.id,
            "video_id": video.id,
            "session_id": session.id,
            "ground_truth_count": len(ground_truth_objects),
            "detection_count": len(detection_events)
        }
        
    except Exception as e:
        logger.error(f"❌ Error creating sample data: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def test_api_endpoints(session_id):
    """Test the enhanced API endpoints with sample data"""
    import requests
    
    # Assuming the API is running on localhost:8000
    base_url = "http://localhost:8000"
    
    endpoints = [
        f"/api/results/{session_id}/results",
        f"/api/results/{session_id}/detection-events",
        f"/api/results/sessions/{session_id}/detailed"
    ]
    
    logger.info("🧪 Testing API endpoints...")
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ {endpoint}: Success")
                
                if "ground_truth_total" in data:
                    logger.info(f"  📊 GT Total: {data['ground_truth_total']}")
                    logger.info(f"  📊 GT Matched: {data['ground_truth_matched']}")
                    logger.info(f"  📊 Precision: {data['precision']}%")
                    logger.info(f"  📊 Recall: {data['recall']}%")
                    logger.info(f"  📊 Avg Latency: {data['avg_latency_ms']}ms")
                
            else:
                logger.warning(f"⚠️ {endpoint}: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ Could not connect to API server at {base_url}")
            logger.info("💡 Start the API server and run this test again")
            break
        except Exception as e:
            logger.error(f"❌ Error testing {endpoint}: {str(e)}")

if __name__ == "__main__":
    logger.info("🚀 Creating sample ground truth data for testing...")
    
    try:
        result = create_sample_ground_truth_data()
        
        # Test API endpoints if server is running
        test_api_endpoints(result["session_id"])
        
        logger.info("✅ Sample data creation completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to create sample data: {str(e)}")
        sys.exit(1)