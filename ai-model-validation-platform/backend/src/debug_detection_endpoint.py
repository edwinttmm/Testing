#!/usr/bin/env python3
"""
Diagnostic Script for Detection Pipeline Endpoint
Identifies the exact cause of the 500 error
"""

import os
import sys
import traceback
from pathlib import Path

# Add the parent directory to sys.path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    
    try:
        from database import SessionLocal
        print("✅ Database import successful")
    except Exception as e:
        print(f"❌ Database import failed: {e}")
        return False
    
    try:
        from models import Video
        print("✅ Models import successful")
    except Exception as e:
        print(f"❌ Models import failed: {e}")
        return False
    
    try:
        from crud import get_video
        print("✅ CRUD import successful")
    except Exception as e:
        print(f"❌ CRUD import failed: {e}")
        return False
    
    try:
        from services.detection_pipeline_service import DetectionPipeline
        print("✅ Detection pipeline service import successful")
    except Exception as e:
        print(f"❌ Detection pipeline service import failed: {e}")
        return False
    
    try:
        from schemas import DetectionPipelineConfigSchema, DetectionPipelineResponse
        print("✅ Schema imports successful")
    except Exception as e:
        print(f"❌ Schema imports failed: {e}")
        return False
    
    return True

def test_database_connection():
    """Test database connection and video lookup"""
    print("\n🔍 Testing database connection...")
    
    try:
        from database import SessionLocal
        from crud import get_video
        
        db = SessionLocal()
        video_id = "21b8d8cf-80e3-42f0-b64b-83390f0345ee"
        
        # Test video lookup
        video = get_video(db=db, video_id=video_id)
        
        if video:
            print(f"✅ Video found: {video.id}")
            print(f"   📁 File path: {video.file_path}")
            print(f"   📊 File size: {video.file_size}")
            print(f"   🎬 Project: {video.project_id}")
            
            # Check if file exists on disk
            if video.file_path and os.path.exists(video.file_path):
                print(f"✅ Video file exists on disk")
                file_size = os.path.getsize(video.file_path)
                print(f"   📏 Actual file size: {file_size} bytes")
            else:
                print(f"❌ Video file not found on disk: {video.file_path}")
                
                # Try alternative path
                alt_path = f"uploads/{video_id}.mp4"
                if os.path.exists(alt_path):
                    print(f"✅ Found video at alternative path: {alt_path}")
                else:
                    print(f"❌ Alternative path also not found: {alt_path}")
        else:
            print(f"❌ Video not found in database: {video_id}")
            
            # List all videos in database
            from models import Video
            all_videos = db.query(Video).all()
            print(f"📊 Total videos in database: {len(all_videos)}")
            if all_videos:
                print("   Available video IDs:")
                for v in all_videos[:5]:  # Show first 5
                    print(f"   - {v.id}")
        
        db.close()
        return video is not None
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        traceback.print_exc()
        return False

def test_detection_service():
    """Test detection pipeline service initialization"""
    print("\n🔍 Testing detection pipeline service...")
    
    try:
        from services.detection_pipeline_service import DetectionPipeline
        
        # Initialize service
        pipeline = DetectionPipeline()
        print("✅ Detection pipeline initialized")
        
        # Test async initialization
        import asyncio
        
        async def test_init():
            try:
                await pipeline.initialize()
                print("✅ Detection pipeline async initialization successful")
                return True
            except Exception as e:
                print(f"❌ Detection pipeline initialization failed: {e}")
                traceback.print_exc()
                return False
        
        result = asyncio.run(test_init())
        return result
        
    except Exception as e:
        print(f"❌ Detection service test failed: {e}")
        traceback.print_exc()
        return False

def test_schema_validation():
    """Test schema validation"""
    print("\n🔍 Testing schema validation...")
    
    try:
        from schemas import DetectionPipelineConfigSchema
        
        # Test with the actual request data
        test_data = {
            "video_id": "21b8d8cf-80e3-42f0-b64b-83390f0345ee",
            "confidence_threshold": 0.5
        }
        
        # Validate schema
        config = DetectionPipelineConfigSchema(**test_data)
        print("✅ Schema validation successful")
        print(f"   🆔 Video ID: {config.video_id}")
        print(f"   🎯 Confidence: {config.confidence_threshold}")
        print(f"   🧠 Model: {config.model_name}")
        print(f"   📊 Target classes: {config.target_classes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        traceback.print_exc()
        return False

def test_end_to_end_flow():
    """Test the complete detection flow"""
    print("\n🔍 Testing end-to-end detection flow...")
    
    try:
        # Import everything we need
        from database import SessionLocal
        from crud import get_video
        from services.detection_pipeline_service import DetectionPipeline
        from schemas import DetectionPipelineConfigSchema
        
        # Create request
        request_data = {
            "video_id": "21b8d8cf-80e3-42f0-b64b-83390f0345ee",
            "confidence_threshold": 0.5
        }
        
        request = DetectionPipelineConfigSchema(**request_data)
        print("✅ Request schema validated")
        
        # Get database session
        db = SessionLocal()
        
        # Look up video
        video = get_video(db=db, video_id=request.video_id)
        if not video:
            print(f"❌ Video not found: {request.video_id}")
            return False
        
        print(f"✅ Video found: {video.id}")
        
        # Check file exists
        if not video.file_path or not os.path.exists(video.file_path):
            print(f"❌ Video file not found: {video.file_path}")
            
            # Try to fix the path
            video_file_path = f"uploads/{request.video_id}.mp4"
            if os.path.exists(video_file_path):
                print(f"✅ Found video file at: {video_file_path}")
                # Update video record with correct path
                video.file_path = os.path.abspath(video_file_path)
                db.commit()
                print(f"✅ Updated video file path in database")
            else:
                print(f"❌ Video file not found anywhere")
                db.close()
                return False
        
        print(f"✅ Video file exists: {video.file_path}")
        
        # Test detection pipeline
        pipeline = DetectionPipeline()
        
        pipeline_config = {
            "confidence_threshold": request.confidence_threshold,
            "nms_threshold": request.nms_threshold,
            "target_classes": request.target_classes
        }
        
        print("✅ Pipeline configuration prepared")
        
        # Test async process (simplified)
        import asyncio
        
        async def test_process():
            try:
                await pipeline.initialize()
                print("✅ Pipeline initialized")
                
                # Test basic video processing (without full storage to avoid long runtime)
                detections = await pipeline.process_video(video.file_path, video.id, pipeline_config)
                print(f"✅ Video processing successful: {len(detections)} detections")
                
                return True
                
            except Exception as e:
                print(f"❌ Video processing failed: {e}")
                traceback.print_exc()
                return False
        
        result = asyncio.run(test_process())
        
        db.close()
        return result
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all diagnostic tests"""
    print("🚀 Starting Detection Pipeline Diagnostics\n")
    
    # Change to the backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)
    print(f"📁 Working directory: {os.getcwd()}")
    
    tests = [
        ("Imports", test_imports),
        ("Database Connection", test_database_connection),
        ("Schema Validation", test_schema_validation),
        ("Detection Service", test_detection_service),
        ("End-to-End Flow", test_end_to_end_flow),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🔧 Running: {test_name}")
        print(f"{'='*50}")
        
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 DIAGNOSTIC SUMMARY")
    print(f"{'='*50}")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    failed_tests = [name for name, passed in results.items() if not passed]
    
    if failed_tests:
        print(f"\n❌ Failed tests: {', '.join(failed_tests)}")
        print("\n🔧 RECOMMENDED FIXES:")
        
        if "Database Connection" in failed_tests:
            print("1. Check if video exists in database")
            print("2. Verify video file path is correct")
            print("3. Update video record with correct file path")
        
        if "Detection Service" in failed_tests:
            print("4. Check ML dependencies (torch, ultralytics)")
            print("5. Verify model file can be downloaded")
            print("6. Check file permissions and disk space")
        
        if "End-to-End Flow" in failed_tests:
            print("7. Run individual components separately")
            print("8. Check for missing environment variables")
            print("9. Verify detection pipeline service initialization")
    else:
        print("\n✅ All tests passed! The detection endpoint should work.")

if __name__ == "__main__":
    main()