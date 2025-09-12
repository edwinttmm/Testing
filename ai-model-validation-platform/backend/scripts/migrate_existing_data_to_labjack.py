#!/usr/bin/env python3
"""
Data Migration Script for LabJack Timing Validation

This script migrates existing AI validation data to be compatible with LabJack timing validation.
It updates existing DetectionEvent records to use the new validation_result format and 
creates compatible TestResult records with latency metrics.

Usage:
    python scripts/migrate_existing_data_to_labjack.py [--dry-run] [--backup]
"""

import sys
import os
import sqlite3
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add the project root to Python path
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import DATABASE_URL, get_database_url
from models import DetectionEvent, TestSession, TestResult, Project
from sqlalchemy import text


class LabJackDataMigrator:
    """Migrates existing AI validation data to LabJack timing format."""
    
    def __init__(self, database_url: str = None, dry_run: bool = False):
        self.database_url = database_url or get_database_url()
        self.dry_run = dry_run
        self.engine = create_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)
        
        print(f"{'DRY RUN: ' if dry_run else ''}Connecting to database: {self.database_url}")
    
    def backup_database(self) -> str:
        """Create a backup of the database before migration."""
        if 'sqlite' in self.database_url:
            db_path = self.database_url.replace('sqlite:///', '')
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if not self.dry_run:
                import shutil
                shutil.copy2(db_path, backup_path)
                print(f"Database backed up to: {backup_path}")
            else:
                print(f"DRY RUN: Would backup database to: {backup_path}")
            
            return backup_path
        else:
            print("WARNING: Database backup not implemented for non-SQLite databases")
            return None
    
    def migrate_detection_events(self) -> Dict[str, int]:
        """Migrate DetectionEvent records for LabJack compatibility."""
        session = self.Session()
        stats = {
            'total_events': 0,
            'migrated_events': 0,
            'skipped_events': 0,
            'error_events': 0
        }
        
        try:
            # Use raw SQL to query detection events to avoid model mismatch
            result = session.execute(text("SELECT * FROM detection_events"))
            detection_events = result.fetchall()
            stats['total_events'] = len(detection_events)
            
            print(f"Processing {stats['total_events']} detection events...")
            
            for event in detection_events:
                try:
                    # Convert AI validation results to LabJack format
                    current_result = event.validation_result if hasattr(event, 'validation_result') else None
                    if current_result in ['TP', 'TN']:
                        new_result = 'Pass'
                    elif current_result in ['FP', 'FN']:
                        new_result = 'Fail'
                    else:
                        # Keep existing value if it's already in LabJack format or unknown
                        new_result = current_result or 'Unknown'
                    
                    # Check if already migrated
                    current_latency = event.latency_ms if hasattr(event, 'latency_ms') else None
                    
                    if event.timestamp and not current_latency:
                        # Simulate latency based on processing time or default
                        processing_time = event.processing_time_ms if hasattr(event, 'processing_time_ms') and event.processing_time_ms else None
                        simulated_latency = processing_time if processing_time else 50.0
                        
                        if not self.dry_run:
                            # Update using raw SQL to avoid model issues
                            session.execute(text("""
                                UPDATE detection_events 
                                SET validation_result = :new_result,
                                    latency_ms = :latency,
                                    labjack_timestamp = :labjack_ts,
                                    video_start_time = :video_start
                                WHERE id = :event_id
                            """), {
                                'new_result': new_result,
                                'latency': simulated_latency,
                                'labjack_ts': event.timestamp,
                                'video_start': 0.0,
                                'event_id': event.id
                            })
                        
                        stats['migrated_events'] += 1
                        
                        if stats['migrated_events'] % 10 == 0:
                            print(f"  Processed {stats['migrated_events']} events...")
                    else:
                        stats['skipped_events'] += 1
                        
                except Exception as e:
                    print(f"Error processing event {event.id}: {e}")
                    stats['error_events'] += 1
            
            if not self.dry_run:
                session.commit()
                print("Detection events migration committed to database")
            else:
                print("DRY RUN: Detection events changes not committed")
                
        except Exception as e:
            print(f"Error during detection events migration: {e}")
            session.rollback()
            raise
        finally:
            session.close()
        
        return stats
    
    def migrate_test_sessions(self) -> Dict[str, int]:
        """Add LabJack timing fields to existing test sessions."""
        session = self.Session()
        stats = {
            'total_sessions': 0,
            'migrated_sessions': 0,
            'skipped_sessions': 0
        }
        
        try:
            # Use raw SQL to avoid model mismatch issues
            result = session.execute(text("SELECT * FROM test_sessions"))
            test_sessions = result.fetchall()
            stats['total_sessions'] = len(test_sessions)
            
            print(f"Processing {stats['total_sessions']} test sessions...")
            
            for session_obj in test_sessions:
                try:
                    # Check if already has LabJack fields set
                    current_threshold = session_obj.latency_threshold_ms if hasattr(session_obj, 'latency_threshold_ms') else None
                    
                    if not current_threshold:
                        # Set default LabJack timing values
                        tolerance = session_obj.tolerance_ms if hasattr(session_obj, 'tolerance_ms') and session_obj.tolerance_ms else 100
                        
                        if not self.dry_run:
                            session.execute(text("""
                                UPDATE test_sessions 
                                SET latency_threshold_ms = :threshold,
                                    video_start_timestamp = :video_start
                                WHERE id = :session_id
                            """), {
                                'threshold': tolerance,
                                'video_start': 0.0,
                                'session_id': session_obj.id
                            })
                        
                        stats['migrated_sessions'] += 1
                    else:
                        stats['skipped_sessions'] += 1
                        
                except Exception as e:
                    print(f"Error processing session {session_obj.id}: {e}")
            
            if not self.dry_run:
                session.commit()
                print("Test sessions migration committed to database")
            else:
                print("DRY RUN: Test sessions changes not committed")
                
        except Exception as e:
            print(f"Error during test sessions migration: {e}")
            session.rollback()
            raise
        finally:
            session.close()
        
        return stats
    
    def create_labjack_test_results(self) -> Dict[str, int]:
        """Create LabJack-compatible TestResult records for existing test sessions."""
        session = self.Session()
        stats = {
            'total_sessions': 0,
            'created_results': 0,
            'skipped_results': 0,
            'error_results': 0
        }
        
        try:
            # Get test sessions without LabJack-style results
            test_sessions = session.query(TestSession).all()
            stats['total_sessions'] = len(test_sessions)
            
            print(f"Creating LabJack test results for {stats['total_sessions']} sessions...")
            
            for test_session in test_sessions:
                try:
                    # Check if LabJack-style results already exist
                    existing_result = session.query(TestResult).filter_by(
                        test_session_id=test_session.id
                    ).filter(
                        TestResult.pass_rate.isnot(None)
                    ).first()
                    
                    if existing_result:
                        stats['skipped_results'] += 1
                        continue
                    
                    # Get detection events for this session
                    detection_events = session.query(DetectionEvent).filter_by(
                        test_session_id=test_session.id
                    ).all()
                    
                    if not detection_events:
                        stats['skipped_results'] += 1
                        continue
                    
                    # Calculate LabJack timing metrics
                    total_detections = len(detection_events)
                    passed_detections = len([e for e in detection_events if e.validation_result == 'Pass'])
                    failed_detections = total_detections - passed_detections
                    pass_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
                    
                    # Calculate latency statistics
                    latencies = [e.latency_ms for e in detection_events if e.latency_ms is not None]
                    if latencies:
                        avg_latency = sum(latencies) / len(latencies)
                        max_latency = max(latencies)
                        min_latency = min(latencies)
                        
                        # Create latency distribution
                        latency_distribution = {
                            'mean': avg_latency,
                            'median': sorted(latencies)[len(latencies)//2],
                            'std_dev': (sum((x - avg_latency)**2 for x in latencies) / len(latencies))**0.5,
                            'percentiles': {
                                '25th': sorted(latencies)[len(latencies)//4],
                                '75th': sorted(latencies)[3*len(latencies)//4],
                                '95th': sorted(latencies)[min(int(0.95*len(latencies)), len(latencies)-1)]
                            }
                        }
                    else:
                        avg_latency = max_latency = min_latency = None
                        latency_distribution = None
                    
                    # Create or update TestResult record
                    if not self.dry_run:
                        test_result = TestResult(
                            test_session_id=test_session.id,
                            pass_rate=pass_rate,
                            avg_latency_ms=avg_latency,
                            max_latency_ms=max_latency,
                            min_latency_ms=min_latency,
                            total_detections=total_detections,
                            passed_detections=passed_detections,
                            failed_detections=failed_detections,
                            latency_distribution=latency_distribution
                        )
                        session.add(test_result)
                    
                    stats['created_results'] += 1
                    
                    if stats['created_results'] % 10 == 0:
                        print(f"  Created {stats['created_results']} test results...")
                        
                except Exception as e:
                    print(f"Error processing test session {test_session.id}: {e}")
                    stats['error_results'] += 1
            
            if not self.dry_run:
                session.commit()
                print("LabJack test results created and committed")
            else:
                print("DRY RUN: LabJack test results not committed")
                
        except Exception as e:
            print(f"Error during test results creation: {e}")
            session.rollback()
            raise
        finally:
            session.close()
        
        return stats
    
    def run_migration(self, backup: bool = True) -> Dict[str, any]:
        """Run complete migration process."""
        print("=" * 60)
        print("LabJack Timing Validation Data Migration")
        print("=" * 60)
        
        if backup:
            backup_path = self.backup_database()
        
        # Run migrations
        detection_stats = self.migrate_detection_events()
        session_stats = self.migrate_test_sessions()
        result_stats = self.create_labjack_test_results()
        
        # Print summary
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        
        print("\nDetection Events:")
        print(f"  Total events: {detection_stats['total_events']}")
        print(f"  Migrated: {detection_stats['migrated_events']}")
        print(f"  Skipped: {detection_stats['skipped_events']}")
        print(f"  Errors: {detection_stats['error_events']}")
        
        print("\nTest Sessions:")
        print(f"  Total sessions: {session_stats['total_sessions']}")
        print(f"  Migrated: {session_stats['migrated_sessions']}")
        print(f"  Skipped: {session_stats['skipped_sessions']}")
        
        print("\nTest Results:")
        print(f"  Total sessions: {result_stats['total_sessions']}")
        print(f"  Created results: {result_stats['created_results']}")
        print(f"  Skipped: {result_stats['skipped_results']}")
        print(f"  Errors: {result_stats['error_results']}")
        
        if self.dry_run:
            print("\n*** DRY RUN COMPLETED - NO CHANGES MADE ***")
        else:
            print("\n*** MIGRATION COMPLETED SUCCESSFULLY ***")
            
        return {
            'detection_events': detection_stats,
            'test_sessions': session_stats,
            'test_results': result_stats,
            'backup_path': backup_path if backup else None
        }


def main():
    parser = argparse.ArgumentParser(description='Migrate existing data to LabJack timing validation format')
    parser.add_argument('--dry-run', action='store_true', help='Run migration without making changes')
    parser.add_argument('--no-backup', action='store_true', help='Skip database backup')
    parser.add_argument('--database-url', help='Override database URL')
    
    args = parser.parse_args()
    
    try:
        migrator = LabJackDataMigrator(
            database_url=args.database_url,
            dry_run=args.dry_run
        )
        
        results = migrator.run_migration(backup=not args.no_backup)
        
        # Exit with appropriate code
        total_errors = (
            results['detection_events']['error_events'] +
            results['test_results']['error_results']
        )
        
        sys.exit(0 if total_errors == 0 else 1)
        
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nMigration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()