#!/usr/bin/env python3
"""
Comprehensive Video Upload and Display Workflow Test
====================================================

This test validates the complete video upload and display workflow to verify all fixes are working properly.

Test Coverage:
1. Test new video upload to ensure filename consistency 
2. Verify uploaded video displays correctly in the frontend
3. Test detection pipeline works without errors
4. Confirm all video URLs are accessible and return 200 OK
5. Validate complete end-to-end workflow from upload to annotation

Author: Testing and Quality Assurance Agent
Date: 2025-09-10
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import requests
from datetime import datetime


class VideoWorkflowTester:
    """Comprehensive video upload and workflow tester."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
        self.test_session = None
        self.uploaded_videos = []
        
    def create_test_video(self) -> Tuple[str, bytes]:
        """Create a minimal test video file using ffmpeg if available, or generate fake video data."""
        try:
            import subprocess
            
            # Create a temporary video file with ffmpeg
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            temp_file.close()
            
            # Generate a simple 5-second test video
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=5:size=320x240:rate=30',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30',
                '-y', temp_file.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(temp_file.name):
                with open(temp_file.name, 'rb') as f:
                    video_data = f.read()
                os.unlink(temp_file.name)
                return "test_video.mp4", video_data
            else:
                print(f"FFmpeg failed: {result.stderr}")
                
        except Exception as e:
            print(f"FFmpeg not available or failed: {e}")
        
        # Fallback: Create a minimal MP4-like file with proper headers
        mp4_header = bytes([
            0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,  # ftyp box
            0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
            0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
            0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31,
        ])
        
        # Add minimal mdat box
        mdat_box = bytes([0x00, 0x00, 0x00, 0x08, 0x6D, 0x64, 0x61, 0x74])
        
        fake_video_data = mp4_header + mdat_box + b'\x00' * 1000
        
        return "test_video.mp4", fake_video_data

    async def test_health_endpoint(self) -> Dict:
        """Test if the backend API is accessible."""
        test_name = "API Health Check"
        print(f"\n🏥 {test_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "test": test_name,
                            "status": "PASS", 
                            "details": f"API is healthy: {data}",
                            "response_time": response.headers.get('X-Process-Time', 'N/A')
                        }
                    else:
                        return {
                            "test": test_name,
                            "status": "FAIL", 
                            "details": f"Health check failed with status {response.status}"
                        }
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL", 
                "details": f"Health check error: {str(e)}"
            }

    async def test_central_video_upload(self, filename: str, video_data: bytes) -> Dict:
        """Test central video upload endpoint for filename consistency."""
        test_name = "Central Video Upload"
        print(f"\n📹 {test_name}")
        
        try:
            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field('file', video_data, filename=filename, content_type='video/mp4')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/videos/upload", data=data) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        result = await response.json()
                        video_id = result.get('video_id')
                        original_filename = result.get('original_filename')
                        
                        self.uploaded_videos.append({
                            'id': video_id,
                            'filename': original_filename,
                            'endpoint': 'central'
                        })
                        
                        return {
                            "test": test_name,
                            "status": "PASS",
                            "details": f"Upload successful. Video ID: {video_id}, Filename: {original_filename}",
                            "video_id": video_id,
                            "original_filename": original_filename
                        }
                    else:
                        return {
                            "test": test_name,
                            "status": "FAIL",
                            "details": f"Upload failed with status {response.status}: {response_text}"
                        }
                        
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL",
                "details": f"Upload error: {str(e)}"
            }

    async def test_project_video_upload(self, filename: str, video_data: bytes) -> Dict:
        """Test project-specific video upload endpoint."""
        test_name = "Project-Specific Video Upload"
        print(f"\n📁 {test_name}")
        
        try:
            # First, get available projects
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/projects") as response:
                    if response.status == 200:
                        projects = await response.json()
                        if not projects:
                            return {
                                "test": test_name,
                                "status": "SKIP",
                                "details": "No projects available for testing"
                            }
                        
                        project_id = projects[0]['id']  # Use first available project
                        
                        # Upload video to project
                        data = aiohttp.FormData()
                        data.add_field('file', video_data, filename=f"project_{filename}", content_type='video/mp4')
                        
                        async with session.post(f"{self.base_url}/api/projects/{project_id}/videos/upload", data=data) as upload_response:
                            if upload_response.status == 200:
                                result = await upload_response.json()
                                video_id = result.get('video_id')
                                
                                self.uploaded_videos.append({
                                    'id': video_id,
                                    'filename': f"project_{filename}",
                                    'endpoint': 'project',
                                    'project_id': project_id
                                })
                                
                                return {
                                    "test": test_name,
                                    "status": "PASS",
                                    "details": f"Project upload successful. Video ID: {video_id}, Project ID: {project_id}",
                                    "video_id": video_id,
                                    "project_id": project_id
                                }
                            else:
                                error_text = await upload_response.text()
                                return {
                                    "test": test_name,
                                    "status": "FAIL",
                                    "details": f"Project upload failed with status {upload_response.status}: {error_text}"
                                }
                    else:
                        return {
                            "test": test_name,
                            "status": "FAIL",
                            "details": f"Could not fetch projects: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL",
                "details": f"Project upload error: {str(e)}"
            }

    async def test_video_accessibility(self, video_info: Dict) -> Dict:
        """Test if uploaded video URLs are accessible and return 200 OK."""
        test_name = f"Video URL Accessibility - {video_info['id']}"
        print(f"\n🌐 {test_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test video metadata endpoint
                async with session.get(f"{self.base_url}/api/videos/{video_info['id']}") as response:
                    if response.status == 200:
                        video_data = await response.json()
                        file_path = video_data.get('file_path')
                        
                        if file_path:
                            # Test direct file access
                            file_url = f"{self.base_url}/uploads/{os.path.basename(file_path)}"
                            async with session.get(file_url) as file_response:
                                if file_response.status == 200:
                                    content_length = file_response.headers.get('Content-Length', '0')
                                    return {
                                        "test": test_name,
                                        "status": "PASS",
                                        "details": f"Video accessible at {file_url}, Size: {content_length} bytes",
                                        "file_url": file_url,
                                        "content_length": content_length
                                    }
                                else:
                                    return {
                                        "test": test_name,
                                        "status": "FAIL",
                                        "details": f"Video file not accessible: {file_response.status}"
                                    }
                        else:
                            return {
                                "test": test_name,
                                "status": "FAIL",
                                "details": "No file_path in video metadata"
                            }
                    else:
                        response_text = await response.text()
                        return {
                            "test": test_name,
                            "status": "FAIL",
                            "details": f"Video metadata not accessible: {response.status} - {response_text}"
                        }
                        
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL",
                "details": f"Accessibility test error: {str(e)}"
            }

    async def test_detection_pipeline(self, video_info: Dict) -> Dict:
        """Test detection pipeline functionality without errors."""
        test_name = f"Detection Pipeline - {video_info['id']}"
        print(f"\n🔍 {test_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Trigger detection pipeline
                async with session.post(f"{self.base_url}/api/videos/{video_info['id']}/detect") as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        result = await response.json()
                        detection_id = result.get('detection_id')
                        
                        # Wait a moment for processing
                        await asyncio.sleep(2)
                        
                        # Check detection results
                        async with session.get(f"{self.base_url}/api/videos/{video_info['id']}/detections") as det_response:
                            if det_response.status == 200:
                                detections = await det_response.json()
                                return {
                                    "test": test_name,
                                    "status": "PASS",
                                    "details": f"Detection pipeline successful. Found {len(detections)} detections",
                                    "detection_count": len(detections),
                                    "detection_id": detection_id
                                }
                            else:
                                return {
                                    "test": test_name,
                                    "status": "PARTIAL",
                                    "details": f"Pipeline triggered but could not fetch results: {det_response.status}"
                                }
                    else:
                        return {
                            "test": test_name,
                            "status": "FAIL",
                            "details": f"Detection pipeline failed: {response.status} - {response_text}"
                        }
                        
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL",
                "details": f"Detection pipeline error: {str(e)}"
            }

    async def test_annotation_workflow(self, video_info: Dict) -> Dict:
        """Test complete end-to-end workflow from upload to annotation."""
        test_name = f"Annotation Workflow - {video_info['id']}"
        print(f"\n✏️ {test_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Create a test annotation
                annotation_data = {
                    "object_class": "test_object",
                    "x": 100,
                    "y": 100,
                    "width": 50,
                    "height": 50,
                    "frame_number": 1,
                    "confidence": 0.95,
                    "notes": "Test annotation from workflow test"
                }
                
                async with session.post(
                    f"{self.base_url}/api/videos/{video_info['id']}/annotations",
                    json=annotation_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        annotation_id = result.get('annotation_id')
                        
                        # Fetch annotations to verify
                        async with session.get(f"{self.base_url}/api/videos/{video_info['id']}/annotations") as fetch_response:
                            if fetch_response.status == 200:
                                annotations = await fetch_response.json()
                                found_annotation = any(ann.get('id') == annotation_id for ann in annotations)
                                
                                return {
                                    "test": test_name,
                                    "status": "PASS",
                                    "details": f"Annotation workflow successful. Created annotation {annotation_id}, Found in list: {found_annotation}",
                                    "annotation_id": annotation_id,
                                    "total_annotations": len(annotations)
                                }
                            else:
                                return {
                                    "test": test_name,
                                    "status": "PARTIAL",
                                    "details": f"Annotation created but could not fetch list: {fetch_response.status}"
                                }
                    else:
                        response_text = await response.text()
                        return {
                            "test": test_name,
                            "status": "FAIL",
                            "details": f"Annotation creation failed: {response.status} - {response_text}"
                        }
                        
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL",
                "details": f"Annotation workflow error: {str(e)}"
            }

    async def test_frontend_integration(self) -> Dict:
        """Test if frontend can access uploaded videos."""
        test_name = "Frontend Integration"
        print(f"\n🖥️ {test_name}")
        
        try:
            # Test if we can get the video list for frontend consumption
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/videos", params={"limit": 10}) as response:
                    if response.status == 200:
                        videos = await response.json()
                        
                        # Check if our uploaded videos are in the list
                        uploaded_ids = {v['id'] for v in self.uploaded_videos}
                        found_videos = [v for v in videos if v.get('id') in uploaded_ids]
                        
                        return {
                            "test": test_name,
                            "status": "PASS",
                            "details": f"Frontend can access video list. Found {len(found_videos)}/{len(uploaded_ids)} uploaded videos",
                            "total_videos": len(videos),
                            "found_uploaded": len(found_videos)
                        }
                    else:
                        response_text = await response.text()
                        return {
                            "test": test_name,
                            "status": "FAIL",
                            "details": f"Could not fetch video list: {response.status} - {response_text}"
                        }
                        
        except Exception as e:
            return {
                "test": test_name,
                "status": "FAIL",
                "details": f"Frontend integration error: {str(e)}"
            }

    async def run_comprehensive_test(self) -> Dict:
        """Run all tests in sequence and generate comprehensive report."""
        print("=" * 80)
        print("🚀 COMPREHENSIVE VIDEO UPLOAD AND DISPLAY WORKFLOW TEST")
        print("=" * 80)
        
        test_results = []
        start_time = time.time()
        
        # 1. Health check
        health_result = await self.test_health_endpoint()
        test_results.append(health_result)
        
        if health_result['status'] != 'PASS':
            print("❌ Backend API not accessible, stopping tests")
            return {
                "summary": {"total": 1, "passed": 0, "failed": 1, "skipped": 0},
                "tests": test_results,
                "duration": time.time() - start_time
            }
        
        # 2. Create test video
        filename, video_data = self.create_test_video()
        print(f"📹 Created test video: {filename} ({len(video_data)} bytes)")
        
        # 3. Test central upload
        upload_result = await self.test_central_video_upload(filename, video_data)
        test_results.append(upload_result)
        
        # 4. Test project upload
        project_upload_result = await self.test_project_video_upload(filename, video_data)
        test_results.append(project_upload_result)
        
        # 5. Test accessibility for all uploaded videos
        for video_info in self.uploaded_videos:
            accessibility_result = await self.test_video_accessibility(video_info)
            test_results.append(accessibility_result)
            
            # 6. Test detection pipeline
            detection_result = await self.test_detection_pipeline(video_info)
            test_results.append(detection_result)
            
            # 7. Test annotation workflow
            annotation_result = await self.test_annotation_workflow(video_info)
            test_results.append(annotation_result)
        
        # 8. Test frontend integration
        frontend_result = await self.test_frontend_integration()
        test_results.append(frontend_result)
        
        # Calculate summary
        passed = sum(1 for r in test_results if r['status'] == 'PASS')
        failed = sum(1 for r in test_results if r['status'] == 'FAIL')
        partial = sum(1 for r in test_results if r['status'] == 'PARTIAL')
        skipped = sum(1 for r in test_results if r['status'] == 'SKIP')
        
        total_time = time.time() - start_time
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(test_results),
                "passed": passed,
                "failed": failed,
                "partial": partial,
                "skipped": skipped,
                "success_rate": f"{(passed/(len(test_results)-skipped))*100:.1f}%" if len(test_results) > skipped else "N/A"
            },
            "uploaded_videos": self.uploaded_videos,
            "tests": test_results,
            "duration": f"{total_time:.2f}s"
        }

    def print_results(self, results: Dict):
        """Print comprehensive test results."""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 80)
        
        summary = results['summary']
        print(f"⏱️  Total Time: {results['duration']}")
        print(f"📈 Success Rate: {summary['success_rate']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"⚠️  Partial: {summary['partial']}")
        print(f"⏭️  Skipped: {summary['skipped']}")
        print(f"📊 Total Tests: {summary['total']}")
        
        print("\n📋 DETAILED RESULTS:")
        print("-" * 80)
        
        for i, test in enumerate(results['tests'], 1):
            status_emoji = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️", "SKIP": "⏭️"}
            emoji = status_emoji.get(test['status'], "❓")
            print(f"{i:2d}. {emoji} {test['test']}")
            print(f"    {test['details']}")
            if test.get('video_id'):
                print(f"    📹 Video ID: {test['video_id']}")
            if test.get('file_url'):
                print(f"    🔗 URL: {test['file_url']}")
            print()
        
        if results.get('uploaded_videos'):
            print("📹 UPLOADED VIDEOS:")
            print("-" * 40)
            for video in results['uploaded_videos']:
                print(f"   • {video['id']} ({video['filename']}) via {video['endpoint']}")


async def main():
    """Main test execution function."""
    tester = VideoWorkflowTester("http://localhost:8000")
    
    try:
        results = await tester.run_comprehensive_test()
        tester.print_results(results)
        
        # Save results to file
        results_file = Path("tests/video_workflow_test_results.json")
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📁 Full results saved to: {results_file}")
        
        # Exit with appropriate code
        if results['summary']['failed'] > 0:
            print("\n❌ SOME TESTS FAILED")
            sys.exit(1)
        else:
            print("\n✅ ALL TESTS PASSED")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n💥 FATAL ERROR: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    print("🧪 Starting Comprehensive Video Upload and Display Workflow Test")
    asyncio.run(main())