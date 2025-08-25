#!/usr/bin/env python3
"""
Video File Validator - Ensures consistency between database entries and physical files
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.append(str(backend_dir))

from database import SessionLocal
from models import Video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoFileValidator:
    """Validates consistency between video database entries and physical files"""
    
    def __init__(self, uploads_dir: str = "uploads"):
        self.uploads_dir = Path(uploads_dir)
        self.uploads_dir.mkdir(exist_ok=True)
    
    def validate_all_videos(self) -> Dict[str, Any]:
        """Validate all videos and return a comprehensive report"""
        
        report = {
            "timestamp": "2025-08-25T23:30:00Z",
            "validation_summary": {
                "total_db_entries": 0,
                "total_physical_files": 0,
                "orphaned_db_entries": 0,
                "orphaned_files": 0,
                "valid_entries": 0
            },
            "orphaned_database_entries": [],
            "orphaned_physical_files": [],
            "valid_videos": [],
            "recommendations": []
        }
        
        try:
            with SessionLocal() as db:
                # Get all database entries
                db_videos = db.query(Video).all()
                report["validation_summary"]["total_db_entries"] = len(db_videos)
                
                # Get all physical files
                physical_files = list(self.uploads_dir.glob("*.mp4"))
                report["validation_summary"]["total_physical_files"] = len(physical_files)
                
                # Check for orphaned database entries
                for video in db_videos:
                    video_path = self.uploads_dir / video.filename
                    if not video_path.exists():
                        report["orphaned_database_entries"].append({
                            "id": video.id,
                            "filename": video.filename,
                            "created_at": str(video.created_at),
                            "status": video.processing_status
                        })
                    else:
                        report["valid_videos"].append({
                            "id": video.id,
                            "filename": video.filename,
                            "file_size": video_path.stat().st_size,
                            "status": video.processing_status
                        })
                
                # Check for orphaned physical files
                db_filenames = {video.filename for video in db_videos}
                for file_path in physical_files:
                    if file_path.name not in db_filenames:
                        report["orphaned_physical_files"].append({
                            "filename": file_path.name,
                            "file_size": file_path.stat().st_size,
                            "modified_at": file_path.stat().st_mtime
                        })
                
                # Calculate summary
                report["validation_summary"]["orphaned_db_entries"] = len(report["orphaned_database_entries"])
                report["validation_summary"]["orphaned_files"] = len(report["orphaned_physical_files"])
                report["validation_summary"]["valid_entries"] = len(report["valid_videos"])
                
                # Generate recommendations
                if report["validation_summary"]["orphaned_db_entries"] > 0:
                    report["recommendations"].append(
                        f"Remove {report['validation_summary']['orphaned_db_entries']} orphaned database entries"
                    )
                
                if report["validation_summary"]["orphaned_files"] > 0:
                    report["recommendations"].append(
                        f"Consider adding {report['validation_summary']['orphaned_files']} orphaned files to database or remove them"
                    )
                
                if not report["recommendations"]:
                    report["recommendations"].append("All video files are properly synchronized")
                
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            report["error"] = str(e)
        
        return report
    
    def cleanup_orphaned_database_entries(self, dry_run: bool = True) -> List[str]:
        """Remove orphaned database entries where physical files don't exist"""
        
        removed_entries = []
        
        try:
            with SessionLocal() as db:
                videos = db.query(Video).all()
                
                for video in videos:
                    video_path = self.uploads_dir / video.filename
                    if not video_path.exists():
                        logger.info(f"Found orphaned entry: {video.filename} (ID: {video.id})")
                        
                        if not dry_run:
                            db.delete(video)
                            removed_entries.append(video.filename)
                            logger.info(f"Deleted orphaned entry: {video.filename}")
                        else:
                            removed_entries.append(f"[DRY RUN] Would delete: {video.filename}")
                
                if not dry_run and removed_entries:
                    db.commit()
                    logger.info(f"Successfully removed {len(removed_entries)} orphaned entries")
                
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise
        
        return removed_entries

def main():
    """Main function for command-line usage"""
    
    validator = VideoFileValidator()
    
    print("=== VIDEO FILE VALIDATION REPORT ===")
    report = validator.validate_all_videos()
    
    print(f"\nSummary:")
    print(f"  Database entries: {report['validation_summary']['total_db_entries']}")
    print(f"  Physical files: {report['validation_summary']['total_physical_files']}")
    print(f"  Valid entries: {report['validation_summary']['valid_entries']}")
    print(f"  Orphaned DB entries: {report['validation_summary']['orphaned_db_entries']}")
    print(f"  Orphaned files: {report['validation_summary']['orphaned_files']}")
    
    if report["orphaned_database_entries"]:
        print("\nOrphaned Database Entries:")
        for entry in report["orphaned_database_entries"]:
            print(f"  - {entry['filename']} (ID: {entry['id']})")
    
    if report["orphaned_physical_files"]:
        print("\nOrphaned Physical Files:")
        for entry in report["orphaned_physical_files"]:
            print(f"  - {entry['filename']} ({entry['file_size']} bytes)")
    
    print("\nRecommendations:")
    for rec in report["recommendations"]:
        print(f"  • {rec}")

if __name__ == "__main__":
    main()