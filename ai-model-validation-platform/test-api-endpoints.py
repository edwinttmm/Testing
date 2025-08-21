#!/usr/bin/env python3
"""
Test script to verify backend API endpoints are working correctly.
"""
import requests
import json

def test_api_endpoints():
    """Test that backend API endpoints return proper video data"""
    
    base_url = "http://155.138.239.131:8000"
    central_store_project_id = "00000000-0000-0000-0000-000000000000"
    
    print("🧪 Testing Backend API Endpoints...")
    print(f"Backend API: {base_url}")
    print(f"Central Store Project ID: {central_store_project_id}")
    
    try:
        # Test 1: Health check
        print("\n📊 Testing health endpoint...")
        response = requests.get(f"{base_url}/health")
        print(f"Health Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Health Response: {response.json()}")
        
        # Test 2: Get all videos
        print("\n📊 Testing /api/videos endpoint...")
        response = requests.get(f"{base_url}/api/videos")
        print(f"All Videos Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            videos = data.get("videos", [])
            print(f"Total videos: {len(videos)}")
            if videos:
                print("Sample video:")
                sample = videos[0]
                print(f"  ID: {sample.get('id')}")
                print(f"  Filename: {sample.get('filename')}")
                print(f"  URL: {sample.get('url')}")
                print(f"  Status: {sample.get('status')}")
        
        # Test 3: Get central store project videos
        print(f"\n📊 Testing /api/projects/{central_store_project_id}/videos endpoint...")
        response = requests.get(f"{base_url}/api/projects/{central_store_project_id}/videos")
        print(f"Central Store Videos Status: {response.status_code}")
        if response.status_code == 200:
            videos = response.json()
            print(f"Central store videos: {len(videos)}")
            if videos:
                print("Sample central store video:")
                sample = videos[0]
                print(f"  ID: {sample.get('id')}")
                print(f"  Filename: {sample.get('filename')}")
                print(f"  URL: {sample.get('url')}")
                print(f"  Status: {sample.get('status')}")
                print(f"  Project ID: {sample.get('projectId')}")
        
        # Test 4: Check if a specific video URL is accessible
        if response.status_code == 200 and videos:
            sample_url = videos[0].get('url')
            if sample_url:
                print(f"\n🔗 Testing video URL accessibility: {sample_url}")
                try:
                    head_response = requests.head(sample_url, timeout=5)
                    print(f"Video URL Status: {head_response.status_code}")
                    if head_response.status_code == 200:
                        print("✅ Video URL is accessible")
                    else:
                        print(f"⚠️ Video URL returned status {head_response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"❌ Video URL not accessible: {e}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_endpoints()
    if success:
        print("\n🎉 API endpoint tests completed!")
    else:
        print("\n💥 API endpoint tests failed!")