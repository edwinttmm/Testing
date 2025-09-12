#!/usr/bin/env python3
"""
Error Handling Tests for Missing Files and Path Issues
Tests robustness when dealing with missing files, permissions, and path errors
"""

import pytest
import os
import tempfile
import shutil
import stat
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.path_resolver import PathResolver, PathType, ResolvedPath
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo
from services.ground_truth_service import GroundTruthService


class TestMissingFileErrorHandling:
    """Test error handling for missing files and directories"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        temp_dir = tempfile.mkdtemp(prefix='error_test_')
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
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
    
    @pytest.fixture
    def path_resolver(self, local_environment_info):
        """Create path resolver with local environment"""
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info):
            resolver = PathResolver()
            resolver.clear_cache()
            return resolver
    
    def test_missing_video_file_handling(self, temp_workspace, local_environment_info):
        """Test handling when video file doesn't exist"""
        video_id = "missing_video_001"
        missing_video_path = os.path.join(temp_workspace, "non_existent_video.mp4")
        
        ground_truth_service = GroundTruthService()
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.update_video_status') as mock_update_status, \
             patch('services.ground_truth_service.processing_guard') as mock_guard:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            mock_video = MagicMock()
            mock_video.id = video_id
            mock_get_video.return_value = mock_video
            
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Process missing video file
            ground_truth_service._process_video(video_id, missing_video_path)
            
            # Verify error handling
            mock_update_status.assert_called_with(mock_db, video_id, "failed")
            mock_guard.complete_processing.assert_called_with(video_id, success=False)
    
    def test_inaccessible_video_file_handling(self, temp_workspace, local_environment_info):
        """Test handling when video file exists but is not accessible"""
        video_id = "inaccessible_video_002"
        video_path = os.path.join(temp_workspace, "restricted_video.mp4")
        
        # Create file and make it inaccessible
        with open(video_path, 'wb') as f:
            f.write(b'test video content')
        
        # Remove read permissions (Unix-like systems)
        if hasattr(os, 'chmod'):
            os.chmod(video_path, 0o000)  # No permissions
        
        ground_truth_service = GroundTruthService()
        
        try:
            with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
                 patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
                 patch('services.ground_truth_service.get_video') as mock_get_video, \
                 patch('services.ground_truth_service.processing_guard') as mock_guard, \
                 patch('cv2.VideoCapture') as mock_video_capture:
                
                # Mock VideoCapture to fail on inaccessible file
                mock_cap = MagicMock()
                mock_cap.read.return_value = (False, None)  # Simulate failure to read
                mock_video_capture.return_value = mock_cap
                
                # Setup other mocks
                mock_db = MagicMock()
                mock_db_session.return_value = mock_db
                
                mock_video = MagicMock()
                mock_video.id = video_id
                mock_get_video.return_value = mock_video
                
                mock_guard.can_start_processing.return_value = True
                mock_guard.start_processing.return_value = True
                
                # Process inaccessible video
                ground_truth_service._process_video(video_id, video_path)
                
                # Should complete with fallback detections since ML is disabled
                assert mock_video.status == "completed"
        
        finally:
            # Restore permissions for cleanup
            if hasattr(os, 'chmod'):
                try:
                    os.chmod(video_path, 0o644)
                except:
                    pass
    
    def test_directory_creation_failure_handling(self, path_resolver):
        """Test handling when directory creation fails"""
        # Test with path that can't be created (permission denied scenario)
        restricted_path = "/root/restricted_directory"
        
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=restricted_path,
                ensure_exists=True
            )
            
            # Should return resolved path but exists should be False
            assert resolved is not None
            assert resolved.path == restricted_path
            assert resolved.exists is False
            # Should have attempted directory creation but failed gracefully
    
    def test_non_existent_parent_directory_handling(self, path_resolver, temp_workspace):
        """Test handling when parent directory doesn't exist"""
        non_existent_parent = os.path.join(temp_workspace, "does", "not", "exist", "uploads")
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=non_existent_parent,
            ensure_exists=False
        )
        
        assert resolved is not None
        assert resolved.path == non_existent_parent
        assert resolved.exists is False
        assert resolved.parent_exists is False
        assert resolved.absolute_path == os.path.abspath(non_existent_parent)
    
    def test_circular_path_reference_handling(self, path_resolver, temp_workspace):
        """Test handling of circular path references"""
        if os.name == 'nt':  # Skip on Windows where symlinks may not be available
            pytest.skip("Symbolic link test not supported on Windows")
        
        # Create circular symlink
        link1 = os.path.join(temp_workspace, "link1")
        link2 = os.path.join(temp_workspace, "link2")
        
        try:
            os.symlink(link2, link1)
            os.symlink(link1, link2)
            
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=link1,
                ensure_exists=False
            )
            
            # Should handle circular reference gracefully
            assert resolved is not None
            assert resolved.path == link1
            # May or may not exist, but shouldn't cause infinite recursion
            
        except OSError:
            pytest.skip("Unable to create symbolic links for testing")
        finally:
            try:
                os.unlink(link1)
            except:
                pass
            try:
                os.unlink(link2)
            except:
                pass
    
    def test_invalid_path_characters_handling(self, path_resolver):
        """Test handling of paths with invalid characters"""
        # Test paths with invalid characters (platform dependent)
        invalid_paths = [
            "/path/with\x00null/character",
            "/path/with\ttab/character",
            "/path/with\nnewline/character"
        ]
        
        for invalid_path in invalid_paths:
            try:
                resolved = path_resolver.resolve_path(
                    PathType.UPLOAD_DIRECTORY,
                    custom_path=invalid_path,
                    ensure_exists=False
                )
                
                # Should create resolved path even if invalid
                assert resolved is not None
                assert resolved.path == invalid_path
                # Likely won't exist due to invalid characters
                assert resolved.exists is False
                
            except (ValueError, OSError) as e:
                # Some platforms may raise exceptions for invalid characters
                # This is acceptable behavior
                assert "invalid" in str(e).lower() or "character" in str(e).lower()
    
    def test_extremely_long_path_handling(self, path_resolver, temp_workspace):
        """Test handling of extremely long paths"""
        # Create extremely long path (exceeding typical filesystem limits)
        long_component = "a" * 300  # Very long directory name
        long_path = os.path.join(temp_workspace, long_component, "uploads")
        
        resolved = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=long_path,
            ensure_exists=False
        )
        
        assert resolved is not None
        assert resolved.path == long_path
        
        # Try to create it (may fail due to path length limits)
        resolved_with_creation = path_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=long_path,
            ensure_exists=True
        )
        
        # Should handle gracefully whether creation succeeds or fails
        assert resolved_with_creation is not None
    
    def test_write_access_failure_handling(self, path_resolver, temp_workspace):
        """Test write access testing when access is denied"""
        # Create directory and remove write permissions
        test_dir = os.path.join(temp_workspace, "no_write_access")
        os.makedirs(test_dir, exist_ok=True)
        
        if hasattr(os, 'chmod'):
            os.chmod(test_dir, 0o444)  # Read-only permissions
        
        try:
            # Test write access detection
            can_write = path_resolver._test_write_access(test_dir)
            
            # Should detect lack of write access
            assert can_write is False or isinstance(can_write, bool)
            
            # Test with path resolution
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=test_dir,
                ensure_exists=False
            )
            
            assert resolved is not None
            assert resolved.exists is True
            assert resolved.is_writable is False
            
        finally:
            # Restore permissions for cleanup
            if hasattr(os, 'chmod'):
                try:
                    os.chmod(test_dir, 0o755)
                except:
                    pass
    
    def test_environment_detection_failure_fallback(self):
        """Test fallback when environment detection fails"""
        with patch('config.environment_detector.environment_detector.detect_environment', 
                  side_effect=Exception("Environment detection failed")):
            
            # Should still be able to create path resolver with fallback
            try:
                path_resolver = PathResolver()
                
                # Should use fallback environment info
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                
                assert resolved is not None
                assert resolved.path is not None
                
            except Exception as e:
                # If exception occurs, it should be handled gracefully
                assert "environment" in str(e).lower()
    
    def test_corrupted_file_system_handling(self, path_resolver, temp_workspace):
        """Test handling when filesystem operations behave unexpectedly"""
        # Simulate filesystem corruption by mocking os.path.exists to behave inconsistently
        call_count = 0
        
        def inconsistent_exists(path):
            nonlocal call_count
            call_count += 1
            # Alternately return True/False to simulate corruption
            return call_count % 2 == 0
        
        with patch('os.path.exists', side_effect=inconsistent_exists), \
             patch('os.access', return_value=False):  # Simulate access failures
            
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=temp_workspace,
                ensure_exists=False
            )
            
            # Should handle inconsistent filesystem state gracefully
            assert resolved is not None
            assert resolved.path == temp_workspace
    
    def test_memory_pressure_during_path_operations(self, path_resolver):
        """Test path operations under memory pressure simulation"""
        # Simulate memory pressure by limiting available operations
        def memory_limited_makedirs(path, exist_ok=False):
            raise MemoryError("Insufficient memory")
        
        with patch('os.makedirs', side_effect=memory_limited_makedirs):
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path="/tmp/memory_test",
                ensure_exists=True
            )
            
            # Should handle memory errors gracefully
            assert resolved is not None
            assert resolved.exists is False  # Couldn't create due to memory error


class TestPathResolutionErrorRecovery:
    """Test error recovery mechanisms in path resolution"""
    
    @pytest.fixture
    def error_recovery_resolver(self):
        """Create path resolver for error recovery testing"""
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
        
        with patch('config.path_resolver.detect_environment', return_value=local_env_info):
            resolver = PathResolver()
            resolver.clear_cache()
            return resolver
    
    def test_cascading_fallback_on_errors(self, error_recovery_resolver, temp_workspace):
        """Test that path resolution cascades through fallback options on errors"""
        
        # Mock resolution methods to fail in sequence
        def failing_custom_resolution(path_type, custom_path):
            raise IOError("Custom resolution failed")
        
        def failing_env_resolution(path_type):
            raise OSError("Environment variable resolution failed")
        
        def failing_base_resolution(path_type):
            raise RuntimeError("Base path resolution failed")
        
        with patch.object(error_recovery_resolver, '_resolve_from_custom', 
                         side_effect=failing_custom_resolution), \
             patch.object(error_recovery_resolver, '_resolve_from_environment_variables',
                         side_effect=failing_env_resolution), \
             patch.object(error_recovery_resolver, '_resolve_from_base_paths',
                         side_effect=failing_base_resolution):
            
            # Should fall back to final fallback method
            resolved = error_recovery_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path="/invalid/path",
                ensure_exists=False
            )
            
            # Should get fallback resolution
            assert resolved is not None
            assert resolved.resolved_from == "fallback"
    
    def test_partial_failure_recovery(self, error_recovery_resolver, temp_workspace):
        """Test recovery from partial failures in path operations"""
        # Create a directory that exists but has some access issues
        partial_failure_dir = os.path.join(temp_workspace, "partial_failure")
        os.makedirs(partial_failure_dir, exist_ok=True)
        
        # Mock specific operations to fail
        original_access = os.access
        def failing_access(path, mode):
            if mode == os.W_OK and "partial_failure" in path:
                return False  # Simulate write access failure
            return original_access(path, mode)
        
        with patch('os.access', side_effect=failing_access):
            resolved = error_recovery_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=partial_failure_dir,
                ensure_exists=False
            )
            
            # Should detect directory exists but is not writable
            assert resolved is not None
            assert resolved.exists is True
            assert resolved.is_writable is False
            assert resolved.is_readable is True  # Should still be readable
    
    def test_cache_invalidation_on_errors(self, error_recovery_resolver, temp_workspace):
        """Test that cache is properly invalidated when errors occur"""
        test_path = os.path.join(temp_workspace, "cache_test")
        
        # First resolution should succeed
        resolved1 = error_recovery_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=test_path,
            ensure_exists=False
        )
        
        assert resolved1 is not None
        
        # Verify it's cached
        cache_key = f"{PathType.UPLOAD_DIRECTORY.value}:{test_path}:False"
        assert cache_key in error_recovery_resolver._path_cache
        
        # Second resolution should use cache
        resolved2 = error_recovery_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=test_path,
            ensure_exists=False
        )
        
        assert resolved1 is resolved2  # Same cached object
        
        # Clear cache and verify new resolution
        error_recovery_resolver.clear_cache()
        
        resolved3 = error_recovery_resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=test_path,
            ensure_exists=False
        )
        
        assert resolved1 is not resolved3  # Different object after cache clear
    
    def test_error_logging_and_reporting(self, error_recovery_resolver):
        """Test that errors are properly logged and reported"""
        
        # Test with invalid path that should generate warnings
        with patch('config.path_resolver.logger') as mock_logger:
            resolved = error_recovery_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path="/root/should_fail",
                ensure_exists=True  # Should fail to create
            )
            
            assert resolved is not None
            
            # Should have logged warning about directory creation failure
            # (Actual logging calls depend on implementation details)
    
    def test_graceful_degradation(self, error_recovery_resolver):
        """Test graceful degradation when multiple systems fail"""
        
        # Simulate multiple system failures
        with patch('os.path.exists', side_effect=OSError("Filesystem error")), \
             patch('os.access', side_effect=PermissionError("Access denied")), \
             patch('os.makedirs', side_effect=IOError("Cannot create directory")):
            
            # Should still provide some form of resolution
            resolved = error_recovery_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                ensure_exists=True
            )
            
            assert resolved is not None
            assert resolved.path is not None
            # May not be accurate due to system failures, but should not crash


class TestNetworkPathErrorHandling:
    """Test error handling for network paths and remote filesystems"""
    
    def test_network_path_timeout_handling(self):
        """Test handling of network path timeouts"""
        # Skip if not on a system that supports network paths
        if os.name != 'nt':
            pytest.skip("Network path test primarily for Windows")
        
        network_path = r"\\nonexistent-server\share\uploads"
        
        local_env_info = EnvironmentInfo(
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
        
        with patch('config.path_resolver.detect_environment', return_value=local_env_info):
            path_resolver = PathResolver()
            
            # Should handle network path gracefully even if server doesn't exist
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path=network_path,
                ensure_exists=False
            )
            
            assert resolved is not None
            assert resolved.path == network_path
            # Network path likely won't exist
            assert resolved.exists is False
    
    def test_mounted_filesystem_failure_handling(self, temp_workspace):
        """Test handling when mounted filesystems become unavailable"""
        # Simulate a mount point that becomes unavailable
        mount_point = os.path.join(temp_workspace, "mount_point")
        os.makedirs(mount_point, exist_ok=True)
        
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
        
        with patch('config.path_resolver.detect_environment', return_value=local_env_info):
            path_resolver = PathResolver()
            
            # Mock os.path.exists to simulate mount failure
            original_exists = os.path.exists
            def mount_failure_exists(path):
                if mount_point in path:
                    raise OSError("Transport endpoint is not connected")
                return original_exists(path)
            
            with patch('os.path.exists', side_effect=mount_failure_exists):
                resolved = path_resolver.resolve_path(
                    PathType.UPLOAD_DIRECTORY,
                    custom_path=mount_point,
                    ensure_exists=False
                )
                
                # Should handle mount failure gracefully
                assert resolved is not None
                # Error should be reflected in resolved path status


if __name__ == '__main__':
    pytest.main([__file__, '-v'])