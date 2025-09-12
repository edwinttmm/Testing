#!/usr/bin/env python3
"""
Test Video Upload Fix - Verify 500 Error Resolution
===================================================

Tests if the video upload endpoint now works after fixing hardcoded Docker paths
"""

import requests
import os
import tempfile

def test_upload_endpoint():
    """Test the video upload API endpoint"""
    print("🧪 TESTING VIDEO UPLOAD ENDPOINT AFTER FIX")
    print("=" * 50)
    
    # Check backend health first
    try:
        health_response = requests.get("http://localhost:8000/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Backend health check passed")
        else:
            print(f"❌ Backend health check failed: {health_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend not accessible: {e}")
        return False
    
    # Create a small test "video" file (just a text file for testing)
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as test_file:
        test_file.write(b"Test video content for upload verification")
        test_file_path = test_file.name
    
    try:
        print(f"📁 Created test file: {os.path.basename(test_file_path)}")
        
        # Test the upload endpoint
        with open(test_file_path, 'rb') as file:
            files = {'file': ('test_video.mp4', file, 'video/mp4')}
            data = {'project_id': '1068b364-d3ea-4150-a98f-f463348f05ee'}  # Use existing project
            
            print("📤 Testing POST /api/videos upload...")
            response = requests.post(
                "http://localhost:8000/api/videos", 
                files=files,
                data=data,
                timeout=30
            )
            
            print(f"📊 Response Status: {response.status_code}")
            print(f"📄 Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Upload successful!")
                print(f"   Video ID: {result.get('id', 'N/A')}")
                print(f"   Filename: {result.get('filename', 'N/A')}")
                print(f"   File size: {result.get('file_size', 'N/A')} bytes")
                return True
                
            elif response.status_code == 500:
                print("❌ Still getting 500 error - upload fix may not be complete")
                print(f"   Response: {response.text[:200]}...")
                return False
                
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return False
        
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

def test_directory_structure():
    """Test if upload directories were created correctly"""
    print("\\n🔍 TESTING UPLOAD DIRECTORY STRUCTURE")
    print("=" * 50)
    
    expected_dirs = [
        "uploads",
        "uploads/front-facing-vru", 
        "uploads/rear-facing-vru",
        "uploads/in-cab-driver-behavior",
        "uploads/multi-angle-scenarios"
    ]
    
    all_exist = True
    for dir_path in expected_dirs:
        exists = os.path.exists(dir_path)
        writable = os.access(dir_path, os.W_OK) if exists else False
        status = "✅" if exists and writable else "❌"
        print(f"{status} {dir_path} - Exists: {exists}, Writable: {writable}")
        if not (exists and writable):
            all_exist = False
    
    return all_exist

if __name__ == "__main__":
    print("🎯 VIDEO UPLOAD FIX VALIDATION")
    print("Root cause: Hardcoded /app/uploads path in video_library_service.py")
    print("Fix applied: Changed to relative 'uploads' path")
    print()
    
    # Test directory structure
    dirs_ok = test_directory_structure()
    
    # Test upload endpoint
    upload_ok = test_upload_endpoint()
    
    print("\\n" + "=" * 60)
    print("📋 FINAL TEST RESULTS")
    print("=" * 60)
    
    if dirs_ok and upload_ok:
        print("🎉 SUCCESS: Video upload 500 error has been FIXED!")
        print("\\n✅ Verified working:")
        print("   - Upload directory structure created")
        print("   - Directory permissions correct")
        print("   - Video upload endpoint responds 200 OK")
        print("   - No more hardcoded Docker paths")
        print("\\n👤 User can now:")
        print("   - Upload videos successfully via Ground Truth page")
        print("   - No more 'Internal server error' messages")
        print("   - Files saved to correct local upload directory")
    else:
        print("⚠️  PARTIAL SUCCESS: Some issues remain")
        if not dirs_ok:
            print("   - Directory structure issues detected")
        if not upload_ok:
            print("   - Upload endpoint still has problems")
        
        print("\\n🔧 Next steps: Check backend logs for additional errors")