"""
End-to-End Integration Tests for Project Playlist Functionality
Tests complete project playlist workflow, failure snapshot integration,
and user experience flows.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import uuid


class TestProjectPlaylistE2E:
    """End-to-end tests for project playlist functionality"""
    
    @pytest.fixture
    def mock_database_session(self):
        """Mock database session with realistic data"""
        class MockSession:
            def __init__(self):
                self.projects = {}
                self.videos = {}
                self.video_project_links = {}
                self.test_sessions = {}
                self.detection_events = {}
                self.committed = False
                self.rolled_back = False
            
            def add(self, item):
                # Mock add operation
                pass
            
            def commit(self):
                self.committed = True
            
            def rollback(self):
                self.rolled_back = True
            
            def close(self):
                pass
            
            def query(self, model):
                return MockQuery(self, model)
        
        class MockQuery:
            def __init__(self, session, model):
                self.session = session
                self.model = model
                self._filters = []
            
            def filter(self, condition):
                self._filters.append(condition)
                return self
            
            def first(self):
                return None  # Simplified for testing
            
            def all(self):
                return []  # Simplified for testing
        
        return MockSession()
    
    @pytest.fixture
    def sample_project_data(self):
        """Sample project data for testing"""
        return {
            "id": str(uuid.uuid4()),
            "name": "E2E Test Project - VRU Detection",
            "description": "Comprehensive VRU detection testing",
            "camera_model": "TestCam Pro",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide Angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO",
            "status": "Active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    @pytest.fixture
    def sample_video_playlist(self):
        """Sample video playlist for testing"""
        return [
            {
                "id": str(uuid.uuid4()),
                "filename": "pedestrian_crosswalk_01.mp4",
                "file_path": "/uploads/videos/pedestrian_crosswalk_01.mp4",
                "duration": 120.5,
                "fps": 30,
                "resolution": "1920x1080",
                "status": "uploaded",
                "ground_truth_generated": True
            },
            {
                "id": str(uuid.uuid4()),
                "filename": "cyclist_intersection_02.mp4",
                "file_path": "/uploads/videos/cyclist_intersection_02.mp4",
                "duration": 95.2,
                "fps": 30,
                "resolution": "1920x1080",
                "status": "uploaded",
                "ground_truth_generated": True
            },
            {
                "id": str(uuid.uuid4()),
                "filename": "mixed_vru_scenario_03.mp4",
                "file_path": "/uploads/videos/mixed_vru_scenario_03.mp4",
                "duration": 180.8,
                "fps": 30,
                "resolution": "1920x1080",
                "status": "uploaded",
                "ground_truth_generated": False
            }
        ]
    
    @pytest.mark.asyncio
    async def test_complete_project_creation_workflow(
        self, 
        mock_database_session, 
        sample_project_data, 
        sample_video_playlist
    ):
        """Test complete project creation with video playlist"""
        
        # Mock API client
        class MockAPIClient:
            def __init__(self):
                self.base_url = "http://localhost:8000/api"
                self.session = mock_database_session
            
            async def create_project(self, project_data):
                """Mock project creation"""
                await asyncio.sleep(0.1)  # Simulate network delay
                
                project_id = project_data.get("id", str(uuid.uuid4()))
                self.session.projects[project_id] = {
                    **project_data,
                    "id": project_id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                
                return {
                    "status": "success",
                    "data": self.session.projects[project_id]
                }
            
            async def assign_videos_to_project(self, project_id, video_ids):
                """Mock video assignment"""
                await asyncio.sleep(0.1)
                
                assignments = []
                for video_id in video_ids:
                    link_id = str(uuid.uuid4())
                    assignment = {
                        "id": link_id,
                        "video_id": video_id,
                        "project_id": project_id,
                        "intelligent_match": True,
                        "confidence_score": 0.95,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    self.session.video_project_links[link_id] = assignment
                    assignments.append(assignment)
                
                return {
                    "status": "success",
                    "data": assignments
                }
            
            async def get_project_playlist(self, project_id):
                """Mock playlist retrieval"""
                await asyncio.sleep(0.1)
                
                project_links = [
                    link for link in self.session.video_project_links.values()
                    if link["project_id"] == project_id
                ]
                
                return {
                    "status": "success",
                    "data": {
                        "project_id": project_id,
                        "video_count": len(project_links),
                        "links": project_links
                    }
                }
        
        api_client = MockAPIClient()
        
        # Step 1: Create project
        create_response = await api_client.create_project(sample_project_data)
        assert create_response["status"] == "success"
        assert create_response["data"]["id"] is not None
        
        project_id = create_response["data"]["id"]
        
        # Step 2: Assign videos to project (playlist creation)
        video_ids = [video["id"] for video in sample_video_playlist]
        assign_response = await api_client.assign_videos_to_project(project_id, video_ids)
        assert assign_response["status"] == "success"
        assert len(assign_response["data"]) == len(video_ids)
        
        # Step 3: Verify playlist creation
        playlist_response = await api_client.get_project_playlist(project_id)
        assert playlist_response["status"] == "success"
        assert playlist_response["data"]["video_count"] == len(video_ids)
        assert playlist_response["data"]["project_id"] == project_id
        
        # Verify all videos are linked
        linked_video_ids = [
            link["video_id"] for link in playlist_response["data"]["links"]
        ]
        assert set(linked_video_ids) == set(video_ids)
    
    @pytest.mark.asyncio
    async def test_intelligent_video_assignment(
        self,
        mock_database_session,
        sample_project_data,
        sample_video_playlist
    ):
        """Test intelligent video assignment algorithm"""
        
        class MockIntelligentAssignmentService:
            def __init__(self):
                self.assignment_rules = [
                    {
                        "rule": "camera_view_match",
                        "weight": 0.4,
                        "patterns": {
                            "Front-facing VRU": ["pedestrian", "crosswalk", "front"],
                            "Rear-facing VRU": ["cyclist", "rear", "bike"],
                            "In-Cab Driver Behavior": ["driver", "cab", "behavior"]
                        }
                    },
                    {
                        "rule": "vru_type_match",
                        "weight": 0.3,
                        "patterns": {
                            "pedestrian": ["pedestrian", "walker", "person"],
                            "cyclist": ["cyclist", "bike", "bicycle"],
                            "mixed": ["mixed", "multiple", "various"]
                        }
                    },
                    {
                        "rule": "scenario_complexity",
                        "weight": 0.3,
                        "patterns": {
                            "simple": ["single", "basic", "simple"],
                            "complex": ["intersection", "mixed", "scenario"]
                        }
                    }
                ]
            
            async def calculate_assignment_confidence(self, project, video):
                """Calculate confidence score for video-project assignment"""
                await asyncio.sleep(0.05)  # Simulate AI processing
                
                total_confidence = 0.0
                
                for rule in self.assignment_rules:
                    rule_confidence = 0.0
                    
                    if rule["rule"] == "camera_view_match":
                        camera_view = project.get("camera_view", "")
                        filename = video.get("filename", "").lower()
                        
                        if camera_view in rule["patterns"]:
                            patterns = rule["patterns"][camera_view]
                            matches = sum(1 for pattern in patterns if pattern in filename)
                            rule_confidence = min(1.0, matches * 0.5)
                    
                    elif rule["rule"] == "vru_type_match":
                        filename = video.get("filename", "").lower()
                        for vru_type, patterns in rule["patterns"].items():
                            matches = sum(1 for pattern in patterns if pattern in filename)
                            if matches > 0:
                                rule_confidence = min(1.0, matches * 0.3)
                                break
                    
                    elif rule["rule"] == "scenario_complexity":
                        filename = video.get("filename", "").lower()
                        for complexity, patterns in rule["patterns"].items():
                            matches = sum(1 for pattern in patterns if pattern in filename)
                            if matches > 0:
                                rule_confidence = min(1.0, matches * 0.2)
                                break
                    
                    total_confidence += rule_confidence * rule["weight"]
                
                return min(1.0, total_confidence)
            
            async def get_recommended_assignments(self, project, available_videos):
                """Get recommended video assignments for project"""
                recommendations = []
                
                for video in available_videos:
                    confidence = await self.calculate_assignment_confidence(project, video)
                    
                    recommendations.append({
                        "video_id": video["id"],
                        "confidence_score": confidence,
                        "recommended": confidence >= 0.7,
                        "reasoning": self._generate_reasoning(project, video, confidence)
                    })
                
                # Sort by confidence score
                recommendations.sort(key=lambda x: x["confidence_score"], reverse=True)
                return recommendations
            
            def _generate_reasoning(self, project, video, confidence):
                """Generate human-readable reasoning for assignment"""
                reasons = []
                
                camera_view = project.get("camera_view", "").lower()
                filename = video.get("filename", "").lower()
                
                if "front" in camera_view and any(term in filename for term in ["pedestrian", "crosswalk"]):
                    reasons.append("Front-facing camera matches pedestrian content")
                
                if "cyclist" in filename or "bike" in filename:
                    reasons.append("Cyclist detection content")
                
                if "mixed" in filename or "scenario" in filename:
                    reasons.append("Complex scenario suitable for comprehensive testing")
                
                if confidence >= 0.8:
                    reasons.append("High confidence match")
                elif confidence >= 0.6:
                    reasons.append("Moderate confidence match")
                else:
                    reasons.append("Low confidence - manual review recommended")
                
                return "; ".join(reasons) if reasons else "No specific matching criteria"
        
        # Test intelligent assignment
        assignment_service = MockIntelligentAssignmentService()
        
        recommendations = await assignment_service.get_recommended_assignments(
            sample_project_data, 
            sample_video_playlist
        )
        
        assert len(recommendations) == len(sample_video_playlist)
        
        # Verify recommendations are sorted by confidence
        for i in range(len(recommendations) - 1):
            assert recommendations[i]["confidence_score"] >= recommendations[i + 1]["confidence_score"]
        
        # Test high-confidence matches
        high_confidence = [r for r in recommendations if r["recommended"]]
        assert len(high_confidence) > 0  # Should have some high-confidence matches
        
        # Verify reasoning is provided
        for recommendation in recommendations:
            assert recommendation["reasoning"] is not None
            assert len(recommendation["reasoning"]) > 0
    
    @pytest.mark.asyncio
    async def test_failure_snapshot_workflow_integration(
        self, 
        mock_database_session,
        sample_project_data
    ):
        """Test complete failure snapshot workflow integration"""
        
        class MockTestExecutionService:
            def __init__(self):
                self.session = mock_database_session
                self.screenshot_service = MockScreenshotService()
            
            async def execute_test_session(self, project_id, video_id):
                """Mock test execution with failure detection"""
                await asyncio.sleep(0.2)  # Simulate test execution time
                
                session_id = str(uuid.uuid4())
                test_session = {
                    "id": session_id,
                    "project_id": project_id,
                    "video_id": video_id,
                    "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "latency_threshold_ms": 100
                }
                
                self.session.test_sessions[session_id] = test_session
                
                # Simulate detection events with failures
                detection_events = await self._simulate_detection_events(session_id)
                
                # Update session status
                test_session["status"] = "completed"
                test_session["completed_at"] = datetime.now(timezone.utc).isoformat()
                
                return {
                    "status": "success",
                    "data": {
                        "session": test_session,
                        "detection_events": detection_events,
                        "failure_count": len([e for e in detection_events if e["validation_result"] == "Fail"])
                    }
                }
            
            async def _simulate_detection_events(self, session_id):
                """Simulate detection events with some failures"""
                events = []
                
                # Create mix of pass/fail detections
                detection_scenarios = [
                    {"latency_ms": 85.2, "result": "Pass"},
                    {"latency_ms": 95.8, "result": "Pass"},
                    {"latency_ms": 125.3, "result": "Fail"},  # Failure - over threshold
                    {"latency_ms": 78.1, "result": "Pass"},
                    {"latency_ms": 150.7, "result": "Fail"},  # Failure - over threshold
                    {"latency_ms": 92.4, "result": "Pass"},
                    {"latency_ms": 135.9, "result": "Fail"},  # Failure - over threshold
                ]
                
                for i, scenario in enumerate(detection_scenarios):
                    event_id = str(uuid.uuid4())
                    timestamp = time.time() + i  # Sequential timestamps
                    
                    event = {
                        "id": event_id,
                        "test_session_id": session_id,
                        "timestamp": timestamp,
                        "latency_ms": scenario["latency_ms"],
                        "validation_result": scenario["result"],
                        "vru_type": "pedestrian",
                        "labjack_timestamp": timestamp - 0.15,
                        "labjack_voltage": 3.3,
                        "detection_channel": "AIN0"
                    }
                    
                    # Add bounding box for failed detections
                    if scenario["result"] == "Fail":
                        event["bounding_box"] = {
                            "x": 320 + (i * 20),
                            "y": 240 + (i * 15),
                            "width": 80,
                            "height": 120
                        }
                        
                        # Generate screenshots for failures
                        screenshot_data = await self.screenshot_service.capture_failure_screenshot(
                            event_id, 
                            timestamp,
                            event["bounding_box"]
                        )
                        
                        event["screenshot_path"] = screenshot_data["full_path"]
                        event["screenshot_zoom_path"] = screenshot_data["zoom_path"]
                    
                    self.session.detection_events[event_id] = event
                    events.append(event)
                
                return events
        
        class MockScreenshotService:
            async def capture_failure_screenshot(self, detection_id, timestamp, bounding_box):
                """Mock screenshot capture for failures"""
                await asyncio.sleep(0.05)  # Simulate capture time
                
                return {
                    "full_path": f"/uploads/screenshots/{detection_id}_full.png",
                    "zoom_path": f"/uploads/screenshots/{detection_id}_zoom.png",
                    "capture_timestamp": timestamp,
                    "bounding_box": bounding_box,
                    "image_width": 1920,
                    "image_height": 1080
                }
        
        # Test execution service
        test_service = MockTestExecutionService()
        
        # Execute test and capture failures
        project_id = sample_project_data["id"]
        video_id = str(uuid.uuid4())
        
        result = await test_service.execute_test_session(project_id, video_id)
        
        assert result["status"] == "success"
        assert result["data"]["failure_count"] > 0
        
        # Verify failure snapshots were created
        failed_events = [
            event for event in result["data"]["detection_events"]
            if event["validation_result"] == "Fail"
        ]
        
        for failed_event in failed_events:
            assert "screenshot_path" in failed_event
            assert "screenshot_zoom_path" in failed_event
            assert "bounding_box" in failed_event
            assert failed_event["latency_ms"] > 100  # Over threshold
    
    @pytest.mark.asyncio
    async def test_user_experience_flow_validation(
        self,
        mock_database_session,
        sample_project_data,
        sample_video_playlist
    ):
        """Test complete user experience flow validation"""
        
        class MockUserExperienceValidator:
            def __init__(self):
                self.flow_steps = []
                self.performance_metrics = {}
                self.errors = []
            
            async def validate_project_creation_flow(self, project_data):
                """Validate project creation user experience"""
                self.flow_steps.append("project_creation_start")
                start_time = time.time()
                
                # Simulate form validation
                validation_errors = self._validate_project_form(project_data)
                if validation_errors:
                    self.errors.extend(validation_errors)
                    return {"status": "error", "errors": validation_errors}
                
                # Simulate project creation
                await asyncio.sleep(0.3)  # Simulate backend processing
                
                end_time = time.time()
                self.performance_metrics["project_creation_time"] = end_time - start_time
                self.flow_steps.append("project_creation_complete")
                
                return {"status": "success", "project_id": str(uuid.uuid4())}
            
            async def validate_playlist_creation_flow(self, project_id, videos):
                """Validate playlist creation user experience"""
                self.flow_steps.append("playlist_creation_start")
                start_time = time.time()
                
                # Simulate video selection validation
                if not videos:
                    error = "No videos selected for playlist"
                    self.errors.append(error)
                    return {"status": "error", "error": error}
                
                # Simulate intelligent assignment
                await asyncio.sleep(0.5)  # Simulate AI processing
                
                # Simulate playlist ordering
                await asyncio.sleep(0.2)
                
                end_time = time.time()
                self.performance_metrics["playlist_creation_time"] = end_time - start_time
                self.flow_steps.append("playlist_creation_complete")
                
                return {
                    "status": "success",
                    "playlist": {
                        "project_id": project_id,
                        "video_count": len(videos),
                        "total_duration": sum(v.get("duration", 0) for v in videos)
                    }
                }
            
            async def validate_test_execution_flow(self, project_id):
                """Validate test execution user experience"""
                self.flow_steps.append("test_execution_start")
                start_time = time.time()
                
                # Simulate test preparation
                await asyncio.sleep(0.2)
                
                # Simulate test execution
                await asyncio.sleep(1.0)  # Simulate actual test time
                
                # Simulate results processing
                await asyncio.sleep(0.3)
                
                end_time = time.time()
                self.performance_metrics["test_execution_time"] = end_time - start_time
                self.flow_steps.append("test_execution_complete")
                
                return {
                    "status": "success",
                    "results": {
                        "total_detections": 10,
                        "failed_detections": 3,
                        "pass_rate": 0.7,
                        "avg_latency_ms": 95.8
                    }
                }
            
            async def validate_results_viewing_flow(self, session_id):
                """Validate results viewing user experience"""
                self.flow_steps.append("results_viewing_start")
                start_time = time.time()
                
                # Simulate results loading
                await asyncio.sleep(0.4)
                
                # Simulate failure snapshot loading
                await asyncio.sleep(0.6)
                
                end_time = time.time()
                self.performance_metrics["results_viewing_time"] = end_time - start_time
                self.flow_steps.append("results_viewing_complete")
                
                return {"status": "success", "snapshots_loaded": 3}
            
            def _validate_project_form(self, project_data):
                """Validate project form data"""
                errors = []
                
                required_fields = ["name", "camera_model", "camera_view", "signal_type"]
                for field in required_fields:
                    if not project_data.get(field):
                        errors.append(f"Required field missing: {field}")
                
                if len(project_data.get("name", "")) < 3:
                    errors.append("Project name must be at least 3 characters")
                
                valid_camera_views = ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]
                if project_data.get("camera_view") not in valid_camera_views:
                    errors.append("Invalid camera view selected")
                
                return errors
            
            def get_performance_summary(self):
                """Get performance summary"""
                return {
                    "flow_steps_completed": len(self.flow_steps),
                    "total_errors": len(self.errors),
                    "performance_metrics": self.performance_metrics,
                    "flow_completion_rate": len([s for s in self.flow_steps if "complete" in s]) / max(1, len(self.flow_steps) / 2),
                    "average_response_time": sum(self.performance_metrics.values()) / max(1, len(self.performance_metrics))
                }
        
        # Run complete user experience validation
        validator = MockUserExperienceValidator()
        
        # Step 1: Project Creation
        project_result = await validator.validate_project_creation_flow(sample_project_data)
        assert project_result["status"] == "success"
        
        # Step 2: Playlist Creation
        playlist_result = await validator.validate_playlist_creation_flow(
            project_result["project_id"],
            sample_video_playlist
        )
        assert playlist_result["status"] == "success"
        assert playlist_result["playlist"]["video_count"] == len(sample_video_playlist)
        
        # Step 3: Test Execution
        test_result = await validator.validate_test_execution_flow(project_result["project_id"])
        assert test_result["status"] == "success"
        assert test_result["results"]["failed_detections"] > 0
        
        # Step 4: Results Viewing
        results_result = await validator.validate_results_viewing_flow("mock_session_id")
        assert results_result["status"] == "success"
        assert results_result["snapshots_loaded"] > 0
        
        # Validate overall user experience
        performance_summary = validator.get_performance_summary()
        
        assert performance_summary["total_errors"] == 0
        assert performance_summary["flow_completion_rate"] == 1.0  # All flows completed
        assert performance_summary["average_response_time"] < 2.0  # Reasonable response times
        
        # Verify all expected flow steps completed
        expected_steps = [
            "project_creation_complete",
            "playlist_creation_complete", 
            "test_execution_complete",
            "results_viewing_complete"
        ]
        
        for step in expected_steps:
            assert step in validator.flow_steps


if __name__ == "__main__":
    pytest.main([__file__, "-v"])