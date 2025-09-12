#!/usr/bin/env python3
"""
Pytest configuration for path management tests
Shared fixtures and test configuration
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch
import platform

# Add backend paths for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))

from config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo


@pytest.fixture(scope="session")
def temp_test_workspace():
    """Create a temporary workspace for all path management tests"""
    temp_dir = tempfile.mkdtemp(prefix='path_test_workspace_')
    
    # Create standard directory structure
    subdirs = ['uploads', 'logs', 'data', 'config', 'temp', 'models', 'exports', 'cache']
    for subdir in subdirs:
        os.makedirs(os.path.join(temp_dir, subdir), exist_ok=True)
    
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def isolated_temp_dir():
    """Create isolated temporary directory for individual tests"""
    temp_dir = tempfile.mkdtemp(prefix='isolated_test_')
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def local_environment_info():
    """Standard local environment info for testing"""
    return EnvironmentInfo(
        environment_type=EnvironmentType.LOCAL,
        service_mode=ServiceMode.DEVELOPMENT,
        platform=platform.platform(),
        python_version=platform.python_version(),
        is_containerized=False,
        is_wsl=False,
        has_docker=False,
        network_info={'hostname': 'test-machine', 'local_ip': '127.0.0.1'},
        filesystem_info={'working_directory': os.getcwd()},
        process_info={'pid': os.getpid()},
        confidence_score=0.9
    )


@pytest.fixture
def docker_environment_info():
    """Docker container environment info for testing"""
    return EnvironmentInfo(
        environment_type=EnvironmentType.DOCKER,
        service_mode=ServiceMode.PRODUCTION,
        platform="Linux-docker",
        python_version="3.12.0",
        is_containerized=True,
        is_wsl=False,
        has_docker=True,
        network_info={'hostname': 'container-abc123', 'local_ip': '172.17.0.2'},
        filesystem_info={'working_directory': '/app', 'filesystem_type': 'overlay'},
        process_info={'pid': 1, 'ppid': 0, 'init_process': 'python'},
        confidence_score=0.95
    )


@pytest.fixture
def kubernetes_environment_info():
    """Kubernetes pod environment info for testing"""
    return EnvironmentInfo(
        environment_type=EnvironmentType.KUBERNETES,
        service_mode=ServiceMode.PRODUCTION,
        platform="Linux-kubernetes",
        python_version="3.12.0",
        is_containerized=True,
        is_wsl=False,
        has_docker=True,
        network_info={'hostname': 'pod-7d8c9b-xyz', 'local_ip': '10.244.0.15'},
        filesystem_info={'working_directory': '/app', 'filesystem_type': 'overlay'},
        process_info={'pid': 1, 'ppid': 0, 'init_process': 'python'},
        confidence_score=0.92
    )


@pytest.fixture
def wsl_environment_info():
    """WSL environment info for testing"""
    return EnvironmentInfo(
        environment_type=EnvironmentType.WSL,
        service_mode=ServiceMode.DEVELOPMENT,
        platform="Linux-wsl",
        python_version="3.12.0",
        is_containerized=False,
        is_wsl=True,
        has_docker=False,
        network_info={'hostname': 'wsl-machine', 'local_ip': '172.20.0.1'},
        filesystem_info={'working_directory': '/home/user/project'},
        process_info={'pid': 1234},
        confidence_score=0.85
    )


@pytest.fixture
def cloud_environment_info():
    """Cloud environment info for testing"""
    return EnvironmentInfo(
        environment_type=EnvironmentType.CLOUD,
        service_mode=ServiceMode.PRODUCTION,
        platform="Linux-cloud",
        python_version="3.12.0",
        is_containerized=True,
        is_wsl=False,
        has_docker=True,
        network_info={'hostname': 'cloud-instance-xyz', 'local_ip': '10.0.1.15'},
        filesystem_info={'working_directory': '/app'},
        process_info={'pid': 1},
        confidence_score=0.88
    )


@pytest.fixture
def mock_video_files(temp_test_workspace):
    """Create mock video files for testing"""
    video_files = {}
    
    video_names = [
        'test_video_1.mp4',
        'test_video_2.mp4',
        'sample_detection.mp4',
        'ground_truth_test.mp4'
    ]
    
    uploads_dir = os.path.join(temp_test_workspace, 'uploads')
    
    for video_name in video_names:
        video_path = os.path.join(uploads_dir, video_name)
        with open(video_path, 'wb') as f:
            f.write(b'mock video content for ' + video_name.encode())
        video_files[video_name] = video_path
    
    return video_files


@pytest.fixture
def clean_environment_variables():
    """Clean environment variables for testing"""
    # Store original values
    original_env = {}
    test_env_vars = [
        'AIVALIDATION_UPLOAD_DIRECTORY',
        'AIVALIDATION_LOG_DIRECTORY', 
        'AIVALIDATION_DATA_DIRECTORY',
        'AIVALIDATION_CONFIG_DIRECTORY',
        'AIVALIDATION_TEMP_DIRECTORY',
        'AIVALIDATION_MODEL_DIRECTORY',
        'AIVALIDATION_EXPORT_DIRECTORY',
        'AIVALIDATION_CACHE_DIRECTORY',
        'UPLOAD_DIRECTORY',
        'LOG_DIRECTORY',
        'DATA_DIRECTORY',
        'TEMP_DIRECTORY',
        'TMP',
        'TMPDIR'
    ]
    
    # Store and clear test environment variables
    for var in test_env_vars:
        if var in os.environ:
            original_env[var] = os.environ[var]
            del os.environ[var]
    
    yield
    
    # Restore original values
    for var, value in original_env.items():
        os.environ[var] = value


@pytest.fixture(autouse=True)
def clear_path_resolver_cache():
    """Automatically clear path resolver cache between tests"""
    # This runs before each test
    yield
    
    # This runs after each test
    try:
        from config.path_resolver import path_resolver
        path_resolver.clear_cache()
    except ImportError:
        # path_resolver module may not be available
        pass


@pytest.fixture
def mock_filesystem_operations():
    """Mock filesystem operations for controlled testing"""
    mocks = {}
    
    def create_mock_exists(existing_paths):
        def mock_exists(path):
            return path in existing_paths
        return mock_exists
    
    def create_mock_access(permissions):
        def mock_access(path, mode):
            return permissions.get(path, {}).get(mode, True)
        return mock_access
    
    def create_mock_makedirs(allowed_paths):
        def mock_makedirs(path, exist_ok=False):
            if path not in allowed_paths:
                raise PermissionError(f"Cannot create directory: {path}")
            return True
        return mock_makedirs
    
    mocks['create_mock_exists'] = create_mock_exists
    mocks['create_mock_access'] = create_mock_access 
    mocks['create_mock_makedirs'] = create_mock_makedirs
    
    return mocks


# Test markers for different test categories
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "path_resolution: mark test as path resolution test"
    )
    config.addinivalue_line(
        "markers", "cross_platform: mark test as cross-platform test"
    )
    config.addinivalue_line(
        "markers", "error_handling: mark test as error handling test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "container: mark test as container-related test"
    )
    config.addinivalue_line(
        "markers", "migration: mark test as migration-related test"
    )


# Pytest collection hooks for organizing tests
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file location"""
    for item in items:
        # Add markers based on test file name
        if "test_path_resolver" in item.nodeid:
            item.add_marker(pytest.mark.unit)
            item.add_marker(pytest.mark.path_resolution)
        
        if "test_environment_detector" in item.nodeid:
            item.add_marker(pytest.mark.unit)
            item.add_marker(pytest.mark.cross_platform)
        
        if "test_ground_truth_path_processing" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.path_resolution)
        
        if "test_working_directory_contexts" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.path_resolution)
        
        if "test_error_handling_missing_files" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.error_handling)
        
        if "test_path_migration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.migration)
        
        if "test_container_deployment_simulation" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.container)
        
        if "test_path_validation_normalization" in item.nodeid:
            item.add_marker(pytest.mark.unit)
            item.add_marker(pytest.mark.path_resolution)
        
        if "test_cross_platform_compatibility" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.cross_platform)


# Skip markers for conditional test execution
def pytest_runtest_setup(item):
    """Setup hook to skip tests based on platform or environment"""
    # Skip Windows-specific tests on non-Windows platforms
    if item.get_closest_marker("windows_only") and os.name != 'nt':
        pytest.skip("Windows-only test")
    
    # Skip Unix-specific tests on Windows
    if item.get_closest_marker("unix_only") and os.name == 'nt':
        pytest.skip("Unix-only test")
    
    # Skip Docker tests if Docker is not available
    if item.get_closest_marker("requires_docker"):
        try:
            import subprocess
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("Docker not available")