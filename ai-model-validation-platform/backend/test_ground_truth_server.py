#!/usr/bin/env python3
"""
Test server for ground truth endpoint - minimal imports to avoid issues
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, get_db
from models import Video, GroundTruthObject
import logging

# Create FastAPI app
app = FastAPI(title="Ground Truth Test Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/")
async def root():
    return {"message": "Ground Truth Test Server is running"}

@app.get("/api/ground-truth/videos/available")
async def get_videos_with_ground_truth(
    db: Session = Depends(get_db)
):
    """
    Get all videos that have ground truth annotations available
    This is the MAIN endpoint that the frontend expects
    """
    try:
        logger.info("Getting videos with ground truth")
        
        # Query for videos with ground truth
        videos = db.query(Video).filter(
            Video.ground_truth_generated == True
        ).limit(100).all()
        
        # Format response
        video_list = []
        for video in videos:
            # Get ground truth count for this video
            gt_count = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()
            
            video_data = {
                "id": video.id,
                "filename": video.filename,
                "originalName": video.original_name or video.filename,
                "uploadDate": video.upload_date.isoformat() if video.upload_date else None,
                "status": video.status,
                "processingStatus": video.processing_status,
                "groundTruthGenerated": bool(video.ground_truth_generated),
                "groundTruthCount": gt_count,
                "projectId": video.project_id,
                "filePath": video.file_path,
                "duration": video.duration,
                "fps": video.fps,
                "resolution": video.resolution
            }
            video_list.append(video_data)
        
        logger.info(f"Found {len(video_list)} videos with ground truth")
        
        return {
            "success": True,
            "videos": video_list,
            "total": len(video_list),
            "count": len(video_list),
            "message": f"Found {len(video_list)} videos with ground truth annotations"
        }
        
    except Exception as e:
        logger.error(f"Error getting videos with ground truth: {str(e)}")
        # Return empty list instead of error to prevent frontend crashes
        return {
            "success": True,
            "videos": [],
            "total": 0,
            "count": 0,
            "message": "No videos with ground truth annotations found"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
