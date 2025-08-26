#!/usr/bin/env python3
"""
Complete end-to-end test for annotation API fixes

This test:
1. Creates a test project
2. Uploads a test video 
3. Creates annotations for that video
4. Tests all the annotation API endpoints
"""

import requests
import json
import sys
import uuid
from datetime import datetime
import time
import tempfile
import os

# Test configuration
BASE_URL = "http://localhost:8001"

def create_test_project():
    """Create a test project"""
    project_data = {
        "name": f"Test Project {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "description": "Test project for annotation API validation",
        "camera_model": "Test Camera v1.0",
        "camera_view": "Front-facing VRU",
        "signal_type": "GPIO"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json=project_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            project = response.json()
            print(f"✅ Created test project: {project.get('id', 'unknown')}")
            return project.get('id')
        else:
            print(f"❌ Failed to create project: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating project: {str(e)}")
        return None

def create_test_video(project_id):
    """Create a test video file and upload it"""
    
    # Create a tiny test video file (just a placeholder)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        # Write minimal MP4 header bytes (not a real video, but enough for testing)
        temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
        temp_file.write(b'\x00' * 100)  # Pad with zeros
        temp_file_path = temp_file.name
    
    try:
        # Upload the test video
        with open(temp_file_path, 'rb') as video_file:
            files = {
                'file': ('test_video.mp4', video_file, 'video/mp4')
            }
            data = {
                'filename': 'test_video.mp4'
            }
            
            response = requests.post(
                f"{BASE_URL}/api/projects/{project_id}/videos",
                files=files,
                data=data,
                timeout=30
            )
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        if response.status_code in [200, 201]:
            video = response.json()
            print(f"✅ Uploaded test video: {video.get('id', 'unknown')}")
            return video.get('id')
        else:
            print(f"❌ Failed to upload video: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error uploading video: {str(e)}")
        # Clean up temp file on error
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return None

def test_annotation_creation_with_real_video(video_id):
    """Test annotation creation with a real video"""
    
    print(f"\n🧪 TESTING ANNOTATION CREATION (Real Video: {video_id[:8]}...)")
    print("=" * 60)
    
    # Test data with proper format
    test_annotations = [
        {
            "name": "Valid pedestrian annotation",
            "data": {
                "detectionId": "DET_PED_001",
                "frameNumber": 30,
                "timestamp": 1.0,
                "vruType": "pedestrian",
                "boundingBox": {
                    "x": 100,
                    "y": 150,
                    "width": 80,
                    "height": 120,
                    "confidence": 0.85
                },
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "validated": False
            },
            "should_pass": True
        },
        {
            "name": "Valid cyclist with auto-generated detection ID",
            "data": {
                "frameNumber": 45,
                "timestamp": 2.0,
                "vruType": "cyclist",
                "boundingBox": {
                    "x": 200,
                    "y": 100,
                    "width": 60,
                    "height": 140,
                    "confidence": 0.9
                },
                "validated": True
            },
            "should_pass": True
        },
        {
            "name": "Invalid bounding box (zero width)",
            "data": {
                "frameNumber": 60,
                "timestamp": 3.0,
                "vruType": "pedestrian",
                "boundingBox": {
                    "x": 100,
                    "y": 150,
                    "width": 0,  # Invalid!
                    "height": 120,
                    "confidence": 0.8
                }
            },
            "should_pass": False
        }
    ]
    
    passed = 0
    failed = 0
    created_annotations = []
    
    for i, test_case in enumerate(test_annotations, 1):
        print(f"\n📝 Test {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            # Send POST request to annotation endpoint
            response = requests.post(
                f"{BASE_URL}/api/videos/{video_id}/annotations",
                json=test_case["data"],
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            if test_case["should_pass"]:
                if response.status_code in [200, 201]:
                    print("✅ PASSED - Annotation created successfully")
                    try:
                        result = response.json()
                        annotation_id = result.get('id', 'N/A')
                        detection_id = result.get('detection_id', 'N/A')
                        print(f"   Created annotation ID: {annotation_id}")
                        print(f"   Detection ID: {detection_id}")
                        print(f"   VRU Type: {result.get('vru_type', 'N/A')}")
                        
                        created_annotations.append(annotation_id)
                        passed += 1
                    except Exception as parse_error:
                        print(f"   Response parsing error: {parse_error}")
                        print(f"   Raw response: {response.text[:200]}")
                else:
                    print(f"❌ FAILED - Expected success but got {response.status_code}")
                    print(f"   Response: {response.text[:200]}...")
                    failed += 1
            else:
                if response.status_code >= 400:
                    print("✅ PASSED - Correctly rejected invalid data")
                    try:
                        error = response.json()
                        print(f"   Error: {error.get('detail', 'No detail')}")
                    except:
                        print(f"   Error response: {response.text[:100]}...")
                    passed += 1
                else:
                    print(f"❌ FAILED - Should have been rejected but got {response.status_code}")
                    failed += 1
            
        except requests.exceptions.RequestException as e:
            print(f"❌ REQUEST ERROR: {str(e)}")
            failed += 1
            
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {str(e)}")
            failed += 1
    
    print(f"\n📊 ANNOTATION CREATION RESULTS")
    print("=" * 35)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%" if (passed+failed) > 0 else "N/A")
    
    return passed, failed, created_annotations

def test_annotation_retrieval(video_id, annotation_ids):
    """Test annotation retrieval endpoints"""
    
    print(f"\n📥 TESTING ANNOTATION RETRIEVAL")
    print("=" * 35)
    
    passed = 0
    failed = 0
    
    # Test 1: Get all annotations for video
    try:
        response = requests.get(
            f"{BASE_URL}/api/videos/{video_id}/annotations",
            timeout=10
        )
        
        print(f"\n🔍 Get all annotations: Status {response.status_code}")
        
        if response.status_code == 200:
            annotations = response.json()
            print(f"✅ Retrieved {len(annotations)} annotations")
            for ann in annotations:
                print(f"   - {ann.get('id', 'N/A')}: {ann.get('vru_type', 'N/A')} at frame {ann.get('frame_number', 'N/A')}")
            passed += 1
        else:
            print(f"❌ Failed to retrieve annotations: {response.text[:100]}")
            failed += 1
            
    except Exception as e:
        print(f"❌ Error retrieving annotations: {str(e)}")
        failed += 1
    
    # Test 2: Get specific annotation by ID
    if annotation_ids:
        try:
            annotation_id = annotation_ids[0]
            response = requests.get(
                f"{BASE_URL}/api/annotations/{annotation_id}",
                timeout=10
            )
            
            print(f"\n🎯 Get specific annotation: Status {response.status_code}")
            
            if response.status_code == 200:
                annotation = response.json()
                print(f"✅ Retrieved annotation {annotation.get('id', 'N/A')}")
                print(f"   VRU Type: {annotation.get('vru_type', 'N/A')}")
                print(f"   Frame: {annotation.get('frame_number', 'N/A')}")
                passed += 1
            else:
                print(f"❌ Failed to retrieve specific annotation: {response.text[:100]}")
                failed += 1
                
        except Exception as e:
            print(f"❌ Error retrieving specific annotation: {str(e)}")
            failed += 1
    
    return passed, failed

def main():
    """Run complete end-to-end test"""
    print("🚀 COMPLETE ANNOTATION API VALIDATION")
    print("=" * 50)
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    total_passed = 0
    total_failed = 0
    
    # Step 1: Create test project
    print(f"\n📁 STEP 1: Creating test project...")
    project_id = create_test_project()
    if not project_id:
        print("❌ Cannot proceed without project")
        return 1
    
    # Step 2: Upload test video
    print(f"\n📹 STEP 2: Uploading test video...")
    video_id = create_test_video(project_id)
    if not video_id:
        print("❌ Cannot proceed without video")
        return 1
    
    # Wait a moment for video processing
    print("⏳ Waiting 2 seconds for video processing...")
    time.sleep(2)
    
    # Step 3: Test annotation creation
    print(f"\n✏️ STEP 3: Testing annotation creation...")
    create_passed, create_failed, annotation_ids = test_annotation_creation_with_real_video(video_id)
    total_passed += create_passed
    total_failed += create_failed
    
    # Step 4: Test annotation retrieval
    print(f"\n📥 STEP 4: Testing annotation retrieval...")
    retrieve_passed, retrieve_failed = test_annotation_retrieval(video_id, annotation_ids)
    total_passed += retrieve_passed
    total_failed += retrieve_failed
    
    # Final summary
    print(f"\n🎯 COMPLETE TEST SUMMARY")
    print("=" * 30)
    print(f"Project ID: {project_id}")
    print(f"Video ID: {video_id}")
    print(f"Annotations Created: {len(annotation_ids)}")
    print(f"Total Tests Passed: {total_passed}")
    print(f"Total Tests Failed: {total_failed}")
    
    success_rate = (total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0
    print(f"Overall Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 ANNOTATION API FIXES ARE WORKING WELL!")
        return 0
    elif success_rate >= 60:
        print("⚠️  Annotation API fixes partially working")
        return 1
    else:
        print("❌ Annotation API fixes need more work")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)