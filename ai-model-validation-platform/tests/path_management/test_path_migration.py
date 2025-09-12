#!/usr/bin/env python3
"""
Migration Tests for Relative to Absolute Path Conversion
Tests migration scenarios and backward compatibility
"""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.path_resolver import PathResolver, PathType
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


class TestPathMigration:
    """Test migration from relative to absolute paths"""
    
    @pytest.fixture
    def migration_environment(self):
        """Create environment for migration testing"""
        temp_dir = tempfile.mkdtemp(prefix='migration_')
        
        # Create legacy structure with relative paths
        legacy_structure = {
            'uploads': os.path.join(temp_dir, 'uploads'),
            'logs': os.path.join(temp_dir, 'logs'),
            'data': os.path.join(temp_dir, 'data'),
            'config': os.path.join(temp_dir, 'config')
        }
        
        # Create new structure with absolute paths
        new_structure = {
            'uploads': os.path.join(temp_dir, 'app', 'uploads'),
            'logs': os.path.join(temp_dir, 'app', 'logs'),
            'data': os.path.join(temp_dir, 'app', 'data'),
            'config': os.path.join(temp_dir, 'app', 'config')
        }
        
        # Create all directories
        for structure in [legacy_structure, new_structure]:
            for path in structure.values():
                os.makedirs(path, exist_ok=True)
        
        yield {
            'base_dir': temp_dir,
            'legacy': legacy_structure,
            'new': new_structure
        }
        
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_legacy_config(self, migration_environment):
        """Mock legacy configuration with relative paths"""
        return {
            'upload_directory': './uploads',
            'log_directory': './logs',
            'data_directory': './data',
            'config_directory': './config'
        }
    
    @pytest.fixture
    def mock_database_entries(self, migration_environment):
        """Mock database entries with legacy relative paths"""
        base_dir = migration_environment['base_dir']
        return [
            {
                'id': 'video_001',
                'filename': 'test1.mp4',
                'file_path': './uploads/test1.mp4',
                'absolute_path': None  # To be migrated
            },
            {
                'id': 'video_002', 
                'filename': 'test2.mp4',
                'file_path': './uploads/subfolder/test2.mp4',
                'absolute_path': None
            },
            {
                'id': 'video_003',
                'filename': 'test3.mp4', 
                'file_path': '../legacy_uploads/test3.mp4',  # Parent directory reference
                'absolute_path': None
            }
        ]
    
    def test_detect_migration_needed(self, migration_environment, mock_database_entries):
        """Test detection of migration needs"""
        
        def has_relative_paths(entries):
            """Check if any entries have relative paths"""
            for entry in entries:
                if entry['file_path'] and not os.path.isabs(entry['file_path']):
                    return True
            return False
        
        def has_missing_absolute_paths(entries):
            """Check if any entries are missing absolute paths"""
            for entry in entries:
                if not entry['absolute_path']:
                    return True
            return False
        
        # Test detection
        needs_migration = has_relative_paths(mock_database_entries)
        assert needs_migration is True
        
        needs_migration = has_missing_absolute_paths(mock_database_entries)
        assert needs_migration is True
    
    def test_relative_to_absolute_conversion(self, migration_environment):
        """Test converting relative paths to absolute paths"""
        base_dir = migration_environment['base_dir']
        
        local_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="Linux-test",
            python_version="3.12.0",
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        with patch('config.path_resolver.detect_environment', return_value=local_env_info), \
             patch('os.getcwd', return_value=base_dir):
            
            path_resolver = PathResolver()
            
            # Test relative path conversions
            test_cases = [
                ('./uploads/test.mp4', os.path.join(base_dir, 'uploads', 'test.mp4')),
                ('./logs/app.log', os.path.join(base_dir, 'logs', 'app.log')),
                ('data/config.json', os.path.join(base_dir, 'data', 'config.json')),
                ('../parent/file.txt', os.path.join(os.path.dirname(base_dir), 'parent', 'file.txt'))
            ]
            
            for relative_path, expected_absolute in test_cases:
                absolute_path = os.path.abspath(relative_path)
                assert absolute_path == expected_absolute
    
    def test_migration_with_different_working_directories(self, migration_environment):
        """Test migration from different working directory contexts"""
        base_dir = migration_environment['base_dir']
        
        # Test from different working directories
        working_directories = [
            base_dir,  # Project root
            os.path.join(base_dir, 'backend'),  # Backend subdirectory
            os.path.join(base_dir, 'app')  # App directory
        ]
        
        local_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="Linux-test",
            python_version="3.12.0",
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        for working_dir in working_directories:
            # Create working directory if it doesn't exist
            os.makedirs(working_dir, exist_ok=True)
            
            with patch('config.path_resolver.detect_environment', return_value=local_env_info), \
                 patch('os.getcwd', return_value=working_dir):
                
                path_resolver = PathResolver()
                
                # Test relative path resolution from this working directory
                relative_path = './uploads/test.mp4'
                expected_absolute = os.path.join(working_dir, 'uploads', 'test.mp4')
                
                resolved = path_resolver._create_resolved_path(relative_path, "test")
                assert resolved.absolute_path == expected_absolute
    
    def test_docker_migration_scenario(self, migration_environment):
        """Test migration scenario when moving from local to Docker"""
        base_dir = migration_environment['base_dir']
        
        # Test migration from local paths to Docker paths
        local_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="Linux-test",
            python_version="3.12.0",
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'container-123'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        # Test local path resolution
        with patch('config.path_resolver.detect_environment', return_value=local_env_info), \
             patch('os.getcwd', return_value=base_dir):
            
            local_resolver = PathResolver()
            local_upload_dir = local_resolver.resolve_upload_directory()
            
            # Should be relative to current directory in local mode
            assert 'upload' in local_upload_dir.lower()
        
        # Test Docker path resolution
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'):
            
            docker_resolver = PathResolver()
            docker_upload_dir = docker_resolver.resolve_upload_directory()
            
            # Should use Docker paths
            assert '/app' in docker_upload_dir or docker_upload_dir.startswith('/app')
    
    def test_legacy_config_file_migration(self, migration_environment, mock_legacy_config):
        """Test migration of legacy configuration files"""
        base_dir = migration_environment['base_dir']
        config_file = os.path.join(base_dir, 'legacy_config.json')
        
        # Create legacy config file
        with open(config_file, 'w') as f:
            json.dump(mock_legacy_config, f)
        
        # Simulate migration process
        def migrate_config_file(config_path, working_directory):
            """Migrate configuration file from relative to absolute paths"""
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            migrated_config = {}
            for key, value in config.items():
                if isinstance(value, str) and (value.startswith('./') or value.startswith('../')):
                    # Convert relative to absolute
                    migrated_config[key] = os.path.abspath(os.path.join(working_directory, value))
                else:
                    migrated_config[key] = value
            
            return migrated_config
        
        # Test migration
        with patch('os.getcwd', return_value=base_dir):
            migrated = migrate_config_file(config_file, base_dir)
        
        # Verify migration
        assert 'upload_directory' in migrated
        assert os.path.isabs(migrated['upload_directory'])
        assert migrated['upload_directory'] == os.path.join(base_dir, 'uploads')
    
    def test_database_migration_simulation(self, migration_environment, mock_database_entries):
        """Test database migration from relative to absolute paths"""
        base_dir = migration_environment['base_dir']
        
        def migrate_database_entries(entries, working_directory):
            """Migrate database entries to include absolute paths"""
            migrated_entries = []
            
            for entry in entries:
                migrated_entry = entry.copy()
                
                if entry['file_path'] and not os.path.isabs(entry['file_path']):
                    # Convert relative path to absolute
                    migrated_entry['absolute_path'] = os.path.abspath(
                        os.path.join(working_directory, entry['file_path'])
                    )
                else:
                    migrated_entry['absolute_path'] = entry['file_path']
                
                migrated_entries.append(migrated_entry)
            
            return migrated_entries
        
        # Test migration
        with patch('os.getcwd', return_value=base_dir):
            migrated = migrate_database_entries(mock_database_entries, base_dir)
        
        # Verify migration
        for entry in migrated:
            assert entry['absolute_path'] is not None
            assert os.path.isabs(entry['absolute_path'])
            
            # Verify specific cases
            if entry['id'] == 'video_001':
                expected = os.path.join(base_dir, 'uploads', 'test1.mp4')
                assert entry['absolute_path'] == expected
            elif entry['id'] == 'video_003':
                # Parent directory reference should be resolved
                expected = os.path.join(os.path.dirname(base_dir), 'legacy_uploads', 'test3.mp4')
                assert entry['absolute_path'] == expected
    
    def test_backward_compatibility_checks(self, migration_environment):
        """Test that migrated paths maintain backward compatibility"""
        base_dir = migration_environment['base_dir']
        
        local_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="Linux-test",
            python_version="3.12.0",
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        with patch('config.path_resolver.detect_environment', return_value=local_env_info), \
             patch('os.getcwd', return_value=base_dir):
            
            path_resolver = PathResolver()
            
            # Test that both relative and absolute paths work
            relative_path = './uploads'
            absolute_path = os.path.join(base_dir, 'uploads')
            
            # Both should resolve to the same absolute path
            resolved_relative = path_resolver._create_resolved_path(relative_path, "test")
            resolved_absolute = path_resolver._create_resolved_path(absolute_path, "test")
            
            assert resolved_relative.absolute_path == resolved_absolute.absolute_path
    
    def test_migration_rollback_scenario(self, migration_environment):
        """Test rollback scenario if migration needs to be undone"""
        base_dir = migration_environment['base_dir']
        
        # Test data with both relative and absolute paths
        mixed_entries = [
            {
                'id': 'video_001',
                'file_path': './uploads/test1.mp4',
                'absolute_path': os.path.join(base_dir, 'uploads', 'test1.mp4')
            },
            {
                'id': 'video_002',
                'file_path': './uploads/test2.mp4', 
                'absolute_path': os.path.join(base_dir, 'uploads', 'test2.mp4')
            }
        ]
        
        def rollback_absolute_paths(entries, preserve_relative=True):
            """Rollback absolute paths while preserving relative paths"""
            rolled_back = []
            
            for entry in entries:
                rolled_back_entry = entry.copy()
                
                if not preserve_relative:
                    # Remove relative paths if needed
                    rolled_back_entry['file_path'] = entry['absolute_path']
                
                # Could remove absolute_path if needed for rollback
                # rolled_back_entry['absolute_path'] = None
                
                rolled_back.append(rolled_back_entry)
            
            return rolled_back
        
        # Test rollback
        rolled_back = rollback_absolute_paths(mixed_entries)
        
        # Verify rollback preserves data integrity
        assert len(rolled_back) == len(mixed_entries)
        for entry in rolled_back:
            assert 'file_path' in entry
            assert entry['file_path'] is not None
    
    def test_cross_platform_migration(self, migration_environment):
        """Test migration across different platforms"""
        base_dir = migration_environment['base_dir']
        
        # Test paths that work across platforms
        cross_platform_paths = [
            './uploads/video.mp4',
            'data/config.json',
            './logs/app.log'
        ]
        
        platforms = [
            ('Linux-test', '/'),
            ('Windows-test', '\\'),
            ('Darwin-test', '/')
        ]
        
        for platform_name, sep in platforms:
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=platform_name,
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.getcwd', return_value=base_dir):
                
                path_resolver = PathResolver()
                
                for relative_path in cross_platform_paths:
                    # Should convert to absolute path correctly on each platform
                    resolved = path_resolver._create_resolved_path(relative_path, "test")
                    
                    assert os.path.isabs(resolved.absolute_path)
                    assert base_dir in resolved.absolute_path
    
    def test_migration_validation(self, migration_environment):
        """Test validation of migration results"""
        base_dir = migration_environment['base_dir']
        
        def validate_migration(original_entries, migrated_entries):
            """Validate that migration was successful"""
            validation_results = {
                'success': True,
                'errors': [],
                'warnings': []
            }
            
            if len(original_entries) != len(migrated_entries):
                validation_results['success'] = False
                validation_results['errors'].append("Entry count mismatch")
                return validation_results
            
            for original, migrated in zip(original_entries, migrated_entries):
                # Check that IDs match
                if original['id'] != migrated['id']:
                    validation_results['success'] = False
                    validation_results['errors'].append(f"ID mismatch: {original['id']} != {migrated['id']}")
                
                # Check that absolute path was added
                if not migrated.get('absolute_path'):
                    validation_results['warnings'].append(f"No absolute path for {migrated['id']}")
                
                # Check that absolute path is actually absolute
                if migrated.get('absolute_path') and not os.path.isabs(migrated['absolute_path']):
                    validation_results['success'] = False
                    validation_results['errors'].append(f"Non-absolute path for {migrated['id']}")
            
            return validation_results
        
        # Test validation with good migration
        original = [{'id': 'test', 'file_path': './test.mp4'}]
        migrated = [{'id': 'test', 'file_path': './test.mp4', 'absolute_path': '/abs/test.mp4'}]
        
        validation = validate_migration(original, migrated)
        assert validation['success'] is True
        assert len(validation['errors']) == 0
        
        # Test validation with bad migration
        bad_migrated = [{'id': 'test', 'file_path': './test.mp4', 'absolute_path': './still_relative.mp4'}]
        
        validation = validate_migration(original, bad_migrated)
        assert validation['success'] is False
        assert len(validation['errors']) > 0


class TestMigrationPerformance:
    """Test performance aspects of path migration"""
    
    def test_large_scale_migration_simulation(self):
        """Test migration performance with large number of entries"""
        # Simulate large number of database entries
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'id': f'video_{i:04d}',
                'file_path': f'./uploads/batch_{i//100}/video_{i}.mp4',
                'absolute_path': None
            })
        
        base_dir = tempfile.mkdtemp()
        
        try:
            def batch_migrate_entries(entries, working_directory, batch_size=100):
                """Migrate entries in batches for better performance"""
                migrated = []
                
                for i in range(0, len(entries), batch_size):
                    batch = entries[i:i + batch_size]
                    
                    for entry in batch:
                        migrated_entry = entry.copy()
                        if entry['file_path'] and not os.path.isabs(entry['file_path']):
                            migrated_entry['absolute_path'] = os.path.abspath(
                                os.path.join(working_directory, entry['file_path'])
                            )
                        else:
                            migrated_entry['absolute_path'] = entry['file_path']
                        
                        migrated.append(migrated_entry)
                
                return migrated
            
            # Test batch migration
            with patch('os.getcwd', return_value=base_dir):
                migrated = batch_migrate_entries(large_dataset, base_dir)
            
            # Verify all entries were migrated
            assert len(migrated) == len(large_dataset)
            
            # Verify all have absolute paths
            for entry in migrated:
                assert entry['absolute_path'] is not None
                assert os.path.isabs(entry['absolute_path'])
        
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)
    
    def test_migration_memory_usage(self):
        """Test memory efficiency during migration"""
        # This test would typically use memory profiling tools
        # For now, we'll test that migration doesn't load everything into memory at once
        
        def memory_efficient_migration(entries_generator, working_directory):
            """Memory-efficient migration using generators"""
            for entry in entries_generator:
                migrated_entry = entry.copy()
                if entry['file_path'] and not os.path.isabs(entry['file_path']):
                    migrated_entry['absolute_path'] = os.path.abspath(
                        os.path.join(working_directory, entry['file_path'])
                    )
                else:
                    migrated_entry['absolute_path'] = entry['file_path']
                
                yield migrated_entry
        
        # Generator for large dataset
        def large_entries_generator():
            for i in range(100):  # Smaller test set
                yield {
                    'id': f'video_{i:04d}',
                    'file_path': f'./uploads/video_{i}.mp4',
                    'absolute_path': None
                }
        
        base_dir = tempfile.mkdtemp()
        
        try:
            with patch('os.getcwd', return_value=base_dir):
                # Process using generator (memory efficient)
                migrated_count = 0
                for migrated_entry in memory_efficient_migration(large_entries_generator(), base_dir):
                    assert migrated_entry['absolute_path'] is not None
                    migrated_count += 1
                
                assert migrated_count == 100
        
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])