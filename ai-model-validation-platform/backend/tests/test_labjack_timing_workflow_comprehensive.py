"""
Comprehensive End-to-End Test Suite for LabJack Timing Validation Workflow
Tests the complete flow from test session creation through results display
"""

import os
import pytest
import asyncio
import logging
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import uuid

# Test framework imports
import pytest_asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Application imports
from database import SessionLocal, get_db, engine, Base
from models import (
    Project, Video, TestSession, DetectionEvent, 
    GroundTruthObject, TestResult, DetectionComparison,
    Annotation
)

# Service imports
from src.enhanced_test_workflow_orchestrator import (
    EnhancedTestWorkflowOrchestrator,
    WorkflowConfiguration,
    WorkflowStatus,
    VideoStatus
)
from services.simple_labjack_detection import EnhancedDetection
from services.labjack_service_manager import LabJackService
from services.websocket_service import realtime_service

# FastAPI app
from main_formatted import app

# Set up logging for testing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestLabJackWorkflowIntegration:
    """
    Comprehensive integration tests for LabJack timing validation workflow
    Tests all components working together end-to-end
    """
    
    @pytest.fixture(autouse=True)
    async def setup_test_environment(self):
        """Set up clean test environment for each test"""
        # Create all tables
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # Create test data directory
        self.test_data_dir = Path(tempfile.mkdtemp(prefix="labjack_test_"))
        self.test_videos_dir = self.test_data_dir / "videos"
        self.test_results_dir = self.test_data_dir / "results"
        self.test_videos_dir.mkdir(parents=True)
        self.test_results_dir.mkdir(parents=True)
        
        # Initialize test client
        self.client = TestClient(app)
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_data_dir, ignore_errors=True)
        Base.metadata.drop_all(bind=engine)
    
    @pytest.fixture
    def mock_labjack_service(self):
        """Mock LabJack service with realistic timing data"""
        mock_service = Mock(spec=LabJackService)
        
        # Simulate realistic detection sequence
        detection_sequence = [
            {"timestamp": 1000.0, "voltage": 3.3, "latency_ms": 45.2},
            {"timestamp": 1002.5, "voltage": 3.3, "latency_ms": 52.1},
            {"timestamp": 1005.0, "voltage": 3.3, "latency_ms": 48.7},
            {"timestamp": 1007.5, "voltage": 3.3, "latency_ms": 44.9},
            {"timestamp": 1010.0, "voltage": 3.3, "latency_ms": 51.3},
            {"timestamp": 1012.5, "voltage": 3.3, "latency_ms": 47.8},
            {"timestamp": 1015.0, "voltage": 3.3, "latency_ms": 49.2},
            {"timestamp": 1017.5, "voltage": 3.3, "latency_ms": 46.5}
        ]
        
        mock_service.start_session.return_value = True
        mock_service.end_session.return_value = True
        mock_service.get_detection_results.return_value = {
            "detections": detection_sequence,
            "metadata": {
                "total_detections": len(detection_sequence),
                "test_duration": 17.5,
                "avg_latency_ms": 48.21,
                "max_latency_ms": 52.1,
                "min_latency_ms": 44.9
            }
        }
        mock_service.is_connected.return_value = True
        
        return mock_service
    
    @pytest.fixture
    def sample_project_data(self):
        """Sample project configuration"""
        return {
            "name": "LabJack Timing Validation Test",
            "description": "Comprehensive test of LabJack timing validation system",
            "camera_model": "Test Camera V1",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide Angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO"
        }
    
    @pytest.fixture
    def sample_video_data(self):
        """Sample video metadata"""
        return {
            "filename": "test_timing_sequence.mp4",
            "duration": 20.0,
            "fps": 30.0,
            "resolution": "1920x1080",
            "file_size": 1024000
        }
    
    async def create_test_project_and_video(self, project_data: Dict, video_data: Dict) -> tuple[Project, Video]:
        """Create test project and video in database"""
        db = SessionLocal()
        try:
            # Create project
            project = Project(**project_data)
            db.add(project)
            db.flush()
            
            # Create test video file
            test_video_path = self.test_videos_dir / video_data["filename"]
            test_video_path.write_text("Mock video content")
            
            # Create video record
            video = Video(
                **video_data,
                file_path=str(test_video_path),
                project_id=project.id,
                ground_truth_generated=True
            )
            db.add(video)
            db.commit()
            db.refresh(project)
            db.refresh(video)
            
            return project, video
            
        finally:
            db.close()
    
    async def create_ground_truth_data(self, video: Video, num_objects: int = 5) -> List[Annotation]:
        """Create ground truth annotations for test video"""
        db = SessionLocal()
        try:
            annotations = []
            
            # Create realistic ground truth sequence
            base_timestamp = 1000.0
            for i in range(num_objects):
                annotation = Annotation(
                    video_id=video.id,
                    detection_id=f"DET_PED_{i:04d}",
                    frame_number=i * 75,  # Every 2.5 seconds at 30fps
                    timestamp=base_timestamp + (i * 2.5),
                    vru_type="pedestrian",
                    bounding_box={
                        "x": 100 + (i * 50),
                        "y": 200,
                        "width": 80,
                        "height": 120
                    },
                    validated=True
                )
                db.add(annotation)
                annotations.append(annotation)
            
            db.commit()
            for ann in annotations:
                db.refresh(ann)
                
            return annotations
            
        finally:
            db.close()
    
    @pytest.mark.asyncio
    async def test_01_complete_workflow_end_to_end(self, mock_labjack_service, sample_project_data, sample_video_data):
        """Test complete workflow from project creation to results display"""
        logger.info("=== Testing Complete End-to-End Workflow ===")
        
        # Step 1: Create project and video
        project, video = await self.create_test_project_and_video(sample_project_data, sample_video_data)
        ground_truth = await self.create_ground_truth_data(video, 8)
        
        assert project.id is not None
        assert video.id is not None
        assert len(ground_truth) == 8
        
        # Step 2: Create test session via API
        session_data = {
            "name": "Complete Workflow Test Session",
            "project_id": project.id,
            "video_id": video.id,
            "tolerance_ms": 100,
            "latency_threshold_ms": 50
        }
        
        response = self.client.post("/api/test-sessions", json=session_data)
        assert response.status_code == 201
        session_response = response.json()
        test_session_id = session_response["id"]
        
        # Step 3: Start enhanced test workflow with mocked LabJack
        with patch('services.labjack_service.labjack_service', mock_labjack_service):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            
            config = WorkflowConfiguration(
                project_id=project.id,
                test_session_name="Complete Workflow Test",
                tolerance_ms=100,
                generate_individual_reports=True,
                generate_aggregate_report=True
            )
            
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            assert workflow_id is not None
            
            # Wait for workflow completion (with timeout)
            timeout_count = 0
            max_timeout = 30  # 30 seconds max wait
            
            while timeout_count < max_timeout:
                workflow_status = orchestrator.get_workflow_status(workflow_id)
                if workflow_status and workflow_status["status"] in ["completed", "failed"]:
                    break
                await asyncio.sleep(1)
                timeout_count += 1
            
            final_status = orchestrator.get_workflow_status(workflow_id)
            assert final_status is not None
            assert final_status["status"] == "completed"
        
        # Step 4: Verify detection events were created
        db = SessionLocal()
        try:
            detection_events = db.execute(select(DetectionEvent).where(
                DetectionEvent.test_session_id == test_session_id
            )).scalars().all()
            
            assert len(detection_events) == 8  # Should match mock data
            
            # Verify timing data is populated
            for event in detection_events:
                assert event.labjack_timestamp is not None
                assert event.latency_ms is not None
                assert event.validation_result in ["Pass", "Fail"]
                
            # Verify latency calculations
            passed_events = [e for e in detection_events if e.validation_result == "Pass"]
            failed_events = [e for e in detection_events if e.validation_result == "Fail"]
            
            logger.info(f"Detection events: {len(detection_events)}, Passed: {len(passed_events)}, Failed: {len(failed_events)}")
            
        finally:
            db.close()
        
        # Step 5: Verify test results were generated
        response = self.client.get(f"/api/test-sessions/{test_session_id}/results")
        assert response.status_code == 200
        
        results_data = response.json()
        assert "pass_rate" in results_data
        assert "avg_latency_ms" in results_data
        assert "total_detections" in results_data
        assert results_data["total_detections"] == 8
        
        # Step 6: Verify results display data
        response = self.client.get(f"/api/test-sessions/{test_session_id}")
        assert response.status_code == 200
        
        session_data = response.json()
        assert session_data["status"] == "completed"
        assert "detection_events" in session_data
        
        logger.info("✅ Complete end-to-end workflow test passed")
    
    @pytest.mark.asyncio
    async def test_02_session_status_transitions(self, mock_labjack_service, sample_project_data, sample_video_data):
        """Test that session status updates correctly through all phases"""
        logger.info("=== Testing Session Status Transitions ===")
        
        project, video = await self.create_test_project_and_video(sample_project_data, sample_video_data)
        
        # Create test session
        session_data = {
            "name": "Status Transition Test",
            "project_id": project.id,
            "video_id": video.id,
            "tolerance_ms": 100
        }
        
        response = self.client.post("/api/test-sessions", json=session_data)
        assert response.status_code == 201
        test_session_id = response.json()["id"]
        
        # Initial status should be "created"
        response = self.client.get(f"/api/test-sessions/{test_session_id}")
        assert response.json()["status"] == "created"
        
        # Start workflow and track status transitions
        with patch('services.labjack_service.labjack_service', mock_labjack_service):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            
            config = WorkflowConfiguration(
                project_id=project.id,
                test_session_name="Status Test"
            )
            
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            # Track expected status transitions
            expected_statuses = [
                WorkflowStatus.INITIALIZING,
                WorkflowStatus.LOADING_VIDEOS,
                WorkflowStatus.PROCESSING_VIDEO,
                WorkflowStatus.RUNNING_DETECTION,
                WorkflowStatus.COMPARING_RESULTS,
                WorkflowStatus.GENERATING_REPORT,
                WorkflowStatus.COMPLETED
            ]
            
            observed_statuses = []
            timeout_count = 0
            
            while timeout_count < 20:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] not in [s.value for s in observed_statuses]:
                    current_status = WorkflowStatus(status["status"])
                    observed_statuses.append(current_status)
                    logger.info(f"Status transition: {current_status.value}")
                    
                    if current_status == WorkflowStatus.COMPLETED:
                        break
                
                await asyncio.sleep(0.5)
                timeout_count += 1
            
            # Verify we went through expected transitions
            assert WorkflowStatus.INITIALIZING in observed_statuses
            assert WorkflowStatus.COMPLETED in observed_statuses
        
        # Final session status should be "completed"
        response = self.client.get(f"/api/test-sessions/{test_session_id}")
        session_final = response.json()
        assert session_final["status"] == "completed"
        assert session_final["completed_at"] is not None
        
        logger.info("✅ Session status transition test passed")
    
    @pytest.mark.asyncio
    async def test_03_video_count_and_timestamp_accuracy(self, mock_labjack_service, sample_project_data):
        """Test video count accuracy and timestamp precision"""
        logger.info("=== Testing Video Count and Timestamp Accuracy ===")
        
        # Create project with multiple videos
        project = Project(**sample_project_data)
        db = SessionLocal()
        try:
            db.add(project)
            db.flush()
            
            # Create 3 test videos
            videos = []
            for i in range(3):
                video_data = {
                    "filename": f"test_video_{i}.mp4",
                    "duration": 10.0 + i,
                    "fps": 30.0,
                    "resolution": "1920x1080",
                    "file_size": 500000 + (i * 100000),
                    "file_path": str(self.test_videos_dir / f"test_video_{i}.mp4"),
                    "project_id": project.id,
                    "ground_truth_generated": True
                }
                
                # Create mock video file
                (self.test_videos_dir / f"test_video_{i}.mp4").write_text("Mock video")
                
                video = Video(**video_data)
                db.add(video)
                videos.append(video)
            
            db.commit()
            for video in videos:
                db.refresh(video)
                
        finally:
            db.close()
        
        # Start workflow
        with patch('services.labjack_service.labjack_service', mock_labjack_service):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            
            config = WorkflowConfiguration(
                project_id=project.id,
                test_session_name="Multi-Video Test"
            )
            
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            # Wait for completion
            timeout_count = 0
            while timeout_count < 30:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] == "completed":
                    break
                await asyncio.sleep(1)
                timeout_count += 1
            
            final_status = orchestrator.get_workflow_status(workflow_id)
            assert final_status["status"] == "completed"
            
            # Verify video count accuracy
            assert final_status["video_count"] == 3
            
            # Check progress tracking was accurate
            progress = final_status["progress"]
            assert progress["total_videos"] == 3
            assert progress["completed_videos"] == 3
            assert progress["overall_progress"] == 100.0
        
        # Verify timestamps in detection events
        db = SessionLocal()
        try:
            all_events = db.execute(select(DetectionEvent)).scalars().all()
            
            for event in all_events:
                # Verify timestamp precision
                assert event.timestamp is not None
                assert event.labjack_timestamp is not None
                assert event.latency_ms is not None
                
                # Timestamps should be reasonable (Unix epoch format)
                assert event.timestamp > 0
                assert event.labjack_timestamp > 0
                
                # Latency should be calculated correctly
                expected_latency = abs(event.timestamp - event.labjack_timestamp) * 1000
                assert abs(event.latency_ms - expected_latency) < 1.0  # Within 1ms tolerance
                
        finally:
            db.close()
        
        logger.info("✅ Video count and timestamp accuracy test passed")
    
    @pytest.mark.asyncio
    async def test_04_labjack_timing_results_generation(self, mock_labjack_service, sample_project_data, sample_video_data):
        """Test LabJack timing results are generated correctly"""
        logger.info("=== Testing LabJack Timing Results Generation ===")
        
        project, video = await self.create_test_project_and_video(sample_project_data, sample_video_data)
        await self.create_ground_truth_data(video, 8)
        
        # Create test session with specific timing parameters
        session_data = {
            "name": "Timing Results Test",
            "project_id": project.id,
            "video_id": video.id,
            "tolerance_ms": 100,
            "latency_threshold_ms": 50  # Set strict threshold for testing
        }
        
        response = self.client.post("/api/test-sessions", json=session_data)
        test_session_id = response.json()["id"]
        
        # Run workflow with mock LabJack data
        with patch('services.labjack_service.labjack_service', mock_labjack_service):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            
            config = WorkflowConfiguration(
                project_id=project.id,
                test_session_name="Timing Test"
            )
            
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            # Wait for completion
            timeout_count = 0
            while timeout_count < 20:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] in ["completed", "failed"]:
                    break
                await asyncio.sleep(1)
                timeout_count += 1
        
        # Verify timing results were generated
        response = self.client.get(f"/api/test-sessions/{test_session_id}/results")
        assert response.status_code == 200
        
        results = response.json()
        
        # Verify all expected timing metrics are present
        timing_metrics = [
            "pass_rate", "avg_latency_ms", "max_latency_ms", "min_latency_ms",
            "median_latency_ms", "std_dev_latency_ms", "total_detections",
            "passed_detections", "failed_detections", "threshold_ms"
        ]
        
        for metric in timing_metrics:
            assert metric in results, f"Missing timing metric: {metric}"
            assert results[metric] is not None
        
        # Verify calculations are correct
        assert results["total_detections"] == results["passed_detections"] + results["failed_detections"]
        assert 0 <= results["pass_rate"] <= 100
        assert results["threshold_ms"] == 50  # Should match our test threshold
        
        # Verify statistical metrics make sense
        assert results["min_latency_ms"] <= results["avg_latency_ms"] <= results["max_latency_ms"]
        
        # Verify latency distribution data
        if "latency_distribution" in results:
            distribution = results["latency_distribution"]
            assert "bins" in distribution
            assert "counts" in distribution
            assert len(distribution["bins"]) > 0
        
        logger.info(f"Results summary: {results['pass_rate']:.1f}% pass rate, "
                   f"{results['avg_latency_ms']:.1f}ms avg latency")
        logger.info("✅ LabJack timing results generation test passed")
    
    @pytest.mark.asyncio
    async def test_05_results_display_integration(self, mock_labjack_service, sample_project_data, sample_video_data):
        """Test results display endpoints and data formatting"""
        logger.info("=== Testing Results Display Integration ===")
        
        project, video = await self.create_test_project_and_video(sample_project_data, sample_video_data)
        await self.create_ground_truth_data(video)
        
        # Create and run test session
        session_data = {
            "name": "Display Integration Test",
            "project_id": project.id,
            "video_id": video.id
        }
        
        response = self.client.post("/api/test-sessions", json=session_data)
        test_session_id = response.json()["id"]
        
        # Run workflow
        with patch('services.labjack_service.labjack_service', mock_labjack_service):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            config = WorkflowConfiguration(project_id=project.id, test_session_name="Display Test")
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            # Wait for completion
            timeout_count = 0
            while timeout_count < 20:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] == "completed":
                    break
                await asyncio.sleep(1)
                timeout_count += 1
        
        # Test various results display endpoints
        endpoints_to_test = [
            f"/api/test-sessions/{test_session_id}",
            f"/api/test-sessions/{test_session_id}/results",
            f"/api/test-sessions/{test_session_id}/detection-events",
            f"/api/projects/{project.id}/test-sessions"
        ]
        
        for endpoint in endpoints_to_test:
            response = self.client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
            data = response.json()
            assert data is not None, f"No data returned from {endpoint}"
            logger.info(f"✓ Endpoint {endpoint} working correctly")
        
        # Test detailed results endpoint
        response = self.client.get(f"/api/test-sessions/{test_session_id}/results/detailed")
        if response.status_code == 200:
            detailed_results = response.json()
            
            # Verify detailed results structure
            expected_sections = ["summary", "timing_analysis", "detection_events", "statistical_analysis"]
            for section in expected_sections:
                if section in detailed_results:
                    assert detailed_results[section] is not None
        
        # Test export functionality
        response = self.client.get(f"/api/test-sessions/{test_session_id}/export/json")
        if response.status_code == 200:
            export_data = response.json()
            assert "test_session" in export_data
            assert "results" in export_data
            assert "detection_events" in export_data
        
        logger.info("✅ Results display integration test passed")
    
    @pytest.mark.asyncio
    async def test_06_error_handling_and_recovery(self, sample_project_data, sample_video_data):
        """Test error handling in workflow and recovery mechanisms"""
        logger.info("=== Testing Error Handling and Recovery ===")
        
        project, video = await self.create_test_project_and_video(sample_project_data, sample_video_data)
        
        # Test 1: LabJack connection failure
        mock_failed_labjack = Mock(spec=LabJackService)
        mock_failed_labjack.start_session.side_effect = Exception("LabJack connection failed")
        mock_failed_labjack.is_connected.return_value = False
        
        with patch('services.labjack_service.labjack_service', mock_failed_labjack):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            config = WorkflowConfiguration(
                project_id=project.id,
                test_session_name="Error Test",
                continue_on_error=True
            )
            
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            # Wait for workflow to handle error
            timeout_count = 0
            while timeout_count < 15:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] in ["failed", "completed"]:
                    break
                await asyncio.sleep(1)
                timeout_count += 1
            
            final_status = orchestrator.get_workflow_status(workflow_id)
            
            # Should fail gracefully
            assert final_status["status"] == "failed"
            assert final_status["error_count"] > 0
        
        # Test 2: Partial failure with recovery
        mock_partial_labjack = Mock(spec=LabJackService)
        mock_partial_labjack.start_detection.return_value = True
        mock_partial_labjack.is_connected.return_value = True
        
        # Return partial results (simulating some detection failures)
        mock_partial_labjack.get_detection_results.return_value = {
            "detections": [
                {"timestamp": 1000.0, "voltage": 3.3, "latency_ms": 45.0},
                {"timestamp": 1002.0, "voltage": 3.3, "latency_ms": 55.0}
            ],
            "metadata": {
                "total_detections": 2,
                "test_duration": 2.0,
                "errors": ["Timeout on detection 3", "Signal lost at 1004.0"]
            }
        }
        
        with patch('services.labjack_service.labjack_service', mock_partial_labjack):
            config.continue_on_error = True
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            timeout_count = 0
            while timeout_count < 15:
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] == "completed":
                    break
                await asyncio.sleep(1)
                timeout_count += 1
            
            final_status = orchestrator.get_workflow_status(workflow_id)
            assert final_status["status"] == "completed"  # Should complete with partial data
        
        logger.info("✅ Error handling and recovery test passed")
    
    @pytest.mark.asyncio
    async def test_07_performance_benchmarks(self, mock_labjack_service, sample_project_data):
        """Test system performance under load"""
        logger.info("=== Testing Performance Benchmarks ===")
        
        # Create project with larger dataset
        project = Project(**sample_project_data)
        db = SessionLocal()
        try:
            db.add(project)
            db.flush()
            
            # Create 10 videos for load testing
            videos = []
            for i in range(10):
                video_data = {
                    "filename": f"perf_test_video_{i}.mp4",
                    "duration": 30.0,
                    "fps": 30.0,
                    "resolution": "1920x1080",
                    "file_size": 1024000,
                    "file_path": str(self.test_videos_dir / f"perf_test_video_{i}.mp4"),
                    "project_id": project.id,
                    "ground_truth_generated": True
                }
                
                # Create mock video file
                (self.test_videos_dir / f"perf_test_video_{i}.mp4").write_text("Mock video")
                
                video = Video(**video_data)
                db.add(video)
                videos.append(video)
                
                # Create ground truth for each video
                for j in range(10):  # 10 detections per video
                    annotation = Annotation(
                        video_id=video.id,
                        detection_id=f"PERF_DET_{i}_{j:04d}",
                        frame_number=j * 90,  # Every 3 seconds
                        timestamp=1000.0 + (j * 3.0),
                        vru_type="pedestrian",
                        bounding_box={"x": 100, "y": 200, "width": 80, "height": 120},
                        validated=True
                    )
                    db.add(annotation)
            
            db.commit()
            
        finally:
            db.close()
        
        # Enhanced mock with more detections
        mock_large_dataset = Mock(spec=LabJackService)
        mock_large_dataset.start_session.return_value = True
        mock_large_dataset.end_session.return_value = True
        mock_large_dataset.is_connected.return_value = True
        
        # Generate 100 detection events (10 per video)
        large_detection_sequence = []
        for i in range(100):
            large_detection_sequence.append({
                "timestamp": 1000.0 + (i * 0.3),
                "voltage": 3.3,
                "latency_ms": 40.0 + (i % 20)  # Vary latency between 40-60ms
            })
        
        mock_large_dataset.get_detection_results.return_value = {
            "detections": large_detection_sequence,
            "metadata": {
                "total_detections": len(large_detection_sequence),
                "test_duration": 30.0,
                "avg_latency_ms": 50.0
            }
        }
        
        # Run performance test
        start_time = datetime.utcnow()
        
        with patch('services.labjack_service.labjack_service', mock_large_dataset):
            orchestrator = EnhancedTestWorkflowOrchestrator()
            config = WorkflowConfiguration(
                project_id=project.id,
                test_session_name="Performance Test",
                parallel_processing=False,  # Sequential for consistent timing
                generate_individual_reports=True
            )
            
            workflow_id = await orchestrator.start_enhanced_test_workflow(config)
            
            # Wait for completion with extended timeout
            timeout_count = 0
            while timeout_count < 60:  # 60 seconds max
                status = orchestrator.get_workflow_status(workflow_id)
                if status and status["status"] in ["completed", "failed"]:
                    break
                await asyncio.sleep(1)
                timeout_count += 1
            
            end_time = datetime.utcnow()
            total_duration = (end_time - start_time).total_seconds()
            
            final_status = orchestrator.get_workflow_status(workflow_id)
            assert final_status["status"] == "completed"
            
            # Performance assertions
            assert total_duration < 45  # Should complete within 45 seconds
            assert final_status["video_count"] == 10
            
            # Verify all detection events were processed
            db = SessionLocal()
            try:
                total_events = db.execute(select(func.count()).select_from(DetectionEvent)).scalar()
                assert total_events == 100  # Should have processed all detections
                
            finally:
                db.close()
        
        logger.info(f"Performance test completed in {total_duration:.2f} seconds")
        logger.info(f"Processing rate: {10/total_duration:.2f} videos/second")
        logger.info("✅ Performance benchmark test passed")

def run_comprehensive_tests():
    """Run all comprehensive tests"""
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "--asyncio-mode=auto"
    ])

if __name__ == "__main__":
    run_comprehensive_tests()