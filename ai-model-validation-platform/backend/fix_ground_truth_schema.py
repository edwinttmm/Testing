#!/usr/bin/env python3
"""
Fix ground truth database schema and add missing endpoint
"""

import sqlite3
import os
import sys
import logging

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from database import engine
from sqlalchemy import text

def fix_schema():
    """Fix the ground truth objects table schema"""
    try:
        print("🔧 Fixing ground truth objects table schema...")
        
        # Connect to database
        with engine.connect() as conn:
            # Check if tracking_id column exists
            result = conn.execute(text("PRAGMA table_info(ground_truth_objects);"))
            columns = [row[1] for row in result.fetchall()]
            
            print(f"📋 Current columns: {columns}")
            
            if 'tracking_id' not in columns:
                print("➕ Adding missing tracking_id column...")
                conn.execute(text("ALTER TABLE ground_truth_objects ADD COLUMN tracking_id TEXT;"))
                conn.commit()
                print("✅ tracking_id column added successfully!")
            else:
                print("✅ tracking_id column already exists")
                
        return True
        
    except Exception as e:
        print(f"❌ Error fixing schema: {e}")
        return False

def add_ground_truth_endpoint():
    """Add the missing /api/videos/{video_id}/generate-ground-truth endpoint"""
    
    endpoint_code = '''
# Add this to main.py after existing ground truth endpoints

@app.post("/api/videos/{video_id}/generate-ground-truth")
async def generate_ground_truth(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate ground truth annotations for a video - compatible with frontend"""
    # This is an alias for the existing process-ground-truth endpoint
    # to maintain frontend compatibility
    return await trigger_ground_truth_processing(video_id, background_tasks, db)

@app.post("/api/videos/batch-generate-ground-truth")
async def batch_generate_ground_truth(
    video_ids: list[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Batch generate ground truth for multiple videos"""
    try:
        results = []
        for video_id in video_ids:
            # Check if video exists
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                results.append({
                    "video_id": video_id,
                    "status": "error", 
                    "message": "Video not found"
                })
                continue
                
            # Trigger processing
            try:
                result = await trigger_ground_truth_processing(video_id, background_tasks, db)
                results.append({
                    "video_id": video_id,
                    "status": "success",
                    "message": result.get("message", "Processing started")
                })
            except Exception as e:
                results.append({
                    "video_id": video_id,
                    "status": "error",
                    "message": str(e)
                })
                
        return {
            "message": f"Batch processing initiated for {len(video_ids)} videos",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch ground truth generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch processing failed: {str(e)}"
        )
'''
    
    print("📝 Ground truth endpoints that should be added to main.py:")
    print(endpoint_code)
    
    return endpoint_code

if __name__ == "__main__":
    print("🚀 Starting ground truth schema and endpoint fix...")
    
    # Fix database schema
    if fix_schema():
        print("✅ Database schema fixed!")
    else:
        print("❌ Failed to fix database schema")
        sys.exit(1)
    
    # Show endpoint code to add
    endpoint_code = add_ground_truth_endpoint()
    
    print("✅ Ground truth system repair completed!")
    print("\n🎯 Summary:")
    print("1. ✅ Fixed database schema (added tracking_id column)")
    print("2. 📝 Generated endpoint code for main.py")
    print("3. 🔄 Restart the backend to apply endpoint changes")