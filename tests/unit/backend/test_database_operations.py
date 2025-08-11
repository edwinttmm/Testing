"""
Unit tests for database operations in the Hive Mind system.
Tests CRUD operations, relationships, queries, and data integrity.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import json
from typing import List, Optional

# Mock database models (in real implementation, import from your models)
Base = declarative_base()

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    size = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    resolution = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    status = Column(String, default="uploaded")
    
    detections = relationship("Detection", back_populates="video", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="video")

class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    timestamp = Column(Float, nullable=False)
    bbox_x = Column(Float, nullable=False)
    bbox_y = Column(Float, nullable=False)
    bbox_width = Column(Float, nullable=False)
    bbox_height = Column(Float, nullable=False)
    class_name = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    track_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    video = relationship("Video", back_populates="detections")

class GroundTruth(Base):
    __tablename__ = "ground_truth"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, nullable=False)
    timestamp = Column(Float, nullable=False)
    bbox_x = Column(Float, nullable=False)
    bbox_y = Column(Float, nullable=False)
    bbox_width = Column(Float, nullable=False)
    bbox_height = Column(Float, nullable=False)
    class_name = Column(String, nullable=False)
    metadata = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(String, primary_key=True)
    video_id = Column(String, ForeignKey("videos.id"))
    report_type = Column(String, nullable=False)
    config = Column(Text)  # JSON string
    status = Column(String, default="pending")
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    video = relationship("Video", back_populates="reports")

class HardwareStatus(Base):
    __tablename__ = "hardware_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String, nullable=False)
    device_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    temperature = Column(Float)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    is_connected = Column(Boolean, default=True)
    last_ping = Column(DateTime, default=datetime.utcnow)
    metadata = Column(Text)  # JSON string

# Database service class for testing
class DatabaseService:
    def __init__(self, session):
        self.session = session
    
    # Video operations
    def create_video(self, video_data: dict) -> Video:
        video = Video(**video_data)
        self.session.add(video)
        self.session.commit()
        self.session.refresh(video)
        return video
    
    def get_video(self, video_id: str) -> Optional[Video]:
        return self.session.query(Video).filter(Video.id == video_id).first()
    
    def get_videos(self, limit: int = 100, offset: int = 0) -> List[Video]:
        return self.session.query(Video).offset(offset).limit(limit).all()
    
    def update_video(self, video_id: str, updates: dict) -> Optional[Video]:
        video = self.get_video(video_id)
        if video:
            for key, value in updates.items():
                setattr(video, key, value)
            self.session.commit()
            self.session.refresh(video)
        return video
    
    def delete_video(self, video_id: str) -> bool:
        video = self.get_video(video_id)
        if video:
            self.session.delete(video)
            self.session.commit()
            return True
        return False
    
    # Detection operations
    def create_detection(self, detection_data: dict) -> Detection:
        detection = Detection(**detection_data)
        self.session.add(detection)
        self.session.commit()
        self.session.refresh(detection)
        return detection
    
    def get_detections_by_video(self, video_id: str) -> List[Detection]:
        return self.session.query(Detection).filter(Detection.video_id == video_id).all()
    
    def get_detections_by_timerange(self, video_id: str, start_time: float, end_time: float) -> List[Detection]:
        return self.session.query(Detection).filter(
            Detection.video_id == video_id,
            Detection.timestamp >= start_time,
            Detection.timestamp <= end_time
        ).all()
    
    def bulk_create_detections(self, detections_data: List[dict]) -> List[Detection]:
        detections = [Detection(**data) for data in detections_data]
        self.session.add_all(detections)
        self.session.commit()
        return detections
    
    # Ground truth operations
    def create_ground_truth(self, gt_data: dict) -> GroundTruth:
        if 'metadata' in gt_data and isinstance(gt_data['metadata'], dict):
            gt_data['metadata'] = json.dumps(gt_data['metadata'])
        
        gt = GroundTruth(**gt_data)
        self.session.add(gt)
        self.session.commit()
        self.session.refresh(gt)
        return gt
    
    def get_ground_truth_by_video(self, video_id: str) -> List[GroundTruth]:
        return self.session.query(GroundTruth).filter(GroundTruth.video_id == video_id).all()
    
    # Report operations
    def create_report(self, report_data: dict) -> Report:
        if 'config' in report_data and isinstance(report_data['config'], dict):
            report_data['config'] = json.dumps(report_data['config'])
        
        report = Report(**report_data)
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return report
    
    def update_report_status(self, report_id: str, status: str, file_path: str = None) -> Optional[Report]:
        report = self.session.query(Report).filter(Report.id == report_id).first()
        if report:
            report.status = status
            if file_path:
                report.file_path = file_path
            if status == "completed":
                report.completed_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(report)
        return report
    
    # Hardware status operations
    def record_hardware_status(self, status_data: dict) -> HardwareStatus:
        if 'metadata' in status_data and isinstance(status_data['metadata'], dict):
            status_data['metadata'] = json.dumps(status_data['metadata'])
        
        status = HardwareStatus(**status_data)
        self.session.add(status)
        self.session.commit()
        self.session.refresh(status)
        return status
    
    def get_latest_hardware_status(self, device_type: str, device_id: str) -> Optional[HardwareStatus]:
        return self.session.query(HardwareStatus).filter(
            HardwareStatus.device_type == device_type,
            HardwareStatus.device_id == device_id
        ).order_by(HardwareStatus.last_ping.desc()).first()

@pytest.fixture
def db_service(test_db_session):
    # Create tables
    Base.metadata.create_all(bind=test_db_session.bind)
    return DatabaseService(test_db_session)

class TestVideoOperations:
    """Test video CRUD operations."""
    
    def test_create_video_success(self, db_service):
        video_data = {
            "id": "test_video_001",
            "filename": "test_video.mp4",
            "file_path": "/uploads/test_video.mp4",
            "size": 1024000,
            "duration": 120.5,
            "fps": 30.0,
            "resolution": "1920x1080"
        }
        
        video = db_service.create_video(video_data)
        
        assert video.id == "test_video_001"
        assert video.filename == "test_video.mp4"
        assert video.size == 1024000
        assert video.uploaded_at is not None
        assert video.status == "uploaded"
    
    def test_create_video_duplicate_id(self, db_service):
        video_data = {
            "id": "duplicate_video",
            "filename": "video1.mp4",
            "file_path": "/uploads/video1.mp4"
        }
        
        # Create first video
        db_service.create_video(video_data)
        
        # Attempt to create duplicate
        with pytest.raises(IntegrityError):
            db_service.create_video(video_data)
    
    def test_get_video_exists(self, db_service):
        video_data = {
            "id": "test_get_video",
            "filename": "get_test.mp4",
            "file_path": "/uploads/get_test.mp4"
        }
        
        created_video = db_service.create_video(video_data)
        retrieved_video = db_service.get_video("test_get_video")
        
        assert retrieved_video is not None
        assert retrieved_video.id == created_video.id
        assert retrieved_video.filename == created_video.filename
    
    def test_get_video_not_exists(self, db_service):
        video = db_service.get_video("nonexistent_video")
        assert video is None
    
    def test_get_videos_pagination(self, db_service):
        # Create multiple videos
        for i in range(15):
            video_data = {
                "id": f"video_{i:03d}",
                "filename": f"video_{i}.mp4",
                "file_path": f"/uploads/video_{i}.mp4"
            }
            db_service.create_video(video_data)
        
        # Test pagination
        first_page = db_service.get_videos(limit=10, offset=0)
        second_page = db_service.get_videos(limit=10, offset=10)
        
        assert len(first_page) == 10
        assert len(second_page) == 5
        
        # Ensure no duplicates
        first_ids = {v.id for v in first_page}
        second_ids = {v.id for v in second_page}
        assert len(first_ids.intersection(second_ids)) == 0
    
    def test_update_video_success(self, db_service):
        video_data = {
            "id": "update_test_video",
            "filename": "original.mp4",
            "file_path": "/uploads/original.mp4"
        }
        
        created_video = db_service.create_video(video_data)
        
        updates = {
            "status": "processed",
            "processed_at": datetime.utcnow(),
            "duration": 95.5
        }
        
        updated_video = db_service.update_video("update_test_video", updates)
        
        assert updated_video.status == "processed"
        assert updated_video.processed_at is not None
        assert updated_video.duration == 95.5
    
    def test_delete_video_success(self, db_service):
        video_data = {
            "id": "delete_test_video",
            "filename": "delete_test.mp4",
            "file_path": "/uploads/delete_test.mp4"
        }
        
        db_service.create_video(video_data)
        
        # Verify video exists
        assert db_service.get_video("delete_test_video") is not None
        
        # Delete video
        deleted = db_service.delete_video("delete_test_video")
        assert deleted is True
        
        # Verify video is gone
        assert db_service.get_video("delete_test_video") is None
    
    def test_delete_video_not_exists(self, db_service):
        deleted = db_service.delete_video("nonexistent_video")
        assert deleted is False

class TestDetectionOperations:
    """Test detection CRUD operations."""
    
    def test_create_detection_success(self, db_service):
        # Create video first
        video_data = {
            "id": "video_for_detection",
            "filename": "detection_test.mp4",
            "file_path": "/uploads/detection_test.mp4"
        }
        db_service.create_video(video_data)
        
        detection_data = {
            "video_id": "video_for_detection",
            "timestamp": 15.5,
            "bbox_x": 100.0,
            "bbox_y": 150.0,
            "bbox_width": 200.0,
            "bbox_height": 300.0,
            "class_name": "person",
            "confidence": 0.95,
            "track_id": 1
        }
        
        detection = db_service.create_detection(detection_data)
        
        assert detection.video_id == "video_for_detection"
        assert detection.timestamp == 15.5
        assert detection.class_name == "person"
        assert detection.confidence == 0.95
        assert detection.created_at is not None
    
    def test_get_detections_by_video(self, db_service):
        # Create video
        video_data = {
            "id": "video_with_detections",
            "filename": "detections_test.mp4",
            "file_path": "/uploads/detections_test.mp4"
        }
        db_service.create_video(video_data)
        
        # Create multiple detections
        detection_data_list = [
            {
                "video_id": "video_with_detections",
                "timestamp": 10.0,
                "bbox_x": 100, "bbox_y": 100, "bbox_width": 50, "bbox_height": 100,
                "class_name": "person", "confidence": 0.9
            },
            {
                "video_id": "video_with_detections",
                "timestamp": 15.0,
                "bbox_x": 200, "bbox_y": 150, "bbox_width": 60, "bbox_height": 80,
                "class_name": "car", "confidence": 0.85
            }
        ]
        
        for detection_data in detection_data_list:
            db_service.create_detection(detection_data)
        
        detections = db_service.get_detections_by_video("video_with_detections")
        
        assert len(detections) == 2
        assert detections[0].class_name in ["person", "car"]
        assert detections[1].class_name in ["person", "car"]
    
    def test_get_detections_by_timerange(self, db_service):
        # Create video
        video_data = {
            "id": "video_timerange_test",
            "filename": "timerange_test.mp4",
            "file_path": "/uploads/timerange_test.mp4"
        }
        db_service.create_video(video_data)
        
        # Create detections at different timestamps
        timestamps = [5.0, 15.0, 25.0, 35.0, 45.0]
        for i, timestamp in enumerate(timestamps):
            detection_data = {
                "video_id": "video_timerange_test",
                "timestamp": timestamp,
                "bbox_x": 100, "bbox_y": 100, "bbox_width": 50, "bbox_height": 50,
                "class_name": f"object_{i}", "confidence": 0.9
            }
            db_service.create_detection(detection_data)
        
        # Get detections in range [10.0, 30.0]
        detections = db_service.get_detections_by_timerange("video_timerange_test", 10.0, 30.0)
        
        assert len(detections) == 2  # timestamps 15.0 and 25.0
        timestamps_found = [d.timestamp for d in detections]
        assert 15.0 in timestamps_found
        assert 25.0 in timestamps_found
    
    def test_bulk_create_detections(self, db_service):
        # Create video
        video_data = {
            "id": "bulk_video",
            "filename": "bulk_test.mp4",
            "file_path": "/uploads/bulk_test.mp4"
        }
        db_service.create_video(video_data)
        
        # Bulk create detections
        bulk_data = []
        for i in range(100):
            bulk_data.append({
                "video_id": "bulk_video",
                "timestamp": float(i),
                "bbox_x": 100 + i, "bbox_y": 100, "bbox_width": 50, "bbox_height": 50,
                "class_name": "person" if i % 2 == 0 else "car",
                "confidence": 0.8 + (i % 10) * 0.02
            })
        
        detections = db_service.bulk_create_detections(bulk_data)
        
        assert len(detections) == 100
        
        # Verify they're in database
        db_detections = db_service.get_detections_by_video("bulk_video")
        assert len(db_detections) == 100

class TestGroundTruthOperations:
    """Test ground truth data operations."""
    
    def test_create_ground_truth_success(self, db_service):
        gt_data = {
            "video_id": "gt_test_video",
            "timestamp": 12.5,
            "bbox_x": 150.0,
            "bbox_y": 200.0,
            "bbox_width": 100.0,
            "bbox_height": 150.0,
            "class_name": "pedestrian",
            "metadata": {"annotator": "human_1", "quality": "high"}
        }
        
        gt = db_service.create_ground_truth(gt_data)
        
        assert gt.video_id == "gt_test_video"
        assert gt.class_name == "pedestrian"
        assert gt.metadata is not None
        
        # Verify metadata is properly stored as JSON
        metadata = json.loads(gt.metadata)
        assert metadata["annotator"] == "human_1"
        assert metadata["quality"] == "high"
    
    def test_get_ground_truth_by_video(self, db_service):
        video_id = "gt_video_test"
        
        # Create multiple ground truth entries
        gt_entries = [
            {
                "video_id": video_id, "timestamp": 10.0,
                "bbox_x": 100, "bbox_y": 100, "bbox_width": 50, "bbox_height": 100,
                "class_name": "person"
            },
            {
                "video_id": video_id, "timestamp": 20.0,
                "bbox_x": 200, "bbox_y": 150, "bbox_width": 80, "bbox_height": 120,
                "class_name": "bicycle"
            }
        ]
        
        for gt_data in gt_entries:
            db_service.create_ground_truth(gt_data)
        
        retrieved_gt = db_service.get_ground_truth_by_video(video_id)
        
        assert len(retrieved_gt) == 2
        classes = [gt.class_name for gt in retrieved_gt]
        assert "person" in classes
        assert "bicycle" in classes

class TestReportOperations:
    """Test report CRUD operations."""
    
    def test_create_report_success(self, db_service):
        # Create video first
        video_data = {
            "id": "report_video",
            "filename": "report_test.mp4",
            "file_path": "/uploads/report_test.mp4"
        }
        db_service.create_video(video_data)
        
        report_data = {
            "id": "report_001",
            "video_id": "report_video",
            "report_type": "performance_analysis",
            "config": {"include_charts": True, "format": "pdf"}
        }
        
        report = db_service.create_report(report_data)
        
        assert report.id == "report_001"
        assert report.report_type == "performance_analysis"
        assert report.status == "pending"
        
        # Verify config is stored as JSON
        config = json.loads(report.config)
        assert config["include_charts"] is True
        assert config["format"] == "pdf"
    
    def test_update_report_status(self, db_service):
        report_data = {
            "id": "status_update_report",
            "report_type": "summary",
            "config": {}
        }
        
        created_report = db_service.create_report(report_data)
        assert created_report.status == "pending"
        assert created_report.completed_at is None
        
        # Update to completed
        updated_report = db_service.update_report_status(
            "status_update_report",
            "completed",
            "/reports/status_update_report.pdf"
        )
        
        assert updated_report.status == "completed"
        assert updated_report.file_path == "/reports/status_update_report.pdf"
        assert updated_report.completed_at is not None

class TestHardwareStatusOperations:
    """Test hardware status logging operations."""
    
    def test_record_hardware_status_success(self, db_service):
        status_data = {
            "device_type": "raspberry_pi",
            "device_id": "pi_001",
            "status": "online",
            "temperature": 45.2,
            "cpu_usage": 25.6,
            "memory_usage": 512.0,
            "disk_usage": 75.3,
            "is_connected": True,
            "metadata": {"location": "intersection_1", "version": "v1.2.3"}
        }
        
        status = db_service.record_hardware_status(status_data)
        
        assert status.device_type == "raspberry_pi"
        assert status.device_id == "pi_001"
        assert status.temperature == 45.2
        assert status.is_connected is True
        
        # Verify metadata
        metadata = json.loads(status.metadata)
        assert metadata["location"] == "intersection_1"
        assert metadata["version"] == "v1.2.3"
    
    def test_get_latest_hardware_status(self, db_service):
        device_type = "camera"
        device_id = "cam_001"
        
        # Record multiple status entries
        for i in range(5):
            status_data = {
                "device_type": device_type,
                "device_id": device_id,
                "status": "online" if i < 3 else "offline",
                "temperature": 40.0 + i,
                "last_ping": datetime.utcnow() - timedelta(minutes=5-i)
            }
            db_service.record_hardware_status(status_data)
        
        latest_status = db_service.get_latest_hardware_status(device_type, device_id)
        
        assert latest_status is not None
        assert latest_status.status == "offline"  # Most recent entry
        assert latest_status.temperature == 44.0  # Last entry temp

class TestDatabaseRelationships:
    """Test database relationships and cascading operations."""
    
    def test_video_detection_relationship(self, db_service):
        # Create video
        video_data = {
            "id": "relationship_video",
            "filename": "relationship_test.mp4",
            "file_path": "/uploads/relationship_test.mp4"
        }
        video = db_service.create_video(video_data)
        
        # Create detection
        detection_data = {
            "video_id": "relationship_video",
            "timestamp": 10.0,
            "bbox_x": 100, "bbox_y": 100, "bbox_width": 50, "bbox_height": 50,
            "class_name": "person", "confidence": 0.9
        }
        detection = db_service.create_detection(detection_data)
        
        # Test relationship
        assert detection.video == video
        assert detection in video.detections
    
    def test_cascade_delete_video_detections(self, db_service):
        # Create video with detections
        video_data = {
            "id": "cascade_video",
            "filename": "cascade_test.mp4",
            "file_path": "/uploads/cascade_test.mp4"
        }
        db_service.create_video(video_data)
        
        # Add detections
        for i in range(3):
            detection_data = {
                "video_id": "cascade_video",
                "timestamp": float(i * 10),
                "bbox_x": 100, "bbox_y": 100, "bbox_width": 50, "bbox_height": 50,
                "class_name": "person", "confidence": 0.9
            }
            db_service.create_detection(detection_data)
        
        # Verify detections exist
        detections = db_service.get_detections_by_video("cascade_video")
        assert len(detections) == 3
        
        # Delete video (should cascade to detections)
        db_service.delete_video("cascade_video")
        
        # Verify detections are also deleted
        detections_after_delete = db_service.get_detections_by_video("cascade_video")
        assert len(detections_after_delete) == 0

@pytest.mark.performance
class TestDatabasePerformance:
    """Test database performance characteristics."""
    
    def test_bulk_insert_performance(self, db_service, performance_monitor):
        # Create video
        video_data = {
            "id": "perf_video",
            "filename": "perf_test.mp4",
            "file_path": "/uploads/perf_test.mp4"
        }
        db_service.create_video(video_data)
        
        # Prepare bulk data
        bulk_data = []
        for i in range(1000):
            bulk_data.append({
                "video_id": "perf_video",
                "timestamp": float(i * 0.1),
                "bbox_x": 100 + (i % 100), "bbox_y": 100, 
                "bbox_width": 50, "bbox_height": 50,
                "class_name": "person", "confidence": 0.8 + (i % 10) * 0.02
            })
        
        performance_monitor.start_timer("bulk_insert")
        db_service.bulk_create_detections(bulk_data)
        duration = performance_monitor.end_timer("bulk_insert")
        
        # Should insert 1000 records in under 1 second
        assert duration < 1.0
        
        # Verify count
        detections = db_service.get_detections_by_video("perf_video")
        assert len(detections) == 1000
    
    def test_query_performance_with_indexes(self, db_service, performance_monitor):
        # Setup: Create video and many detections
        video_data = {
            "id": "query_perf_video",
            "filename": "query_perf.mp4",
            "file_path": "/uploads/query_perf.mp4"
        }
        db_service.create_video(video_data)
        
        # Insert many detections
        bulk_data = []
        for i in range(5000):
            bulk_data.append({
                "video_id": "query_perf_video",
                "timestamp": float(i * 0.1),
                "bbox_x": 100, "bbox_y": 100, "bbox_width": 50, "bbox_height": 50,
                "class_name": f"class_{i % 10}", "confidence": 0.8
            })
        db_service.bulk_create_detections(bulk_data)
        
        # Test query performance
        performance_monitor.start_timer("timerange_query")
        detections = db_service.get_detections_by_timerange("query_perf_video", 100.0, 200.0)
        duration = performance_monitor.end_timer("timerange_query")
        
        # Query should complete quickly even with large dataset
        assert duration < 0.5
        assert len(detections) > 0