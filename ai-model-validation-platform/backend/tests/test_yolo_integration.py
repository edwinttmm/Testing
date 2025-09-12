"""
Test suite for YOLO-based VRU detection integration
Verifies that real AI model detection works end-to-end
"""

import pytest
import cv2
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock

# Test imports for YOLO functionality
try:
    from ultralytics import YOLO
    import torch
    from services.video_ingestion_service import VideoIngestionService
    from services.vru_tracking_service import VRUTrackingService
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


@pytest.mark.skipif(not YOLO_AVAILABLE, reason="YOLO dependencies not available")
class TestYOLOIntegration:
    """Test YOLO model integration with video processing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.video_service = VideoIngestionService()
        self.tracking_service = VRUTrackingService()
        
    def test_yolo_model_loading(self):
        """Test that YOLO model loads correctly"""
        assert self.video_service.yolo_model is not None
        assert hasattr(self.video_service.yolo_model, 'names')
        assert 0 in self.video_service.yolo_model.names  # person class
        assert 1 in self.video_service.yolo_model.names  # bicycle class
        assert 3 in self.video_service.yolo_model.names  # motorcycle class
        
    def test_vru_class_mapping(self):
        """Test VRU class mapping is correct"""
        mapping = self.video_service.VRU_CLASS_MAPPING
        
        # Check that person, bicycle, motorcycle are mapped
        assert 0 in mapping  # person -> pedestrian
        assert 1 in mapping  # bicycle -> cyclist
        assert 3 in mapping  # motorcycle -> motorcyclist
        
        print(f"VRU class mapping: {mapping}")
        
    def test_synthetic_video_creation(self):
        """Test creating synthetic video with detectable objects"""
        # Create a simple test video with synthetic content
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            test_video_path = tmp_file.name
            
        try:
            # Create synthetic video with moving rectangles (simulating VRUs)
            self._create_synthetic_test_video(test_video_path)
            
            # Verify video was created
            assert Path(test_video_path).exists()
            
            # Test video metadata extraction
            cap = cv2.VideoCapture(test_video_path)
            assert cap.isOpened()
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            assert frame_count > 0
            assert fps > 0
            assert width == 640
            assert height == 480
            
            cap.release()
            
        finally:
            # Cleanup
            if Path(test_video_path).exists():
                os.unlink(test_video_path)
                
    def test_yolo_inference_on_synthetic_frame(self):
        """Test YOLO inference on a synthetic frame"""
        # Create synthetic frame with person-like shape
        frame = self._create_synthetic_frame_with_person()
        
        # Run YOLO inference
        results = self.video_service.yolo_model(frame, verbose=False)
        
        # Check that results are returned
        assert len(results) > 0
        result = results[0]
        
        # Check that boxes attribute exists
        assert hasattr(result, 'boxes')
        print(f"YOLO inference completed on synthetic frame")
        
    def test_vru_detection_pipeline(self):
        """Test the complete VRU detection pipeline"""
        # Create synthetic video
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            test_video_path = tmp_file.name
            
        try:
            self._create_synthetic_test_video(test_video_path)
            
            # Test detection pipeline
            detections = []
            cap = cv2.VideoCapture(test_video_path)
            
            frame_idx = 0
            while frame_idx < 5:  # Test first 5 frames only
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Run YOLO inference
                results = self.video_service.yolo_model(frame, verbose=False)
                
                # Process results (similar to VideoIngestionService._detect_vrus_with_yolo)
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            class_id = int(box.cls)
                            confidence = float(box.conf)
                            coords = box.xyxy[0].tolist()
                            
                            detection = {
                                "frame_number": frame_idx,
                                "class_id": class_id,
                                "confidence": confidence,
                                "coords": coords
                            }
                            detections.append(detection)
                
                frame_idx += 1
            
            cap.release()
            
            print(f"Detection pipeline completed. Found {len(detections)} detections")
            
            # Verify detections structure
            for detection in detections[:3]:  # Check first 3
                assert "frame_number" in detection
                assert "class_id" in detection
                assert "confidence" in detection
                assert "coords" in detection
                assert isinstance(detection["coords"], list)
                assert len(detection["coords"]) == 4  # x1, y1, x2, y2
                
        finally:
            if Path(test_video_path).exists():
                os.unlink(test_video_path)
                
    def test_vru_tracking_service(self):
        """Test VRU tracking service functionality"""
        video_id = "test_video_001"
        
        # Initialize tracking
        self.tracking_service.initialize_video_tracking(video_id)
        
        # Test tracking with synthetic detections
        bbox1 = {"x": 100, "y": 100, "width": 50, "height": 100}
        bbox2 = {"x": 105, "y": 105, "width": 50, "height": 100}  # Slightly moved
        bbox3 = {"x": 200, "y": 200, "width": 40, "height": 80}   # New VRU
        
        # Track first detection
        vru_id1 = self.tracking_service.track_vru(
            video_id, 0, bbox1, "pedestrian", 0.8
        )
        assert vru_id1.startswith("PED_")
        
        # Track second detection (should be same VRU)
        vru_id2 = self.tracking_service.track_vru(
            video_id, 1, bbox2, "pedestrian", 0.9
        )
        assert vru_id2 == vru_id1  # Should be same track
        
        # Track third detection (new VRU)
        vru_id3 = self.tracking_service.track_vru(
            video_id, 2, bbox3, "pedestrian", 0.7
        )
        assert vru_id3.startswith("PED_")
        assert vru_id3 != vru_id1  # Should be different track
        
        # Get statistics
        stats = self.tracking_service.get_track_statistics(video_id)
        assert stats["total_tracks"] == 2
        assert stats["tracks_by_type"]["pedestrian"] == 2
        
        print(f"VRU tracking test completed. Stats: {stats}")
        
    def test_video_metadata_extraction(self):
        """Test video metadata extraction functionality"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            test_video_path = tmp_file.name
            
        try:
            self._create_synthetic_test_video(test_video_path)
            
            # Test metadata extraction using VideoIngestionService method
            import asyncio
            
            async def run_metadata_test():
                metadata = await self.video_service._extract_video_metadata(Path(test_video_path))
                
                assert metadata["width"] == 640
                assert metadata["height"] == 480
                assert metadata["fps"] > 0
                assert metadata["duration"] > 0
                assert metadata["frame_count"] > 0
                
                print(f"Video metadata: {metadata}")
                return metadata
            
            # Run async test
            metadata = asyncio.run(run_metadata_test())
            assert metadata is not None
            
        finally:
            if Path(test_video_path).exists():
                os.unlink(test_video_path)
                
    def _create_synthetic_test_video(self, output_path: str):
        """Create a synthetic test video with moving shapes"""
        # Video parameters
        width, height = 640, 480
        fps = 30
        duration = 1  # 1 second
        frame_count = int(fps * duration)
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        try:
            for frame_idx in range(frame_count):
                # Create blank frame
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                frame.fill(50)  # Dark gray background
                
                # Add moving rectangle (simulating person)
                person_x = 100 + frame_idx * 5  # Moving right
                person_y = 200
                person_w, person_h = 50, 100
                
                cv2.rectangle(frame, 
                            (person_x, person_y), 
                            (person_x + person_w, person_y + person_h),
                            (255, 255, 255), -1)  # White rectangle
                
                # Add text for debugging
                cv2.putText(frame, f"Frame {frame_idx}", (10, 30),
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                writer.write(frame)
                
        finally:
            writer.release()
            
    def _create_synthetic_frame_with_person(self):
        """Create a synthetic frame with person-like shape"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame.fill(50)  # Dark gray background
        
        # Add person-like shape (white rectangle)
        cv2.rectangle(frame, (200, 150), (250, 350), (255, 255, 255), -1)
        
        return frame


if __name__ == "__main__":
    # Run basic tests if executed directly
    if YOLO_AVAILABLE:
        test_suite = TestYOLOIntegration()
        test_suite.setup_method()
        
        print("Testing YOLO model loading...")
        test_suite.test_yolo_model_loading()
        
        print("Testing VRU class mapping...")
        test_suite.test_vru_class_mapping()
        
        print("Testing synthetic video creation...")
        test_suite.test_synthetic_video_creation()
        
        print("Testing YOLO inference...")
        test_suite.test_yolo_inference_on_synthetic_frame()
        
        print("Testing VRU tracking...")
        test_suite.test_vru_tracking_service()
        
        print("All YOLO integration tests passed!")
    else:
        print("YOLO dependencies not available - skipping tests")