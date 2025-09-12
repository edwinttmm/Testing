#!/usr/bin/env python3
"""
Unit tests for PathResolver - Path Management Component
Tests path resolution utilities with comprehensive scenarios
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import platform

# Add backend src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../backend/src'))

from config.path_resolver import (
    PathResolver, PathType, ResolvedPath,
    resolve_upload_directory, resolve_log_directory
)
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


class TestPathResolver:
    """Comprehensive tests for PathResolver class"""
    
    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_env_info(self):
        """Mock environment info for controlled testing"""
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
    
    @pytest.fixture
    def path_resolver(self, mock_env_info):
        """Create PathResolver with mocked environment"""
        with patch('config.path_resolver.detect_environment', return_value=mock_env_info):
            resolver = PathResolver()
            resolver._path_cache.clear()  # Clear cache for clean tests
            return resolver

    def test_path_resolver_initialization(self, path_resolver):
        """Test PathResolver initializes correctly"""
        assert path_resolver is not None
        assert hasattr(path_resolver, '_env_info')
        assert hasattr(path_resolver, '_path_cache')
        assert hasattr(path_resolver, '_base_paths')
    
    def test_resolve_upload_directory_default(self, path_resolver, temp_directory):
        """Test default upload directory resolution"""
        with patch('os.getcwd', return_value=temp_directory):
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved is not None
            assert isinstance(resolved, ResolvedPath)
            assert 'uploads' in resolved.path or 'upload' in resolved.path.lower()
            assert resolved.resolved_from in ['base_path_local', 'fallback']
    
    def test_resolve_custom_path_override(self, path_resolver, temp_directory):
        """Test custom path override functionality"""
        custom_path = os.path.join(temp_directory, 'custom_uploads')
        os.makedirs(custom_path, exist_ok=True)
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY, 
            custom_path=custom_path,
            ensure_exists=False
        )
        
        assert resolved.path == custom_path
        assert resolved.resolved_from == 'custom_override'
        assert resolved.exists is True
    
    def test_environment_variable_resolution(self, path_resolver, temp_directory):
        """Test path resolution from environment variables"""
        custom_upload_path = os.path.join(temp_directory, 'env_uploads')
        
        with patch.dict(os.environ, {'AIVALIDATION_UPLOAD_DIRECTORY': custom_upload_path}):
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved.path == custom_upload_path
            assert resolved.resolved_from.startswith('env_var_')
    
    def test_ensure_directory_creation(self, path_resolver, temp_directory):
        """Test directory creation when ensure_exists=True"""
        custom_path = os.path.join(temp_directory, 'new_directory', 'nested')
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=custom_path,
            ensure_exists=True
        )
        
        assert os.path.exists(custom_path)
        assert resolved.exists is True
        assert resolved.parent_exists is True
    
    def test_docker_environment_paths(self, temp_directory):
        """Test path resolution in Docker environment"""
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.95
        )
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info):
            resolver = PathResolver()
            resolved = resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert '/app' in resolved.path or resolved.path.startswith('/app')
            assert resolved.resolved_from == 'base_path_docker'
    
    def test_wsl_environment_paths(self, temp_directory):
        """Test path resolution in WSL environment"""
        wsl_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.WSL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="Linux-wsl",
            python_version="3.12.0",
            is_containerized=False,
            is_wsl=True,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.85
        )
        
        with patch('config.path_resolver.detect_environment', return_value=wsl_env_info):
            resolver = PathResolver()
            resolved = resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved.resolved_from == 'base_path_wsl'
    
    def test_path_caching(self, path_resolver, temp_directory):
        """Test path resolution caching functionality"""
        # First resolution
        resolved1 = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
        
        # Second resolution should use cache
        resolved2 = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
        
        assert resolved1 is resolved2  # Should be the same cached object
        assert len(path_resolver._path_cache) > 0
    
    def test_path_access_permissions(self, path_resolver, temp_directory):
        """Test path access permission checking"""
        # Create a directory with known permissions
        test_dir = os.path.join(temp_directory, 'test_permissions')
        os.makedirs(test_dir)
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=test_dir,
            ensure_exists=False
        )
        
        assert resolved.exists is True
        # Permissions may vary by system, but should be detectable
        assert isinstance(resolved.is_readable, bool)
        assert isinstance(resolved.is_writable, bool)
    
    def test_fallback_resolution(self, path_resolver):
        """Test fallback path resolution when all else fails"""
        # Mock all resolution methods to fail except fallback
        with patch.object(path_resolver, '_resolve_from_custom', return_value=None), \
             patch.object(path_resolver, '_resolve_from_environment_variables', return_value=None), \
             patch.object(path_resolver, '_resolve_from_base_paths', return_value=None):
            
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved.resolved_from == 'fallback'
            assert 'upload' in resolved.path.lower()
    
    def test_all_path_types(self, path_resolver):
        """Test resolution for all PathType enums"""
        for path_type in PathType:
            resolved = path_resolver.resolve_path(path_type, ensure_exists=False)
            
            assert resolved is not None
            assert isinstance(resolved, ResolvedPath)
            assert resolved.path is not None
            assert resolved.resolved_from is not None
    
    def test_path_expansion(self, path_resolver):
        """Test path expansion for ~, environment variables, etc."""
        home_path = "~/test_uploads"
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=home_path,
            ensure_exists=False
        )
        
        assert '~' not in resolved.path  # Should be expanded
        assert os.path.expanduser('~') in resolved.absolute_path
    
    def test_convenience_functions(self, temp_directory):
        """Test convenience functions for common paths"""
        with patch('os.getcwd', return_value=temp_directory):
            upload_dir = resolve_upload_directory()
            log_dir = resolve_log_directory()
            
            assert upload_dir is not None
            assert log_dir is not None
            assert isinstance(upload_dir, str)
            assert isinstance(log_dir, str)
    
    def test_path_validation_comprehensive(self, path_resolver):
        """Test comprehensive path validation"""
        validation_results = path_resolver.validate_paths()
        
        assert 'environment_type' in validation_results
        assert 'service_mode' in validation_results
        assert 'paths' in validation_results
        assert 'warnings' in validation_results
        assert 'errors' in validation_results
        
        # Check that all path types are validated
        for path_type in PathType:
            assert path_type.value in validation_results['paths']
    
    def test_ensure_directory_structure(self, path_resolver, temp_directory):
        """Test ensuring entire directory structure"""
        with patch('os.getcwd', return_value=temp_directory):
            results = path_resolver.ensure_directory_structure()
            
            assert isinstance(results, dict)
            assert len(results) == len(PathType)
            
            for path_type_name, resolved_path in results.items():
                assert isinstance(resolved_path, ResolvedPath)
    
    def test_write_access_testing(self, path_resolver, temp_directory):
        """Test write access detection functionality"""
        # Test with writable directory
        writable_dir = os.path.join(temp_directory, 'writable')
        os.makedirs(writable_dir)
        
        is_writable = path_resolver._test_write_access(writable_dir)
        assert is_writable is True
        
        # Test with non-existent path (should test parent)
        non_existent = os.path.join(temp_directory, 'does_not_exist')
        is_writable = path_resolver._test_write_access(non_existent)
        assert isinstance(is_writable, bool)
    
    def test_error_handling_invalid_paths(self, path_resolver):
        """Test error handling for invalid paths"""
        # Test with invalid custom path
        invalid_path = "/this/path/should/not/exist/hopefully"
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=invalid_path,
            ensure_exists=False
        )
        
        assert resolved is not None
        assert resolved.exists is False
        # Should still provide a resolved path even if invalid
    
    def test_clear_cache(self, path_resolver):
        """Test cache clearing functionality"""
        # Populate cache
        path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
        assert len(path_resolver._path_cache) > 0
        
        # Clear cache
        path_resolver.clear_cache()
        assert len(path_resolver._path_cache) == 0
    
    def test_get_path_summary(self, path_resolver):
        """Test path summary functionality"""
        summary = path_resolver.get_path_summary()
        
        assert isinstance(summary, dict)
        assert len(summary) == len(PathType)
        
        for path_type in PathType:
            assert path_type.value in summary
            assert isinstance(summary[path_type.value], str)


class TestPathResolverEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_permission_denied_directory_creation(self, temp_directory):
        """Test handling when directory creation fails due to permissions"""
        mock_env_info = EnvironmentInfo(
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
        
        with patch('config.path_resolver.detect_environment', return_value=mock_env_info):
            resolver = PathResolver()
            
            # Mock os.makedirs to raise PermissionError
            with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
                resolved = resolver.resolve_path(
                    PathType.UPLOAD_DIRECTORY,
                    custom_path="/root/restricted",
                    ensure_exists=True
                )
                
                # Should still return a resolved path, but exists should be False
                assert resolved is not None
                assert resolved.exists is False
    
    def test_multiple_environment_variables(self, temp_directory):
        """Test resolution when multiple environment variables are set"""
        mock_env_info = EnvironmentInfo(
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
        
        with patch('config.path_resolver.detect_environment', return_value=mock_env_info):
            resolver = PathResolver()
            
            # Set multiple environment variables
            env_vars = {
                'AIVALIDATION_UPLOAD_DIRECTORY': os.path.join(temp_directory, 'specific'),
                'UPLOAD_DIRECTORY': os.path.join(temp_directory, 'general'),
                'UPLOADS_PATH': os.path.join(temp_directory, 'alternative')
            }
            
            with patch.dict(os.environ, env_vars):
                resolved = resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                
                # Should use the first priority variable
                expected_path = env_vars['AIVALIDATION_UPLOAD_DIRECTORY']
                assert resolved.path == expected_path
                assert resolved.resolved_from == 'env_var_AIVALIDATION_UPLOAD_DIRECTORY'
    
    def test_circular_dependency_protection(self, temp_directory):
        """Test protection against circular path dependencies"""
        mock_env_info = EnvironmentInfo(
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
        
        with patch('config.path_resolver.detect_environment', return_value=mock_env_info):
            resolver = PathResolver()
            
            # Mock recursive test_write_access to prevent infinite recursion
            original_method = resolver._test_write_access
            call_count = 0
            
            def mock_test_write_access(path):
                nonlocal call_count
                call_count += 1
                if call_count > 10:  # Prevent infinite recursion in test
                    return False
                return original_method(path)
            
            with patch.object(resolver, '_test_write_access', side_effect=mock_test_write_access):
                # This should not cause infinite recursion
                resolved = resolver._create_resolved_path("/non/existent/deep/path", "test")
                assert resolved is not None


class TestPathResolverIntegration:
    """Integration tests combining multiple path resolution features"""
    
    def test_complete_path_workflow(self, temp_directory):
        """Test complete path resolution workflow"""
        # Create a realistic directory structure
        base_dir = os.path.join(temp_directory, 'app')
        os.makedirs(base_dir)
        
        # Set environment to simulate production Docker
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'container-123'},
            filesystem_info={'working_directory': base_dir},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value=base_dir):
            
            resolver = PathResolver()
            
            # Test directory structure creation
            results = resolver.ensure_directory_structure()
            
            # Validate all directories were processed
            assert len(results) == len(PathType)
            
            # Test validation
            validation = resolver.validate_paths()
            assert validation['environment_type'] == 'docker'
            assert validation['service_mode'] == 'production'
            
            # Test summary
            summary = resolver.get_path_summary()
            assert all('/app' in path or path.startswith('./') for path in summary.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])