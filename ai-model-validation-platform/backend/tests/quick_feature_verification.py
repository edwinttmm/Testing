#!/usr/bin/env python3
"""
Quick Feature Verification Script
Tests core features with corrected endpoints
"""

import requests
import tempfile
import json

def test_corrected_video_upload():
    """Test the corrected video upload endpoint"""
    print("🎥 Testing Corrected Video Upload Endpoint...")
    
    # Create a small test file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_file.write(b"fake video content for testing")
        tmp_file_path = tmp_file.name
    
    try:
        with open(tmp_file_path, 'rb') as f:
            files = {"file": ("test_upload.mp4", f, "video/mp4")}
            response = requests.post("http://localhost:8000/api/videos", files=files, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("✅ Video upload SUCCESSFUL")
            print(f"Video ID: {result.get('video_id')}")
            print(f"Status: {result.get('status')}")
            return True
        else:
            print("❌ Video upload FAILED")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Video upload ERROR: {e}")
        return False
    finally:
        import os
        os.unlink(tmp_file_path)

def test_project_creation():
    """Test project creation with corrected expectations"""
    print("\n📁 Testing Project Creation...")
    
    project_data = {
        "name": f"Verification Test Project",
        "description": "Quick verification test",
        "cameraModel": "Test Camera",
        "cameraView": "Front-facing VRU",
        "signalType": "GPIO"
    }
    
    try:
        response = requests.post("http://localhost:8000/api/projects", json=project_data, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:  # Accept both as API returns 200
            project = response.json()
            print("✅ Project creation SUCCESSFUL")
            print(f"Project ID: {project.get('id')}")
            print(f"Name: {project.get('name')}")
            return True, project.get('id')
        else:
            print("❌ Project creation FAILED")
            print(f"Response: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Project creation ERROR: {e}")
        return False, None

def test_frontend_health():
    """Quick frontend health check"""
    print("\n🖥️ Testing Frontend Health...")
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            content = response.text
            indicators = {
                "React app": 'id="root"' in content,
                "JavaScript": '<script' in content,
                "Proper size": len(content) > 1000
            }
            
            all_good = all(indicators.values())
            if all_good:
                print("✅ Frontend health EXCELLENT")
                for test, result in indicators.items():
                    print(f"  - {test}: {'✅' if result else '❌'}")
                return True
            else:
                print("⚠️ Frontend health PARTIAL")
                for test, result in indicators.items():
                    print(f"  - {test}: {'✅' if result else '❌'}")
                return False
        else:
            print(f"❌ Frontend not accessible: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Frontend health ERROR: {e}")
        return False

def main():
    """Run all verification tests"""
    print("🚀 AI Model Validation Platform - Quick Feature Verification")
    print("=" * 60)
    
    results = []
    
    # Test corrected video upload
    video_result = test_corrected_video_upload()
    results.append(("Video Upload", video_result))
    
    # Test project creation  
    project_result, project_id = test_project_creation()
    results.append(("Project Creation", project_result))
    
    # Test frontend health
    frontend_result = test_frontend_health()
    results.append(("Frontend Health", frontend_result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} : {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL CORE FEATURES VERIFIED!")
        return 0
    elif passed >= total * 0.7:  # 70% threshold
        print("✅ CORE FEATURES MOSTLY WORKING")
        return 0
    else:
        print("⚠️ SIGNIFICANT ISSUES FOUND")
        return 1

if __name__ == "__main__":
    exit(main())