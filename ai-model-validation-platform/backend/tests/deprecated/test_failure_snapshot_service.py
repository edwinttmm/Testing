"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_failure_snapshot_service.py
"""

#!/usr/bin/env python3
"""
Comprehensive test suite for Enhanced Failure Snapshot Service
PRD Module 3.3 validation
"""

import pytest
import asyncio
import cv2
import numpy as np
import tempfile
import json
from pathlib import Path
from datetime import datetime

from services.failure_snapshot_service import FailureSnapshotService

class TestFailureSnapshotService:
    """Test suite for comprehensive failure snapshot functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield tmp_dir
    
    @pytest.fixture
    def snapshot_service(self, temp_dir):
        """Create snapshot service instance"""
        return FailureSnapshotService(temp_dir)
    
    @pytest.fixture
    def test_video(self, temp_dir):
        """Create test video file"""
        video_path = Path(temp_dir) / "test_video.mp4"
        
        # Create simple test video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
        
        # Generate 300 frames (10 seconds at 30 fps)
        for frame_num in range(300):
            # Create frame with moving rectangle
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Add moving rectangle to simulate detection target
            x = int(50 + (frame_num * 2) % 500)
            y = int(100 + (frame_num % 200))
            cv2.rectangle(frame, (x, y), (x + 80, y + 60), (0, 255, 0), -1)
            
            # Add frame number overlay
            cv2.putText(frame, f"Frame {frame_num}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            out.write(frame)
        
        out.release()
        return str(video_path)
    
    @pytest.mark.asyncio
    async def test_basic_failure_snapshot_capture(self, snapshot_service, test_video):
        """Test basic failure snapshot capture functionality"""
        
        event_id = "test-event-001"
        timestamp_ms = 5000.0  # 5 seconds
        failure_type = "HIGH_LATENCY"
        
        result = await snapshot_service.capture_failure_snapshot(
            video_path=test_video,
            timestamp_ms=timestamp_ms,
            failure_type=failure_type,
            event_id=event_id
        )
        
        assert result is not None
        assert result["failure_type"] == failure_type
        assert result["event_id"] == event_id
        assert result["timestamp_ms"] == timestamp_ms
        assert "snapshots" in result
        assert "full" in result["snapshots"]
        
        # Verify file was created
        full_snapshot = result["snapshots"]["full"]
        assert Path(full_snapshot["path"]).exists()
        assert full_snapshot["size"] > 0
    
    @pytest.mark.asyncio
    async def test_detection_data_overlay(self, snapshot_service, test_video):
        """Test snapshot capture with detection data overlays"""
        
        detection_data = {
            "bounding_box": {"x": 100, "y": 100, "width": 80, "height": 60},
            "confidence": 0.85,
            "class_label": "pedestrian"
        }
        
        result = await snapshot_service.capture_failure_snapshot(
            video_path=test_video,
            timestamp_ms=3000.0,
            failure_type="ACCURACY",
            event_id="test-accuracy-001",
            detection_data=detection_data
        )
        
        assert result is not None
        assert result["detection_data"] == detection_data
        assert "full" in result["snapshots"]
        assert "zoom" in result["snapshots"]  # Should have zoomed region
        
        # Verify both full and zoom files exist
        full_path = Path(result["snapshots"]["full"]["path"])
        zoom_path = Path(result["snapshots"]["zoom"]["path"])
        
        assert full_path.exists()
        assert zoom_path.exists()
        assert zoom_path.stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_comparison_view_generation(self, snapshot_service, test_video):
        """Test side-by-side comparison view generation"""
        
        detection_data = {
            "bounding_box": {"x": 120, "y": 110, "width": 70, "height": 55},
            "confidence": 0.75,
            "class_label": "cyclist"
        }
        
        ground_truth_data = {
            "bounding_box": {"x": 100, "y": 100, "width": 80, "height": 60},
            "class_label": "pedestrian"
        }
        
        result = await snapshot_service.capture_failure_snapshot(
            video_path=test_video,
            timestamp_ms=7000.0,
            failure_type="MISSED_DETECTION",
            event_id="test-comparison-001",
            detection_data=detection_data,
            ground_truth_data=ground_truth_data
        )
        
        assert result is not None
        assert "comparison" in result["snapshots"]
        assert result["total_snapshots"] >= 2
        
        # Verify comparison file exists and is larger (side-by-side)
        comparison_path = Path(result["snapshots"]["comparison"]["path"])
        full_path = Path(result["snapshots"]["full"]["path"])
        
        assert comparison_path.exists()
        
        # Load and check image dimensions
        comparison_img = cv2.imread(str(comparison_path))
        full_img = cv2.imread(str(full_path))
        
        assert comparison_img.shape[1] >= full_img.shape[1] * 1.8  # Should be ~2x wider
    
    @pytest.mark.asyncio
    async def test_multiple_failure_types(self, snapshot_service, test_video):
        """Test different failure types with appropriate color coding"""
        
        failure_types = ["HIGH_LATENCY", "MISSED_DETECTION", "ACCURACY", "SYSTEM"]
        results = []
        
        for i, failure_type in enumerate(failure_types):
            result = await snapshot_service.capture_failure_snapshot(
                video_path=test_video,
                timestamp_ms=1000.0 + (i * 2000),
                failure_type=failure_type,
                event_id=f"test-{failure_type.lower()}-001"
            )
            
            assert result is not None
            assert result["failure_type"] == failure_type
            results.append(result)
        
        # Verify all snapshots were created with different filenames
        filenames = set()
        for result in results:
            filename = result["snapshots"]["full"]["filename"]
            assert filename not in filenames
            filenames.add(filename)
        
        assert len(filenames) == len(failure_types)
    
    def test_snapshot_statistics(self, snapshot_service):
        """Test snapshot statistics gathering"""
        
        # Create some mock snapshot files
        full_dir = snapshot_service.full_frame_dir
        zoom_dir = snapshot_service.zoomed_dir
        comp_dir = snapshot_service.comparison_dir
        
        # Create test files
        test_files = [
            full_dir / "high_latency_test1_20240101_120000_full.jpg",
            zoom_dir / "high_latency_test1_20240101_120000_zoom.jpg",
            comp_dir / "missed_detection_test2_20240101_120100_comparison.jpg"
        ]
        
        for file_path in test_files:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Write dummy data
            with open(file_path, 'wb') as f:
                f.write(b"dummy_image_data" * 100)  # Create some file size
        
        stats = snapshot_service.get_snapshot_stats()
        
        assert stats is not None
        assert "full_frame" in stats
        assert "zoomed" in stats
        assert "comparison" in stats
        assert "total_snapshots" in stats
        assert "total_size_mb" in stats
        assert "failure_type_breakdown" in stats
        
        assert stats["total_snapshots"] > 0
        assert stats["total_size_mb"] > 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, snapshot_service):
        """Test error handling for invalid inputs"""
        
        # Test with non-existent video file
        result = await snapshot_service.capture_failure_snapshot(
            video_path="/nonexistent/video.mp4",
            timestamp_ms=1000.0,
            failure_type="HIGH_LATENCY",
            event_id="error-test-001"
        )
        
        assert result is None
        
        # Test with invalid timestamp
        result = await snapshot_service.capture_failure_snapshot(
            video_path="valid_but_not_tested.mp4",  # This will still fail file check
            timestamp_ms=-1000.0,  # Negative timestamp
            failure_type="HIGH_LATENCY", 
            event_id="error-test-002"
        )
        
        assert result is None
    
    def test_cleanup_functionality(self, snapshot_service, temp_dir):
        """Test snapshot cleanup functionality"""
        
        # Create old test files
        old_file = snapshot_service.full_frame_dir / "old_snapshot.jpg"
        old_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(old_file, 'w') as f:
            f.write("old snapshot data")
        
        # Manually set old timestamp (30+ days old)
        import time
        old_timestamp = time.time() - (31 * 24 * 60 * 60)  # 31 days ago
        old_file.touch(times=(old_timestamp, old_timestamp))
        
        # Verify file exists before cleanup
        assert old_file.exists()
        
        # Run cleanup
        snapshot_service.cleanup_old_snapshots(days_old=30)
        
        # Verify old file was removed
        assert not old_file.exists()
    
    @pytest.mark.asyncio
    async def test_concurrent_snapshot_capture(self, snapshot_service, test_video):
        """Test concurrent snapshot capture operations"""
        
        # Create multiple concurrent capture tasks
        tasks = []
        for i in range(5):
            task = snapshot_service.capture_failure_snapshot(
                video_path=test_video,
                timestamp_ms=1000.0 + (i * 500),
                failure_type="HIGH_LATENCY",
                event_id=f"concurrent-test-{i:03d}"
            )
            tasks.append(task)
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all succeeded
        assert all(result is not None for result in results)
        
        # Verify unique filenames
        filenames = set()
        for result in results:
            filename = result["snapshots"]["full"]["filename"]
            assert filename not in filenames
            filenames.add(filename)
        
        assert len(filenames) == 5
    
    def test_directory_structure_creation(self, temp_dir):
        """Test proper directory structure creation"""
        
        service = FailureSnapshotService(temp_dir)
        
        # Verify all required directories were created
        assert service.snapshots_dir.exists()
        assert service.failure_snapshots_dir.exists()
        assert service.full_frame_dir.exists()
        assert service.zoomed_dir.exists()
        assert service.comparison_dir.exists()
        
        # Verify directory hierarchy
        assert service.full_frame_dir.parent == service.failure_snapshots_dir
        assert service.zoomed_dir.parent == service.failure_snapshots_dir
        assert service.comparison_dir.parent == service.failure_snapshots_dir

if __name__ == "__main__":
    pytest.main([__file__, "-v"])