#!/usr/bin/env python3

import sys
import os
import requests
import json

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'ai-model-validation-platform', 'backend')
sys.path.insert(0, backend_path)

def test_api_endpoints():
    """Test API endpoints directly"""
    base_url = "http://localhost:8000"
    
    print("=== Testing API Endpoints ===")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # Test dashboard stats
    try:
        response = requests.get(f"{base_url}/api/dashboard/stats")
        print(f"Dashboard: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Dashboard failed: {e}")
    
    # Test list projects
    try:
        response = requests.get(f"{base_url}/api/projects")
        print(f"List Projects: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"List projects failed: {e}")
    
    # Test create project
    try:
        project_data = {
            "name": "API Test Project",
            "description": "Testing API creation",
            "camera_model": "Test Camera",
            "camera_view": "front",
            "signal_type": "video"
        }
        response = requests.post(
            f"{base_url}/api/projects",
            headers={"Content-Type": "application/json"},
            data=json.dumps(project_data)
        )
        print(f"Create Project: {response.status_code}")
        if response.status_code == 500:
            print(f"Error response: {response.text}")
        else:
            print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Create project failed: {e}")
    
    # Test list projects again
    try:
        response = requests.get(f"{base_url}/api/projects")
        print(f"List Projects After Create: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"List projects after create failed: {e}")

if __name__ == "__main__":
    test_api_endpoints()