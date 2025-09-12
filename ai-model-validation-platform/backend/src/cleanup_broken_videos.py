#!/usr/bin/env python3
"""
Cleanup Broken Video Database Records
Removes video records that point to non-existent files
"""

import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Video

def cleanup_broken_videos():
    """Remove video records that point to non-existent files"""
    print("🧹 Cleaning up broken video database records...\n")
    
    # Change to the backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)
    
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        print("❌ uploads/ directory not found!")
        return
    
    db = SessionLocal()
    
    try:
        # Get all videos from database
        all_videos = db.query(Video).all()
        print(f"📊 Found {len(all_videos)} videos in database:")
        
        broken_videos = []
        valid_videos = []
        
        for video in all_videos:
            print(f"   🔍 Checking: {video.id} -> {video.filename}")
            
            # Check if the actual file exists
            file_path = uploads_dir / video.filename
            
            if file_path.exists():
                print(f"     ✅ File exists: {file_path}")
                valid_videos.append(video)
            else:
                print(f"     ❌ File missing: {file_path}")
                broken_videos.append(video)
        
        print(f"\n📈 Summary:")
        print(f"   ✅ Valid videos: {len(valid_videos)}")
        print(f"   ❌ Broken videos: {len(broken_videos)}")
        
        if broken_videos:
            print(f"\n🗑️ Removing {len(broken_videos)} broken video records:")
            
            for video in broken_videos:
                print(f"   🗑️ Removing: {video.id} ({video.filename})")
                db.delete(video)
            
            db.commit()
            print(f"✅ Successfully removed {len(broken_videos)} broken records!")
        else:
            print("✅ No broken video records found!")
        
        # Verify final state
        final_videos = db.query(Video).all()
        print(f"\n📊 Final database state: {len(final_videos)} videos")
        for video in final_videos:
            print(f"   ✅ {video.id}: {video.filename}")
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error cleaning up videos: {e}")
        raise
    
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_broken_videos()