#!/usr/bin/env python3
"""
Complete Sequential Video Processing Test
Tests the full user workflow:
1. ONE button starts ALL videos
2. Sequential processing (video1 → video2 → video3)
3. Results stored for each video
4. Results appear in results page
5. Project-based sessions (no random)
"""

import asyncio
import httpx
import json
import time
import logging
from datetime import datetime
import io
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SequentialWorkflowTester:
    """Complete workflow tester for sequential video processing"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)
        
        # Test data
        self.test_project_id = "66f9c296-ee1e-4e81-b0ba-96d03fdc8c90"  # User's test project
        self.test_videos = [
            {
                "filename": "ae8e974b-0533-4cab-959a-493793e00328.mp4",
                "content": b"Mock video content for UUID-named vehicle detection test",
                "expected_types": ["vehicle", "car"]
            },
            {
                "filename": "child-1-1-1.mp4",
                "content": b"Mock video content for child pedestrian detection test",
                "expected_types": ["child", "pedestrian", "person"]
            },
            {
                "filename": "child-1-1-1.mp4",  # Third video (different ID)
                "content": b"Mock video content for duplicate named child video",
                "expected_types": ["child", "person"]
            }
        ]
        
        self.uploaded_videos = []
        self.session_id = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def test_complete_workflow(self) -> Dict[str, Any]:
        """Test the complete user workflow"""
        print("🚀 Starting Complete Sequential Video Processing Test")
        print("=" * 70)
        
        results = {
            "test_started": datetime.utcnow().isoformat(),
            "steps": {},
            "overall_success": False,
            "errors": []
        }
        
        try:
            # Step 1: Verify project exists
            print("\n📁 Step 1: Verifying test project exists...")
            project_exists = await self._verify_project_exists()
            results["steps"]["project_verification"] = {
                "success": project_exists,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not project_exists:
                # Create project if it doesn't exist
                print("   Creating test project...")
                project_created = await self._create_test_project()
                if not project_created:
                    raise Exception("Failed to create test project")
            
            # Step 2: Upload test videos
            print("\n📤 Step 2: Uploading test videos...")
            upload_success = await self._upload_test_videos()
            results["steps"]["video_upload"] = {
                "success": upload_success,
                "videos_uploaded": len(self.uploaded_videos),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not upload_success:
                raise Exception("Failed to upload test videos")
            
            # Step 3: Start sequential processing (ONE BUTTON)
            print("\n🎬 Step 3: Starting sequential video processing...")
            processing_started = await self._start_sequential_processing()
            results["steps"]["processing_start"] = {
                "success": processing_started,
                "session_id": self.session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not processing_started:
                raise Exception("Failed to start sequential processing")
            
            # Step 4: Monitor processing progress
            print("\n⏱️ Step 4: Monitoring sequential processing...")
            processing_completed = await self._monitor_processing()
            results["steps"]["processing_monitoring"] = {
                "success": processing_completed,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not processing_completed:
                raise Exception("Processing did not complete successfully")
            
            # Step 5: Verify results storage
            print("\n📊 Step 5: Verifying results storage...")
            results_stored = await self._verify_results_storage()
            results["steps"]["results_verification"] = {
                "success": results_stored,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not results_stored:
                raise Exception("Results were not properly stored")
            
            # Step 6: Test results page population
            print("\n📋 Step 6: Testing results page population...")
            results_page_populated = await self._test_results_page()
            results["steps"]["results_page"] = {
                "success": results_page_populated,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if not results_page_populated:
                raise Exception("Results page is not properly populated")
            
            # Step 7: Verify project-based session (no random)
            print("\n🎯 Step 7: Verifying project-based session management...")
            session_proper = await self._verify_session_management()
            results["steps"]["session_management"] = {
                "success": session_proper,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            results["overall_success"] = True
            print("\n✅ ALL TESTS PASSED! Sequential video processing workflow is working correctly.")
            
        except Exception as e:
            error_msg = str(e)
            results["errors"].append(error_msg)
            print(f"\n❌ TEST FAILED: {error_msg}")
            logger.error(f"Workflow test failed: {e}")
        
        results["test_completed"] = datetime.utcnow().isoformat()
        return results
    
    async def _verify_project_exists(self) -> bool:
        """Verify the test project exists"""
        try:
            response = await self.client.get(f"{self.base_url}/api/projects/{self.test_project_id}")
            if response.status_code == 200:
                project_data = response.json()
                print(f"   ✅ Project found: {project_data['name']}")
                return True
            elif response.status_code == 404:
                print(f"   ⚠️ Project {self.test_project_id} not found")
                return False
            else:
                print(f"   ❌ Error checking project: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Error verifying project: {e}")
            return False
    
    async def _create_test_project(self) -> bool:
        """Create the test project if it doesn't exist"""
        try:
            project_data = {
                "name": "VRU Detection Test Project",
                "description": "Test project for sequential video processing validation",
                "cameraModel": "Test Camera Model",
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO"
            }
            
            response = await self.client.post(f"{self.base_url}/api/projects", json=project_data)
            if response.status_code == 201:
                created_project = response.json()
                self.test_project_id = created_project["id"]
                print(f"   ✅ Created project: {created_project['name']} (ID: {self.test_project_id})")
                return True
            else:
                print(f"   ❌ Failed to create project: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Error creating project: {e}")
            return False
    
    async def _upload_test_videos(self) -> bool:
        """Upload test videos to the project"""
        try:
            for i, video_data in enumerate(self.test_videos):
                print(f"   Uploading video {i+1}/3: {video_data['filename']}")
                
                files = {
                    "file": (video_data["filename"], io.BytesIO(video_data["content"]), "video/mp4")
                }
                data = {
                    "project_id": self.test_project_id,
                    "description": f"Test video for sequential processing - {video_data['filename']}"
                }
                
                response = await self.client.post(
                    f"{self.base_url}/api/videos",
                    files=files,
                    data=data
                )
                
                if response.status_code == 201:
                    uploaded_video = response.json()
                    self.uploaded_videos.append({
                        "id": uploaded_video["id"],
                        "filename": uploaded_video["filename"],
                        "expected_types": video_data["expected_types"]
                    })
                    print(f"      ✅ Uploaded: {uploaded_video['filename']} (ID: {uploaded_video['id'][:8]}...)")
                else:
                    print(f"      ❌ Failed to upload {video_data['filename']}: {response.status_code}")
                    return False
            
            print(f"   ✅ Successfully uploaded {len(self.uploaded_videos)} videos")
            return True
            
        except Exception as e:
            print(f"   ❌ Error uploading videos: {e}")
            return False
    
    async def _start_sequential_processing(self) -> bool:
        """Start sequential processing using ONE BUTTON functionality"""
        try:
            video_ids = [v["id"] for v in self.uploaded_videos]
            
            request_data = {
                "project_id": self.test_project_id,
                "video_ids": video_ids,
                "session_name": "Sequential Processing Test Session"
            }
            
            print(f"   Starting processing for {len(video_ids)} videos...")
            
            response = await self.client.post(
                f"{self.base_url}/api/sequential-video/start-all-videos",
                json=request_data
            )
            
            if response.status_code == 200:
                result = response.json()
                self.session_id = result["session_id"]
                print(f"   ✅ Sequential processing started!")
                print(f"      Session ID: {self.session_id}")
                print(f"      Videos to process: {result['videos_to_process']}")
                print(f"      Processing order: {result['processing_order']}")
                return True
            else:
                print(f"   ❌ Failed to start processing: {response.status_code}")
                if response.content:
                    print(f"      Error details: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error starting sequential processing: {e}")
            return False
    
    async def _monitor_processing(self) -> bool:
        """Monitor processing until completion"""
        try:
            max_wait_time = 300  # 5 minutes maximum
            start_time = time.time()
            last_status = None
            
            print("   Monitoring processing progress...")
            
            while time.time() - start_time < max_wait_time:
                response = await self.client.get(
                    f"{self.base_url}/api/sequential-video/sessions/{self.session_id}/status"
                )
                
                if response.status_code == 200:
                    status = response.json()
                    
                    # Only print status updates when they change
                    current_status_key = f"{status['status']}-{status['current_video_index']}"
                    if last_status != current_status_key:
                        print(f"      Status: {status['status']} | Progress: {status['progress']:.1f}% | Video: {status['current_video']} ({status['processed_videos']}/{status['total_videos']})")
                        last_status = current_status_key
                    
                    if status["status"] == "completed":
                        print(f"   ✅ Sequential processing completed successfully!")
                        print(f"      Total videos processed: {status['processed_videos']}")
                        print(f"      Total time: {status['elapsed_time_seconds']:.1f} seconds")
                        return True
                    elif status["status"] == "failed":
                        print(f"   ❌ Processing failed!")
                        return False
                else:
                    print(f"   ⚠️ Failed to get status: {response.status_code}")
                
                await asyncio.sleep(3)  # Check every 3 seconds
            
            print("   ⏰ Processing monitoring timed out")
            return False
            
        except Exception as e:
            print(f"   ❌ Error monitoring processing: {e}")
            return False
    
    async def _verify_results_storage(self) -> bool:
        """Verify that results are properly stored"""
        try:
            print("   Checking results storage...")
            
            response = await self.client.get(
                f"{self.base_url}/api/sequential-video/sessions/{self.session_id}/results"
            )
            
            if response.status_code == 200:
                results = response.json()
                
                print(f"      Session: {results['session_name']}")
                print(f"      Status: {results['status']}")
                print(f"      Videos processed: {len(results['test_results'])}")
                print(f"      Detection events: {len(results['detection_events'])}")
                print(f"      Detection comparisons: {len(results['detection_comparisons'])}")
                
                # Verify we have results for all videos
                expected_videos = len(self.uploaded_videos)
                actual_video_results = len(set(r["video_id"] for r in results["test_results"]))
                
                if actual_video_results >= expected_videos and len(results["detection_events"]) > 0:
                    print(f"   ✅ Results properly stored for all videos")
                    return True
                else:
                    print(f"   ❌ Missing results: expected {expected_videos} videos, found {actual_video_results}")
                    return False
            else:
                print(f"   ❌ Failed to retrieve results: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error verifying results storage: {e}")
            return False
    
    async def _test_results_page(self) -> bool:
        """Test that results page is properly populated"""
        try:
            print("   Testing results page population...")
            
            # Test project sessions endpoint
            response = await self.client.get(
                f"{self.base_url}/api/results/projects/{self.test_project_id}/sessions"
            )
            
            if response.status_code == 200:
                sessions = response.json()
                
                # Find our session
                our_session = None
                for session in sessions:
                    if session["session_id"] == self.session_id:
                        our_session = session
                        break
                
                if our_session and our_session["has_results"]:
                    print(f"      ✅ Session found in results page")
                    print(f"         Results: {our_session['results_count']} test results")
                    print(f"         Detections: {our_session['detection_events']} events")
                    print(f"         Comparisons: {our_session['detection_comparisons']} comparisons")
                    
                    # Test detailed results
                    detailed_response = await self.client.get(
                        f"{self.base_url}/api/results/sessions/{self.session_id}/detailed"
                    )
                    
                    if detailed_response.status_code == 200:
                        detailed = detailed_response.json()
                        print(f"         Detailed results: {len(detailed['video_results'])} videos")
                        print(f"         Overall success rate: {detailed['statistics']['overall_success_rate']:.1f}%")
                        return True
                    else:
                        print(f"      ❌ Failed to get detailed results: {detailed_response.status_code}")
                        return False
                else:
                    print(f"   ❌ Session not found or has no results in results page")
                    return False
            else:
                print(f"   ❌ Failed to get project sessions: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error testing results page: {e}")
            return False
    
    async def _verify_session_management(self) -> bool:
        """Verify session is project-based and not random"""
        try:
            print("   Verifying project-based session management...")
            
            response = await self.client.get(
                f"{self.base_url}/api/sequential-video/sessions/{self.session_id}/status"
            )
            
            if response.status_code == 200:
                status = response.json()
                
                # Check that session is linked to our project
                if status["project_id"] == self.test_project_id:
                    print(f"      ✅ Session properly linked to project {self.test_project_id}")
                    
                    # Check that it's not a random session
                    if status["project_id"] != "00000000-0000-0000-0000-000000000000":
                        print(f"      ✅ Not a random/phantom session")
                        return True
                    else:
                        print(f"      ❌ Session appears to be a random/phantom session")
                        return False
                else:
                    print(f"      ❌ Session linked to wrong project: {status['project_id']}")
                    return False
            else:
                print(f"   ❌ Failed to verify session: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error verifying session management: {e}")
            return False

async def main():
    """Run the complete workflow test"""
    async with SequentialWorkflowTester() as tester:
        results = await tester.test_complete_workflow()
        
        print("\n" + "=" * 70)
        print("🔍 TEST SUMMARY")
        print("=" * 70)
        
        for step_name, step_data in results["steps"].items():
            status_icon = "✅" if step_data["success"] else "❌"
            print(f"{status_icon} {step_name.replace('_', ' ').title()}")
        
        if results["errors"]:
            print(f"\n❌ ERRORS ENCOUNTERED:")
            for error in results["errors"]:
                print(f"   • {error}")
        
        print(f"\n🏁 Overall Result: {'✅ SUCCESS' if results['overall_success'] else '❌ FAILED'}")
        
        # Save results to file
        import os
        results_file = os.path.join(os.path.dirname(__file__), "test_results.json")
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"📄 Full test results saved to: {results_file}")
        
        return results["overall_success"]

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)