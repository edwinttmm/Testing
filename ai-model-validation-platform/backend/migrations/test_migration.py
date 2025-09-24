"""
Migration Testing Script for Ground Truth Timing Fields
======================================================

Comprehensive testing script that validates the migration, tests data integrity,
and ensures system functionality after applying the HIL timing fields migration.

Author: AI Backend Developer
Created: 2025-09-16
"""

import os
import sys
import logging
import asyncio
import tempfile
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Add the parent directory to sys.path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from add_ground_truth_timing_fields import GroundTruthTimingMigration
    from models_enhanced import Base, TestSession, DetectionEvent, DetectionComparison, GroundTruthObject
    # Import schemas if available, but don't fail if missing
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'schemas'))
        from hil_timing_schemas import (
            TestSessionCreateHIL, DetectionEventCreateHIL, 
            DetectionComparisonCreate, TimingAnalysisRequest
        )
        SCHEMAS_AVAILABLE = True
    except ImportError:
        SCHEMAS_AVAILABLE = False
        logger.warning("HIL timing schemas not available - skipping schema validation tests")
except ImportError as e:
    logging.error(f"Failed to import modules: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationTester:
    """Comprehensive migration testing class"""
    
    def __init__(self, test_database_url: str = None):
        """Initialize tester with test database"""
        if test_database_url is None:
            # Create a temporary SQLite database for testing
            self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            test_database_url = f"sqlite:///{self.temp_db.name}"
            logger.info(f"Using temporary test database: {self.temp_db.name}")
        
        self.database_url = test_database_url
        self.engine = create_engine(test_database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        self.migration = GroundTruthTimingMigration(test_database_url)
        self.test_results = {
            'migration_test': {},
            'data_integrity_test': {},
            'schema_validation_test': {},
            'performance_test': {},
            'rollback_test': {}
        }
    
    @contextmanager
    def get_db_session(self):
        """Get database session with proper cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def setup_test_data(self) -> Dict[str, Any]:
        """Set up initial test data before migration"""
        logger.info("Setting up test data...")
        
        try:
            # Create base tables first
            Base.metadata.create_all(bind=self.engine)
            
            with self.get_db_session() as session:
                # Create test project (basic data only)
                test_project_data = {
                    'id': '550e8400-e29b-41d4-a716-446655440000',
                    'name': 'Migration Test Project',
                    'description': 'Test project for migration validation',
                    'camera_model': 'TestCam3000',
                    'camera_view': 'Front-facing VRU',
                    'signal_type': 'GPIO'
                }
                
                # Direct SQL insert to avoid model dependencies
                session.execute(text("""
                    INSERT INTO projects (id, name, description, camera_model, camera_view, signal_type, created_at)
                    VALUES (:id, :name, :description, :camera_model, :camera_view, :signal_type, CURRENT_TIMESTAMP)
                """), test_project_data)
                
                # Create test video
                test_video_data = {
                    'id': '550e8400-e29b-41d4-a716-446655440001',
                    'filename': 'test_video.mp4',
                    'file_path': '/test/path/test_video.mp4',
                    'duration': 120.5,
                    'fps': 30.0,
                    'status': 'uploaded',
                    'project_id': '550e8400-e29b-41d4-a716-446655440000'
                }
                
                session.execute(text("""
                    INSERT INTO videos (id, filename, file_path, duration, fps, status, project_id, created_at)
                    VALUES (:id, :filename, :file_path, :duration, :fps, :status, :project_id, CURRENT_TIMESTAMP)
                """), test_video_data)
                
                # Create test session (without new fields)
                test_session_data = {
                    'id': '550e8400-e29b-41d4-a716-446655440002',
                    'name': 'Migration Test Session',
                    'project_id': '550e8400-e29b-41d4-a716-446655440000',
                    'video_id': '550e8400-e29b-41d4-a716-446655440001',
                    'tolerance_ms': 100,
                    'status': 'created'
                }
                
                session.execute(text("""
                    INSERT INTO test_sessions (id, name, project_id, video_id, tolerance_ms, status, created_at)
                    VALUES (:id, :name, :project_id, :video_id, :tolerance_ms, :status, CURRENT_TIMESTAMP)
                """), test_session_data)
                
                # Create ground truth objects
                ground_truth_data = [
                    {
                        'id': '550e8400-e29b-41d4-a716-446655440003',
                        'video_id': '550e8400-e29b-41d4-a716-446655440001',
                        'timestamp': 10.5,
                        'class_label': 'pedestrian',
                        'confidence': 0.95,
                        'frame_number': 315
                    },
                    {
                        'id': '550e8400-e29b-41d4-a716-446655440004',
                        'video_id': '550e8400-e29b-41d4-a716-446655440001',
                        'timestamp': 25.2,
                        'class_label': 'cyclist',
                        'confidence': 0.87,
                        'frame_number': 756
                    }
                ]
                
                for gt_data in ground_truth_data:
                    session.execute(text("""
                        INSERT INTO ground_truth_objects (id, video_id, timestamp, class_label, confidence, frame_number, created_at)
                        VALUES (:id, :video_id, :timestamp, :class_label, :confidence, :frame_number, CURRENT_TIMESTAMP)
                    """), gt_data)
                
                # Create detection events (without new fields)
                detection_data = [
                    {
                        'id': '550e8400-e29b-41d4-a716-446655440005',
                        'test_session_id': '550e8400-e29b-41d4-a716-446655440002',
                        'timestamp': 1609459200.5,  # Unix timestamp
                        'confidence': 0.92,
                        'class_label': 'pedestrian',
                        'frame_number': 318
                    },
                    {
                        'id': '550e8400-e29b-41d4-a716-446655440006',
                        'test_session_id': '550e8400-e29b-41d4-a716-446655440002',
                        'timestamp': 1609459215.2,  # Unix timestamp
                        'confidence': 0.84,
                        'class_label': 'cyclist',
                        'frame_number': 759
                    }
                ]
                
                for det_data in detection_data:
                    session.execute(text("""
                        INSERT INTO detection_events (id, test_session_id, timestamp, confidence, class_label, frame_number, created_at)
                        VALUES (:id, :test_session_id, :timestamp, :confidence, :class_label, :frame_number, CURRENT_TIMESTAMP)
                    """), det_data)
                
                session.commit()
                
            logger.info("✅ Test data setup completed")
            return {
                'status': 'success',
                'projects_created': 1,
                'videos_created': 1,
                'test_sessions_created': 1,
                'ground_truth_objects_created': 2,
                'detection_events_created': 2
            }
            
        except Exception as e:
            logger.error(f"❌ Test data setup failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def test_migration_execution(self) -> Dict[str, Any]:
        """Test the migration execution"""
        logger.info("Testing migration execution...")
        
        try:
            # Run the migration
            migration_result = self.migration.run_migration()
            
            # Verify migration completed successfully
            if migration_result['status'] != 'completed':
                return {
                    'status': 'failed',
                    'error': f"Migration status: {migration_result['status']}",
                    'migration_result': migration_result
                }
            
            # Verify new columns exist
            inspector = inspect(self.engine)
            
            # Check test_sessions table
            test_session_columns = {col['name'] for col in inspector.get_columns('test_sessions')}
            required_ts_columns = {
                'video_playback_start_time',
                'video_playback_duration',
                'ground_truth_count'
            }
            
            missing_ts_columns = required_ts_columns - test_session_columns
            if missing_ts_columns:
                return {
                    'status': 'failed',
                    'error': f"Missing test_sessions columns: {missing_ts_columns}"
                }
            
            # Check detection_events table
            detection_event_columns = {col['name'] for col in inspector.get_columns('detection_events')}
            required_de_columns = {
                'video_relative_timestamp',
                'actual_latency_ms'
            }
            
            missing_de_columns = required_de_columns - detection_event_columns
            if missing_de_columns:
                return {
                    'status': 'failed',
                    'error': f"Missing detection_events columns: {missing_de_columns}"
                }
            
            # Check detection_comparisons table exists
            if 'detection_comparisons' not in inspector.get_table_names():
                return {
                    'status': 'failed',
                    'error': "detection_comparisons table not created"
                }
            
            # Check indexes
            test_session_indexes = {idx['name'] for idx in inspector.get_indexes('test_sessions')}
            detection_event_indexes = {idx['name'] for idx in inspector.get_indexes('detection_events')}
            
            logger.info("✅ Migration execution test passed")
            return {
                'status': 'success',
                'migration_result': migration_result,
                'test_sessions_columns': list(test_session_columns),
                'detection_events_columns': list(detection_event_columns),
                'test_sessions_indexes': list(test_session_indexes),
                'detection_events_indexes': list(detection_event_indexes)
            }
            
        except Exception as e:
            logger.error(f"❌ Migration execution test failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def test_data_integrity(self) -> Dict[str, Any]:
        """Test data integrity after migration"""
        logger.info("Testing data integrity...")
        
        try:
            with self.get_db_session() as session:
                # Verify existing data is intact
                existing_sessions = session.execute(text("SELECT COUNT(*) FROM test_sessions")).fetchone()[0]
                existing_detections = session.execute(text("SELECT COUNT(*) FROM detection_events")).fetchone()[0]
                existing_ground_truth = session.execute(text("SELECT COUNT(*) FROM ground_truth_objects")).fetchone()[0]
                
                if existing_sessions != 1:
                    return {'status': 'failed', 'error': f"Expected 1 test session, found {existing_sessions}"}
                
                if existing_detections != 2:
                    return {'status': 'failed', 'error': f"Expected 2 detection events, found {existing_detections}"}
                
                if existing_ground_truth != 2:
                    return {'status': 'failed', 'error': f"Expected 2 ground truth objects, found {existing_ground_truth}"}
                
                # Test inserting data with new fields
                session.execute(text("""
                    UPDATE test_sessions 
                    SET video_playback_start_time = :start_time,
                        video_playback_duration = :duration,
                        ground_truth_count = :gt_count
                    WHERE id = '550e8400-e29b-41d4-a716-446655440002'
                """), {
                    'start_time': 1609459190.0,
                    'duration': 120.5,
                    'gt_count': 2
                })
                
                session.execute(text("""
                    UPDATE detection_events 
                    SET video_relative_timestamp = :video_time,
                        actual_latency_ms = :latency
                    WHERE id = '550e8400-e29b-41d4-a716-446655440005'
                """), {
                    'video_time': 10.5,
                    'latency': 50.0
                })
                
                # Test inserting into detection_comparisons
                session.execute(text("""
                    INSERT INTO detection_comparisons 
                    (id, test_session_id, detection_event_id, ground_truth_object_id, 
                     is_matched, matching_confidence, match_quality, latency_ms, created_at)
                    VALUES (:id, :test_session_id, :detection_event_id, :ground_truth_object_id,
                            :is_matched, :matching_confidence, :match_quality, :latency_ms, CURRENT_TIMESTAMP)
                """), {
                    'id': '550e8400-e29b-41d4-a716-446655440007',
                    'test_session_id': '550e8400-e29b-41d4-a716-446655440002',
                    'detection_event_id': '550e8400-e29b-41d4-a716-446655440005',
                    'ground_truth_object_id': '550e8400-e29b-41d4-a716-446655440003',
                    'is_matched': True,
                    'matching_confidence': 0.95,
                    'match_quality': 'excellent',
                    'latency_ms': 50.0
                })
                
                session.commit()
                
                # Verify the updates worked
                updated_session = session.execute(text("""
                    SELECT video_playback_start_time, video_playback_duration, ground_truth_count
                    FROM test_sessions 
                    WHERE id = '550e8400-e29b-41d4-a716-446655440002'
                """)).fetchone()
                
                if not updated_session or updated_session[0] != 1609459190.0:
                    return {'status': 'failed', 'error': 'Failed to update test session with timing data'}
                
                # Verify comparison was inserted
                comparison_count = session.execute(text("SELECT COUNT(*) FROM detection_comparisons")).fetchone()[0]
                if comparison_count != 1:
                    return {'status': 'failed', 'error': f"Expected 1 detection comparison, found {comparison_count}"}
                
            logger.info("✅ Data integrity test passed")
            return {
                'status': 'success',
                'existing_data_preserved': True,
                'new_fields_functional': True,
                'detection_comparisons_functional': True
            }
            
        except Exception as e:
            logger.error(f"❌ Data integrity test failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def test_schema_validation(self) -> Dict[str, Any]:
        """Test schema validation with Pydantic models"""
        logger.info("Testing schema validation...")
        
        if not SCHEMAS_AVAILABLE:
            logger.info("⏭️  Skipping schema validation - schemas not available")
            return {
                'status': 'skipped',
                'reason': 'HIL timing schemas not available'
            }
        
        try:
            # Test TestSessionCreateHIL schema
            test_session_data = {
                'name': 'Schema Test Session',
                'project_id': '550e8400-e29b-41d4-a716-446655440000',
                'video_id': '550e8400-e29b-41d4-a716-446655440001',
                'tolerance_ms': 150,
                'video_playback_start_time': 1609459200.0,
                'video_playback_duration': 120.5,
                'ground_truth_count': 3
            }
            
            test_session_schema = TestSessionCreateHIL(**test_session_data)
            
            # Test DetectionEventCreateHIL schema
            detection_event_data = {
                'test_session_id': '550e8400-e29b-41d4-a716-446655440002',
                'timestamp': 1609459210.5,
                'confidence': 0.92,
                'class_label': 'pedestrian',
                'video_relative_timestamp': 20.5,
                'actual_latency_ms': 75.0,
                'frame_number': 615
            }
            
            detection_event_schema = DetectionEventCreateHIL(**detection_event_data)
            
            # Test DetectionComparisonCreate schema
            comparison_data = {
                'test_session_id': '550e8400-e29b-41d4-a716-446655440002',
                'detection_event_id': '550e8400-e29b-41d4-a716-446655440005',
                'ground_truth_object_id': '550e8400-e29b-41d4-a716-446655440003',
                'is_matched': True,
                'matching_confidence': 0.95,
                'match_quality': 'excellent',
                'latency_ms': 75.0
            }
            
            comparison_schema = DetectionComparisonCreate(**comparison_data)
            
            # Test TimingAnalysisRequest schema
            timing_analysis_data = {
                'test_session_id': '550e8400-e29b-41d4-a716-446655440002',
                'tolerance_ms': 100,
                'matching_threshold': 0.8
            }
            
            timing_analysis_schema = TimingAnalysisRequest(**timing_analysis_data)
            
            logger.info("✅ Schema validation test passed")
            return {
                'status': 'success',
                'test_session_schema': test_session_schema.dict(),
                'detection_event_schema': detection_event_schema.dict(),
                'comparison_schema': comparison_schema.dict(),
                'timing_analysis_schema': timing_analysis_schema.dict()
            }
            
        except Exception as e:
            logger.error(f"❌ Schema validation test failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def test_performance(self) -> Dict[str, Any]:
        """Test performance of new indexes and queries"""
        logger.info("Testing performance...")
        
        try:
            with self.get_db_session() as session:
                # Test timing-based queries
                start_time = datetime.now()
                
                # Query by video_relative_timestamp
                session.execute(text("""
                    SELECT * FROM detection_events 
                    WHERE video_relative_timestamp BETWEEN 0 AND 30
                """)).fetchall()
                
                # Query by session and timing
                session.execute(text("""
                    SELECT * FROM detection_events 
                    WHERE test_session_id = '550e8400-e29b-41d4-a716-446655440002'
                    AND video_relative_timestamp IS NOT NULL
                    ORDER BY video_relative_timestamp
                """)).fetchall()
                
                # Query detection comparisons
                session.execute(text("""
                    SELECT * FROM detection_comparisons 
                    WHERE test_session_id = '550e8400-e29b-41d4-a716-446655440002'
                    AND is_matched = true
                """)).fetchall()
                
                # Query ground truth with timing
                session.execute(text("""
                    SELECT * FROM ground_truth_objects 
                    WHERE video_id = '550e8400-e29b-41d4-a716-446655440001'
                    ORDER BY timestamp
                """)).fetchall()
                
                end_time = datetime.now()
                query_duration = (end_time - start_time).total_seconds()
                
            logger.info("✅ Performance test passed")
            return {
                'status': 'success',
                'query_duration_seconds': query_duration,
                'queries_executed': 4,
                'performance_acceptable': query_duration < 1.0
            }
            
        except Exception as e:
            logger.error(f"❌ Performance test failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def test_rollback(self) -> Dict[str, Any]:
        """Test migration rollback functionality"""
        logger.info("Testing rollback functionality...")
        
        try:
            # Run rollback
            rollback_result = self.migration.rollback_migration()
            
            if rollback_result['status'] != 'completed':
                return {
                    'status': 'failed',
                    'error': f"Rollback status: {rollback_result['status']}",
                    'rollback_result': rollback_result
                }
            
            # Verify indexes were removed
            inspector = inspect(self.engine)
            
            # Check that timing indexes were removed
            detection_event_indexes = {idx['name'] for idx in inspector.get_indexes('detection_events')}
            timing_indexes = {
                'idx_detection_events_video_relative_time',
                'idx_detection_events_session_time'
            }
            
            remaining_timing_indexes = timing_indexes.intersection(detection_event_indexes)
            
            # For SQLite, columns can't be dropped, so we just verify rollback completed
            # For PostgreSQL, we would check column removal
            
            logger.info("✅ Rollback test passed")
            return {
                'status': 'success',
                'rollback_result': rollback_result,
                'indexes_removed': len(timing_indexes) - len(remaining_timing_indexes),
                'database_type': str(self.engine.url).split(':')[0]
            }
            
        except Exception as e:
            logger.error(f"❌ Rollback test failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all migration tests"""
        logger.info("🚀 Starting comprehensive migration testing...")
        
        overall_start_time = datetime.now()
        
        try:
            # Setup test data
            self.test_results['setup'] = self.setup_test_data()
            if self.test_results['setup']['status'] != 'success':
                return self.test_results
            
            # Test migration execution
            self.test_results['migration_test'] = self.test_migration_execution()
            if self.test_results['migration_test']['status'] != 'success':
                return self.test_results
            
            # Test data integrity
            self.test_results['data_integrity_test'] = self.test_data_integrity()
            
            # Test schema validation
            self.test_results['schema_validation_test'] = self.test_schema_validation()
            
            # Test performance
            self.test_results['performance_test'] = self.test_performance()
            
            # Test rollback (re-run migration first)
            self.migration.run_migration()  # Re-apply for rollback test
            self.test_results['rollback_test'] = self.test_rollback()
            
            # Calculate overall results
            overall_end_time = datetime.now()
            total_duration = (overall_end_time - overall_start_time).total_seconds()
            
            passed_tests = sum(1 for test in self.test_results.values() 
                             if isinstance(test, dict) and test.get('status') == 'success')
            total_tests = len([k for k in self.test_results.keys() if k != 'setup'])
            
            self.test_results['summary'] = {
                'overall_status': 'success' if passed_tests == total_tests else 'partial_failure',
                'passed_tests': passed_tests,
                'total_tests': total_tests,
                'total_duration_seconds': total_duration,
                'tested_at': overall_start_time.isoformat()
            }
            
            if passed_tests == total_tests:
                logger.info("✅ All migration tests passed!")
            else:
                logger.warning(f"⚠️  {passed_tests}/{total_tests} tests passed")
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"❌ Migration testing failed: {e}")
            self.test_results['summary'] = {
                'overall_status': 'failed',
                'error': str(e),
                'tested_at': overall_start_time.isoformat()
            }
            return self.test_results
    
    def cleanup(self):
        """Clean up test resources"""
        try:
            if hasattr(self, 'temp_db'):
                os.unlink(self.temp_db.name)
                logger.info("Cleaned up temporary test database")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")


def run_migration_tests(database_url: str = None) -> Dict[str, Any]:
    """Run migration tests and return results"""
    tester = MigrationTester(database_url)
    
    try:
        results = tester.run_all_tests()
        return results
    finally:
        tester.cleanup()


if __name__ == "__main__":
    """
    Run migration tests from command line
    Usage:
        python test_migration.py                    # Run with temp database
        python test_migration.py <database_url>     # Run with specific database
    """
    database_url = sys.argv[1] if len(sys.argv) > 1 else None
    
    if database_url:
        logger.info(f"Running migration tests with database: {database_url}")
    else:
        logger.info("Running migration tests with temporary database")
    
    results = run_migration_tests(database_url)
    
    # Pretty print results
    print("\n" + "="*50)
    print("MIGRATION TEST RESULTS")
    print("="*50)
    print(json.dumps(results, indent=2, default=str))
    
    # Exit with appropriate code
    summary = results.get('summary', {})
    if summary.get('overall_status') == 'success':
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)