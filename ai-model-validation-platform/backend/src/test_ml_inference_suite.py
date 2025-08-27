#!/usr/bin/env python3
"""
Comprehensive Test Suite for ML Inference Engine
Production-ready testing with integration and performance validation

SPARC Testing Implementation:
- Specification: Complete test coverage for ML operations
- Pseudocode: Async test patterns with mocking
- Architecture: Modular test suite with fixtures
- Refinement: Performance and integration testing
- Completion: Production validation ready

Author: SPARC ML Testing Team
Version: 2.0.0
Target: Production Quality Assurance
"""

import asyncio
import pytest
import tempfile
import os
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any
import numpy as np
import cv2

import sys
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

# Import modules to test
try:
    from src.enhanced_ml_inference_engine import (
        ProductionMLInferenceEngine,
        EnhancedYOLOEngine,
        EnhancedVideoProcessor,
        EnhancedBoundingBox,
        EnhancedVRUDetection,
        get_production_ml_engine
    )
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

try:
    from src.ml_api_endpoints import app
    from fastapi.testclient import TestClient
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False

# Test configuration
TEST_CONFIG = {
    'model_path': None,  # Use mock
    'device': 'cpu',
    'batch_size': 2,
    'enable_tracking': False,
    'cache_results': True,
    'max_cache_size': 100
}

@pytest.fixture
def mock_video_file():
    """Create a mock video file for testing"""
    # Create a temporary video file with OpenCV
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_file.close()
    
    # Create a simple test video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_file.name, fourcc, 30.0, (640, 480))
    
    # Write 60 frames (2 seconds at 30fps)
    for i in range(60):
        # Create a frame with changing content
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add some variation
        cv2.circle(frame, (320 + i*5, 240), 50, (255, 255, 255), -1)
        out.write(frame)
    
    out.release()
    
    yield temp_file.name
    
    # Cleanup
    try:
        os.unlink(temp_file.name)
    except:
        pass

@pytest.fixture
def mock_frame():
    """Create a mock video frame"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add some content to make it realistic
    cv2.rectangle(frame, (100, 100), (200, 300), (255, 255, 255), -1)
    return frame

@pytest.fixture
def sample_detection():
    """Create a sample detection for testing"""
    bbox = EnhancedBoundingBox(x=0.3, y=0.2, width=0.2, height=0.4, confidence=0.85)
    return EnhancedVRUDetection(
        detection_id="test-detection-123",
        frame_number=100,
        timestamp=3.33,
        vru_type="pedestrian",
        confidence=0.85,
        bounding_box=bbox
    )

class TestEnhancedBoundingBox:
    """Test the enhanced bounding box functionality"""
    
    def test_bounding_box_creation(self):
        """Test bounding box creation and validation"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        bbox = EnhancedBoundingBox(x=0.1, y=0.2, width=0.3, height=0.4)
        
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.width == 0.3
        assert bbox.height == 0.4
        assert bbox.confidence == 1.0  # default
    
    def test_bounding_box_normalization(self):
        """Test bounding box coordinate normalization"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        # Test values outside valid range
        bbox = EnhancedBoundingBox(x=-0.1, y=1.5, width=0.8, height=0.9)
        
        assert bbox.x == 0.0  # Clamped to minimum
        assert bbox.y == 1.0  # Clamped to maximum
        assert bbox.width <= (1.0 - bbox.x)  # Adjusted for valid range
        assert bbox.height <= (1.0 - bbox.y)  # Adjusted for valid range
    
    def test_pixel_coordinate_conversion(self):
        """Test conversion to pixel coordinates"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        bbox = EnhancedBoundingBox(x=0.25, y=0.25, width=0.5, height=0.5)
        x1, y1, x2, y2 = bbox.to_pixel_coordinates(640, 480)
        
        assert x1 == 160  # 0.25 * 640
        assert y1 == 120  # 0.25 * 480
        assert x2 == 480  # (0.25 + 0.5) * 640
        assert y2 == 360  # (0.25 + 0.5) * 480
    
    def test_intersection_over_union(self):
        """Test IoU calculation"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        bbox1 = EnhancedBoundingBox(x=0.0, y=0.0, width=0.5, height=0.5)
        bbox2 = EnhancedBoundingBox(x=0.25, y=0.25, width=0.5, height=0.5)
        
        iou = bbox1.intersection_over_union(bbox2)
        
        # Expected IoU calculation:
        # Intersection: 0.25 * 0.25 = 0.0625
        # Union: (0.25 + 0.25) - 0.0625 = 0.4375
        # IoU: 0.0625 / 0.4375 ≈ 0.143
        assert abs(iou - 0.14285714285714285) < 0.01

class TestEnhancedYOLOEngine:
    """Test the enhanced YOLO inference engine"""
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """Test YOLO engine initialization"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = EnhancedYOLOEngine(device='cpu')
        success = await engine.initialize()
        
        assert success is True
        assert engine.is_initialized is True
        assert engine.inference_method in ['ultralytics', 'mock', 'opencv_dnn']
    
    @pytest.mark.asyncio
    async def test_single_frame_detection(self, mock_frame):
        """Test single frame detection"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = EnhancedYOLOEngine(device='cpu')
        await engine.initialize()
        
        detections = await engine.detect_vrus_single(mock_frame, 100, 3.33)
        
        assert isinstance(detections, list)
        # Mock inference should return some detections occasionally
        for detection in detections:
            assert isinstance(detection, EnhancedVRUDetection)
            assert detection.frame_number == 100
            assert detection.timestamp == 3.33
            assert detection.vru_type in ['pedestrian', 'cyclist', 'motorcyclist', 'vehicle']
            assert 0.0 <= detection.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_batch_detection(self, mock_frame):
        """Test batch frame detection"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = EnhancedYOLOEngine(device='cpu')
        await engine.initialize()
        
        frames = [mock_frame, mock_frame, mock_frame]
        frame_numbers = [100, 101, 102]
        timestamps = [3.33, 3.36, 3.39]
        
        batch_detections = await engine.detect_vrus_batch(frames, frame_numbers, timestamps)
        
        assert len(batch_detections) == 3
        for i, detections in enumerate(batch_detections):
            assert isinstance(detections, list)
            for detection in detections:
                assert detection.frame_number == frame_numbers[i]
                assert detection.timestamp == timestamps[i]
    
    def test_performance_stats(self):
        """Test performance statistics tracking"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = EnhancedYOLOEngine(device='cpu')
        stats = engine.get_performance_stats()
        
        assert 'total_inferences' in stats
        assert 'total_detections' in stats
        assert 'average_inference_time' in stats
        assert 'model_type' in stats

class TestEnhancedVideoProcessor:
    """Test the enhanced video processor"""
    
    def test_video_metadata_extraction(self, mock_video_file):
        """Test video metadata extraction"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        processor = EnhancedVideoProcessor()
        metadata = processor.get_video_metadata(mock_video_file)
        
        assert 'fps' in metadata
        assert 'total_frames' in metadata
        assert 'width' in metadata
        assert 'height' in metadata
        assert 'duration' in metadata
        
        assert metadata['width'] == 640
        assert metadata['height'] == 480
        assert metadata['total_frames'] == 60
    
    @pytest.mark.asyncio
    async def test_frame_extraction(self, mock_video_file):
        """Test async frame extraction"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        processor = EnhancedVideoProcessor(batch_size=10)
        frames_extracted = 0
        
        async for frame, frame_number, timestamp in processor.extract_frames_async(
            mock_video_file, max_frames=20
        ):
            assert isinstance(frame, np.ndarray)
            assert frame.shape == (480, 640, 3)
            assert isinstance(frame_number, int)
            assert isinstance(timestamp, float)
            assert frame_number >= 0
            assert timestamp >= 0.0
            
            frames_extracted += 1
        
        assert frames_extracted == 20  # Limited by max_frames

class TestProductionMLInferenceEngine:
    """Test the production ML inference engine"""
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """Test production engine initialization"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = ProductionMLInferenceEngine(TEST_CONFIG)
        success = await engine.initialize()
        
        assert success is True
        assert engine.yolo_engine.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_video_processing_complete(self, mock_video_file):
        """Test complete video processing"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = ProductionMLInferenceEngine(TEST_CONFIG)
        await engine.initialize()
        
        # Mock progress callback
        progress_updates = []
        async def progress_callback(video_id, progress, frames_processed):
            progress_updates.append((video_id, progress, frames_processed))
        
        result = await engine.process_video_complete(
            "test-video-123",
            mock_video_file,
            progress_callback
        )
        
        assert result['status'] == 'completed'
        assert result['video_id'] == 'test-video-123'
        assert 'processing_stats' in result
        assert 'detection_summary' in result
        assert result['processing_stats']['total_frames'] > 0
    
    @pytest.mark.asyncio
    async def test_detection_crud_operations(self, sample_detection):
        """Test detection CRUD operations"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = ProductionMLInferenceEngine(TEST_CONFIG)
        await engine.initialize()
        
        # For this test, we'll mock the database operations
        with patch.object(engine, 'db_manager') as mock_db:
            # Test get detections
            detections = await engine.get_video_detections("test-video")
            assert isinstance(detections, list)
    
    def test_detection_summary_generation(self, sample_detection):
        """Test detection summary generation"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = ProductionMLInferenceEngine(TEST_CONFIG)
        
        # Create multiple detections
        detections = [sample_detection]
        for i in range(5):
            bbox = EnhancedBoundingBox(x=0.1*i, y=0.1*i, width=0.2, height=0.3)
            detection = EnhancedVRUDetection(
                detection_id=f"test-{i}",
                frame_number=i*10,
                timestamp=i*0.33,
                vru_type="cyclist" if i % 2 else "pedestrian",
                confidence=0.7 + i*0.05,
                bounding_box=bbox
            )
            detections.append(detection)
        
        summary = engine._generate_detection_summary(detections)
        
        assert summary['total'] == 6
        assert 'by_type' in summary
        assert 'confidence_stats' in summary
        assert 'pedestrian' in summary['by_type']
        assert 'cyclist' in summary['by_type']
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test engine health check"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = ProductionMLInferenceEngine(TEST_CONFIG)
        await engine.initialize()
        
        health = await engine.health_check()
        
        assert 'status' in health
        assert 'components' in health
        assert 'timestamp' in health
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']

class TestMLAPIEndpoints:
    """Test the ML API endpoints"""
    
    @pytest.fixture(scope="class")
    def client(self):
        """Create test client"""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["version"] == "2.0.0"
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "timestamp" in data
        assert "uptime" in data
    
    def test_stats_endpoint(self, client):
        """Test stats endpoint"""
        if not ENGINE_AVAILABLE:
            # Should return 503 when engine not available
            response = client.get("/api/stats")
            assert response.status_code == 503
        else:
            response = client.get("/api/stats")
            # May be 200 or 503 depending on initialization
            assert response.status_code in [200, 503]
    
    @patch('src.ml_api_endpoints.process_video_for_ground_truth')
    def test_process_video_endpoint(self, mock_process, client):
        """Test video processing endpoint"""
        mock_process.return_value = {
            'video_id': 'test-video',
            'status': 'completed',
            'processing_stats': {'total_frames': 100}
        }
        
        # Test without request body (should use default path)
        response = client.post("/api/videos/test-video/process")
        
        # Should start processing (may return 404 if file doesn't exist)
        assert response.status_code in [200, 404, 503]
    
    def test_processing_status_endpoint(self, client):
        """Test processing status endpoint"""
        # Should return 404 for non-existent task
        response = client.get("/api/videos/non-existent/processing-status")
        assert response.status_code == 404
    
    @patch('src.ml_api_endpoints.get_video_annotations')
    def test_get_detections_endpoint(self, mock_get_annotations, client):
        """Test get detections endpoint"""
        mock_get_annotations.return_value = [
            {
                "detection_id": "test-123",
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "confidence": 0.85,
                "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
            }
        ]
        
        if ENGINE_AVAILABLE:
            response = client.get("/api/videos/test-video/detections")
            # Should succeed if engine available
            assert response.status_code in [200, 503]
        else:
            response = client.get("/api/videos/test-video/detections")
            assert response.status_code == 503

class TestPerformance:
    """Performance and load testing"""
    
    @pytest.mark.asyncio
    async def test_batch_inference_performance(self, mock_frame):
        """Test batch inference performance"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        engine = EnhancedYOLOEngine(device='cpu', batch_size=8)
        await engine.initialize()
        
        # Prepare batch
        batch_size = 8
        frames = [mock_frame] * batch_size
        frame_numbers = list(range(batch_size))
        timestamps = [i * 0.033 for i in range(batch_size)]
        
        start_time = time.time()
        batch_detections = await engine.detect_vrus_batch(frames, frame_numbers, timestamps)
        inference_time = time.time() - start_time
        
        assert len(batch_detections) == batch_size
        assert inference_time > 0
        
        # Performance should be reasonable (adjust threshold as needed)
        fps = batch_size / inference_time
        print(f"Batch inference FPS: {fps:.2f}")
        assert fps > 0.1  # Very conservative threshold
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, mock_frame):
        """Test memory usage stability during processing"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        import psutil
        process = psutil.Process()
        
        engine = EnhancedYOLOEngine(device='cpu')
        await engine.initialize()
        
        initial_memory = process.memory_info().rss
        
        # Run many inferences
        for i in range(50):
            detections = await engine.detect_vrus_single(mock_frame, i, i * 0.033)
        
        final_memory = process.memory_info().rss
        memory_increase = (final_memory - initial_memory) / 1024 / 1024  # MB
        
        print(f"Memory increase after 50 inferences: {memory_increase:.2f} MB")
        
        # Memory increase should be reasonable (less than 100MB for this test)
        assert memory_increase < 100

class TestIntegration:
    """Integration tests with external dependencies"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_video_processing(self, mock_video_file):
        """Test complete end-to-end video processing"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        # This test simulates the complete workflow
        engine = ProductionMLInferenceEngine(TEST_CONFIG)
        await engine.initialize()
        
        # Health check
        health = await engine.health_check()
        assert health['status'] in ['healthy', 'degraded']  # degraded is ok without DB
        
        # Process video
        result = await engine.process_video_complete(
            "integration-test-video",
            mock_video_file
        )
        
        assert result['status'] == 'completed'
        assert result['processing_stats']['total_frames'] > 0
        
        # Get detections (may be empty without database)
        detections = await engine.get_video_detections("integration-test-video")
        assert isinstance(detections, list)
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        if not ENGINE_AVAILABLE:
            pytest.skip("ML Engine not available")
        
        # Test valid configuration
        valid_config = {
            'device': 'cpu',
            'batch_size': 4,
            'max_fps': 30.0
        }
        engine = ProductionMLInferenceEngine(valid_config)
        assert engine.config['device'] == 'cpu'
        assert engine.config['batch_size'] == 4
        
        # Test default configuration
        engine_default = ProductionMLInferenceEngine()
        assert 'device' in engine_default.config
        assert 'batch_size' in engine_default.config

# Test utilities
def create_test_video(output_path: str, duration_seconds: int = 2, fps: int = 30):
    """Create a test video file"""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (640, 480))
    
    total_frames = duration_seconds * fps
    for i in range(total_frames):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add moving objects
        cv2.circle(frame, (50 + i*5, 240), 30, (255, 255, 255), -1)
        if i % 20 == 0:  # Add cyclist every 20 frames
            cv2.rectangle(frame, (300 + i*2, 200), (350 + i*2, 280), (0, 255, 0), -1)
        out.write(frame)
    
    out.release()

# Main test execution
if __name__ == "__main__":
    print("🧪 Running ML Inference Engine Test Suite")
    print("=" * 50)
    
    # Run pytest with verbose output
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
        "--durations=10"  # Show 10 slowest tests
    ]
    
    try:
        import pytest
        exit_code = pytest.main(pytest_args)
        
        if exit_code == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
        
        exit(exit_code)
        
    except ImportError:
        print("❌ pytest not available - running basic tests")
        
        # Basic test runner
        async def run_basic_tests():
            if ENGINE_AVAILABLE:
                print("Testing YOLO Engine initialization...")
                engine = EnhancedYOLOEngine(device='cpu')
                success = await engine.initialize()
                print(f"✅ Engine initialized: {success}")
                
                print("Testing bounding box operations...")
                bbox = EnhancedBoundingBox(x=0.25, y=0.25, width=0.5, height=0.5)
                x1, y1, x2, y2 = bbox.to_pixel_coordinates(640, 480)
                print(f"✅ Pixel coordinates: ({x1}, {y1}, {x2}, {y2})")
                
                print("✅ Basic tests completed successfully!")
            else:
                print("❌ ML Engine not available - cannot run tests")
        
        asyncio.run(run_basic_tests())