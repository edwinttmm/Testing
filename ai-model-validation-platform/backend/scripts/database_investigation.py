#!/usr/bin/env python3
"""
Comprehensive Database Investigation Script
Analyzes data integrity issues with persistent "Manual" status display

This script performs direct database queries to identify inconsistencies
between Video table processing_status and actual DetectionEvent data.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker
from database import get_database_url
from models import Video, DetectionEvent, TestSession, Project

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseInvestigator:
    """Comprehensive database investigation for status display issues"""
    
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
        """Run all investigation checks"""
        logger.info("=== STARTING COMPREHENSIVE DATABASE INVESTIGATION ===")
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database_url': self.database_url,
            'database_file': self.db_file,
            'investigation_results': {}
        }
        
        try:
            # 1. Direct Database Schema Analysis
            results['investigation_results']['schema'] = self.analyze_schema()
            
            # 2. Video Table Direct Query
            results['investigation_results']['video_table'] = self.query_video_table_direct()
            
            # 3. DetectionEvent Table Analysis
            results['investigation_results']['detection_events'] = self.analyze_detection_events()
            
            # 4. Data Consistency Verification
            results['investigation_results']['consistency'] = self.verify_data_consistency()
            
            # 5. Recent Data Analysis
            results['investigation_results']['recent_data'] = self.analyze_recent_data()
            
            # 6. Foreign Key Constraint Check
            results['investigation_results']['constraints'] = self.check_foreign_key_constraints()
            
            # 7. Transaction Integrity Check
            results['investigation_results']['transactions'] = self.check_transaction_integrity()
            
            # 8. API-Database Consistency Test
            results['investigation_results']['api_consistency'] = self.test_api_database_consistency()
            
        except Exception as e:
            logger.error(f"Investigation failed: {str(e)}")
            results['investigation_results']['error'] = str(e)
        
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
        """Direct query of Video table to examine actual data"""
        logger.info("2. Querying Video table directly...")
        
        try:
            # Use SQLAlchemy query
            query = text("""
                SELECT 
                    id, 
                    filename, 
                    processing_status, 
                    metadata,
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
                    'metadata': row[3],
                    'created_at': str(row[4]),
                    'updated_at': str(row[5]),
                    'project_id': row[6]
                }
                video_data.append(video_record)
            
            logger.info(f"Found {len(video_data)} videos in database")
            
            # Status distribution
            status_counts = {}
            for video in video_data:
                status = video['processing_status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'total_videos': len(video_data),
                'status_distribution': status_counts,
                'videos': video_data
            }
            
        except Exception as e:
            logger.error(f"Video table query failed: {e}")
            return {'error': str(e)}
    
    def analyze_detection_events(self):
        """Analyze DetectionEvent table and count events per video"""
        logger.info("3. Analyzing DetectionEvent table...")
        
        try:
            # Count detection events per video
            query = text("""
                SELECT 
                    video_id,
                    COUNT(*) as event_count,
                    MIN(timestamp) as first_detection,
                    MAX(timestamp) as last_detection,
                    GROUP_CONCAT(DISTINCT event_type) as event_types
                FROM detection_events 
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
                    'event_types': row[4] if row[4] else None
                }
                detection_data.append(detection_record)
            
            # Get total detection events
            total_query = text("SELECT COUNT(*) FROM detection_events")
            total_result = self.session.execute(total_query)
            total_events = total_result.scalar()
            
            logger.info(f"Found {total_events} total detection events across {len(detection_data)} videos")
            
            return {
                'total_detection_events': total_events,
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
            # Join videos with detection counts
            query = text("""
                SELECT 
                    v.id,
                    v.filename,
                    v.processing_status,
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
                    'stored_status': row[2],
                    'actual_detections': row[3],
                    'expected_status': row[4],
                    'video_updated': str(row[5]) if row[5] else None,
                    'last_detection': str(row[6]) if row[6] else None
                }
                
                consistency_data.append(record)
                
                # Check for inconsistencies
                if record['stored_status'] == 'Manual' and record['actual_detections'] == 24:
                    inconsistencies.append({
                        **record,
                        'issue': 'Status shows Manual but has complete detections (24)'
                    })
                elif record['stored_status'] == 'Completed' and record['actual_detections'] != 24:
                    inconsistencies.append({
                        **record,
                        'issue': f'Status shows Completed but has {record["actual_detections"]} detections'
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
                    event_type,
                    timestamp,
                    metadata
                FROM detection_events 
                WHERE timestamp > datetime('now', '-1 day')
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            
            result = self.session.execute(recent_detections_query)
            recent_detections = []
            for row in result.fetchall():
                recent_detections.append({
                    'video_id': row[0],
                    'event_type': row[1],
                    'timestamp': str(row[2]),
                    'metadata': row[3]
                })
            
            # Recent video updates
            recent_videos_query = text("""
                SELECT 
                    id,
                    filename,
                    processing_status,
                    created_at,
                    updated_at
                FROM videos 
                WHERE updated_at > datetime('now', '-1 day')
                ORDER BY updated_at DESC
            """)
            
            result = self.session.execute(recent_videos_query)
            recent_videos = []
            for row in result.fetchall():
                recent_videos.append({
                    'id': row[0],
                    'filename': row[1],
                    'processing_status': row[2],
                    'created_at': str(row[3]),
                    'updated_at': str(row[4])
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
    
    def check_foreign_key_constraints(self):
        """Check for foreign key constraint violations"""
        logger.info("6. Checking foreign key constraints...")
        
        try:
            # Check for orphaned detection events
            orphaned_detections_query = text("""
                SELECT COUNT(*) as orphaned_count
                FROM detection_events de
                LEFT JOIN videos v ON de.video_id = v.id
                WHERE v.id IS NULL
            """)
            
            result = self.session.execute(orphaned_detections_query)
            orphaned_detections = result.scalar()
            
            # Check for videos without projects (if project_id is supposed to be non-null)
            orphaned_videos_query = text("""
                SELECT COUNT(*) as orphaned_video_count
                FROM videos v
                LEFT JOIN projects p ON v.project_id = p.id
                WHERE v.project_id IS NOT NULL AND p.id IS NULL
            """)
            
            result = self.session.execute(orphaned_videos_query)
            orphaned_videos = result.scalar()
            
            return {
                'orphaned_detection_events': orphaned_detections,
                'orphaned_videos': orphaned_videos,
                'has_constraint_violations': orphaned_detections > 0 or orphaned_videos > 0
            }
            
        except Exception as e:
            logger.error(f"Foreign key constraint check failed: {e}")
            return {'error': str(e)}
    
    def check_transaction_integrity(self):
        """Check for signs of incomplete transactions"""
        logger.info("7. Checking transaction integrity...")
        
        try:
            # Look for videos with detection events but status not updated
            incomplete_transactions_query = text("""
                SELECT 
                    v.id,
                    v.filename,
                    v.processing_status,
                    COUNT(de.id) as detection_count,
                    MAX(de.timestamp) as last_detection_time,
                    v.updated_at as video_updated_time
                FROM videos v
                LEFT JOIN detection_events de ON v.id = de.video_id
                GROUP BY v.id, v.filename, v.processing_status, v.updated_at
                HAVING COUNT(de.id) > 0 
                AND v.processing_status = 'Manual'
                AND datetime(MAX(de.timestamp)) > datetime(v.updated_at)
            """)
            
            result = self.session.execute(incomplete_transactions_query)
            incomplete_transactions = []
            for row in result.fetchall():
                incomplete_transactions.append({
                    'video_id': row[0],
                    'filename': row[1],
                    'processing_status': row[2],
                    'detection_count': row[3],
                    'last_detection_time': str(row[4]),
                    'video_updated_time': str(row[5])
                })
            
            return {
                'incomplete_transactions': incomplete_transactions,
                'incomplete_count': len(incomplete_transactions),
                'has_incomplete_transactions': len(incomplete_transactions) > 0
            }
            
        except Exception as e:
            logger.error(f"Transaction integrity check failed: {e}")
            return {'error': str(e)}
    
    def test_api_database_consistency(self):
        """Test API responses vs direct database queries"""
        logger.info("8. Testing API-Database consistency...")
        
        try:
            # This would normally make API calls, but for now we'll simulate
            # by comparing what the API logic would return vs database state
            
            # Get videos that should show as completed but don't
            api_db_mismatch_query = text("""
                SELECT 
                    v.id,
                    v.filename,
                    v.processing_status as db_status,
                    COUNT(de.id) as detection_count,
                    CASE 
                        WHEN COUNT(de.id) = 24 THEN 'Completed'
                        WHEN COUNT(de.id) > 0 THEN 'Processing'
                        ELSE 'Manual'
                    END as expected_api_status
                FROM videos v
                LEFT JOIN detection_events de ON v.id = de.video_id
                GROUP BY v.id, v.filename, v.processing_status
                HAVING db_status != expected_api_status
            """)
            
            result = self.session.execute(api_db_mismatch_query)
            mismatches = []
            for row in result.fetchall():
                mismatches.append({
                    'video_id': row[0],
                    'filename': row[1],
                    'database_status': row[2],
                    'detection_count': row[3],
                    'expected_api_status': row[4]
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
        filename = f"database_investigation_results_{timestamp}.json"
        filepath = Path(__file__).parent / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Investigation results saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    
    def print_summary(self, results):
        """Print investigation summary"""
        logger.info("=== INVESTIGATION SUMMARY ===")
        
        if 'error' in results['investigation_results']:
            logger.error(f"Investigation failed: {results['investigation_results']['error']}")
            return
        
        try:
            # Video table summary
            video_data = results['investigation_results'].get('video_table', {})
            if video_data and 'status_distribution' in video_data:
                logger.info("Video Status Distribution:")
                for status, count in video_data['status_distribution'].items():
                    logger.info(f"  {status}: {count} videos")
            
            # Consistency issues
            consistency_data = results['investigation_results'].get('consistency', {})
            if consistency_data and 'inconsistencies' in consistency_data:
                inconsistencies = consistency_data['inconsistencies']
                logger.info(f"\nDATA CONSISTENCY ISSUES: {len(inconsistencies)} found")
                for issue in inconsistencies[:5]:  # Show first 5
                    logger.warning(f"  Video {issue['video_id']} ({issue['filename']}): {issue['issue']}")
            
            # Transaction integrity
            transaction_data = results['investigation_results'].get('transactions', {})
            if transaction_data and transaction_data.get('has_incomplete_transactions'):
                logger.warning(f"INCOMPLETE TRANSACTIONS: {transaction_data['incomplete_count']} found")
            
            # Foreign key violations
            constraint_data = results['investigation_results'].get('constraints', {})
            if constraint_data and constraint_data.get('has_constraint_violations'):
                logger.warning("FOREIGN KEY VIOLATIONS detected")
            
            logger.info("=== END INVESTIGATION SUMMARY ===")
            
        except Exception as e:
            logger.error(f"Failed to print summary: {e}")

def main():
    """Main execution function"""
    print("Starting comprehensive database investigation...")
    
    investigator = DatabaseInvestigator()
    results = investigator.run_comprehensive_investigation()
    
    # Return results for potential use by other scripts
    return results

if __name__ == "__main__":
    main()