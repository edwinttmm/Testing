#!/usr/bin/env python3
"""
Sequential Video Processing Validation Tests
============================================

Tests to validate that multiple videos in a test session process sequentially
without creating phantom sessions. Addresses user concern: 
"videos are coming separately it should automatically play one after another"
"""
import pytest
import httpx
import json
import asyncio
import time
import sqlite3
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import io
import websockets

# Test Configuration
BASE_URL = "http://localhost:8001"
WS_URL = "ws://localhost:8001"
TIMEOUT = 60.0

class SequentialVideoProcessingTester:
    """Test sequential video processing and phantom session prevention"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.test_videos = [
            {
                "filename": "child-1-1-1.mp4",
                "content": b"fake video content for child-1-1-1 testing",
                "expected_detections": ["pedestrian", "child"]
            },
            {
                "filename": "ae8e974b-0533-4cab-959a-493793e00328.mp4", 
                "content": b"fake video content for ae8e974b testing",
                "expected_detections": ["vehicle", "cyclist"]
            }
        ]
        self.session_id = None
        self.project_id = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

class TestSequentialVideoProcessing:
    """Test sequential video processing workflow"""
    
    @pytest.mark.asyncio
    async def test_sequential_video_processing_no_phantom_sessions(self):
        """Test that multiple videos process sequentially without phantom sessions"""
        async with SequentialVideoProcessingTester() as tester:
            # 1. Create a project for testing
            project_data = {
                "name": "Sequential Video Test Project",
                "description": "Testing sequential video processing",
                "cameraModel": "Sequential Test Camera",
                "cameraView": "Front-facing VRU", 
                "signalType": "GPIO"
            }
            
            project_response = await tester.client.post(
                f"{BASE_URL}/api/projects", 
                json=project_data
            )
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # 2. Create a single test session
            session_data = {
                "name": "Sequential Video Processing Test",
                "description": "Test sequential processing of multiple videos", 
                "project_id": tester.project_id,
                "configuration": {
                    "auto_advance": True,
                    "sequential_processing": True
                }
            }
            
            session_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions",
                json=session_data
            )
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # 3. Upload multiple videos to the SAME session
            uploaded_videos = []
            for video_data in tester.test_videos:
                files = {
                    "file": (video_data["filename"], io.BytesIO(video_data["content"]), "video/mp4")
                }
                data = {
                    "project_id": tester.project_id,
                    "session_id": tester.session_id  # Key: All videos use SAME session
                }
                
                upload_response = await tester.client.post(
                    f"{BASE_URL}/api/videos",
                    files=files,
                    data=data
                )
                assert upload_response.status_code == 201
                uploaded_videos.append(upload_response.json())
            
            # 4. Start the test session with multiple videos
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                json={"video_ids": [v["id"] for v in uploaded_videos]}
            )
            assert start_response.status_code == 200
            
            # 5. Monitor session status - ensure no phantom sessions created
            await asyncio.sleep(2)  # Allow processing to start
            
            # Check that only ONE session exists for this project
            sessions_response = await tester.client.get(
                f"{BASE_URL}/api/enhanced-test/sessions?project_id={tester.project_id}"
            )
            assert sessions_response.status_code == 200
            sessions = sessions_response.json()
            
            # CRITICAL TEST: Only one session should exist
            assert len(sessions) == 1, f"Expected 1 session, found {len(sessions)} - phantom sessions detected!"
            
            # Verify it's our session
            assert sessions[0]["id"] == tester.session_id
            
            # 6. Check that videos are processed sequentially
            session_status_response = await tester.client.get(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status"
            )
            assert session_status_response.status_code == 200
            status = session_status_response.json()
            
            # Should have processing queue with multiple videos
            assert "video_queue" in status
            assert len(status["video_queue"]) == 2
            
            # Videos should be in queue order (not all processing simultaneously)
            assert status["video_queue"][0]["status"] in ["processing", "queued"]
            assert status["video_queue"][1]["status"] in ["queued", "pending"]
            
    @pytest.mark.asyncio
    async def test_video_auto_advance_workflow(self):
        """Test that videos automatically advance from one to another"""
        async with SequentialVideoProcessingTester() as tester:
            # Setup project and session
            project_data = {
                "name": "Auto-Advance Test Project",
                "cameraModel": "Auto-Advance Camera",
                "signalType": "GPIO"
            }
            
            project_response = await tester.client.post(
                f"{BASE_URL}/api/projects",
                json=project_data
            )
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            session_data = {
                "name": "Auto-Advance Test Session",
                "project_id": tester.project_id,
                "configuration": {
                    "auto_advance": True,
                    "sequential_processing": True,
                    "processing_mode": "automatic"
                }
            }
            
            session_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions",
                json=session_data
            )
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # Upload test videos
            video_ids = []
            for video_data in tester.test_videos:
                files = {"file": (video_data["filename"], io.BytesIO(video_data["content"]), "video/mp4")}
                data = {"project_id": tester.project_id, "session_id": tester.session_id}
                
                upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
                assert upload_response.status_code == 201
                video_ids.append(upload_response.json()["id"])
            
            # Start processing with auto-advance
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                json={
                    "video_ids": video_ids,
                    "auto_advance": True,
                    "processing_mode": "sequential"
                }
            )
            assert start_response.status_code == 200
            
            # Monitor the sequential processing
            max_wait_time = 30  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                status_response = await tester.client.get(
                    f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status"
                )
                assert status_response.status_code == 200
                status = status_response.json()
                
                # Check if processing is complete
                if status.get("status") == "completed":
                    # Verify both videos were processed
                    assert "processed_videos" in status
                    assert len(status["processed_videos"]) == 2
                    
                    # Check processing order
                    processed_videos = status["processed_videos"]
                    assert processed_videos[0]["filename"] == "child-1-1-1.mp4"
                    assert processed_videos[1]["filename"] == "ae8e974b-0533-4cab-959a-493793e00328.mp4"
                    break
                    
                await asyncio.sleep(2)
            else:
                pytest.fail("Auto-advance processing did not complete within timeout")

    @pytest.mark.asyncio
    async def test_websocket_sequential_updates(self):
        """Test WebSocket updates during sequential video processing"""
        async with SequentialVideoProcessingTester() as tester:
            # Setup project and session
            project_data = {"name": "WebSocket Sequential Test", "cameraModel": "WS Camera", "signalType": "GPIO"}
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            session_data = {
                "name": "WebSocket Sequential Session",
                "project_id": tester.project_id,
                "configuration": {"auto_advance": True, "sequential_processing": True}
            }
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # Upload videos
            video_ids = []
            for video_data in tester.test_videos:
                files = {"file": (video_data["filename"], io.BytesIO(video_data["content"]), "video/mp4")}
                data = {"project_id": tester.project_id, "session_id": tester.session_id}
                upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
                assert upload_response.status_code == 201
                video_ids.append(upload_response.json()["id"])
            
            # Connect to WebSocket for real-time updates
            ws_updates = []
            
            async def monitor_websocket():
                try:
                    async with websockets.connect(f"{WS_URL}/ws/test-session/{tester.session_id}") as websocket:
                        while True:
                            try:
                                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                                update = json.loads(message)
                                ws_updates.append(update)
                                
                                # Break if session completed
                                if update.get("status") == "completed":
                                    break
                            except asyncio.TimeoutError:
                                continue
                except Exception as e:
                    print(f"WebSocket error: {e}")
            
            # Start monitoring and processing simultaneously
            monitor_task = asyncio.create_task(monitor_websocket())
            
            # Start processing
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                json={"video_ids": video_ids, "auto_advance": True}
            )
            assert start_response.status_code == 200
            
            # Wait for completion
            try:
                await asyncio.wait_for(monitor_task, timeout=30)
            except asyncio.TimeoutError:
                monitor_task.cancel()
            
            # Verify we received sequential updates
            assert len(ws_updates) >= 2, "Should receive updates for each video processing step"
            
            # Check for sequential processing indicators
            video_start_updates = [u for u in ws_updates if u.get("event") == "video_processing_started"]
            assert len(video_start_updates) == 2, "Should receive start events for both videos"

class TestPhantomSessionPrevention:
    """Test prevention of phantom/duplicate sessions"""
    
    @pytest.mark.asyncio
    async def test_no_duplicate_sessions_created(self):
        """Ensure duplicate sessions are not created for same project/video combo"""
        async with SequentialVideoProcessingTester() as tester:
            # Create project
            project_data = {"name": "Phantom Prevention Test", "cameraModel": "Test Camera", "signalType": "GPIO"}
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # Try to create multiple sessions with same parameters (should be prevented)
            session_data = {
                "name": "Duplicate Session Test",
                "project_id": tester.project_id,
                "configuration": {"auto_advance": True}
            }
            
            # First session should succeed
            session1_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session1_response.status_code == 201
            session1_id = session1_response.json()["id"]
            
            # Check total sessions before second attempt
            sessions_before = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions?project_id={tester.project_id}")
            assert sessions_before.status_code == 200
            sessions_count_before = len(sessions_before.json())
            
            # Second identical session should either:
            # 1. Return the existing session ID, OR
            # 2. Create a new session with different name/config
            session_data["name"] = "Duplicate Session Test - Attempt 2"
            session2_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            
            if session2_response.status_code == 201:
                # If new session created, verify it has different properties
                session2_id = session2_response.json()["id"]
                assert session2_id != session1_id, "New session should have different ID"
                
                # Check total sessions increased by exactly 1
                sessions_after = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions?project_id={tester.project_id}")
                assert sessions_after.status_code == 200
                sessions_count_after = len(sessions_after.json())
                assert sessions_count_after == sessions_count_before + 1
            else:
                # If duplicate prevented, should get appropriate error
                assert session2_response.status_code in [409, 422], "Should prevent duplicate sessions"

    @pytest.mark.asyncio
    async def test_session_cleanup_on_failure(self):
        """Test that failed sessions are properly cleaned up"""
        async with SequentialVideoProcessingTester() as tester:
            # Create project
            project_data = {"name": "Session Cleanup Test", "cameraModel": "Cleanup Camera", "signalType": "GPIO"}
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # Create session with invalid configuration to force failure
            session_data = {
                "name": "Failing Session Test",
                "project_id": tester.project_id,
                "configuration": {
                    "invalid_config": True,
                    "force_failure": True
                }
            }
            
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            if session_response.status_code == 201:
                tester.session_id = session_response.json()["id"]
                
                # Try to start with invalid data
                start_response = await tester.client.post(
                    f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                    json={"video_ids": ["nonexistent-video-id"]}
                )
                
                # Session should handle failure gracefully
                if start_response.status_code != 200:
                    # Check that session is marked as failed, not left hanging
                    status_response = await tester.client.get(
                        f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status"
                    )
                    assert status_response.status_code == 200
                    status = status_response.json()
                    assert status.get("status") in ["failed", "error", "stopped"]

class TestEndToEndAutomation:
    """Test the complete 'click start and come back everything done' workflow"""
    
    @pytest.mark.asyncio
    async def test_full_automation_workflow(self):
        """Test complete automated workflow from start to results"""
        async with SequentialVideoProcessingTester() as tester:
            # 1. Setup: Create project
            project_data = {
                "name": "Full Automation Test Project",
                "description": "Testing complete automation workflow",
                "cameraModel": "Automation Test Camera",
                "signalType": "GPIO"
            }
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # 2. Create automated test session
            session_data = {
                "name": "Full Automation Session",
                "project_id": tester.project_id,
                "configuration": {
                    "auto_advance": True,
                    "sequential_processing": True,
                    "auto_analysis": True,
                    "auto_report": True,
                    "auto_export": True
                }
            }
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # 3. Upload test videos
            video_ids = []
            for video_data in tester.test_videos:
                files = {"file": (video_data["filename"], io.BytesIO(video_data["content"]), "video/mp4")}
                data = {"project_id": tester.project_id, "session_id": tester.session_id}
                upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
                assert upload_response.status_code == 201
                video_ids.append(upload_response.json()["id"])
            
            # 4. Single click to start everything
            automation_start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start-automation",
                json={
                    "video_ids": video_ids,
                    "full_automation": True,
                    "expected_completion_time": 60  # seconds
                }
            )
            assert automation_start_response.status_code == 200
            automation_data = automation_start_response.json()
            assert automation_data.get("automation_started") is True
            
            # 5. Monitor progress until completion (user would "come back later")
            max_wait = 90  # Extended timeout for full automation
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status_response = await tester.client.get(
                    f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status"
                )
                assert status_response.status_code == 200
                status = status_response.json()
                
                if status.get("status") == "completed":
                    # 6. Verify everything is done automatically
                    
                    # Check results are populated
                    results_response = await tester.client.get(
                        f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/results"
                    )
                    assert results_response.status_code == 200
                    results = results_response.json()
                    assert len(results.get("video_results", [])) == 2
                    
                    # Check detection comparisons are created
                    comparisons_response = await tester.client.get(
                        f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/comparisons"
                    )
                    assert comparisons_response.status_code == 200
                    comparisons = comparisons_response.json()
                    assert len(comparisons) > 0
                    
                    # Check report is generated
                    report_response = await tester.client.get(
                        f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/report"
                    )
                    assert report_response.status_code == 200
                    report = report_response.json()
                    assert "summary" in report
                    assert "detailed_results" in report
                    
                    # Check export is available
                    export_response = await tester.client.get(
                        f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/export"
                    )
                    assert export_response.status_code == 200
                    
                    print("✅ Full automation workflow completed successfully")
                    return
                    
                print(f"⏳ Automation progress: {status.get('progress', 0)}%")
                await asyncio.sleep(5)
            
            pytest.fail("Full automation workflow did not complete within timeout")

if __name__ == "__main__":
    print("🎥 Running Sequential Video Processing Tests")
    print("=" * 60)
    
    # Run pytest with verbose output
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", __file__, 
        "-v", "--tb=short", "--no-header", "-s"
    ], cwd=os.path.dirname(__file__) or ".")
    
    exit_code = result.returncode
    if exit_code == 0:
        print("\n✅ All sequential video processing tests passed!")
    else:
        print(f"\n❌ Some tests failed (exit code: {exit_code})")
    
    exit(exit_code)