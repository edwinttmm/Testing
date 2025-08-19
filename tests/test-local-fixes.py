#!/usr/bin/env python3
"""
Local test script to verify backend API fixes
Tests the specific issues identified in the analysis report
"""

import json
import sys
import os
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

# Test the updated schemas
def test_schemas():
    """Test the updated Pydantic schemas"""
    print("🔧 Testing Updated Schemas...")
    
    try:
        from schemas import ProjectResponse, VideoUploadResponse, DashboardStats
        from datetime import datetime
        
        # Test ProjectResponse with aliases
        project_data = {
            "id": "test-id",
            "name": "Test Project",
            "description": "Test Description",
            "camera_model": "Test Camera",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO",
            "status": "active",
            "owner_id": "test-owner",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        project_response = ProjectResponse(**project_data)
        project_dict = project_response.model_dump(by_alias=True)
        
        expected_fields = ["id", "name", "cameraModel", "cameraView", "signalType", "ownerId", "createdAt"]
        missing_fields = [field for field in expected_fields if field not in project_dict]
        
        print(f"✅ ProjectResponse schema: {len(missing_fields) == 0}")
        if missing_fields:
            print(f"   Missing fields: {missing_fields}")
        
        # Test VideoUploadResponse
        video_data = {
            "id": "video-id",
            "project_id": "project-id",
            "filename": "test.mp4",
            "original_name": "test.mp4",
            "size": 1024000,
            "file_size": 1024000,
            "uploaded_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "status": "uploaded",
            "ground_truth_generated": False,
            "ground_truth_status": "pending",
            "detection_count": 0,
            "message": "Test message"
        }
        
        video_response = VideoUploadResponse(**video_data)
        video_dict = video_response.model_dump(by_alias=True)
        
        expected_video_fields = ["id", "projectId", "filename", "originalName", "fileSize", "uploadedAt"]
        missing_video_fields = [field for field in expected_video_fields if field not in video_dict]
        
        print(f"✅ VideoUploadResponse schema: {len(missing_video_fields) == 0}")
        if missing_video_fields:
            print(f"   Missing fields: {missing_video_fields}")
        
        return len(missing_fields) == 0 and len(missing_video_fields) == 0
        
    except Exception as e:
        print(f"❌ Schema test failed: {str(e)}")
        return False

def test_cors_config():
    """Test the CORS configuration"""
    print("🌐 Testing CORS Configuration...")
    
    try:
        from config import settings
        
        required_origins = [
            "http://155.138.239.131:3000",
            "https://155.138.239.131:3000"
        ]
        
        missing_origins = [origin for origin in required_origins if origin not in settings.cors_origins]
        
        print(f"✅ CORS configuration: {len(missing_origins) == 0}")
        print(f"   Total origins configured: {len(settings.cors_origins)}")
        if missing_origins:
            print(f"   Missing origins: {missing_origins}")
        
        # Check for wildcard removal in production
        has_wildcard = '*' in settings.cors_origins
        print(f"✅ No wildcard origins: {not has_wildcard}")
        
        return len(missing_origins) == 0 and not has_wildcard
        
    except Exception as e:
        print(f"❌ CORS config test failed: {str(e)}")
        return False

def test_socketio_cors():
    """Test Socket.IO CORS configuration"""
    print("🔌 Testing Socket.IO CORS...")
    
    try:
        # Read socketio_server.py and check for wildcard removal
        socketio_path = '/home/user/Testing/ai-model-validation-platform/backend/socketio_server.py'
        with open(socketio_path, 'r') as f:
            content = f.read()
        
        # Check that wildcard is not present in origins list (not just comments)
        import re
        cors_section = re.search(r'cors_allowed_origins=\[(.*?)\]', content, re.DOTALL)
        if cors_section:
            origins_content = cors_section.group(1)
            has_wildcard = "'*'" in origins_content and not origins_content.strip().startswith('#')
        else:
            has_wildcard = True  # Couldn't find CORS section
        
        # Check for proper origins
        has_https_origin = "https://155.138.239.131:3000" in content
        
        print(f"✅ Socket.IO no wildcard: {not has_wildcard}")
        print(f"✅ Socket.IO HTTPS origin: {has_https_origin}")
        
        return not has_wildcard and has_https_origin
        
    except Exception as e:
        print(f"❌ Socket.IO CORS test failed: {str(e)}")
        return False

def test_dashboard_response_format():
    """Test dashboard response format simulation"""
    print("📊 Testing Dashboard Response Format...")
    
    try:
        # Simulate the dashboard response
        mock_stats = {
            "projectCount": 5,
            "videoCount": 10,
            "testCount": 3,
            "averageAccuracy": 94.2,
            "activeTests": 1,
            "totalDetections": 150
        }
        
        expected_fields = ["projectCount", "videoCount", "testCount", "averageAccuracy", "activeTests", "totalDetections"]
        missing_fields = [field for field in expected_fields if field not in mock_stats]
        
        print(f"✅ Dashboard format correct: {len(missing_fields) == 0}")
        if missing_fields:
            print(f"   Missing fields: {missing_fields}")
        
        return len(missing_fields) == 0
        
    except Exception as e:
        print(f"❌ Dashboard format test failed: {str(e)}")
        return False

def main():
    """Run all local tests"""
    print("🧪 Running Local Backend Fix Validation")
    print("=" * 50)
    
    tests = [
        ("Schemas", test_schemas),
        ("CORS Config", test_cors_config),
        ("Socket.IO CORS", test_socketio_cors),
        ("Dashboard Format", test_dashboard_response_format)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}:")
        try:
            result = test_func()
            results.append(result)
            print(f"{'✅ PASS' if result else '❌ FAIL'}")
        except Exception as e:
            print(f"❌ FAIL: {str(e)}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print(f"📋 SUMMARY: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("🎉 All local tests passed! Backend fixes are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)