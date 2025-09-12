#!/usr/bin/env python3
"""
Container Deployment Simulation Tests
Tests path resolution robustness in containerized environments
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
import json

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.path_resolver import PathResolver, PathType
from config.environment_detector import UnifiedEnvironmentDetector, EnvironmentType, ServiceMode, EnvironmentInfo
from services.ground_truth_service import GroundTruthService


class TestDockerContainerSimulation:
    """Test Docker container deployment scenarios"""
    
    @pytest.fixture
    def docker_environment_info(self):
        """Docker container environment info"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={
                'hostname': 'ai-validation-container-abc123',
                'local_ip': '172.17.0.2'
            },
            filesystem_info={
                'working_directory': '/app',
                'filesystem_type': 'overlay'
            },
            process_info={
                'pid': 1,
                'ppid': 0,
                'init_process': 'python'
            },
            confidence_score=0.95
        )
    
    @pytest.fixture
    def container_filesystem_structure(self):
        """Simulate Docker container filesystem structure"""
        temp_dir = tempfile.mkdtemp(prefix='docker_sim_')
        
        # Create Docker-like directory structure
        structure = {
            'app': os.path.join(temp_dir, 'app'),
            'app_uploads': os.path.join(temp_dir, 'app', 'uploads'),
            'app_logs': os.path.join(temp_dir, 'app', 'logs'),
            'app_data': os.path.join(temp_dir, 'app', 'data'),
            'app_config': os.path.join(temp_dir, 'app', 'config'),
            'tmp': os.path.join(temp_dir, 'tmp'),
            'var_log': os.path.join(temp_dir, 'var', 'log'),
            'etc_config': os.path.join(temp_dir, 'etc', 'config')
        }
        
        # Create all directories
        for path in structure.values():
            os.makedirs(path, exist_ok=True)
        
        # Create some test files
        test_files = [
            os.path.join(structure['app_uploads'], 'container_video.mp4'),
            os.path.join(structure['app_logs'], 'application.log'),
            os.path.join(structure['app_config'], 'settings.json')
        ]
        
        for test_file in test_files:
            with open(test_file, 'w') as f:
                f.write(f'test content for {os.path.basename(test_file)}')
        
        yield structure
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_docker_container_path_resolution(self, docker_environment_info, container_filesystem_structure):
        """Test path resolution in Docker container environment"""
        app_dir = container_filesystem_structure['app']
        
        with patch('config.path_resolver.detect_environment', return_value=docker_environment_info), \
             patch('os.getcwd', return_value=app_dir):
            
            path_resolver = PathResolver()
            
            # Test all path types resolve to Docker paths
            for path_type in PathType:
                resolved = path_resolver.resolve_path(path_type, ensure_exists=False)
                
                assert resolved is not None
                assert resolved.resolved_from == 'base_path_docker'
                
                # Should use Docker-style absolute paths
                assert '/app' in resolved.path or resolved.path.startswith('/tmp')
                
                # Specific checks for important path types
                if path_type == PathType.UPLOAD_DIRECTORY:
                    assert '/app' in resolved.path
                    assert 'upload' in resolved.path.lower()
                elif path_type == PathType.TEMP_DIRECTORY:
                    assert resolved.path.startswith('/tmp')
    
    def test_docker_environment_detection_simulation(self):
        """Test Docker environment detection with simulated indicators"""
        
        # Mock Docker environment indicators
        docker_indicators = {
            '/.dockerenv': True,
            '/proc/1/cgroup': 'docker\ncontainer_id',
            '/proc/mounts': 'overlay /merged overlay',
            'HOSTNAME': 'container-abc123',
            'container_hostname_length': 12
        }
        
        def mock_exists(path):
            return docker_indicators.get(path, False)
        
        def mock_open_file(filename, mode='r'):
            content = docker_indicators.get(filename, '')
            return mock_open(read_data=content)()
        
        with patch('os.path.exists', side_effect=mock_exists), \
             patch('builtins.open', side_effect=mock_open_file), \
             patch.dict(os.environ, {'HOSTNAME': docker_indicators['HOSTNAME']}):
            
            detector = UnifiedEnvironmentDetector()
            env_info = detector.detect_environment()
            
            assert env_info.environment_type == EnvironmentType.DOCKER
            assert env_info.is_containerized is True
            assert env_info.confidence_score > 0.7
    
    def test_docker_volume_mount_handling(self, docker_environment_info, container_filesystem_structure):
        """Test handling of Docker volume mounts"""
        app_dir = container_filesystem_structure['app']
        
        # Simulate mounted volumes
        mounted_uploads = '/mnt/external-storage/uploads'
        mounted_logs = '/mnt/external-storage/logs'
        
        with patch('config.path_resolver.detect_environment', return_value=docker_environment_info), \
             patch('os.getcwd', return_value=app_dir), \
             patch.dict(os.environ, {
                 'AIVALIDATION_UPLOAD_DIRECTORY': mounted_uploads,
                 'AIVALIDATION_LOG_DIRECTORY': mounted_logs
             }):
            
            path_resolver = PathResolver()
            
            # Should use mounted volume paths from environment variables
            upload_resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            log_resolved = path_resolver.resolve_path(PathType.LOG_DIRECTORY, ensure_exists=False)
            
            assert upload_resolved.path == mounted_uploads
            assert upload_resolved.resolved_from.startswith('env_var_')
            
            assert log_resolved.path == mounted_logs
            assert log_resolved.resolved_from.startswith('env_var_')
    
    def test_docker_multi_stage_build_paths(self, container_filesystem_structure):
        """Test path handling in multi-stage Docker builds"""
        
        # Simulate different stages of Docker build
        build_stages = [
            {
                'stage': 'builder',
                'working_dir': '/build',
                'environment_type': EnvironmentType.DOCKER,
                'service_mode': ServiceMode.DEVELOPMENT
            },
            {
                'stage': 'runtime',
                'working_dir': '/app',
                'environment_type': EnvironmentType.DOCKER,
                'service_mode': ServiceMode.PRODUCTION
            }
        ]
        
        for stage_config in build_stages:
            env_info = EnvironmentInfo(
                environment_type=stage_config['environment_type'],
                service_mode=stage_config['service_mode'],
                platform="Linux-docker",
                python_version="3.12.0",
                is_containerized=True,
                is_wsl=False,
                has_docker=True,
                network_info={'hostname': f"{stage_config['stage']}-container"},
                filesystem_info={'working_directory': stage_config['working_dir']},
                process_info={'pid': 1},
                confidence_score=0.9
            )
            
            with patch('config.path_resolver.detect_environment', return_value=env_info), \
                 patch('os.getcwd', return_value=stage_config['working_dir']):
                
                path_resolver = PathResolver()
                resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
                
                # Should resolve appropriately for each stage
                assert resolved is not None
                assert resolved.resolved_from == 'base_path_docker'
                assert '/app' in resolved.path  # Docker base paths always use /app
    
    def test_docker_compose_service_integration(self, docker_environment_info, container_filesystem_structure):
        """Test integration with Docker Compose service setup"""
        app_dir = container_filesystem_structure['app']
        
        # Simulate Docker Compose environment variables
        compose_env = {
            'COMPOSE_PROJECT_NAME': 'ai-validation-platform',
            'COMPOSE_SERVICE': 'backend',
            'AIVALIDATION_UPLOAD_DIRECTORY': '/app/uploads',
            'AIVALIDATION_LOG_DIRECTORY': '/app/logs',
            'AIVALIDATION_DATA_DIRECTORY': '/app/data'
        }
        
        with patch('config.path_resolver.detect_environment', return_value=docker_environment_info), \
             patch('os.getcwd', return_value=app_dir), \
             patch.dict(os.environ, compose_env):
            
            path_resolver = PathResolver()
            
            # Test all configured paths resolve correctly
            upload_dir = path_resolver.resolve_upload_directory()
            log_dir = path_resolver.resolve_log_directory() 
            data_dir = path_resolver.resolve_data_directory()
            
            assert upload_dir == '/app/uploads'
            assert log_dir == '/app/logs'
            assert data_dir == '/app/data'
    
    def test_docker_health_check_paths(self, docker_environment_info, container_filesystem_structure):
        """Test path resolution for Docker health checks"""
        app_dir = container_filesystem_structure['app']
        
        with patch('config.path_resolver.detect_environment', return_value=docker_environment_info), \
             patch('os.getcwd', return_value=app_dir):
            
            path_resolver = PathResolver()
            
            # Health check should be able to validate paths
            validation = path_resolver.validate_paths()
            
            assert validation['environment_type'] == 'docker'
            assert validation['service_mode'] == 'production'
            
            # All critical paths should be validated
            critical_paths = [
                PathType.UPLOAD_DIRECTORY.value,
                PathType.LOG_DIRECTORY.value,
                PathType.TEMP_DIRECTORY.value
            ]
            
            for path_type in critical_paths:
                assert path_type in validation['paths']
                path_info = validation['paths'][path_type]
                assert 'path' in path_info
                assert 'resolved_from' in path_info


class TestKubernetesContainerSimulation:
    """Test Kubernetes container deployment scenarios"""
    
    @pytest.fixture
    def kubernetes_environment_info(self):
        """Kubernetes pod environment info"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.KUBERNETES,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-kubernetes",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={
                'hostname': 'ai-validation-pod-7d8c9b-xyz',
                'local_ip': '10.244.0.15'
            },
            filesystem_info={
                'working_directory': '/app',
                'filesystem_type': 'overlay'
            },
            process_info={
                'pid': 1,
                'ppid': 0,
                'init_process': 'python'
            },
            confidence_score=0.92
        )
    
    def test_kubernetes_pod_path_resolution(self, kubernetes_environment_info):
        """Test path resolution in Kubernetes pod"""
        
        with patch('config.path_resolver.detect_environment', return_value=kubernetes_environment_info), \
             patch('os.getcwd', return_value='/app'):
            
            path_resolver = PathResolver()
            
            # Should use Docker-style paths in Kubernetes (since K8s runs containers)
            resolved = path_resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert resolved is not None
            assert resolved.resolved_from == 'base_path_docker'  # K8s uses Docker base paths
            assert '/app' in resolved.path
    
    def test_kubernetes_persistent_volume_handling(self, kubernetes_environment_info):
        """Test handling of Kubernetes persistent volumes"""
        
        # Simulate Kubernetes persistent volume mounts
        k8s_env = {
            'KUBERNETES_SERVICE_HOST': '10.96.0.1',
            'KUBERNETES_SERVICE_PORT': '443',
            'K8S_NAMESPACE': 'ai-validation',
            'AIVALIDATION_UPLOAD_DIRECTORY': '/mnt/shared-storage/uploads',
            'AIVALIDATION_LOG_DIRECTORY': '/mnt/shared-storage/logs'
        }
        
        with patch('config.path_resolver.detect_environment', return_value=kubernetes_environment_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, k8s_env):
            
            path_resolver = PathResolver()
            
            # Should use persistent volume paths
            upload_dir = path_resolver.resolve_upload_directory()
            log_dir = path_resolver.resolve_log_directory()
            
            assert upload_dir == '/mnt/shared-storage/uploads'
            assert log_dir == '/mnt/shared-storage/logs'
    
    def test_kubernetes_environment_detection_simulation(self):
        """Test Kubernetes environment detection"""
        
        k8s_indicators = {
            '/var/run/secrets/kubernetes.io': True,
            'KUBERNETES_SERVICE_HOST': '10.96.0.1',
            'KUBERNETES_SERVICE_PORT': '443',
            'K8S_NAMESPACE': 'default'
        }
        
        with patch('os.path.exists', side_effect=lambda path: k8s_indicators.get(path, False)), \
             patch.dict(os.environ, k8s_indicators):
            
            detector = UnifiedEnvironmentDetector()
            env_info = detector.detect_environment()
            
            assert env_info.environment_type == EnvironmentType.KUBERNETES
            assert env_info.is_containerized is True
            assert env_info.confidence_score > 0.8


class TestCloudContainerSimulation:
    """Test cloud container service scenarios"""
    
    def test_aws_ecs_container_paths(self):
        """Test AWS ECS container path resolution"""
        ecs_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.CLOUD,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-ecs",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'ecs-task-abc123'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.88
        )
        
        ecs_env = {
            'AWS_REGION': 'us-east-1',
            'AWS_EXECUTION_ENV': 'AWS_ECS_FARGATE',
            'ECS_CONTAINER_METADATA_URI': 'http://169.254.170.2/v3',
            'AIVALIDATION_UPLOAD_DIRECTORY': '/app/uploads'
        }
        
        with patch('config.path_resolver.detect_environment', return_value=ecs_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, ecs_env):
            
            path_resolver = PathResolver()
            upload_dir = path_resolver.resolve_upload_directory()
            
            # Should use environment-specified path for cloud deployment
            assert upload_dir == '/app/uploads'
    
    def test_gcp_cloud_run_container_paths(self):
        """Test Google Cloud Run container path resolution"""
        gcp_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.CLOUD,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-cloudrun",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'cloudrun-instance-xyz'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.85
        )
        
        gcp_env = {
            'GOOGLE_CLOUD_PROJECT': 'ai-validation-project',
            'CLOUD_RUN_SERVICE': 'ai-validation-backend',
            'PORT': '8080',
            'AIVALIDATION_UPLOAD_DIRECTORY': '/tmp/uploads',  # Cloud Run uses /tmp
            'AIVALIDATION_LOG_DIRECTORY': '/tmp/logs'
        }
        
        with patch('config.path_resolver.detect_environment', return_value=gcp_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, gcp_env):
            
            path_resolver = PathResolver()
            
            upload_dir = path_resolver.resolve_upload_directory()
            log_dir = path_resolver.resolve_log_directory()
            
            # Cloud Run typically uses /tmp for writable storage
            assert upload_dir == '/tmp/uploads'
            assert log_dir == '/tmp/logs'


class TestContainerIntegrationScenarios:
    """Test integration scenarios across container platforms"""
    
    @pytest.fixture
    def ground_truth_service(self):
        """Ground truth service for container testing"""
        service = GroundTruthService()
        service.ml_available = False  # Disable ML for faster testing
        return service
    
    def test_container_video_processing_integration(self, ground_truth_service):
        """Test video processing in container environment"""
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'processing-container'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        video_id = "container_video_001"
        container_video_path = "/app/uploads/container_video.mp4"
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch('os.path.exists', return_value=True), \
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
            
            # Process video in container environment
            ground_truth_service._process_video(video_id, container_video_path)
            
            # Should complete successfully in container
            assert mock_video.status == "completed"
            assert mock_video.ground_truth_generated is True
    
    def test_container_to_host_path_mapping(self):
        """Test path mapping between container and host filesystems"""
        
        # Simulate Docker bind mounts
        path_mappings = [
            ('/host/data/uploads', '/app/uploads'),
            ('/host/logs', '/app/logs'),
            ('/host/config', '/app/config')
        ]
        
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'mapped-container'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'):
            
            path_resolver = PathResolver()
            
            # Test that container paths resolve correctly
            upload_dir = path_resolver.resolve_upload_directory()
            log_dir = path_resolver.resolve_log_directory()
            config_dir = path_resolver.resolve_config_directory()
            
            # Should use container paths (not host paths)
            assert upload_dir.startswith('/app/')
            assert log_dir.startswith('/app/')
            assert config_dir.startswith('/app/')
    
    def test_container_network_storage_integration(self):
        """Test integration with network storage in containers"""
        k8s_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.KUBERNETES,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-kubernetes",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'storage-pod-abc'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.90
        )
        
        # Simulate network-attached storage
        network_storage_env = {
            'AIVALIDATION_UPLOAD_DIRECTORY': '/mnt/nfs/uploads',
            'AIVALIDATION_LOG_DIRECTORY': '/mnt/nfs/logs',
            'AIVALIDATION_DATA_DIRECTORY': '/mnt/s3fs/data'
        }
        
        with patch('config.path_resolver.detect_environment', return_value=k8s_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, network_storage_env):
            
            path_resolver = PathResolver()
            
            upload_dir = path_resolver.resolve_upload_directory()
            log_dir = path_resolver.resolve_log_directory()
            data_dir = path_resolver.resolve_data_directory()
            
            # Should use network storage paths
            assert upload_dir == '/mnt/nfs/uploads'
            assert log_dir == '/mnt/nfs/logs'
            assert data_dir == '/mnt/s3fs/data'
    
    def test_container_restart_path_persistence(self):
        """Test path resolution consistency across container restarts"""
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'persistent-container'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        persistent_env = {
            'AIVALIDATION_UPLOAD_DIRECTORY': '/persistent/uploads',
            'AIVALIDATION_LOG_DIRECTORY': '/persistent/logs'
        }
        
        # Simulate first container start
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, persistent_env):
            
            resolver1 = PathResolver()
            upload_dir1 = resolver1.resolve_upload_directory()
            log_dir1 = resolver1.resolve_log_directory()
        
        # Simulate container restart (new resolver instance)
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, persistent_env):
            
            resolver2 = PathResolver()
            upload_dir2 = resolver2.resolve_upload_directory()
            log_dir2 = resolver2.resolve_log_directory()
        
        # Paths should be consistent across restarts
        assert upload_dir1 == upload_dir2
        assert log_dir1 == log_dir2
        assert upload_dir1 == '/persistent/uploads'
        assert log_dir1 == '/persistent/logs'


class TestContainerSecurityAndPermissions:
    """Test container security and permission scenarios"""
    
    def test_container_read_only_filesystem(self):
        """Test path resolution with read-only container filesystems"""
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'readonly-container'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        # Only /tmp should be writable in read-only containers
        readonly_env = {
            'AIVALIDATION_UPLOAD_DIRECTORY': '/tmp/uploads',
            'AIVALIDATION_LOG_DIRECTORY': '/tmp/logs',
            'AIVALIDATION_TEMP_DIRECTORY': '/tmp'
        }
        
        def mock_access(path, mode):
            # Simulate read-only filesystem except for /tmp
            if mode == os.W_OK:
                return path.startswith('/tmp')
            return True  # Read access allowed everywhere
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch.dict(os.environ, readonly_env), \
             patch('os.access', side_effect=mock_access):
            
            path_resolver = PathResolver()
            
            # Should resolve to writable /tmp paths
            upload_dir = path_resolver.resolve_upload_directory()
            log_dir = path_resolver.resolve_log_directory()
            temp_dir = path_resolver.resolve_temp_directory()
            
            assert upload_dir == '/tmp/uploads'
            assert log_dir == '/tmp/logs'
            assert temp_dir == '/tmp'
    
    def test_container_non_root_user_permissions(self):
        """Test path resolution with non-root container user"""
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'nonroot-container'},
            filesystem_info={
                'working_directory': '/app',
                'is_root_user': False
            },
            process_info={'pid': 1000},  # Non-root PID
            confidence_score=0.95
        )
        
        def mock_getuid():
            return 1000  # Non-root user ID
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch('os.getuid', side_effect=mock_getuid):
            
            path_resolver = PathResolver()
            
            # Should handle non-root permissions gracefully
            validation = path_resolver.validate_paths()
            
            assert 'filesystem' in validation
            # Should detect non-root user context
    
    def test_container_capability_restricted_environment(self):
        """Test path operations with restricted container capabilities"""
        docker_env_info = EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.PRODUCTION,
            platform="Linux-docker",
            python_version="3.12.0",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={'hostname': 'restricted-container'},
            filesystem_info={'working_directory': '/app'},
            process_info={'pid': 1},
            confidence_score=0.95
        )
        
        def restricted_makedirs(path, exist_ok=False):
            # Simulate capability restrictions
            if 'restricted' in path:
                raise PermissionError("Operation not permitted")
            # Allow /tmp operations
            if path.startswith('/tmp'):
                return True
            raise OSError("Capability restriction")
        
        with patch('config.path_resolver.detect_environment', return_value=docker_env_info), \
             patch('os.getcwd', return_value='/app'), \
             patch('os.makedirs', side_effect=restricted_makedirs):
            
            path_resolver = PathResolver()
            
            # Should handle capability restrictions gracefully
            resolved = path_resolver.resolve_path(
                PathType.UPLOAD_DIRECTORY,
                custom_path='/restricted/uploads',
                ensure_exists=True
            )
            
            # Should attempt creation but handle failure gracefully
            assert resolved is not None
            assert resolved.exists is False  # Creation failed due to restrictions


if __name__ == '__main__':
    pytest.main([__file__, '-v'])