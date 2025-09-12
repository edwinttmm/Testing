"""
API Contract Validation Tests for New Schema
Tests API endpoints with new many-to-many schema, validates request/response formats,
and ensures backwards compatibility.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any, Optional
import jsonschema


class TestAPIContractValidation:
    """Test suite for API contract validation with new schema"""
    
    @pytest.fixture
    def api_schemas(self):
        """Define API schemas for validation"""
        return {
            "project_create_request": {
                "type": "object",
                "required": ["name", "camera_model", "camera_view", "signal_type"],
                "properties": {
                    "name": {"type": "string", "minLength": 3, "maxLength": 255},
                    "description": {"type": "string", "maxLength": 1000},
                    "camera_model": {"type": "string", "minLength": 1},
                    "camera_view": {
                        "type": "string",
                        "enum": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]
                    },
                    "lens_type": {"type": "string"},
                    "resolution": {"type": "string"},
                    "frame_rate": {"type": "integer", "minimum": 1, "maximum": 120},
                    "signal_type": {
                        "type": "string", 
                        "enum": ["GPIO", "Network Packet", "Serial"]
                    }
                },
                "additionalProperties": False
            },
            
            "project_response": {
                "type": "object",
                "required": ["id", "name", "camera_model", "camera_view", "signal_type", "status", "created_at"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
                    "name": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "camera_model": {"type": "string"},
                    "camera_view": {"type": "string"},
                    "lens_type": {"type": ["string", "null"]},
                    "resolution": {"type": ["string", "null"]},
                    "frame_rate": {"type": ["integer", "null"]},
                    "signal_type": {"type": "string"},
                    "status": {"type": "string", "enum": ["Active", "Completed", "Draft"]},
                    "owner_id": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": ["string", "null"], "format": "date-time"},
                    "video_count": {"type": "integer", "minimum": 0},
                    "total_duration": {"type": ["number", "null"], "minimum": 0}
                }
            },
            
            "video_assignment_request": {
                "type": "object",
                "required": ["project_id", "video_ids"],
                "properties": {
                    "project_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
                    "video_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
                        "minItems": 1,
                        "maxItems": 100
                    },
                    "assignment_reason": {"type": "string", "maxLength": 500},
                    "intelligent_match": {"type": "boolean", "default": True}
                }
            },
            
            "video_assignment_response": {
                "type": "object",
                "required": ["assignments", "success_count", "failure_count"],
                "properties": {
                    "assignments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "video_id", "project_id", "confidence_score", "created_at"],
                            "properties": {
                                "id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
                                "video_id": {"type": "string"},
                                "project_id": {"type": "string"},
                                "assignment_reason": {"type": ["string", "null"]},
                                "intelligent_match": {"type": "boolean"},
                                "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                                "created_at": {"type": "string", "format": "date-time"}
                            }
                        }
                    },
                    "success_count": {"type": "integer", "minimum": 0},
                    "failure_count": {"type": "integer", "minimum": 0},
                    "errors": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            
            "project_playlist_response": {
                "type": "object",
                "required": ["project", "videos", "total_count", "total_duration"],
                "properties": {
                    "project": {
                        "type": "object",
                        "required": ["id", "name"],
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": ["string", "null"]},
                            "camera_view": {"type": "string"}
                        }
                    },
                    "videos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "filename", "duration", "assignment"],
                            "properties": {
                                "id": {"type": "string"},
                                "filename": {"type": "string"},
                                "file_path": {"type": "string"},
                                "duration": {"type": "number", "minimum": 0},
                                "fps": {"type": ["number", "null"]},
                                "resolution": {"type": ["string", "null"]},
                                "file_size": {"type": ["integer", "null"]},
                                "status": {"type": "string"},
                                "ground_truth_generated": {"type": "boolean"},
                                "assignment": {
                                    "type": "object",
                                    "required": ["id", "confidence_score", "intelligent_match"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "confidence_score": {"type": "number"},
                                        "intelligent_match": {"type": "boolean"},
                                        "assignment_reason": {"type": ["string", "null"]},
                                        "created_at": {"type": "string", "format": "date-time"}
                                    }
                                }
                            }
                        }
                    },
                    "total_count": {"type": "integer", "minimum": 0},
                    "total_duration": {"type": "number", "minimum": 0},
                    "pagination": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "minimum": 1},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                            "total_pages": {"type": "integer", "minimum": 0}
                        }
                    }
                }
            },
            
            "failure_snapshot_response": {
                "type": "object",
                "required": ["detection_event", "snapshot_data"],
                "properties": {
                    "detection_event": {
                        "type": "object",
                        "required": ["id", "test_session_id", "timestamp", "validation_result"],
                        "properties": {
                            "id": {"type": "string"},
                            "test_session_id": {"type": "string"},
                            "video_id": {"type": ["string", "null"]},
                            "timestamp": {"type": "number"},
                            "validation_result": {"type": "string", "enum": ["Pass", "Fail"]},
                            "latency_ms": {"type": ["number", "null"]},
                            "labjack_timestamp": {"type": ["number", "null"]},
                            "vru_type": {"type": ["string", "null"]},
                            "bounding_box": {
                                "type": ["object", "null"],
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "width": {"type": "number", "minimum": 0},
                                    "height": {"type": "number", "minimum": 0}
                                }
                            }
                        }
                    },
                    "snapshot_data": {
                        "type": "object",
                        "properties": {
                            "screenshot_path": {"type": ["string", "null"]},
                            "screenshot_zoom_path": {"type": ["string", "null"]},
                            "screenshot_url": {"type": ["string", "null"]},
                            "zoom_url": {"type": ["string", "null"]},
                            "image_width": {"type": ["integer", "null"]},
                            "image_height": {"type": ["integer", "null"]},
                            "capture_timestamp": {"type": ["number", "null"]}
                        }
                    }
                }
            }
        }
    
    @pytest.fixture
    def mock_api_client(self):
        """Mock API client for testing"""
        class MockAPIClient:
            def __init__(self):
                self.base_url = "http://localhost:8000/api"
                self.projects = {}
                self.videos = {}
                self.video_project_links = {}
                self.test_sessions = {}
                self.detection_events = {}
            
            async def post(self, endpoint: str, data: dict) -> dict:
                """Mock POST request"""
                await asyncio.sleep(0.01)  # Simulate network delay
                
                if endpoint == "/projects":
                    return await self._handle_create_project(data)
                elif endpoint == "/projects/assign-videos":
                    return await self._handle_assign_videos(data)
                elif endpoint.startswith("/projects/") and endpoint.endswith("/test-sessions"):
                    project_id = endpoint.split("/")[2]
                    return await self._handle_create_test_session(project_id, data)
                else:
                    return {"status": "error", "message": f"Unknown endpoint: {endpoint}"}
            
            async def get(self, endpoint: str, params: dict = None) -> dict:
                """Mock GET request"""
                await asyncio.sleep(0.01)  # Simulate network delay
                
                if endpoint.startswith("/projects/") and endpoint.endswith("/playlist"):
                    project_id = endpoint.split("/")[2]
                    return await self._handle_get_project_playlist(project_id, params or {})
                elif endpoint.startswith("/projects/"):
                    project_id = endpoint.split("/")[2]
                    return await self._handle_get_project(project_id)
                elif endpoint == "/projects":
                    return await self._handle_list_projects(params or {})
                elif endpoint.startswith("/detection-events/") and endpoint.endswith("/snapshot"):
                    event_id = endpoint.split("/")[2]
                    return await self._handle_get_failure_snapshot(event_id)
                else:
                    return {"status": "error", "message": f"Unknown endpoint: {endpoint}"}
            
            async def _handle_create_project(self, data: dict) -> dict:
                """Handle project creation"""
                project_id = str(uuid.uuid4())
                project = {
                    "id": project_id,
                    **data,
                    "status": "Active",
                    "owner_id": "test-user",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": None,
                    "video_count": 0,
                    "total_duration": 0.0
                }
                
                self.projects[project_id] = project
                return {"status": "success", "data": project}
            
            async def _handle_assign_videos(self, data: dict) -> dict:
                """Handle video assignment"""
                project_id = data["project_id"]
                video_ids = data["video_ids"]
                
                if project_id not in self.projects:
                    return {"status": "error", "message": "Project not found"}
                
                assignments = []
                success_count = 0
                failure_count = 0
                errors = []
                
                for video_id in video_ids:
                    # Check if assignment already exists
                    existing = any(
                        link["video_id"] == video_id and link["project_id"] == project_id
                        for link in self.video_project_links.values()
                    )
                    
                    if existing:
                        errors.append(f"Video {video_id} already assigned to project {project_id}")
                        failure_count += 1
                        continue
                    
                    # Create assignment
                    link_id = str(uuid.uuid4())
                    assignment = {
                        "id": link_id,
                        "video_id": video_id,
                        "project_id": project_id,
                        "assignment_reason": data.get("assignment_reason"),
                        "intelligent_match": data.get("intelligent_match", True),
                        "confidence_score": 0.95,  # Mock high confidence
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    
                    self.video_project_links[link_id] = assignment
                    assignments.append(assignment)
                    success_count += 1
                
                return {
                    "status": "success",
                    "data": {
                        "assignments": assignments,
                        "success_count": success_count,
                        "failure_count": failure_count,
                        "errors": errors
                    }
                }
            
            async def _handle_get_project_playlist(self, project_id: str, params: dict) -> dict:
                """Handle project playlist retrieval"""
                if project_id not in self.projects:
                    return {"status": "error", "message": "Project not found"}
                
                project = self.projects[project_id]
                
                # Get project video links
                project_links = [
                    link for link in self.video_project_links.values()
                    if link["project_id"] == project_id
                ]
                
                # Mock video data for playlist
                videos = []
                total_duration = 0.0
                
                for i, link in enumerate(project_links):
                    video = {
                        "id": link["video_id"],
                        "filename": f"playlist_video_{i+1:03d}.mp4",
                        "file_path": f"/uploads/videos/playlist_video_{i+1:03d}.mp4",
                        "duration": 120.5 + (i * 15),  # Varying durations
                        "fps": 30,
                        "resolution": "1920x1080",
                        "file_size": 50000000 + (i * 5000000),  # Varying sizes
                        "status": "uploaded",
                        "ground_truth_generated": i % 2 == 0,  # Alternate ground truth status
                        "assignment": {
                            "id": link["id"],
                            "confidence_score": link["confidence_score"],
                            "intelligent_match": link["intelligent_match"],
                            "assignment_reason": link["assignment_reason"],
                            "created_at": link["created_at"]
                        }
                    }
                    videos.append(video)
                    total_duration += video["duration"]
                
                # Handle pagination
                page = params.get("page", 1)
                limit = params.get("limit", 20)
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                
                paginated_videos = videos[start_idx:end_idx]
                total_pages = (len(videos) + limit - 1) // limit
                
                return {
                    "status": "success",
                    "data": {
                        "project": {
                            "id": project["id"],
                            "name": project["name"],
                            "description": project.get("description"),
                            "camera_view": project["camera_view"]
                        },
                        "videos": paginated_videos,
                        "total_count": len(videos),
                        "total_duration": total_duration,
                        "pagination": {
                            "page": page,
                            "limit": limit,
                            "total_pages": total_pages
                        }
                    }
                }
            
            async def _handle_get_failure_snapshot(self, event_id: str) -> dict:
                """Handle failure snapshot retrieval"""
                # Mock detection event
                detection_event = {
                    "id": event_id,
                    "test_session_id": str(uuid.uuid4()),
                    "video_id": str(uuid.uuid4()),
                    "timestamp": 1625097600.0,
                    "validation_result": "Fail",
                    "latency_ms": 125.3,
                    "labjack_timestamp": 1625097599.875,
                    "vru_type": "pedestrian",
                    "bounding_box": {
                        "x": 320,
                        "y": 240,
                        "width": 80,
                        "height": 120
                    }
                }
                
                # Mock snapshot data
                snapshot_data = {
                    "screenshot_path": f"/uploads/screenshots/{event_id}_full.png",
                    "screenshot_zoom_path": f"/uploads/screenshots/{event_id}_zoom.png",
                    "screenshot_url": f"http://localhost:8000/api/screenshots/{event_id}_full.png",
                    "zoom_url": f"http://localhost:8000/api/screenshots/{event_id}_zoom.png",
                    "image_width": 1920,
                    "image_height": 1080,
                    "capture_timestamp": 1625097600.1
                }
                
                return {
                    "status": "success",
                    "data": {
                        "detection_event": detection_event,
                        "snapshot_data": snapshot_data
                    }
                }
            
            async def _handle_get_project(self, project_id: str) -> dict:
                """Handle single project retrieval"""
                if project_id not in self.projects:
                    return {"status": "error", "message": "Project not found"}
                
                return {"status": "success", "data": self.projects[project_id]}
            
            async def _handle_list_projects(self, params: dict) -> dict:
                """Handle project listing"""
                projects = list(self.projects.values())
                
                # Apply filters
                if "status" in params:
                    projects = [p for p in projects if p["status"] == params["status"]]
                
                if "camera_view" in params:
                    projects = [p for p in projects if p["camera_view"] == params["camera_view"]]
                
                return {"status": "success", "data": {"projects": projects, "total": len(projects)}}
        
        return MockAPIClient()
    
    def validate_schema(self, data: dict, schema: dict) -> bool:
        """Validate data against JSON schema"""
        try:
            jsonschema.validate(data, schema)
            return True
        except jsonschema.ValidationError as e:
            print(f"Schema validation error: {e}")
            return False
    
    @pytest.mark.asyncio
    async def test_project_creation_api_contract(self, mock_api_client, api_schemas):
        """Test project creation API contract"""
        # Valid project creation request
        valid_request = {
            "name": "API Contract Test Project",
            "description": "Testing API contract validation",
            "camera_model": "TestCam Pro",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide Angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO"
        }
        
        # Test valid request
        assert self.validate_schema(valid_request, api_schemas["project_create_request"])
        
        response = await mock_api_client.post("/projects", valid_request)
        assert response["status"] == "success"
        
        # Validate response schema
        project_data = response["data"]
        assert self.validate_schema(project_data, api_schemas["project_response"])
        
        # Test required fields
        assert "id" in project_data
        assert project_data["name"] == valid_request["name"]
        assert project_data["camera_view"] == valid_request["camera_view"]
        assert project_data["status"] in ["Active", "Completed", "Draft"]
        
        # Test invalid requests
        invalid_requests = [
            # Missing required field
            {
                "description": "Missing name field",
                "camera_model": "TestCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            },
            # Invalid camera_view
            {
                "name": "Test Project",
                "camera_model": "TestCam",
                "camera_view": "Invalid View",
                "signal_type": "GPIO"
            },
            # Invalid signal_type
            {
                "name": "Test Project",
                "camera_model": "TestCam", 
                "camera_view": "Front-facing VRU",
                "signal_type": "Invalid Signal"
            },
            # Name too short
            {
                "name": "AB",  # Less than 3 characters
                "camera_model": "TestCam",
                "camera_view": "Front-facing VRU", 
                "signal_type": "GPIO"
            }
        ]
        
        for invalid_request in invalid_requests:
            assert not self.validate_schema(invalid_request, api_schemas["project_create_request"])
    
    @pytest.mark.asyncio
    async def test_video_assignment_api_contract(self, mock_api_client, api_schemas):
        """Test video assignment API contract"""
        # Create a project first
        project_data = {
            "name": "Video Assignment Test",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        project_response = await mock_api_client.post("/projects", project_data)
        project_id = project_response["data"]["id"]
        
        # Valid assignment request
        valid_request = {
            "project_id": project_id,
            "video_ids": [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())],
            "assignment_reason": "Test assignment for API contract validation",
            "intelligent_match": True
        }
        
        # Test valid request schema
        assert self.validate_schema(valid_request, api_schemas["video_assignment_request"])
        
        # Test assignment
        response = await mock_api_client.post("/projects/assign-videos", valid_request)
        assert response["status"] == "success"
        
        # Validate response schema
        assignment_data = response["data"]
        assert self.validate_schema(assignment_data, api_schemas["video_assignment_response"])
        
        # Test response data
        assert assignment_data["success_count"] == len(valid_request["video_ids"])
        assert assignment_data["failure_count"] == 0
        assert len(assignment_data["assignments"]) == len(valid_request["video_ids"])
        
        # Test assignment properties
        for assignment in assignment_data["assignments"]:
            assert assignment["project_id"] == project_id
            assert assignment["video_id"] in valid_request["video_ids"]
            assert 0 <= assignment["confidence_score"] <= 1
            assert isinstance(assignment["intelligent_match"], bool)
        
        # Test invalid requests
        invalid_requests = [
            # Missing project_id
            {
                "video_ids": [str(uuid.uuid4())]
            },
            # Empty video_ids
            {
                "project_id": project_id,
                "video_ids": []
            },
            # Invalid project_id format
            {
                "project_id": "invalid-uuid",
                "video_ids": [str(uuid.uuid4())]
            },
            # Too many video_ids (over limit)
            {
                "project_id": project_id,
                "video_ids": [str(uuid.uuid4()) for _ in range(101)]  # Over 100 limit
            }
        ]
        
        for invalid_request in invalid_requests:
            assert not self.validate_schema(invalid_request, api_schemas["video_assignment_request"])
    
    @pytest.mark.asyncio
    async def test_project_playlist_api_contract(self, mock_api_client, api_schemas):
        """Test project playlist API contract"""
        # Create project and assign videos
        project_data = {
            "name": "Playlist Test Project",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        project_response = await mock_api_client.post("/projects", project_data)
        project_id = project_response["data"]["id"]
        
        # Assign some videos
        video_ids = [str(uuid.uuid4()) for _ in range(5)]
        assignment_request = {
            "project_id": project_id,
            "video_ids": video_ids,
            "assignment_reason": "Playlist testing"
        }
        
        await mock_api_client.post("/projects/assign-videos", assignment_request)
        
        # Test playlist retrieval
        playlist_response = await mock_api_client.get(f"/projects/{project_id}/playlist")
        assert playlist_response["status"] == "success"
        
        # Validate response schema
        playlist_data = playlist_response["data"]
        assert self.validate_schema(playlist_data, api_schemas["project_playlist_response"])
        
        # Test playlist structure
        assert playlist_data["project"]["id"] == project_id
        assert playlist_data["total_count"] == len(video_ids)
        assert playlist_data["total_duration"] > 0
        assert len(playlist_data["videos"]) <= playlist_data["total_count"]
        
        # Test video structure in playlist
        for video in playlist_data["videos"]:
            assert "id" in video
            assert "filename" in video
            assert "duration" in video
            assert "assignment" in video
            
            # Test assignment structure
            assignment = video["assignment"]
            assert "id" in assignment
            assert "confidence_score" in assignment
            assert "intelligent_match" in assignment
            assert 0 <= assignment["confidence_score"] <= 1
        
        # Test pagination
        paginated_response = await mock_api_client.get(
            f"/projects/{project_id}/playlist",
            {"page": 1, "limit": 2}
        )
        
        paginated_data = paginated_response["data"]
        assert len(paginated_data["videos"]) <= 2
        assert paginated_data["pagination"]["page"] == 1
        assert paginated_data["pagination"]["limit"] == 2
    
    @pytest.mark.asyncio
    async def test_failure_snapshot_api_contract(self, mock_api_client, api_schemas):
        """Test failure snapshot API contract"""
        event_id = str(uuid.uuid4())
        
        # Test snapshot retrieval
        response = await mock_api_client.get(f"/detection-events/{event_id}/snapshot")
        assert response["status"] == "success"
        
        # Validate response schema
        snapshot_data = response["data"]
        assert self.validate_schema(snapshot_data, api_schemas["failure_snapshot_response"])
        
        # Test detection event structure
        detection_event = snapshot_data["detection_event"]
        assert detection_event["id"] == event_id
        assert detection_event["validation_result"] == "Fail"
        assert "timestamp" in detection_event
        assert "test_session_id" in detection_event
        
        # Test bounding box structure if present
        if detection_event.get("bounding_box"):
            bbox = detection_event["bounding_box"]
            assert bbox["width"] >= 0
            assert bbox["height"] >= 0
            assert isinstance(bbox["x"], (int, float))
            assert isinstance(bbox["y"], (int, float))
        
        # Test snapshot data structure
        snapshot = snapshot_data["snapshot_data"]
        assert "screenshot_path" in snapshot
        assert "screenshot_url" in snapshot
        
        # Test URL formats if present
        if snapshot["screenshot_url"]:
            assert snapshot["screenshot_url"].startswith("http")
        
        if snapshot["zoom_url"]:
            assert snapshot["zoom_url"].startswith("http")
    
    @pytest.mark.asyncio
    async def test_backwards_compatibility(self, mock_api_client):
        """Test backwards compatibility with existing API"""
        # Test that old API still works alongside new schema
        
        # Create project using new schema
        new_project = {
            "name": "Backwards Compatibility Test",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = await mock_api_client.post("/projects", new_project)
        project_id = response["data"]["id"]
        
        # Test that project can be retrieved with both old and new formats
        project_response = await mock_api_client.get(f"/projects/{project_id}")
        project_data = project_response["data"]
        
        # Should contain all new fields
        assert "video_count" in project_data
        assert "total_duration" in project_data
        
        # Should maintain old field compatibility
        assert "created_at" in project_data
        assert "status" in project_data
        
        # Test listing projects with filters (should work with old parameters)
        filtered_response = await mock_api_client.get("/projects", {"status": "Active"})
        assert filtered_response["status"] == "success"
        
        filtered_projects = filtered_response["data"]["projects"]
        assert len(filtered_projects) > 0
        
        # All returned projects should have Active status
        for project in filtered_projects:
            assert project["status"] == "Active"
    
    @pytest.mark.asyncio
    async def test_error_handling_contracts(self, mock_api_client):
        """Test error handling API contracts"""
        # Test 404 errors
        nonexistent_id = str(uuid.uuid4())
        
        # Non-existent project
        response = await mock_api_client.get(f"/projects/{nonexistent_id}")
        assert response["status"] == "error"
        assert "not found" in response["message"].lower()
        
        # Non-existent project playlist
        response = await mock_api_client.get(f"/projects/{nonexistent_id}/playlist")
        assert response["status"] == "error"
        assert "not found" in response["message"].lower()
        
        # Test validation errors for video assignment
        invalid_assignment = {
            "project_id": "invalid-uuid-format",
            "video_ids": ["also-invalid"]
        }
        
        # This should fail at schema validation level
        # (In real implementation, this would return a 400 error)
        
        # Test duplicate assignment
        # First create a valid project
        project_data = {
            "name": "Error Test Project",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU", 
            "signal_type": "GPIO"
        }
        
        project_response = await mock_api_client.post("/projects", project_data)
        project_id = project_response["data"]["id"]
        
        video_id = str(uuid.uuid4())
        
        # First assignment should succeed
        first_assignment = {
            "project_id": project_id,
            "video_ids": [video_id]
        }
        
        response1 = await mock_api_client.post("/projects/assign-videos", first_assignment)
        assert response1["status"] == "success"
        assert response1["data"]["success_count"] == 1
        
        # Second assignment of same video should show error
        response2 = await mock_api_client.post("/projects/assign-videos", first_assignment)
        assert response2["status"] == "success"  # API succeeds but shows errors
        assert response2["data"]["failure_count"] == 1
        assert len(response2["data"]["errors"]) > 0
        assert "already assigned" in response2["data"]["errors"][0].lower()
    
    @pytest.mark.asyncio
    async def test_performance_contract_compliance(self, mock_api_client):
        """Test API performance contract compliance"""
        import time
        
        # Test response time contracts
        performance_tests = [
            {
                "name": "project_creation",
                "max_time_ms": 500,
                "test_func": lambda: mock_api_client.post("/projects", {
                    "name": "Performance Test",
                    "camera_model": "TestCam",
                    "camera_view": "Front-facing VRU",
                    "signal_type": "GPIO"
                })
            },
            {
                "name": "project_retrieval",
                "max_time_ms": 200,
                "setup_func": lambda: mock_api_client.post("/projects", {
                    "name": "Perf Test Project",
                    "camera_model": "TestCam",
                    "camera_view": "Front-facing VRU",
                    "signal_type": "GPIO"
                }),
                "test_func": None  # Will be set after setup
            },
            {
                "name": "playlist_retrieval", 
                "max_time_ms": 300,
                "setup_func": None,  # Will be set
                "test_func": None
            }
        ]
        
        for test in performance_tests:
            # Setup if needed
            if test.get("setup_func"):
                setup_response = await test["setup_func"]()
                project_id = setup_response["data"]["id"]
                
                if test["name"] == "project_retrieval":
                    test["test_func"] = lambda pid=project_id: mock_api_client.get(f"/projects/{pid}")
                elif test["name"] == "playlist_retrieval":
                    # Assign videos first
                    await mock_api_client.post("/projects/assign-videos", {
                        "project_id": project_id,
                        "video_ids": [str(uuid.uuid4()) for _ in range(3)]
                    })
                    test["test_func"] = lambda pid=project_id: mock_api_client.get(f"/projects/{pid}/playlist")
            
            # Performance test
            start_time = time.perf_counter()
            response = await test["test_func"]()
            end_time = time.perf_counter()
            
            execution_time_ms = (end_time - start_time) * 1000
            
            # Assert performance contract
            assert response["status"] == "success", f"{test['name']} failed"
            assert execution_time_ms <= test["max_time_ms"], \
                f"{test['name']} took {execution_time_ms:.1f}ms, exceeds {test['max_time_ms']}ms contract"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])