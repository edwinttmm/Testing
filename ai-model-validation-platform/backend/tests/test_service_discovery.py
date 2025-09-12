#!/usr/bin/env python3
"""
Comprehensive tests for service discovery component
Tests adaptive endpoint resolution and fallback strategies
"""

import pytest
import asyncio
import os
import socket
import time
import unittest.mock as mock
from typing import Dict, Any, Optional

# Import the service discovery components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.service_discovery import (
    ServiceDiscoveryManager,
    ServiceType,
    ServiceStatus,
    ServiceEndpoint,
    ServiceInfo,
    service_discovery,
    discover_database,
    discover_redis,
    get_database_url,
    get_redis_url
)

from src.config.environment_detector import EnvironmentType, ServiceMode, EnvironmentInfo

class TestServiceEndpoint:
    """Test ServiceEndpoint functionality"""
    
    def test_endpoint_creation(self):
        """Test basic endpoint creation"""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=5432,
            protocol="postgresql",
            username="user",
            password="pass",
            database="testdb"
        )
        
        assert endpoint.host == "localhost"
        assert endpoint.port == 5432
        assert endpoint.protocol == "postgresql"
        assert endpoint.username == "user"
        assert endpoint.password == "pass"
        assert endpoint.database == "testdb"
    
    def test_endpoint_to_url(self):
        """Test URL generation from endpoint"""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=5432,
            protocol="postgresql",
            username="user",
            password="pass",
            database="testdb"
        )
        
        expected_url = "postgresql://user:pass@localhost:5432/testdb"
        assert endpoint.to_url() == expected_url
    
    def test_endpoint_to_url_no_auth(self):
        """Test URL generation without authentication"""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=6379,
            protocol="redis"
        )
        
        expected_url = "redis://localhost:6379"
        assert endpoint.to_url() == expected_url
    
    def test_endpoint_connection_string(self):
        """Test connection string generation"""
        endpoint = ServiceEndpoint(
            host="postgres",
            port=5432,
            protocol="postgresql",
            username="postgres",
            password="password",
            database="ai_validation"
        )
        
        expected_conn_str = "postgresql://postgres:password@postgres:5432/ai_validation"
        assert endpoint.to_connection_string() == expected_conn_str

class TestServiceInfo:
    """Test ServiceInfo functionality"""
    
    def test_service_info_creation(self):
        """Test ServiceInfo creation with all fields"""
        endpoint = ServiceEndpoint(host="localhost", port=5432)
        
        service_info = ServiceInfo(
            name="postgres",
            service_type=ServiceType.DATABASE,
            endpoint=endpoint,
            status=ServiceStatus.AVAILABLE,
            response_time_ms=50.5,
            metadata={"version": "13.4"}
        )
        
        assert service_info.name == "postgres"
        assert service_info.service_type == ServiceType.DATABASE
        assert service_info.status == ServiceStatus.AVAILABLE
        assert service_info.response_time_ms == 50.5
        assert service_info.metadata["version"] == "13.4"
    
    def test_service_info_post_init(self):
        """Test ServiceInfo post-init metadata handling"""
        endpoint = ServiceEndpoint(host="localhost", port=5432)
        
        service_info = ServiceInfo(
            name="postgres",
            service_type=ServiceType.DATABASE,
            endpoint=endpoint,
            status=ServiceStatus.AVAILABLE
        )
        
        # Metadata should be initialized as empty dict
        assert service_info.metadata == {}

class TestServiceDiscoveryManager:
    """Test ServiceDiscoveryManager functionality"""
    
    @pytest.fixture
    def discovery_manager(self):
        """Create a fresh discovery manager for each test"""
        return ServiceDiscoveryManager()
    
    @pytest.fixture
    def mock_environment(self):
        """Mock environment variables"""
        original_env = os.environ.copy()
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
    
    @pytest.fixture
    def mock_docker_env(self):
        """Mock Docker environment info"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.DOCKER,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="linux",
            python_version="3.9",
            is_containerized=True,
            is_wsl=False,
            has_docker=True,
            network_info={"hostname": "container-123", "local_ip": "172.17.0.2"},
            filesystem_info={},
            process_info={},
            confidence_score=0.9
        )
    
    @pytest.fixture
    def mock_local_env(self):
        """Mock local environment info"""
        return EnvironmentInfo(
            environment_type=EnvironmentType.LOCAL,
            service_mode=ServiceMode.DEVELOPMENT,
            platform="linux",
            python_version="3.9",
            is_containerized=False,
            is_wsl=False,
            has_docker=False,
            network_info={"hostname": "localhost", "local_ip": "127.0.0.1"},
            filesystem_info={},
            process_info={},
            confidence_score=0.8
        )
    
    @pytest.mark.asyncio
    async def test_discover_from_environment_variables(self, discovery_manager, mock_environment):
        """Test service discovery from environment variables"""
        # Set PostgreSQL environment variables
        os.environ['POSTGRES_URL'] = 'postgresql://user:pass@postgres:5432/testdb'
        
        endpoints = await discovery_manager._discover_environment_variables("postgres", ServiceType.DATABASE)
        
        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert endpoint.host == "postgres"
        assert endpoint.port == 5432
        assert endpoint.username == "user"
        assert endpoint.password == "pass"
        assert endpoint.database == "testdb"
    
    @pytest.mark.asyncio
    async def test_discover_from_components(self, discovery_manager, mock_environment):
        """Test service discovery from individual components"""
        # Set individual component environment variables
        os.environ['POSTGRES_HOST'] = 'localhost'
        os.environ['POSTGRES_PORT'] = '5432'
        os.environ['POSTGRES_USER'] = 'postgres'
        os.environ['POSTGRES_PASSWORD'] = 'password'
        os.environ['POSTGRES_DB'] = 'ai_validation'
        
        endpoints = await discovery_manager._discover_environment_variables("postgres", ServiceType.DATABASE)
        
        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert endpoint.host == "localhost"
        assert endpoint.port == 5432
        assert endpoint.username == "postgres"
        assert endpoint.password == "password"
        assert endpoint.database == "ai_validation"
    
    @pytest.mark.asyncio
    async def test_docker_service_discovery(self, discovery_manager, mock_docker_env):
        """Test Docker service discovery using DNS resolution"""
        discovery_manager._env_info = mock_docker_env
        
        with mock.patch('socket.gethostbyname') as mock_gethostbyname:
            mock_gethostbyname.return_value = "172.17.0.3"
            
            with mock.patch.object(discovery_manager, '_test_tcp_connection') as mock_tcp:
                mock_tcp.return_value = True
                
                endpoints = await discovery_manager._discover_docker_services("postgres", ServiceType.DATABASE)
                
                assert len(endpoints) > 0
                # Check that postgres hostname was resolved
                mock_gethostbyname.assert_called()
                mock_tcp.assert_called()
    
    @pytest.mark.asyncio
    async def test_localhost_service_discovery(self, discovery_manager, mock_local_env):
        """Test localhost service discovery"""
        discovery_manager._env_info = mock_local_env
        
        with mock.patch.object(discovery_manager, '_test_tcp_connection') as mock_tcp:
            mock_tcp.return_value = True
            
            endpoints = await discovery_manager._discover_localhost_services("postgres", ServiceType.DATABASE)
            
            assert len(endpoints) > 0
            # Should test localhost and 127.0.0.1
            assert any(endpoint.host in ['localhost', '127.0.0.1'] for endpoint in endpoints)
    
    @pytest.mark.asyncio
    async def test_cloud_service_discovery(self, discovery_manager, mock_environment):
        """Test cloud service discovery"""
        os.environ['CLOUD_POSTGRES_URL'] = 'postgresql://user:pass@cloud-db:5432/prod'
        
        endpoints = await discovery_manager._discover_cloud_services("postgres", ServiceType.DATABASE)
        
        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert endpoint.host == "cloud-db"
        assert endpoint.port == 5432
    
    @pytest.mark.asyncio
    async def test_default_port_discovery(self, discovery_manager, mock_docker_env):
        """Test default port discovery fallback"""
        discovery_manager._env_info = mock_docker_env
        
        endpoints = await discovery_manager._discover_default_ports("postgres", ServiceType.DATABASE)
        
        assert len(endpoints) > 0
        # Should include default PostgreSQL port
        assert any(endpoint.port == 5432 for endpoint in endpoints)
        # Should include service name as host for containerized environment
        assert any(endpoint.host == "postgres" for endpoint in endpoints)
    
    @pytest.mark.asyncio
    async def test_tcp_connection_test(self, discovery_manager):
        """Test TCP connection testing"""
        # Test connection to a port that should be available (assuming nothing is running on 65432)
        result = await discovery_manager._test_tcp_connection("localhost", 65432, timeout=1.0)
        assert result is False
        
        # Test with a reasonable timeout that connection fails quickly
        start_time = time.time()
        result = await discovery_manager._test_tcp_connection("192.0.2.1", 80, timeout=1.0)  # Non-routable IP
        elapsed = time.time() - start_time
        assert result is False
        assert elapsed < 2.0  # Should timeout quickly
    
    @pytest.mark.asyncio
    async def test_database_connection_test(self, discovery_manager):
        """Test database connection testing"""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=5432,
            protocol="postgresql",
            username="test",
            password="test",
            database="test"
        )
        
        # Mock psycopg2 not being available
        with mock.patch('builtins.__import__') as mock_import:
            mock_import.side_effect = ImportError("psycopg2 not available")
            
            result = await discovery_manager._test_database_connection(endpoint)
            # Should assume available if can't test
            assert result is True
    
    @pytest.mark.asyncio
    async def test_redis_connection_test(self, discovery_manager):
        """Test Redis connection testing"""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=6379,
            protocol="redis"
        )
        
        # Mock redis library not being available
        with mock.patch('builtins.__import__') as mock_import:
            mock_import.side_effect = ImportError("redis not available")
            
            result = await discovery_manager._test_redis_connection(endpoint)
            # Should assume available if can't test
            assert result is True
    
    def test_url_parsing(self, discovery_manager):
        """Test URL parsing to endpoint"""
        url = "postgresql://user:pass@host:5432/database"
        endpoint = discovery_manager._parse_url_to_endpoint(url)
        
        assert endpoint is not None
        assert endpoint.host == "host"
        assert endpoint.port == 5432
        assert endpoint.protocol == "postgresql"
        assert endpoint.username == "user"
        assert endpoint.password == "pass"
        assert endpoint.database == "database"
    
    def test_url_parsing_invalid(self, discovery_manager):
        """Test URL parsing with invalid URLs"""
        invalid_urls = [
            "not-a-url",
            "http://host-without-port",
            "",
            None
        ]
        
        for url in invalid_urls:
            endpoint = discovery_manager._parse_url_to_endpoint(url) if url else None
            if endpoint:
                # If parsed, should have reasonable defaults
                assert endpoint.host is not None
            else:
                assert endpoint is None
    
    def test_default_ports_mapping(self, discovery_manager):
        """Test default port mappings for different service types"""
        # Test database ports
        db_ports = discovery_manager._get_default_ports(ServiceType.DATABASE)
        assert 5432 in db_ports  # PostgreSQL
        assert 3306 in db_ports  # MySQL
        
        # Test Redis ports
        redis_ports = discovery_manager._get_default_ports(ServiceType.REDIS)
        assert 6379 in redis_ports
        
        # Test API ports
        api_ports = discovery_manager._get_default_ports(ServiceType.API)
        assert 8000 in api_ports
        assert 8080 in api_ports
    
    def test_default_protocol_mapping(self, discovery_manager):
        """Test default protocol mappings for different service types"""
        assert discovery_manager._get_default_protocol(ServiceType.DATABASE) == "postgresql"
        assert discovery_manager._get_default_protocol(ServiceType.REDIS) == "redis"
        assert discovery_manager._get_default_protocol(ServiceType.API) == "http"
    
    @pytest.mark.asyncio
    async def test_service_discovery_full_flow(self, discovery_manager, mock_environment):
        """Test complete service discovery flow"""
        # Set up environment for successful discovery
        os.environ['POSTGRES_HOST'] = 'localhost'
        os.environ['POSTGRES_PORT'] = '5432'
        
        with mock.patch.object(discovery_manager, '_test_tcp_connection') as mock_tcp:
            mock_tcp.return_value = True
            
            with mock.patch.object(discovery_manager, '_test_database_connection') as mock_db:
                mock_db.return_value = True
                
                service_info = await discovery_manager.discover_service("postgres", ServiceType.DATABASE)
                
                assert service_info.name == "postgres"
                assert service_info.service_type == ServiceType.DATABASE
                assert service_info.status == ServiceStatus.AVAILABLE
                assert service_info.response_time_ms is not None
                assert service_info.last_checked is not None
    
    @pytest.mark.asyncio
    async def test_service_discovery_no_endpoints(self, discovery_manager, mock_environment):
        """Test service discovery when no endpoints are found"""
        # Don't set any environment variables
        
        with mock.patch.object(discovery_manager, '_test_tcp_connection') as mock_tcp:
            mock_tcp.return_value = False
            
            service_info = await discovery_manager.discover_service("nonexistent", ServiceType.DATABASE)
            
            assert service_info.name == "nonexistent"
            assert service_info.service_type == ServiceType.DATABASE
            assert service_info.status == ServiceStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_service_discovery_caching(self, discovery_manager, mock_environment):
        """Test service discovery caching mechanism"""
        os.environ['REDIS_HOST'] = 'localhost'
        os.environ['REDIS_PORT'] = '6379'
        
        with mock.patch.object(discovery_manager, '_test_tcp_connection') as mock_tcp:
            mock_tcp.return_value = True
            
            # First discovery
            service_info1 = await discovery_manager.discover_service("redis", ServiceType.REDIS)
            
            # Second discovery should use cache
            service_info2 = await discovery_manager.discover_service("redis", ServiceType.REDIS)
            
            # Should be the same cached object
            assert service_info1 is service_info2
            
            # Force refresh should create new discovery
            service_info3 = await discovery_manager.discover_service("redis", ServiceType.REDIS, force_refresh=True)
            
            # Should have same values but different object
            assert service_info1.name == service_info3.name
            assert service_info1 is not service_info3
    
    def test_cache_validity_check(self, discovery_manager):
        """Test cache validity checking"""
        endpoint = ServiceEndpoint(host="localhost", port=5432)
        
        # Create service info with recent timestamp
        service_info = ServiceInfo(
            name="test",
            service_type=ServiceType.DATABASE,
            endpoint=endpoint,
            status=ServiceStatus.AVAILABLE,
            last_checked=time.time()
        )
        
        assert discovery_manager._is_cache_valid(service_info) is True
        
        # Create service info with old timestamp
        service_info.last_checked = time.time() - 400  # Older than cache TTL
        assert discovery_manager._is_cache_valid(service_info) is False
        
        # Create service info with no timestamp
        service_info.last_checked = None
        assert discovery_manager._is_cache_valid(service_info) is False
    
    @pytest.mark.asyncio
    async def test_health_check_services(self, discovery_manager, mock_environment):
        """Test health checking of multiple services"""
        # Pre-populate cache
        endpoint1 = ServiceEndpoint(host="localhost", port=5432)
        service1 = ServiceInfo("postgres", ServiceType.DATABASE, endpoint1, ServiceStatus.AVAILABLE)
        discovery_manager._service_cache["postgres:database"] = service1
        
        endpoint2 = ServiceEndpoint(host="localhost", port=6379)
        service2 = ServiceInfo("redis", ServiceType.REDIS, endpoint2, ServiceStatus.AVAILABLE)
        discovery_manager._service_cache["redis:redis"] = service2
        
        with mock.patch.object(discovery_manager, 'discover_service') as mock_discover:
            mock_discover.side_effect = [service1, service2]
            
            results = await discovery_manager.health_check_services(["postgres:database", "redis:redis"])
            
            assert len(results) == 2
            assert "postgres:database" in results
            assert "redis:redis" in results
    
    def test_cache_management(self, discovery_manager):
        """Test cache clearing and info retrieval"""
        # Add something to cache
        endpoint = ServiceEndpoint(host="localhost", port=5432)
        service = ServiceInfo("test", ServiceType.DATABASE, endpoint, ServiceStatus.AVAILABLE)
        discovery_manager._service_cache["test:database"] = service
        
        # Check cache info
        cache_info = discovery_manager.get_cache_info()
        assert cache_info['cache_size'] == 1
        assert 'test:database' in cache_info['cached_services']
        
        # Clear cache
        discovery_manager.clear_cache()
        
        # Check cache is empty
        cache_info = discovery_manager.get_cache_info()
        assert cache_info['cache_size'] == 0
        assert cache_info['cached_services'] == []

class TestConvenienceFunctions:
    """Test convenience functions for service discovery"""
    
    @pytest.mark.asyncio
    async def test_discover_database_function(self):
        """Test global discover_database function"""
        with mock.patch.object(service_discovery, 'discover_service') as mock_discover:
            mock_endpoint = ServiceEndpoint(host="localhost", port=5432)
            mock_service = ServiceInfo("postgres", ServiceType.DATABASE, mock_endpoint, ServiceStatus.AVAILABLE)
            mock_discover.return_value = mock_service
            
            result = await discover_database()
            
            assert result == mock_service
            mock_discover.assert_called_once_with("postgres", ServiceType.DATABASE)
    
    @pytest.mark.asyncio
    async def test_discover_redis_function(self):
        """Test global discover_redis function"""
        with mock.patch.object(service_discovery, 'discover_service') as mock_discover:
            mock_endpoint = ServiceEndpoint(host="localhost", port=6379)
            mock_service = ServiceInfo("redis", ServiceType.REDIS, mock_endpoint, ServiceStatus.AVAILABLE)
            mock_discover.return_value = mock_service
            
            result = await discover_redis()
            
            assert result == mock_service
            mock_discover.assert_called_once_with("redis", ServiceType.REDIS)
    
    @pytest.mark.asyncio
    async def test_get_database_url_function(self):
        """Test get_database_url function"""
        with mock.patch.object(service_discovery, 'get_database_url') as mock_get_url:
            mock_get_url.return_value = "postgresql://localhost:5432/testdb"
            
            result = await get_database_url()
            
            assert result == "postgresql://localhost:5432/testdb"
            mock_get_url.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_redis_url_function(self):
        """Test get_redis_url function"""
        with mock.patch.object(service_discovery, 'get_redis_url') as mock_get_url:
            mock_get_url.return_value = "redis://localhost:6379"
            
            result = await get_redis_url()
            
            assert result == "redis://localhost:6379"
            mock_get_url.assert_called_once()

class TestErrorHandling:
    """Test error handling in service discovery"""
    
    @pytest.mark.asyncio
    async def test_discovery_strategy_failure_handling(self, discovery_manager):
        """Test handling of individual discovery strategy failures"""
        # Mock a strategy to fail
        original_method = discovery_manager._discover_environment_variables
        
        async def failing_method(*args):
            raise Exception("Test failure")
        
        discovery_manager._discover_environment_variables = failing_method
        
        # Discovery should still work with other strategies
        try:
            service_info = await discovery_manager.discover_service("test", ServiceType.DATABASE)
            assert isinstance(service_info, ServiceInfo)
        finally:
            # Restore original method
            discovery_manager._discover_environment_variables = original_method
    
    @pytest.mark.asyncio
    async def test_network_failure_handling(self, discovery_manager):
        """Test handling of network failures"""
        with mock.patch.object(discovery_manager, '_test_tcp_connection') as mock_tcp:
            mock_tcp.side_effect = Exception("Network error")
            
            service_info = await discovery_manager.discover_service("test", ServiceType.DATABASE)
            
            # Should handle network errors gracefully
            assert service_info.status == ServiceStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, discovery_manager):
        """Test handling of DNS resolution failures"""
        with mock.patch('socket.gethostbyname') as mock_dns:
            mock_dns.side_effect = socket.gaierror("DNS resolution failed")
            
            endpoints = await discovery_manager._discover_docker_services("nonexistent", ServiceType.DATABASE)
            
            # Should handle DNS failures gracefully and return empty list
            assert isinstance(endpoints, list)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])