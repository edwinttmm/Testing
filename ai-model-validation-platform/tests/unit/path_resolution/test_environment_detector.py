#!/usr/bin/env python3
"""
Unit tests for UnifiedEnvironmentDetector - Environment Detection Component
Tests environment detection with comprehensive mock scenarios
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open, MagicMock
import socket
import platform

# Add backend src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../backend/src'))

from config.environment_detector import (
    UnifiedEnvironmentDetector, EnvironmentType, ServiceMode, EnvironmentInfo,
    detect_environment, get_environment_type, is_containerized, is_docker, is_local
)


class TestUnifiedEnvironmentDetector:
    """Comprehensive tests for UnifiedEnvironmentDetector"""
    
    @pytest.fixture
    def detector(self):
        """Create fresh detector for each test"""
        detector = UnifiedEnvironmentDetector()
        detector._cached_detection = None  # Clear cache
        return detector
    
    def test_detector_initialization(self, detector):
        """Test detector initializes correctly"""
        assert detector is not None
        assert hasattr(detector, 'detection_methods')
        assert len(detector.detection_methods) > 0
        assert hasattr(detector, '_cached_detection')
    
    def test_docker_primary_detection_dockerenv(self, detector):
        """Test Docker detection using .dockerenv file"""
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == '/.dockerenv'
            
            result = detector._detect_docker_primary()
            
            assert result['docker_indicators'] >= 3  # .dockerenv gives 3 points
    
    def test_docker_primary_detection_hostname(self, detector):
        """Test Docker detection using hostname pattern"""
        with patch('os.path.exists', return_value=False), \
             patch.dict(os.environ, {'HOSTNAME': 'abc123def456'}):  # 12-char alphanumeric
            
            result = detector._detect_docker_primary()
            
            assert result['docker_indicators'] >= 2  # Hostname pattern gives 2 points
    
    def test_docker_secondary_detection_cgroup(self, detector):
        """Test Docker detection using /proc/1/cgroup"""
        cgroup_content = """
        12:devices:/docker/container123
        11:cpuset:/docker/container123
        10:memory:/docker/container123
        """
        
        with patch('os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=cgroup_content)):
            mock_exists.side_effect = lambda path: path == '/proc/1/cgroup'
            
            result = detector._detect_docker_secondary()
            
            assert result['docker_indicators'] >= 2  # cgroup docker indicators
    
    def test_docker_secondary_detection_overlay_fs(self, detector):
        """Test Docker detection using overlay filesystem"""
        mounts_content = """
        overlay /merged overlay rw,relatime,lowerdir=/var/lib/docker/overlay2
        tmpfs /dev tmpfs rw,nosuid,size=65536k,mode=755
        """
        
        with patch('os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=mounts_content)):
            mock_exists.side_effect = lambda path: path == '/proc/mounts'
            
            result = detector._detect_docker_secondary()
            
            assert result['docker_indicators'] >= 2  # overlay + docker in mounts
    
    def test_kubernetes_detection(self, detector):
        """Test Kubernetes environment detection"""
        with patch('os.path.exists') as mock_exists, \
             patch.dict(os.environ, {
                 'KUBERNETES_SERVICE_HOST': '10.96.0.1',
                 'KUBERNETES_SERVICE_PORT': '443'
             }):
            mock_exists.side_effect = lambda path: path == '/var/run/secrets/kubernetes.io'
            
            result = detector._detect_kubernetes()
            
            assert result['k8s_indicators'] >= 5  # Service account + 2 env vars
    
    def test_cloud_aws_detection(self, detector):
        """Test AWS cloud environment detection"""
        with patch.dict(os.environ, {
            'AWS_REGION': 'us-east-1',
            'AWS_EXECUTION_ENV': 'AWS_ECS_FARGATE',
            'ECS_CONTAINER_METADATA_URI': 'http://169.254.170.2/v3'
        }):
            result = detector._detect_cloud_providers()
            
            assert result['cloud_indicators'] >= 3  # 3 AWS indicators
    
    def test_cloud_gcp_detection(self, detector):
        """Test Google Cloud environment detection"""
        with patch.dict(os.environ, {
            'GOOGLE_CLOUD_PROJECT': 'my-project-123',
            'CLOUD_RUN_SERVICE': 'my-service'
        }):
            result = detector._detect_cloud_providers()
            
            assert result['cloud_indicators'] >= 2  # 2 GCP indicators
    
    def test_cloud_azure_detection(self, detector):
        """Test Azure cloud environment detection"""
        with patch.dict(os.environ, {
            'AZURE_RESOURCE_GROUP': 'my-rg',
            'WEBSITE_SITE_NAME': 'my-app-service'  # Azure App Service
        }):
            result = detector._detect_cloud_providers()
            
            assert result['cloud_indicators'] >= 2  # 2 Azure indicators
    
    def test_wsl_detection_proc_version(self, detector):
        """Test WSL detection using /proc/version"""
        version_content = "Linux version 4.19.128-microsoft-standard (oe-user@oe-host)"
        
        with patch('os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=version_content)):
            mock_exists.side_effect = lambda path: path == '/proc/version'
            
            result = detector._detect_wsl()
            
            assert result['wsl_indicators'] >= 3  # Microsoft in /proc/version
    
    def test_wsl_detection_environment_vars(self, detector):
        """Test WSL detection using environment variables"""
        with patch.dict(os.environ, {
            'WSL_DISTRO_NAME': 'Ubuntu',
            'WSLENV': 'PATH/l'
        }):
            result = detector._detect_wsl()
            
            assert result['wsl_indicators'] >= 2  # 2 WSL env vars
    
    def test_wsl_detection_windows_mounts(self, detector):
        """Test WSL detection using Windows filesystem mounts"""
        with patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == '/mnt/c'
            
            result = detector._detect_wsl()
            
            assert result['wsl_indicators'] >= 1  # Windows mount detected
    
    def test_local_fallback_detection(self, detector):
        """Test local environment fallback detection"""
        with patch('os.path.exists') as mock_exists, \
             patch('platform.system', return_value='Linux'), \
             patch('os.path.expanduser') as mock_expanduser:
            
            # Mock home directory files
            mock_expanduser.side_effect = lambda path: path.replace('~', '/home/user')
            mock_exists.side_effect = lambda path: path in [
                '/home/user/.bashrc', '/home/user/.profile', '/usr/local', '/home'
            ]
            
            result = detector._detect_local_fallback()
            
            assert result['local_indicators'] >= 4  # Should detect multiple local indicators
    
    def test_service_mode_detection_production(self, detector):
        """Test production service mode detection"""
        with patch.dict(os.environ, {
            'AIVALIDATION_APP_ENVIRONMENT': 'production',
            'DEBUG': 'false',
            'SSL_ENABLED': 'true'
        }):
            mode = detector._detect_service_mode()
            assert mode == ServiceMode.PRODUCTION
    
    def test_service_mode_detection_staging(self, detector):
        """Test staging service mode detection"""
        with patch.dict(os.environ, {'APP_ENV': 'staging'}):
            mode = detector._detect_service_mode()
            assert mode == ServiceMode.STAGING
    
    def test_service_mode_detection_testing(self, detector):
        """Test testing service mode detection"""
        with patch.dict(os.environ, {'NODE_ENV': 'test'}):
            mode = detector._detect_service_mode()
            assert mode == ServiceMode.TESTING
    
    def test_service_mode_detection_development_default(self, detector):
        """Test development service mode as default"""
        with patch.dict(os.environ, {}, clear=True):
            mode = detector._detect_service_mode()
            assert mode == ServiceMode.DEVELOPMENT
    
    def test_complete_environment_detection_docker(self, detector):
        """Test complete Docker environment detection"""
        with patch('os.path.exists') as mock_exists, \
             patch.dict(os.environ, {
                 'HOSTNAME': 'container123',
                 'APP_ENV': 'production'
             }):
            mock_exists.side_effect = lambda path: path == '/.dockerenv'
            
            env_info = detector.detect_environment()
            
            assert env_info.environment_type == EnvironmentType.DOCKER
            assert env_info.service_mode == ServiceMode.PRODUCTION
            assert env_info.is_containerized is True
            assert env_info.confidence_score > 0.5
    
    def test_complete_environment_detection_kubernetes(self, detector):
        """Test complete Kubernetes environment detection"""
        with patch('os.path.exists') as mock_exists, \
             patch.dict(os.environ, {
                 'KUBERNETES_SERVICE_HOST': '10.96.0.1',
                 'KUBERNETES_SERVICE_PORT': '443',
                 'K8S_NAMESPACE': 'default'
             }):
            mock_exists.side_effect = lambda path: path == '/var/run/secrets/kubernetes.io'
            
            env_info = detector.detect_environment()
            
            assert env_info.environment_type == EnvironmentType.KUBERNETES
            assert env_info.is_containerized is True
            assert env_info.confidence_score > 0.7
    
    def test_complete_environment_detection_wsl(self, detector):
        """Test complete WSL environment detection"""
        version_content = "Linux version 4.19.128-microsoft-standard"
        
        with patch('os.path.exists') as mock_exists, \
             patch('builtins.open', mock_open(read_data=version_content)), \
             patch.dict(os.environ, {'WSL_DISTRO_NAME': 'Ubuntu'}):
            mock_exists.side_effect = lambda path: path in ['/proc/version', '/mnt/c']
            
            env_info = detector.detect_environment()
            
            assert env_info.environment_type == EnvironmentType.WSL
            assert env_info.is_wsl is True
            assert env_info.is_containerized is False
            assert env_info.confidence_score > 0.5
    
    def test_complete_environment_detection_local(self, detector):
        """Test complete local environment detection"""
        with patch('os.path.exists') as mock_exists, \
             patch('platform.system', return_value='Linux'), \
             patch('os.path.expanduser') as mock_expanduser:
            
            mock_expanduser.side_effect = lambda path: path.replace('~', '/home/user')
            mock_exists.side_effect = lambda path: path in [
                '/home/user/.bashrc', '/usr/local', '/home'
            ] and path != '/.dockerenv'
            
            env_info = detector.detect_environment()
            
            assert env_info.environment_type == EnvironmentType.LOCAL
            assert env_info.is_containerized is False
            assert env_info.is_wsl is False
    
    def test_caching_mechanism(self, detector):
        """Test environment detection caching"""
        with patch('os.path.exists', return_value=False):
            # First detection
            env_info1 = detector.detect_environment()
            
            # Second detection should use cache
            env_info2 = detector.detect_environment()
            
            assert env_info1 is env_info2  # Same object from cache
    
    def test_force_refresh_bypasses_cache(self, detector):
        """Test force refresh bypasses cache"""
        with patch('os.path.exists', return_value=False):
            # Initial detection
            env_info1 = detector.detect_environment()
            
            # Force refresh should create new detection
            env_info2 = detector.detect_environment(force_refresh=True)
            
            # Should be different objects (new detection)
            assert env_info1 is not env_info2
    
    def test_network_info_gathering(self, detector):
        """Test network information gathering"""
        network_info = detector._gather_network_info()
        
        assert 'hostname' in network_info
        assert 'local_ip' in network_info
        assert isinstance(network_info['hostname'], str)
        assert isinstance(network_info['local_ip'], str)
    
    def test_filesystem_info_gathering(self, detector):
        """Test filesystem information gathering"""
        filesystem_info = detector._gather_filesystem_info()
        
        assert 'working_directory' in filesystem_info
        assert 'home_directory' in filesystem_info
        assert isinstance(filesystem_info['working_directory'], str)
    
    def test_process_info_gathering(self, detector):
        """Test process information gathering"""
        process_info = detector._gather_process_info()
        
        assert 'pid' in process_info
        assert isinstance(process_info['pid'], int)
    
    def test_docker_availability_check(self, detector):
        """Test Docker availability checking"""
        # Mock successful docker command
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            has_docker = detector._check_docker_availability()
            assert has_docker is True
        
        # Mock failed docker command
        with patch('subprocess.run', side_effect=FileNotFoundError):
            has_docker = detector._check_docker_availability()
            assert has_docker is False
    
    def test_environment_summary(self, detector):
        """Test environment summary generation"""
        with patch('os.path.exists', return_value=False):
            summary = detector.get_environment_summary()
            
            assert 'environment_type' in summary
            assert 'service_mode' in summary
            assert 'platform' in summary
            assert 'confidence_score' in summary
            assert 'network' in summary
            assert 'filesystem' in summary


class TestEnvironmentDetectorConvenienceFunctions:
    """Test convenience functions for environment detection"""
    
    def test_detect_environment_function(self):
        """Test convenience detect_environment function"""
        with patch('config.environment_detector.environment_detector.detect_environment') as mock_detect:
            mock_env_info = EnvironmentInfo(
                environment_type=EnvironmentType.DOCKER,
                service_mode=ServiceMode.PRODUCTION,
                platform="Linux",
                python_version="3.12.0",
                is_containerized=True,
                is_wsl=False,
                has_docker=True,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            mock_detect.return_value = mock_env_info
            
            result = detect_environment()
            assert result.environment_type == EnvironmentType.DOCKER
    
    def test_get_environment_type_function(self):
        """Test get_environment_type convenience function"""
        with patch('config.environment_detector.environment_detector.detect_environment') as mock_detect:
            mock_env_info = EnvironmentInfo(
                environment_type=EnvironmentType.LOCAL,
                service_mode=ServiceMode.DEVELOPMENT,
                platform="Linux",
                python_version="3.12.0",
                is_containerized=False,
                is_wsl=False,
                has_docker=False,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.8
            )
            mock_detect.return_value = mock_env_info
            
            result = get_environment_type()
            assert result == EnvironmentType.LOCAL
    
    def test_is_containerized_function(self):
        """Test is_containerized convenience function"""
        with patch('config.environment_detector.environment_detector.detect_environment') as mock_detect:
            mock_env_info = EnvironmentInfo(
                environment_type=EnvironmentType.DOCKER,
                service_mode=ServiceMode.PRODUCTION,
                platform="Linux",
                python_version="3.12.0",
                is_containerized=True,
                is_wsl=False,
                has_docker=True,
                network_info={},
                filesystem_info={},
                process_info={},
                confidence_score=0.9
            )
            mock_detect.return_value = mock_env_info
            
            result = is_containerized()
            assert result is True
    
    def test_is_docker_function(self):
        """Test is_docker convenience function"""
        with patch('config.environment_detector.get_environment_type') as mock_get_type:
            mock_get_type.return_value = EnvironmentType.DOCKER
            
            result = is_docker()
            assert result is True
    
    def test_is_local_function(self):
        """Test is_local convenience function"""
        with patch('config.environment_detector.get_environment_type') as mock_get_type:
            mock_get_type.return_value = EnvironmentType.LOCAL
            
            result = is_local()
            assert result is True


class TestEnvironmentDetectorErrorHandling:
    """Test error handling in environment detection"""
    
    def test_detection_method_failure_resilience(self):
        """Test that detection continues even when some methods fail"""
        detector = UnifiedEnvironmentDetector()
        
        # Mock one detection method to fail
        original_method = detector._detect_docker_primary
        def failing_method():
            raise Exception("Simulated failure")
        
        detector._detect_docker_primary = failing_method
        
        # Detection should still work
        env_info = detector.detect_environment()
        assert env_info is not None
        assert isinstance(env_info, EnvironmentInfo)
    
    def test_network_info_failure_handling(self):
        """Test network info gathering failure handling"""
        detector = UnifiedEnvironmentDetector()
        
        with patch('socket.socket', side_effect=Exception("Network error")):
            network_info = detector._gather_network_info()
            
            # Should return default values
            assert network_info['hostname'] == 'localhost'
            assert network_info['local_ip'] == '127.0.0.1'
    
    def test_filesystem_info_failure_handling(self):
        """Test filesystem info gathering failure handling"""
        detector = UnifiedEnvironmentDetector()
        
        with patch('os.getcwd', side_effect=Exception("Filesystem error")):
            filesystem_info = detector._gather_filesystem_info()
            
            # Should handle gracefully
            assert isinstance(filesystem_info, dict)
    
    def test_low_confidence_fallback(self):
        """Test fallback to local when confidence is too low"""
        detector = UnifiedEnvironmentDetector()
        
        # Mock all detection methods to return minimal indicators
        with patch.object(detector, '_detect_docker_primary', return_value={'docker_indicators': 0}), \
             patch.object(detector, '_detect_docker_secondary', return_value={'docker_indicators': 0}), \
             patch.object(detector, '_detect_kubernetes', return_value={'k8s_indicators': 0}), \
             patch.object(detector, '_detect_cloud_providers', return_value={'cloud_indicators': 0}), \
             patch.object(detector, '_detect_wsl', return_value={'wsl_indicators': 0}), \
             patch.object(detector, '_detect_local_fallback', return_value={'local_indicators': 1}):
            
            env_info = detector.detect_environment()
            
            # Should fall back to local with low confidence
            assert env_info.environment_type == EnvironmentType.LOCAL
            assert env_info.confidence_score < 0.3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])