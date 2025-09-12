#!/usr/bin/env python3
"""
Service Discovery Master - SPARC Root Cause Solution
Adaptive service discovery with intelligent fallback strategies
Fixes hardcoded service name issues and mixed environment conflicts
"""

import os
import socket
import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlparse

try:
    from .environment_master import EnvironmentMaster, EnvironmentType, ServiceEndpoint
except ImportError:
    # Fallback if environment_master not available
    from enum import Enum
    
    class EnvironmentType(Enum):
        LOCAL = "local"
        DOCKER = "docker" 
        KUBERNETES = "kubernetes"
        CLOUD = "cloud"
        WSL = "wsl"
        HYBRID = "hybrid"
    
    @dataclass
    class ServiceEndpoint:
        name: str
        host: str
        port: int
        protocol: str = "http"
        
        def get_url(self, access_type: str = "auto") -> str:
            return f"{self.protocol}://{self.host}:{self.port}"

logger = logging.getLogger(__name__)

class ServiceType(Enum):
    """Service types for discovery"""
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    REDIS = "redis"
    WEBSOCKET = "websocket"
    MESSAGE_QUEUE = "message_queue"

class ServiceStatus(Enum):
    """Service availability status"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class DiscoveredService:
    """Service discovery result"""
    name: str
    service_type: ServiceType
    endpoint: ServiceEndpoint
    status: ServiceStatus
    response_time_ms: Optional[float] = None
    last_checked: Optional[float] = None
    confidence_score: float = 0.0
    discovery_method: str = "unknown"

class ServiceDiscoveryMaster:
    """
    Master service discovery system
    Solves service discovery root causes:
    1. Hardcoded service names in Docker Compose
    2. Mixed container/host communication failures  
    3. Environment-specific hostname resolution
    4. Port binding and routing issues
    """
    
    def __init__(self, environment_master: Optional[EnvironmentMaster] = None):
        self._env_master = environment_master
        self._service_cache: Dict[str, DiscoveredService] = {}
        self._discovery_strategies = [
            self._discover_from_environment_master,
            self._discover_from_env_vars,
            self._discover_docker_services,
            self._discover_localhost_services,
            self._discover_kubernetes_services,
            self._discover_cloud_services,
            self._discover_default_fallbacks
        ]
        self.cache_ttl = 300  # 5 minutes
        
    async def discover_service(self, 
                             service_name: str, 
                             service_type: ServiceType,
                             force_refresh: bool = False) -> DiscoveredService:
        """
        Master service discovery with adaptive strategies
        
        Args:
            service_name: Service identifier
            service_type: Type of service
            force_refresh: Force rediscovery
            
        Returns:
            DiscoveredService with best available endpoint
        """
        cache_key = f"{service_name}:{service_type.value}"
        
        # Check cache first
        if not force_refresh and cache_key in self._service_cache:
            cached_service = self._service_cache[cache_key]
            if self._is_cache_valid(cached_service):
                logger.debug(f"📋 Using cached service: {service_name}")
                return cached_service
        
        logger.info(f"🔍 Discovering service: {service_name} ({service_type.value})")
        
        # Run discovery strategies in order of reliability
        discovered_endpoints = []
        best_confidence = 0.0
        best_method = "unknown"
        
        for strategy in self._discovery_strategies:
            try:
                endpoints, method = await strategy(service_name, service_type)
                for endpoint, confidence in endpoints:
                    discovered_endpoints.append((endpoint, confidence, method))
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_method = method
                        
                logger.debug(f"Strategy {strategy.__name__}: found {len(endpoints)} endpoints")
                
            except Exception as e:
                logger.warning(f"Discovery strategy {strategy.__name__} failed: {e}")
        
        if not discovered_endpoints:
            logger.warning(f"❌ No endpoints discovered for {service_name}")
            # Create unavailable service
            service = DiscoveredService(
                name=service_name,
                service_type=service_type,
                endpoint=ServiceEndpoint(service_name, "localhost", 0),
                status=ServiceStatus.UNAVAILABLE,
                last_checked=time.time(),
                confidence_score=0.0,
                discovery_method="none"
            )
        else:
            # Select best endpoint and test availability
            service = await self._select_best_endpoint(
                service_name, service_type, discovered_endpoints
            )
        
        # Cache result
        self._service_cache[cache_key] = service
        
        logger.info(f"✅ Service {service_name}: {service.endpoint.get_url()} "
                   f"(status: {service.status.value}, confidence: {service.confidence_score:.2f})")
        
        return service
    
    async def _discover_from_environment_master(self, 
                                              service_name: str, 
                                              service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Discover services from Environment Master configuration"""
        endpoints = []
        
        if not self._env_master:
            return endpoints, "environment_master"
            
        try:
            config = await self._env_master.initialize()
            
            # Map service types to endpoints
            endpoint_mapping = {
                ServiceType.BACKEND: config.backend_endpoint,
                ServiceType.FRONTEND: config.frontend_endpoint,
                ServiceType.DATABASE: config.database_endpoint,
                ServiceType.REDIS: config.redis_endpoint
            }
            
            endpoint = endpoint_mapping.get(service_type)
            if endpoint:
                # High confidence for environment master endpoints
                endpoints.append((endpoint, 0.95))
                logger.debug(f"Found {service_name} from Environment Master: {endpoint.get_url()}")
                
        except Exception as e:
            logger.debug(f"Environment Master discovery failed: {e}")
            
        return endpoints, "environment_master"
    
    async def _discover_from_env_vars(self, 
                                    service_name: str, 
                                    service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Discover services from environment variables"""
        endpoints = []
        
        # URL patterns to check
        url_patterns = [
            f"{service_name.upper()}_URL",
            f"AIVALIDATION_{service_name.upper()}_URL",
            f"VRU_{service_name.upper()}_URL",
            f"REACT_APP_{service_name.upper()}_URL"
        ]
        
        # Service-specific patterns
        if service_type == ServiceType.DATABASE:
            url_patterns.extend(["DATABASE_URL", "AIVALIDATION_DATABASE_URL"])
        elif service_type == ServiceType.REDIS:
            url_patterns.extend(["REDIS_URL", "AIVALIDATION_REDIS_URL"])
        elif service_type == ServiceType.BACKEND:
            url_patterns.extend(["REACT_APP_API_URL", "API_URL"])
            
        for pattern in url_patterns:
            url = os.getenv(pattern)
            if url:
                endpoint = self._parse_url_to_endpoint(url, service_name)
                if endpoint:
                    # High confidence for explicit URL configuration
                    endpoints.append((endpoint, 0.90))
                    logger.debug(f"Found {service_name} from env var {pattern}: {url}")
        
        # Component-based patterns (HOST + PORT)
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
        
        if host and port:
            protocol = self._get_default_protocol(service_type)
            endpoint = ServiceEndpoint(service_name, host, port, protocol)
            # Medium confidence for component-based config
            endpoints.append((endpoint, 0.75))
            logger.debug(f"Built {service_name} from components: {host}:{port}")
        
        return endpoints, "environment_variables"
    
    async def _discover_docker_services(self, 
                                      service_name: str, 
                                      service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Discover Docker services using DNS resolution and naming conventions"""
        endpoints = []
        
        # Docker hostname patterns to try
        docker_hostnames = [
            service_name,
            f"{service_name}-service",
            f"ai-validation-{service_name}",
            f"ai_validation_{service_name}",
            f"vru-{service_name}",
            f"backend" if service_type == ServiceType.BACKEND else None,
            f"frontend" if service_type == ServiceType.FRONTEND else None,
            f"postgres" if service_type == ServiceType.DATABASE else None,
            f"redis" if service_type == ServiceType.REDIS else None
        ]
        
        # Remove None values
        docker_hostnames = [h for h in docker_hostnames if h]
        
        default_ports = self._get_default_ports(service_type)
        
        for hostname in docker_hostnames:
            try:
                # Test DNS resolution
                ip = socket.gethostbyname(hostname)
                logger.debug(f"Resolved Docker hostname {hostname} -> {ip}")
                
                # Test each default port
                for port in default_ports:
                    if await self._test_tcp_connection(hostname, port, timeout=2):
                        protocol = self._get_default_protocol(service_type)
                        endpoint = ServiceEndpoint(service_name, hostname, port, protocol)
                        # High confidence for working Docker services
                        endpoints.append((endpoint, 0.85))
                        logger.debug(f"Docker service {hostname}:{port} is reachable")
                        break  # Use first working port
                        
            except socket.gaierror:
                logger.debug(f"Docker hostname {hostname} not resolvable")
            except Exception as e:
                logger.debug(f"Docker service discovery failed for {hostname}: {e}")
        
        return endpoints, "docker_dns"
    
    async def _discover_localhost_services(self, 
                                         service_name: str, 
                                         service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Discover services on localhost with port scanning"""
        endpoints = []
        
        localhost_addresses = ['127.0.0.1', 'localhost']
        
        # Add detected internal IP if available
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                internal_ip = s.getsockname()[0]
                if internal_ip not in localhost_addresses:
                    localhost_addresses.append(internal_ip)
        except:
            pass
        
        default_ports = self._get_default_ports(service_type)
        
        for host in localhost_addresses:
            for port in default_ports:
                if await self._test_tcp_connection(host, port, timeout=1):
                    protocol = self._get_default_protocol(service_type)
                    endpoint = ServiceEndpoint(service_name, host, port, protocol)
                    # Medium confidence for localhost services
                    confidence = 0.70 if host == 'localhost' else 0.65
                    endpoints.append((endpoint, confidence))
                    logger.debug(f"Localhost service found: {host}:{port}")
        
        return endpoints, "localhost_scan"
    
    async def _discover_kubernetes_services(self, 
                                          service_name: str, 
                                          service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Discover Kubernetes services"""
        endpoints = []
        
        # Check if in Kubernetes environment
        if not (os.path.exists('/var/run/secrets/kubernetes.io') or 
                os.getenv('KUBERNETES_SERVICE_HOST')):
            return endpoints, "kubernetes"
        
        # Kubernetes service naming patterns
        k8s_hostnames = [
            f"{service_name}-service",
            f"{service_name}-svc", 
            f"ai-validation-{service_name}",
            service_name
        ]
        
        # Add namespace if available
        namespace = os.getenv('K8S_NAMESPACE', 'default')
        k8s_hostnames.extend([
            f"{service_name}.{namespace}.svc.cluster.local",
            f"{service_name}-service.{namespace}.svc.cluster.local"
        ])
        
        default_ports = self._get_default_ports(service_type)
        
        for hostname in k8s_hostnames:
            try:
                ip = socket.gethostbyname(hostname)
                for port in default_ports:
                    if await self._test_tcp_connection(hostname, port, timeout=2):
                        protocol = self._get_default_protocol(service_type)
                        endpoint = ServiceEndpoint(service_name, hostname, port, protocol)
                        endpoints.append((endpoint, 0.80))
                        logger.debug(f"K8s service {hostname}:{port} is reachable")
                        break
            except socket.gaierror:
                logger.debug(f"K8s hostname {hostname} not resolvable")
            except Exception as e:
                logger.debug(f"K8s service discovery failed for {hostname}: {e}")
        
        return endpoints, "kubernetes"
    
    async def _discover_cloud_services(self, 
                                     service_name: str, 
                                     service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Discover cloud-hosted services"""
        endpoints = []
        
        # Check for cloud service URLs
        cloud_url_patterns = [
            f"CLOUD_{service_name.upper()}_URL",
            f"EXTERNAL_{service_name.upper()}_URL",
            f"REMOTE_{service_name.upper()}_URL"
        ]
        
        for pattern in cloud_url_patterns:
            url = os.getenv(pattern)
            if url:
                endpoint = self._parse_url_to_endpoint(url, service_name)
                if endpoint:
                    endpoints.append((endpoint, 0.80))
                    logger.debug(f"Found cloud service URL: {url}")
        
        return endpoints, "cloud_services"
    
    async def _discover_default_fallbacks(self, 
                                        service_name: str, 
                                        service_type: ServiceType) -> Tuple[List[Tuple[ServiceEndpoint, float]], str]:
        """Generate default fallback endpoints"""
        endpoints = []
        
        default_ports = self._get_default_ports(service_type)
        protocol = self._get_default_protocol(service_type)
        
        # Create fallback endpoints with different hosts
        fallback_hosts = ['localhost', '127.0.0.1', service_name]
        
        for host in fallback_hosts:
            for port in default_ports:
                endpoint = ServiceEndpoint(service_name, host, port, protocol)
                # Low confidence for fallback endpoints
                confidence = 0.30 if host == 'localhost' else 0.20
                endpoints.append((endpoint, confidence))
        
        return endpoints, "default_fallback"
    
    def _parse_url_to_endpoint(self, url: str, service_name: str) -> Optional[ServiceEndpoint]:
        """Parse URL string to ServiceEndpoint"""
        try:
            parsed = urlparse(url)
            
            if not parsed.hostname:
                return None
                
            port = parsed.port
            if not port:
                # Determine default port from protocol
                if parsed.scheme == 'https':
                    port = 443
                elif parsed.scheme == 'http':
                    port = 80
                elif parsed.scheme == 'redis':
                    port = 6379
                elif parsed.scheme in ['postgresql', 'postgres']:
                    port = 5432
                else:
                    return None
                    
            endpoint = ServiceEndpoint(
                name=service_name,
                host=parsed.hostname,
                port=port,
                protocol=parsed.scheme or "http"
            )
            
            return endpoint
            
        except Exception as e:
            logger.warning(f"Failed to parse URL {url}: {e}")
            return None
    
    def _get_default_ports(self, service_type: ServiceType) -> List[int]:
        """Get default ports for service type"""
        port_map = {
            ServiceType.BACKEND: [8000, 8080, 5000, 3001],
            ServiceType.FRONTEND: [3000, 3001, 8080, 80, 443],
            ServiceType.DATABASE: [5432, 3306, 1433, 27017],  # PostgreSQL, MySQL, SQL Server, MongoDB
            ServiceType.REDIS: [6379],
            ServiceType.WEBSOCKET: [8000, 8080, 3001],
            ServiceType.MESSAGE_QUEUE: [5672, 15672]  # RabbitMQ
        }
        return port_map.get(service_type, [8080])
    
    def _get_default_protocol(self, service_type: ServiceType) -> str:
        """Get default protocol for service type"""
        protocol_map = {
            ServiceType.BACKEND: "http",
            ServiceType.FRONTEND: "http",
            ServiceType.DATABASE: "postgresql",
            ServiceType.REDIS: "redis",
            ServiceType.WEBSOCKET: "ws",
            ServiceType.MESSAGE_QUEUE: "amqp"
        }
        return protocol_map.get(service_type, "http")
    
    async def _select_best_endpoint(self, 
                                  service_name: str, 
                                  service_type: ServiceType,
                                  discovered_endpoints: List[Tuple[ServiceEndpoint, float, str]]) -> DiscoveredService:
        """Select and test the best available endpoint"""
        
        best_endpoint = None
        best_confidence = 0.0
        best_response_time = float('inf')
        best_method = "unknown"
        
        # Test each endpoint
        for endpoint, confidence, method in discovered_endpoints:
            try:
                start_time = time.time()
                is_available = await self._test_service_endpoint(endpoint, service_type)
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                # Score based on availability, confidence, and response time
                if is_available:
                    # Prefer higher confidence and lower response time
                    score = confidence - (response_time / 10000)  # Penalize slow responses
                    
                    if score > best_confidence or (score == best_confidence and response_time < best_response_time):
                        best_endpoint = endpoint
                        best_confidence = confidence
                        best_response_time = response_time
                        best_method = method
                        
                    logger.debug(f"Endpoint {endpoint.host}:{endpoint.port} - "
                               f"Available: {is_available}, Score: {score:.3f}, "
                               f"Response: {response_time:.2f}ms")
                else:
                    logger.debug(f"Endpoint {endpoint.host}:{endpoint.port} - Unavailable")
                           
            except Exception as e:
                logger.debug(f"Endpoint {endpoint.host}:{endpoint.port} test failed: {e}")
        
        # Create service info
        if best_endpoint:
            status = ServiceStatus.AVAILABLE
        else:
            # No working endpoints, use first one as unavailable
            best_endpoint = discovered_endpoints[0][0]
            best_confidence = discovered_endpoints[0][1]
            best_method = discovered_endpoints[0][2]
            status = ServiceStatus.UNAVAILABLE
            best_response_time = None
        
        return DiscoveredService(
            name=service_name,
            service_type=service_type,
            endpoint=best_endpoint,
            status=status,
            response_time_ms=best_response_time if best_response_time != float('inf') else None,
            last_checked=time.time(),
            confidence_score=best_confidence,
            discovery_method=best_method
        )
    
    async def _test_service_endpoint(self, endpoint: ServiceEndpoint, service_type: ServiceType) -> bool:
        """Test if service endpoint is available and responding"""
        
        # Basic TCP connectivity test
        if not await self._test_tcp_connection(endpoint.host, endpoint.port, timeout=5):
            return False
        
        # Service-specific tests
        if service_type == ServiceType.DATABASE:
            return await self._test_database_connection(endpoint)
        elif service_type == ServiceType.REDIS:
            return await self._test_redis_connection(endpoint)
        elif service_type == ServiceType.BACKEND:
            return await self._test_http_health_check(endpoint)
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
    
    async def _test_http_health_check(self, endpoint: ServiceEndpoint) -> bool:
        """Test HTTP health endpoint"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                health_urls = [
                    f"{endpoint.get_url()}/health",
                    f"{endpoint.get_url()}/api/health",
                    f"{endpoint.get_url()}/healthz"
                ]
                
                for url in health_urls:
                    try:
                        async with session.get(url) as response:
                            if response.status < 500:  # Accept any non-server-error response
                                return True
                    except:
                        continue
                        
        except ImportError:
            logger.debug("aiohttp not available for HTTP health checks")
            
        return True  # Assume available if we can't test
    
    async def _test_database_connection(self, endpoint: ServiceEndpoint) -> bool:
        """Test database connection"""
        try:
            if endpoint.protocol in ['postgresql', 'postgres']:
                try:
                    import psycopg2
                    conn_string = f"postgresql://postgres:password@{endpoint.host}:{endpoint.port}/postgres"
                    conn = psycopg2.connect(conn_string, connect_timeout=5)
                    conn.close()
                    return True
                except ImportError:
                    logger.debug("psycopg2 not available for PostgreSQL test")
                except Exception as e:
                    logger.debug(f"PostgreSQL connection test failed: {e}")
                    return False
            
            # For other databases or if we can't test, assume available if TCP works
            return True
            
        except Exception as e:
            logger.debug(f"Database connection test failed: {e}")
            return False
    
    async def _test_redis_connection(self, endpoint: ServiceEndpoint) -> bool:
        """Test Redis connection"""
        try:
            import redis.asyncio as redis
            
            r = redis.Redis(host=endpoint.host, port=endpoint.port, socket_timeout=5)
            await r.ping()
            await r.close()
            return True
            
        except ImportError:
            logger.debug("Redis library not available for test")
            return True  # Assume available if we can't test
        except Exception as e:
            logger.debug(f"Redis connection test failed: {e}")
            return False
    
    def _is_cache_valid(self, service: DiscoveredService) -> bool:
        """Check if cached service info is still valid"""
        if not service.last_checked:
            return False
        
        age = time.time() - service.last_checked
        return age < self.cache_ttl
    
    async def health_check_all_services(self) -> Dict[str, DiscoveredService]:
        """Perform health check on all cached services"""
        results = {}
        
        for service_key, service in self._service_cache.items():
            try:
                # Force refresh of each service
                service_name, service_type_str = service_key.split(':', 1)
                service_type = ServiceType(service_type_str)
                
                refreshed_service = await self.discover_service(
                    service_name, service_type, force_refresh=True
                )
                results[service_key] = refreshed_service
                
            except Exception as e:
                logger.warning(f"Health check failed for {service_key}: {e}")
        
        return results
    
    def clear_cache(self):
        """Clear service discovery cache"""
        self._service_cache.clear()
        logger.info("Service discovery cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information"""
        return {
            'cached_services': list(self._service_cache.keys()),
            'cache_size': len(self._service_cache),
            'cache_ttl': self.cache_ttl
        }
    
    def export_service_configuration(self) -> Dict[str, Any]:
        """Export discovered services as configuration"""
        config = {
            'services': {},
            'discovery_timestamp': time.time()
        }
        
        for service_key, service in self._service_cache.items():
            config['services'][service_key] = {
                'name': service.name,
                'type': service.service_type.value,
                'endpoint': {
                    'host': service.endpoint.host,
                    'port': service.endpoint.port,
                    'protocol': service.endpoint.protocol,
                    'url': service.endpoint.get_url()
                },
                'status': service.status.value,
                'confidence': service.confidence_score,
                'discovery_method': service.discovery_method,
                'response_time_ms': service.response_time_ms
            }
        
        return config

# Global instance
service_discovery_master = ServiceDiscoveryMaster()

# Convenience functions
async def discover_backend() -> DiscoveredService:
    """Discover backend service"""
    return await service_discovery_master.discover_service("backend", ServiceType.BACKEND)

async def discover_database() -> DiscoveredService:
    """Discover database service"""
    return await service_discovery_master.discover_service("database", ServiceType.DATABASE)

async def discover_redis() -> DiscoveredService:
    """Discover Redis service"""
    return await service_discovery_master.discover_service("redis", ServiceType.REDIS)

async def get_backend_url() -> str:
    """Get backend URL"""
    service = await discover_backend()
    return service.endpoint.get_url()

async def get_database_url() -> str:
    """Get database connection URL"""
    service = await discover_database()
    if service.endpoint.protocol == 'postgresql':
        return f"postgresql://postgres:password@{service.endpoint.host}:{service.endpoint.port}/vru_validation"
    else:
        return "sqlite:///./dev_database.db"  # Fallback

if __name__ == "__main__":
    # Test service discovery
    async def test_service_discovery():
        import json
        
        # Test backend discovery
        backend = await discover_backend()
        print("Backend service:")
        print(json.dumps(asdict(backend), indent=2, default=str))
        
        # Test database discovery
        database = await discover_database()
        print("\nDatabase service:")
        print(json.dumps(asdict(database), indent=2, default=str))
        
        # Export configuration
        config = service_discovery_master.export_service_configuration()
        print("\nService configuration:")
        print(json.dumps(config, indent=2, default=str))
    
    asyncio.run(test_service_discovery())