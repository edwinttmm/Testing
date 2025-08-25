#!/usr/bin/env python3
"""
Script to fix the specific orphaned video entry that's causing 404 errors
"""

import os
import sys
import requests
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.append(str(backend_dir))

def fix_orphaned_video_via_api():
    """Remove the specific orphaned video entry via API calls"""
    
    api_base = "http://155.138.239.131:8000/api"
    orphaned_filename = "30adaef3-8430-476d-a126-6606a6ae2a6f.mp4"
    
    try:
        # Get current videos
        response = requests.get(f"{api_base}/videos")
        response.raise_for_status()
        videos_data = response.json()
        
        print(f"Found {videos_data['total']} videos in database")
        
        # Find the orphaned video
        orphaned_video = None
        for video in videos_data['videos']:
            if video['filename'] == orphaned_filename:
                orphaned_video = video
                break
        
        if not orphaned_video:
            print(f"No orphaned video found with filename: {orphaned_filename}")
            return
        
        print(f"Found orphaned video: {orphaned_video['filename']} (ID: {orphaned_video['id']})")
        
        # Check if physical file exists
        uploads_dir = backend_dir / "uploads"
        video_path = uploads_dir / orphaned_filename
        
        if video_path.exists():
            print(f"Physical file exists: {video_path}")
            print("No cleanup needed")
            return
        
        print(f"Physical file missing: {video_path}")
        print("This video entry should be removed from the database")
        
        # For now, just report the issue - actual cleanup would require database access
        print("\nTo fix this issue, the database entry should be deleted.")
        print(f"Video ID to delete: {orphaned_video['id']}")
        
    except requests.RequestException as e:
        print(f"API request failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

def list_video_file_status():
    """List all video files and their database status"""
    
    uploads_dir = backend_dir / "uploads"
    api_base = "http://155.138.239.131:8000/api"
    
    try:
        # Get database videos
        response = requests.get(f"{api_base}/videos")
        response.raise_for_status()
        videos_data = response.json()
        
        db_videos = {video['filename']: video for video in videos_data['videos']}
        
        # Get physical files
        video_files = list(uploads_dir.glob("*.mp4"))
        
        print("\n=== VIDEO FILE STATUS ===")
        print(f"Database entries: {len(db_videos)}")
        print(f"Physical files: {len(video_files)}")
        
        print("\n--- Files with database entries ---")
        for filename, video in db_videos.items():
            file_exists = (uploads_dir / filename).exists()
            status = "✓ EXISTS" if file_exists else "✗ MISSING"
            print(f"{status}: {filename}")
        
        print("\n--- Files without database entries ---")
        for file_path in video_files:
            if file_path.name not in db_videos:
                print(f"NO DB ENTRY: {file_path.name}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("=== Orphaned Video Cleanup Tool ===")
    fix_orphaned_video_via_api()
    list_video_file_status()