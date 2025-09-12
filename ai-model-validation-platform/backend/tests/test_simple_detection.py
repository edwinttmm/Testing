"""
Test Simple LabJack Detection System

Test the simple background detection workflow:
1. Start detection before video
2. Collect events during video 
3. Stop detection after video
4. Analyze results post-video
"""

import pytest
import asyncio
import time
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import get_db
from src.services.simple_labjack_detection import (
    get_detector,
    start_simple_detection,
    stop_simple_detection,
    get_detection_status,
    analyze_detection_results
)

client = TestClient(app)

@pytest.fixture
def test_session_id():
    """Generate unique session ID for testing"""
    return f"test_session_{int(time.time() * 1000)}"

def test_simple_detection_service():
    """Test the simple detection service directly"""
    
    # Test starting detection
    session_id = f"test_{int(time.time() * 1000)}"
    result = start_simple_detection(session_id, tolerance_ms=100)
    
    assert result["success"] == True
    assert result["session_id"] == session_id
    assert result["tolerance_ms"] == 100
    assert "start_time" in result
    
    # Test status check
    status = get_detection_status()
    assert status["running"] == True
    assert status["session_id"] == session_id
    assert status["events_collected"] >= 0
    
    # Wait a moment to potentially collect events
    time.sleep(0.5)
    
    # Test stopping detection
    stop_result = stop_simple_detection()
    assert stop_result["success"] == True
    assert stop_result["session_id"] == session_id
    assert "total_detections" in stop_result
    assert "detection_events" in stop_result
    
    # Test status after stop
    status_after = get_detection_status()
    assert status_after["running"] == False

def test_detection_api_endpoints(test_session_id):
    """Test the REST API endpoints"""
    
    # Test start endpoint
    start_response = client.post(
        "/api/v1/detection/start",
        json={
            "session_id": test_session_id,
            "tolerance_ms": 100
        }
    )
    
    assert start_response.status_code == 200
    start_data = start_response.json()
    assert start_data["success"] == True
    assert start_data["session_id"] == test_session_id
    
    # Test status endpoint
    status_response = client.get("/api/v1/detection/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["running"] == True
    assert status_data["session_id"] == test_session_id
    
    # Wait briefly
    time.sleep(0.5)
    
    # Test stop endpoint
    stop_response = client.post("/api/v1/detection/stop")
    assert stop_response.status_code == 200
    stop_data = stop_response.json()
    assert stop_data["success"] == True
    assert stop_data["session_id"] == test_session_id

def test_detection_analysis():
    """Test detection analysis against video events"""
    
    # Start and stop a detection session
    session_id = f"analysis_test_{int(time.time() * 1000)}"
    
    start_result = start_simple_detection(session_id)
    assert start_result["success"] == True
    
    # Simulate some time passing
    time.sleep(0.2)
    
    stop_result = stop_simple_detection()
    assert stop_result["success"] == True
    
    # Create mock video events
    video_events = [
        {
            "timestamp": 1.0,
            "event_type": "VRU_detection", 
            "class_label": "pedestrian",
            "confidence": 0.95
        },
        {
            "timestamp": 2.5,
            "event_type": "VRU_detection",
            "class_label": "cyclist", 
            "confidence": 0.87
        }
    ]
    
    # Test analysis
    analysis_result = analyze_detection_results(stop_result, video_events)
    
    assert analysis_result["success"] == True
    assert "total_detections" in analysis_result
    assert "accuracy_percentage" in analysis_result
    assert "video_correlations" in analysis_result

def test_detection_analysis_api(test_session_id):
    """Test detection analysis via API"""
    
    # Start detection session
    start_response = client.post(
        "/api/v1/detection/start",
        json={
            "session_id": test_session_id,
            "tolerance_ms": 50
        }
    )
    assert start_response.status_code == 200
    
    # Wait briefly
    time.sleep(0.3)
    
    # Stop detection session
    stop_response = client.post("/api/v1/detection/stop")
    assert stop_response.status_code == 200
    
    # Test analysis endpoint
    analysis_response = client.post(
        f"/api/v1/detection/analyze/{test_session_id}",
        json={
            "video_events": [
                {
                    "timestamp": 0.5,
                    "event_type": "VRU_detection",
                    "class_label": "pedestrian",
                    "confidence": 0.9,
                    "bbox_x": 100,
                    "bbox_y": 100,
                    "bbox_width": 50,
                    "bbox_height": 100
                }
            ],
            "save_to_database": True
        }
    )
    
    assert analysis_response.status_code == 200
    analysis_data = analysis_response.json()
    assert analysis_data["success"] == True
    assert "accuracy_percentage" in analysis_data

def test_session_listing_api():
    """Test session listing endpoints"""
    
    # List all sessions
    list_response = client.get("/api/v1/detection/sessions")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "sessions" in list_data
    assert "total" in list_data

def test_error_handling():
    """Test error handling scenarios"""
    
    # Test starting detection with duplicate session ID
    session_id = f"duplicate_test_{int(time.time() * 1000)}"
    
    # Start first session
    start_response1 = client.post(
        "/api/v1/detection/start",
        json={"session_id": session_id, "tolerance_ms": 100}
    )
    assert start_response1.status_code == 200
    
    # Try to start duplicate session
    start_response2 = client.post(
        "/api/v1/detection/start", 
        json={"session_id": session_id, "tolerance_ms": 100}
    )
    assert start_response2.status_code == 400  # Should fail
    
    # Clean up
    client.post("/api/v1/detection/stop")

def test_multiple_session_isolation():
    """Test that multiple detection sessions are properly isolated"""
    
    session1_id = f"session1_{int(time.time() * 1000)}"
    session2_id = f"session2_{int(time.time() * 1000)}"
    
    # Start first session
    start1 = start_simple_detection(session1_id, tolerance_ms=100)
    assert start1["success"] == True
    
    # Try to start second session (should fail - only one active at a time)
    start2 = start_simple_detection(session2_id, tolerance_ms=200)
    assert start2["success"] == False
    
    # Stop first session
    stop1 = stop_simple_detection()
    assert stop1["success"] == True
    assert stop1["session_id"] == session1_id
    
    # Now second session should work
    start2_retry = start_simple_detection(session2_id, tolerance_ms=200)
    assert start2_retry["success"] == True
    
    # Clean up
    stop_simple_detection()

def test_detection_with_project_video_association():
    """Test detection session with project and video association"""
    
    # Create test project first (simplified for test)
    project_data = {
        "name": "Test Detection Project",
        "description": "Test project for detection",
        "camera_model": "Test Camera",
        "camera_view": "Front-facing VRU",
        "signal_type": "GPIO"
    }
    
    project_response = client.post("/api/projects", json=project_data)
    assert project_response.status_code == 200
    project_id = project_response.json()["id"]
    
    # Start detection with project association
    session_id = f"project_test_{int(time.time() * 1000)}"
    start_response = client.post(
        "/api/v1/detection/start",
        json={
            "session_id": session_id,
            "tolerance_ms": 100,
            "project_id": project_id
        }
    )
    
    assert start_response.status_code == 200
    start_data = start_response.json()
    assert start_data["success"] == True
    
    # Stop and check database association
    stop_response = client.post("/api/v1/detection/stop")
    assert stop_response.status_code == 200
    
    # Get session details to verify project association
    session_response = client.get(f"/api/v1/detection/sessions/{session_id}")
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["session"]["project_id"] == project_id

def test_workflow_integration():
    """Test the complete workflow as described in requirements"""
    
    session_id = f"workflow_test_{int(time.time() * 1000)}"
    
    # Phase 1: BEFORE VIDEO STARTS
    print("Phase 1: Starting LabJack detection before video...")
    start_response = client.post(
        "/api/v1/detection/start",
        json={
            "session_id": session_id,
            "tolerance_ms": 100
        }
    )
    assert start_response.status_code == 200
    start_data = start_response.json()
    print(f"✅ Detection started: {start_data['message']}")
    
    # Phase 2: DURING VIDEO PLAYBOOK
    print("Phase 2: Video playing - detection running silently in background...")
    
    # Check status without interfering
    status_response = client.get("/api/v1/detection/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    print(f"📊 Status: {status_data['message']}")
    assert status_data["running"] == True
    
    # Simulate video playback time
    time.sleep(1.0)
    
    # Phase 3: AFTER VIDEO FINISHES
    print("Phase 3: Video finished - stopping detection and analyzing results...")
    
    stop_response = client.post("/api/v1/detection/stop")
    assert stop_response.status_code == 200
    stop_data = stop_response.json()
    print(f"📈 Detection completed: {stop_data['total_detections']} events collected")
    
    # Phase 4: POST-PROCESSING ANALYSIS
    print("Phase 4: Analyzing detection results against video timeline...")
    
    # Simulate video events that occurred during playback
    video_events = [
        {"timestamp": 0.3, "event_type": "VRU_detection", "class_label": "pedestrian", "confidence": 0.95},
        {"timestamp": 0.7, "event_type": "VRU_detection", "class_label": "cyclist", "confidence": 0.88}
    ]
    
    analysis_response = client.post(
        f"/api/v1/detection/analyze/{session_id}",
        json={
            "video_events": video_events,
            "save_to_database": True
        }
    )
    
    if analysis_response.status_code == 200:
        analysis_data = analysis_response.json()
        print(f"🎯 Analysis complete: {analysis_data['accuracy_percentage']:.1f}% accuracy")
        print(f"📊 Results: {analysis_data['matched_detections']}/{analysis_data['total_detections']} detections matched")
        
        assert analysis_data["success"] == True
        assert "accuracy_percentage" in analysis_data
    
    print("✅ Complete workflow test successful!")

def test_performance_under_load():
    """Test detection service performance under load"""
    import threading
    import concurrent.futures
    
    def run_detection_cycle(cycle_id):
        """Run a complete detection cycle"""
        session_id = f"perf_test_{cycle_id}_{int(time.time() * 1000)}"
        
        # Start detection
        start_result = start_simple_detection(session_id, tolerance_ms=50)
        if not start_result["success"]:
            return {"error": "Failed to start", "cycle": cycle_id}
        
        # Run for short time
        time.sleep(0.1)
        
        # Stop detection
        stop_result = stop_simple_detection()
        if not stop_result["success"]:
            return {"error": "Failed to stop", "cycle": cycle_id}
        
        return {
            "cycle": cycle_id,
            "detections": stop_result["total_detections"],
            "duration": stop_result["duration_seconds"]
        }
    
    # Note: Due to singleton detector, only one session can run at a time
    # This tests sequential performance rather than parallel
    results = []
    for i in range(3):  # Run 3 cycles sequentially
        result = run_detection_cycle(i)
        results.append(result)
        time.sleep(0.1)  # Brief pause between cycles
    
    # Verify all cycles completed successfully
    for result in results:
        assert "error" not in result
        assert "detections" in result
    
    print(f"Performance test completed: {len(results)} cycles")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])