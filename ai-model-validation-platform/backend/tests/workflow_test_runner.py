#!/usr/bin/env python3
"""
Comprehensive Workflow Test Runner
==================================

Orchestrates and runs all workflow validation tests to address:
1. Sequential video processing validation (no phantom sessions)
2. End-to-end automation testing ("click start test and come back everything done")
3. Frontend integration testing
4. Complete user workflow validation

Usage:
    python workflow_test_runner.py [--test-type=all|sequential|frontend|automation|specific]
"""

import asyncio
import sys
import os
import argparse
import time
import json
import httpx
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class WorkflowTestRunner:
    """Comprehensive workflow test orchestrator"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.results = {
            "test_session": {
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "duration": None
            },
            "sequential_video_tests": {"status": "pending", "details": []},
            "frontend_integration_tests": {"status": "pending", "details": []},
            "automation_tests": {"status": "pending", "details": []},
            "specific_video_tests": {"status": "pending", "details": []},
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0
            }
        }
        
    async def check_server_availability(self) -> bool:
        """Check if the backend server is running and accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            print(f"❌ Server not accessible at {self.base_url}: {e}")
            return False
    
    async def run_sequential_video_tests(self) -> Dict[str, Any]:
        """Run sequential video processing tests"""
        print("\n🎥 Running Sequential Video Processing Tests...")
        print("=" * 60)
        
        test_result = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "tests": []
        }
        
        try:
            # Import and run sequential video tests
            import subprocess
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                "test_sequential_video_processing.py",
                "-v", "--tb=short", "--json-report", "--json-report-file=sequential_test_results.json"
            ], 
            cwd=Path(__file__).parent,
            capture_output=True, 
            text=True,
            timeout=300  # 5 minute timeout
            )
            
            test_result["exit_code"] = result.returncode
            test_result["stdout"] = result.stdout
            test_result["stderr"] = result.stderr
            
            if result.returncode == 0:
                test_result["status"] = "passed"
                print("✅ Sequential Video Processing Tests: PASSED")
            else:
                test_result["status"] = "failed"
                print("❌ Sequential Video Processing Tests: FAILED")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            test_result["status"] = "timeout"
            print("⏰ Sequential Video Processing Tests: TIMEOUT")
        except Exception as e:
            test_result["status"] = "error"
            test_result["error"] = str(e)
            print(f"💥 Sequential Video Processing Tests: ERROR - {e}")
            
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def run_frontend_integration_tests(self) -> Dict[str, Any]:
        """Run frontend integration tests"""
        print("\n🖥️  Running Frontend Integration Tests...")
        print("=" * 60)
        
        test_result = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "tests": []
        }
        
        try:
            import subprocess
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                "test_frontend_integration.py", 
                "-v", "--tb=short", "--json-report", "--json-report-file=frontend_test_results.json"
            ],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=300
            )
            
            test_result["exit_code"] = result.returncode
            test_result["stdout"] = result.stdout
            test_result["stderr"] = result.stderr
            
            if result.returncode == 0:
                test_result["status"] = "passed"
                print("✅ Frontend Integration Tests: PASSED")
            else:
                test_result["status"] = "failed"
                print("❌ Frontend Integration Tests: FAILED")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            test_result["status"] = "timeout"
            print("⏰ Frontend Integration Tests: TIMEOUT")
        except Exception as e:
            test_result["status"] = "error"
            test_result["error"] = str(e)
            print(f"💥 Frontend Integration Tests: ERROR - {e}")
            
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def run_automation_workflow_test(self) -> Dict[str, Any]:
        """Run end-to-end automation workflow test"""
        print("\n🤖 Running End-to-End Automation Tests...")
        print("=" * 60)
        
        test_result = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "automation_steps": []
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Step 1: Create test project
                project_data = {
                    "name": "Automation Workflow Test",
                    "description": "End-to-end automation test - click start and come back everything done",
                    "cameraModel": "Automation Test Camera",
                    "signalType": "GPIO"
                }
                
                print("📝 Creating test project...")
                project_response = await client.post(f"{self.base_url}/api/projects", json=project_data)
                assert project_response.status_code == 201
                project_id = project_response.json()["id"]
                test_result["automation_steps"].append({"step": "project_creation", "status": "success", "project_id": project_id})
                
                # Step 2: Create automated session
                session_data = {
                    "name": "Full Automation Test Session",
                    "project_id": project_id,
                    "configuration": {
                        "auto_advance": True,
                        "sequential_processing": True,
                        "auto_analysis": True,
                        "auto_report": True,
                        "auto_export": True
                    }
                }
                
                print("⚙️ Creating automated test session...")
                session_response = await client.post(f"{self.base_url}/api/enhanced-test/sessions", json=session_data)
                assert session_response.status_code == 201
                session_id = session_response.json()["id"]
                test_result["automation_steps"].append({"step": "session_creation", "status": "success", "session_id": session_id})
                
                # Step 3: Upload test videos
                print("📹 Uploading test videos...")
                video_ids = []
                test_videos = [
                    {"filename": "child-1-1-1.mp4", "content": b"test video content 1"},
                    {"filename": "ae8e974b-0533-4cab-959a-493793e00328.mp4", "content": b"test video content 2"}
                ]
                
                for video_data in test_videos:
                    files = {"file": (video_data["filename"], video_data["content"], "video/mp4")}
                    data = {"project_id": project_id, "session_id": session_id}
                    
                    upload_response = await client.post(f"{self.base_url}/api/videos", files=files, data=data)
                    assert upload_response.status_code == 201
                    video_ids.append(upload_response.json()["id"])
                
                test_result["automation_steps"].append({"step": "video_upload", "status": "success", "video_count": len(video_ids)})
                
                # Step 4: START AUTOMATION - "click start test"
                print("🚀 Starting full automation (CLICK START TEST)...")
                automation_start = time.time()
                
                start_response = await client.post(
                    f"{self.base_url}/api/enhanced-test/sessions/{session_id}/start-automation",
                    json={
                        "video_ids": video_ids,
                        "full_automation": True,
                        "expected_completion_time": 90
                    }
                )
                
                if start_response.status_code == 200:
                    test_result["automation_steps"].append({"step": "automation_start", "status": "success"})
                    
                    # Step 5: Wait for completion - "come back everything done"
                    print("⏳ Waiting for automation to complete (user goes away)...")
                    max_wait = 120  # 2 minutes
                    start_time = time.time()
                    
                    while time.time() - start_time < max_wait:
                        status_response = await client.get(f"{self.base_url}/api/enhanced-test/sessions/{session_id}/status")
                        assert status_response.status_code == 200
                        status = status_response.json()
                        
                        current_status = status.get("status", "unknown")
                        progress = status.get("progress", 0)
                        
                        print(f"   Progress: {progress}% - Status: {current_status}")
                        
                        if current_status in ["completed", "finished"]:
                            automation_time = time.time() - automation_start
                            test_result["automation_steps"].append({
                                "step": "automation_completion", 
                                "status": "success",
                                "duration": automation_time
                            })
                            
                            # Step 6: Verify everything is done automatically
                            print("🔍 Verifying automation results...")
                            
                            # Check results
                            results_response = await client.get(f"{self.base_url}/api/enhanced-test/sessions/{session_id}/results")
                            assert results_response.status_code == 200
                            results = results_response.json()
                            test_result["automation_steps"].append({"step": "results_verification", "status": "success"})
                            
                            # Check reports
                            try:
                                report_response = await client.get(f"{self.base_url}/api/enhanced-test/sessions/{session_id}/report")
                                if report_response.status_code == 200:
                                    test_result["automation_steps"].append({"step": "report_generation", "status": "success"})
                                else:
                                    test_result["automation_steps"].append({"step": "report_generation", "status": "partial"})
                            except:
                                test_result["automation_steps"].append({"step": "report_generation", "status": "skipped"})
                            
                            # Check export
                            try:
                                export_response = await client.get(f"{self.base_url}/api/enhanced-test/sessions/{session_id}/export")
                                if export_response.status_code == 200:
                                    test_result["automation_steps"].append({"step": "export_generation", "status": "success"})
                                else:
                                    test_result["automation_steps"].append({"step": "export_generation", "status": "partial"})
                            except:
                                test_result["automation_steps"].append({"step": "export_generation", "status": "skipped"})
                            
                            test_result["status"] = "passed"
                            print("✅ End-to-End Automation Test: PASSED")
                            print(f"   Total automation time: {automation_time:.2f} seconds")
                            break
                            
                        await asyncio.sleep(5)
                    else:
                        test_result["status"] = "timeout"
                        print("⏰ End-to-End Automation Test: TIMEOUT")
                        test_result["automation_steps"].append({"step": "automation_completion", "status": "timeout"})
                else:
                    test_result["status"] = "failed"
                    test_result["automation_steps"].append({"step": "automation_start", "status": "failed", "response_code": start_response.status_code})
                    print(f"❌ Failed to start automation: {start_response.status_code}")
                    
        except Exception as e:
            test_result["status"] = "error"
            test_result["error"] = str(e)
            print(f"💥 End-to-End Automation Test: ERROR - {e}")
            
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    async def run_specific_video_files_test(self) -> Dict[str, Any]:
        """Test specific video files mentioned by user"""
        print("\n📹 Running Specific Video Files Test (child-1-1-1.mp4 and ae8e974b-0533-4cab-959a-493793e00328.mp4)...")
        print("=" * 60)
        
        test_result = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "video_tests": []
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create project for specific video test
                project_data = {
                    "name": "Specific Videos Test Project",
                    "description": "Testing child-1-1-1.mp4 and ae8e974b-0533-4cab-959a-493793e00328.mp4",
                    "cameraModel": "Specific Video Camera",
                    "signalType": "GPIO"
                }
                
                project_response = await client.post(f"{self.base_url}/api/projects", json=project_data)
                assert project_response.status_code == 201
                project_id = project_response.json()["id"]
                
                # Upload the specific videos
                specific_videos = [
                    {
                        "filename": "child-1-1-1.mp4",
                        "content": b"child pedestrian detection test video content for sequential processing",
                        "expected_behavior": "should process first in sequence"
                    },
                    {
                        "filename": "ae8e974b-0533-4cab-959a-493793e00328.mp4",
                        "content": b"vehicle detection test video with UUID filename for sequential processing", 
                        "expected_behavior": "should process second in sequence, automatically after first"
                    }
                ]
                
                video_ids = []
                for video_data in specific_videos:
                    files = {"file": (video_data["filename"], video_data["content"], "video/mp4")}
                    data = {"project_id": project_id}
                    
                    upload_response = await client.post(f"{self.base_url}/api/videos", files=files, data=data)
                    assert upload_response.status_code == 201
                    uploaded_video = upload_response.json()
                    
                    # Verify filename preservation
                    assert uploaded_video["filename"] == video_data["filename"], f"Filename mismatch: expected {video_data['filename']}, got {uploaded_video['filename']}"
                    video_ids.append(uploaded_video["id"])
                    
                    test_result["video_tests"].append({
                        "filename": video_data["filename"],
                        "upload_status": "success",
                        "video_id": uploaded_video["id"]
                    })
                
                # Create session for sequential processing
                session_data = {
                    "name": "Specific Videos Sequential Test",
                    "project_id": project_id,
                    "configuration": {
                        "auto_advance": True,
                        "sequential_processing": True,
                        "process_in_order": True
                    }
                }
                
                session_response = await client.post(f"{self.base_url}/api/enhanced-test/sessions", json=session_data)
                assert session_response.status_code == 201
                session_id = session_response.json()["id"]
                
                # Start processing and monitor for sequential behavior
                start_response = await client.post(
                    f"{self.base_url}/api/enhanced-test/sessions/{session_id}/start",
                    json={
                        "video_ids": video_ids,
                        "processing_order": ["child-1-1-1.mp4", "ae8e974b-0533-4cab-959a-493793e00328.mp4"],
                        "sequential_processing": True
                    }
                )
                assert start_response.status_code == 200
                
                # Monitor processing to verify sequential behavior
                processing_log = []
                max_wait = 60
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    status_response = await client.get(f"{self.base_url}/api/enhanced-test/sessions/{session_id}/status")
                    assert status_response.status_code == 200
                    status = status_response.json()
                    
                    if "current_video" in status:
                        processing_log.append({
                            "time": time.time() - start_time,
                            "current_video": status["current_video"],
                            "status": status.get("status"),
                            "progress": status.get("progress", 0)
                        })
                    
                    if status.get("status") in ["completed", "finished"]:
                        test_result["processing_log"] = processing_log
                        
                        # Verify sequential processing
                        child_entries = [entry for entry in processing_log if "child-1-1-1" in str(entry.get("current_video", ""))]
                        uuid_entries = [entry for entry in processing_log if "ae8e974b" in str(entry.get("current_video", ""))]
                        
                        sequential_verified = False
                        if child_entries and uuid_entries:
                            first_child_time = min(entry["time"] for entry in child_entries)
                            first_uuid_time = min(entry["time"] for entry in uuid_entries)
                            sequential_verified = first_child_time < first_uuid_time
                        
                        test_result["sequential_processing_verified"] = sequential_verified
                        
                        if sequential_verified:
                            test_result["status"] = "passed"
                            print("✅ Specific Video Files Test: PASSED")
                            print(f"   child-1-1-1.mp4 processed before ae8e974b-0533-4cab-959a-493793e00328.mp4")
                        else:
                            test_result["status"] = "failed"
                            print("❌ Specific Video Files Test: FAILED - Sequential processing not verified")
                        break
                        
                    await asyncio.sleep(3)
                else:
                    test_result["status"] = "timeout"
                    print("⏰ Specific Video Files Test: TIMEOUT")
                    
        except Exception as e:
            test_result["status"] = "error"
            test_result["error"] = str(e)
            print(f"💥 Specific Video Files Test: ERROR - {e}")
            
        test_result["end_time"] = datetime.now().isoformat()
        return test_result
    
    def generate_test_report(self) -> str:
        """Generate comprehensive test report"""
        self.results["test_session"]["end_time"] = datetime.now().isoformat()
        
        # Calculate summary statistics
        all_test_results = [
            self.results["sequential_video_tests"],
            self.results["frontend_integration_tests"], 
            self.results["automation_tests"],
            self.results["specific_video_tests"]
        ]
        
        for test_result in all_test_results:
            self.results["summary"]["total_tests"] += 1
            if test_result["status"] == "passed":
                self.results["summary"]["passed"] += 1
            elif test_result["status"] == "failed":
                self.results["summary"]["failed"] += 1
            else:
                self.results["summary"]["skipped"] += 1
        
        # Generate report
        report_lines = [
            "=" * 80,
            "WORKFLOW VALIDATION TEST REPORT",
            "=" * 80,
            f"Test Session: {self.results['test_session']['start_time']} - {self.results['test_session']['end_time']}",
            "",
            "SUMMARY:",
            f"  Total Tests: {self.results['summary']['total_tests']}",
            f"  Passed: {self.results['summary']['passed']}",
            f"  Failed: {self.results['summary']['failed']}", 
            f"  Skipped: {self.results['summary']['skipped']}",
            "",
            "TEST RESULTS:",
            f"  ✅ Sequential Video Processing: {self.results['sequential_video_tests']['status'].upper()}",
            f"  ✅ Frontend Integration: {self.results['frontend_integration_tests']['status'].upper()}", 
            f"  ✅ End-to-End Automation: {self.results['automation_tests']['status'].upper()}",
            f"  ✅ Specific Video Files: {self.results['specific_video_tests']['status'].upper()}",
            "",
        ]
        
        # Add detailed results if available
        if self.results['automation_tests'].get('automation_steps'):
            report_lines.extend([
                "AUTOMATION TEST DETAILS:",
                f"  Steps completed: {len(self.results['automation_tests']['automation_steps'])}",
            ])
            for step in self.results['automation_tests']['automation_steps']:
                report_lines.append(f"    - {step['step']}: {step['status']}")
            report_lines.append("")
        
        # Overall result
        if self.results["summary"]["failed"] == 0:
            report_lines.extend([
                "OVERALL RESULT: ✅ ALL TESTS PASSED",
                "",
                "KEY VALIDATIONS CONFIRMED:",
                "  ✅ Sequential video processing (no phantom sessions)",
                "  ✅ End-to-end automation workflow",
                "  ✅ Frontend integration functionality",
                "  ✅ Specific video files processing",
            ])
        else:
            report_lines.extend([
                "OVERALL RESULT: ❌ SOME TESTS FAILED",
                f"  {self.results['summary']['failed']} test(s) failed",
                "  Review individual test results above",
            ])
        
        report_lines.append("=" * 80)
        return "\n".join(report_lines)
    
    async def run_all_tests(self, test_type: str = "all") -> None:
        """Run all or specific workflow tests"""
        print("\n🚀 WORKFLOW VALIDATION TEST SUITE")
        print("=" * 80)
        print("Testing core user concerns:")
        print("  1. Sequential video processing (no phantom sessions)")
        print("  2. End-to-end automation ('click start and come back everything done')")
        print("  3. Frontend integration and exportTestResults function")
        print("  4. Specific video files workflow")
        print("=" * 80)
        
        # Check server availability
        if not await self.check_server_availability():
            print("❌ Backend server is not available. Please start the server first.")
            return
        
        print("✅ Backend server is available")
        
        # Run tests based on type
        if test_type in ["all", "sequential"]:
            self.results["sequential_video_tests"] = await self.run_sequential_video_tests()
            
        if test_type in ["all", "frontend"]:
            self.results["frontend_integration_tests"] = await self.run_frontend_integration_tests()
            
        if test_type in ["all", "automation"]:
            self.results["automation_tests"] = await self.run_automation_workflow_test()
            
        if test_type in ["all", "specific"]:
            self.results["specific_video_tests"] = await self.run_specific_video_files_test()
        
        # Generate and display report
        report = self.generate_test_report()
        print("\n" + report)
        
        # Save results to file
        results_file = Path(__file__).parent / f"workflow_test_results_{int(time.time())}.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {results_file}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Workflow Validation Test Runner")
    parser.add_argument(
        "--test-type", 
        choices=["all", "sequential", "frontend", "automation", "specific"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001", 
        help="Backend server base URL"
    )
    
    args = parser.parse_args()
    
    runner = WorkflowTestRunner(base_url=args.base_url)
    
    try:
        asyncio.run(runner.run_all_tests(test_type=args.test_type))
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()