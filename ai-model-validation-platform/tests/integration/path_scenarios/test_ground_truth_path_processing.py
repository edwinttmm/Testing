#!/usr/bin/env python3
"""
Integration tests for Ground Truth Processing with Path Scenarios
Tests path resolution robustness across different deployment contexts
"""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../backend/src'))

from services.ground_truth_service import GroundTruthService
from config.path_resolver import PathResolver, PathType
from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


class TestGroundTruthPathProcessing:
    """Integration tests for ground truth processing with various path scenarios"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        temp_dir = tempfile.mkdtemp(prefix='gt_test_')
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_video_file(self, temp_workspace):
        """Create mock video file"""
        video_path = os.path.join(temp_workspace, 'test_video.mp4')
        # Create dummy video file
        with open(video_path, 'wb') as f:
            f.write(b'mock video content')
        return video_path
    
    @pytest.fixture
    def local_environment_info(self):
        """Mock local development environment"""
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
    def docker_environment_info(self):
        """Mock Docker container environment"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'container-abc123'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
    
    @pytest.fixture
    def ground_truth_service(self):
        """Create ground truth service with ML disabled for testing"""
        service = GroundTruthService()
        service.ml_available = False  # Disable ML for faster testing
        return service
    
    def test_local_development_absolute_paths(self, temp_workspace, mock_video_file, 
                                           local_environment_info, ground_truth_service):
        """Test ground truth processing with absolute paths in local development"""
        video_id = "test_video_123"
        
        # Setup local environment
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=temp_workspace), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.create_ground_truth_object') as mock_create_gt, \
             patch('services.ground_truth_service.processing_guard') as mock_guard:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            mock_video = MagicMock()
            mock_video.id = video_id
            mock_video.status = "uploaded"
            mock_get_video.return_value = mock_video
            
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Process video with absolute path
            ground_truth_service._process_video(video_id, mock_video_file)
            
            # Verify video status was updated
            assert mock_video.status == "completed"
            assert mock_video.ground_truth_generated is True
            
            # Verify fallback detections were created
            mock_create_gt.assert_called()
            assert mock_create_gt.call_count >= 3  # Should create fallback detections
    
    def test_docker_container_relative_paths(self, temp_workspace, docker_environment_info, 
                                           ground_truth_service):
        """Test ground truth processing with relative paths in Docker container"""
        video_id = "docker_video_456"
        
        # Create video file in container-like structure
        app_dir = os.path.join(temp_workspace, 'app')
        uploads_dir = os.path.join(app_dir, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        video_file = os.path.join(uploads_dir, 'video.mp4')
        with open(video_file, 'wb') as f:
            f.write(b'docker mock video')
        
        # Test with relative path that needs resolution
        relative_video_path = './uploads/video.mp4'
        
        with patch('config.path_resolver.detect_environment', return_value=docker_environment_info), \
             patch('os.getcwd', return_value=app_dir), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.processing_guard') as mock_guard:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            mock_video = MagicMock()
            mock_video.id = video_id
            mock_get_video.return_value = mock_video
            
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Process with relative path
            ground_truth_service._process_video(video_id, relative_video_path)
            
            # Verify processing completed successfully
            assert mock_video.status == "completed"
    
    def test_path_resolution_with_environment_variables(self, temp_workspace, 
                                                      local_environment_info, ground_truth_service):
        """Test path resolution using environment variables"""
        video_id = "env_var_video_789"
        
        # Setup custom upload directory via environment variable
        custom_upload_dir = os.path.join(temp_workspace, 'custom_uploads')
        os.makedirs(custom_upload_dir, exist_ok=True)
        
        video_file = os.path.join(custom_upload_dir, 'env_video.mp4')
        with open(video_file, 'wb') as f:
            f.write(b'env var video')
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch.dict(os.environ, {'AIVALIDATION_UPLOAD_DIRECTORY': custom_upload_dir}), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.processing_guard') as mock_guard:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            mock_video = MagicMock()
            mock_video.id = video_id
            mock_get_video.return_value = mock_video
            
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Test that PathResolver picks up the environment variable
            path_resolver = PathResolver()
            resolved_upload_dir = path_resolver.resolve_upload_directory()
            
            assert resolved_upload_dir == custom_upload_dir
            
            # Process video
            ground_truth_service._process_video(video_id, video_file)
            assert mock_video.status == "completed"
    
    def test_cross_environment_path_compatibility(self, temp_workspace, ground_truth_service):
        """Test path compatibility across different environments"""
        video_id = "cross_env_video_101"
        
        # Create video file
        video_file = os.path.join(temp_workspace, 'cross_env_video.mp4')
        with open(video_file, 'wb') as f:
            f.write(b'cross env video')
        
        # Test paths in different environments
        environments = [
            EnvironmentType.LOCAL,
            EnvironmentType.DOCKER,
            EnvironmentType.WSL
        ]
        
        for env_type in environments:
            env_info = EnvironmentInfo(
                environment_type=env_type,
                service_mode=ServiceMode.DEVELOPMENT,
                platform=f"Linux-{env_type.value}",
                python_version="3.12.0",
                is_containerized=env_type in [EnvironmentType.DOCKER],
                is_wsl=env_type == EnvironmentType.WSL,
                has_docker=env_type == EnvironmentType.DOCKER,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.8
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.getcwd', return_value=temp_workspace), \
                 patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
                 patch('services.ground_truth_service.get_video') as mock_get_video, \
                 patch('services.ground_truth_service.processing_guard') as mock_guard:
                
                # Setup mocks
                mock_db = MagicMock()
                mock_db_session.return_value = mock_db
                
                mock_video = MagicMock()
                mock_video.id = video_id
                mock_get_video.return_value = mock_video
                
                mock_guard.can_start_processing.return_value = True
                mock_guard.start_processing.return_value = True
                
                # Test path resolution works in this environment
                path_resolver = PathResolver()
                upload_dir = path_resolver.resolve_upload_directory()
                
                assert upload_dir is not None
                assert isinstance(upload_dir, str)
                
                # Process video should work regardless of environment
                ground_truth_service._process_video(video_id, video_file)
                assert mock_video.status == "completed"
    
    def test_missing_file_error_handling(self, temp_workspace, local_environment_info, 
                                       ground_truth_service):
        """Test error handling when video files are missing"""
        video_id = "missing_video_404"
        missing_video_path = os.path.join(temp_workspace, 'does_not_exist.mp4')
        
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
            
            # Process missing video
            ground_truth_service._process_video(video_id, missing_video_path)
            
            # Verify error handling
            mock_update_status.assert_called_with(mock_db, video_id, "failed")
            mock_guard.complete_processing.assert_called_with(video_id, success=False)
    
    def test_screenshot_path_resolution(self, temp_workspace, local_environment_info, 
                                      ground_truth_service):
        """Test screenshot path resolution and creation"""
        video_id = "screenshot_video_202"
        
        # Create video file
        video_file = os.path.join(temp_workspace, 'screenshot_video.mp4')
        with open(video_file, 'wb') as f:
            f.write(b'screenshot video')
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=temp_workspace), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.processing_guard') as mock_guard, \
             patch('os.makedirs') as mock_makedirs:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            mock_video = MagicMock()
            mock_video.id = video_id
            mock_get_video.return_value = mock_video
            
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Test screenshot directory creation
            # The service should create screenshots directory if it doesn't exist
            ground_truth_service._process_video(video_id, video_file)
            
            # Verify screenshot directory creation was attempted
            # (This would happen in the _generate_screenshot method if ML was enabled)
            # Since ML is disabled, we're testing the fallback path
            assert mock_video.status == "completed"
    
    def test_path_normalization_across_platforms(self, temp_workspace, ground_truth_service):
        """Test path normalization works across different platforms"""
        video_id = "normalized_video_303"
        
        # Test different path formats
        path_formats = [
            os.path.join(temp_workspace, 'video.mp4'),  # Normal path
            temp_workspace + '/video.mp4',  # Forward slash
            temp_workspace + '\\video.mp4' if os.name == 'nt' else temp_workspace + '/video.mp4'  # Backslash on Windows
        ]
        
        for path_format in path_formats:
            # Create video file
            normalized_path = os.path.normpath(path_format)
            os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
            
            with open(normalized_path, 'wb') as f:
                f.write(b'normalized video')
            
            with patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
                 patch('services.ground_truth_service.get_video') as mock_get_video, \
                 patch('services.ground_truth_service.processing_guard') as mock_guard:
                
                # Setup mocks
                mock_db = MagicMock()
                mock_db_session.return_value = mock_db
                
                mock_video = MagicMock()
                mock_video.id = video_id
                mock_get_video.return_value = mock_video
                
                mock_guard.can_start_processing.return_value = True
                mock_guard.start_processing.return_value = True
                
                # Process video with different path format
                ground_truth_service._process_video(video_id, path_format)
                
                # Should handle path normalization correctly
                assert mock_video.status == "completed"
            
            # Clean up
            try:
                os.remove(normalized_path)
            except:
                pass
    
    def test_concurrent_processing_path_safety(self, temp_workspace, local_environment_info, 
                                             ground_truth_service):
        """Test path safety during concurrent processing scenarios"""
        # This test simulates concurrent access to ensure paths are handled safely
        video_ids = ["concurrent_video_1", "concurrent_video_2", "concurrent_video_3"]
        
        # Create multiple video files
        video_files = []
        for i, video_id in enumerate(video_ids):
            video_file = os.path.join(temp_workspace, f'concurrent_video_{i}.mp4')
            with open(video_file, 'wb') as f:
                f.write(f'concurrent video {i}'.encode())
            video_files.append(video_file)
        
        with patch('config.path_resolver.detect_environment', return_value=local_environment_info), \
             patch('os.getcwd', return_value=temp_workspace), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.processing_guard') as mock_guard:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            def mock_get_video_side_effect(db, video_id):
                mock_video = MagicMock()
                mock_video.id = video_id
                return mock_video
            
            mock_get_video.side_effect = mock_get_video_side_effect
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Process multiple videos
            for video_id, video_file in zip(video_ids, video_files):
                ground_truth_service._process_video(video_id, video_file)
            
            # Verify all processing completed
            assert mock_guard.start_processing.call_count == len(video_ids)
            assert mock_guard.complete_processing.call_count == len(video_ids)


class TestPathMigrationScenarios:
    """Test scenarios for migrating from relative to absolute paths"""
    
    @pytest.fixture
    def migration_workspace(self):
        """Create workspace for migration testing"""
        temp_dir = tempfile.mkdtemp(prefix='migration_test_')
        
        # Create legacy relative path structure
        legacy_uploads = os.path.join(temp_dir, 'legacy_uploads')
        os.makedirs(legacy_uploads, exist_ok=True)
        
        # Create new absolute path structure
        new_uploads = os.path.join(temp_dir, 'app', 'uploads')
        os.makedirs(new_uploads, exist_ok=True)
        
        yield {
            'temp_dir': temp_dir,
            'legacy_uploads': legacy_uploads,
            'new_uploads': new_uploads
        }
        
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_legacy_relative_path_migration(self, migration_workspace, ground_truth_service):
        """Test migration from legacy relative paths to new absolute paths"""
        video_id = "migration_video_501"
        
        # Create video in legacy location
        legacy_video = os.path.join(migration_workspace['legacy_uploads'], 'legacy_video.mp4')
        with open(legacy_video, 'wb') as f:
            f.write(b'legacy video content')
        
        # Simulate old relative path reference
        relative_path = './legacy_uploads/legacy_video.mp4'
        
        with patch('os.getcwd', return_value=migration_workspace['temp_dir']), \
             patch('services.ground_truth_service.SessionLocal') as mock_db_session, \
             patch('services.ground_truth_service.get_video') as mock_get_video, \
             patch('services.ground_truth_service.processing_guard') as mock_guard:
            
            # Setup mocks
            mock_db = MagicMock()
            mock_db_session.return_value = mock_db
            
            mock_video = MagicMock()
            mock_video.id = video_id
            mock_get_video.return_value = mock_video
            
            mock_guard.can_start_processing.return_value = True
            mock_guard.start_processing.return_value = True
            
            # Process video with relative path
            ground_truth_service._process_video(video_id, relative_path)
            
            # Should resolve and process successfully
            assert mock_video.status == "completed"
    
    def test_path_resolution_fallback_chain(self, migration_workspace, ground_truth_service):
        """Test the complete fallback chain for path resolution"""
        video_id = "fallback_video_502"
        
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
             patch('os.getcwd', return_value=migration_workspace['temp_dir']):
            
            path_resolver = PathResolver()
            
            # Test fallback chain: custom -> env vars -> base paths -> fallback
            
            # 1. Test with no custom path or env vars (should use base paths)
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            assert resolved.resolved_from in ['base_path_local', 'fallback']
            
            # 2. Test with environment variable (should use env var)
            with patch.dict(os.environ, {'AIVALIDATION_UPLOAD_DIRECTORY': migration_workspace['new_uploads']}):
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                assert resolved.resolved_from.startswith('env_var_')
                assert resolved.path == migration_workspace['new_uploads']
            
            # 3. Test with custom path (should use custom)
            custom_path = migration_workspace['legacy_uploads']
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY, 
                custom_path=custom_path,
                ensure_exists=False
            )
            assert resolved.resolved_from == 'custom_override'
            assert resolved.path == custom_path


if __name__ == '__main__':
    pytest.main([__file__, '-v'])