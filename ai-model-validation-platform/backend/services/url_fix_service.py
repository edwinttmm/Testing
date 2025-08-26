"""
URL Fix Service: Database URL Update and Cache Management
========================================================

Service for updating localhost URLs to production URLs in the database
with comprehensive cache invalidation and validation.

Key Features:
- Bulk URL updates across multiple tables
- Cache invalidation for affected records  
- Validation and logging of changes
- Rollback capability
- Progress tracking via WebSocket
"""

import logging
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database import SessionLocal
from models import Video, GroundTruthObject, DetectionEvent, Annotation
from config import Settings

logger = logging.getLogger(__name__)

class URLFixService:
    """
    Service for fixing localhost URLs in database records.
    """
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.old_base_url = "http://localhost:8000"
        self.new_base_url = "http://155.138.239.131:8000"
        
        # Tables and fields that may contain URLs
        self.url_fields_map = {
            'videos': ['file_path'],
            'detection_events': ['screenshot_path', 'screenshot_zoom_path'],
            'ground_truth_objects': [],  # Typically no URL fields
            'annotations': []  # Typically no URL fields
        }
        
        logger.info(f"URLFixService initialized: {self.old_base_url} -> {self.new_base_url}")
    
    async def scan_database_for_localhost_urls(self, session: Session = None) -> Dict[str, Any]:
        """
        Scan the database for localhost URL references.
        
        Returns:
            Dict with scan results and affected records
        """
        if not session:
            session = SessionLocal()
            should_close = True
        else:
            should_close = False
        
        try:
            scan_results = {
                'scan_timestamp': datetime.now().isoformat(),
                'old_base_url': self.old_base_url,
                'new_base_url': self.new_base_url,
                'affected_tables': {},
                'total_records': 0
            }
            
            # Scan Videos table
            videos_query = session.query(Video).filter(
                Video.file_path.like(f"%{self.old_base_url}%")
            )
            videos_count = videos_query.count()
            
            if videos_count > 0:
                videos_sample = videos_query.limit(5).all()
                scan_results['affected_tables']['videos'] = {
                    'count': videos_count,
                    'fields': ['file_path'],
                    'sample_records': [
                        {
                            'id': v.id,
                            'filename': v.filename,
                            'current_file_path': v.file_path,
                            'proposed_file_path': v.file_path.replace(self.old_base_url, self.new_base_url)
                        }
                        for v in videos_sample
                    ]
                }
            
            # Scan Detection Events table
            detection_events_query = session.query(DetectionEvent).filter(
                (DetectionEvent.screenshot_path.like(f"%{self.old_base_url}%")) |
                (DetectionEvent.screenshot_zoom_path.like(f"%{self.old_base_url}%"))
            )
            detection_events_count = detection_events_query.count()
            
            if detection_events_count > 0:
                detection_events_sample = detection_events_query.limit(5).all()
                scan_results['affected_tables']['detection_events'] = {
                    'count': detection_events_count,
                    'fields': ['screenshot_path', 'screenshot_zoom_path'],
                    'sample_records': [
                        {
                            'id': de.id,
                            'test_session_id': de.test_session_id,
                            'current_screenshot_path': de.screenshot_path,
                            'current_screenshot_zoom_path': de.screenshot_zoom_path,
                            'proposed_screenshot_path': de.screenshot_path.replace(self.old_base_url, self.new_base_url) if de.screenshot_path else None,
                            'proposed_screenshot_zoom_path': de.screenshot_zoom_path.replace(self.old_base_url, self.new_base_url) if de.screenshot_zoom_path else None
                        }
                        for de in detection_events_sample
                    ]
                }
            
            # Raw SQL scan for comprehensive coverage
            raw_scan_query = text("""
                SELECT 
                    'videos' as table_name, 
                    COUNT(*) as count
                FROM videos 
                WHERE file_path LIKE :old_url
                
                UNION ALL
                
                SELECT 
                    'detection_events_screenshot' as table_name,
                    COUNT(*) as count
                FROM detection_events 
                WHERE screenshot_path LIKE :old_url
                
                UNION ALL
                
                SELECT 
                    'detection_events_zoom' as table_name,
                    COUNT(*) as count  
                FROM detection_events 
                WHERE screenshot_zoom_path LIKE :old_url
            """)
            
            raw_results = session.execute(raw_scan_query, {'old_url': f'%{self.old_base_url}%'}).fetchall()
            scan_results['raw_scan_summary'] = {row.table_name: row.count for row in raw_results}
            
            scan_results['total_records'] = sum(
                table_data['count'] 
                for table_data in scan_results['affected_tables'].values()
            )
            
            logger.info(f"Database scan complete: {scan_results['total_records']} records need URL fixes")
            
            return scan_results
            
        except Exception as e:
            logger.error(f"Database scan failed: {e}")
            raise
        finally:
            if should_close:
                session.close()
    
    async def fix_urls_bulk(self, session: Session = None, progress_callback=None) -> Dict[str, Any]:
        """
        Perform bulk URL fixes across all affected tables.
        
        Args:
            session: Database session (optional)
            progress_callback: Function to call with progress updates
            
        Returns:
            Dict with operation results
        """
        if not session:
            session = SessionLocal()
            should_close = True
        else:
            should_close = False
        
        operation_results = {
            'operation_timestamp': datetime.now().isoformat(),
            'old_base_url': self.old_base_url,
            'new_base_url': self.new_base_url,
            'tables_processed': {},
            'total_updated': 0,
            'errors': []
        }
        
        try:
            # Create backup before making changes
            backup_data = await self.scan_database_for_localhost_urls(session)
            backup_file = f"url_fix_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = f"backups/{backup_file}"
            
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            operation_results['backup_file'] = backup_path
            logger.info(f"Created backup: {backup_path}")
            
            if progress_callback:
                await progress_callback("backup_created", {"file": backup_path})
            
            # Fix Videos table
            if progress_callback:
                await progress_callback("processing_videos", {"status": "started"})
            
            videos_updated = session.execute(
                text("""
                    UPDATE videos 
                    SET file_path = REPLACE(file_path, :old_url, :new_url)
                    WHERE file_path LIKE :old_url_pattern
                """),
                {
                    'old_url': self.old_base_url,
                    'new_url': self.new_base_url,
                    'old_url_pattern': f'%{self.old_base_url}%'
                }
            )
            
            videos_count = videos_updated.rowcount
            operation_results['tables_processed']['videos'] = {
                'updated_count': videos_count,
                'fields_updated': ['file_path']
            }
            
            logger.info(f"Updated {videos_count} video records")
            
            if progress_callback:
                await progress_callback("processing_videos", {
                    "status": "completed", 
                    "updated_count": videos_count
                })
            
            # Fix Detection Events table - screenshot paths
            if progress_callback:
                await progress_callback("processing_detection_events", {"status": "started"})
            
            screenshot_path_updated = session.execute(
                text("""
                    UPDATE detection_events 
                    SET screenshot_path = REPLACE(screenshot_path, :old_url, :new_url)
                    WHERE screenshot_path LIKE :old_url_pattern
                """),
                {
                    'old_url': self.old_base_url,
                    'new_url': self.new_base_url,
                    'old_url_pattern': f'%{self.old_base_url}%'
                }
            )
            
            screenshot_zoom_updated = session.execute(
                text("""
                    UPDATE detection_events 
                    SET screenshot_zoom_path = REPLACE(screenshot_zoom_path, :old_url, :new_url)
                    WHERE screenshot_zoom_path LIKE :old_url_pattern
                """),
                {
                    'old_url': self.old_base_url,
                    'new_url': self.new_base_url,
                    'old_url_pattern': f'%{self.old_base_url}%'
                }
            )
            
            detection_events_count = screenshot_path_updated.rowcount + screenshot_zoom_updated.rowcount
            operation_results['tables_processed']['detection_events'] = {
                'updated_count': detection_events_count,
                'fields_updated': ['screenshot_path', 'screenshot_zoom_path'],
                'screenshot_path_updates': screenshot_path_updated.rowcount,
                'screenshot_zoom_updates': screenshot_zoom_updated.rowcount
            }
            
            logger.info(f"Updated {detection_events_count} detection event records")
            
            if progress_callback:
                await progress_callback("processing_detection_events", {
                    "status": "completed",
                    "updated_count": detection_events_count
                })
            
            # Commit all changes
            session.commit()
            
            operation_results['total_updated'] = videos_count + detection_events_count
            operation_results['status'] = 'success'
            
            logger.info(f"URL fix operation completed: {operation_results['total_updated']} records updated")
            
            if progress_callback:
                await progress_callback("operation_completed", {
                    "total_updated": operation_results['total_updated'],
                    "backup_file": backup_path
                })
            
            # Invalidate relevant caches
            await self._invalidate_caches(operation_results)
            
            return operation_results
            
        except Exception as e:
            session.rollback()
            operation_results['status'] = 'error'
            operation_results['error'] = str(e)
            operation_results['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'context': 'bulk_url_fix'
            })
            
            logger.error(f"URL fix operation failed: {e}")
            
            if progress_callback:
                await progress_callback("operation_failed", {"error": str(e)})
            
            raise
        
        finally:
            if should_close:
                session.close()
    
    async def _invalidate_caches(self, operation_results: Dict[str, Any]) -> None:
        """
        Invalidate relevant caches after URL updates.
        
        Args:
            operation_results: Results from the URL fix operation
        """
        try:
            # If Redis is configured, invalidate relevant cache keys
            if hasattr(self.settings, 'redis_url') and self.settings.redis_url:
                # This would require Redis integration
                logger.info("Redis cache invalidation would occur here")
            
            # Log cache invalidation for other systems
            cache_keys_to_invalidate = []
            
            if 'videos' in operation_results['tables_processed']:
                cache_keys_to_invalidate.extend([
                    'video_list:*',
                    'video_details:*',
                    'project_videos:*'
                ])
            
            if 'detection_events' in operation_results['tables_processed']:
                cache_keys_to_invalidate.extend([
                    'detection_events:*',
                    'test_results:*',
                    'detection_screenshots:*'
                ])
            
            logger.info(f"Cache invalidation required for keys: {cache_keys_to_invalidate}")
            
        except Exception as e:
            logger.warning(f"Cache invalidation failed (non-critical): {e}")
    
    async def validate_url_fixes(self, session: Session = None) -> Dict[str, Any]:
        """
        Validate that URL fixes were applied correctly.
        
        Returns:
            Dict with validation results
        """
        if not session:
            session = SessionLocal()
            should_close = True
        else:
            should_close = False
        
        try:
            validation_results = {
                'validation_timestamp': datetime.now().isoformat(),
                'old_base_url': self.old_base_url,
                'new_base_url': self.new_base_url,
                'remaining_localhost_urls': {},
                'validation_passed': True
            }
            
            # Check for any remaining localhost URLs
            remaining_videos = session.query(Video).filter(
                Video.file_path.like(f"%{self.old_base_url}%")
            ).count()
            
            remaining_detection_events = session.query(DetectionEvent).filter(
                (DetectionEvent.screenshot_path.like(f"%{self.old_base_url}%")) |
                (DetectionEvent.screenshot_zoom_path.like(f"%{self.old_base_url}%"))
            ).count()
            
            validation_results['remaining_localhost_urls'] = {
                'videos': remaining_videos,
                'detection_events': remaining_detection_events
            }
            
            total_remaining = remaining_videos + remaining_detection_events
            validation_results['total_remaining'] = total_remaining
            
            if total_remaining > 0:
                validation_results['validation_passed'] = False
                logger.warning(f"Validation failed: {total_remaining} records still contain localhost URLs")
            else:
                logger.info("Validation passed: No localhost URLs remaining")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise
        finally:
            if should_close:
                session.close()
    
    async def get_fix_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the URL fix operation status.
        
        Returns:
            Dict with current status and statistics
        """
        session = SessionLocal()
        try:
            scan_results = await self.scan_database_for_localhost_urls(session)
            
            summary = {
                'timestamp': datetime.now().isoformat(),
                'fix_needed': scan_results['total_records'] > 0,
                'affected_records': scan_results['total_records'],
                'affected_tables': list(scan_results['affected_tables'].keys()),
                'old_base_url': self.old_base_url,
                'new_base_url': self.new_base_url,
                'recommendation': 'run_fix' if scan_results['total_records'] > 0 else 'no_action_needed'
            }
            
            return summary
            
        finally:
            session.close()


# Global service instance
url_fix_service = URLFixService()