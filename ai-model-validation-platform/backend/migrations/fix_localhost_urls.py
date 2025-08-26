#!/usr/bin/env python3
"""
Database Migration Script: Fix Localhost URLs to Production URLs
==============================================================

This script updates all localhost URLs in the database to production URLs.
Specifically targets video URLs and other URL references that need to be updated.

Target:
- FROM: http://localhost:8000/uploads/...
- TO: http://155.138.239.131:8000/uploads/...

Affected Tables:
- Videos (any URL fields)
- Ground Truth Objects (screenshot paths, file references)  
- Detection Events (screenshot_path, screenshot_zoom_path)
- Any other tables with URL/file path fields

Usage:
    python fix_localhost_urls.py --dry-run  # Preview changes
    python fix_localhost_urls.py --execute  # Apply changes
    python fix_localhost_urls.py --rollback # Revert changes (if backup exists)
"""

import os
import sys
import sqlite3
import argparse
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.orm import sessionmaker
    from config import Settings
    from database import SessionLocal
    from models import Video, GroundTruthObject, DetectionEvent
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please run from the backend directory with proper environment setup")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LocalhostURLFixer:
    """
    Service for fixing localhost URLs in the database.
    """
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.session = SessionLocal()
        self.old_base_url = "http://localhost:8000"
        self.new_base_url = "http://155.138.239.131:8000"
        
        # Backup file for rollback capability
        self.backup_file = f"url_fix_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.backup_data = {}
        
        logger.info(f"Initialized URL fixer: {self.old_base_url} -> {self.new_base_url}")
    
    def find_url_fields(self) -> Dict[str, List[str]]:
        """
        Identify all URL/path fields that might contain localhost references.
        
        Returns:
            Dict mapping table names to field names that may contain URLs
        """
        url_fields = {
            'videos': ['file_path'],  # May contain full URLs in some cases
            'ground_truth_objects': [],  # No direct URL fields typically
            'detection_events': ['screenshot_path', 'screenshot_zoom_path'],
            'annotations': [],  # No direct URL fields typically
        }
        
        logger.info(f"Identified URL fields: {url_fields}")
        return url_fields
    
    def scan_for_localhost_urls(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scan database for localhost URLs across all relevant tables.
        
        Returns:
            Dict with table names and records containing localhost URLs
        """
        findings = {}
        
        try:
            # Check Videos table
            videos_with_localhost = self.session.query(Video).filter(
                Video.file_path.like(f"%{self.old_base_url}%")
            ).all()
            
            if videos_with_localhost:
                findings['videos'] = [
                    {
                        'id': v.id,
                        'filename': v.filename,
                        'file_path': v.file_path,
                        'old_value': v.file_path,
                        'new_value': v.file_path.replace(self.old_base_url, self.new_base_url)
                    }
                    for v in videos_with_localhost
                ]
            
            # Check Detection Events for screenshot paths
            detection_events = self.session.query(DetectionEvent).filter(
                (DetectionEvent.screenshot_path.like(f"%{self.old_base_url}%")) |
                (DetectionEvent.screenshot_zoom_path.like(f"%{self.old_base_url}%"))
            ).all()
            
            if detection_events:
                findings['detection_events'] = []
                for de in detection_events:
                    record = {'id': de.id}
                    if de.screenshot_path and self.old_base_url in de.screenshot_path:
                        record['screenshot_path_old'] = de.screenshot_path
                        record['screenshot_path_new'] = de.screenshot_path.replace(self.old_base_url, self.new_base_url)
                    if de.screenshot_zoom_path and self.old_base_url in de.screenshot_zoom_path:
                        record['screenshot_zoom_path_old'] = de.screenshot_zoom_path
                        record['screenshot_zoom_path_new'] = de.screenshot_zoom_path.replace(self.old_base_url, self.new_base_url)
                    findings['detection_events'].append(record)
            
            # Raw SQL scan for any other localhost references
            raw_scan_query = text("""
                SELECT 'videos' as table_name, id, 'file_path' as field_name, file_path as value
                FROM videos 
                WHERE file_path LIKE :old_url
                
                UNION ALL
                
                SELECT 'detection_events' as table_name, id, 'screenshot_path' as field_name, screenshot_path as value
                FROM detection_events 
                WHERE screenshot_path LIKE :old_url
                
                UNION ALL
                
                SELECT 'detection_events' as table_name, id, 'screenshot_zoom_path' as field_name, screenshot_zoom_path as value
                FROM detection_events 
                WHERE screenshot_zoom_path LIKE :old_url
            """)
            
            raw_results = self.session.execute(raw_scan_query, {'old_url': f'%{self.old_base_url}%'}).fetchall()
            
            if raw_results:
                findings['raw_scan'] = [
                    {
                        'table': row.table_name,
                        'id': row.id,
                        'field': row.field_name,
                        'current_value': row.value,
                        'updated_value': row.value.replace(self.old_base_url, self.new_base_url) if row.value else None
                    }
                    for row in raw_results
                ]
            
            total_records = sum(len(records) for records in findings.values())
            logger.info(f"Found {total_records} records with localhost URLs across {len(findings)} tables")
            
        except Exception as e:
            logger.error(f"Error scanning for localhost URLs: {e}")
            raise
        
        return findings
    
    def create_backup(self, findings: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Create backup of current URL values for rollback capability.
        
        Args:
            findings: Data structure with records to be changed
            
        Returns:
            Path to backup file
        """
        try:
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'old_base_url': self.old_base_url,
                'new_base_url': self.new_base_url,
                'findings': findings
            }
            
            backup_path = f"migrations/{self.backup_file}"
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"Created backup file: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def apply_url_fixes(self, findings: Dict[str, List[Dict[str, Any]]], dry_run: bool = True) -> Dict[str, int]:
        """
        Apply URL fixes to the database.
        
        Args:
            findings: Records to update
            dry_run: If True, only show what would be changed
            
        Returns:
            Dict with count of updated records per table
        """
        update_counts = {}
        
        try:
            if dry_run:
                logger.info("DRY RUN MODE - No changes will be made")
            else:
                logger.info("EXECUTING URL FIXES")
            
            # Update Videos table
            if 'videos' in findings:
                count = 0
                for record in findings['videos']:
                    if not dry_run:
                        video = self.session.query(Video).filter(Video.id == record['id']).first()
                        if video:
                            video.file_path = record['new_value']
                            count += 1
                    else:
                        logger.info(f"[DRY RUN] Video {record['id']}: {record['old_value']} -> {record['new_value']}")
                        count += 1
                
                update_counts['videos'] = count
            
            # Update Detection Events table
            if 'detection_events' in findings:
                count = 0
                for record in findings['detection_events']:
                    if not dry_run:
                        de = self.session.query(DetectionEvent).filter(DetectionEvent.id == record['id']).first()
                        if de:
                            if 'screenshot_path_new' in record:
                                de.screenshot_path = record['screenshot_path_new']
                            if 'screenshot_zoom_path_new' in record:
                                de.screenshot_zoom_path = record['screenshot_zoom_path_new']
                            count += 1
                    else:
                        logger.info(f"[DRY RUN] DetectionEvent {record['id']}: Updates planned")
                        count += 1
                
                update_counts['detection_events'] = count
            
            # Commit changes if not dry run
            if not dry_run:
                self.session.commit()
                logger.info("Database changes committed successfully")
            
            total_updates = sum(update_counts.values())
            logger.info(f"{'Would update' if dry_run else 'Updated'} {total_updates} records")
            
        except Exception as e:
            if not dry_run:
                self.session.rollback()
            logger.error(f"Error applying URL fixes: {e}")
            raise
        
        return update_counts
    
    def rollback_changes(self, backup_file: str) -> bool:
        """
        Rollback URL changes using backup file.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if rollback successful
        """
        try:
            logger.info(f"Starting rollback from backup: {backup_file}")
            
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
            
            findings = backup_data['findings']
            
            # Rollback Videos
            if 'videos' in findings:
                for record in findings['videos']:
                    video = self.session.query(Video).filter(Video.id == record['id']).first()
                    if video:
                        video.file_path = record['old_value']
            
            # Rollback Detection Events
            if 'detection_events' in findings:
                for record in findings['detection_events']:
                    de = self.session.query(DetectionEvent).filter(DetectionEvent.id == record['id']).first()
                    if de:
                        if 'screenshot_path_old' in record:
                            de.screenshot_path = record['screenshot_path_old']
                        if 'screenshot_zoom_path_old' in record:
                            de.screenshot_zoom_path = record['screenshot_zoom_path_old']
            
            self.session.commit()
            logger.info("Rollback completed successfully")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Rollback failed: {e}")
            return False
    
    def close(self):
        """Close database session."""
        if self.session:
            self.session.close()


def main():
    parser = argparse.ArgumentParser(description="Fix localhost URLs in database")
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be changed without making changes')
    parser.add_argument('--execute', action='store_true',
                       help='Execute the URL fixes')
    parser.add_argument('--rollback', type=str,
                       help='Rollback using specified backup file')
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan and report findings')
    
    args = parser.parse_args()
    
    if not any([args.dry_run, args.execute, args.rollback, args.scan_only]):
        print("Please specify one of: --dry-run, --execute, --rollback, --scan-only")
        parser.print_help()
        return
    
    fixer = LocalhostURLFixer()
    
    try:
        if args.rollback:
            success = fixer.rollback_changes(args.rollback)
            print(f"Rollback {'successful' if success else 'failed'}")
            return
        
        # Scan for localhost URLs
        print("Scanning database for localhost URLs...")
        findings = fixer.scan_for_localhost_urls()
        
        if not findings:
            print("✅ No localhost URLs found in database")
            return
        
        # Display findings
        total_records = sum(len(records) for records in findings.values())
        print(f"\n📋 Found {total_records} records with localhost URLs:")
        
        for table, records in findings.items():
            print(f"\n  {table.upper()}: {len(records)} records")
            for i, record in enumerate(records[:3]):  # Show first 3 examples
                if table == 'videos':
                    print(f"    - ID {record['id']}: {record['filename']}")
                    print(f"      OLD: {record['old_value']}")
                    print(f"      NEW: {record['new_value']}")
                elif table == 'detection_events':
                    print(f"    - ID {record['id']}")
                    for key, value in record.items():
                        if key.endswith('_old') or key.endswith('_new'):
                            print(f"      {key}: {value}")
            
            if len(records) > 3:
                print(f"    ... and {len(records) - 3} more records")
        
        if args.scan_only:
            return
        
        # Create backup before making changes
        if args.execute:
            backup_path = fixer.create_backup(findings)
            print(f"📦 Created backup: {backup_path}")
        
        # Apply fixes
        update_counts = fixer.apply_url_fixes(findings, dry_run=args.dry_run)
        
        if args.dry_run:
            print(f"\n🔍 DRY RUN COMPLETE - Would update {sum(update_counts.values())} records")
            print("Use --execute to apply these changes")
        else:
            print(f"\n✅ URL FIX COMPLETE - Updated {sum(update_counts.values())} records")
            print(f"Backup saved to: {backup_path}")
        
        # Show update summary
        print(f"\n📊 Update Summary:")
        for table, count in update_counts.items():
            print(f"  {table}: {count} records")
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"❌ Migration failed: {e}")
        return 1
    
    finally:
        fixer.close()


if __name__ == "__main__":
    exit(main())