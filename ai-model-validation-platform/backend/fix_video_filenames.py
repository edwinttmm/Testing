#!/usr/bin/env python3
"""
Quick fix for video filename mismatch between database and actual files
"""
import os
import sys
from pathlib import Path
from database import SessionLocal, engine
from models import Video
from sqlalchemy.orm import Session

def fix_video_filenames():
    print("🔧 Fixing video filename mismatch...")
    
    # Get actual files in uploads directory
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        print("❌ Uploads directory not found")
        return
    
    actual_files = list(uploads_dir.glob("*.mp4"))
    print(f"📁 Found {len(actual_files)} actual video files:")
    for f in actual_files:
        print(f"   - {f.name}")
    
    # Get database records
    with SessionLocal() as db:
        videos = db.query(Video).all()
        print(f"📊 Found {len(videos)} video records in database")
        
        for video in videos:
            print(f"\n🎥 Video ID: {video.id}")
            print(f"   Current filename: {video.filename}")
            
            # Check if current filename exists
            current_file = uploads_dir / video.filename
            if current_file.exists():
                print("   ✅ File exists - no fix needed")
                continue
            
            # Find a matching file (by size or take the first available)
            if actual_files:
                # Use the first available file as replacement
                new_filename = actual_files[0].name
                
                print(f"   🔄 Updating to: {new_filename}")
                video.filename = new_filename
                
                # Remove this file from available list
                actual_files.pop(0)
            else:
                print("   ❌ No available files to assign")
        
        # Commit changes
        try:
            db.commit()
            print("\n✅ Database updated successfully!")
        except Exception as e:
            print(f"\n❌ Error updating database: {e}")
            db.rollback()

if __name__ == "__main__":
    fix_video_filenames()