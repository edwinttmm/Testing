#!/usr/bin/env python3
"""
Tests for Different Working Directory Contexts
Tests path resolution robustness when working directory changes
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.path_resolver import PathResolver, PathType, ResolvedPath
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


class TestWorkingDirectoryContexts:
    """Test path resolution across different working directory scenarios"""
    
    @pytest.fixture
    def multi_directory_setup(self):
        """Create multiple directory structures for testing"""
        base_temp = tempfile.mkdtemp(prefix='wd_test_')
        
        contexts = {}
        
        # Create different working directory scenarios
        scenarios = [
            'project_root',
            'backend_subdirectory', 
            'deep_nested_path',
            'different_drive_simulation'
        ]
        
        for scenario in scenarios:
            scenario_path = os.path.join(base_temp, scenario)
            os.makedirs(scenario_path, exist_ok=True)
            
            # Create some subdirectories
            for subdir in ['uploads', 'logs', 'data', 'config']:
                os.makedirs(os.path.join(scenario_path, subdir), exist_ok=True)
            
            contexts[scenario] = scenario_path
        
        yield contexts
        shutil.rmtree(base_temp, ignore_errors=True)
    
    @pytest.fixture
    def local_environment_info(self):
        """Standard local environment info"""
        return EnvironmentInfo(
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
    
    def test_path_resolution_from_project_root(self, multi_directory_setup, local_environment_info):
        """Test path resolution when working directory is project root"""
        project_root = multi_directory_setup['project_root']
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=project_root):
            
            path_resolver = PathResolver()
            
            # Test all path types resolve correctly from project root
            for path_type in PathType:
                resolved = path_resolver.resolve_path(path_type, ensure_exists=False)
                
                assert resolved is not None
                assert isinstance(resolved.path, str)
                assert resolved.absolute_path is not None
                
                # Path should be relative to project root or absolute
                assert os.path.isabs(resolved.absolute_path)
                
                # For local environment, paths should typically be relative to cwd
                if path_type == PathType.UPLOAD_DIRECTORY:
                    assert 'upload' in resolved.path.lower()
    
    def test_path_resolution_from_backend_subdirectory(self, multi_directory_setup, local_environment_info):
        """Test path resolution when working directory is in backend subdirectory"""
        backend_dir = multi_directory_setup['backend_subdirectory']
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=backend_dir):
            
            path_resolver = PathResolver()
            
            # Test upload directory resolution from backend subdirectory
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            # Should resolve correctly even from subdirectory
            assert resolved is not None
            assert 'upload' in resolved.path.lower()
            
            # Absolute path should be valid
            assert os.path.isabs(resolved.absolute_path)
            
            # Test multiple path types
            for path_type in [PathType.LOG_DIRECTORY, PathType.DATA_DIRECTORY, PathType.CONFIG_DIRECTORY]:
                resolved = path_resolver.resolve_path(path_type, ensure_exists=False)
                assert resolved is not None
                assert resolved.resolved_from in ['base_path_local', 'fallback']
    
    def test_path_resolution_from_deep_nested_path(self, multi_directory_setup, local_environment_info):
        """Test path resolution from deeply nested working directory"""
        deep_nested = multi_directory_setup['deep_nested_path']
        
        # Create even deeper nesting
        deeper_path = os.path.join(deep_nested, 'level1', 'level2', 'level3')
        os.makedirs(deeper_path, exist_ok=True)
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=deeper_path):
            
            path_resolver = PathResolver()
            
            # Test that resolution works from deep paths
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved is not None
            assert resolved.path is not None
            
            # Should have valid absolute path
            assert os.path.isabs(resolved.absolute_path)
            
            # Test creating directory structure from deep path
            results = path_resolver.ensure_directory_structure([PathType.UPLOAD_DIRECTORY])
            
            assert PathType.UPLOAD_DIRECTORY.value in results
            upload_result = results[PathType.UPLOAD_DIRECTORY.value]
            assert isinstance(upload_result, ResolvedPath)
    
    def test_absolute_vs_relative_path_consistency(self, multi_directory_setup, local_environment_info):
        """Test consistency between absolute and relative path resolution"""
        scenarios = ['project_root', 'backend_subdirectory', 'deep_nested_path']
        
        path_results = {}
        
        for scenario in scenarios:
            working_dir = multi_directory_setup[scenario]
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=working_dir):
                
                path_resolver = PathResolver()
                
                # Get resolved paths for this working directory
                paths_for_scenario = {}
                for path_type in PathType:
                    resolved = path_resolver.resolve_path(path_type, ensure_exists=False)
                    paths_for_scenario[path_type] = {
                        'relative': resolved.path,
                        'absolute': resolved.absolute_path,
                        'resolved_from': resolved.resolved_from
                    }
                
                path_results[scenario] = paths_for_scenario
        
        # Verify consistency rules
        for scenario, paths in path_results.items():
            for path_type, path_info in paths.items():
                # All absolute paths should be valid
                assert os.path.isabs(path_info['absolute'])
                
                # Resolution method should be consistent for same path type
                assert path_info['resolved_from'] in [
                    'base_path_local', 'fallback', 'env_var_' + path_type.name, 'custom_override'
                ]
    
    def test_working_directory_change_impact(self, multi_directory_setup, local_environment_info):
        """Test impact of working directory changes on cached paths"""
        initial_dir = multi_directory_setup['project_root']
        changed_dir = multi_directory_setup['backend_subdirectory']
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info):
            path_resolver = PathResolver()
            
            # Initial resolution from first directory
            with patch('os.getcwd', return_value=initial_dir):
                initial_resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                initial_absolute = initial_resolved.absolute_path
            
            # Change working directory and resolve again
            with patch('os.getcwd', return_value=changed_dir):
                # Clear cache to force re-resolution
                path_resolver.clear_cache()
                
                changed_resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                changed_absolute = changed_resolved.absolute_path
            
            # Absolute paths might be different due to different base directories
            # But both should be valid absolute paths
            assert os.path.isabs(initial_absolute)
            assert os.path.isabs(changed_absolute)
            
            # Both should resolve successfully
            assert initial_resolved.resolved_from in ['base_path_local', 'fallback']
            assert changed_resolved.resolved_from in ['base_path_local', 'fallback']
    
    def test_custom_path_override_working_directory_independence(self, multi_directory_setup, 
                                                               local_environment_info):
        """Test that custom path overrides work regardless of working directory"""
        custom_upload_path = multi_directory_setup['project_root']  # Use as custom path
        scenarios = ['backend_subdirectory', 'deep_nested_path']
        
        for scenario in scenarios:
            working_dir = multi_directory_setup[scenario]
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=working_dir):
                
                path_resolver = PathResolver()
                
                # Use custom path override
                resolved = path_resolver.resolve_path(
                    PathType.UPLOAD_DIRECTORY,
                    custom_path=custom_upload_path,
                    ensure_exists=False
                )
                
                # Custom path should always win, regardless of working directory
                assert resolved.path == custom_upload_path
                assert resolved.resolved_from == 'custom_override'
                assert resolved.absolute_path == os.path.abspath(custom_upload_path)
    
    def test_environment_variable_working_directory_interaction(self, multi_directory_setup, 
                                                              local_environment_info):
        """Test interaction between environment variables and working directory"""
        env_upload_path = multi_directory_setup['different_drive_simulation']
        
        scenarios = ['project_root', 'backend_subdirectory']
        
        for scenario in scenarios:
            working_dir = multi_directory_setup[scenario]
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=working_dir), \
                 patch.dict(os.environ, {'AIVALIDATION_UPLOAD_DIRECTORY': env_upload_path}):
                
                path_resolver = PathResolver()
                path_resolver.clear_cache()  # Ensure fresh resolution
                
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                
                # Environment variable should always win, regardless of working directory
                assert resolved.path == env_upload_path
                assert resolved.resolved_from.startswith('env_var_')
                assert resolved.absolute_path == os.path.abspath(env_upload_path)
    
    def test_path_validation_across_working_directories(self, multi_directory_setup, 
                                                       local_environment_info):
        """Test path validation results across different working directories"""
        scenarios = ['project_root', 'backend_subdirectory']
        
        validation_results = {}
        
        for scenario in scenarios:
            working_dir = multi_directory_setup[scenario]
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=working_dir):
                
                path_resolver = PathResolver()
                validation = path_resolver.validate_paths()
                validation_results[scenario] = validation
        
        # Compare validation results
        for scenario, validation in validation_results.items():
            assert 'environment_type' in validation
            assert validation['environment_type'] == 'local'
            
            assert 'paths' in validation
            assert len(validation['paths']) == len(PathType)
            
            # All path types should be validated
            for path_type in PathType:
                assert path_type.value in validation['paths']
                path_info = validation['paths'][path_type.value]
                
                # Basic validation checks
                assert 'path' in path_info
                assert 'exists' in path_info
                assert 'resolved_from' in path_info
    
    def test_directory_creation_from_different_working_directories(self, multi_directory_setup, 
                                                                  local_environment_info):
        """Test directory creation works from different working directories"""
        scenarios = ['project_root', 'backend_subdirectory']
        
        for scenario in scenarios:
            working_dir = multi_directory_setup[scenario]
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=working_dir):
                
                path_resolver = PathResolver()
                
                # Test ensuring single directory
                resolved = path_resolver.resolve_path(
                    PathType.TEMP_DIRECTORY,
                    ensure_exists=True
                )
                
                # Directory should be created or already exist
                assert resolved.exists is True or resolved.parent_exists is True
                
                # Test ensuring directory structure
                results = path_resolver.ensure_directory_structure([
                    PathType.UPLOAD_DIRECTORY,
                    PathType.LOG_DIRECTORY
                ])
                
                assert len(results) == 2
                for path_type_name, resolved_path in results.items():
                    assert isinstance(resolved_path, ResolvedPath)
    
    def test_write_access_testing_across_working_directories(self, multi_directory_setup, 
                                                           local_environment_info):
        """Test write access detection from different working directories"""
        scenarios = ['project_root', 'backend_subdirectory']
        
        for scenario in scenarios:
            working_dir = multi_directory_setup[scenario]
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=working_dir):
                
                path_resolver = PathResolver()
                
                # Test write access to working directory
                is_writable = path_resolver._test_write_access(working_dir)
                assert isinstance(is_writable, bool)
                
                # Test write access to resolved paths
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                
                # Write access should be testable
                assert isinstance(resolved.is_writable, bool)
                
                # If path exists, write access result should be meaningful
                if resolved.exists:
                    # Can actually test write access
                    actual_write_access = path_resolver._test_write_access(resolved.path)
                    assert isinstance(actual_write_access, bool)


class TestWorkingDirectoryEdgeCases:
    """Test edge cases related to working directory handling"""
    
    def test_non_existent_working_directory_handling(self, local_environment_info):
        """Test handling when working directory doesn't exist or is inaccessible"""
        non_existent_dir = "/this/directory/should/not/exist"
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=non_existent_dir):
            
            path_resolver = PathResolver()
            
            # Should still be able to resolve paths
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved is not None
            assert resolved.resolved_from in ['base_path_local', 'fallback']
    
    def test_permission_denied_working_directory(self, local_environment_info):
        """Test handling when working directory has restricted permissions"""
        restricted_dir = "/root"  # Typically restricted on most systems
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=restricted_dir):
            
            path_resolver = PathResolver()
            
            # Should handle gracefully even with permission issues
            try:
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                assert resolved is not None
            except PermissionError:
                # If permission error occurs, it should be handled gracefully
                # by the fallback mechanisms
                pass
    
    def test_symbolic_link_working_directory(self, multi_directory_setup, local_environment_info):
        """Test path resolution when working directory is a symbolic link"""
        if os.name == 'nt':  # Skip on Windows where symlinks may not be available
            pytest.skip("Symbolic link test not supported on Windows")
        
        target_dir = multi_directory_setup['project_root']
        link_dir = os.path.join(os.path.dirname(target_dir), 'symlink_working_dir')
        
        try:
            os.symlink(target_dir, link_dir)
            
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('os.getcwd', return_value=link_dir):
                
                path_resolver = PathResolver()
                
                # Should resolve paths correctly even through symbolic link
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                
                assert resolved is not None
                assert resolved.path is not None
                
        except OSError:
            # Skip if symlink creation fails (permissions, etc.)
            pytest.skip("Unable to create symbolic link for testing")
        finally:
            try:
                os.unlink(link_dir)
            except:
                pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])