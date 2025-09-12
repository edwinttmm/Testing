#!/usr/bin/env python3
"""
Test workflow to demonstrate the complete data pipeline for test results

This script will:
1. Create a test project and video
2. Create a test session with detection events
3. Complete the test session 
4. Verify results appear in the API
5. Test the complete pipeline from execution to results display
"""

import requests
import json
import time
import uuid
from typing import Dict, Any, List

BASE_URL = "http://localhost:8000"

def create_test_project() -> str:
    """Create a test project"""
    project_data = {
        "name": "Test Results Pipeline Demo",
        "description": "Testing the complete data pipeline",
        "camera_model": "TestCam3000",
        "camera_view": "Front-facing VRU",
        "lens_type": "Standard",
        "resolution": "1920x1080",
        "frame_rate": 30,
        "signal_type": "GPIO"
    }
    
    response = requests.post(f"{BASE_URL}/api/projects", json=project_data)
    if response.status_code != 200:
        raise Exception(f"Failed to create project: {response.text}")
    
    project = response.json()
    print(f"✅ Created project: {project['name']} (ID: {project['id']})")
    return project['id']

def create_test_video(project_id: str) -> str:
    """Create a test video for the project"""
    # First, let's create a video record manually using the database
    video_data = {
        "project_id": project_id,
        "filename": "test_video.mp4",
        "file_path": "/mock/path/test_video.mp4",
        "file_size": 100000000,
        "duration": 120.0,
        "fps": 30.0,
        "resolution": "1920x1080",
        "status": "completed",
        "ground_truth_generated": True
    }
    
    # We need to create this via SQL since there's no direct API endpoint
    from database import SessionLocal
    from models import Video
    import uuid
    
    db = SessionLocal()
    try:
        video = Video(
            id=str(uuid.uuid4()),
            project_id=project_id,
            filename="test_video.mp4",
            file_path="/mock/path/test_video.mp4",
            file_size=100000000,
            duration=120.0,
            fps=30.0,
            resolution="1920x1080",
            status="completed",
            ground_truth_generated=True
        )
        db.add(video)
        db.commit()
        
        print(f"✅ Created video: {video.filename} (ID: {video.id})")
        return video.id
    finally:
        db.close()

def create_test_session(project_id: str, video_id: str) -> str:
    """Create a test session manually"""
    from database import SessionLocal
    from models import TestSession
    from datetime import datetime
    import uuid
    
    db = SessionLocal()
    try:
        session_id = str(uuid.uuid4())
        test_session = TestSession(
            id=session_id,
            name=f"Pipeline Test Session {session_id[:8]}",
            project_id=project_id,
            video_id=video_id,
            tolerance_ms=100,
            status="running",
            session_type="user_created",
            started_at=datetime.utcnow()
        )
        
        db.add(test_session)
        db.commit()
        
        print(f"✅ Created test session: {test_session.name} (ID: {session_id})")
        return session_id
    finally:
        db.close()

def complete_test_session_with_results(session_id: str) -> bool:
    """Complete test session using our service"""
    try:
        from services.test_execution_service import test_execution_service
        success = test_execution_service.complete_test_session(session_id)
        if success:
            print(f"✅ Test session {session_id} completed with generated results")
        else:
            print(f"❌ Failed to complete test session {session_id}")
        return success
    except Exception as e:
        print(f"❌ Error completing session: {e}")
        return False

def verify_results_api(session_id: str) -> bool:
    """Verify results are available via API"""
    try:
        # Check results API
        response = requests.get(f"{BASE_URL}/api/test-sessions/{session_id}/results")
        if response.status_code == 200:
            results = response.json()
            print(f"✅ Results API working - Accuracy: {results.get('accuracy', 0):.1f}%, Total: {results.get('totalDetections', 0)}")
            return True
        else:
            print(f"❌ Results API failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking results API: {e}")
        return False

def verify_enhanced_results_api(project_id: str, session_id: str) -> bool:
    """Verify enhanced results API"""
    try:
        # Check enhanced results API
        response = requests.get(f"{BASE_URL}/api/results/projects/{project_id}/sessions")
        if response.status_code == 200:
            sessions = response.json()
            target_session = next((s for s in sessions if s['session_id'] == session_id), None)
            if target_session:
                print(f"✅ Enhanced Results API working - Found session with {target_session.get('detection_events', 0)} events")
                return True
            else:
                print(f"❌ Enhanced Results API - session not found in response")
                return False
        else:
            print(f"❌ Enhanced Results API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking enhanced results API: {e}")
        return False

def test_frontend_api_compatibility() -> bool:
    """Test APIs that the frontend uses"""
    try:
        # Test projects list
        response = requests.get(f"{BASE_URL}/api/projects")
        if response.status_code != 200:
            print(f"❌ Projects API failed")
            return False
        
        projects = response.json()
        print(f"✅ Projects API - Found {len(projects)} projects")
        
        # Test test sessions API (what Results.tsx uses)
        if projects:
            project_id = projects[0]['id']
            response = requests.get(f"{BASE_URL}/api/projects/{project_id}/test-sessions")
            if response.status_code == 200:
                sessions = response.json()
                print(f"✅ Test Sessions API - Found {len(sessions)} sessions")
                return True
            else:
                print(f"❌ Test Sessions API failed: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing frontend APIs: {e}")
        return False

def main():
    """Run the complete workflow test"""
    print("🚀 Testing Complete Data Pipeline for Test Results")
    print("=" * 60)
    
    try:
        # Step 1: Create test project
        project_id = create_test_project()
        
        # Step 2: Create test video
        video_id = create_test_video(project_id)
        
        # Step 3: Create test session
        session_id = create_test_session(project_id, video_id)
        
        # Step 4: Complete test session with results
        success = complete_test_session_with_results(session_id)
        if not success:
            print("❌ Workflow failed at session completion")
            return False
        
        # Wait a moment for completion
        time.sleep(1)
        
        # Step 5: Verify results via standard API
        results_ok = verify_results_api(session_id)
        
        # Step 6: Verify enhanced results API
        enhanced_ok = verify_enhanced_results_api(project_id, session_id)
        
        # Step 7: Test frontend compatibility
        frontend_ok = test_frontend_api_compatibility()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Pipeline Test Results:")
        print(f"   Project Creation: ✅")
        print(f"   Video Creation: ✅")  
        print(f"   Session Creation: ✅")
        print(f"   Session Completion: {'✅' if success else '❌'}")
        print(f"   Results API: {'✅' if results_ok else '❌'}")
        print(f"   Enhanced API: {'✅' if enhanced_ok else '❌'}")
        print(f"   Frontend APIs: {'✅' if frontend_ok else '❌'}")
        
        overall_success = all([success, results_ok, enhanced_ok, frontend_ok])
        print(f"\n🎯 Overall Pipeline: {'✅ WORKING' if overall_success else '❌ NEEDS FIXES'}")
        
        if overall_success:
            print(f"\n🌟 SUCCESS: Test results should now appear in the Results page!")
            print(f"   - Session ID: {session_id}")
            print(f"   - Project ID: {project_id}")
            print(f"   - Check the Results page in the frontend to see the data")
        else:
            print(f"\n⚠️  Some issues found - check the logs above")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Workflow failed with error: {e}")
        return False

if __name__ == "__main__":
    main()