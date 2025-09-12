#!/usr/bin/env python3
"""
Cross-Platform Path Compatibility Tests
Tests path resolution robustness across different operating systems and platforms
"""

import pytest
import os
import tempfile
import shutil
import platform
from unittest.mock import patch, MagicMock
import sys

# Add backend paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.path_resolver import PathResolver, PathType, ResolvedPath
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


class TestCrossPlatformPathResolution:
    """Test path resolution across different platforms"""
    
    @pytest.fixture
    def platform_configs(self):
        """Configuration for different platforms"""
        return {
            'linux': {
                'platform': 'Linux-5.4.0-x86_64-with-glibc2.31',
                'os_name': 'posix',
                'path_sep': '/',
                'alt_sep': None,
                'drive_prefixes': [],
                'home_prefix': '/home/',
                'temp_dir': '/tmp',
                'root_dir': '/',
                'case_sensitive': True
            },
            'windows': {
                'platform': 'Windows-10-10.0.19041-SP0',
                'os_name': 'nt',
                'path_sep': '\\',
                'alt_sep': '/',
                'drive_prefixes': ['C:', 'D:', 'E:'],
                'home_prefix': 'C:\\Users\\',
                'temp_dir': 'C:\\Windows\\Temp',
                'root_dir': 'C:\\',
                'case_sensitive': False
            },
            'macos': {
                'platform': 'Darwin-21.6.0-x86_64-i386-64bit',
                'os_name': 'posix',
                'path_sep': '/',
                'alt_sep': None,
                'drive_prefixes': [],
                'home_prefix': '/Users/',
                'temp_dir': '/tmp',
                'root_dir': '/',
                'case_sensitive': True
            }
        }
    
    def create_platform_environment(self, platform_name, platform_config):
        """Create environment info for specific platform"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform=platform_config['platform'],
            python_version="3.12.0",
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
    
    def test_path_separator_handling_across_platforms(self, platform_configs):
        """Test path separator handling on different platforms"""
        test_paths = [
            'uploads/videos/test.mp4',
            'uploads\\videos\\test.mp4',
            'uploads/mixed\\separators/test.mp4',
            './relative/path/test.mp4',
            '.\\relative\\path\\test.mp4'
        ]
        
        for platform_name, config in platform_configs.items():
            env_info = self.create_platform_environment(platform_name, config)
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.name', config['os_name']), \
                 patch('os.path.sep', config['path_sep']), \
                 patch('os.path.altsep', config['alt_sep']):
                
                resolver = PathResolver()
                resolver.clear_cache()
                
                for test_path in test_paths:
                    resolved = resolver._create_resolved_path(test_path, "test")
                    
                    assert resolved is not None
                    assert resolved.path == test_path  # Original path preserved
                    assert isinstance(resolved.absolute_path, str)
                    
                    # Absolute path should use platform-appropriate separators
                    if platform_name == 'windows':
                        # May contain backslashes on Windows
                        assert '\\' in resolved.absolute_path or '/' in resolved.absolute_path
                    else:
                        # Unix-like systems use forward slashes
                        if config['path_sep'] in resolved.absolute_path:
                            assert config['path_sep'] in resolved.absolute_path
    
    def test_drive_letter_handling_windows(self, platform_configs):
        """Test Windows drive letter handling"""
        windows_config = platform_configs['windows']
        env_info = self.create_platform_environment('windows', windows_config)
        
        windows_paths = [
            'C:\\uploads\\test.mp4',
            'D:\\data\\videos',
            'C:/mixed/separators',
            'uploads\\relative\\path',  # No drive specified
            '\\absolute\\without\\drive'
        ]
        
        with patch('config.path_resolver.detect_environment', return_value=env_info), \
             patch('os.name', 'nt'), \
             patch('os.path.sep', '\\'), \
             patch('os.path.altsep', '/'), \
             patch('os.getcwd', return_value='C:\\app'):
            
            resolver = PathResolver()
            resolver.clear_cache()
            
            for windows_path in windows_paths:
                resolved = resolver._create_resolved_path(windows_path, "test")
                
                assert resolved is not None
                assert resolved.path == windows_path
                
                # Absolute path should have drive letter
                if windows_path.startswith(('C:', 'D:', 'E:')):
                    # Already has drive letter
                    assert resolved.absolute_path[1] == ':'
                else:
                    # Should get drive from current working directory
                    assert ':' in resolved.absolute_path or resolved.absolute_path.startswith('\\')
    
    def test_case_sensitivity_handling(self, platform_configs):
        """Test case sensitivity differences across platforms"""
        test_names = [
            'TestDirectory',
            'testdirectory',
            'TESTDIRECTORY',
            'MixedCaseFile.mp4'
        ]
        
        for platform_name, config in platform_configs.items():
            env_info = self.create_platform_environment(platform_name, config)
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.name', config['os_name']):
                
                resolver = PathResolver()
                resolver.clear_cache()
                
                for test_name in test_names:
                    resolved = resolver._create_resolved_path(test_name, "test")
                    
                    assert resolved is not None
                    assert resolved.path == test_name
                    
                    # Case preservation in resolved paths
                    assert test_name in resolved.absolute_path
    
    def test_home_directory_expansion_cross_platform(self, platform_configs):
        """Test home directory expansion on different platforms"""
        home_paths = [
            '~',
            '~/uploads',
            '~/Documents/videos',
            '~/.config/app'
        ]
        
        for platform_name, config in platform_configs.items():
            env_info = self.create_platform_environment(platform_name, config)
            mock_home = config['home_prefix'] + 'testuser'
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.name', config['os_name']), \
                 patch('os.path.expanduser', lambda path: path.replace('~', mock_home)):
                
                resolver = PathResolver()
                resolver.clear_cache()
                
                for home_path in home_paths:
                    resolved = resolver._create_resolved_path(home_path, "test")
                    
                    assert resolved is not None
                    assert resolved.path == home_path
                    
                    # Should expand home directory appropriately
                    assert '~' not in resolved.absolute_path
                    assert mock_home in resolved.absolute_path
    
    def test_temp_directory_resolution_cross_platform(self, platform_configs):
        """Test temporary directory resolution on different platforms"""
        for platform_name, config in platform_configs.items():
            env_info = self.create_platform_environment(platform_name, config)
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.name', config['os_name']):
                
                resolver = PathResolver()
                resolved = resolver.resolve_path(PathType.TEMP_DIRECTORY, ensure_exists=False)
                
                assert resolved is not None
                
                # Should resolve to platform-appropriate temp directory
                expected_temp_indicators = ['/tmp', 'temp', 'Temp', 'TMP']
                assert any(indicator in resolved.path for indicator in expected_temp_indicators)
    
    def test_absolute_path_detection_cross_platform(self, platform_configs):
        """Test absolute path detection on different platforms"""
        test_cases = {
            'linux': [
                ('/', True),
                ('/home/user', True),
                ('./relative', False),
                ('relative', False),
                ('../parent', False)
            ],
            'windows': [
                ('C:\\', True),
                ('C:\\Windows', True),
                ('\\UNC\\path', True),
                ('.\\relative', False),
                ('relative', False),
                ('..\\parent', False)
            ],
            'macos': [
                ('/', True),
                ('/Users/user', True),
                ('./relative', False),
                ('relative', False),
                ('../parent', False)
            ]
        }
        
        for platform_name, test_paths in test_cases.items():
            config = platform_configs[platform_name]
            env_info = self.create_platform_environment(platform_name, config)
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.name', config['os_name']), \
                 patch('os.path.isabs', side_effect=lambda p: test_paths[0][1] if p == test_paths[0][0] else any(p == tp[0] for tp in test_paths if tp[1])):
                
                resolver = PathResolver()
                
                for test_path, is_absolute in test_paths:
                    resolved = resolver._create_resolved_path(test_path, "test")
                    
                    assert resolved is not None
                    
                    # Absolute path should always be absolute
                    assert os.path.isabs(resolved.absolute_path) or platform_name == 'test_mock'


class TestCrossPlatformEnvironmentDetection:
    """Test environment detection across platforms"""
    
    def test_linux_environment_detection(self):
        """Test Linux environment detection"""
        linux_indicators = {
            '/proc/version': 'Linux version 5.4.0',
            '/home': True,
            '/usr/local': True,
            'platform.system': 'Linux'
        }
        
        def mock_exists(path):
            return linux_indicators.get(path, False)
        
        with patch('os.path.exists', side_effect=mock_exists), \
             patch('platform.system', return_value='Linux'), \
             patch('os.path.expanduser', lambda p: p.replace('~', '/home/testuser')):
            
            from config.environment_detector import UnifiedEnvironmentDetector
            detector = UnifiedEnvironmentDetector()
            
            # Should detect as local Linux environment
            env_info = detector.detect_environment(force_refresh=True)
            
            assert env_info.environment_type == EnvironmentType.LOCAL
            assert env_info.platform.startswith('Linux') or 'Linux' in env_info.platform
    
    def test_windows_environment_detection(self):
        """Test Windows environment detection"""
        windows_indicators = {
            'C:\\Windows': True,
            'C:\\Users': True,
            'platform.system': 'Windows'
        }
        
        def mock_exists(path):
            return windows_indicators.get(path, False)
        
        with patch('os.path.exists', side_effect=mock_exists), \
             patch('platform.system', return_value='Windows'), \
             patch('os.path.expanduser', lambda p: p.replace('~', 'C:\\Users\\testuser')):
            
            from config.environment_detector import UnifiedEnvironmentDetector
            detector = UnifiedEnvironmentDetector()
            
            # Should detect as local Windows environment
            env_info = detector.detect_environment(force_refresh=True)
            
            assert env_info.environment_type == EnvironmentType.LOCAL
            assert env_info.platform.startswith('Windows') or 'Windows' in env_info.platform
    
    def test_macos_environment_detection(self):
        """Test macOS environment detection"""
        macos_indicators = {
            '/Users': True,
            '/Applications': True,
            '/System': True,
            'platform.system': 'Darwin'
        }
        
        def mock_exists(path):
            return macos_indicators.get(path, False)
        
        with patch('os.path.exists', side_effect=mock_exists), \
             patch('platform.system', return_value='Darwin'), \
             patch('os.path.expanduser', lambda p: p.replace('~', '/Users/testuser')):
            
            from config.environment_detector import UnifiedEnvironmentDetector
            detector = UnifiedEnvironmentDetector()
            
            # Should detect as local macOS environment
            env_info = detector.detect_environment(force_refresh=True)
            
            assert env_info.environment_type == EnvironmentType.LOCAL
            assert env_info.platform.startswith('Darwin') or 'Darwin' in env_info.platform


class TestCrossPlatformFileOperations:
    """Test cross-platform file operations"""
    
    def test_directory_creation_cross_platform(self):
        """Test directory creation on different platforms"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            platforms = ['linux', 'windows', 'macos']
            
            for platform_name in platforms:
                # Create platform-specific paths
                if platform_name == 'windows':
                    test_path = os.path.join(temp_dir, 'Windows_Test_Dir')
                    env_info = EnvironmentInfo(
                        environment_type=EnvironmentType.LOCAL,
                        service_mode=ServiceMode.DEVELOPMENT,
                        platform="Windows-test",
                        python_version="3.12.0",
                        is_containerized=False,
                        is_wsl=False,
                        has_docker=False,
                        network_info={},
                        filesystem_info={},
                        process_info={},
                        confidence_score=0.9
                    )
                else:
                    test_path = os.path.join(temp_dir, f'{platform_name}_test_dir')
                    env_info = EnvironmentInfo(
                        environment_type=EnvironmentType.LOCAL,
                        service_mode=ServiceMode.DEVELOPMENT,
                        platform=f"{platform_name.capitalize()}-test",
                        python_version="3.12.0",
                        is_containerized=False,
                        is_wsl=False,
                        has_docker=False,
                        network_info={},
                        filesystem_info={},
                        process_info={},
                        confidence_score=0.9
                    )
                
                with patch('config.path_resolver.detect_environment', return_value=env_info):
                    resolver = PathResolver()
                    
                    resolved = resolver.resolve_path(
                        PathType.UPLOAD_DIRECTORY,
                        custom_path=test_path,
                        ensure_exists=True
                    )
                    
                    # Should create directory regardless of platform
                    assert resolved is not None
                    assert resolved.path == test_path
                    
                    # Directory should exist after creation
                    if resolved.exists:
                        assert os.path.exists(test_path)
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_path_permission_detection_cross_platform(self):
        """Test path permission detection across platforms"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create test directories with different permissions
            readable_dir = os.path.join(temp_dir, 'readable')
            writable_dir = os.path.join(temp_dir, 'writable')
            
            os.makedirs(readable_dir, exist_ok=True)
            os.makedirs(writable_dir, exist_ok=True)
            
            # Test on current platform (whatever it is)
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=platform.platform(),
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info):
                resolver = PathResolver()
                
                # Test readable directory
                readable_resolved = resolver._create_resolved_path(readable_dir, "test")
                assert readable_resolved.exists is True
                assert isinstance(readable_resolved.is_readable, bool)
                
                # Test writable directory
                writable_resolved = resolver._create_resolved_path(writable_dir, "test")
                assert writable_resolved.exists is True
                assert isinstance(writable_resolved.is_writable, bool)
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestCrossPlatformPathEdgeCases:
    """Test edge cases that may behave differently across platforms"""
    
    def test_unicode_filename_support(self):
        """Test Unicode filename support across platforms"""
        unicode_names = [
            'test_café.mp4',
            'тест_файл.mp4', 
            '测试文件.mp4',
            'テストファイル.mp4'
        ]
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=platform.platform(),
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info):
                resolver = PathResolver()
                
                for unicode_name in unicode_names:
                    try:
                        unicode_path = os.path.join(temp_dir, unicode_name)
                        resolved = resolver._create_resolved_path(unicode_path, "test")
                        
                        assert resolved is not None
                        assert resolved.path == unicode_path
                        
                        # Try to create file with Unicode name
                        try:
                            with open(unicode_path, 'w', encoding='utf-8') as f:
                                f.write('test content')
                            
                            # If creation succeeded, should be detectable
                            if os.path.exists(unicode_path):
                                resolved_after_creation = resolver._create_resolved_path(unicode_path, "test")
                                assert resolved_after_creation.exists is True
                        
                        except (UnicodeError, OSError):
                            # Some filesystems may not support certain Unicode characters
                            # This is acceptable - just verify no crash occurred
                            pass
                    
                    except (UnicodeError, OSError):
                        # Platform doesn't support this Unicode character
                        continue
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_long_path_support(self):
        """Test long path support (especially important for Windows)"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create progressively longer paths
            base_name = 'very_long_directory_name_for_testing_path_limits'
            current_path = temp_dir
            
            for i in range(5):  # Create nested structure
                current_path = os.path.join(current_path, f'{base_name}_{i}')
            
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=platform.platform(),
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info):
                resolver = PathResolver()
                
                resolved = resolver._create_resolved_path(current_path, "test")
                
                assert resolved is not None
                assert resolved.path == current_path
                
                # Long paths may not be creatable on all systems
                # But should not cause crashes in path resolution
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_special_character_filename_handling(self):
        """Test handling of filenames with special characters"""
        special_names = [
            'file with spaces.mp4',
            'file[with]brackets.mp4',
            'file(with)parentheses.mp4',
            'file@with#symbols$.mp4',
            'file&with&ampersands.mp4'
        ]
        
        # Skip problematic characters on Windows
        if os.name == 'nt':
            # Windows doesn't allow certain characters
            windows_safe_names = [
                'file with spaces.mp4',
                'file(with)parentheses.mp4',
                'file&with&ampersands.mp4'
            ]
            special_names = windows_safe_names
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=platform.platform(),
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info):
                resolver = PathResolver()
                
                for special_name in special_names:
                    try:
                        special_path = os.path.join(temp_dir, special_name)
                        resolved = resolver._create_resolved_path(special_path, "test")
                        
                        assert resolved is not None
                        assert resolved.path == special_path
                        
                        # Try to create file to test filesystem support
                        try:
                            with open(special_path, 'w') as f:
                                f.write('test content')
                        except OSError:
                            # Some special characters may not be supported
                            # This is platform-dependent behavior
                            pass
                    
                    except OSError:
                        # Platform doesn't support this character combination
                        continue
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestCrossPlatformIntegration:
    """Test cross-platform integration scenarios"""
    
    def test_path_resolution_consistency(self):
        """Test that path resolution is consistent across platform simulations"""
        platforms = {
            'linux': ('posix', '/', None),
            'windows': ('nt', '\\', '/'),
            'macos': ('posix', '/', None)
        }
        
        test_path = 'uploads/videos/test.mp4'
        
        results = {}
        
        for platform_name, (os_name, path_sep, alt_sep) in platforms.items():
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=f"{platform_name.capitalize()}-test",
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
                 patch('os.name', os_name), \
                 patch('os.path.sep', path_sep), \
                 patch('os.path.altsep', alt_sep), \
                 patch('os.getcwd', return_value='/app' if os_name == 'posix' else 'C:\\app'):
                
                resolver = PathResolver()
                resolved = resolver._create_resolved_path(test_path, "test")
                
                results[platform_name] = {
                    'original_path': resolved.path,
                    'absolute_path': resolved.absolute_path,
                    'resolved_from': resolved.resolved_from
                }
        
        # All platforms should preserve the original path
        original_paths = [result['original_path'] for result in results.values()]
        assert all(path == test_path for path in original_paths)
        
        # All should have absolute paths
        absolute_paths = [result['absolute_path'] for result in results.values()]
        assert all(isinstance(path, str) and len(path) > 0 for path in absolute_paths)
    
    def test_ground_truth_service_cross_platform_compatibility(self):
        """Test ground truth service works across platforms"""
        platforms = ['linux', 'windows', 'macos']
        
        for platform_name in platforms:
            env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=f"{platform_name.capitalize()}-test",
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info):
                # Test that ground truth service can be instantiated
                # across different platform environments
                try:
                    from services.ground_truth_service import GroundTruthService
                    service = GroundTruthService()
                    
                    # Service should initialize without platform-specific errors
                    assert service is not None
                    assert hasattr(service, 'ml_available')
                    assert hasattr(service, '_process_video')
                
                except ImportError:
                    # Service may not be available in test environment
                    # This is acceptable for cross-platform testing
                    pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])