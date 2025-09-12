"""
Basic Upload Functionality Test
==============================

Simple test to verify core upload functionality works correctly.
This test focuses on essential upload features without complex dependencies.
"""

import os
import sys
import tempfile
import json
import requests
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_backend_availability():
    """Test if backend server is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_api_docs_available():
    """Test if API documentation is accessible"""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        return response.status_code == 200
    except:
        return False

def create_test_project():
    """Create a test project for video uploads"""
    project_data = {
        "name": "Basic Upload Test Project",
        "description": "Testing basic upload functionality",
        "camera_model": "TestCamera",
        "camera_view": "Front-facing VRU",
        "signal_type": "GPIO"
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/projects",
            json=project_data,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()["id"]
        else:
            print(f"Project creation failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Project creation error: {e}")
        return None

def test_video_upload(project_id):
    """Test basic video file upload"""
    # Create a small test video file
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        # Write some fake video content
        test_content = b'fake mp4 video content for testing' * 100  # ~3.4KB
        temp_file.write(test_content)
        temp_file.flush()
        
        try:
            # Upload the file
            with open(temp_file.name, 'rb') as f:
                files = {'file': ('test_video.mp4', f, 'video/mp4')}
                response = requests.post(
                    f"http://localhost:8000/api/projects/{project_id}/videos",
                    files=files,
                    timeout=30
                )
            
            # Clean up temp file
            os.unlink(temp_file.name)
            
            if response.status_code == 200:
                video_data = response.json()
                return {
                    'success': True,
                    'video_id': video_data.get('id'),
                    'filename': video_data.get('filename'),
                    'file_size': video_data.get('file_size'),
                    'status': video_data.get('status')
                }
            else:
                return {
                    'success': False,
                    'error': f"Upload failed: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_file.name)
            except:
                pass
            
            return {
                'success': False,
                'error': f"Upload exception: {e}"
            }

def test_invalid_file_upload(project_id):
    """Test upload with invalid file type"""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        temp_file.write(b'This is not a video file')
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as f:
                files = {'file': ('invalid_file.txt', f, 'text/plain')}
                response = requests.post(
                    f"http://localhost:8000/api/projects/{project_id}/videos",
                    files=files,
                    timeout=30
                )
            
            os.unlink(temp_file.name)
            
            # Should reject invalid file type
            return {
                'success': response.status_code in [400, 422],
                'status_code': response.status_code,
                'response_text': response.text
            }
            
        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except:
                pass
            
            return {
                'success': False,
                'error': str(e)
            }

def test_project_video_listing(project_id):
    """Test listing videos in a project"""
    try:
        response = requests.get(
            f"http://localhost:8000/api/projects/{project_id}/videos",
            timeout=10
        )
        
        if response.status_code == 200:
            videos = response.json()
            return {
                'success': True,
                'video_count': len(videos),
                'videos': videos
            }
        else:
            return {
                'success': False,
                'error': f"Listing failed: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def main():
    """Run basic upload functionality tests"""
    print("🧪 Basic Upload Functionality Test")
    print("=" * 50)
    
    results = {}
    
    # Test 1: Backend Availability
    print("\n1. Testing backend availability...")
    backend_available = test_backend_availability()
    results['backend_available'] = backend_available
    
    if backend_available:
        print("✅ Backend is running")
    else:
        print("❌ Backend is not available")
        print("   Please start the backend server with: uvicorn main:app --reload")
        return results
    
    # Test 2: API Documentation
    print("\n2. Testing API documentation...")
    docs_available = test_api_docs_available()
    results['docs_available'] = docs_available
    
    if docs_available:
        print("✅ API documentation is accessible")
    else:
        print("⚠️  API documentation not accessible")
    
    # Test 3: Create Test Project
    print("\n3. Creating test project...")
    project_id = create_test_project()
    results['project_creation'] = project_id is not None
    
    if project_id:
        print(f"✅ Test project created: {project_id}")
        results['project_id'] = project_id
    else:
        print("❌ Failed to create test project")
        return results
    
    # Test 4: Valid File Upload
    print("\n4. Testing valid video upload...")
    upload_result = test_video_upload(project_id)
    results['valid_upload'] = upload_result
    
    if upload_result['success']:
        print(f"✅ Video uploaded successfully")
        print(f"   Video ID: {upload_result.get('video_id')}")
        print(f"   Filename: {upload_result.get('filename')}")
        print(f"   File Size: {upload_result.get('file_size')} bytes")
        print(f"   Status: {upload_result.get('status')}")
    else:
        print(f"❌ Video upload failed: {upload_result.get('error')}")
    
    # Test 5: Invalid File Upload
    print("\n5. Testing invalid file rejection...")
    invalid_result = test_invalid_file_upload(project_id)
    results['invalid_upload'] = invalid_result
    
    if invalid_result['success']:
        print(f"✅ Invalid file properly rejected (status: {invalid_result.get('status_code')})")
    else:
        print(f"❌ Invalid file handling failed: {invalid_result.get('error')}")
    
    # Test 6: Video Listing
    print("\n6. Testing video listing...")
    listing_result = test_project_video_listing(project_id)
    results['video_listing'] = listing_result
    
    if listing_result['success']:
        print(f"✅ Video listing works - found {listing_result.get('video_count')} videos")
    else:
        print(f"❌ Video listing failed: {listing_result.get('error')}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    test_count = 0
    passed_count = 0
    
    test_results = [
        ('Backend Availability', results.get('backend_available', False)),
        ('API Documentation', results.get('docs_available', False)),
        ('Project Creation', results.get('project_creation', False)),
        ('Valid Upload', results.get('valid_upload', {}).get('success', False)),
        ('Invalid Upload Rejection', results.get('invalid_upload', {}).get('success', False)),
        ('Video Listing', results.get('video_listing', {}).get('success', False))
    ]
    
    for test_name, passed in test_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:25} {status}")
        test_count += 1
        if passed:
            passed_count += 1
    
    success_rate = (passed_count / test_count) * 100 if test_count > 0 else 0
    
    print(f"\nResults: {passed_count}/{test_count} tests passed ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("🎉 Upload system is functioning well!")
        status = "HEALTHY"
    elif success_rate >= 50:
        print("⚠️  Upload system has some issues")
        status = "NEEDS ATTENTION"
    else:
        print("❌ Upload system has major problems")
        status = "CRITICAL"
    
    # Save results to file
    results['summary'] = {
        'total_tests': test_count,
        'passed_tests': passed_count,
        'success_rate': success_rate,
        'status': status
    }
    
    results_file = backend_dir / "tests" / "basic_upload_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    return results

if __name__ == "__main__":
    results = main()
    
    # Exit with error code if critical tests failed
    backend_ok = results.get('backend_available', False)
    upload_ok = results.get('valid_upload', {}).get('success', False)
    
    if backend_ok and upload_ok:
        exit(0)  # Success
    else:
        exit(1)  # Failure