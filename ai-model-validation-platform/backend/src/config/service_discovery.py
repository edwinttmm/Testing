#!/usr/bin/env python3
"""
ServiceDiscoveryManager - SPARC Architecture Component
Adaptive endpoint resolution with intelligent fallback strategies
Solves hardcoded service name issues in mixed environments
"""

import os
import socket
import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlparse
import subprocess

from .environment_detector import detect_environment, EnvironmentType, ServiceMode

logger = logging.getLogger(__name__)

class ServiceType(Enum):
    """Types of services that can be discovered"""
    DATABASE = "database"
    REDIS = "redis"
    API = "api"
    WEB = "web"
    MESSAGE_QUEUE = "message_queue"

class ServiceStatus(Enum):
    """Service availability status"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class ServiceEndpoint:
    """Service endpoint information"""
    host: str
    port: int
    protocol: str = "http"
    path: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    
    def to_url(self) -> str:
        """Convert to complete URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        elif self.username:
            auth = f"{self.username}@"
        elif self.password and self.protocol == "redis":
            # Redis password-only authentication format
            auth = f":{self.password}@"
            
        path = self.path.rstrip('/') if self.path else ""
        database_suffix = f"/{self.database}" if self.database else ""
        
        return f"{self.protocol}://{auth}{self.host}:{self.port}{path}{database_suffix}"
    
    def to_connection_string(self) -> str:
        """Convert to connection string (for databases)"""
        if self.database:
            # PostgreSQL/MySQL style
            auth = ""
            if self.username and self.password:
                auth = f"{self.username}:{self.password}@"
            return f"postgresql://{auth}{self.host}:{self.port}/{self.database}"
        else:
            return self.to_url()

@dataclass
class ServiceInfo:
    """Complete service information"""
    name: str
    service_type: ServiceType
    endpoint: ServiceEndpoint
    status: ServiceStatus
    response_time_ms: Optional[float] = None
    last_checked: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ServiceDiscoveryManager:
    """
    Intelligent service discovery with adaptive endpoint resolution
    Handles Docker service names, localhost fallbacks, and cloud endpoints
    """
    
    def __init__(self):
        self._service_cache: Dict[str, ServiceInfo] = {}
        self._discovery_strategies = [
            self._discover_environment_variables,
            self._discover_docker_services,
            self._discover_localhost_services,
            self._discover_cloud_services,
            self._discover_default_ports
        ]
        self._env_info = detect_environment()
        self.cache_ttl = 300  # 5 minutes
        
    async def discover_service(self, 
                             service_name: str, 
                             service_type: ServiceType,
                             force_refresh: bool = False) -> ServiceInfo:
        """
        Discover a service using multiple strategies
        
        Args:
            service_name: Name of the service (e.g., 'postgres', 'redis')
            service_type: Type of service
            force_refresh: Force re-discovery instead of using cache
            
        Returns:
            ServiceInfo with discovered endpoint and status
        """
        cache_key = f"{service_name}:{service_type.value}"
        
        # Check cache first
        if not force_refresh and cache_key in self._service_cache:
            cached_service = self._service_cache[cache_key]
            if self._is_cache_valid(cached_service):
                logger.debug(f"Using cached service info for {service_name}")
                return cached_service
        
        logger.info(f"🔍 Discovering service: {service_name} ({service_type.value})")
        
        # Try each discovery strategy
        discovered_endpoints = []
        
        for strategy in self._discovery_strategies:
            try:
                endpoints = await strategy(service_name, service_type)
                discovered_endpoints.extend(endpoints)
                logger.debug(f"Strategy {strategy.__name__} found {len(endpoints)} endpoints")
            except Exception as e:
                logger.warning(f"Discovery strategy {strategy.__name__} failed: {e}")
        
        if not discovered_endpoints:
            logger.warning(f"No endpoints discovered for {service_name}")
            # Create unavailable service info
            service_info = ServiceInfo(
                name=service_name,
                service_type=service_type,
                endpoint=ServiceEndpoint(host="localhost", port=0),
                status=ServiceStatus.UNAVAILABLE,
                last_checked=time.time()
            )
        else:
            # Test endpoints and select the best one
            service_info = await self._select_best_endpoint(
                service_name, service_type, discovered_endpoints
            )
        
        # Cache the result
        self._service_cache[cache_key] = service_info
        
        logger.info(f"✅ Service {service_name} discovered: {service_info.endpoint.to_url()} "
                   f"(status: {service_info.status.value})")
        
        return service_info
    
    async def _discover_environment_variables(self, 
                                           service_name: str, 
                                           service_type: ServiceType) -> List[ServiceEndpoint]:
        """Discover services from environment variables"""
        endpoints = []
        
        # Standard URL patterns
        url_patterns = [
            f"{service_name.upper()}_URL",
            f"AIVALIDATION_{service_name.upper()}_URL",
            f"{service_name.upper()}_CONNECTION_STRING",
            f"DATABASE_URL" if service_type == ServiceType.DATABASE else None,
            f"REDIS_URL" if service_type == ServiceType.REDIS else None
        ]
        
        for pattern in url_patterns:
            if pattern and os.getenv(pattern):
                url = os.getenv(pattern)
                endpoint = self._parse_url_to_endpoint(url)
                if endpoint:
                    endpoints.append(endpoint)
                    logger.debug(f"Found {service_name} URL in {pattern}: {url}")
        
        # Individual component patterns
        host_patterns = [
            f"{service_name.upper()}_HOST",
            f"AIVALIDATION_{service_name.upper()}_HOST"
        ]
        
        port_patterns = [
            f"{service_name.upper()}_PORT", 
            f"AIVALIDATION_{service_name.upper()}_PORT"
        ]
        
        host = None
        port = None
        
        for pattern in host_patterns:
            if os.getenv(pattern):
                host = os.getenv(pattern)
                break
                
        for pattern in port_patterns:
            if os.getenv(pattern):
                try:
                    port = int(os.getenv(pattern))
                    break
                except ValueError:
                    pass
        
        # Build endpoint from components
        if host and port:
            protocol = self._get_default_protocol(service_type)
            endpoint = ServiceEndpoint(host=host, port=port, protocol=protocol)
            
            # Add database name if applicable
            if service_type == ServiceType.DATABASE:
                db_name = os.getenv(f"{service_name.upper()}_DB") or os.getenv("DATABASE_NAME")
                if db_name:
                    endpoint.database = db_name
                    
            # Add credentials
            username = os.getenv(f"{service_name.upper()}_USER") or os.getenv(f"{service_name.upper()}_USERNAME")
            password = os.getenv(f"{service_name.upper()}_PASSWORD") or os.getenv(f"{service_name.upper()}_PASS")
            
            if username:
                endpoint.username = username
            if password:
                endpoint.password = password
                
            endpoints.append(endpoint)
            logger.debug(f"Built {service_name} endpoint from components: {host}:{port}")
        
        return endpoints
    
    async def _discover_docker_services(self, 
                                      service_name: str, 
                                      service_type: ServiceType) -> List[ServiceEndpoint]:
        """Discover Docker services using DNS resolution"""
        endpoints = []
        
        # Only try Docker service discovery in containerized environments
        if not self._env_info.is_containerized:
            return endpoints
        
        docker_hostnames = [
            service_name,
            f"{service_name}-service",
            f"ai-validation-{service_name}",
            f"vru-{service_name}",
            f"backend-{service_name}"
        ]
        
        default_ports = self._get_default_ports(service_type)
        
        for hostname in docker_hostnames:
            try:
                # Test DNS resolution
                ip = socket.gethostbyname(hostname)
                logger.debug(f"Resolved Docker hostname {hostname} -> {ip}")
                
                # Try each default port
                for port in default_ports:
                    if await self._test_tcp_connection(hostname, port, timeout=2):
                        protocol = self._get_default_protocol(service_type)
                        endpoint = ServiceEndpoint(host=hostname, port=port, protocol=protocol)
                        endpoints.append(endpoint)
                        logger.debug(f"Docker service {hostname}:{port} is reachable")
                        break  # Use first working port
                        
            except socket.gaierror:
                logger.debug(f"Docker hostname {hostname} not resolvable")
            except Exception as e:
                logger.debug(f"Docker service discovery failed for {hostname}: {e}")
        
        return endpoints
    
    async def _discover_localhost_services(self, 
                                         service_name: str, 
                                         service_type: ServiceType) -> List[ServiceEndpoint]:
        """Discover services on localhost"""
        endpoints = []
        
        localhost_addresses = ['127.0.0.1', 'localhost']
        if self._env_info.network_info.get('local_ip'):
            localhost_addresses.append(self._env_info.network_info['local_ip'])
        
        default_ports = self._get_default_ports(service_type)
        
        for host in localhost_addresses:
            for port in default_ports:
                if await self._test_tcp_connection(host, port, timeout=1):
                    protocol = self._get_default_protocol(service_type)
                    endpoint = ServiceEndpoint(host=host, port=port, protocol=protocol)
                    endpoints.append(endpoint)
                    logger.debug(f"Localhost service found: {host}:{port}")
        
        return endpoints
    
    async def _discover_cloud_services(self, 
                                     service_name: str, 
                                     service_type: ServiceType) -> List[ServiceEndpoint]:
        """Discover cloud-based services"""
        endpoints = []
        
        # Check for cloud service URLs
        cloud_url_patterns = [
            f"CLOUD_{service_name.upper()}_URL",
            f"EXTERNAL_{service_name.upper()}_URL",
            f"REMOTE_{service_name.upper()}_URL"
        ]
        
        for pattern in cloud_url_patterns:
            if os.getenv(pattern):
                url = os.getenv(pattern)
                endpoint = self._parse_url_to_endpoint(url)
                if endpoint:
                    endpoints.append(endpoint)
                    logger.debug(f"Found cloud service URL: {url}")
        
        return endpoints
    
    async def _discover_default_ports(self, 
                                    service_name: str, 
                                    service_type: ServiceType) -> List[ServiceEndpoint]:
        """Fallback: create endpoints with default configurations"""
        endpoints = []
        
        default_ports = self._get_default_ports(service_type)
        protocol = self._get_default_protocol(service_type)
        
        # Try common host patterns
        if self._env_info.is_containerized:
            hosts = [service_name, 'localhost', '127.0.0.1']
        else:
            hosts = ['localhost', '127.0.0.1']
        
        for host in hosts:
            for port in default_ports:
                endpoint = ServiceEndpoint(host=host, port=port, protocol=protocol)
                endpoints.append(endpoint)
        
        logger.debug(f"Generated {len(endpoints)} default endpoints for {service_name}")
        return endpoints
    
    async def _select_best_endpoint(self, 
                                  service_name: str, 
                                  service_type: ServiceType, 
                                  endpoints: List[ServiceEndpoint]) -> ServiceInfo:
        """Test endpoints and select the best available one"""
        
        best_endpoint = None
        best_response_time = float('inf')
        
        # Test each endpoint
        for endpoint in endpoints:
            try:
                start_time = time.time()
                is_available = await self._test_service_endpoint(endpoint, service_type)
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                if is_available and response_time < best_response_time:
                    best_endpoint = endpoint
                    best_response_time = response_time
                    
                logger.debug(f"Endpoint {endpoint.host}:{endpoint.port} - "
                           f"Available: {is_available}, Response time: {response_time:.2f}ms")
                           
            except Exception as e:
                logger.debug(f"Endpoint {endpoint.host}:{endpoint.port} test failed: {e}")
        
        # Create service info
        if best_endpoint:
            return ServiceInfo(
                name=service_name,
                service_type=service_type,
                endpoint=best_endpoint,
                status=ServiceStatus.AVAILABLE,
                response_time_ms=best_response_time,
                last_checked=time.time()
            )
        else:
            # No working endpoints found, return the first one as unavailable
            return ServiceInfo(
                name=service_name,
                service_type=service_type,
                endpoint=endpoints[0] if endpoints else ServiceEndpoint(host="localhost", port=0),
                status=ServiceStatus.UNAVAILABLE,
                last_checked=time.time()
            )
    
    async def _test_service_endpoint(self, endpoint: ServiceEndpoint, service_type: ServiceType) -> bool:
        """Test if a service endpoint is available and responding"""
        
        # Basic TCP connectivity test
        if not await self._test_tcp_connection(endpoint.host, endpoint.port, timeout=5):
            return False
        
        # Service-specific tests
        if service_type == ServiceType.DATABASE:
            return await self._test_database_connection(endpoint)
        elif service_type == ServiceType.REDIS:
            return await self._test_redis_connection(endpoint)
        else:
            # For other services, TCP connectivity is sufficient
            return True
    
    async def _test_tcp_connection(self, host: str, port: int, timeout: float = 5.0) -> bool:
        """Test TCP connectivity to host:port"""
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False
    
    async def _test_database_connection(self, endpoint: ServiceEndpoint) -> bool:
        """Test database connection"""
        try:
            # Try to import database libraries
            if endpoint.protocol in ['postgresql', 'postgres']:
                try:
                    import psycopg2
                    conn_string = endpoint.to_connection_string()
                    conn = psycopg2.connect(conn_string, connect_timeout=5)
                    conn.close()
                    return True
                except ImportError:
                    logger.debug("psycopg2 not available for PostgreSQL test")
                    return True  # Assume available if we can't test
                except Exception as e:
                    logger.debug(f"PostgreSQL connection test failed: {e}")
                    return False
            
            # For SQLite or other databases, assume available if TCP test passed
            return True
            
        except Exception as e:
            logger.debug(f"Database connection test failed: {e}")
            return False
    
    async def _test_redis_connection(self, endpoint: ServiceEndpoint) -> bool:
        """Test Redis connection"""
        try:
            import redis
            redis_url = endpoint.to_url()
            r = redis.from_url(redis_url, socket_timeout=5)
            r.ping()
            return True
        except ImportError:
            logger.debug("Redis library not available for test")
            return True  # Assume available if we can't test
        except Exception as e:
            logger.debug(f"Redis connection test failed: {e}")
            return False
    
    def _parse_url_to_endpoint(self, url: str) -> Optional[ServiceEndpoint]:
        """Parse URL string to ServiceEndpoint"""
        try:
            parsed = urlparse(url)
            
            if not parsed.hostname or not parsed.port:
                return None
                
            endpoint = ServiceEndpoint(
                host=parsed.hostname,
                port=parsed.port,
                protocol=parsed.scheme or "http",
                path=parsed.path or "",
                username=parsed.username,
                password=parsed.password
            )
            
            # Extract database name from path for database URLs
            if parsed.path and parsed.path.startswith('/'):
                potential_db = parsed.path[1:]  # Remove leading slash
                if potential_db and '/' not in potential_db:  # Simple database name
                    endpoint.database = potential_db
                    endpoint.path = ""  # Clear path since it's the database name
            
            return endpoint
            
        except Exception as e:
            logger.warning(f"Failed to parse URL {url}: {e}")
            return None
    
    def _get_default_ports(self, service_type: ServiceType) -> List[int]:
        """Get default ports for service type"""
        port_map = {
            ServiceType.DATABASE: [5432, 3306, 1433, 27017],  # PostgreSQL, MySQL, SQL Server, MongoDB
            ServiceType.REDIS: [6379],
            ServiceType.API: [8000, 8080, 3000, 5000],
            ServiceType.WEB: [3000, 8080, 80, 443],
            ServiceType.MESSAGE_QUEUE: [5672, 15672]  # RabbitMQ
        }
        return port_map.get(service_type, [8080])
    
    def _get_default_protocol(self, service_type: ServiceType) -> str:
        """Get default protocol for service type"""
        protocol_map = {
            ServiceType.DATABASE: "postgresql",
            ServiceType.REDIS: "redis",
            ServiceType.API: "http",
            ServiceType.WEB: "http",
            ServiceType.MESSAGE_QUEUE: "amqp"
        }
        return protocol_map.get(service_type, "http")
    
    def _is_cache_valid(self, service_info: ServiceInfo) -> bool:
        """Check if cached service info is still valid"""
        if not service_info.last_checked:
            return False
        
        age = time.time() - service_info.last_checked
        return age < self.cache_ttl
    
    async def get_database_url(self, service_name: str = "postgres") -> str:
        """Get database connection URL"""
        service_info = await self.discover_service(service_name, ServiceType.DATABASE)
        return service_info.endpoint.to_connection_string()
    
    async def get_redis_url(self, service_name: str = "redis") -> str:
        """Get Redis connection URL"""
        service_info = await self.discover_service(service_name, ServiceType.REDIS)
        return service_info.endpoint.to_url()
    
    async def get_api_url(self, service_name: str = "api") -> str:
        """Get API base URL"""
        service_info = await self.discover_service(service_name, ServiceType.API)
        return service_info.endpoint.to_url()
    
    async def health_check_services(self, service_names: List[str] = None) -> Dict[str, ServiceInfo]:
        """Perform health check on all or specified services"""
        if service_names is None:
            service_names = list(self._service_cache.keys())
        
        results = {}
        
        for service_key in service_names:
            if ':' in service_key:
                service_name, service_type_str = service_key.split(':', 1)
                try:
                    service_type = ServiceType(service_type_str)
                    service_info = await self.discover_service(service_name, service_type, force_refresh=True)
                    results[service_key] = service_info
                except ValueError:
                    logger.warning(f"Unknown service type in key: {service_key}")
            
        return results
    
    def clear_cache(self):
        """Clear the service discovery cache"""
        self._service_cache.clear()
        logger.info("Service discovery cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the current cache state"""
        return {
            'cached_services': list(self._service_cache.keys()),
            'cache_size': len(self._service_cache),
            'cache_ttl': self.cache_ttl,
            'environment_type': self._env_info.environment_type.value
        }

# Global service discovery manager
service_discovery = ServiceDiscoveryManager()

# Convenience functions
async def discover_database() -> ServiceInfo:
    """Discover database service"""
    return await service_discovery.discover_service("postgres", ServiceType.DATABASE)

async def discover_redis() -> ServiceInfo:
    """Discover Redis service"""
    return await service_discovery.discover_service("redis", ServiceType.REDIS)

async def get_database_url() -> str:
    """Get database connection URL"""
    return await service_discovery.get_database_url()

async def get_redis_url() -> str:
    """Get Redis connection URL"""
    return await service_discovery.get_redis_url()

if __name__ == "__main__":
    # Test the service discovery
    async def test_discovery():
        import json
        
        # Test database discovery
        db_service = await discover_database()
        print("Database service:")
        print(json.dumps(asdict(db_service), indent=2, default=str))
        
        # Test Redis discovery
        redis_service = await discover_redis()
        print("\nRedis service:")
        print(json.dumps(asdict(redis_service), indent=2, default=str))
        
        # Test cache info
        cache_info = service_discovery.get_cache_info()
        print("\nCache info:")
        print(json.dumps(cache_info, indent=2))
    
    asyncio.run(test_discovery())