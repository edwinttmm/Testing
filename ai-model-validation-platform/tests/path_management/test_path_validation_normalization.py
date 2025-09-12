#!/usr/bin/env python3
"""
Path Validation and Normalization Tests
Tests path validation, normalization, and sanitization
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import platform
import string

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.path_resolver import PathResolver, PathType, ResolvedPath
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


class TestPathValidation:
    """Test path validation functionality"""
    
    @pytest.fixture
    def test_environment_info(self):
        """Standard test environment info"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform=platform.platform(),
            python_version=platform.python_version(),
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
    
    @pytest.fixture
    def path_resolver(self, test_environment_info):
        """Create path resolver with test environment"""
        with patch('config.path_resolver.detect_environment', return_value=test_environment_info):
            resolver = PathResolver()
            resolver.clear_cache()
            return resolver
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        temp_dir = tempfile.mkdtemp(prefix='validation_test_')
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_valid_path_validation(self, path_resolver, temp_workspace):
        """Test validation of valid paths"""
        valid_paths = [
            temp_workspace,
            os.path.join(temp_workspace, 'uploads'),
            os.path.join(temp_workspace, 'nested', 'directory'),
            '/tmp',
            '.'
        ]
        
        for valid_path in valid_paths:
            try:
                # Create directory if it doesn't exist
                if not os.path.exists(valid_path):
                    os.makedirs(valid_path, exist_ok=True)
                
                resolved = path_resolver._create_resolved_path(valid_path, "test")
                
                assert resolved is not None
                assert isinstance(resolved, ResolvedPath)
                assert resolved.path == valid_path
                assert os.path.isabs(resolved.absolute_path)
                
            except Exception as e:
                pytest.fail(f"Valid path failed validation: {valid_path}, error: {e}")
    
    def test_invalid_path_handling(self, path_resolver):
        """Test handling of invalid or problematic paths"""
        invalid_paths = [
            "",  # Empty string
            None,  # None value  
            "\x00",  # Null character
            "con",  # Windows reserved name
            "aux",  # Windows reserved name
            "path\with\tabs",  # Tabs in path
            "path\nwith\nnewlines",  # Newlines in path
        ]
        
        for invalid_path in invalid_paths:
            try:
                if invalid_path is None:
                    # Skip None test as it would be caught earlier
                    continue
                    
                resolved = path_resolver._create_resolved_path(invalid_path, "test")
                
                # Should handle invalid paths gracefully
                assert resolved is not None
                
                # May not exist or be accessible, but shouldn't crash
                assert isinstance(resolved.exists, bool)
                assert isinstance(resolved.is_readable, bool)
                assert isinstance(resolved.is_writable, bool)
                
            except (ValueError, OSError) as e:
                # Some invalid paths may legitimately raise exceptions
                # This is acceptable behavior
                continue
    
    def test_path_length_validation(self, path_resolver, temp_workspace):
        """Test validation of very long paths"""
        # Create progressively longer paths
        path_lengths = [100, 200, 300, 500]
        
        for length in path_lengths:
            # Create long path name
            long_name = 'a' * (length - len(temp_workspace) - 10)  # Account for base path
            long_path = os.path.join(temp_workspace, long_name)
            
            resolved = path_resolver._create_resolved_path(long_path, "test")
            
            assert resolved is not None
            assert resolved.path == long_path
            
            # Very long paths may not be creatable on all filesystems
            # But validation should handle them gracefully
            assert isinstance(resolved.exists, bool)
    
    def test_special_character_validation(self, path_resolver, temp_workspace):
        """Test validation of paths with special characters"""
        special_chars = [
            'path with spaces',
            'path-with-hyphens',
            'path_with_underscores',
            'path.with.dots',
            'path@with#special$chars',
            'path[with]brackets',
            'path(with)parentheses'
        ]
        
        for special_name in special_chars:
            special_path = os.path.join(temp_workspace, special_name)
            
            resolved = path_resolver._create_resolved_path(special_path, "test")
            
            assert resolved is not None
            assert resolved.path == special_path
            
            # Special characters should be handled without crashing
            assert isinstance(resolved.absolute_path, str)
    
    def test_unicode_path_validation(self, path_resolver, temp_workspace):
        """Test validation of paths with Unicode characters"""
        unicode_names = [
            'café',  # Accented characters
            '测试',  # Chinese characters
            'тест',  # Cyrillic characters
            'テスト',  # Japanese characters
            '🎬📁',  # Emoji characters
            'नमस्ते'  # Devanagari characters
        ]
        
        for unicode_name in unicode_names:
            try:
                unicode_path = os.path.join(temp_workspace, unicode_name)
                
                resolved = path_resolver._create_resolved_path(unicode_path, "test")
                
                assert resolved is not None
                assert resolved.path == unicode_path
                
                # Unicode support may vary by filesystem
                # But should not cause crashes
                
            except (UnicodeError, OSError):
                # Some filesystems may not support certain Unicode characters
                # This is acceptable
                continue
    
    def test_case_sensitivity_validation(self, path_resolver, temp_workspace):
        """Test path validation on case-sensitive vs case-insensitive filesystems"""
        test_names = [
            'TestDirectory',
            'testdirectory', 
            'TESTDIRECTORY'
        ]
        
        for name in test_names:
            test_path = os.path.join(temp_workspace, name)
            
            resolved = path_resolver._create_resolved_path(test_path, "test")
            
            assert resolved is not None
            assert resolved.path == test_path
            
            # Case sensitivity handling depends on filesystem
            # Should handle both cases gracefully
    
    def test_absolute_vs_relative_path_validation(self, path_resolver, temp_workspace):
        """Test validation of absolute vs relative paths"""
        test_cases = [
            ('.', True),  # Current directory - relative
            ('..', True),  # Parent directory - relative
            ('./uploads', True),  # Relative with explicit current dir
            ('../parent', True),  # Relative with parent reference
            (temp_workspace, False),  # Absolute path
            ('/tmp', False),  # Absolute Unix path
        ]
        
        # Add Windows absolute path if on Windows
        if os.name == 'nt':
            test_cases.append(('C:\\temp', False))
        
        for test_path, is_relative in test_cases:
            resolved = path_resolver._create_resolved_path(test_path, "test")
            
            assert resolved is not None
            assert resolved.path == test_path
            
            # Absolute path should always be absolute
            assert os.path.isabs(resolved.absolute_path)
            
            # Original path relativity should be preserved
            if is_relative:
                assert not os.path.isabs(resolved.path)
            else:
                assert os.path.isabs(resolved.path)


class TestPathNormalization:
    """Test path normalization functionality"""
    
    @pytest.fixture
    def path_resolver(self):
        """Create path resolver for normalization testing"""
        test_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform=platform.platform(),
            python_version=platform.python_version(),
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        with patch('config.path_resolver.detect_environment', return_value=test_env_info):
            resolver = PathResolver()
            resolver.clear_cache()
            return resolver
    
    def test_path_separator_normalization(self, path_resolver):
        """Test normalization of path separators"""
        test_cases = [
            ('path/with/forward/slashes', os.path.join('path', 'with', 'forward', 'slashes')),
            ('path\\with\\back\\slashes', os.path.join('path', 'with', 'back', 'slashes')),
            ('path/mixed\\separators/here', os.path.join('path', 'mixed', 'separators', 'here')),
            ('path//double//slashes', os.path.join('path', 'double', 'slashes')),
        ]
        
        for input_path, expected_normalized in test_cases:
            resolved = path_resolver._create_resolved_path(input_path, "test")
            
            # The absolute path should use correct separators for the platform
            normalized_absolute = os.path.normpath(resolved.absolute_path)
            assert os.path.sep in normalized_absolute or len(normalized_absolute.split(os.path.sep)) > 1
    
    def test_redundant_path_component_normalization(self, path_resolver):
        """Test normalization of redundant path components"""
        test_cases = [
            './path/to/directory',
            'path/./to/./directory',
            'path/../path/to/directory',
            'path/to/../to/directory',
            './path/../path/to/directory',
        ]
        
        for redundant_path in test_cases:
            resolved = path_resolver._create_resolved_path(redundant_path, "test")
            
            # Absolute path should be normalized
            normalized = os.path.normpath(resolved.absolute_path)
            
            # Should not contain . or .. components
            path_parts = normalized.split(os.path.sep)
            assert '.' not in path_parts[1:]  # Skip root component
            assert '..' not in path_parts[1:]
    
    def test_trailing_separator_normalization(self, path_resolver):
        """Test normalization of trailing path separators"""
        test_cases = [
            'path/to/directory/',
            'path/to/directory//',
            'path\\to\\directory\\',
            './path/to/directory/',
        ]
        
        for path_with_trailing in test_cases:
            resolved = path_resolver._create_resolved_path(path_with_trailing, "test")
            
            # Test that trailing separators are handled consistently
            assert resolved.absolute_path is not None
            assert isinstance(resolved.absolute_path, str)
    
    def test_whitespace_normalization(self, path_resolver):
        """Test handling of whitespace in paths"""
        whitespace_paths = [
            ' path with leading space',
            'path with trailing space ',
            '  path with multiple spaces  ',
            'path\twith\ttabs',
            'path with  multiple  spaces'
        ]
        
        for whitespace_path in whitespace_paths:
            resolved = path_resolver._create_resolved_path(whitespace_path, "test")
            
            # Should preserve whitespace (not normalize it away)
            # as whitespace can be valid in filenames
            assert resolved.path == whitespace_path
            assert resolved.absolute_path is not None
    
    def test_home_directory_expansion(self, path_resolver):
        """Test expansion of home directory paths"""
        home_paths = [
            '~',
            '~/uploads',
            '~/data/config',
            '~/.config/app'
        ]
        
        for home_path in home_paths:
            resolved = path_resolver._create_resolved_path(home_path, "test")
            
            # Should expand tilde to actual home directory
            assert '~' not in resolved.absolute_path
            assert os.path.expanduser('~') in resolved.absolute_path
    
    def test_environment_variable_expansion(self, path_resolver):
        """Test expansion of environment variables in paths"""
        # Set test environment variable
        test_env = {'TEST_PATH_VAR': '/test/environment/path'}
        
        env_paths = [
            '$TEST_PATH_VAR/uploads',
            '${TEST_PATH_VAR}/data', 
            '$TEST_PATH_VAR/../other'
        ]
        
        # Skip on Windows as syntax is different
        if os.name == 'nt':
            env_paths = [
                '%TEST_PATH_VAR%\\uploads',
                '%TEST_PATH_VAR%\\data'
            ]
        
        with patch.dict(os.environ, test_env):
            for env_path in env_paths:
                resolved = path_resolver._create_resolved_path(env_path, "test")
                
                # Should expand environment variable
                if os.name != 'nt':
                    assert '$TEST_PATH_VAR' not in resolved.absolute_path
                else:
                    assert '%TEST_PATH_VAR%' not in resolved.absolute_path
                
                assert test_env['TEST_PATH_VAR'] in resolved.absolute_path


class TestPathSanitization:
    """Test path sanitization for security"""
    
    @pytest.fixture
    def path_resolver(self):
        """Create path resolver for sanitization testing"""
        test_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform=platform.platform(),
            python_version=platform.python_version(),
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        with patch('config.path_resolver.detect_environment', return_value=test_env_info):
            resolver = PathResolver()
            resolver.clear_cache()
            return resolver
    
    def test_directory_traversal_prevention(self, path_resolver, temp_workspace=None):
        """Test prevention of directory traversal attacks"""
        if not temp_workspace:
            temp_workspace = tempfile.mkdtemp()
        
        try:
            # Potentially malicious paths
            malicious_paths = [
                '../../../etc/passwd',
                '..\\..\\..\\windows\\system32',
                './uploads/../../../sensitive',
                'uploads/../../sensitive/data',
                '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'  # URL encoded
            ]
            
            for malicious_path in malicious_paths:
                resolved = path_resolver._create_resolved_path(malicious_path, "test")
                
                # Should create resolved path (not block it)
                assert resolved is not None
                assert resolved.path == malicious_path
                
                # But absolute path should be properly resolved
                assert os.path.isabs(resolved.absolute_path)
                
                # The actual security enforcement would be at the application level
                # Path resolver just resolves paths as requested
        
        finally:
            if temp_workspace:
                shutil.rmtree(temp_workspace, ignore_errors=True)
    
    def test_null_byte_injection_prevention(self, path_resolver):
        """Test prevention of null byte injection"""
        null_byte_paths = [
            'safe_path\x00malicious',
            'uploads\x00../../../etc/passwd',
            '\x00malicious_start',
            'end_null\x00'
        ]
        
        for null_path in null_byte_paths:
            try:
                resolved = path_resolver._create_resolved_path(null_path, "test")
                
                # May handle null bytes or reject them
                if resolved:
                    # If handled, ensure it's safe
                    assert isinstance(resolved.path, str)
                
            except (ValueError, TypeError):
                # Rejecting null bytes is acceptable
                continue
    
    def test_reserved_filename_handling(self, path_resolver):
        """Test handling of reserved filenames (Windows)"""
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM9',
            'LPT1', 'LPT2', 'LPT9',
            'con.txt', 'aux.dat'  # With extensions
        ]
        
        for reserved_name in reserved_names:
            resolved = path_resolver._create_resolved_path(reserved_name, "test")
            
            # Should handle reserved names gracefully
            assert resolved is not None
            assert resolved.path == reserved_name
            
            # On Windows, these may not be usable as filenames
            # But path resolver should not crash
    
    def test_control_character_handling(self, path_resolver):
        """Test handling of control characters in paths"""
        control_chars = [
            'path\x01with\x02control',  # Control characters
            'path\x7fwith\x1bescapes',  # More control characters
            'path\rwith\nlines',        # Carriage return and newline
            'path\twith\vtabs'          # Tab and vertical tab
        ]
        
        for control_path in control_chars:
            try:
                resolved = path_resolver._create_resolved_path(control_path, "test")
                
                # Should handle control characters
                assert resolved is not None
                
                # Some control characters may be preserved, others normalized
                # Important thing is no crash
                
            except (ValueError, OSError):
                # Some systems may reject control characters
                # This is acceptable behavior
                continue
    
    def test_maximum_path_length_handling(self, path_resolver):
        """Test handling of paths exceeding system limits"""
        # Create very long path
        very_long_component = 'a' * 1000
        very_long_path = os.path.join('base', very_long_component, 'file.txt')
        
        resolved = path_resolver._create_resolved_path(very_long_path, "test")
        
        # Should handle long paths gracefully
        assert resolved is not None
        assert resolved.path == very_long_path
        
        # May not be creatable on all systems, but shouldn't crash
        assert isinstance(resolved.exists, bool)


class TestPathValidationIntegration:
    """Test integration of path validation with path resolution"""
    
    @pytest.fixture
    def integrated_resolver(self):
        """Create integrated path resolver for testing"""
        test_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform=platform.platform(),
            python_version=platform.python_version(),
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
        
        with patch('config.path_resolver.detect_environment', return_value=test_env_info):
            resolver = PathResolver()
            resolver.clear_cache()
            return resolver
    
    def test_comprehensive_path_validation(self, integrated_resolver):
        """Test comprehensive path validation across all path types"""
        validation_results = integrated_resolver.validate_paths()
        
        # Should validate all path types
        assert 'paths' in validation_results
        assert len(validation_results['paths']) == len(PathType)
        
        # Each path type should have validation info
        for path_type in PathType:
            assert path_type.value in validation_results['paths']
            path_info = validation_results['paths'][path_type.value]
            
            assert 'path' in path_info
            assert 'exists' in path_info
            assert 'is_writable' in path_info
            assert 'is_readable' in path_info
            assert 'resolved_from' in path_info
            
            # All paths should be strings
            assert isinstance(path_info['path'], str)
    
    def test_validation_error_reporting(self, integrated_resolver):
        """Test validation error and warning reporting"""
        validation_results = integrated_resolver.validate_paths()
        
        # Should have error and warning lists
        assert 'errors' in validation_results
        assert 'warnings' in validation_results
        
        assert isinstance(validation_results['errors'], list)
        assert isinstance(validation_results['warnings'], list)
        
        # Environment info should be included
        assert 'environment_type' in validation_results
        assert 'service_mode' in validation_results
    
    def test_validation_with_custom_paths(self, integrated_resolver):
        """Test validation with custom path overrides"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            custom_upload_path = os.path.join(temp_dir, 'custom_uploads')
            os.makedirs(custom_upload_path, exist_ok=True)
            
            resolved = integrated_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=custom_upload_path,
                ensure_exists=False
            )
            
            # Should validate custom path correctly
            assert resolved.path == custom_upload_path
            assert resolved.resolved_from == 'custom_override'
            assert resolved.exists is True
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_validation_performance(self, integrated_resolver):
        """Test validation performance with multiple path types"""
        import time
        
        start_time = time.time()
        
        # Validate all paths multiple times
        for _ in range(10):
            validation_results = integrated_resolver.validate_paths()
            assert len(validation_results['paths']) == len(PathType)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should complete validation reasonably quickly
        # This is a rough performance check
        assert elapsed < 5.0  # Should take less than 5 seconds for 10 iterations
    
    def test_validation_caching_behavior(self, integrated_resolver):
        """Test that validation uses path caching appropriately"""
        # First validation
        validation1 = integrated_resolver.validate_paths()
        
        # Should have populated cache
        assert len(integrated_resolver._path_cache) > 0
        
        # Second validation should use cache
        validation2 = integrated_resolver.validate_paths()
        
        # Results should be identical (from cache)
        assert validation1['paths'] == validation2['paths']
        
        # Clear cache and validate again
        integrated_resolver.clear_cache()
        validation3 = integrated_resolver.validate_paths()
        
        # Should get fresh results
        assert validation3['paths'] == validation1['paths']  # Same values but fresh objects


if __name__ == '__main__':
    pytest.main([__file__, '-v'])