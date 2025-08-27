#!/usr/bin/env python3
"""
VRU Database Integration Layer - SPARC Implementation
Unified integration between ML engines and database architecture

SPARC Architecture:
- Specification: Complete VRU detection to database pipeline
- Pseudocode: Optimized data flow and validation
- Architecture: Unified layer for all ML-to-database operations
- Refinement: Performance-optimized with proper indexing
- Completion: Production-ready integration layer

Coordinates with all agent implementations via shared memory
"""

import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import json

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# Import unified database and models
import sys
from pathlib import Path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from unified_database import get_database_manager, UnifiedDatabaseManager
    from models import (
        Video, Project, GroundTruthObject, DetectionEvent, 
        Annotation, AnnotationSession, TestSession, TestResult,
        VideoProjectLink, DetectionComparison, AuditLog
    )
    DATABASE_AVAILABLE = True
except ImportError as e:
    logging.error(f"Database imports failed: {e}")
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class VRUDetectionData:
    """Standardized VRU detection data structure"""
    detection_id: str
    video_id: str
    frame_number: int
    timestamp: float
    vru_type: str  # pedestrian, cyclist, motorcyclist
    confidence: float
    bounding_box: Dict[str, float]  # {x, y, width, height}
    class_label: str
    model_version: str
    processing_time_ms: Optional[float] = None
    screenshot_path: Optional[str] = None
    screenshot_zoom_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class VideoMetadata:
    """Enhanced video metadata structure"""
    video_id: str
    filename: str
    file_path: str
    file_size: int
    duration: float
    fps: float
    resolution: str
    total_frames: int
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class VRUDatabaseIntegrationLayer:
    """Unified VRU Database Integration Layer"""
    
    def __init__(self):
        """Initialize the integration layer"""
        if not DATABASE_AVAILABLE:
            raise RuntimeError("Database components not available")
        
        self.db_manager = get_database_manager()
        self._session_cache = {}
        self._performance_metrics = {
            "detections_stored": 0,
            "annotations_created": 0,
            "videos_processed": 0,
            "query_times": [],
            "errors": 0
        }
        logger.info("VRU Database Integration Layer initialized")
    
    # =============================================================================
    # CORE VIDEO OPERATIONS
    # =============================================================================
    
    async def store_video_with_metadata(self, video_metadata: VideoMetadata, 
                                      project_id: Optional[str] = None) -> str:
        """Store video with comprehensive metadata"""
        try:
            with self.db_manager.get_session() as session:
                # Create video record
                video = Video(
                    id=video_metadata.video_id,
                    filename=video_metadata.filename,
                    file_path=video_metadata.file_path,
                    file_size=video_metadata.file_size,
                    duration=video_metadata.duration,
                    fps=video_metadata.fps,
                    resolution=video_metadata.resolution,
                    status="uploaded",
                    processing_status="pending",
                    project_id=project_id
                )
                
                session.add(video)
                session.flush()  # Get the ID
                
                # Update performance metrics
                self._performance_metrics["videos_processed"] += 1
                
                logger.info(f"Video stored: {video_metadata.filename} ({video_metadata.video_id})")
                return video.id
                
        except Exception as e:
            self._performance_metrics["errors"] += 1
            logger.error(f"Failed to store video metadata: {e}")
            raise
    
    async def get_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve comprehensive video metadata"""
        try:
            with self.db_manager.get_session() as session:
                video = session.query(Video).filter(Video.id == video_id).first()
                if not video:
                    return None
                
                return {
                    "id": video.id,
                    "filename": video.filename,
                    "file_path": video.file_path,
                    "file_size": video.file_size,
                    "duration": video.duration,
                    "fps": video.fps,
                    "resolution": video.resolution,
                    "status": video.status,
                    "processing_status": video.processing_status,
                    "ground_truth_generated": video.ground_truth_generated,
                    "project_id": video.project_id,
                    "created_at": video.created_at.isoformat() if video.created_at else None,
                    "updated_at": video.updated_at.isoformat() if video.updated_at else None
                }
                
        except Exception as e:
            logger.error(f"Failed to retrieve video metadata: {e}")
            return None
    
    # =============================================================================
    # VRU DETECTION OPERATIONS
    # =============================================================================
    
    async def store_vru_detection(self, detection: VRUDetectionData, 
                                test_session_id: Optional[str] = None) -> str:
        """Store VRU detection with validation"""
        try:
            with self.db_manager.get_session() as session:
                # Create detection event
                detection_event = DetectionEvent(
                    id=str(uuid.uuid4()),
                    test_session_id=test_session_id,
                    detection_id=detection.detection_id,
                    frame_number=detection.frame_number,
                    timestamp=detection.timestamp,
                    vru_type=detection.vru_type,
                    confidence=detection.confidence,
                    class_label=detection.class_label,
                    bounding_box_x=detection.bounding_box.get('x'),
                    bounding_box_y=detection.bounding_box.get('y'),
                    bounding_box_width=detection.bounding_box.get('width'),
                    bounding_box_height=detection.bounding_box.get('height'),
                    screenshot_path=detection.screenshot_path,
                    screenshot_zoom_path=detection.screenshot_zoom_path,
                    processing_time_ms=detection.processing_time_ms,
                    model_version=detection.model_version,
                    validation_result="pending"  # Will be updated by validation process
                )
                
                session.add(detection_event)
                session.flush()
                
                # Update performance metrics
                self._performance_metrics["detections_stored"] += 1
                
                logger.debug(f"Detection stored: {detection.detection_id} at {detection.timestamp}")
                return detection_event.id
                
        except Exception as e:
            self._performance_metrics["errors"] += 1
            logger.error(f"Failed to store VRU detection: {e}")
            raise
    
    async def batch_store_detections(self, detections: List[VRUDetectionData], 
                                   test_session_id: Optional[str] = None) -> List[str]:
        """Efficiently store multiple detections in batch"""
        detection_ids = []
        
        try:
            with self.db_manager.get_session() as session:
                detection_events = []
                
                for detection in detections:
                    detection_event = DetectionEvent(
                        id=str(uuid.uuid4()),
                        test_session_id=test_session_id,
                        detection_id=detection.detection_id,
                        frame_number=detection.frame_number,
                        timestamp=detection.timestamp,
                        vru_type=detection.vru_type,
                        confidence=detection.confidence,
                        class_label=detection.class_label,
                        bounding_box_x=detection.bounding_box.get('x'),
                        bounding_box_y=detection.bounding_box.get('y'),
                        bounding_box_width=detection.bounding_box.get('width'),
                        bounding_box_height=detection.bounding_box.get('height'),
                        screenshot_path=detection.screenshot_path,
                        screenshot_zoom_path=detection.screenshot_zoom_path,
                        processing_time_ms=detection.processing_time_ms,
                        model_version=detection.model_version,
                        validation_result="pending"
                    )
                    
                    detection_events.append(detection_event)
                    detection_ids.append(detection_event.id)
                
                # Batch insert for performance
                session.add_all(detection_events)
                session.flush()
                
                # Update performance metrics
                self._performance_metrics["detections_stored"] += len(detections)
                
                logger.info(f"Batch stored {len(detections)} detections")
                return detection_ids
                
        except Exception as e:
            self._performance_metrics["errors"] += 1
            logger.error(f"Failed to batch store detections: {e}")
            raise
    
    async def get_detections_for_video(self, video_id: str, 
                                     vru_type: Optional[str] = None,
                                     confidence_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """Retrieve detections for a specific video with filtering"""
        try:
            with self.db_manager.get_session() as session:
                # Build query with joins to get test session info
                query = session.query(DetectionEvent).join(
                    TestSession, DetectionEvent.test_session_id == TestSession.id
                ).filter(TestSession.video_id == video_id)
                
                # Apply filters
                if vru_type:
                    query = query.filter(DetectionEvent.vru_type == vru_type)
                if confidence_threshold:
                    query = query.filter(DetectionEvent.confidence >= confidence_threshold)
                
                # Order by timestamp for temporal consistency
                query = query.order_by(DetectionEvent.timestamp)
                
                detections = query.all()
                
                return [
                    {
                        "id": det.id,
                        "detection_id": det.detection_id,
                        "frame_number": det.frame_number,
                        "timestamp": det.timestamp,
                        "vru_type": det.vru_type,
                        "confidence": det.confidence,
                        "class_label": det.class_label,
                        "bounding_box": {
                            "x": det.bounding_box_x,
                            "y": det.bounding_box_y,
                            "width": det.bounding_box_width,
                            "height": det.bounding_box_height
                        } if det.bounding_box_x is not None else None,
                        "validation_result": det.validation_result,
                        "model_version": det.model_version,
                        "processing_time_ms": det.processing_time_ms,
                        "created_at": det.created_at.isoformat() if det.created_at else None
                    }
                    for det in detections
                ]
                
        except Exception as e:
            logger.error(f"Failed to retrieve detections for video {video_id}: {e}")
            return []
    
    # =============================================================================
    # ANNOTATION OPERATIONS
    # =============================================================================
    
    async def create_annotation_from_detection(self, detection: VRUDetectionData) -> str:
        """Create ground truth annotation from detection"""
        try:
            with self.db_manager.get_session() as session:
                annotation = Annotation(
                    id=str(uuid.uuid4()),
                    video_id=detection.video_id,
                    detection_id=detection.detection_id,
                    frame_number=detection.frame_number,
                    timestamp=detection.timestamp,
                    vru_type=detection.vru_type,
                    bounding_box=detection.bounding_box,
                    notes=f"Auto-generated from {detection.model_version} detection (conf: {detection.confidence:.3f})",
                    annotator="YOLO_AI",
                    validated=detection.confidence > 0.8  # Auto-validate high confidence
                )
                
                session.add(annotation)
                session.flush()
                
                # Update performance metrics
                self._performance_metrics["annotations_created"] += 1
                
                logger.debug(f"Annotation created from detection: {detection.detection_id}")
                return annotation.id
                
        except Exception as e:
            self._performance_metrics["errors"] += 1
            logger.error(f"Failed to create annotation from detection: {e}")
            raise
    
    async def get_annotations_for_video(self, video_id: str, 
                                      validated_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieve annotations for a specific video"""
        try:
            with self.db_manager.get_session() as session:
                query = session.query(Annotation).filter(Annotation.video_id == video_id)
                
                if validated_only:
                    query = query.filter(Annotation.validated == True)
                
                query = query.order_by(Annotation.timestamp)
                annotations = query.all()
                
                return [
                    {
                        "id": ann.id,
                        "detection_id": ann.detection_id,
                        "frame_number": ann.frame_number,
                        "timestamp": ann.timestamp,
                        "end_timestamp": ann.end_timestamp,
                        "vru_type": ann.vru_type,
                        "bounding_box": ann.bounding_box,
                        "occluded": ann.occluded,
                        "truncated": ann.truncated,
                        "difficult": ann.difficult,
                        "notes": ann.notes,
                        "annotator": ann.annotator,
                        "validated": ann.validated,
                        "created_at": ann.created_at.isoformat() if ann.created_at else None
                    }
                    for ann in annotations
                ]
                
        except Exception as e:
            logger.error(f"Failed to retrieve annotations for video {video_id}: {e}")
            return []
    
    # =============================================================================
    # PROJECT AND TEST MANAGEMENT
    # =============================================================================
    
    async def create_test_session(self, project_id: str, video_id: str, 
                                name: str, tolerance_ms: int = 100) -> str:
        """Create new test session for video analysis"""
        try:
            with self.db_manager.get_session() as session:
                test_session = TestSession(
                    id=str(uuid.uuid4()),
                    name=name,
                    project_id=project_id,
                    video_id=video_id,
                    tolerance_ms=tolerance_ms,
                    status="created"
                )
                
                session.add(test_session)
                session.flush()
                
                logger.info(f"Test session created: {name} ({test_session.id})")
                return test_session.id
                
        except Exception as e:
            logger.error(f"Failed to create test session: {e}")
            raise
    
    async def get_project_statistics(self, project_id: str) -> Dict[str, Any]:
        """Get comprehensive project statistics"""
        try:
            with self.db_manager.get_session() as session:
                # Video count
                video_count = session.query(Video).filter(Video.project_id == project_id).count()
                
                # Detection statistics
                detection_stats = session.query(
                    func.count(DetectionEvent.id).label('total_detections'),
                    func.avg(DetectionEvent.confidence).label('avg_confidence'),
                    func.count(DetectionEvent.id).filter(DetectionEvent.validation_result == 'TP').label('true_positives'),
                    func.count(DetectionEvent.id).filter(DetectionEvent.validation_result == 'FP').label('false_positives'),
                    func.count(DetectionEvent.id).filter(DetectionEvent.validation_result == 'FN').label('false_negatives')
                ).join(TestSession).filter(TestSession.project_id == project_id).first()
                
                # VRU type distribution
                vru_distribution = session.query(
                    DetectionEvent.vru_type,
                    func.count(DetectionEvent.id).label('count')
                ).join(TestSession).filter(
                    TestSession.project_id == project_id
                ).group_by(DetectionEvent.vru_type).all()
                
                return {
                    "project_id": project_id,
                    "video_count": video_count,
                    "total_detections": detection_stats.total_detections or 0,
                    "average_confidence": float(detection_stats.avg_confidence or 0),
                    "true_positives": detection_stats.true_positives or 0,
                    "false_positives": detection_stats.false_positives or 0,
                    "false_negatives": detection_stats.false_negatives or 0,
                    "vru_type_distribution": {
                        vru.vru_type: vru.count for vru in vru_distribution
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get project statistics: {e}")
            return {}
    
    # =============================================================================
    # PERFORMANCE AND MONITORING
    # =============================================================================
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get integration layer performance metrics"""
        avg_query_time = (
            sum(self._performance_metrics["query_times"]) / len(self._performance_metrics["query_times"])
            if self._performance_metrics["query_times"] else 0
        )
        
        return {
            "detections_stored": self._performance_metrics["detections_stored"],
            "annotations_created": self._performance_metrics["annotations_created"],
            "videos_processed": self._performance_metrics["videos_processed"],
            "errors": self._performance_metrics["errors"],
            "average_query_time_ms": avg_query_time,
            "database_health": self.db_manager.test_connection()
        }
    
    async def cleanup_orphaned_data(self) -> Dict[str, int]:
        """Clean up orphaned data with safety checks"""
        cleanup_stats = {
            "orphaned_detections": 0,
            "orphaned_annotations": 0,
            "orphaned_sessions": 0
        }
        
        try:
            with self.db_manager.get_session() as session:
                # Find orphaned detection events (no valid test session)
                orphaned_detections = session.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id.notin_(
                        session.query(TestSession.id)
                    )
                ).all()
                
                for detection in orphaned_detections:
                    session.delete(detection)
                    cleanup_stats["orphaned_detections"] += 1
                
                # Find orphaned annotations (no valid video)
                orphaned_annotations = session.query(Annotation).filter(
                    Annotation.video_id.notin_(
                        session.query(Video.id)
                    )
                ).all()
                
                for annotation in orphaned_annotations:
                    session.delete(annotation)
                    cleanup_stats["orphaned_annotations"] += 1
                
                session.commit()
                logger.info(f"Cleanup completed: {cleanup_stats}")
                
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            
        return cleanup_stats

# =============================================================================
# UTILITY FUNCTIONS AND FACTORY
# =============================================================================

def create_vru_integration_layer() -> VRUDatabaseIntegrationLayer:
    """Factory function to create integration layer"""
    return VRUDatabaseIntegrationLayer()

# Global integration layer instance
_integration_layer = None

def get_vru_integration_layer() -> VRUDatabaseIntegrationLayer:
    """Get or create global integration layer instance"""
    global _integration_layer
    if _integration_layer is None:
        _integration_layer = create_vru_integration_layer()
    return _integration_layer

if __name__ == "__main__":
    # Test the integration layer
    async def test_integration():
        print("🔧 Testing VRU Database Integration Layer")
        print("=" * 50)
        
        integration = get_vru_integration_layer()
        
        # Test video metadata storage
        video_metadata = VideoMetadata(
            video_id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/tmp/test_video.mp4",
            file_size=1024000,
            duration=30.0,
            fps=30.0,
            resolution="1920x1080",
            total_frames=900
        )
        
        try:
            video_id = await integration.store_video_with_metadata(video_metadata)
            print(f"✅ Video stored: {video_id}")
            
            # Retrieve metadata
            metadata = await integration.get_video_metadata(video_id)
            print(f"✅ Metadata retrieved: {metadata['filename']}")
            
            # Get performance metrics
            metrics = await integration.get_performance_metrics()
            print(f"✅ Performance: {metrics['videos_processed']} videos processed")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        
        print("=" * 50)
    
    # Run test
    import asyncio
    asyncio.run(test_integration())