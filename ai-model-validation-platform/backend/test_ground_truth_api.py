"""
Ground Truth API Test
SPARC Implementation - Test ground truth endpoints functionality
"""

import sys
import os
import requests
import json
import time
import uuid
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ground_truth_api():
    """Test ground truth management API endpoints"""
    
    base_url = "http://localhost:8000"
    api_base = f"{base_url}/api/ground-truth"
    
    print("🚀 Starting Ground Truth API Tests")
    print("=" * 50)
    
    # Test 1: Health Check
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Server not responding: {str(e)}")
        return
    
    # Test 2: Create Test Video (if needed)
    print("\n📹 Creating test video...")
    video_data = {
        "filename": "test_ground_truth_video.mp4",
        "project_id": str(uuid.uuid4())
    }
    
    try:
        # Create via direct API if available
        video_response = requests.post(f"{base_url}/api/videos/", json=video_data, timeout=10)
        if video_response.status_code in [200, 201]:
            video_id = video_response.json().get("id")
            print(f"✅ Test video created: {video_id}")
        else:
            # Use a mock video ID for testing
            video_id = str(uuid.uuid4())
            print(f"⚠️ Using mock video ID: {video_id}")
    except Exception as e:
        video_id = str(uuid.uuid4())
        print(f"⚠️ Using mock video ID due to error: {str(e)}")
    
    # Test 3: Create Ground Truth Object
    print("\n🎯 Testing ground truth object creation...")
    gt_data = {
        "videoId": video_id,
        "frameNumber": 100,
        "timestamp": 3.33,
        "classLabel": "pedestrian",
        "boundingBox": {
            "x": 150.0,
            "y": 200.0,
            "width": 80.0,
            "height": 160.0
        },
        "confidence": 0.85,
        "validated": False,
        "difficult": False,
        "generationMethod": "manual"
    }
    
    try:
        response = requests.post(f"{api_base}/", json=gt_data, timeout=10)
        print(f"Ground truth creation response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            gt_response = response.json()
            ground_truth_id = gt_response.get("id")
            workflow_id = gt_response.get("workflow_id")
            print(f"✅ Ground truth object created: {ground_truth_id}")
            print(f"✅ Validation workflow created: {workflow_id}")
        else:
            print(f"❌ Ground truth creation failed: {response.text}")
            ground_truth_id = None
            workflow_id = None
    except Exception as e:
        print(f"❌ Ground truth creation error: {str(e)}")
        ground_truth_id = None
        workflow_id = None
    
    # Test 4: Create Validation Workflow (if not auto-created)
    if ground_truth_id and not workflow_id:
        print("\n✅ Testing validation workflow creation...")
        workflow_data = {
            "groundTruthId": ground_truth_id,
            "assignedReviewer": "test_reviewer",
            "qualityLevel": "medium",
            "reviewNotes": "Test workflow creation",
            "confidenceScore": 0.75
        }
        
        try:
            response = requests.post(f"{api_base}/validation-workflow", json=workflow_data, timeout=10)
            print(f"Validation workflow response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                workflow_response = response.json()
                workflow_id = workflow_response.get("workflow_id")
                print(f"✅ Validation workflow created: {workflow_id}")
            else:
                print(f"❌ Validation workflow creation failed: {response.text}")
        except Exception as e:
            print(f"❌ Validation workflow error: {str(e)}")
    
    # Test 5: Submit Validation Decision
    if workflow_id:
        print("\n📋 Testing validation decision submission...")
        decision_data = {
            "validationStatus": "approved",
            "reviewNotes": "Test approval - looks good",
            "qualityLevel": "high",
            "reviewerId": "test_reviewer_123"
        }
        
        try:
            response = requests.put(
                f"{api_base}/validation-workflow/{workflow_id}/review",
                json=decision_data,
                timeout=10
            )
            print(f"Validation decision response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print("✅ Validation decision submitted successfully")
            else:
                print(f"❌ Validation decision failed: {response.text}")
        except Exception as e:
            print(f"❌ Validation decision error: {str(e)}")
    
    # Test 6: Test Automated Generation
    print("\n🤖 Testing automated ground truth generation...")
    try:
        response = requests.post(
            f"{api_base}/generate/video/{video_id}",
            params={
                "confidence_threshold": 0.5,
                "processing_method": "automated_ml"
            },
            timeout=10
        )
        print(f"Automated generation response: {response.status_code}")
        
        if response.status_code in [200, 201, 202]:
            print("✅ Automated generation started successfully")
        else:
            print(f"❌ Automated generation failed: {response.text}")
    except Exception as e:
        print(f"❌ Automated generation error: {str(e)}")
    
    # Test 7: Test Batch Processing
    print("\n📦 Testing batch processing...")
    batch_data = {
        "batchName": "Test Batch Processing",
        "videoIds": [video_id],
        "processingMethod": "automated_ml",
        "description": "Test batch for API validation"
    }
    
    try:
        response = requests.post(f"{api_base}/batch", json=batch_data, timeout=10)
        print(f"Batch processing response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            batch_response = response.json()
            batch_id = batch_response.get("batch_id")
            print(f"✅ Batch processing job created: {batch_id}")
            
            # Check batch status
            if batch_id:
                time.sleep(2)  # Wait a moment
                status_response = requests.get(f"{api_base}/batch/{batch_id}/status", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"✅ Batch status: {status_data.get('status')}")
                else:
                    print(f"⚠️ Could not get batch status: {status_response.status_code}")
        else:
            print(f"❌ Batch processing failed: {response.text}")
    except Exception as e:
        print(f"❌ Batch processing error: {str(e)}")
    
    # Test 8: Test Export Creation
    print("\n📤 Testing export functionality...")
    export_data = {
        "exportName": "Test JSON Export",
        "formatType": "json",
        "description": "Test export for API validation"
    }
    
    try:
        response = requests.post(f"{api_base}/export", json=export_data, timeout=10)
        print(f"Export creation response: {response.status_code}")
        
        if response.status_code in [200, 201, 202]:
            export_response = response.json()
            export_id = export_response.get("export_id")
            print(f"✅ Export job created: {export_id}")
        else:
            print(f"❌ Export creation failed: {response.text}")
    except Exception as e:
        print(f"❌ Export creation error: {str(e)}")
    
    # Test 9: Test Quality Metrics
    print("\n📊 Testing quality metrics...")
    try:
        response = requests.get(f"{api_base}/stats/video/{video_id}/quality", timeout=10)
        print(f"Quality metrics response: {response.status_code}")
        
        if response.status_code == 200:
            metrics_data = response.json()
            print(f"✅ Quality metrics retrieved")
            print(f"   Total objects: {metrics_data.get('total_objects', 0)}")
        else:
            print(f"❌ Quality metrics failed: {response.text}")
    except Exception as e:
        print(f"❌ Quality metrics error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🎉 Ground Truth API Tests Completed!")
    print("=" * 50)

if __name__ == "__main__":
    test_ground_truth_api()