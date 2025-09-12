"""
Annotation CRUD Integration Example
==================================

Complete integration example showing how to use the new annotation CRUD endpoints
with the existing FastAPI application. Includes:

- Integration with main FastAPI app
- Sample usage examples
- Testing scenarios
- Performance monitoring
- Error handling demonstrations

Usage:
    python annotation_crud_integration.py
"""

import sys
import os
import asyncio
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import uuid
import logging

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# FastAPI imports
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# Import our new modules
from annotation_crud_endpoints import router as annotation_router
from annotation_validation_utils import (
    AnnotationValidator, AnnotationQueryOptimizer, 
    AnnotationSecurityValidator, AnnotationPerformanceMonitor
)

# Import existing modules
from database import get_db, engine, Base
from models import Video, Project, Annotation, AnnotationSession
from serializers import create_single_response, create_error_response

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# INTEGRATION SETUP
# =============================================================================

def setup_annotation_crud_integration(app: FastAPI):
    """Integrate annotation CRUD endpoints with main FastAPI app"""
    
    # Include the annotation router
    app.include_router(annotation_router, tags=["Annotation Management"])
    
    # Add custom middleware for annotation operations
    @app.middleware("http")
    async def annotation_monitoring_middleware(request, call_next):
        if request.url.path.startswith("/api/annotations"):
            start_time = datetime.utcnow()
            
            response = await call_next(request)
            
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"Annotation API call: {request.method} {request.url.path} - {duration:.2f}ms")
            
            return response
        
        return await call_next(request)
    
    return app

# =============================================================================
# SAMPLE DATA GENERATION
# =============================================================================

def create_sample_data(db: Session) -> Dict[str, str]:
    """Create sample data for testing annotation CRUD operations"""
    
    try:
        # Create sample project
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Annotation Project",
            description="Sample project for annotation CRUD testing",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            lens_type="Wide Angle",
            resolution="1920x1080",
            frame_rate=30,
            signal_type="GPIO",
            status="Active",
            owner_id="test_user",
            created_at=datetime.utcnow()
        )
        db.add(project)
        db.flush()
        
        # Create sample video
        video = Video(
            id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            file_size=1024000,
            duration=120.0,  # 2 minutes
            fps=30.0,
            resolution="1920x1080",
            status="uploaded",
            processing_status="completed",
            ground_truth_generated=True,
            project_id=project.id,
            created_at=datetime.utcnow()
        )
        db.add(video)
        db.flush()
        
        # Create sample annotation session
        session = AnnotationSession(
            id=str(uuid.uuid4()),
            video_id=video.id,
            project_id=project.id,
            annotator_id="test_annotator",
            status="active",
            total_frames=3600,  # 2 minutes at 30 FPS
            created_at=datetime.utcnow()
        )
        db.add(session)
        
        db.commit()
        
        return {
            "project_id": project.id,
            "video_id": video.id,
            "session_id": session.id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating sample data: {str(e)}")
        raise

# =============================================================================
# API TESTING EXAMPLES
# =============================================================================

class AnnotationCRUDTester:
    """Test class for annotation CRUD operations"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_data = {}
    
    def test_create_annotation(self, video_id: str) -> Optional[str]:
        """Test annotation creation"""
        logger.info("Testing annotation creation...")
        
        annotation_data = {
            "frameNumber": 150,
            "timestamp": 5.0,
            "vruType": "pedestrian",
            "boundingBox": {
                "x": 100.0,
                "y": 200.0,
                "width": 80.0,
                "height": 160.0,
                "confidence": 0.95
            },
            "occluded": False,
            "truncated": False,
            "difficult": False,
            "notes": "Test annotation for pedestrian detection",
            "annotator": "test_annotator",
            "validated": False
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/annotations/videos/{video_id}",
                json=annotation_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                annotation_id = result["data"]["id"]
                logger.info(f"✅ Annotation created successfully: {annotation_id}")
                return annotation_id
            else:
                logger.error(f"❌ Failed to create annotation: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception during annotation creation: {str(e)}")
            return None
    
    def test_get_annotations(self, video_id: str) -> bool:
        """Test annotation retrieval"""
        logger.info("Testing annotation retrieval...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/annotations/videos/{video_id}",
                params={"page": 1, "per_page": 10}
            )
            
            if response.status_code == 200:
                result = response.json()
                count = len(result["data"])
                logger.info(f"✅ Retrieved {count} annotations successfully")
                return True
            else:
                logger.error(f"❌ Failed to retrieve annotations: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during annotation retrieval: {str(e)}")
            return False
    
    def test_update_annotation(self, annotation_id: str) -> bool:
        """Test annotation update"""
        logger.info("Testing annotation update...")
        
        update_data = {
            "notes": "Updated test annotation",
            "validated": True,
            "boundingBox": {
                "x": 105.0,
                "y": 205.0,
                "width": 85.0,
                "height": 165.0,
                "confidence": 0.98
            }
        }
        
        try:
            response = self.session.put(
                f"{self.base_url}/api/annotations/{annotation_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info("✅ Annotation updated successfully")
                return True
            else:
                logger.error(f"❌ Failed to update annotation: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during annotation update: {str(e)}")
            return False
    
    def test_batch_create_annotations(self, video_id: str) -> bool:
        """Test batch annotation creation"""
        logger.info("Testing batch annotation creation...")
        
        batch_data = {
            "annotations": [
                {
                    "frameNumber": 300,
                    "timestamp": 10.0,
                    "vruType": "cyclist",
                    "boundingBox": {
                        "x": 150.0,
                        "y": 250.0,
                        "width": 60.0,
                        "height": 120.0,
                        "confidence": 0.85
                    },
                    "notes": "Batch annotation 1"
                },
                {
                    "frameNumber": 450,
                    "timestamp": 15.0,
                    "vruType": "pedestrian",
                    "boundingBox": {
                        "x": 200.0,
                        "y": 300.0,
                        "width": 70.0,
                        "height": 140.0,
                        "confidence": 0.92
                    },
                    "notes": "Batch annotation 2"
                }
            ]
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/annotations/videos/{video_id}/batch",
                json=batch_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                count = len(result["data"])
                logger.info(f"✅ Created {count} annotations in batch")
                return True
            else:
                logger.error(f"❌ Failed to create batch annotations: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during batch annotation creation: {str(e)}")
            return False
    
    def test_search_annotations(self) -> bool:
        """Test annotation search"""
        logger.info("Testing annotation search...")
        
        search_data = {
            "vruType": "pedestrian",
            "validated": True,
            "timestampStart": 0.0,
            "timestampEnd": 30.0
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/annotations/search",
                json=search_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                count = result["meta"]["total"] if "meta" in result else len(result.get("data", []))
                logger.info(f"✅ Search returned {count} annotations")
                return True
            else:
                logger.error(f"❌ Failed to search annotations: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during annotation search: {str(e)}")
            return False
    
    def test_annotation_session_crud(self, video_id: str, project_id: str) -> Optional[str]:
        """Test annotation session CRUD operations"""
        logger.info("Testing annotation session CRUD...")
        
        # Create session
        session_data = {
            "videoId": video_id,
            "projectId": project_id,
            "annotatorId": "test_annotator",
            "totalFrames": 3600
        }
        
        try:
            # Create
            response = self.session.post(
                f"{self.base_url}/api/annotations/sessions",
                json=session_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to create session: {response.text}")
                return None
            
            session_id = response.json()["data"]["id"]
            logger.info(f"✅ Session created: {session_id}")
            
            # Get
            response = self.session.get(f"{self.base_url}/api/annotations/sessions/{session_id}")
            if response.status_code != 200:
                logger.error(f"❌ Failed to get session: {response.text}")
                return None
            
            logger.info("✅ Session retrieved successfully")
            
            # Update
            update_data = {
                "status": "paused",
                "currentFrame": 1200
            }
            
            response = self.session.put(
                f"{self.base_url}/api/annotations/sessions/{session_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to update session: {response.text}")
                return None
            
            logger.info("✅ Session updated successfully")
            return session_id
            
        except Exception as e:
            logger.error(f"❌ Exception during session CRUD: {str(e)}")
            return None
    
    def test_ground_truth_crud(self, video_id: str) -> Optional[str]:
        """Test ground truth object CRUD operations"""
        logger.info("Testing ground truth CRUD...")
        
        # Create ground truth
        gt_data = {
            "timestamp": 20.0,
            "frameNumber": 600,
            "classLabel": "pedestrian",
            "x": 120.0,
            "y": 180.0,
            "width": 75.0,
            "height": 150.0,
            "confidence": 1.0,
            "validated": True
        }
        
        try:
            # Create
            response = self.session.post(
                f"{self.base_url}/api/annotations/ground-truth/videos/{video_id}",
                json=gt_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to create ground truth: {response.text}")
                return None
            
            gt_id = response.json()["data"]["id"]
            logger.info(f"✅ Ground truth created: {gt_id}")
            
            # Get all ground truths for video
            response = self.session.get(f"{self.base_url}/api/annotations/ground-truth/videos/{video_id}")
            if response.status_code != 200:
                logger.error(f"❌ Failed to get ground truths: {response.text}")
                return None
            
            count = len(response.json()["data"])
            logger.info(f"✅ Retrieved {count} ground truth objects")
            
            # Update ground truth
            update_data = {
                "confidence": 0.95,
                "classLabel": "pedestrian_validated"
            }
            
            response = self.session.put(
                f"{self.base_url}/api/annotations/ground-truth/{gt_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to update ground truth: {response.text}")
                return None
            
            logger.info("✅ Ground truth updated successfully")
            return gt_id
            
        except Exception as e:
            logger.error(f"❌ Exception during ground truth CRUD: {str(e)}")
            return None
    
    def test_analytics_endpoint(self) -> bool:
        """Test analytics endpoint"""
        logger.info("Testing analytics endpoint...")
        
        try:
            response = self.session.get(f"{self.base_url}/api/annotations/analytics/summary")
            
            if response.status_code == 200:
                result = response.json()
                total = result["data"]["totalAnnotations"]
                logger.info(f"✅ Analytics retrieved: {total} total annotations")
                return True
            else:
                logger.error(f"❌ Failed to get analytics: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during analytics test: {str(e)}")
            return False
    
    def run_comprehensive_test(self) -> Dict[str, bool]:
        """Run comprehensive test suite"""
        logger.info("🚀 Starting comprehensive annotation CRUD tests...")
        
        results = {}
        
        # First, we need to create test data (this would typically be done via database setup)
        # For now, we'll assume test data exists
        
        # These would be real IDs from your test database
        test_video_id = "test-video-id"
        test_project_id = "test-project-id"
        
        try:
            # Test basic annotation CRUD
            annotation_id = self.test_create_annotation(test_video_id)
            results["create_annotation"] = annotation_id is not None
            
            if annotation_id:
                results["update_annotation"] = self.test_update_annotation(annotation_id)
            
            results["get_annotations"] = self.test_get_annotations(test_video_id)
            results["batch_create"] = self.test_batch_create_annotations(test_video_id)
            results["search_annotations"] = self.test_search_annotations()
            
            # Test annotation session CRUD
            session_id = self.test_annotation_session_crud(test_video_id, test_project_id)
            results["annotation_session_crud"] = session_id is not None
            
            # Test ground truth CRUD
            gt_id = self.test_ground_truth_crud(test_video_id)
            results["ground_truth_crud"] = gt_id is not None
            
            # Test analytics
            results["analytics"] = self.test_analytics_endpoint()
            
        except Exception as e:
            logger.error(f"❌ Exception during comprehensive test: {str(e)}")
        
        # Print results summary
        logger.info("🏁 Test Results Summary:")
        logger.info("=" * 50)
        
        passed = 0
        total = len(results)
        
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{test_name:<30} {status}")
            if success:
                passed += 1
        
        logger.info("=" * 50)
        logger.info(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        return results

# =============================================================================
# VALIDATION EXAMPLE
# =============================================================================

async def demonstrate_validation():
    """Demonstrate validation utilities"""
    logger.info("🔧 Demonstrating validation utilities...")
    
    # This would be called with a real database session
    # db = next(get_db())
    # validator = AnnotationValidator(db)
    
    # Example validation data
    test_annotation = {
        "frame_number": 150,
        "timestamp": 5.0,
        "vru_type": "pedestrian",
        "bounding_box": {
            "x": 100.0,
            "y": 200.0,
            "width": 80.0,
            "height": 160.0
        },
        "notes": "Test annotation"
    }
    
    logger.info("Sample annotation validation data:")
    logger.info(json.dumps(test_annotation, indent=2))
    
    # Example of what validation would return
    logger.info("✅ Validation would check:")
    logger.info("  - Video exists")
    logger.info("  - Required fields present")
    logger.info("  - Bounding box coordinates valid")
    logger.info("  - Timestamp within video duration")
    logger.info("  - VRU type is valid")
    logger.info("  - No duplicate annotations")

# =============================================================================
# PERFORMANCE MONITORING EXAMPLE
# =============================================================================

def demonstrate_performance_monitoring():
    """Demonstrate performance monitoring"""
    logger.info("📊 Demonstrating performance monitoring...")
    
    monitor = AnnotationPerformanceMonitor()
    
    # Simulate operations
    import time
    
    # Operation 1
    op1_id = monitor.start_operation("create_annotation")
    time.sleep(0.1)  # Simulate work
    op1_result = monitor.end_operation(op1_id)
    
    # Operation 2 (slow)
    op2_id = monitor.start_operation("batch_create_annotations")
    time.sleep(0.2)  # Simulate work
    op2_result = monitor.end_operation(op2_id)
    
    # Get stats
    stats = monitor.get_operation_stats()
    
    logger.info(f"Operation 1: {op1_result['duration_ms']:.2f}ms")
    logger.info(f"Operation 2: {op2_result['duration_ms']:.2f}ms")
    logger.info(f"Average duration: {stats['avg_duration_ms']:.2f}ms")

# =============================================================================
# MAIN INTEGRATION FUNCTION
# =============================================================================

def main():
    """Main integration demonstration"""
    print("🚀 Annotation CRUD Integration Demo")
    print("=" * 50)
    
    # Create FastAPI app with integration
    app = FastAPI(title="AI Model Validation Platform - Annotation CRUD Demo")
    app = setup_annotation_crud_integration(app)
    
    print("✅ FastAPI app configured with annotation CRUD endpoints")
    
    # Demonstrate validation utilities
    asyncio.run(demonstrate_validation())
    
    # Demonstrate performance monitoring
    demonstrate_performance_monitoring()
    
    # Show available endpoints
    print("\n📋 Available Annotation CRUD Endpoints:")
    print("=" * 50)
    endpoints = [
        "POST   /api/annotations/videos/{video_id}",
        "GET    /api/annotations/videos/{video_id}",
        "GET    /api/annotations/{annotation_id}",
        "PUT    /api/annotations/{annotation_id}",
        "DELETE /api/annotations/{annotation_id}",
        "POST   /api/annotations/videos/{video_id}/batch",
        "PATCH  /api/annotations/{annotation_id}/validate",
        "POST   /api/annotations/search",
        "POST   /api/annotations/sessions",
        "GET    /api/annotations/sessions/{session_id}",
        "PUT    /api/annotations/sessions/{session_id}",
        "DELETE /api/annotations/sessions/{session_id}",
        "GET    /api/annotations/sessions",
        "POST   /api/annotations/ground-truth/videos/{video_id}",
        "GET    /api/annotations/ground-truth/videos/{video_id}",
        "PUT    /api/annotations/ground-truth/{ground_truth_id}",
        "DELETE /api/annotations/ground-truth/{ground_truth_id}",
        "GET    /api/annotations/test-results/sessions/{session_id}",
        "GET    /api/annotations/analytics/summary",
        "GET    /api/annotations/videos/{video_id}/export",
        "GET    /api/annotations/health"
    ]
    
    for endpoint in endpoints:
        print(f"  {endpoint}")
    
    print("\n🎯 Integration Complete!")
    print("To run tests against a live server:")
    print("  tester = AnnotationCRUDTester('http://localhost:8000')")
    print("  results = tester.run_comprehensive_test()")
    
    return app

if __name__ == "__main__":
    app = main()
    print("\n🌟 Ready to integrate with main FastAPI application!")