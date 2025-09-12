#!/usr/bin/env python3
"""
Migration script to update 'completed' video status to 'validated'
for backwards compatibility with new video validation workflow
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path to import from the backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from models import Video, Base

DATABASE_URL = settings.database_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_video_status():
    """Migrate existing 'completed' videos to 'validated' status"""
    try:
        # Create engine and session
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        logger.info("🚀 Starting video status migration: 'completed' → 'validated'")
        
        # Find all videos with 'completed' status
        completed_videos = db.query(Video).filter(
            Video.status == 'completed',
            Video.ground_truth_generated == True
        ).all()
        
        logger.info(f"📊 Found {len(completed_videos)} videos with 'completed' status")
        
        if len(completed_videos) == 0:
            logger.info("✅ No videos to migrate")
            return
        
        # Update videos to 'validated' status
        updated_count = 0
        for video in completed_videos:
            try:
                video.status = 'validated'
                updated_count += 1
                logger.info(f"📝 Updated video {video.id} ({video.filename}) to 'validated'")
            except Exception as e:
                logger.error(f"❌ Failed to update video {video.id}: {e}")
        
        # Commit changes
        db.commit()
        logger.info(f"✅ Successfully migrated {updated_count} videos to 'validated' status")
        
        # Verify migration
        validated_count = db.query(Video).filter(Video.status == 'validated').count()
        logger.info(f"🔍 Verification: {validated_count} videos now have 'validated' status")
        
    except Exception as e:
        logger.error(f"💥 Migration failed: {e}")
        if 'db' in locals():
            db.rollback()
        raise
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    migrate_video_status()