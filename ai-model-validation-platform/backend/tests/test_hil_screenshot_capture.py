"""
Test HIL Screenshot Capture Functionality

This test validates the complete HIL testing workflow with:
- Video frame capture during LabJack voltage detection
- Ground truth comparison with visual evidence
- Screenshot generation and serving
- API endpoint functionality
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import cv2
import numpy as np
from datetime import datetime, timezone

# Test imports
from services.hil_screenshot_service import (
    HILVideoFrameCapture, 
    HILGroundTruthComparison,
    HILScreenshotResult
)
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor, HILDetectionEvent
from routers.hil_testing import router


class TestHILScreenshotCapture:
    """Test HIL screenshot capture functionality"""
    
    @pytest.fixture
    def temp_screenshot_dir(self):
        """Create temporary directory for screenshots"""
        temp_dir = tempfile.mkdtemp(prefix="hil_screenshots_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_video_file(self):
        """Create a mock video file for testing"""
        # Create a simple test video frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add some visual elements
        cv2.rectangle(frame, (100, 100), (200, 300), (255, 255, 255), -1)
        cv2.putText(frame, "Test VRU", (120, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        # Create temporary video file
        temp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        
        # Mock video file properties
        return {
            'path': temp_video.name,
            'frame': frame,
            'fps': 30.0,
            'total_frames': 900,  # 30 seconds
            'width': 640,
            'height': 480
        }
    
    @pytest.fixture
    def hil_frame_capture(self, temp_screenshot_dir):
        """HIL video frame capture service instance"""
        return HILVideoFrameCapture(screenshot_dir=temp_screenshot_dir)
    
    @pytest.fixture 
    def sample_detection_data(self):
        """Sample HIL detection event data"""
        return {
            'id': 'test-detection-001',
            'unix_timestamp': 1640995200.123,  # 2022-01-01 00:00:00.123
            'video_relative_timestamp': 15.456,  # 15.456 seconds into video
            'video_relative_timestamp_ns': '15456789012',
            'actual_latency_ms': 45.7,
            'video_frame_number': 463,  # Frame at 15.456s @ 30fps
            'timing_sync_quality': 'high',
            'labjack_voltage': 4.2,
            'detection_channel': 'AIN0',
            'precision_ns': 1000000.0  # 1ms precision
        }
    
    @pytest.mark.asyncio
    async def test_hil_frame_capture_initialization(self, hil_frame_capture, mock_video_file):
        """Test HIL video frame capture initialization"""
        session_id = "test-session-001"
        video_metadata = {
            'fps': mock_video_file['fps'],
            'duration': 30.0
        }
        
        # Mock cv2.VideoCapture
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap_instance = Mock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = True
            mock_cap_instance.get.side_effect = lambda prop: {
                cv2.CAP_PROP_FPS: mock_video_file['fps'],
                cv2.CAP_PROP_FRAME_COUNT: mock_video_file['total_frames'],
                cv2.CAP_PROP_FRAME_WIDTH: mock_video_file['width'],
                cv2.CAP_PROP_FRAME_HEIGHT: mock_video_file['height']
            }.get(prop, 0)
            
            # Test initialization
            success = hil_frame_capture.initialize_video_session(
                session_id, mock_video_file['path'], video_metadata
            )
            
            assert success is True
            assert session_id in hil_frame_capture.video_captures
            assert session_id in hil_frame_capture.video_metadata
            
            metadata = hil_frame_capture.video_metadata[session_id]
            assert metadata['fps'] == mock_video_file['fps']
            assert metadata['total_frames'] == mock_video_file['total_frames']
            assert metadata['width'] == mock_video_file['width']
            assert metadata['height'] == mock_video_file['height']
    
    @pytest.mark.asyncio
    async def test_hil_screenshot_capture(self, hil_frame_capture, mock_video_file, sample_detection_data):
        """Test HIL screenshot capture during detection"""
        session_id = "test-session-002"
        
        # Initialize session
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap_instance = Mock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = True
            mock_cap_instance.get.side_effect = lambda prop: {
                cv2.CAP_PROP_FPS: 30.0,
                cv2.CAP_PROP_FRAME_COUNT: 900,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
                cv2.CAP_PROP_POS_FRAMES: sample_detection_data['video_frame_number']
            }.get(prop, 0)
            mock_cap_instance.read.return_value = (True, mock_video_file['frame'])
            
            # Initialize session
            hil_frame_capture.initialize_video_session(session_id, mock_video_file['path'], {})
            
            # Mock cv2.imwrite to simulate successful screenshot saving
            with patch('cv2.imwrite', return_value=True):
                # Capture screenshot
                result = await hil_frame_capture.capture_detection_frame(
                    session_id=session_id,
                    detection_timestamp=sample_detection_data['unix_timestamp'],
                    video_relative_timestamp=sample_detection_data['video_relative_timestamp'],
                    frame_number=sample_detection_data['video_frame_number'],
                    detection_id=sample_detection_data['id']
                )
                
                # Verify result
                assert isinstance(result, HILScreenshotResult)
                assert result.capture_success is True
                assert result.detection_id == sample_detection_data['id']
                assert result.video_relative_timestamp == sample_detection_data['video_relative_timestamp']
                assert result.frame_number == sample_detection_data['video_frame_number']
                assert result.screenshot_path is not None
                assert result.screenshot_zoom_path is not None
                assert "hil_detection_" in result.screenshot_path
                assert sample_detection_data['id'] in result.screenshot_path
    
    @pytest.mark.asyncio
    async def test_hil_ground_truth_comparison(self, sample_detection_data):
        """Test HIL ground truth comparison with screenshots"""
        with patch('services.hil_screenshot_service.get_ground_truth_matching_service') as mock_gt_service:
            # Mock ground truth service
            mock_service = Mock()
            mock_gt_service.return_value = mock_service
            mock_service.match_detections_to_ground_truth.return_value = Mock(
                true_positives=1,
                false_positives=0,
                false_negatives=0,
                precision=1.0,
                recall=1.0,
                f1_score=1.0,
                mean_latency_ms=45.7
            )
            mock_service.get_detailed_analysis.return_value = {
                'session_id': 'test-session',
                'summary': {'total_comparisons': 1, 'true_positives': 1},
                'temporal_analysis': {'mean_offset_ms': 45.7}
            }
            mock_service.get_matching_results_summary.return_value = {
                'session_id': 'test-session',
                'status': 'success',
                'summary': {'precision': 1.0, 'recall': 1.0, 'f1_score': 1.0}
            }
            
            # Create HIL comparison service
            hil_comparison = HILGroundTruthComparison()
            
            # Mock video frame capture
            with patch.object(hil_comparison.video_frame_capture, 'initialize_video_session', return_value=True):
                with patch.object(hil_comparison.video_frame_capture, 'capture_detection_frame') as mock_capture:
                    # Mock successful screenshot capture
                    mock_capture.return_value = HILScreenshotResult(
                        detection_id=sample_detection_data['id'],
                        timestamp=sample_detection_data['unix_timestamp'],
                        video_relative_timestamp=sample_detection_data['video_relative_timestamp'],
                        frame_number=sample_detection_data['video_frame_number'],
                        screenshot_path="/screenshots/hil/test_detection.jpg",
                        screenshot_zoom_path="/screenshots/hil/test_detection_zoom.jpg",
                        capture_success=True
                    )
                    
                    # Process HIL detection
                    result = await hil_comparison.process_hil_detection_with_screenshots(
                        session_id="test-session",
                        detection_data=sample_detection_data,
                        video_path="/path/to/test/video.mp4",
                        video_metadata={'fps': 30.0, 'duration': 30.0}
                    )
                    
                    # Verify comprehensive result
                    assert result['success'] is True
                    assert result['detection_id'] == sample_detection_data['id']
                    assert 'screenshot_capture' in result
                    assert 'ground_truth_comparison' in result
                    assert 'hil_detection' in result
                    
                    # Verify screenshot capture data
                    screenshot_data = result['screenshot_capture']
                    assert screenshot_data['success'] is True
                    assert screenshot_data['screenshot_path'] is not None
                    assert screenshot_data['screenshot_zoom_path'] is not None
                    
                    # Verify ground truth comparison data
                    gt_data = result['ground_truth_comparison']
                    assert gt_data['metrics'] is not None
                    assert gt_data['detailed_analysis'] is not None
                    assert gt_data['matching_summary'] is not None
                    
                    # Verify HIL detection data
                    hil_data = result['hil_detection']
                    assert hil_data['voltage'] == 4.2
                    assert hil_data['channel'] == 'AIN0'
                    assert hil_data['latency_ms'] == 45.7
    
    def test_hil_detection_event_enhancement(self, sample_detection_data):
        """Test enhanced HIL detection event with screenshot data"""
        # Create HIL detection event
        hil_event = HILDetectionEvent(
            id=sample_detection_data['id'],
            session_id="test-session",
            unix_timestamp=sample_detection_data['unix_timestamp'],
            video_relative_timestamp=sample_detection_data['video_relative_timestamp'],
            video_relative_timestamp_ns=sample_detection_data['video_relative_timestamp_ns'],
            actual_latency_ms=sample_detection_data['actual_latency_ms'],
            video_frame_number=sample_detection_data['video_frame_number'],
            timing_sync_quality=sample_detection_data['timing_sync_quality'],
            labjack_voltage=sample_detection_data['labjack_voltage'],
            detection_channel=sample_detection_data['detection_channel'],
            precision_ns=sample_detection_data['precision_ns'],
            screenshot_path="/screenshots/hil/test_detection.jpg",
            screenshot_zoom_path="/screenshots/hil/test_detection_zoom.jpg",
            ground_truth_comparison={'precision': 1.0, 'recall': 1.0, 'f1_score': 1.0},
            created_at=datetime.now(timezone.utc)
        )
        
        # Verify enhanced fields
        assert hil_event.screenshot_path is not None
        assert hil_event.screenshot_zoom_path is not None
        assert hil_event.ground_truth_comparison is not None
        assert hil_event.labjack_voltage == 4.2
        assert hil_event.detection_channel == 'AIN0'
        assert hil_event.timing_sync_quality == 'high'
        assert hil_event.actual_latency_ms == 45.7


class TestHILAPIEndpoints:
    """Test HIL API endpoints"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def sample_test_session(self):
        """Sample test session data"""
        return Mock(
            id="test-session-001",
            name="HIL Test Session",
            status="completed",
            video_id="video-001",
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def sample_detection_events(self):
        """Sample detection events with screenshots"""
        events = []
        for i in range(3):
            event = Mock()
            event.id = f"detection-{i+1:03d}"
            event.timestamp = 1640995200.0 + i * 5.0  # 5 seconds apart
            event.video_relative_timestamp = i * 5.0
            event.actual_latency_ms = 45.0 + i * 2.0
            event.video_frame_number = i * 150  # 30fps * 5s
            event.labjack_voltage = 4.2
            event.detection_channel = 'AIN0'
            event.timing_sync_quality = 'high'
            event.validation_result = 'Pass'
            event.screenshot_path = f"/screenshots/hil/detection_{event.id}.jpg"
            event.screenshot_zoom_path = f"/screenshots/hil/detection_{event.id}_zoom.jpg"
            event.created_at = datetime.now(timezone.utc)
            events.append(event)
        return events
    
    @pytest.mark.asyncio
    async def test_ground_truth_comparison_endpoint(self, mock_db_session, sample_test_session, sample_detection_events):
        """Test ground truth comparison API endpoint"""
        from routers.hil_testing import get_ground_truth_comparison_with_screenshots
        
        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_test_session
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_detection_events
        
        # Mock ground truth service
        with patch('routers.hil_testing.get_ground_truth_matching_service') as mock_gt_service:
            mock_service = Mock()
            mock_gt_service.return_value = mock_service
            mock_service.match_detections_to_ground_truth.return_value = Mock(
                true_positives=3,
                false_positives=0,
                false_negatives=0,
                precision=1.0,
                recall=1.0,
                f1_score=1.0,
                mean_latency_ms=47.0,
                within_tolerance_percentage=100.0
            )
            mock_service.get_detailed_analysis.return_value = {
                'session_id': 'test-session-001',
                'summary': {'total_comparisons': 3, 'true_positives': 3}
            }
            mock_service.get_matching_results_summary.return_value = {
                'session_id': 'test-session-001',
                'status': 'success'
            }
            
            # Mock HIL session events
            with patch('routers.hil_testing.get_hil_session_events', return_value=[]):
                # Mock Path.exists for screenshot files
                with patch('pathlib.Path.exists', return_value=True):
                    # Call endpoint
                    result = await get_ground_truth_comparison_with_screenshots(
                        session_id="test-session-001",
                        tolerance_ms=100,
                        include_screenshots=True,
                        db=mock_db_session
                    )
                    
                    # Verify response structure
                    assert result['session_id'] == "test-session-001"
                    assert 'test_session_info' in result
                    assert 'ground_truth_analysis' in result
                    assert 'detection_events' in result
                    assert 'summary' in result
                    assert 'visual_evidence' in result
                    
                    # Verify detection events with screenshots
                    detection_events = result['detection_events']
                    assert len(detection_events) == 3
                    
                    for event in detection_events:
                        assert 'screenshot_url' in event
                        assert event['screenshot_url'] is not None
                        assert '/api/hil/screenshots/' in event['screenshot_url']
                    
                    # Verify summary metrics
                    summary = result['summary']
                    assert summary['total_detections'] == 3
                    assert summary['detections_with_screenshots'] == 3
                    assert summary['precision'] == 1.0
                    assert summary['recall'] == 1.0
                    assert summary['f1_score'] == 1.0
    
    @pytest.mark.asyncio
    async def test_detection_events_endpoint(self, mock_db_session, sample_test_session, sample_detection_events):
        """Test HIL detection events API endpoint"""
        from routers.hil_testing import get_hil_detection_events
        
        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_test_session
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_detection_events
        
        # Mock HIL session events and Path.exists
        with patch('routers.hil_testing.get_hil_session_events', return_value=[]):
            with patch('pathlib.Path.exists', return_value=True):
                # Call endpoint
                result = await get_hil_detection_events(
                    session_id="test-session-001",
                    include_screenshots=True,
                    db=mock_db_session
                )
                
                # Verify response
                assert result['session_id'] == "test-session-001"
                assert 'detection_events' in result
                assert 'summary' in result
                
                # Verify detection events
                events = result['detection_events']
                assert len(events) == 3
                
                for event in events:
                    assert 'screenshots' in event
                    screenshots = event['screenshots']
                    assert screenshots['screenshot_exists'] is True
                    assert screenshots['screenshot_zoom_exists'] is True
                    assert 'screenshot_url' in screenshots
                    assert 'screenshot_zoom_url' in screenshots


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])