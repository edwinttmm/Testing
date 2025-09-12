#!/usr/bin/env python3
"""
Data Backup Script for Project-Video Migration
Creates comprehensive backup of existing data before migration
"""

import json
import sqlite3
import logging
import os
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseBackupManager:
    """Manages database backup operations for safe migrations"""
    
    def __init__(self, db_path: str = "./dev_database.db"):
        self.db_path = db_path
        self.backup_dir = Path("./migration_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def create_comprehensive_backup(self) -> Dict[str, str]:
        """Create comprehensive backup before migration"""
        logger.info("Starting comprehensive database backup...")
        
        backup_files = {
            "database_copy": self._create_database_copy(),
            "projects_json": self._backup_projects_to_json(),
            "videos_json": self._backup_videos_to_json(),
            "relationships_json": self._backup_relationships_to_json(),
            "metadata": self._create_backup_metadata()
        }
        
        logger.info(f"Backup completed successfully: {backup_files}")
        return backup_files
    
    def _create_database_copy(self) -> str:
        """Create complete database file copy"""
        backup_file = self.backup_dir / f"database_backup_{self.timestamp}.db"
        
        if os.path.exists(self.db_path):
            import shutil
            shutil.copy2(self.db_path, backup_file)
            logger.info(f"Database copy created: {backup_file}")
        else:
            logger.warning(f"Source database not found: {self.db_path}")
            
        return str(backup_file)
    
    def _backup_projects_to_json(self) -> str:
        """Backup projects table to JSON"""
        backup_file = self.backup_dir / f"projects_backup_{self.timestamp}.json"
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get projects with all current fields
            cursor.execute("""
                SELECT 
                    id, name, description, camera_model, camera_view, lens_type,
                    resolution, frame_rate, signal_type, status, owner_id,
                    created_at, updated_at
                FROM projects
            """)
            
            projects = [dict(row) for row in cursor.fetchall()]
            
            with open(backup_file, 'w') as f:
                json.dump(projects, f, indent=2, default=str)
                
            logger.info(f"Projects backup created: {backup_file} ({len(projects)} records)")
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to backup projects: {e}")
            
        return str(backup_file)
    
    def _backup_videos_to_json(self) -> str:
        """Backup videos table to JSON"""
        backup_file = self.backup_dir / f"videos_backup_{self.timestamp}.json"
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get videos with all current fields
            cursor.execute("""
                SELECT 
                    id, filename, file_path, file_size, duration, fps, resolution,
                    status, ground_truth_generated, project_id, upload_timestamp,
                    created_at, updated_at, metadata
                FROM videos
                WHERE project_id IS NOT NULL
            """)
            
            videos = [dict(row) for row in cursor.fetchall()]
            
            with open(backup_file, 'w') as f:
                json.dump(videos, f, indent=2, default=str)
                
            logger.info(f"Videos backup created: {backup_file} ({len(videos)} records)")
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to backup videos: {e}")
            
        return str(backup_file)
    
    def _backup_relationships_to_json(self) -> str:
        """Backup existing project-video relationships"""
        backup_file = self.backup_dir / f"project_video_relationships_{self.timestamp}.json"
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get current project-video relationships
            cursor.execute("""
                SELECT 
                    p.id as project_id,
                    p.name as project_name,
                    v.id as video_id,
                    v.filename as video_filename,
                    v.project_id as current_project_id
                FROM projects p
                LEFT JOIN videos v ON p.id = v.project_id
                WHERE v.id IS NOT NULL
            """)
            
            relationships = [dict(row) for row in cursor.fetchall()]
            
            with open(backup_file, 'w') as f:
                json.dump(relationships, f, indent=2, default=str)
                
            logger.info(f"Relationships backup created: {backup_file} ({len(relationships)} records)")
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to backup relationships: {e}")
            
        return str(backup_file)
    
    def _create_backup_metadata(self) -> str:
        """Create backup metadata file"""
        metadata_file = self.backup_dir / f"backup_metadata_{self.timestamp}.json"
        
        metadata = {
            "backup_timestamp": self.timestamp,
            "source_database": self.db_path,
            "backup_purpose": "project_video_many_to_many_migration",
            "backup_files": list(self.backup_dir.glob(f"*_{self.timestamp}.*")),
            "migration_version": "0004_project_video_many_to_many",
            "created_by": "database_migration_script"
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
            
        logger.info(f"Backup metadata created: {metadata_file}")
        return str(metadata_file)
    
    def verify_backup_integrity(self, backup_files: Dict[str, str]) -> bool:
        """Verify backup integrity"""
        logger.info("Verifying backup integrity...")
        
        for backup_type, file_path in backup_files.items():
            if not os.path.exists(file_path):
                logger.error(f"Backup file missing: {file_path}")
                return False
                
            if backup_type.endswith('.json') and os.path.getsize(file_path) == 0:
                logger.error(f"Backup file empty: {file_path}")
                return False
                
        logger.info("Backup integrity verification passed")
        return True
    
    def restore_from_backup(self, backup_files: Dict[str, str]) -> bool:
        """Restore database from backup if needed"""
        logger.info("Restoring database from backup...")
        
        try:
            database_backup = backup_files.get("database_copy")
            if database_backup and os.path.exists(database_backup):
                import shutil
                shutil.copy2(database_backup, self.db_path)
                logger.info(f"Database restored from: {database_backup}")
                return True
            else:
                logger.error("Database backup file not found for restoration")
                return False
                
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

def main():
    """Main backup execution function"""
    backup_manager = DatabaseBackupManager()
    
    try:
        # Create comprehensive backup
        backup_files = backup_manager.create_comprehensive_backup()
        
        # Verify backup integrity
        if backup_manager.verify_backup_integrity(backup_files):
            print("✅ Database backup completed successfully!")
            print(f"📁 Backup location: {backup_manager.backup_dir}")
            for backup_type, file_path in backup_files.items():
                print(f"   {backup_type}: {file_path}")
        else:
            print("❌ Backup integrity verification failed!")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"❌ Backup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)