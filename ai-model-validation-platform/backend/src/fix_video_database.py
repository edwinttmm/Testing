#!/usr/bin/env python3
"""
Fix Video Database Records
Creates missing video records for files that exist in uploads/
"""

import os
import sys
from pathlib import Path
import uuid

# Add the parent directory to sys.path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Video, Project
from crud import create_video
import cv2

def get_video_metadata(file_path):
    """Extract video metadata using OpenCV"""
    try:
        cap = cv2.VideoCapture(file_path)
        
        if not cap.isOpened():
            return None
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        duration = frame_count / fps if fps > 0 else 0
        resolution = f"{width}x{height}"
        
        cap.release()
        
        return {
            "fps": fps,
            "duration": duration,
            "resolution": resolution,
            "frame_count": frame_count
        }
    except Exception as e:
        print(f"⚠️ Error getting metadata for {file_path}: {e}")
        return None

def ensure_default_project(db):
    """Ensure a default project exists for videos"""
    # Check if default project exists
    default_project = db.query(Project).first()
    
    if not default_project:
        # Create a default project
        from schemas import ProjectCreate
        
        project_data = ProjectCreate(
            name="Default Project",
            description="Default project for video files",
            cameraModel="Generic Camera",
            cameraView="Front-facing VRU",
            signalType="GPIO"
        )
        
        db_project = Project(
            id=str(uuid.uuid4()),
            name=project_data.name,
            description=project_data.description,
            camera_model=project_data.camera_model,
            camera_view=project_data.camera_view,
            signal_type=project_data.signal_type,
            status="Active",
            owner_id="system"
        )
        
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        
        print(f"✅ Created default project: {db_project.id}")
        return db_project
    
    return default_project

def fix_video_records():
    """Fix missing video records in database"""
    print("🔧 Fixing video database records...\n")
    
    # Change to the backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)
    
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        print("❌ uploads/ directory not found!")
        return
    
    db = SessionLocal()
    
    try:
        # Get all existing video IDs from database
        existing_videos = db.query(Video).all()
        existing_ids = {video.id for video in existing_videos}
        
        print(f"📊 Found {len(existing_videos)} videos in database:")
        for video in existing_videos:
            print(f"   - {video.id}: {video.filename}")
        
        # Get all video files in uploads
        video_files = list(uploads_dir.glob("*.mp4"))
        print(f"\n📁 Found {len(video_files)} video files in uploads/:")
        
        for file_path in video_files:
            print(f"   - {file_path.name}")
        
        # Ensure default project exists
        default_project = ensure_default_project(db)
        
        # Process each video file
        created_count = 0
        
        for video_file in video_files:
            # Extract video ID from filename (assuming UUID format)
            video_id = video_file.stem
            
            # Skip if video already exists in database
            if video_id in existing_ids:
                print(f"✅ Video {video_id} already in database")
                continue
            
            # Check if filename looks like a UUID
            try:
                uuid.UUID(video_id)
            except ValueError:
                # Not a UUID, generate one
                print(f"⚠️ {video_file.name} is not UUID format, generating new ID...")
                video_id = str(uuid.uuid4())
            
            # Get file size
            file_size = video_file.stat().st_size
            
            # Get video metadata
            metadata = get_video_metadata(str(video_file))
            
            # Create video record
            db_video = Video(
                id=video_id,
                filename=video_file.name,
                file_path=str(video_file.absolute()),
                file_size=file_size,
                project_id=default_project.id,
                status="uploaded",
                processing_status="ready",
                ground_truth_generated=False,
                fps=metadata["fps"] if metadata else None,
                duration=metadata["duration"] if metadata else None,
                resolution=metadata["resolution"] if metadata else None
            )
            
            db.add(db_video)
            created_count += 1
            
            print(f"✅ Created video record: {video_id}")
            if metadata:
                print(f"   📊 Duration: {metadata['duration']:.2f}s")
                print(f"   🎬 FPS: {metadata['fps']:.2f}")
                print(f"   📏 Resolution: {metadata['resolution']}")
            print(f"   📁 File: {video_file.name} ({file_size} bytes)")
        
        # Commit all changes
        db.commit()
        
        print(f"\n🎉 Successfully created {created_count} video records!")
        
        # Verify the specific video we need
        target_video_id = "21b8d8cf-80e3-42f0-b64b-83390f0345ee"
        target_video = db.query(Video).filter(Video.id == target_video_id).first()
        
        if target_video:
            print(f"\n✅ Target video now in database:")
            print(f"   🆔 ID: {target_video.id}")
            print(f"   📁 File: {target_video.filename}")
            print(f"   📂 Path: {target_video.file_path}")
            print(f"   📊 Size: {target_video.file_size}")
            print(f"   ⏱️ Duration: {target_video.duration}")
        else:
            print(f"\n⚠️ Target video {target_video_id} still not found")
            # List all videos now
            all_videos = db.query(Video).all()
            print(f"📊 Total videos now: {len(all_videos)}")
            for video in all_videos:
                print(f"   - {video.id}: {video.filename}")
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error fixing video records: {e}")
        raise
    
    finally:
        db.close()

if __name__ == "__main__":
    fix_video_records()