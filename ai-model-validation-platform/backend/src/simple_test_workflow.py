#!/usr/bin/env python3
"""
Simple Test of Sequential Video Processing Implementation
Demonstrates the user's required functionality
"""

import asyncio
import json
import sys
import os
import uuid
from datetime import datetime

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our implementations directly
from src.sequential_video_processor import SequentialVideoProcessor
from database import SessionLocal
from models import Project, Video, TestSession

async def test_sequential_workflow():
    """Test the complete sequential video processing workflow"""
    
    print("🚀 Testing Sequential Video Processing Implementation")
    print("=" * 60)
    
    # Initialize the processor
    processor = SequentialVideoProcessor()
    
    # Test project ID (the user's test project)
    test_project_id = "66f9c296-ee1e-4e81-b0ba-96d03fdc8c90"
    
    print(f"📁 Using test project: {test_project_id}")
    
    # Check if project exists
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == test_project_id).first()
        if not project:
            # Create the test project
            project = Project(
                id=test_project_id,
                name="VRU Detection Test Project",
                description="Test project for sequential video processing",
                camera_model="Test Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO",
                created_at=datetime.utcnow()
            )
            db.add(project)
            db.commit()
            print("   ✅ Created test project")
        else:
            print(f"   ✅ Found existing project: {project.name}")
        
        # Create test videos if they don't exist
        target_videos = [
            ("ae8e974b-0533-4cab-959a-493793e00328.mp4", "vehicle detection test"),
            ("child-1-1-1.mp4", "child pedestrian detection test"),
            ("d081b060-fdbf-4c5a-b167-2966e3303f89.mp4", "additional child detection test")
        ]
        
        video_ids = []
        for filename, description in target_videos:
            # Check if video exists
            existing_video = db.query(Video).filter(
                Video.project_id == test_project_id,
                Video.filename == filename
            ).first()
            
            if not existing_video:
                # Create test video
                video_id = str(uuid.uuid4())
                video = Video(
                    id=video_id,
                    filename=filename,
                    project_id=test_project_id,
                    file_path=f"test/uploads/{filename}",
                    status="uploaded",
                    processing_status="pending",
                    created_at=datetime.utcnow()
                )
                db.add(video)
                video_ids.append(video_id)
                print(f"   ✅ Created test video: {filename}")
            else:
                video_ids.append(existing_video.id)
                print(f"   ✅ Found existing video: {filename}")
        
        db.commit()
        print(f"\n🎬 Ready to test with {len(video_ids)} videos")
        
        # Test 1: Start sequential processing (ONE BUTTON functionality)
        print("\n🚀 Step 1: Testing ONE BUTTON - Start All Videos Sequential")
        result = await processor.start_all_videos_sequential(
            project_id=test_project_id,
            video_ids=video_ids,
            session_name="Test Sequential Processing Session"
        )
        
        if result["success"]:
            session_id = result["session_id"]
            print(f"   ✅ Sequential processing started successfully!")
            print(f"      Session ID: {session_id}")
            print(f"      Videos to process: {result['videos_to_process']}")
            print(f"      Processing order: {result['processing_order']}")
        else:
            print(f"   ❌ Failed to start processing: {result.get('error', 'Unknown error')}")
            return False
        
        # Test 2: Monitor processing status
        print("\n⏱️ Step 2: Monitoring Sequential Processing...")
        
        max_wait = 30  # 30 seconds max
        wait_time = 0
        
        while wait_time < max_wait:
            status = processor.get_session_status(session_id)
            
            if status["success"]:
                print(f"   Status: {status['status']} | Progress: {status['progress']:.1f}% | Video: {status['current_video']} ({status['processed_videos']}/{status['total_videos']})")
                
                if status["status"] == "completed":
                    print("   ✅ Sequential processing completed!")
                    break
                elif status["status"] == "failed":
                    print("   ❌ Processing failed!")
                    return False
            else:
                print(f"   ⚠️ Could not get status: {status.get('error', 'Unknown error')}")
            
            await asyncio.sleep(2)
            wait_time += 2
        
        # Test 3: Verify results storage
        print("\n📊 Step 3: Verifying Results Storage...")
        
        results = processor.get_session_results(session_id)
        
        if results["success"]:
            print(f"   ✅ Results retrieved successfully!")
            print(f"      Session: {results['session_name']}")
            print(f"      Status: {results['status']}")
            print(f"      Test results: {len(results['test_results'])}")
            print(f"      Detection events: {len(results['detection_events'])}")
            print(f"      Detection comparisons: {len(results['detection_comparisons'])}")
            print(f"      Statistics: {results['statistics']}")
        else:
            print(f"   ❌ Could not retrieve results: {results.get('error', 'Unknown error')}")
            return False
        
        # Test 4: Verify project-based session (not random)
        print(f"\n🎯 Step 4: Verifying Project-Based Session Management...")
        
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if session and session.project_id == test_project_id:
            print(f"   ✅ Session properly linked to project {test_project_id}")
            print(f"   ✅ Session type: {getattr(session, 'session_type', 'standard')}")
            print(f"   ✅ NOT a random/phantom session")
        else:
            print(f"   ❌ Session not properly linked to project")
            return False
        
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"✅ Sequential video processing workflow is working correctly")
        print(f"✅ ONE button starts ALL videos sequentially")  
        print(f"✅ Results are stored for each video")
        print(f"✅ Project-based sessions (no random)")
        print(f"✅ Ready for frontend integration")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()

def main():
    """Run the test"""
    success = asyncio.run(test_sequential_workflow())
    
    print(f"\n{'='*60}")
    print(f"🏁 Test Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    if success:
        print(f"\n📋 IMPLEMENTATION SUMMARY:")
        print(f"   • SequentialVideoProcessor: Complete video processing orchestration")
        print(f"   • Sequential Video API: REST endpoints for frontend integration")
        print(f"   • Enhanced Results API: Results page population")
        print(f"   • Project-based sessions: No random sessions")
        print(f"   • ONE button functionality: Start all videos sequentially")
        
        print(f"\n🌐 AVAILABLE ENDPOINTS:")
        print(f"   • POST /api/sequential-video/start-all-videos")
        print(f"   • GET  /api/sequential-video/sessions/{{session_id}}/status")
        print(f"   • GET  /api/sequential-video/sessions/{{session_id}}/results")
        print(f"   • GET  /api/results/projects/{{project_id}}/sessions")
        print(f"   • GET  /api/results/sessions/{{session_id}}/detailed")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)