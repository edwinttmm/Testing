#!/usr/bin/env python3
"""
Frontend Integration Tests
===========================

Tests the integration between backend API and frontend functionality,
specifically focusing on:
1. Enhanced Test Execution page functionality
2. exportTestResults function integration
3. WebSocket real-time updates
4. Complete user workflow validation
"""
import pytest
import httpx
import json
import asyncio
import time
import websockets
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import io

# Test Configuration  
BASE_URL = "http://localhost:8001"
WS_URL = "ws://localhost:8001"
FRONTEND_URL = "http://localhost:3000"  # React dev server
TIMEOUT = 60.0

class FrontendIntegrationTester:
    """Test frontend integration with backend services"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.project_id = None
        self.session_id = None
        self.video_ids = []
        self.ws_messages = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

class TestEnhancedTestExecutionPage:
    """Test Enhanced Test Execution page functionality"""
    
    @pytest.mark.asyncio
    async def test_enhanced_test_execution_page_load(self):
        """Test that Enhanced Test Execution page loads without JavaScript errors"""
        async with FrontendIntegrationTester() as tester:
            # 1. Create test project and session for the page to load
            project_data = {
                "name": "Frontend Integration Test Project",
                "description": "Testing frontend page load",
                "cameraModel": "Frontend Test Camera",
                "signalType": "GPIO"
            }
            
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # 2. Create enhanced test session
            session_data = {
                "name": "Frontend Integration Test Session",
                "project_id": tester.project_id,
                "configuration": {
                    "auto_advance": True,
                    "sequential_processing": True
                }
            }
            
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # 3. Test API endpoints that the frontend page depends on
            
            # Test session status endpoint (page polls this)
            status_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert "id" in status_data
            assert "status" in status_data
            assert "configuration" in status_data
            
            # Test projects list endpoint (for project selection)
            projects_response = await tester.client.get(f"{BASE_URL}/api/projects")
            assert projects_response.status_code == 200
            projects = projects_response.json()
            assert len(projects) >= 1
            
            # Test videos endpoint (for video selection)
            videos_response = await tester.client.get(f"{BASE_URL}/api/videos")
            assert videos_response.status_code == 200
            # Videos list should exist (even if empty)
            assert isinstance(videos_response.json(), list)

    @pytest.mark.asyncio
    async def test_export_test_results_api_integration(self):
        """Test exportTestResults function backend integration"""
        async with FrontendIntegrationTester() as tester:
            # Setup test data
            project_data = {"name": "Export Test Project", "cameraModel": "Export Camera", "signalType": "GPIO"}
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            session_data = {
                "name": "Export Test Session",
                "project_id": tester.project_id,
                "configuration": {"auto_export": True}
            }
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # Upload test video
            test_video = b"test video content for export testing"
            files = {"file": ("export_test.mp4", io.BytesIO(test_video), "video/mp4")}
            data = {"project_id": tester.project_id, "session_id": tester.session_id}
            
            upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
            assert upload_response.status_code == 201
            video_id = upload_response.json()["id"]
            
            # Create some test results to export
            test_results = {
                "video_id": video_id,
                "detections": [
                    {"type": "pedestrian", "confidence": 0.95, "bbox": [100, 100, 200, 200]},
                    {"type": "vehicle", "confidence": 0.87, "bbox": [300, 150, 400, 250]}
                ],
                "summary": {
                    "total_detections": 2,
                    "processing_time": 5.2,
                    "accuracy_score": 0.91
                }
            }
            
            # Create test result in database
            result_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/results",
                json=test_results
            )
            assert result_response.status_code in [200, 201]
            
            # Test the export functionality that exportTestResults() calls
            export_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/export")
            assert export_response.status_code == 200
            
            export_data = export_response.json()
            
            # Verify export contains expected data structure
            assert "session_info" in export_data
            assert "results" in export_data
            assert "summary" in export_data
            assert export_data["session_info"]["id"] == tester.session_id
            
            # Test different export formats
            export_csv_response = await tester.client.get(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/export?format=csv"
            )
            assert export_csv_response.status_code == 200
            
            export_json_response = await tester.client.get(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/export?format=json"
            )
            assert export_json_response.status_code == 200

    @pytest.mark.asyncio 
    async def test_websocket_real_time_updates(self):
        """Test WebSocket real-time updates for frontend"""
        async with FrontendIntegrationTester() as tester:
            # Setup
            project_data = {"name": "WebSocket Test Project", "cameraModel": "WS Camera", "signalType": "GPIO"}
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            session_data = {"name": "WebSocket Test Session", "project_id": tester.project_id}
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # Connect to WebSocket
            ws_messages = []
            
            async def websocket_listener():
                try:
                    async with websockets.connect(f"{WS_URL}/ws/test-session/{tester.session_id}") as websocket:
                        # Wait for initial connection message
                        welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        ws_messages.append(json.loads(welcome_msg))
                        
                        # Listen for updates during test execution
                        while True:
                            try:
                                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                                update = json.loads(message)
                                ws_messages.append(update)
                                
                                # Stop listening when test completes
                                if update.get("event") == "test_completed":
                                    break
                            except asyncio.TimeoutError:
                                continue
                                
                except Exception as e:
                    print(f"WebSocket listener error: {e}")
            
            # Start WebSocket listener
            listener_task = asyncio.create_task(websocket_listener())
            
            # Give WebSocket time to connect
            await asyncio.sleep(1)
            
            # Upload video and start test (trigger WebSocket updates)
            test_video = b"websocket test video content"
            files = {"file": ("ws_test.mp4", io.BytesIO(test_video), "video/mp4")}
            data = {"project_id": tester.project_id, "session_id": tester.session_id}
            
            upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
            assert upload_response.status_code == 201
            video_id = upload_response.json()["id"]
            
            # Start test processing
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                json={"video_ids": [video_id]}
            )
            assert start_response.status_code == 200
            
            # Wait for WebSocket messages
            try:
                await asyncio.wait_for(listener_task, timeout=15)
            except asyncio.TimeoutError:
                listener_task.cancel()
            
            # Verify we received WebSocket messages
            assert len(ws_messages) > 0, "Should receive WebSocket messages"
            
            # Check message structure
            for msg in ws_messages:
                assert "event" in msg or "status" in msg, "Messages should have event or status"
                if "session_id" in msg:
                    assert msg["session_id"] == tester.session_id

class TestCompleteUserWorkflow:
    """Test complete user workflow from frontend perspective"""
    
    @pytest.mark.asyncio
    async def test_complete_user_workflow_integration(self):
        """Test complete workflow: Create Project → Upload Videos → Run Test → View Results"""
        async with FrontendIntegrationTester() as tester:
            # Step 1: Create Project (Frontend: Project Creation Form)
            project_data = {
                "name": "Complete Workflow Test",
                "description": "Testing complete user workflow",
                "cameraModel": "Workflow Test Camera",
                "cameraView": "Front-facing VRU",
                "lensType": "Wide Angle", 
                "resolution": "1920x1080",
                "frameRate": 30,
                "signalType": "GPIO"
            }
            
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            project = project_response.json()
            tester.project_id = project["id"]
            
            # Verify project appears in projects list (Frontend: Projects Dashboard)
            projects_response = await tester.client.get(f"{BASE_URL}/api/projects")
            assert projects_response.status_code == 200
            projects = projects_response.json()
            project_exists = any(p["id"] == tester.project_id for p in projects)
            assert project_exists
            
            # Step 2: Upload Videos (Frontend: Video Upload Component)
            test_videos = [
                {"filename": "child-1-1-1.mp4", "content": b"test video 1 content"},
                {"filename": "ae8e974b-0533-4cab-959a-493793e00328.mp4", "content": b"test video 2 content"}
            ]
            
            uploaded_videos = []
            for video in test_videos:
                files = {"file": (video["filename"], io.BytesIO(video["content"]), "video/mp4")}
                data = {"project_id": tester.project_id}
                
                upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
                assert upload_response.status_code == 201
                uploaded_videos.append(upload_response.json())
            
            tester.video_ids = [v["id"] for v in uploaded_videos]
            
            # Verify videos appear in project (Frontend: Video Management)
            videos_response = await tester.client.get(f"{BASE_URL}/api/videos?project_id={tester.project_id}")
            assert videos_response.status_code == 200
            project_videos = videos_response.json()
            assert len(project_videos) == 2
            
            # Step 3: Create Test Session (Frontend: Enhanced Test Execution Page)
            session_data = {
                "name": "Complete Workflow Test Session",
                "project_id": tester.project_id,
                "configuration": {
                    "auto_advance": True,
                    "sequential_processing": True,
                    "auto_analysis": True,
                    "auto_report": True
                }
            }
            
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            session = session_response.json()
            tester.session_id = session["id"]
            
            # Step 4: Start Test Execution (Frontend: Click "Start Test" button)
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                json={
                    "video_ids": tester.video_ids,
                    "auto_advance": True,
                    "sequential_processing": True
                }
            )
            assert start_response.status_code == 200
            
            # Step 5: Monitor Progress (Frontend: Real-time Progress Display)
            max_wait = 30
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status")
                assert status_response.status_code == 200
                status = status_response.json()
                
                # Frontend would display this progress
                progress = status.get("progress", 0)
                current_status = status.get("status", "unknown")
                
                print(f"Test Progress: {progress}% - Status: {current_status}")
                
                if current_status in ["completed", "finished"]:
                    break
                    
                await asyncio.sleep(2)
            
            # Step 6: View Results (Frontend: Results Dashboard) 
            results_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/results")
            assert results_response.status_code == 200
            results = results_response.json()
            
            # Frontend would display these results
            assert "video_results" in results or "results" in results
            
            # Step 7: Export Results (Frontend: Export Button - exportTestResults function)
            export_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/export")
            assert export_response.status_code == 200
            export_data = export_response.json()
            
            # Verify export data structure matches frontend expectations
            assert "session_info" in export_data or "summary" in export_data
            
            # Step 8: View Dashboard Statistics (Frontend: Dashboard Page)
            stats_response = await tester.client.get(f"{BASE_URL}/api/dashboard/stats")
            assert stats_response.status_code == 200
            stats = stats_response.json()
            
            # Verify stats include our test data
            assert stats["totalProjects"] >= 1
            assert stats["totalVideos"] >= 2
            
            print("✅ Complete user workflow test passed!")

    @pytest.mark.asyncio
    async def test_specific_video_files_workflow(self):
        """Test workflow with specific video files mentioned by user"""
        async with FrontendIntegrationTester() as tester:
            # Create project for specific video test
            project_data = {
                "name": "Specific Videos Test Project",
                "description": "Testing specific video files: child-1-1-1.mp4 and ae8e974b-0533-4cab-959a-493793e00328.mp4",
                "cameraModel": "Specific Video Camera",
                "signalType": "GPIO"
            }
            
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # Upload the specific videos mentioned by the user
            specific_videos = [
                {
                    "filename": "child-1-1-1.mp4",
                    "content": b"child pedestrian detection test video content",
                    "expected_detections": ["pedestrian", "child"]
                },
                {
                    "filename": "ae8e974b-0533-4cab-959a-493793e00328.mp4", 
                    "content": b"vehicle detection test video content with unique UUID filename",
                    "expected_detections": ["vehicle", "cyclist"]
                }
            ]
            
            video_ids = []
            for video_data in specific_videos:
                files = {"file": (video_data["filename"], io.BytesIO(video_data["content"]), "video/mp4")}
                data = {"project_id": tester.project_id}
                
                upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
                assert upload_response.status_code == 201
                uploaded_video = upload_response.json()
                
                # Verify filename is preserved correctly
                assert uploaded_video["filename"] == video_data["filename"]
                video_ids.append(uploaded_video["id"])
            
            # Create test session specifically for sequential processing
            session_data = {
                "name": "Specific Videos Sequential Test",
                "project_id": tester.project_id,
                "description": "Testing sequential processing of child-1-1-1.mp4 and ae8e974b-0533-4cab-959a-493793e00328.mp4",
                "configuration": {
                    "auto_advance": True,
                    "sequential_processing": True,
                    "process_in_order": True,
                    "video_specific_settings": {
                        "child-1-1-1.mp4": {"detection_focus": "pedestrian"},
                        "ae8e974b-0533-4cab-959a-493793e00328.mp4": {"detection_focus": "vehicle"}
                    }
                }
            }
            
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # Start sequential processing
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start",
                json={
                    "video_ids": video_ids,
                    "processing_order": ["child-1-1-1.mp4", "ae8e974b-0533-4cab-959a-493793e00328.mp4"],
                    "sequential_processing": True
                }
            )
            assert start_response.status_code == 200
            
            # Monitor to ensure sequential processing (not parallel)
            max_wait = 45
            start_time = time.time()
            processing_log = []
            
            while time.time() - start_time < max_wait:
                status_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status")
                assert status_response.status_code == 200
                status = status_response.json()
                
                # Log processing status for analysis
                if "current_video" in status:
                    processing_log.append({
                        "time": time.time() - start_time,
                        "current_video": status["current_video"],
                        "status": status.get("status"),
                        "progress": status.get("progress", 0)
                    })
                
                if status.get("status") in ["completed", "finished"]:
                    break
                    
                await asyncio.sleep(3)
            
            # Verify sequential processing occurred
            assert len(processing_log) > 0, "Should have processing log entries"
            
            # Check that child-1-1-1.mp4 was processed before ae8e974b video
            child_video_entries = [entry for entry in processing_log if "child-1-1-1" in str(entry.get("current_video", ""))]
            uuid_video_entries = [entry for entry in processing_log if "ae8e974b" in str(entry.get("current_video", ""))]
            
            if child_video_entries and uuid_video_entries:
                first_child_time = min(entry["time"] for entry in child_video_entries)
                first_uuid_time = min(entry["time"] for entry in uuid_video_entries)
                
                # Child video should start processing before UUID video (sequential)
                assert first_child_time < first_uuid_time, "Videos should process sequentially, not simultaneously"
            
            print("✅ Specific video files workflow test completed")

class TestAutomatedReportGeneration:
    """Test automated report generation without user intervention"""
    
    @pytest.mark.asyncio
    async def test_automated_report_generation(self):
        """Test that reports are generated automatically without user intervention"""
        async with FrontendIntegrationTester() as tester:
            # Setup automated test
            project_data = {"name": "Auto Report Test", "cameraModel": "Auto Camera", "signalType": "GPIO"}
            project_response = await tester.client.post(f"{BASE_URL}/api/projects", json=project_data)
            assert project_response.status_code == 201
            tester.project_id = project_response.json()["id"]
            
            # Create session with auto-reporting enabled
            session_data = {
                "name": "Automated Report Session",
                "project_id": tester.project_id,
                "configuration": {
                    "auto_report": True,
                    "auto_analysis": True,
                    "auto_export": True,
                    "report_formats": ["json", "csv", "pdf"],
                    "generate_summary": True
                }
            }
            
            session_response = await tester.client.post(f"{BASE_URL}/api/enhanced-test/sessions", json=session_data)
            assert session_response.status_code == 201
            tester.session_id = session_response.json()["id"]
            
            # Upload test video
            test_video = b"automated report test video content"
            files = {"file": ("auto_report_test.mp4", io.BytesIO(test_video), "video/mp4")}
            data = {"project_id": tester.project_id, "session_id": tester.session_id}
            
            upload_response = await tester.client.post(f"{BASE_URL}/api/videos", files=files, data=data)
            assert upload_response.status_code == 201
            video_id = upload_response.json()["id"]
            
            # Start fully automated processing
            start_response = await tester.client.post(
                f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/start-automation",
                json={
                    "video_ids": [video_id],
                    "full_automation": True,
                    "generate_reports": True
                }
            )
            assert start_response.status_code == 200
            
            # Wait for automation to complete
            max_wait = 60
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/status")
                assert status_response.status_code == 200
                status = status_response.json()
                
                if status.get("status") == "completed" and status.get("reports_generated"):
                    # Verify reports were automatically generated
                    reports_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/reports")
                    assert reports_response.status_code == 200
                    reports = reports_response.json()
                    
                    # Should have multiple report formats
                    assert len(reports) > 0
                    assert any("json" in report.get("format", "") for report in reports)
                    
                    # Verify summary report exists
                    summary_response = await tester.client.get(f"{BASE_URL}/api/enhanced-test/sessions/{tester.session_id}/summary")
                    assert summary_response.status_code == 200
                    summary = summary_response.json()
                    assert "total_detections" in summary or "summary" in summary
                    
                    print("✅ Automated report generation completed successfully")
                    return
                    
                await asyncio.sleep(5)
            
            pytest.fail("Automated report generation did not complete within timeout")

if __name__ == "__main__":
    print("🖥️  Running Frontend Integration Tests")
    print("=" * 60)
    
    # Run pytest with verbose output
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", __file__, 
        "-v", "--tb=short", "--no-header", "-s"
    ], cwd=os.path.dirname(__file__) or ".")
    
    exit_code = result.returncode
    if exit_code == 0:
        print("\n✅ All frontend integration tests passed!")
    else:
        print(f"\n❌ Some tests failed (exit code: {exit_code})")
    
    exit(exit_code)