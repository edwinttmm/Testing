"""
Database Migration: Add Ground Truth Timing Fields for HIL System
================================================================

This migration adds the required columns and indexes to support:
1. Video timing synchronization
2. Ground truth matching with temporal alignment
3. Enhanced detection event tracking
4. Performance metrics for latency analysis

Migration Operations:
1. Add timing fields to test_sessions table
2. Add timing fields to detection_events table  
3. Enhance detection_comparisons table (create if missing)
4. Add performance indexes for timing-based queries
5. Backfill existing data where possible

Author: AI Backend Developer
Created: 2025-09-16
"""

import logging
from sqlalchemy import (
    create_engine, text, inspect, Column, String, Float, Integer, 
    Boolean, ForeignKey, Index, MetaData, Table
)
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError
from sqlalchemy.schema import CreateIndex, DropIndex
from typing import Dict, List, Optional
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GroundTruthTimingMigration:
    """Migration class for ground truth timing fields"""
    
    def __init__(self, database_url: str = None):
        """Initialize migration with database connection"""
        if database_url is None:
            # Get database URL from environment
            database_url = (
                os.getenv("VRU_DATABASE_URL") or
                os.getenv("DATABASE_URL") or 
                os.getenv("AIVALIDATION_DATABASE_URL") or
                "sqlite:///./dev_database.db"
            )
        
        self.engine = create_engine(database_url)
        self.metadata = MetaData()
        self.inspector = inspect(self.engine)
        
        logger.info(f"Migration initialized for database: {self._mask_url(database_url)}")
    
    def _mask_url(self, url: str) -> str:
        """Mask password in database URL for logging"""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)
    
    def check_column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            columns = self.inspector.get_columns(table_name)
            return any(col['name'] == column_name for col in columns)
        except Exception as e:
            logger.warning(f"Could not check column {column_name} in {table_name}: {e}")
            return False
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        return table_name in self.inspector.get_table_names()
    
    def check_index_exists(self, table_name: str, index_name: str) -> bool:
        """Check if an index exists"""
        try:
            indexes = self.inspector.get_indexes(table_name)
            return any(idx['name'] == index_name for idx in indexes)
        except Exception as e:
            logger.warning(f"Could not check index {index_name} on {table_name}: {e}")
            return False
    
    def add_test_sessions_fields(self) -> Dict[str, str]:
        """Add timing fields to test_sessions table"""
        logger.info("Adding timing fields to test_sessions table...")
        results = {}
        
        if not self.check_table_exists('test_sessions'):
            results['test_sessions'] = 'table_not_found'
            logger.warning("test_sessions table not found")
            return results
        
        # Define new columns for test_sessions
        new_columns = [
            ('video_playback_start_time', 'DOUBLE PRECISION'),
            ('video_playback_duration', 'DOUBLE PRECISION'), 
            ('ground_truth_count', 'INTEGER')
        ]
        
        with self.engine.begin() as conn:
            for column_name, column_type in new_columns:
                if not self.check_column_exists('test_sessions', column_name):
                    try:
                        if str(self.engine.url).startswith('sqlite'):
                            # SQLite syntax
                            sql = f"ALTER TABLE test_sessions ADD COLUMN {column_name} {column_type}"
                        else:
                            # PostgreSQL syntax
                            sql = f"ALTER TABLE test_sessions ADD COLUMN {column_name} {column_type}"
                        
                        conn.execute(text(sql))
                        results[column_name] = 'added'
                        logger.info(f"✅ Added column: test_sessions.{column_name}")
                    except Exception as e:
                        results[column_name] = f'error: {str(e)}'
                        logger.error(f"❌ Failed to add column test_sessions.{column_name}: {e}")
                else:
                    results[column_name] = 'already_exists'
                    logger.info(f"ℹ️  Column test_sessions.{column_name} already exists")
        
        return results
    
    def add_detection_events_fields(self) -> Dict[str, str]:
        """Add timing fields to detection_events table"""
        logger.info("Adding timing fields to detection_events table...")
        results = {}
        
        if not self.check_table_exists('detection_events'):
            results['detection_events'] = 'table_not_found'
            logger.warning("detection_events table not found")
            return results
        
        # Define new columns for detection_events
        new_columns = [
            ('video_relative_timestamp', 'DOUBLE PRECISION'),
            ('actual_latency_ms', 'DOUBLE PRECISION'),
            ('ground_truth_match_id', 'VARCHAR(36)')
        ]
        
        with self.engine.begin() as conn:
            for column_name, column_type in new_columns:
                if not self.check_column_exists('detection_events', column_name):
                    try:
                        if str(self.engine.url).startswith('sqlite'):
                            # SQLite syntax
                            sql = f"ALTER TABLE detection_events ADD COLUMN {column_name} {column_type}"
                        else:
                            # PostgreSQL syntax  
                            sql = f"ALTER TABLE detection_events ADD COLUMN {column_name} {column_type}"
                        
                        conn.execute(text(sql))
                        results[column_name] = 'added'
                        logger.info(f"✅ Added column: detection_events.{column_name}")
                    except Exception as e:
                        results[column_name] = f'error: {str(e)}'
                        logger.error(f"❌ Failed to add column detection_events.{column_name}: {e}")
                else:
                    results[column_name] = 'already_exists'
                    logger.info(f"ℹ️  Column detection_events.{column_name} already exists")
        
        return results
    
    def create_detection_comparisons_table(self) -> Dict[str, str]:
        """Create or enhance detection_comparisons table"""
        logger.info("Creating/enhancing detection_comparisons table...")
        results = {}
        
        # Table creation SQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS detection_comparisons (
            id VARCHAR(36) PRIMARY KEY,
            test_session_id VARCHAR(36) NOT NULL,
            detection_event_id VARCHAR(36),
            ground_truth_object_id VARCHAR(36),
            is_matched BOOLEAN DEFAULT FALSE,
            matching_confidence DOUBLE PRECISION,
            match_quality VARCHAR(20),
            latency_ms DOUBLE PRECISION,
            validation_result VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (detection_event_id) REFERENCES detection_events(id) ON DELETE CASCADE,
            FOREIGN KEY (ground_truth_object_id) REFERENCES ground_truth_objects(id) ON DELETE CASCADE
        )
        """
        
        # Enhancement columns if table already exists
        enhancement_columns = [
            ('is_matched', 'BOOLEAN DEFAULT FALSE'),
            ('matching_confidence', 'DOUBLE PRECISION'),
            ('match_quality', 'VARCHAR(20)'),
            ('latency_ms', 'DOUBLE PRECISION')
        ]
        
        try:
            with self.engine.begin() as conn:
                if not self.check_table_exists('detection_comparisons'):
                    # Create new table
                    conn.execute(text(create_table_sql))
                    results['table_created'] = 'success'
                    logger.info("✅ Created detection_comparisons table")
                else:
                    # Enhance existing table
                    for column_name, column_type in enhancement_columns:
                        if not self.check_column_exists('detection_comparisons', column_name):
                            try:
                                sql = f"ALTER TABLE detection_comparisons ADD COLUMN {column_name} {column_type}"
                                conn.execute(text(sql))
                                results[f'added_{column_name}'] = 'success'
                                logger.info(f"✅ Added column: detection_comparisons.{column_name}")
                            except Exception as e:
                                results[f'added_{column_name}'] = f'error: {str(e)}'
                                logger.error(f"❌ Failed to add column detection_comparisons.{column_name}: {e}")
                        else:
                            results[f'added_{column_name}'] = 'already_exists'
                            logger.info(f"ℹ️  Column detection_comparisons.{column_name} already exists")
                
        except Exception as e:
            results['table_created'] = f'error: {str(e)}'
            logger.error(f"❌ Failed to create/enhance detection_comparisons table: {e}")
        
        return results
    
    def add_performance_indexes(self) -> Dict[str, str]:
        """Add performance indexes for timing-based queries"""
        logger.info("Adding performance indexes...")
        results = {}
        
        # Define indexes to create
        indexes_to_create = [
            # Detection events timing indexes
            {
                'table': 'detection_events',
                'name': 'idx_detection_events_video_relative_time',
                'columns': ['video_relative_timestamp'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_detection_events_video_relative_time ON detection_events(video_relative_timestamp)'
            },
            {
                'table': 'detection_events', 
                'name': 'idx_detection_events_session_time',
                'columns': ['test_session_id', 'video_relative_timestamp'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_detection_events_session_time ON detection_events(test_session_id, video_relative_timestamp)'
            },
            # Ground truth timing indexes
            {
                'table': 'ground_truth_objects',
                'name': 'idx_ground_truth_video_time', 
                'columns': ['video_id', 'timestamp'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_ground_truth_video_time ON ground_truth_objects(video_id, timestamp)'
            },
            # Detection comparisons indexes
            {
                'table': 'detection_comparisons',
                'name': 'idx_detection_comparisons_session',
                'columns': ['test_session_id'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_detection_comparisons_session ON detection_comparisons(test_session_id)'
            },
            {
                'table': 'detection_comparisons',
                'name': 'idx_detection_comparisons_matched',
                'columns': ['is_matched', 'match_quality'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_detection_comparisons_matched ON detection_comparisons(is_matched, match_quality)'
            }
        ]
        
        with self.engine.begin() as conn:
            for index_info in indexes_to_create:
                table_name = index_info['table']
                index_name = index_info['name']
                
                if not self.check_table_exists(table_name):
                    results[index_name] = 'table_not_found'
                    logger.warning(f"Table {table_name} not found, skipping index {index_name}")
                    continue
                
                if not self.check_index_exists(table_name, index_name):
                    try:
                        conn.execute(text(index_info['sql']))
                        results[index_name] = 'created'
                        logger.info(f"✅ Created index: {index_name}")
                    except Exception as e:
                        results[index_name] = f'error: {str(e)}'
                        logger.error(f"❌ Failed to create index {index_name}: {e}")
                else:
                    results[index_name] = 'already_exists'
                    logger.info(f"ℹ️  Index {index_name} already exists")
        
        return results
    
    def backfill_existing_data(self) -> Dict[str, str]:
        """Backfill existing data with computed values where possible"""
        logger.info("Backfilling existing data...")
        results = {}
        
        try:
            with self.engine.begin() as conn:
                # Backfill ground_truth_count for test_sessions
                if self.check_column_exists('test_sessions', 'ground_truth_count'):
                    sql = """
                    UPDATE test_sessions 
                    SET ground_truth_count = (
                        SELECT COUNT(*) 
                        FROM ground_truth_objects gto 
                        WHERE gto.video_id = test_sessions.video_id
                    )
                    WHERE ground_truth_count IS NULL
                    """
                    result = conn.execute(text(sql))
                    results['ground_truth_count_backfill'] = f'updated_{result.rowcount}_rows'
                    logger.info(f"✅ Backfilled ground_truth_count for {result.rowcount} test sessions")
                
                # Set default values for new boolean fields
                if self.check_column_exists('detection_comparisons', 'is_matched'):
                    sql = "UPDATE detection_comparisons SET is_matched = FALSE WHERE is_matched IS NULL"
                    result = conn.execute(text(sql))
                    results['is_matched_default'] = f'updated_{result.rowcount}_rows'
                    logger.info(f"✅ Set default is_matched for {result.rowcount} comparisons")
                
        except Exception as e:
            results['backfill_error'] = str(e)
            logger.error(f"❌ Data backfill error: {e}")
        
        return results
    
    def run_migration(self) -> Dict[str, any]:
        """Run the complete migration"""
        logger.info("🚀 Starting Ground Truth Timing Fields Migration...")
        migration_results = {
            'migration_name': 'add_ground_truth_timing_fields',
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Step 1: Add test_sessions fields
            migration_results['test_sessions_fields'] = self.add_test_sessions_fields()
            
            # Step 2: Add detection_events fields
            migration_results['detection_events_fields'] = self.add_detection_events_fields()
            
            # Step 3: Create/enhance detection_comparisons table
            migration_results['detection_comparisons_table'] = self.create_detection_comparisons_table()
            
            # Step 4: Add performance indexes
            migration_results['performance_indexes'] = self.add_performance_indexes()
            
            # Step 5: Backfill existing data
            migration_results['data_backfill'] = self.backfill_existing_data()
            
            migration_results['status'] = 'completed'
            migration_results['completed_at'] = datetime.now().isoformat()
            
            logger.info("✅ Ground Truth Timing Fields Migration completed successfully!")
            
        except Exception as e:
            migration_results['status'] = 'failed'
            migration_results['error'] = str(e)
            migration_results['failed_at'] = datetime.now().isoformat()
            logger.error(f"❌ Migration failed: {e}")
            raise
        
        return migration_results
    
    def rollback_migration(self) -> Dict[str, any]:
        """Rollback the migration by removing added columns and indexes"""
        logger.info("🔄 Rolling back Ground Truth Timing Fields Migration...")
        rollback_results = {
            'rollback_name': 'rollback_ground_truth_timing_fields',
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            with self.engine.begin() as conn:
                # Remove indexes
                indexes_to_drop = [
                    'idx_detection_events_video_relative_time',
                    'idx_detection_events_session_time', 
                    'idx_ground_truth_video_time',
                    'idx_detection_comparisons_session',
                    'idx_detection_comparisons_matched'
                ]
                
                for index_name in indexes_to_drop:
                    try:
                        conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                        logger.info(f"✅ Dropped index: {index_name}")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not drop index {index_name}: {e}")
                
                # Remove columns from test_sessions
                test_sessions_columns = [
                    'video_playback_start_time',
                    'video_playback_duration', 
                    'ground_truth_count'
                ]
                
                # Remove columns from detection_events
                detection_events_columns = [
                    'video_relative_timestamp',
                    'actual_latency_ms',
                    'ground_truth_match_id'
                ]
                
                # Note: SQLite doesn't support DROP COLUMN, so we log what would be removed
                if str(self.engine.url).startswith('sqlite'):
                    logger.warning("SQLite doesn't support DROP COLUMN - columns remain but can be ignored")
                    rollback_results['columns_removed'] = 'sqlite_limitation'
                else:
                    # PostgreSQL supports DROP COLUMN
                    for column in test_sessions_columns:
                        try:
                            conn.execute(text(f"ALTER TABLE test_sessions DROP COLUMN IF EXISTS {column}"))
                            logger.info(f"✅ Dropped column: test_sessions.{column}")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not drop column test_sessions.{column}: {e}")
                    
                    for column in detection_events_columns:
                        try:
                            conn.execute(text(f"ALTER TABLE detection_events DROP COLUMN IF EXISTS {column}"))
                            logger.info(f"✅ Dropped column: detection_events.{column}")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not drop column detection_events.{column}: {e}")
            
            rollback_results['status'] = 'completed'
            rollback_results['completed_at'] = datetime.now().isoformat()
            logger.info("✅ Rollback completed successfully!")
            
        except Exception as e:
            rollback_results['status'] = 'failed'
            rollback_results['error'] = str(e)
            rollback_results['failed_at'] = datetime.now().isoformat()
            logger.error(f"❌ Rollback failed: {e}")
            raise
        
        return rollback_results


def run_migration(database_url: str = None) -> Dict[str, any]:
    """Run the migration"""
    migration = GroundTruthTimingMigration(database_url)
    return migration.run_migration()


def rollback_migration(database_url: str = None) -> Dict[str, any]:
    """Rollback the migration"""
    migration = GroundTruthTimingMigration(database_url)
    return migration.rollback_migration()


if __name__ == "__main__":
    """
    Run migration from command line
    Usage:
        python add_ground_truth_timing_fields.py           # Run migration
        python add_ground_truth_timing_fields.py rollback  # Rollback migration
    """
    import sys
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
            result = rollback_migration()
            print("Rollback Results:", result)
        else:
            result = run_migration()
            print("Migration Results:", result)
    except Exception as e:
        logger.error(f"Command line execution failed: {e}")
        sys.exit(1)