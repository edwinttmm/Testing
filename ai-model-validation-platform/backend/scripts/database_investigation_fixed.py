#!/usr/bin/env python3
"""
CORRECTED Comprehensive Database Investigation Script
Analyzes data integrity issues with persistent "Manual" status display

This script uses the correct column names from the actual database schema.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from database import get_database_url
from models import Video, DetectionEvent, TestSession, Project

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseInvestigatorFixed:
    """Fixed comprehensive database investigation for status display issues"""
    
    def __init__(self):
        self.database_url = get_database_url()
        self.engine = create_engine(self.database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.session = SessionLocal()
        
        # Determine database file path for direct SQLite queries
        if self.database_url.startswith('sqlite:///'):
            self.db_file = self.database_url.replace('sqlite:///', '')
            if not self.db_file.startswith('/'):
                self.db_file = os.path.join(os.getcwd(), self.db_file)
        else:
            self.db_file = None
        
        logger.info(f"Investigating database: {self.database_url}")
        if self.db_file:
            logger.info(f"SQLite file path: {self.db_file}")
    
    def run_comprehensive_investigation(self):
        """Run all investigation checks with correct schema"""
        logger.info("=== STARTING CORRECTED DATABASE INVESTIGATION ===")
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database_url': self.database_url,
            'database_file': self.db_file,
            'investigation_results': {}
        }
        
        try:
            # 1. Direct Database Schema Analysis
            results['investigation_results']['schema'] = self.analyze_schema()
            
            # 2. Video Table Direct Query (corrected columns)
            results['investigation_results']['video_table'] = self.query_video_table_direct()
            
            # 3. DetectionEvent Table Analysis (corrected columns)  
            results['investigation_results']['detection_events'] = self.analyze_detection_events()
            
            # 4. Data Consistency Verification
            results['investigation_results']['consistency'] = self.verify_data_consistency()
            
            # 5. Recent Data Analysis
            results['investigation_results']['recent_data'] = self.analyze_recent_data()
            
            # 6. API-Database Consistency Test
            results['investigation_results']['api_consistency'] = self.test_api_database_consistency()
            
        except Exception as e:
            logger.error(f"Investigation failed: {str(e)}")
            results['investigation_results']['error'] = str(e)
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
        
        finally:
            self.session.close()
        
        # Save results
        self.save_investigation_results(results)
        self.print_summary(results)
        
        return results
    
    def analyze_schema(self):
        """Analyze database schema structure"""
        logger.info("1. Analyzing database schema...")
        
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            schema_info = {
                'tables': tables,
                'table_details': {}
            }
            
            for table in ['videos', 'detection_events', 'test_sessions']:
                if table in tables:
                    columns = inspector.get_columns(table)
                    indexes = inspector.get_indexes(table)
                    foreign_keys = inspector.get_foreign_keys(table)
                    
                    schema_info['table_details'][table] = {
                        'columns': [{'name': col['name'], 'type': str(col['type']), 'nullable': col['nullable']} for col in columns],
                        'indexes': indexes,
                        'foreign_keys': foreign_keys
                    }
            
            return schema_info
            
        except Exception as e:
            logger.error(f"Schema analysis failed: {e}")
            return {'error': str(e)}
    
    def query_video_table_direct(self):
        """Direct query of Video table with correct columns"""
        logger.info("2. Querying Video table directly...")
        
        try:
            # Use correct columns from Video model
            query = text("""
                SELECT 
                    id, 
                    filename, 
                    processing_status,
                    status,
                    ground_truth_generated,
                    created_at,
                    updated_at,
                    project_id
                FROM videos 
                ORDER BY created_at DESC
            """)
            
            result = self.session.execute(query)
            rows = result.fetchall()
            
            video_data = []
            for row in rows:
                video_record = {
                    'id': row[0],
                    'filename': row[1],
                    'processing_status': row[2],
                    'status': row[3],
                    'ground_truth_generated': row[4],
                    'created_at': str(row[5]),
                    'updated_at': str(row[6]),
                    'project_id': row[7]
                }
                video_data.append(video_record)
            
            logger.info(f"Found {len(video_data)} videos in database")
            
            # Status distributions
            processing_status_counts = {}
            status_counts = {}
            for video in video_data:
                proc_status = video['processing_status']
                status = video['status']
                processing_status_counts[proc_status] = processing_status_counts.get(proc_status, 0) + 1
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'total_videos': len(video_data),
                'processing_status_distribution': processing_status_counts,
                'status_distribution': status_counts,
                'videos': video_data
            }
            
        except Exception as e:
            logger.error(f"Video table query failed: {e}")
            return {'error': str(e)}
    
    def analyze_detection_events(self):
        """Analyze DetectionEvent table with correct schema"""
        logger.info("3. Analyzing DetectionEvent table...")
        
        try:
            # Count detection events per video (using correct column name)
            query = text("""
                SELECT 
                    video_id,
                    COUNT(*) as event_count,
                    MIN(timestamp) as first_detection,
                    MAX(timestamp) as last_detection,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM detection_events 
                WHERE video_id IS NOT NULL
                GROUP BY video_id
                ORDER BY event_count DESC
            """)
            
            result = self.session.execute(query)
            rows = result.fetchall()
            
            detection_data = []
            for row in rows:
                detection_record = {
                    'video_id': row[0],
                    'event_count': row[1],
                    'first_detection': str(row[2]) if row[2] else None,
                    'last_detection': str(row[3]) if row[3] else None,
                    'first_created': str(row[4]) if row[4] else None,
                    'last_created': str(row[5]) if row[5] else None
                }
                detection_data.append(detection_record)
            
            # Get total detection events
            total_query = text("SELECT COUNT(*) FROM detection_events")
            total_result = self.session.execute(total_query)
            total_events = total_result.scalar()
            
            # Get events without video_id
            orphaned_query = text("SELECT COUNT(*) FROM detection_events WHERE video_id IS NULL")
            orphaned_result = self.session.execute(orphaned_query)
            orphaned_events = orphaned_result.scalar()
            
            logger.info(f"Found {total_events} total detection events ({orphaned_events} without video_id) across {len(detection_data)} videos")
            
            return {
                'total_detection_events': total_events,
                'orphaned_events': orphaned_events,
                'videos_with_detections': len(detection_data),
                'detection_summary': detection_data
            }
            
        except Exception as e:
            logger.error(f"DetectionEvent analysis failed: {e}")
            return {'error': str(e)}
    
    def verify_data_consistency(self):
        """Check consistency between Video processing_status and DetectionEvent counts"""
        logger.info("4. Verifying data consistency...")
        
        try:
            # Join videos with detection counts using correct schema
            query = text("""
                SELECT 
                    v.id,
                    v.filename,
                    v.processing_status,
                    v.status as video_status,
                    v.ground_truth_generated,
                    COALESCE(de.event_count, 0) as actual_detections,
                    CASE 
                        WHEN COALESCE(de.event_count, 0) = 0 THEN 'no_detections'
                        WHEN COALESCE(de.event_count, 0) < 24 THEN 'incomplete'
                        WHEN COALESCE(de.event_count, 0) = 24 THEN 'complete'
                        ELSE 'excess'
                    END as expected_status,
                    v.updated_at as video_updated,
                    de.last_detection
                FROM videos v
                LEFT JOIN (
                    SELECT 
                        video_id,
                        COUNT(*) as event_count,
                        MAX(timestamp) as last_detection
                    FROM detection_events 
                    WHERE video_id IS NOT NULL
                    GROUP BY video_id
                ) de ON v.id = de.video_id
                ORDER BY v.created_at DESC
            """)
            
            result = self.session.execute(query)
            rows = result.fetchall()
            
            consistency_data = []
            inconsistencies = []
            
            for row in rows:
                record = {
                    'video_id': row[0],
                    'filename': row[1],
                    'stored_processing_status': row[2],
                    'stored_video_status': row[3],
                    'ground_truth_generated': row[4],
                    'actual_detections': row[5],
                    'expected_status': row[6],
                    'video_updated': str(row[7]) if row[7] else None,
                    'last_detection': str(row[8]) if row[8] else None
                }
                
                consistency_data.append(record)
                
                # Check for inconsistencies - CRITICAL ANALYSIS
                if record['stored_processing_status'] == 'Manual' and record['actual_detections'] == 24:
                    inconsistencies.append({
                        **record,
                        'issue': 'Status shows Manual but has complete detections (24) - DATA INTEGRITY ISSUE'
                    })
                elif record['stored_processing_status'] == 'completed' and record['actual_detections'] != 24:
                    inconsistencies.append({
                        **record,
                        'issue': f'Status shows completed but has {record["actual_detections"]} detections'
                    })
                elif record['stored_processing_status'] == 'pending' and record['actual_detections'] > 0:
                    inconsistencies.append({
                        **record,
                        'issue': f'Status shows pending but has {record["actual_detections"]} detections - STATUS NOT UPDATED'
                    })
            
            logger.info(f"Found {len(inconsistencies)} data inconsistencies")
            
            return {
                'total_videos_analyzed': len(consistency_data),
                'inconsistencies_found': len(inconsistencies),
                'inconsistencies': inconsistencies,
                'all_records': consistency_data
            }
            
        except Exception as e:
            logger.error(f"Consistency verification failed: {e}")
            return {'error': str(e)}
    
    def analyze_recent_data(self):
        """Analyze recent DetectionEvents and Video updates"""
        logger.info("5. Analyzing recent data...")
        
        try:
            # Recent detection events
            recent_detections_query = text("""
                SELECT 
                    video_id,
                    test_session_id,
                    timestamp,
                    validation_result,
                    created_at
                FROM detection_events 
                WHERE created_at > datetime('now', '-24 hours')
                ORDER BY created_at DESC
                LIMIT 50
            """)
            
            result = self.session.execute(recent_detections_query)
            recent_detections = []
            for row in result.fetchall():
                recent_detections.append({
                    'video_id': row[0],
                    'test_session_id': row[1],
                    'timestamp': row[2],
                    'validation_result': row[3],
                    'created_at': str(row[4])
                })
            
            # Recent video updates
            recent_videos_query = text("""
                SELECT 
                    id,
                    filename,
                    processing_status,
                    status,
                    created_at,
                    updated_at
                FROM videos 
                WHERE updated_at > datetime('now', '-24 hours')
                ORDER BY updated_at DESC
            """)
            
            result = self.session.execute(recent_videos_query)
            recent_videos = []
            for row in result.fetchall():
                recent_videos.append({
                    'id': row[0],
                    'filename': row[1],
                    'processing_status': row[2],
                    'status': row[3],
                    'created_at': str(row[4]),
                    'updated_at': str(row[5])
                })
            
            return {
                'recent_detections': recent_detections,
                'recent_video_updates': recent_videos,
                'recent_detections_count': len(recent_detections),
                'recent_video_updates_count': len(recent_videos)
            }
            
        except Exception as e:
            logger.error(f"Recent data analysis failed: {e}")
            return {'error': str(e)}
    
    def test_api_database_consistency(self):
        """Test what API should return vs what's stored in database"""
        logger.info("6. Testing API-Database consistency...")
        
        try:
            # Simulate what the API logic should do vs database state
            api_db_mismatch_query = text("""
                SELECT 
                    v.id,
                    v.filename,
                    v.processing_status as db_processing_status,
                    v.status as db_status,
                    COUNT(de.id) as detection_count,
                    CASE 
                        WHEN COUNT(de.id) = 24 THEN 'completed'
                        WHEN COUNT(de.id) > 0 THEN 'processing' 
                        ELSE 'pending'
                    END as expected_processing_status
                FROM videos v
                LEFT JOIN detection_events de ON v.id = de.video_id
                GROUP BY v.id, v.filename, v.processing_status, v.status
                HAVING db_processing_status != expected_processing_status
            """)
            
            result = self.session.execute(api_db_mismatch_query)
            mismatches = []
            for row in result.fetchall():
                mismatches.append({
                    'video_id': row[0],
                    'filename': row[1],
                    'database_processing_status': row[2],
                    'database_status': row[3],
                    'detection_count': row[4],
                    'expected_processing_status': row[5]
                })
            
            return {
                'api_db_mismatches': mismatches,
                'mismatch_count': len(mismatches),
                'has_api_db_inconsistency': len(mismatches) > 0
            }
            
        except Exception as e:
            logger.error(f"API-Database consistency check failed: {e}")
            return {'error': str(e)}
    
    def save_investigation_results(self, results):
        """Save investigation results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"database_investigation_CORRECTED_results_{timestamp}.json"
        filepath = Path(__file__).parent / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Investigation results saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    
    def print_summary(self, results):
        """Print investigation summary with findings"""
        logger.info("=== CORRECTED INVESTIGATION SUMMARY ===")
        
        if 'error' in results['investigation_results']:
            logger.error(f"Investigation failed: {results['investigation_results']['error']}")
            return
        
        try:
            # Video table summary
            video_data = results['investigation_results'].get('video_table', {})
            if video_data and 'processing_status_distribution' in video_data:
                logger.info("Video Processing Status Distribution:")
                for status, count in video_data['processing_status_distribution'].items():
                    logger.info(f"  Processing Status '{status}': {count} videos")
                
                logger.info("Video Status Distribution:")
                for status, count in video_data['status_distribution'].items():
                    logger.info(f"  Status '{status}': {count} videos")
            
            # Detection events summary
            detection_data = results['investigation_results'].get('detection_events', {})
            if detection_data:
                logger.info(f"Detection Events: {detection_data.get('total_detection_events', 0)} total")
                logger.info(f"Videos with detections: {detection_data.get('videos_with_detections', 0)}")
                logger.info(f"Orphaned events: {detection_data.get('orphaned_events', 0)}")
            
            # CRITICAL: Consistency issues
            consistency_data = results['investigation_results'].get('consistency', {})
            if consistency_data and 'inconsistencies' in consistency_data:
                inconsistencies = consistency_data['inconsistencies']
                logger.warning(f"CRITICAL DATA CONSISTENCY ISSUES: {len(inconsistencies)} found")
                
                manual_with_detections = [i for i in inconsistencies if 'Manual but has complete detections' in i.get('issue', '')]
                pending_with_detections = [i for i in inconsistencies if 'pending but has' in i.get('issue', '')]
                
                logger.warning(f"Videos showing 'Manual' but have 24 detections: {len(manual_with_detections)}")
                logger.warning(f"Videos showing 'pending' but have detections: {len(pending_with_detections)}")
                
                for issue in inconsistencies[:3]:  # Show first 3 critical issues
                    logger.error(f"CRITICAL: Video {issue['video_id']} ({issue['filename']}): {issue['issue']}")
            
            # API consistency
            api_data = results['investigation_results'].get('api_consistency', {})
            if api_data and api_data.get('has_api_db_inconsistency'):
                logger.warning(f"API-DATABASE MISMATCHES: {api_data['mismatch_count']} found")
            
            logger.info("=== END CORRECTED INVESTIGATION SUMMARY ===")
            
        except Exception as e:
            logger.error(f"Failed to print summary: {e}")

def main():
    """Main execution function"""
    print("Starting CORRECTED comprehensive database investigation...")
    
    investigator = DatabaseInvestigatorFixed()
    results = investigator.run_comprehensive_investigation()
    
    # Return results for potential use by other scripts
    return results

if __name__ == "__main__":
    main()