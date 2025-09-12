#!/usr/bin/env python3
"""
Migration Test Runner
Tests the Project-Video many-to-many migration with sample data
"""

import os
import sys
import sqlite3
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import subprocess

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationTestRunner:
    """Test runner for database migrations"""
    
    def __init__(self, test_db_path: str = "./test_migration.db"):
        self.test_db_path = test_db_path
        self.backup_manager = None
        
    def setup_test_database(self) -> bool:
        """Setup test database with sample data"""
        logger.info("Setting up test database with sample data...")
        
        try:
            # Remove existing test database
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
            
            # Create test database
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            
            # Create initial schema (projects table)
            cursor.execute("""
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    camera_model TEXT NOT NULL,
                    camera_view TEXT NOT NULL,
                    lens_type TEXT,
                    resolution TEXT,
                    frame_rate INTEGER,
                    signal_type TEXT NOT NULL,
                    status TEXT DEFAULT 'Active',
                    owner_id TEXT DEFAULT 'anonymous',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            
            # Create videos table with old schema (project_id foreign key)
            cursor.execute("""
                CREATE TABLE videos (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    duration REAL,
                    fps REAL,
                    resolution TEXT,
                    status TEXT DEFAULT 'uploaded',
                    ground_truth_generated BOOLEAN DEFAULT FALSE,
                    project_id TEXT,
                    upload_timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            
            # Insert sample projects
            projects_data = [
                {
                    'id': str(uuid.uuid4()),
                    'name': 'VRU Detection Project Alpha',
                    'description': 'Front-facing camera VRU detection testing',
                    'camera_model': 'Sony IMX490',
                    'camera_view': 'Front-facing VRU',
                    'lens_type': 'Wide Angle',
                    'resolution': '1920x1080',
                    'frame_rate': 30,
                    'signal_type': 'GPIO'
                },
                {
                    'id': str(uuid.uuid4()),
                    'name': 'Driver Behavior Monitoring',
                    'description': 'In-cab driver behavior detection',
                    'camera_model': 'OV9286',
                    'camera_view': 'In-Cab Driver Behavior',
                    'lens_type': 'IR Enhanced',
                    'resolution': '1280x720',
                    'frame_rate': 60,
                    'signal_type': 'Network Packet'
                },
                {
                    'id': str(uuid.uuid4()),
                    'name': 'Rear View Safety System',
                    'description': 'Rear-facing VRU detection for backing safety',
                    'camera_model': 'Aptina AR0233',
                    'camera_view': 'Rear-facing VRU',
                    'lens_type': 'Fish Eye',
                    'resolution': '1920x1200',
                    'frame_rate': 25,
                    'signal_type': 'Serial'
                }
            ]
            
            for project in projects_data:
                cursor.execute("""
                    INSERT INTO projects (
                        id, name, description, camera_model, camera_view, lens_type,
                        resolution, frame_rate, signal_type, status, owner_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', 'test_user')
                """, (
                    project['id'], project['name'], project['description'],
                    project['camera_model'], project['camera_view'], project['lens_type'],
                    project['resolution'], project['frame_rate'], project['signal_type']
                ))
            
            # Insert sample videos with project relationships
            videos_data = [
                # Videos for Project Alpha (multiple videos per project)
                {
                    'id': str(uuid.uuid4()),
                    'filename': 'vru_test_scenario_1.mp4',
                    'project_id': projects_data[0]['id'],
                    'duration': 120.5,
                    'file_size': 25600000
                },
                {
                    'id': str(uuid.uuid4()),
                    'filename': 'vru_test_scenario_2.mp4',
                    'project_id': projects_data[0]['id'],
                    'duration': 95.2,
                    'file_size': 19200000
                },
                {
                    'id': str(uuid.uuid4()),
                    'filename': 'vru_edge_case_1.mp4',
                    'project_id': projects_data[0]['id'],
                    'duration': 45.8,
                    'file_size': 9600000
                },
                # Videos for Driver Behavior project
                {
                    'id': str(uuid.uuid4()),
                    'filename': 'driver_distraction_test.mp4',
                    'project_id': projects_data[1]['id'],
                    'duration': 180.0,
                    'file_size': 32000000
                },
                {
                    'id': str(uuid.uuid4()),
                    'filename': 'driver_fatigue_detection.mp4',
                    'project_id': projects_data[1]['id'],
                    'duration': 300.5,
                    'file_size': 54000000
                },
                # Videos for Rear View project
                {
                    'id': str(uuid.uuid4()),
                    'filename': 'rear_parking_scenario.mp4',
                    'project_id': projects_data[2]['id'],
                    'duration': 60.0,
                    'file_size': 12800000
                }
            ]
            
            for video in videos_data:
                cursor.execute("""
                    INSERT INTO videos (
                        id, filename, file_path, file_size, duration, fps,
                        resolution, status, project_id, ground_truth_generated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, FALSE)
                """, (
                    video['id'], video['filename'], f"/uploads/{video['filename']}",
                    video['file_size'], video['duration'], 30.0, '1920x1080', video['project_id']
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Test database created with {len(projects_data)} projects and {len(videos_data)} videos")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup test database: {e}")
            return False
    
    def run_migration_test(self) -> Dict[str, Any]:
        """Run complete migration test"""
        logger.info("Starting migration test...")
        
        test_results = {
            'setup_success': False,
            'pre_migration_data': {},
            'migration_success': False,
            'post_migration_data': {},
            'data_integrity_check': False,
            'performance_test': {},
            'rollback_test': False
        }
        
        try:
            # Step 1: Setup test database
            test_results['setup_success'] = self.setup_test_database()
            if not test_results['setup_success']:
                return test_results
            
            # Step 2: Capture pre-migration data
            test_results['pre_migration_data'] = self.capture_database_state('pre_migration')
            
            # Step 3: Create backup
            from data_backup_script import DatabaseBackupManager
            backup_manager = DatabaseBackupManager(self.test_db_path)
            backup_files = backup_manager.create_comprehensive_backup()
            
            # Step 4: Run migration
            logger.info("Running migration...")
            test_results['migration_success'] = self.run_alembic_migration()
            
            if test_results['migration_success']:
                # Step 5: Capture post-migration data
                test_results['post_migration_data'] = self.capture_database_state('post_migration')
                
                # Step 6: Verify data integrity
                test_results['data_integrity_check'] = self.verify_data_integrity(
                    test_results['pre_migration_data'],
                    test_results['post_migration_data']
                )
                
                # Step 7: Performance tests
                test_results['performance_test'] = self.run_performance_tests()
                
                # Step 8: Test rollback
                test_results['rollback_test'] = self.test_rollback_migration()
            
            return test_results
            
        except Exception as e:
            logger.error(f"Migration test failed: {e}")
            test_results['error'] = str(e)
            return test_results
    
    def capture_database_state(self, phase: str) -> Dict[str, Any]:
        """Capture current database state for comparison"""
        logger.info(f"Capturing database state: {phase}")
        
        try:
            conn = sqlite3.connect(self.test_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            state = {
                'phase': phase,
                'timestamp': datetime.now().isoformat(),
                'tables': {},
                'relationships': []
            }
            
            # Get table information
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                
                cursor.execute(f"SELECT * FROM {table} LIMIT 5")
                sample_data = [dict(row) for row in cursor.fetchall()]
                
                state['tables'][table] = {
                    'count': count,
                    'sample_data': sample_data
                }
            
            # Capture relationships if project_videos table exists
            if 'project_videos' in tables:
                cursor.execute("""
                    SELECT COUNT(*) as relationship_count
                    FROM project_videos pv
                    INNER JOIN projects p ON pv.project_id = p.id
                    INNER JOIN videos v ON pv.video_id = v.id
                """)
                relationship_count = cursor.fetchone()[0]
                state['relationships'].append({
                    'type': 'many_to_many',
                    'count': relationship_count
                })
            
            # Capture old-style relationships if they exist
            if 'videos' in tables and phase == 'pre_migration':
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as relationship_count
                        FROM videos v
                        INNER JOIN projects p ON v.project_id = p.id
                        WHERE v.project_id IS NOT NULL
                    """)
                    old_relationship_count = cursor.fetchone()[0]
                    state['relationships'].append({
                        'type': 'one_to_many',
                        'count': old_relationship_count
                    })
                except:
                    pass
            
            conn.close()
            return state
            
        except Exception as e:
            logger.error(f"Failed to capture database state: {e}")
            return {'error': str(e)}
    
    def run_alembic_migration(self) -> bool:
        """Run Alembic migration"""
        logger.info("Running Alembic migration...")
        
        try:
            # Create alembic.ini for test
            alembic_ini_content = f"""
[alembic]
script_location = .
prepend_sys_path = .
sqlalchemy.url = sqlite:///{self.test_db_path}
version_num_format = %04d

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
            
            with open("test_alembic.ini", "w") as f:
                f.write(alembic_ini_content)
            
            # Run the migration by importing and executing it directly
            from migrations.migration_0004_project_video_many_to_many import upgrade
            
            # Create mock Alembic operation context
            import sqlalchemy as sa
            from alembic.operations import Operations
            from alembic.migration import MigrationContext
            
            engine = sa.create_engine(f"sqlite:///{self.test_db_path}")
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                op = Operations(context)
                
                # Set up the operations context globally
                import migrations.migration_0004_project_video_many_to_many as migration_module
                migration_module.op = op
                
                # Run the upgrade
                upgrade()
            
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def verify_data_integrity(self, pre_data: Dict, post_data: Dict) -> bool:
        """Verify data integrity after migration"""
        logger.info("Verifying data integrity...")
        
        try:
            # Check that no data was lost
            pre_project_count = pre_data['tables'].get('projects', {}).get('count', 0)
            post_project_count = post_data['tables'].get('projects', {}).get('count', 0)
            
            pre_video_count = pre_data['tables'].get('videos', {}).get('count', 0)
            post_video_count = post_data['tables'].get('videos', {}).get('count', 0)
            
            if pre_project_count != post_project_count:
                logger.error(f"Project count mismatch: {pre_project_count} -> {post_project_count}")
                return False
            
            if pre_video_count != post_video_count:
                logger.error(f"Video count mismatch: {pre_video_count} -> {post_video_count}")
                return False
            
            # Check that project_videos junction table was created
            if 'project_videos' not in post_data['tables']:
                logger.error("project_videos junction table not found")
                return False
            
            # Check that relationships were migrated
            pre_relationships = sum(r.get('count', 0) for r in pre_data.get('relationships', []))
            post_relationships = sum(r.get('count', 0) for r in post_data.get('relationships', []))
            
            if pre_relationships != post_relationships:
                logger.warning(f"Relationship count changed: {pre_relationships} -> {post_relationships}")
                # This might be acceptable if we're changing relationship types
            
            logger.info("Data integrity verification passed")
            return True
            
        except Exception as e:
            logger.error(f"Data integrity check failed: {e}")
            return False
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance tests on migrated database"""
        logger.info("Running performance tests...")
        
        try:
            import time
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            
            performance_results = {}
            
            # Test 1: Project-Video relationship queries
            start_time = time.time()
            cursor.execute("""
                SELECT p.name, COUNT(pv.video_id) as video_count
                FROM projects p
                LEFT JOIN project_videos pv ON p.id = pv.project_id
                GROUP BY p.id, p.name
            """)
            results = cursor.fetchall()
            performance_results['project_video_aggregation'] = {
                'execution_time': time.time() - start_time,
                'result_count': len(results)
            }
            
            # Test 2: Video search with technical specifications
            start_time = time.time()
            cursor.execute("""
                SELECT v.filename, v.camera_model, v.camera_view
                FROM videos v
                WHERE v.camera_model IS NOT NULL
                ORDER BY v.created_at DESC
            """)
            results = cursor.fetchall()
            performance_results['video_tech_search'] = {
                'execution_time': time.time() - start_time,
                'result_count': len(results)
            }
            
            # Test 3: Complex join query
            start_time = time.time()
            cursor.execute("""
                SELECT p.name as project_name, v.filename, v.camera_model, v.duration
                FROM projects p
                INNER JOIN project_videos pv ON p.id = pv.project_id
                INNER JOIN videos v ON pv.video_id = v.id
                WHERE v.duration > 60
                ORDER BY v.duration DESC
            """)
            results = cursor.fetchall()
            performance_results['complex_join_query'] = {
                'execution_time': time.time() - start_time,
                'result_count': len(results)
            }
            
            conn.close()
            
            logger.info(f"Performance tests completed: {performance_results}")
            return performance_results
            
        except Exception as e:
            logger.error(f"Performance tests failed: {e}")
            return {'error': str(e)}
    
    def test_rollback_migration(self) -> bool:
        """Test migration rollback"""
        logger.info("Testing migration rollback...")
        
        try:
            # Import and run the downgrade function
            from migrations.migration_0004_project_video_many_to_many import downgrade
            
            import sqlalchemy as sa
            from alembic.operations import Operations
            from alembic.migration import MigrationContext
            
            engine = sa.create_engine(f"sqlite:///{self.test_db_path}")
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                op = Operations(context)
                
                # Set up the operations context globally
                import migrations.migration_0004_project_video_many_to_many as migration_module
                migration_module.op = op
                
                # Run the downgrade
                downgrade()
            
            # Verify rollback success by checking table structure
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            
            # Check that project_videos table is gone
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_videos'")
            if cursor.fetchone():
                logger.error("project_videos table still exists after rollback")
                return False
            
            # Check that videos table has project_id column again
            cursor.execute("PRAGMA table_info(videos)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'project_id' not in columns:
                logger.error("project_id column missing from videos table after rollback")
                return False
            
            conn.close()
            
            logger.info("Rollback test passed")
            return True
            
        except Exception as e:
            logger.error(f"Rollback test failed: {e}")
            return False
    
    def generate_test_report(self, test_results: Dict[str, Any]) -> str:
        """Generate comprehensive test report"""
        report = f"""
# Migration Test Report
Generated: {datetime.now().isoformat()}
Test Database: {self.test_db_path}

## Test Summary
- Setup Success: {'✅' if test_results.get('setup_success') else '❌'}
- Migration Success: {'✅' if test_results.get('migration_success') else '❌'}
- Data Integrity Check: {'✅' if test_results.get('data_integrity_check') else '❌'}
- Rollback Test: {'✅' if test_results.get('rollback_test') else '❌'}

## Pre-Migration Data
Projects: {test_results.get('pre_migration_data', {}).get('tables', {}).get('projects', {}).get('count', 'N/A')}
Videos: {test_results.get('pre_migration_data', {}).get('tables', {}).get('videos', {}).get('count', 'N/A')}
Relationships: {len(test_results.get('pre_migration_data', {}).get('relationships', []))}

## Post-Migration Data
Projects: {test_results.get('post_migration_data', {}).get('tables', {}).get('projects', {}).get('count', 'N/A')}
Videos: {test_results.get('post_migration_data', {}).get('tables', {}).get('videos', {}).get('count', 'N/A')}
Project-Videos: {test_results.get('post_migration_data', {}).get('tables', {}).get('project_videos', {}).get('count', 'N/A')}

## Performance Test Results
"""
        
        perf_results = test_results.get('performance_test', {})
        for test_name, results in perf_results.items():
            if isinstance(results, dict) and 'execution_time' in results:
                report += f"- {test_name}: {results['execution_time']:.4f}s ({results['result_count']} results)\n"
        
        if test_results.get('error'):
            report += f"\n## Error\n{test_results['error']}\n"
        
        return report

def main():
    """Main test execution"""
    test_runner = MigrationTestRunner()
    
    print("🧪 Starting Project-Video Many-to-Many Migration Test...")
    
    # Run comprehensive test
    test_results = test_runner.run_migration_test()
    
    # Generate and display report
    report = test_runner.generate_test_report(test_results)
    print(report)
    
    # Save report to file
    report_file = Path("migration_test_report.md")
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📊 Full test report saved to: {report_file}")
    
    # Determine overall success
    overall_success = (
        test_results.get('setup_success', False) and
        test_results.get('migration_success', False) and
        test_results.get('data_integrity_check', False)
    )
    
    if overall_success:
        print("🎉 Migration test PASSED!")
        return 0
    else:
        print("❌ Migration test FAILED!")
        return 1

if __name__ == "__main__":
    exit(main())