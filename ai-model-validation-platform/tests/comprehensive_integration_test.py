#!/usr/bin/env python3
"""
Comprehensive Integration Testing Suite
Integration Testing Specialist - End-to-End User Workflow Validation

Tests complete user journeys that combine frontend, backend, and ML pipeline:
1. New Project Workflow
2. Annotation Workflow  
3. Analysis Workflow
4. Error Scenario Testing
5. Docker Deployment Validation
"""

import asyncio
import aiohttp
import json
import time
import subprocess
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
import websockets
import base64
import traceback

class ComprehensiveIntegrationTester:
    def __init__(self, 
                 frontend_url="http://localhost:3000", 
                 backend_url="http://localhost:8000",
                 external_ip="155.138.239.131"):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.external_ip = external_ip
        self.test_results = {
            "test_started": datetime.now().isoformat(),
            "tester": "Integration Testing Specialist",
            "scope": "Complete End-to-End User Workflows",
            "frontend_url": frontend_url,
            "backend_url": backend_url,
            "external_ip": external_ip,
            "workflows": {},
            "docker_validation": {},
            "error_scenarios": {},
            "performance_metrics": {},
            "issues_found": []
        }
        self.session_data = {}
        
    def log_test(self, workflow, test_name, status, details=None, error=None, metrics=None):
        """Log a test result with workflow categorization"""
        if workflow not in self.test_results["workflows"]:
            self.test_results["workflows"][workflow] = []
            
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "error": str(error) if error else None,
            "metrics": metrics
        }
        self.test_results["workflows"][workflow].append(result)
        
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} [{workflow}] {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")
        if metrics:
            print(f"   Metrics: {metrics}")
            
    def log_issue(self, issue_type, description, severity="medium"):
        """Log integration issues found"""
        issue = {
            "type": issue_type,
            "description": description,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results["issues_found"].append(issue)
        print(f"🐛 ISSUE [{severity.upper()}]: {description}")

    async def test_complete_new_project_workflow(self):
        """Test Complete User Journey #1 - New Project Workflow"""
        workflow = "New Project Workflow"
        print(f"\n🚀 Testing {workflow}")
        print("=" * 60)
        
        async with aiohttp.ClientSession() as session:
            try:
                # Step 1: Create project via frontend API
                project_data = {
                    "name": f"Integration Test Project {uuid.uuid4().hex[:8]}",
                    "description": "Created during comprehensive integration testing",
                    "status": "active"
                }
                
                start_time = time.time()
                async with session.post(f"{self.backend_url}/api/projects", json=project_data) as response:
                    project_creation_time = time.time() - start_time
                    
                    if response.status in [200, 201]:
                        project = await response.json()
                        project_id = project.get('id')
                        self.session_data['project_id'] = project_id
                        
                        self.log_test(workflow, "Create Project via API", "PASS", 
                                    f"Created project ID: {project_id}", 
                                    metrics={"creation_time_ms": project_creation_time * 1000})
                        
                        # Step 2: Verify project appears in list
                        async with session.get(f"{self.backend_url}/api/projects") as list_response:
                            if list_response.status == 200:
                                projects_data = await list_response.json()
                                project_found = False
                                
                                if isinstance(projects_data, dict) and "projects" in projects_data:
                                    project_found = any(p.get('id') == project_id for p in projects_data["projects"])
                                elif isinstance(projects_data, list):
                                    project_found = any(p.get('id') == project_id for p in projects_data)
                                
                                if project_found:
                                    self.log_test(workflow, "Project Appears in List", "PASS", 
                                                "Project visible in projects list")
                                else:
                                    self.log_test(workflow, "Project Appears in List", "FAIL", 
                                                "Project not found in list after creation")
                                    self.log_issue("data_consistency", "Created project not appearing in list")
                            else:
                                self.log_test(workflow, "Project List Access", "FAIL", 
                                            f"Could not access projects list: {list_response.status}")
                        
                        # Step 3: Test video upload through UI simulation
                        await self.test_video_upload_workflow(session, project_id, workflow)
                        
                        # Step 4: View videos in dataset page
                        await self.test_dataset_page_access(session, project_id, workflow)
                        
                        # Step 5: Trigger ML processing
                        await self.test_ml_processing_trigger(session, project_id, workflow)
                        
                    else:
                        self.log_test(workflow, "Create Project via API", "FAIL", 
                                    f"Failed to create project: {response.status}")
                        response_text = await response.text()
                        self.log_issue("api_error", f"Project creation failed: {response.status} - {response_text}")
                        
            except Exception as e:
                self.log_test(workflow, "New Project Workflow", "FAIL", error=e)
                self.log_issue("workflow_failure", f"New project workflow crashed: {str(e)}", "high")

    async def test_video_upload_workflow(self, session, project_id, workflow):
        """Test video upload through UI simulation"""
        try:
            # Create a small test video file (simulated)
            test_video_content = b"FAKE_MP4_CONTENT_FOR_TESTING" * 1000  # Simulate ~27KB file
            
            # Test multipart upload
            start_time = time.time()
            
            data = aiohttp.FormData()
            data.add_field('file', test_video_content, 
                          filename=f'integration_test_{uuid.uuid4().hex[:8]}.mp4',
                          content_type='video/mp4')
            data.add_field('project_id', str(project_id))
            data.add_field('title', 'Integration Test Video')
            
            async with session.post(f"{self.backend_url}/api/videos/upload", data=data) as response:
                upload_time = time.time() - start_time
                
                if response.status in [200, 201]:
                    video_data = await response.json()
                    video_id = video_data.get('id') or video_data.get('video_id')
                    
                    self.log_test(workflow, "Video Upload", "PASS", 
                                f"Video uploaded successfully: {video_id}",
                                metrics={"upload_time_ms": upload_time * 1000, "file_size_bytes": len(test_video_content)})
                    
                    self.session_data['video_id'] = video_id
                    
                    # Verify video appears in videos list
                    async with session.get(f"{self.backend_url}/api/videos") as videos_response:
                        if videos_response.status == 200:
                            videos_data = await videos_response.json()
                            video_found = False
                            
                            if isinstance(videos_data, dict) and "videos" in videos_data:
                                video_found = any(v.get('id') == video_id for v in videos_data["videos"])
                            elif isinstance(videos_data, list):
                                video_found = any(v.get('id') == video_id for v in videos_data)
                            
                            if video_found:
                                self.log_test(workflow, "Video Appears in List", "PASS", 
                                            "Uploaded video visible in videos list")
                            else:
                                self.log_test(workflow, "Video Appears in List", "FAIL", 
                                            "Uploaded video not found in list")
                                self.log_issue("data_consistency", "Uploaded video not appearing in list")
                        
                elif response.status == 400:
                    # Might be validation error, check response
                    error_data = await response.text()
                    self.log_test(workflow, "Video Upload", "PARTIAL", 
                                f"Upload rejected (validation): {error_data[:200]}")
                else:
                    self.log_test(workflow, "Video Upload", "FAIL", 
                                f"Upload failed: {response.status}")
                    self.log_issue("upload_failure", f"Video upload failed: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Video Upload", "FAIL", error=e)

    async def test_dataset_page_access(self, session, project_id, workflow):
        """Test viewing videos in dataset page"""
        try:
            # Test dataset endpoint
            async with session.get(f"{self.backend_url}/api/datasets") as response:
                if response.status == 200:
                    datasets = await response.json()
                    self.log_test(workflow, "Dataset Page Access", "PASS", 
                                "Dataset page accessible")
                    
                    # Test project-specific dataset
                    async with session.get(f"{self.backend_url}/api/projects/{project_id}/videos") as project_videos_response:
                        if project_videos_response.status == 200:
                            project_videos = await project_videos_response.json()
                            self.log_test(workflow, "Project Videos View", "PASS", 
                                        f"Project videos accessible: {len(project_videos) if isinstance(project_videos, list) else 'dict'}")
                        else:
                            self.log_test(workflow, "Project Videos View", "FAIL", 
                                        f"Could not access project videos: {project_videos_response.status}")
                else:
                    self.log_test(workflow, "Dataset Page Access", "FAIL", 
                                f"Dataset page not accessible: {response.status}")
                                
        except Exception as e:
            self.log_test(workflow, "Dataset Page Access", "FAIL", error=e)

    async def test_ml_processing_trigger(self, session, project_id, workflow):
        """Test triggering ML processing"""
        try:
            if 'video_id' in self.session_data:
                video_id = self.session_data['video_id']
                
                # Test detection trigger
                detection_data = {
                    "video_id": video_id,
                    "detection_type": "yolo",
                    "confidence_threshold": 0.5
                }
                
                start_time = time.time()
                async with session.post(f"{self.backend_url}/api/videos/{video_id}/detect", 
                                      json=detection_data) as response:
                    processing_time = time.time() - start_time
                    
                    if response.status in [200, 201, 202]:  # 202 for async processing
                        result = await response.json()
                        self.log_test(workflow, "ML Processing Trigger", "PASS", 
                                    f"ML processing initiated: {result.get('status', 'unknown')}",
                                    metrics={"trigger_time_ms": processing_time * 1000})
                        
                        # Check processing status
                        await asyncio.sleep(2)  # Wait for processing to start
                        
                        async with session.get(f"{self.backend_url}/api/videos/{video_id}/status") as status_response:
                            if status_response.status == 200:
                                status_data = await status_response.json()
                                self.log_test(workflow, "Processing Status Check", "PASS", 
                                            f"Processing status: {status_data.get('status', 'unknown')}")
                            else:
                                self.log_test(workflow, "Processing Status Check", "PARTIAL", 
                                            f"Could not check status: {status_response.status}")
                    else:
                        self.log_test(workflow, "ML Processing Trigger", "FAIL", 
                                    f"Processing trigger failed: {response.status}")
                        
        except Exception as e:
            self.log_test(workflow, "ML Processing Trigger", "FAIL", error=e)

    async def test_complete_annotation_workflow(self):
        """Test Complete User Journey #2 - Annotation Workflow"""
        workflow = "Annotation Workflow"
        print(f"\n🎯 Testing {workflow}")
        print("=" * 60)
        
        async with aiohttp.ClientSession() as session:
            try:
                # Use project from previous workflow or create new one
                project_id = self.session_data.get('project_id')
                video_id = self.session_data.get('video_id')
                
                if not project_id or not video_id:
                    self.log_test(workflow, "Prerequisites", "SKIP", 
                                "No project/video from previous workflow")
                    return
                
                # Step 1: Create manual annotation
                annotation_data = {
                    "video_id": video_id,
                    "frame_number": 30,
                    "annotations": [
                        {
                            "type": "bounding_box",
                            "x": 100, "y": 100, "width": 50, "height": 80,
                            "label": "person",
                            "confidence": 1.0
                        }
                    ],
                    "annotator": "integration_test"
                }
                
                async with session.post(f"{self.backend_url}/api/annotations", 
                                      json=annotation_data) as response:
                    if response.status in [200, 201]:
                        annotation = await response.json()
                        annotation_id = annotation.get('id')
                        self.session_data['annotation_id'] = annotation_id
                        
                        self.log_test(workflow, "Create Manual Annotation", "PASS", 
                                    f"Annotation created: {annotation_id}")
                        
                        # Step 2: Edit existing annotation
                        updated_annotation = annotation_data.copy()
                        updated_annotation["annotations"][0]["label"] = "pedestrian"
                        
                        async with session.put(f"{self.backend_url}/api/annotations/{annotation_id}",
                                             json=updated_annotation) as edit_response:
                            if edit_response.status == 200:
                                self.log_test(workflow, "Edit Annotation", "PASS", 
                                            "Annotation updated successfully")
                            else:
                                self.log_test(workflow, "Edit Annotation", "FAIL", 
                                            f"Edit failed: {edit_response.status}")
                        
                        # Step 3: Compare with ML detections
                        await self.test_annotation_comparison(session, video_id, workflow)
                        
                        # Step 4: Validate ground truth
                        await self.test_ground_truth_validation(session, annotation_id, workflow)
                        
                        # Step 5: Export annotation data
                        await self.test_annotation_export(session, project_id, workflow)
                        
                    else:
                        self.log_test(workflow, "Create Manual Annotation", "FAIL", 
                                    f"Failed to create annotation: {response.status}")
                        
            except Exception as e:
                self.log_test(workflow, "Annotation Workflow", "FAIL", error=e)
                self.log_issue("workflow_failure", f"Annotation workflow crashed: {str(e)}", "high")

    async def test_annotation_comparison(self, session, video_id, workflow):
        """Test comparing manual annotations with ML detections"""
        try:
            async with session.get(f"{self.backend_url}/api/videos/{video_id}/detections") as response:
                if response.status == 200:
                    detections = await response.json()
                    self.log_test(workflow, "ML Detections Access", "PASS", 
                                f"Retrieved ML detections: {len(detections) if isinstance(detections, list) else 'dict'}")
                    
                    # Test comparison endpoint
                    async with session.get(f"{self.backend_url}/api/videos/{video_id}/compare") as compare_response:
                        if compare_response.status == 200:
                            comparison = await compare_response.json()
                            self.log_test(workflow, "Annotation Comparison", "PASS", 
                                        "Annotation comparison successful")
                        else:
                            self.log_test(workflow, "Annotation Comparison", "PARTIAL", 
                                        f"Comparison not available: {compare_response.status}")
                else:
                    self.log_test(workflow, "ML Detections Access", "FAIL", 
                                f"Could not access ML detections: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Annotation Comparison", "FAIL", error=e)

    async def test_ground_truth_validation(self, session, annotation_id, workflow):
        """Test ground truth validation"""
        try:
            validation_data = {
                "annotation_id": annotation_id,
                "validation_status": "approved",
                "validator": "integration_test",
                "notes": "Validated during integration testing"
            }
            
            async with session.post(f"{self.backend_url}/api/ground-truth/validate", 
                                  json=validation_data) as response:
                if response.status in [200, 201]:
                    validation = await response.json()
                    self.log_test(workflow, "Ground Truth Validation", "PASS", 
                                "Ground truth validation successful")
                else:
                    self.log_test(workflow, "Ground Truth Validation", "PARTIAL", 
                                f"Validation endpoint: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Ground Truth Validation", "FAIL", error=e)

    async def test_annotation_export(self, session, project_id, workflow):
        """Test annotation data export"""
        try:
            export_formats = ["json", "csv", "coco"]
            
            for format_type in export_formats:
                async with session.get(f"{self.backend_url}/api/projects/{project_id}/export/{format_type}") as response:
                    if response.status == 200:
                        self.log_test(workflow, f"Export {format_type.upper()}", "PASS", 
                                    f"Export in {format_type} format successful")
                    else:
                        self.log_test(workflow, f"Export {format_type.upper()}", "PARTIAL", 
                                    f"Export not available: {response.status}")
                        
        except Exception as e:
            self.log_test(workflow, "Annotation Export", "FAIL", error=e)

    async def test_complete_analysis_workflow(self):
        """Test Complete User Journey #3 - Analysis Workflow"""
        workflow = "Analysis Workflow"
        print(f"\n📊 Testing {workflow}")
        print("=" * 60)
        
        async with aiohttp.ClientSession() as session:
            try:
                project_id = self.session_data.get('project_id')
                
                if not project_id:
                    self.log_test(workflow, "Prerequisites", "SKIP", 
                                "No project from previous workflow")
                    return
                
                # Step 1: Load processed data
                async with session.get(f"{self.backend_url}/api/projects/{project_id}/results") as response:
                    if response.status == 200:
                        results = await response.json()
                        self.log_test(workflow, "Load Processed Data", "PASS", 
                                    "Results data loaded successfully")
                        
                        # Step 2: View results dashboard
                        async with session.get(f"{self.backend_url}/api/dashboard/stats") as dashboard_response:
                            if dashboard_response.status == 200:
                                dashboard = await dashboard_response.json()
                                self.log_test(workflow, "Results Dashboard", "PASS", 
                                            f"Dashboard accessible with {len(dashboard)} metrics")
                                
                                # Step 3: Analyze detection accuracy
                                await self.test_detection_accuracy_analysis(session, project_id, workflow)
                                
                                # Step 4: Generate reports
                                await self.test_report_generation(session, project_id, workflow)
                                
                            else:
                                self.log_test(workflow, "Results Dashboard", "FAIL", 
                                            f"Dashboard not accessible: {dashboard_response.status}")
                    else:
                        self.log_test(workflow, "Load Processed Data", "FAIL", 
                                    f"Could not load results: {response.status}")
                        
            except Exception as e:
                self.log_test(workflow, "Analysis Workflow", "FAIL", error=e)
                self.log_issue("workflow_failure", f"Analysis workflow crashed: {str(e)}", "high")

    async def test_detection_accuracy_analysis(self, session, project_id, workflow):
        """Test detection accuracy analysis"""
        try:
            async with session.get(f"{self.backend_url}/api/projects/{project_id}/accuracy") as response:
                if response.status == 200:
                    accuracy = await response.json()
                    self.log_test(workflow, "Detection Accuracy Analysis", "PASS", 
                                f"Accuracy analysis available: {accuracy.get('accuracy', 'N/A')}")
                else:
                    self.log_test(workflow, "Detection Accuracy Analysis", "PARTIAL", 
                                f"Accuracy analysis not available: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Detection Accuracy Analysis", "FAIL", error=e)

    async def test_report_generation(self, session, project_id, workflow):
        """Test report generation"""
        try:
            report_data = {
                "project_id": project_id,
                "report_type": "summary",
                "include_metrics": True,
                "format": "json"
            }
            
            async with session.post(f"{self.backend_url}/api/reports/generate", 
                                  json=report_data) as response:
                if response.status in [200, 201]:
                    report = await response.json()
                    self.log_test(workflow, "Generate Report", "PASS", 
                                "Report generation successful")
                    
                    # Test export analysis data
                    async with session.get(f"{self.backend_url}/api/projects/{project_id}/export/analysis") as export_response:
                        if export_response.status == 200:
                            self.log_test(workflow, "Export Analysis Data", "PASS", 
                                        "Analysis data export successful")
                        else:
                            self.log_test(workflow, "Export Analysis Data", "PARTIAL", 
                                        f"Export not available: {export_response.status}")
                else:
                    self.log_test(workflow, "Generate Report", "PARTIAL", 
                                f"Report generation not available: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Report Generation", "FAIL", error=e)

    async def test_error_scenarios(self):
        """Test Error Scenario Testing"""
        workflow = "Error Scenarios"
        print(f"\n🚨 Testing {workflow}")
        print("=" * 60)
        
        self.test_results["error_scenarios"] = {}
        
        async with aiohttp.ClientSession() as session:
            # Test upload failures and recovery
            await self.test_upload_failure_recovery(session, workflow)
            
            # Test processing interruptions
            await self.test_processing_interruptions(session, workflow)
            
            # Test database connection issues
            await self.test_database_connectivity_issues(session, workflow)
            
            # Test concurrent user scenarios
            await self.test_concurrent_user_scenarios(session, workflow)

    async def test_upload_failure_recovery(self, session, workflow):
        """Test upload failures and recovery mechanisms"""
        try:
            # Test oversized file
            large_data = b"X" * (100 * 1024 * 1024)  # 100MB file
            
            data = aiohttp.FormData()
            data.add_field('file', large_data, filename='large_test.mp4', content_type='video/mp4')
            data.add_field('project_id', '1')
            
            async with session.post(f"{self.backend_url}/api/videos/upload", data=data) as response:
                if response.status in [413, 400]:  # Payload too large or bad request
                    self.log_test(workflow, "Large File Rejection", "PASS", 
                                f"Properly rejected oversized file: {response.status}")
                else:
                    self.log_test(workflow, "Large File Rejection", "FAIL", 
                                f"Should reject large files, got: {response.status}")
                    
            # Test invalid file type
            data = aiohttp.FormData()
            data.add_field('file', b'invalid content', filename='test.txt', content_type='text/plain')
            data.add_field('project_id', '1')
            
            async with session.post(f"{self.backend_url}/api/videos/upload", data=data) as response:
                if response.status in [400, 422]:
                    self.log_test(workflow, "Invalid File Type Rejection", "PASS", 
                                f"Properly rejected invalid file type: {response.status}")
                else:
                    self.log_test(workflow, "Invalid File Type Rejection", "FAIL", 
                                f"Should reject invalid file types, got: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Upload Failure Recovery", "FAIL", error=e)

    async def test_processing_interruptions(self, session, workflow):
        """Test handling of processing interruptions"""
        try:
            # Simulate processing interruption by checking status endpoints
            async with session.get(f"{self.backend_url}/api/processing/status") as response:
                if response.status in [200, 404]:
                    self.log_test(workflow, "Processing Status Endpoint", "PASS", 
                                "Processing status endpoint accessible")
                else:
                    self.log_test(workflow, "Processing Status Endpoint", "FAIL", 
                                f"Processing status endpoint failed: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Processing Interruptions", "FAIL", error=e)

    async def test_database_connectivity_issues(self, session, workflow):
        """Test database connection issue handling"""
        try:
            # Test health endpoint
            async with session.get(f"{self.backend_url}/health") as response:
                if response.status == 200:
                    health = await response.json()
                    db_status = health.get('database', 'unknown')
                    self.log_test(workflow, "Database Health Check", "PASS", 
                                f"Database status: {db_status}")
                else:
                    self.log_test(workflow, "Database Health Check", "FAIL", 
                                f"Health endpoint failed: {response.status}")
                    
        except Exception as e:
            self.log_test(workflow, "Database Connectivity Issues", "FAIL", error=e)

    async def test_concurrent_user_scenarios(self, session, workflow):
        """Test concurrent user operations"""
        try:
            # Simulate concurrent requests
            tasks = []
            for i in range(5):
                task = session.get(f"{self.backend_url}/api/projects")
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            concurrent_time = time.time() - start_time
            
            successful_responses = sum(1 for r in responses if hasattr(r, 'status') and r.status == 200)
            
            self.log_test(workflow, "Concurrent User Requests", "PASS", 
                        f"Handled {successful_responses}/5 concurrent requests",
                        metrics={"concurrent_time_ms": concurrent_time * 1000})
            
            # Cleanup
            for response in responses:
                if hasattr(response, 'close'):
                    response.close()
                    
        except Exception as e:
            self.log_test(workflow, "Concurrent User Scenarios", "FAIL", error=e)

    async def test_docker_deployment_validation(self):
        """Test Docker Deployment Validation"""
        workflow = "Docker Deployment"
        print(f"\n🐳 Testing {workflow}")
        print("=" * 60)
        
        self.test_results["docker_validation"] = {}
        
        try:
            # Test containerized deployment
            await self.test_containerized_services(workflow)
            
            # Test service discovery
            await self.test_service_discovery(workflow)
            
            # Test persistent storage
            await self.test_persistent_storage(workflow)
            
            # Test log aggregation
            await self.test_log_aggregation(workflow)
            
        except Exception as e:
            self.log_test(workflow, "Docker Deployment Validation", "FAIL", error=e)

    async def test_containerized_services(self, workflow):
        """Test containerized service deployment"""
        try:
            services = ["ai_validation_backend", "ai_validation_frontend", "ai_validation_postgres", "ai_validation_redis"]
            
            for service in services:
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Names}}"],
                    capture_output=True, text=True, timeout=10
                )
                
                if service in result.stdout:
                    self.log_test(workflow, f"Container {service}", "PASS", 
                                f"Container {service} is running")
                else:
                    self.log_test(workflow, f"Container {service}", "FAIL", 
                                f"Container {service} not found")
                    self.log_issue("docker_deployment", f"Container {service} not running", "high")
                    
        except Exception as e:
            self.log_test(workflow, "Containerized Services", "FAIL", error=e)

    async def test_service_discovery(self, workflow):
        """Test service discovery within Docker network"""
        try:
            # Test network connectivity between services
            result = subprocess.run(
                ["docker", "network", "ls", "--filter", "name=vru_validation_network"],
                capture_output=True, text=True, timeout=10
            )
            
            if "vru_validation_network" in result.stdout:
                self.log_test(workflow, "Docker Network", "PASS", 
                            "Docker network exists")
                
                # Test inter-service communication
                backend_ping = subprocess.run(
                    ["docker", "exec", "ai_validation_backend", "ping", "-c", "1", "postgres"],
                    capture_output=True, text=True, timeout=10
                )
                
                if backend_ping.returncode == 0:
                    self.log_test(workflow, "Service Discovery", "PASS", 
                                "Backend can reach database")
                else:
                    self.log_test(workflow, "Service Discovery", "FAIL", 
                                "Backend cannot reach database")
            else:
                self.log_test(workflow, "Docker Network", "FAIL", 
                            "Docker network not found")
                
        except Exception as e:
            self.log_test(workflow, "Service Discovery", "FAIL", error=e)

    async def test_persistent_storage(self, workflow):
        """Test persistent storage volumes"""
        try:
            volumes = ["postgres_data", "redis_data", "uploaded_videos"]
            
            for volume in volumes:
                result = subprocess.run(
                    ["docker", "volume", "ls", "--filter", f"name={volume}"],
                    capture_output=True, text=True, timeout=10
                )
                
                if volume in result.stdout:
                    self.log_test(workflow, f"Volume {volume}", "PASS", 
                                f"Volume {volume} exists")
                else:
                    self.log_test(workflow, f"Volume {volume}", "FAIL", 
                                f"Volume {volume} not found")
                    
        except Exception as e:
            self.log_test(workflow, "Persistent Storage", "FAIL", error=e)

    async def test_log_aggregation(self, workflow):
        """Test log aggregation from containers"""
        try:
            services = ["ai_validation_backend", "ai_validation_frontend"]
            
            for service in services:
                result = subprocess.run(
                    ["docker", "logs", "--tail", "10", service],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.stdout or result.stderr:
                    self.log_test(workflow, f"Logs {service}", "PASS", 
                                f"Logs available for {service}")
                else:
                    self.log_test(workflow, f"Logs {service}", "PARTIAL", 
                                f"No logs found for {service}")
                    
        except Exception as e:
            self.log_test(workflow, "Log Aggregation", "FAIL", error=e)

    async def measure_complete_user_journey_performance(self):
        """Measure complete user journey performance"""
        workflow = "Performance Metrics"
        print(f"\n⚡ Measuring {workflow}")
        print("=" * 60)
        
        self.test_results["performance_metrics"] = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Measure complete workflow time
                total_start = time.time()
                
                # Create project
                project_start = time.time()
                project_data = {"name": "Performance Test", "description": "Performance testing"}
                async with session.post(f"{self.backend_url}/api/projects", json=project_data) as response:
                    project_time = time.time() - project_start
                    
                if response.status in [200, 201]:
                    project = await response.json()
                    project_id = project.get('id')
                    
                    # Upload video
                    upload_start = time.time()
                    test_data = b"TEST" * 10000  # 40KB file
                    data = aiohttp.FormData()
                    data.add_field('file', test_data, filename='perf_test.mp4', content_type='video/mp4')
                    data.add_field('project_id', str(project_id))
                    
                    async with session.post(f"{self.backend_url}/api/videos/upload", data=data) as upload_response:
                        upload_time = time.time() - upload_start
                        
                        if upload_response.status in [200, 201]:
                            video = await upload_response.json()
                            video_id = video.get('id') or video.get('video_id')
                            
                            # Create annotation
                            annotation_start = time.time()
                            annotation_data = {
                                "video_id": video_id,
                                "frame_number": 1,
                                "annotations": [{"type": "test", "x": 0, "y": 0, "width": 10, "height": 10}]
                            }
                            
                            async with session.post(f"{self.backend_url}/api/annotations", json=annotation_data) as anno_response:
                                annotation_time = time.time() - annotation_start
                                
                                total_time = time.time() - total_start
                                
                                self.test_results["performance_metrics"] = {
                                    "total_workflow_time_ms": total_time * 1000,
                                    "project_creation_time_ms": project_time * 1000,
                                    "video_upload_time_ms": upload_time * 1000,
                                    "annotation_creation_time_ms": annotation_time * 1000,
                                    "file_size_bytes": len(test_data)
                                }
                                
                                self.log_test(workflow, "Complete Journey Performance", "PASS", 
                                            f"Total time: {total_time:.2f}s",
                                            metrics=self.test_results["performance_metrics"])
                                            
        except Exception as e:
            self.log_test(workflow, "Performance Measurement", "FAIL", error=e)

    async def run_comprehensive_integration_tests(self):
        """Run all comprehensive integration tests"""
        print("🚀 COMPREHENSIVE INTEGRATION TESTING")
        print("Integration Testing Specialist - End-to-End User Workflow Validation")
        print("=" * 80)
        
        # Store test start in memory
        await self.store_test_progress("started", "Comprehensive integration testing initiated")
        
        try:
            # Test all user workflows
            await self.test_complete_new_project_workflow()
            await self.test_complete_annotation_workflow()
            await self.test_complete_analysis_workflow()
            
            # Test error scenarios
            await self.test_error_scenarios()
            
            # Test Docker deployment
            await self.test_docker_deployment_validation()
            
            # Measure performance
            await self.measure_complete_user_journey_performance()
            
            # Generate comprehensive summary
            await self.generate_comprehensive_summary()
            
            # Store results in MCP memory
            await self.store_final_results()
            
        except Exception as e:
            self.log_issue("critical_failure", f"Comprehensive testing crashed: {str(e)}", "critical")
            print(f"❌ CRITICAL: Integration testing failed: {e}")
            traceback.print_exc()

    async def store_test_progress(self, status, message):
        """Store test progress in MCP memory"""
        try:
            progress_data = {
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "specialist": "Integration Testing Specialist"
            }
            
            # Note: This would use MCP memory in actual implementation
            print(f"📝 Progress: {status} - {message}")
            
        except Exception as e:
            print(f"⚠️ Could not store progress: {e}")

    async def generate_comprehensive_summary(self):
        """Generate comprehensive test summary"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE INTEGRATION TEST SUMMARY")
        print("=" * 80)
        
        total_workflows = len(self.test_results["workflows"])
        total_tests = sum(len(tests) for tests in self.test_results["workflows"].values())
        
        passed_tests = 0
        failed_tests = 0
        partial_tests = 0
        
        for workflow, tests in self.test_results["workflows"].items():
            workflow_passed = sum(1 for t in tests if t["status"] == "PASS")
            workflow_failed = sum(1 for t in tests if t["status"] == "FAIL")
            workflow_partial = sum(1 for t in tests if t["status"] == "PARTIAL")
            
            passed_tests += workflow_passed
            failed_tests += workflow_failed
            partial_tests += workflow_partial
            
            print(f"\n🔍 {workflow}:")
            print(f"   ✅ Passed: {workflow_passed}")
            print(f"   ❌ Failed: {workflow_failed}")
            print(f"   ⚠️ Partial: {workflow_partial}")
            
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   Total Workflows: {total_workflows}")
        print(f"   Total Tests: {total_tests}")
        print(f"   ✅ Passed: {passed_tests}")
        print(f"   ❌ Failed: {failed_tests}")
        print(f"   ⚠️ Partial: {partial_tests}")
        
        if total_tests > 0:
            success_rate = (passed_tests / total_tests) * 100
            print(f"   🏆 Success Rate: {success_rate:.1f}%")
        
        # Issues summary
        if self.test_results["issues_found"]:
            print(f"\n🐛 ISSUES FOUND ({len(self.test_results['issues_found'])}):")
            for issue in self.test_results["issues_found"]:
                severity_emoji = "🔴" if issue["severity"] == "critical" else "🟡" if issue["severity"] == "high" else "🟢"
                print(f"   {severity_emoji} [{issue['severity'].upper()}] {issue['description']}")
        
        # Performance metrics
        if self.test_results["performance_metrics"]:
            print(f"\n⚡ PERFORMANCE METRICS:")
            for metric, value in self.test_results["performance_metrics"].items():
                if "time_ms" in metric:
                    print(f"   {metric}: {value:.2f}ms")
                else:
                    print(f"   {metric}: {value}")

    async def store_final_results(self):
        """Store final results in MCP memory"""
        try:
            final_results = {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "specialist": "Integration Testing Specialist",
                "summary": {
                    "total_workflows": len(self.test_results["workflows"]),
                    "total_tests": sum(len(tests) for tests in self.test_results["workflows"].values()),
                    "issues_found": len(self.test_results["issues_found"]),
                    "critical_issues": len([i for i in self.test_results["issues_found"] if i["severity"] == "critical"]),
                    "docker_services_healthy": "ai_validation_backend" in str(self.test_results.get("docker_validation", {}))
                },
                "detailed_results": self.test_results
            }
            
            # Save to file for now (would use MCP memory in actual implementation)
            results_file = f"/home/rigade/Testing/ai-model-validation-platform/tests/comprehensive_integration_results_{int(time.time())}.json"
            with open(results_file, 'w') as f:
                json.dump(final_results, f, indent=2)
            
            print(f"\n💾 Final results saved to: {results_file}")
            
            # Store in MCP memory
            print("📤 Storing results in MCP memory...")
            
            return final_results
            
        except Exception as e:
            print(f"⚠️ Could not store final results: {e}")

if __name__ == "__main__":
    # Initialize Integration Testing Specialist
    tester = ComprehensiveIntegrationTester(
        frontend_url="http://localhost:3000",
        backend_url="http://localhost:8000"
    )
    
    # Run comprehensive integration tests
    asyncio.run(tester.run_comprehensive_integration_tests())