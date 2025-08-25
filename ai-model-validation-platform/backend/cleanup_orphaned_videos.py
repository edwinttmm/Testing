#!/usr/bin/env python3
"""
Script to clean up orphaned video database entries where the physical files don't exist
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.append(str(backend_dir))

from database import SessionLocal
from models import Video

def cleanup_orphaned_videos():
    """Remove database entries for videos where the physical files don't exist"""
    
    uploads_dir = backend_dir / "uploads"
    
    with SessionLocal() as db:
        # Get all videos from database
        videos = db.query(Video).all()
        print(f"Found {len(videos)} video entries in database")
        
        orphaned_videos = []
        for video in videos:
            video_path = uploads_dir / video.filename
            if not video_path.exists():
                orphaned_videos.append(video)
                print(f"Orphaned video found: {video.filename} (ID: {video.id})")
        
        if orphaned_videos:
            print(f"\nFound {len(orphaned_videos)} orphaned video entries")
            
            # Ask for confirmation
            response = input("Delete orphaned database entries? (y/N): ").lower()
            if response in ['y', 'yes']:
                for video in orphaned_videos:
                    print(f"Deleting database entry for: {video.filename}")
                    db.delete(video)
                
                db.commit()
                print(f"Successfully deleted {len(orphaned_videos)} orphaned video entries")
            else:
                print("Cleanup cancelled")
        else:
            print("No orphaned video entries found")
        
        # Show existing files without database entries
        existing_files = list(uploads_dir.glob("*.mp4"))
        db_filenames = {video.filename for video in db.query(Video).all()}
        
        files_without_db_entries = []
        for file_path in existing_files:
            if file_path.name not in db_filenames:
                files_without_db_entries.append(file_path.name)
        
        if files_without_db_entries:
            print(f"\nFound {len(files_without_db_entries)} video files without database entries:")
            for filename in files_without_db_entries:
                print(f"  - {filename}")

if __name__ == "__main__":
    cleanup_orphaned_videos()