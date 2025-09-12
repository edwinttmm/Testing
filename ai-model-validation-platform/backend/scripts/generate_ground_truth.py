#!/usr/bin/env python3
"""
Generate Ground Truth Script
Creates ground truth data for videos to enable enhanced results comparison
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_ground_truth_for_videos():
    """Generate ground truth for all videos that need it"""
    try:
        from database import SessionLocal
        from models import Video
        from services.ground_truth_service import GroundTruthService
        import asyncio
        
        db = SessionLocal()
        gt_service = GroundTruthService()
        
        print("=" * 80)
        print("🎯 GROUND TRUTH GENERATION")
        print("=" * 80)
        
        # Find videos that need ground truth generation
        videos = db.query(Video).filter(Video.ground_truth_generated == False).all()
        
        if not videos:
            print("✅ No videos need ground truth generation")
            # Check if we have any videos at all
            all_videos = db.query(Video).all()
            print(f"📊 Total videos in database: {len(all_videos)}")
            
            for video in all_videos[:3]:  # Show first 3
                print(f"  Video: {video.filename}")
                print(f"    ID: {video.id}")
                print(f"    Ground Truth Generated: {video.ground_truth_generated}")
                print(f"    File Path: {video.file_path}")
                print()
            
            db.close()
            return True
        
        print(f"📹 Found {len(videos)} videos needing ground truth generation")
        
        async def process_videos():
            for i, video in enumerate(videos, 1):
                print(f"\n🚀 Processing video {i}/{len(videos)}: {video.filename}")
                print(f"   Video ID: {video.id}")
                print(f"   File Path: {video.file_path}")
                
                # Check if file exists
                if not os.path.exists(video.file_path):
                    print(f"❌ File not found: {video.file_path}")
                    continue
                
                try:
                    # Process the video to generate ground truth
                    await gt_service.process_video_async(video.id, video.file_path)
                    print(f"✅ Successfully processed {video.filename}")
                    
                except Exception as e:
                    print(f"❌ Failed to process {video.filename}: {e}")
                    continue
        
        # Run the async processing
        asyncio.run(process_videos())
        
        db.close()
        
        # Verify results
        print("\n" + "=" * 80)
        print("🔍 VERIFICATION")
        print("=" * 80)
        
        db = SessionLocal()
        from models import GroundTruthObject
        
        # Count ground truth objects
        total_gt = db.query(GroundTruthObject).count()
        print(f"📊 Total Ground Truth Objects: {total_gt}")
        
        if total_gt > 0:
            # Show summary by video
            from sqlalchemy import func
            
            gt_by_video = db.query(
                GroundTruthObject.video_id,
                func.count(GroundTruthObject.id).label('count')
            ).group_by(GroundTruthObject.video_id).all()
            
            print("\nGround Truth by Video:")
            for video_id, count in gt_by_video:
                video = db.query(Video).filter(Video.id == video_id).first()
                video_name = video.filename if video else "Unknown"
                print(f"  {video_name} ({video_id}): {count} objects")
                
            # Show summary by class
            gt_by_class = db.query(
                GroundTruthObject.class_label,
                func.count(GroundTruthObject.id).label('count')
            ).group_by(GroundTruthObject.class_label).all()
            
            print("\nGround Truth by Class:")
            for class_label, count in gt_by_class:
                print(f"  {class_label}: {count} objects")
        
        db.close()
        
        print("\n" + "=" * 80)
        print("✅ GROUND TRUTH GENERATION COMPLETE")
        print("=" * 80)
        
        if total_gt > 0:
            print("🎉 Ground truth data is now available for enhanced results!")
            print("💡 You can now run tests and see detailed accuracy metrics.")
        else:
            print("⚠️  No ground truth objects were generated.")
            print("💡 Check video files and ML model availability.")
        
        return True
        
    except Exception as e:
        print(f"❌ Ground truth generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def force_generate_test_ground_truth():
    """Force generate test ground truth data for development"""
    try:
        from database import SessionLocal
        from models import Video, GroundTruthObject
        from crud import create_ground_truth_object
        import uuid
        
        print("🧪 GENERATING TEST GROUND TRUTH DATA")
        print("=" * 50)
        
        db = SessionLocal()
        
        # Get the first video
        video = db.query(Video).first()
        if not video:
            print("❌ No videos found in database")
            return False
        
        print(f"📹 Using video: {video.filename} ({video.id})")
        
        # Delete existing ground truth for this video
        existing_gt = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video.id
        ).delete()
        
        if existing_gt > 0:
            print(f"🗑️  Deleted {existing_gt} existing ground truth objects")
        
        # Create test ground truth objects
        test_objects = [
            {
                "timestamp": 1.0,
                "frame_number": 30,
                "class_label": "pedestrian",
                "x": 100.0,
                "y": 150.0,
                "width": 80.0,
                "height": 180.0,
                "confidence": 0.95
            },
            {
                "timestamp": 2.5,
                "frame_number": 75,
                "class_label": "cyclist",
                "x": 250.0,
                "y": 120.0,
                "width": 60.0,
                "height": 120.0,
                "confidence": 0.88
            },
            {
                "timestamp": 4.0,
                "frame_number": 120,
                "class_label": "pedestrian",
                "x": 320.0,
                "y": 160.0,
                "width": 70.0,
                "height": 170.0,
                "confidence": 0.92
            },
            {
                "timestamp": 6.2,
                "frame_number": 186,
                "class_label": "child",
                "x": 180.0,
                "y": 200.0,
                "width": 50.0,
                "height": 100.0,
                "confidence": 0.85
            }
        ]
        
        created_count = 0
        for obj_data in test_objects:
            try:
                create_ground_truth_object(
                    db=db,
                    video_id=video.id,
                    frame_number=obj_data["frame_number"],
                    timestamp=obj_data["timestamp"],
                    class_label=obj_data["class_label"],
                    x=obj_data["x"],
                    y=obj_data["y"],
                    width=obj_data["width"],
                    height=obj_data["height"],
                    confidence=obj_data["confidence"],
                    validated=True,
                    difficult=False
                )
                created_count += 1
                print(f"✅ Created ground truth: {obj_data['class_label']} at {obj_data['timestamp']}s")
                
            except Exception as e:
                print(f"❌ Failed to create ground truth object: {e}")
        
        # Mark video as having ground truth
        video.ground_truth_generated = True
        db.commit()
        
        print(f"\n✅ Created {created_count} test ground truth objects")
        print(f"📝 Updated video ground truth status")
        
        db.close()
        
        print("\n🎉 Test ground truth generation complete!")
        print("💡 Enhanced results should now show meaningful accuracy metrics.")
        
        return True
        
    except Exception as e:
        print(f"❌ Test ground truth generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("🧪 Running in test mode - generating synthetic ground truth data")
        success = force_generate_test_ground_truth()
    else:
        print("🚀 Running ML-based ground truth generation")
        success = generate_ground_truth_for_videos()
    
    print("\nUsage:")
    print("  python scripts/generate_ground_truth.py           # ML-based generation")
    print("  python scripts/generate_ground_truth.py --test    # Generate test data")
    
    sys.exit(0 if success else 1)