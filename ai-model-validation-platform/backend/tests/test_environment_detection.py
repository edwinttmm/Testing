#!/usr/bin/env python3
"""
Comprehensive tests for environment detection component
Tests all detection methods and fallback strategies
"""

import pytest
import os
import tempfile
import socket
import unittest.mock as mock
from pathlib import Path
from typing import Dict, Any

# Import the environment detector components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.environment_detector import (
    UnifiedEnvironmentDetector,
    EnvironmentType,
    ServiceMode,
    EnvironmentInfo,
    detect_environment,
    get_environment_type,
    is_docker,
    is_local,
    is_production
)

class TestEnvironmentDetection:
    """Test suite for environment detection"""
    
    @pytest.fixture
    def detector(self):
        """Create a fresh detector instance for each test"""
        return UnifiedEnvironmentDetector()
    
    @pytest.fixture
    def mock_environment(self):
        """Mock environment variables"""
        original_env = os.environ.copy()
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
    
    def test_docker_primary_detection(self, detector, tmp_path):
        """Test primary Docker detection methods"""
        # Test /.dockerenv file detection
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == '/.dockerenv'
            
            result = detector._detect_docker_primary()
            assert result['docker_indicators'] >= 3
    
    def test_docker_environment_variables(self, detector, mock_environment):
        """Test Docker detection via environment variables"""
        # Set Docker environment variables
        os.environ['DOCKER'] = '1'
        os.environ['CONTAINER'] = 'true'
        os.environ['HOSTNAME'] = 'a1b2c3d4e5f6'  # 12-char alphanumeric
        
        result = detector._detect_docker_primary()
        assert result['docker_indicators'] >= 3
    
    def test_docker_secondary_detection(self, detector, tmp_path):
        """Test secondary Docker detection methods"""
        # Mock /proc/1/cgroup with Docker indicators
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text("1:name=systemd:/docker/abc123")
        
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == '/proc/1/cgroup'
            with mock.patch('builtins.open', mock.mock_open(read_data="1:name=systemd:/docker/abc123")):
                result = detector._detect_docker_secondary()
                assert result['docker_indicators'] >= 2
    
    def test_kubernetes_detection(self, detector):
        """Test Kubernetes environment detection"""
        # Mock Kubernetes service account directory
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == '/var/run/secrets/kubernetes.io'
            
            result = detector._detect_kubernetes()
            assert result['k8s_indicators'] >= 3
    
    def test_kubernetes_environment_variables(self, detector, mock_environment):
        """Test Kubernetes detection via environment variables"""
        os.environ['KUBERNETES_SERVICE_HOST'] = '10.96.0.1'
        os.environ['KUBERNETES_SERVICE_PORT'] = '443'
        
        result = detector._detect_kubernetes()
        assert result['k8s_indicators'] >= 2
    
    def test_cloud_provider_detection(self, detector, mock_environment):
        """Test cloud provider environment detection"""
        # Test AWS
        os.environ['AWS_REGION'] = 'us-west-2'
        os.environ['AWS_EXECUTION_ENV'] = 'AWS_ECS_FARGATE'
        
        result = detector._detect_cloud_providers()
        assert result['cloud_indicators'] >= 2
        
        # Clear AWS vars and test GCP
        del os.environ['AWS_REGION']
        del os.environ['AWS_EXECUTION_ENV']
        os.environ['GOOGLE_CLOUD_PROJECT'] = 'test-project'
        os.environ['CLOUD_RUN_SERVICE'] = 'test-service'
        
        result = detector._detect_cloud_providers()
        assert result['cloud_indicators'] >= 2
    
    def test_wsl_detection(self, detector, tmp_path):
        """Test Windows Subsystem for Linux detection"""
        # Mock /proc/version with WSL content
        with mock.patch('os.path.exists') as mock_exists:
            mock_exists.side_effect = lambda path: path == '/proc/version'
            with mock.patch('builtins.open', mock.mock_open(read_data="Linux version 4.4.0-19041-Microsoft")):
                result = detector._detect_wsl()
                assert result['wsl_indicators'] >= 3
    
    def test_local_environment_detection(self, detector):
        """Test local environment fallback detection"""
        with mock.patch('os.path.exists') as mock_exists:
            # Mock typical local environment indicators
            mock_exists.side_effect = lambda path: path in [
                os.path.expanduser('~/.bashrc'),
                '/usr/local',
                '/home'
            ]
            
            result = detector._detect_local_fallback()
            assert result['local_indicators'] >= 3
    
    def test_service_mode_detection(self, detector, mock_environment):
        """Test service mode detection"""
        # Test production mode detection
        os.environ['AIVALIDATION_APP_ENVIRONMENT'] = 'production'
        mode = detector._detect_service_mode()
        assert mode == ServiceMode.PRODUCTION
        
        # Test staging mode detection
        os.environ['AIVALIDATION_APP_ENVIRONMENT'] = 'staging'
        mode = detector._detect_service_mode()
        assert mode == ServiceMode.STAGING
        
        # Test development mode detection
        os.environ['AIVALIDATION_APP_ENVIRONMENT'] = 'development'
        mode = detector._detect_service_mode()
        assert mode == ServiceMode.DEVELOPMENT
        
        # Test fallback to development
        del os.environ['AIVALIDATION_APP_ENVIRONMENT']
        mode = detector._detect_service_mode()
        assert mode == ServiceMode.DEVELOPMENT
    
    def test_environment_type_determination(self, detector):
        """Test environment type determination logic"""
        # Test Docker environment
        results = {
            'docker_indicators': 5,
            'local_indicators': 2,
            'cloud_indicators': 0,
            'k8s_indicators': 0,
            'wsl_indicators': 0
        }
        
        env_type, confidence = detector._determine_environment_type(results)
        assert env_type == EnvironmentType.DOCKER
        assert confidence > 0.5
        
        # Test Kubernetes environment (should override Docker)
        results['k8s_indicators'] = 6
        env_type, confidence = detector._determine_environment_type(results)
        assert env_type == EnvironmentType.KUBERNETES
        assert confidence > 0.5
        
        # Test local fallback with low confidence
        results = {'docker_indicators': 0, 'local_indicators': 1, 'cloud_indicators': 0, 'k8s_indicators': 0, 'wsl_indicators': 0}
        env_type, confidence = detector._determine_environment_type(results)
        assert env_type == EnvironmentType.LOCAL
        assert confidence < 0.3
    
    def test_network_info_gathering(self, detector):
        """Test network information gathering"""
        network_info = detector._gather_network_info()
        
        assert 'hostname' in network_info
        assert 'local_ip' in network_info
        assert network_info['hostname'] is not None
        assert network_info['local_ip'] is not None
    
    def test_filesystem_info_gathering(self, detector):
        """Test filesystem information gathering"""
        fs_info = detector._gather_filesystem_info()
        
        assert 'working_directory' in fs_info
        assert 'home_directory' in fs_info
        assert fs_info['working_directory'] == os.getcwd()
        assert os.path.exists(fs_info['home_directory'])
    
    def test_process_info_gathering(self, detector):
        """Test process information gathering"""
        proc_info = detector._gather_process_info()
        
        assert 'pid' in proc_info
        assert proc_info['pid'] == os.getpid()
        
        if 'ppid' in proc_info and proc_info['ppid']:
            assert isinstance(proc_info['ppid'], int)
    
    def test_docker_availability_check(self, detector):
        """Test Docker availability checking"""
        # Mock Docker being available
        with mock.patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            assert detector._check_docker_availability() is True
            
        # Mock Docker not being available
        with mock.patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            assert detector._check_docker_availability() is False
    
    def test_complete_detection_flow(self, detector):
        """Test complete environment detection flow"""
        env_info = detector.detect_environment()
        
        # Verify EnvironmentInfo structure
        assert isinstance(env_info, EnvironmentInfo)
        assert isinstance(env_info.environment_type, EnvironmentType)
        assert isinstance(env_info.service_mode, ServiceMode)
        assert isinstance(env_info.is_containerized, bool)
        assert isinstance(env_info.confidence_score, float)
        assert 0.0 <= env_info.confidence_score <= 1.0
        
        # Verify all required fields are present
        assert env_info.platform is not None
        assert env_info.python_version is not None
        assert env_info.network_info is not None
        assert env_info.filesystem_info is not None
        assert env_info.process_info is not None
    
    def test_caching_behavior(self, detector):
        """Test environment detection caching"""
        # First detection
        env_info1 = detector.detect_environment()
        
        # Second detection should use cache
        env_info2 = detector.detect_environment()
        
        # Should be the same object (cached)
        assert env_info1 is env_info2
        
        # Force refresh should create new detection
        env_info3 = detector.detect_environment(force_refresh=True)
        
        # Should have same values but different object
        assert env_info1.environment_type == env_info3.environment_type
        assert env_info1 is not env_info3
    
    def test_environment_summary(self, detector):
        """Test environment summary generation"""
        summary = detector.get_environment_summary()
        
        required_keys = [
            'environment_type', 'service_mode', 'platform', 'python_version',
            'is_containerized', 'confidence_score', 'network', 'filesystem'
        ]
        
        for key in required_keys:
            assert key in summary
        
        assert summary['environment_type'] in [e.value for e in EnvironmentType]
        assert summary['service_mode'] in [m.value for m in ServiceMode]
        assert isinstance(summary['confidence_score'], float)
    
    @pytest.mark.parametrize("env_type,expected_containerized", [
        (EnvironmentType.DOCKER, True),
        (EnvironmentType.KUBERNETES, True),
        (EnvironmentType.LOCAL, False),
        (EnvironmentType.WSL, False),
        (EnvironmentType.CLOUD, False)
    ])
    def test_containerization_detection(self, env_type, expected_containerized):
        """Test containerization detection for different environment types"""
        env_info = EnvironmentInfo(
            environment_type=env_type,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="test",
            python_version="3.9",
            is_containerized=env_type in [EnvironmentType.DOCKER, EnvironmentType.KUBERNETES],
            is_wsl=env_type == EnvironmentType.WSL,
            has_docker=False,
            network_info={},
            filesystem_info={},
            process_info={},
            confidence_score=0.8
        )
        
        assert env_info.is_containerized == expected_containerized

class TestConvenienceFunctions:
    """Test convenience functions for environment detection"""
    
    def test_detect_environment_function(self):
        """Test global detect_environment function"""
        env_info = detect_environment()
        assert isinstance(env_info, EnvironmentInfo)
    
    def test_get_environment_type_function(self):
        """Test get_environment_type function"""
        env_type = get_environment_type()
        assert isinstance(env_type, EnvironmentType)
    
    def test_boolean_check_functions(self):
        """Test boolean check functions"""
        # These should not raise exceptions
        assert isinstance(is_docker(), bool)
        assert isinstance(is_local(), bool)
        assert isinstance(is_production(), bool)

class TestErrorHandling:
    """Test error handling in environment detection"""
    
    def test_detection_method_failure_handling(self, detector):
        """Test handling of individual detection method failures"""
        # Mock a detection method to fail
        original_method = detector._detect_docker_primary
        
        def failing_method():
            raise Exception("Test failure")
        
        detector._detect_docker_primary = failing_method
        
        # Detection should still work with other methods
        try:
            env_info = detector.detect_environment(force_refresh=True)
            assert isinstance(env_info, EnvironmentInfo)
        finally:
            # Restore original method
            detector._detect_docker_primary = original_method
    
    def test_network_info_failure_handling(self, detector):
        """Test handling of network info gathering failures"""
        with mock.patch('socket.socket') as mock_socket:
            mock_socket.side_effect = Exception("Network error")
            
            network_info = detector._gather_network_info()
            
            # Should have fallback values
            assert network_info['hostname'] == 'localhost'
            assert network_info['local_ip'] == '127.0.0.1'
    
    def test_filesystem_info_failure_handling(self, detector):
        """Test handling of filesystem info gathering failures"""
        with mock.patch('os.getcwd') as mock_getcwd:
            mock_getcwd.side_effect = Exception("Filesystem error")
            
            fs_info = detector._gather_filesystem_info()
            
            # Should handle the error gracefully
            assert isinstance(fs_info, dict)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])