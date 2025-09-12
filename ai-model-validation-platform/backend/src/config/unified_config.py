"""
Unified Configuration System - Backend Implementation
Automatically detects environment and configures CORS, API endpoints, and security
Part of the SPARC Unified Configuration Architecture
"""

from typing import List, Dict, Any, Optional, Union
import os
import json
import socket
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse
import ipaddress

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class NetworkInfo:
    """Network configuration information"""
    internal_ip: str
    external_ip: Optional[str] = None
    hostname: str = "localhost"
    docker_network: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)

@dataclass 
class APIConfiguration:
    """API service configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = ""
    timeout: int = 30
    max_retries: int = 3
    workers: int = 1

@dataclass
class CORSConfiguration:
    """CORS configuration with auto-detection"""
    origins: List[str] = field(default_factory=list)
    credentials: bool = True
    methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    headers: List[str] = field(default_factory=lambda: ["*"])
    max_age: int = 3600
    auto_detect: bool = True

@dataclass
class SecurityConfiguration:
    """Security configuration"""
    ssl_enabled: bool = False
    security_headers_enabled: bool = True
    csp_enabled: bool = False
    hsts_enabled: bool = False
    secret_key: str = "REPLACE-ME-IN-PRODUCTION"
    allowed_hosts: List[str] = field(default_factory=list)

@dataclass
class FeatureConfiguration:
    """Feature flags and toggles"""
    debug_mode: bool = False
    monitoring_enabled: bool = False
    analytics_enabled: bool = False
    caching_enabled: bool = True
    async_processing: bool = False
    rate_limiting: bool = True

@dataclass
class LoggingConfiguration:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5
    structured: bool = False

@dataclass
class UnifiedConfig:
    """Complete unified configuration"""
    # Environment detection
    environment: str = "development"  # development, staging, production
    platform: str = "local"          # local, docker, cloud
    
    # Network and infrastructure
    network: NetworkInfo = field(default_factory=lambda: NetworkInfo("127.0.0.1"))
    
    # Service configurations
    api: APIConfiguration = field(default_factory=APIConfiguration)
    cors: CORSConfiguration = field(default_factory=CORSConfiguration) 
    security: SecurityConfiguration = field(default_factory=SecurityConfiguration)
    features: FeatureConfiguration = field(default_factory=FeatureConfiguration)
    logging: LoggingConfiguration = field(default_factory=LoggingConfiguration)
    
    # Metadata
    created_at: Optional[str] = None
    config_version: str = "1.0.0"

class ConfigurationManager:
    """Unified configuration manager with auto-detection"""
    
    def __init__(self):
        self._config: Optional[UnifiedConfig] = None
        self._network_info: Optional[NetworkInfo] = None
        self._validation_errors: List[str] = []
        
    async def initialize(self) -> UnifiedConfig:
        """Initialize unified configuration with environment detection."""
        if self._config:
            return self._config
        
        logger.info("🔧 Initializing unified configuration system...")
        
        try:
            # Step 1: Detect environment and platform
            logger.info("📍 Step 1: Environment detection")
            environment = self._detect_environment()
            platform = self._detect_platform()
            
            # Step 2: Detect network configuration
            logger.info("🌐 Step 2: Network detection")
            network_info = await self._detect_network()
            
            # Step 3: Load configuration hierarchy
            logger.info("📚 Step 3: Configuration hierarchy loading")
            config_data = await self._load_configuration_hierarchy(environment, platform)
            
            # Step 4: Create unified configuration
            logger.info("🔀 Step 4: Configuration merging")
            
            # Convert dict configs to dataclass instances
            api_config = APIConfiguration(**config_data.get('api', {}))
            cors_config = CORSConfiguration(**config_data.get('cors', {}))
            security_config = SecurityConfiguration(**config_data.get('security', {}))
            features_config = FeatureConfiguration(**config_data.get('features', {}))
            logging_config = LoggingConfiguration(**config_data.get('logging', {}))
            
            self._config = UnifiedConfig(
                environment=environment,
                platform=platform,
                network=network_info,
                api=api_config,
                cors=cors_config,
                security=security_config,
                features=features_config,
                logging=logging_config
            )
            
            # Step 5: Generate dynamic configurations
            logger.info("⚙️  Step 5: Dynamic configuration generation")
            await self._generate_dynamic_config()
            
            # Step 6: Validate configuration
            logger.info("✅ Step 6: Configuration validation")
            await self._validate_configuration()
            
            # Step 7: Set metadata
            from datetime import datetime
            self._config.created_at = datetime.utcnow().isoformat()
            
            logger.info("✅ Configuration system initialized successfully")
            self._log_configuration_summary()
            
            return self._config
            
        except Exception as e:
            logger.error(f"❌ Configuration initialization failed: {e}")
            raise
    
    def _detect_environment(self) -> str:
        """Detect current environment type."""
        # Check environment variables in order of specificity
        env_indicators = [
            os.getenv('AIVALIDATION_APP_ENVIRONMENT'),
            os.getenv('APP_ENV'),
            os.getenv('ENVIRONMENT'), 
            os.getenv('NODE_ENV'),
            os.getenv('FLASK_ENV'),
            os.getenv('DJANGO_SETTINGS_MODULE')
        ]
        
        for env in env_indicators:
            if env:
                env_lower = env.lower()
                if env_lower in ['production', 'prod']:
                    return 'production'
                elif env_lower in ['staging', 'stage', 'test']:
                    return 'staging'
                elif env_lower in ['development', 'dev', 'local']:
                    return 'development'
        
        # Auto-detect based on other indicators
        if self._is_production_environment():
            return 'production'
        elif self._is_staging_environment():
            return 'staging'
            
        return 'development'
    
    def _is_production_environment(self) -> bool:
        """Check for production environment indicators."""
        return any([
            os.getenv('DEBUG', '').lower() == 'false',
            os.getenv('SSL_ENABLED', '').lower() == 'true',
            os.getenv('MONITORING_ENABLED', '').lower() == 'true',
            os.getenv('PRODUCTION', '').lower() == 'true'
        ])
    
    def _is_staging_environment(self) -> bool:
        """Check for staging environment indicators.""" 
        return any([
            os.getenv('STAGING', '').lower() == 'true',
            'staging' in os.getenv('HOSTNAME', '').lower(),
            'staging' in os.getenv('API_HOST', '').lower()
        ])
    
    def _detect_platform(self) -> str:
        """Detect deployment platform."""
        # Check for Docker
        docker_indicators = [
            os.getenv('DOCKER') == 'true',
            os.path.exists('/.dockerenv'),
            'docker' in os.getenv('HOSTNAME', '').lower(),
            os.getenv('CONTAINER_NAME') is not None
        ]
        
        if any(docker_indicators):
            return 'docker'
        
        # Check for Kubernetes
        k8s_indicators = [
            os.getenv('KUBERNETES_SERVICE_HOST'),
            os.getenv('K8S_NAMESPACE'), 
            os.path.exists('/var/run/secrets/kubernetes.io')
        ]
        
        if any(k8s_indicators):
            return 'cloud'
        
        # Check for cloud providers
        cloud_indicators = [
            os.getenv('AWS_REGION'),
            os.getenv('GOOGLE_CLOUD_PROJECT'),
            os.getenv('AZURE_RESOURCE_GROUP'),
            os.getenv('CLOUD_PROVIDER')
        ]
        
        if any(cloud_indicators):
            return 'cloud'
            
        return 'local'
    
    async def _detect_network(self) -> NetworkInfo:
        """Detect network configuration."""
        internal_ip = self._get_internal_ip()
        external_ip = await self._get_external_ip()
        hostname = self._get_hostname()
        docker_network = self._detect_docker_network()
        interfaces = self._get_network_interfaces()
        
        return NetworkInfo(
            internal_ip=internal_ip,
            external_ip=external_ip,
            hostname=hostname,
            docker_network=docker_network,
            interfaces=interfaces
        )
    
    def _get_internal_ip(self) -> str:
        """Get internal IP address."""
        try:
            # Connect to external address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            # Fallback to localhost
            return "127.0.0.1"
    
    async def _get_external_ip(self) -> Optional[str]:
        """Get external IP address with multiple fallback strategies."""
        # Check configured external IP first
        configured_ips = [
            os.getenv('EXTERNAL_IP'),
            os.getenv('PUBLIC_IP'),
            os.getenv('SERVER_IP'),
            os.getenv('AIVALIDATION_EXTERNAL_IP')
        ]
        
        for ip in configured_ips:
            if ip and self._is_valid_ip(ip):
                logger.info(f"📍 Using configured external IP: {ip}")
                return ip
        
        # Auto-detect external IP if requests is available
        if REQUESTS_AVAILABLE:
            return await self._auto_detect_external_ip()
        
        logger.warning("⚠️ Requests library not available for external IP detection")
        return None
    
    async def _auto_detect_external_ip(self) -> Optional[str]:
        """Auto-detect external IP using multiple services."""
        ip_services = [
            'https://api.ipify.org?format=json',
            'https://httpbin.org/ip', 
            'https://ipinfo.io/json',
            'https://api.myip.com'
        ]
        
        for service in ip_services:
            try:
                logger.debug(f"🌐 Trying IP detection service: {service}")
                
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Different services return IP in different formats
                    ip = data.get('ip') or data.get('origin', '').split(' ')[0] or data
                    
                    if isinstance(ip, str) and self._is_valid_ip(ip):
                        logger.info(f"📍 Auto-detected external IP: {ip}")
                        return ip
                        
            except Exception as e:
                logger.debug(f"Service {service} failed: {e}")
                continue
                
        logger.warning("⚠️ Could not auto-detect external IP from any service")
        return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _get_hostname(self) -> str:
        """Get system hostname."""
        return (
            os.getenv('HOSTNAME') or 
            os.getenv('COMPUTERNAME') or 
            socket.gethostname() or 
            'localhost'
        )
    
    def _detect_docker_network(self) -> Optional[str]:
        """Detect Docker network name."""
        docker_networks = [
            os.getenv('DOCKER_NETWORK'),
            os.getenv('COMPOSE_PROJECT_NAME'),
            'vru_validation_network',
            'ai_validation_network'
        ]
        
        for network in docker_networks:
            if network:
                return network
        
        return None
    
    def _get_network_interfaces(self) -> List[str]:
        """Get available network interfaces."""
        try:
            import socket
            hostname = socket.gethostname()
            interfaces = socket.getaddrinfo(hostname, None)
            return list(set([info[4][0] for info in interfaces if info[4][0]]))
        except Exception:
            return ['127.0.0.1']
    
    async def _load_configuration_hierarchy(self, environment: str, platform: str) -> Dict[str, Any]:
        """Load configuration from hierarchy: env vars > files > defaults."""
        # Load defaults based on environment
        defaults = self._get_default_configuration(environment, platform)
        
        # Load from configuration files
        file_config = await self._load_config_files(environment, platform)
        
        # Load from environment variables
        env_config = self._load_environment_variables()
        
        # Merge with priority: env vars > files > defaults
        merged_config = {**defaults, **file_config, **env_config}
        
        return merged_config
    
    def _get_default_configuration(self, environment: str, platform: str) -> Dict[str, Any]:
        """Get default configuration based on environment."""
        is_production = environment == 'production'
        is_docker = platform == 'docker'
        
        return {
            'api': {
                'host': '0.0.0.0',
                'port': int(os.getenv('PORT', os.getenv('API_PORT', '8000'))),
                'timeout': 30 if is_production else 10,
                'max_retries': 3 if is_production else 1,
                'workers': 4 if is_production else 1
            },
            'cors': {
                'origins': [],  # Will be populated dynamically
                'credentials': True,
                'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                'headers': ['*'],
                'max_age': 3600,
                'auto_detect': True
            },
            'security': {
                'ssl_enabled': is_production,
                'security_headers_enabled': True,
                'csp_enabled': is_production,
                'hsts_enabled': is_production,
                'secret_key': os.getenv('SECRET_KEY', 'REPLACE-ME-IN-PRODUCTION'),
                'allowed_hosts': []  # Will be populated dynamically
            },
            'features': {
                'debug_mode': not is_production,
                'monitoring_enabled': is_production or environment == 'staging',
                'analytics_enabled': is_production,
                'caching_enabled': True,
                'async_processing': is_production,
                'rate_limiting': True
            },
            'logging': {
                'level': 'INFO' if is_production else 'DEBUG',
                'structured': is_production,
                'file': os.getenv('LOG_FILE') if is_production else None
            }
        }
    
    async def _load_config_files(self, environment: str, platform: str) -> Dict[str, Any]:
        """Load configuration from files."""
        config_paths = [
            f'config/{environment}.json',
            f'config/{platform}.json',
            'config/app.json',
            'config.json'
        ]
        
        for path in config_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        config = json.load(f)
                        logger.info(f"📁 Loaded configuration from: {path}")
                        return config
            except Exception as e:
                logger.warning(f"⚠️ Could not load config from {path}: {e}")
                
        return {}
    
    def _load_environment_variables(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # API configuration
        api_config = {}
        if os.getenv('API_HOST'):
            api_config['host'] = os.getenv('API_HOST')
        if os.getenv('API_PORT'):
            api_config['port'] = int(os.getenv('API_PORT'))
        if api_config:
            config['api'] = api_config
        
        # CORS configuration
        cors_config = {}
        cors_origins = (
            os.getenv('AIVALIDATION_CORS_ORIGINS') or 
            os.getenv('CORS_ORIGINS') or 
            os.getenv('ALLOWED_ORIGINS')
        )
        if cors_origins:
            cors_config['origins'] = self._parse_cors_origins(cors_origins)
        if cors_config:
            config['cors'] = cors_config
        
        # Security configuration
        security_config = {}
        if os.getenv('SSL_ENABLED'):
            security_config['ssl_enabled'] = os.getenv('SSL_ENABLED').lower() == 'true'
        if os.getenv('SECRET_KEY'):
            security_config['secret_key'] = os.getenv('SECRET_KEY')
        if security_config:
            config['security'] = security_config
        
        # Feature flags
        features_config = {}
        if os.getenv('DEBUG'):
            features_config['debug_mode'] = os.getenv('DEBUG').lower() == 'true'
        if os.getenv('MONITORING_ENABLED'):
            features_config['monitoring_enabled'] = os.getenv('MONITORING_ENABLED').lower() == 'true'
        if features_config:
            config['features'] = features_config
        
        return config
    
    def _parse_cors_origins(self, origins_string: str) -> List[str]:
        """Parse CORS origins from various formats."""
        try:
            # Try JSON array format first
            if origins_string.strip().startswith('['):
                return json.loads(origins_string)
        except json.JSONDecodeError:
            pass
        
        # Parse as comma-separated string
        return [origin.strip() for origin in origins_string.split(',') if origin.strip()]
    
    async def _generate_dynamic_config(self):
        """Generate dynamic configuration based on detected environment."""
        if not self._config:
            return
        
        # Generate API base URL
        protocol = 'https' if self._config.security.ssl_enabled else 'http'
        host = self._config.network.external_ip or self._config.network.internal_ip
        self._config.api.base_url = f"{protocol}://{host}:{self._config.api.port}"
        
        # Generate CORS origins if auto-detect is enabled
        if self._config.cors.auto_detect:
            self._config.cors.origins = self._generate_cors_origins()
        
        # Generate allowed hosts
        self._config.security.allowed_hosts = self._generate_allowed_hosts()
    
    def _generate_cors_origins(self) -> List[str]:
        """Generate CORS origins based on detected network configuration."""
        origins = set()
        
        # Add configured origins from environment
        configured_origins = (
            os.getenv('AIVALIDATION_CORS_ORIGINS', '') +
            ',' + os.getenv('CORS_ORIGINS', '') +
            ',' + os.getenv('ALLOWED_ORIGINS', '')
        ).split(',')
        origins.update([origin.strip() for origin in configured_origins if origin.strip()])
        
        # Add localhost origins for development
        if self._config.environment == 'development':
            origins.update([
                'http://localhost:3000',
                'http://127.0.0.1:3000',
                'http://localhost:3001',  # Alternative port
                'http://127.0.0.1:3001'
            ])
        
        # Add detected IP origins
        protocol = 'https' if self._config.security.ssl_enabled else 'http'
        frontend_ports = [3000, 3001, 80, 443]  # Common frontend ports
        
        # Add external IP origins
        if self._config.network.external_ip:
            for port in frontend_ports:
                if not (port == 443 and protocol == 'http') and not (port == 80 and protocol == 'https'):
                    origins.add(f"{protocol}://{self._config.network.external_ip}:{port}")
        
        # Add internal IP origins (for Docker networks)
        if (self._config.network.internal_ip and 
            self._config.network.internal_ip != self._config.network.external_ip):
            for port in frontend_ports:
                if not (port == 443 and protocol == 'http') and not (port == 80 and protocol == 'https'):
                    origins.add(f"{protocol}://{self._config.network.internal_ip}:{port}")
        
        # Filter out invalid origins and return as list
        valid_origins = []
        for origin in origins:
            if origin and origin not in ['http://', 'https://']:
                try:
                    parsed = urlparse(origin)
                    if parsed.scheme and parsed.netloc:
                        valid_origins.append(origin)
                except Exception:
                    pass
        
        return valid_origins
    
    def _generate_allowed_hosts(self) -> List[str]:
        """Generate allowed hosts for security middleware."""
        hosts = set()
        
        # Add localhost
        hosts.update(['localhost', '127.0.0.1', '0.0.0.0'])
        
        # Add detected IPs
        if self._config.network.external_ip:
            hosts.add(self._config.network.external_ip)
        if self._config.network.internal_ip:
            hosts.add(self._config.network.internal_ip)
        
        # Add hostname
        hosts.add(self._config.network.hostname)
        
        # Add configured hosts
        configured_hosts = os.getenv('ALLOWED_HOSTS', '').split(',')
        hosts.update([host.strip() for host in configured_hosts if host.strip()])
        
        return list(hosts)
    
    async def _validate_configuration(self):
        """Validate configuration integrity."""
        self._validation_errors = []
        
        if not self._config:
            self._validation_errors.append("Configuration not initialized")
            return
        
        # Validate API configuration
        self._validate_api_config()
        
        # Validate CORS configuration 
        self._validate_cors_config()
        
        # Validate security configuration
        self._validate_security_config()
        
        # Log warnings for validation errors
        if self._validation_errors:
            logger.warning("⚠️ Configuration validation warnings:")
            for error in self._validation_errors:
                logger.warning(f"  - {error}")
    
    def _validate_api_config(self):
        """Validate API configuration."""
        if self._config.api.port < 1 or self._config.api.port > 65535:
            self._validation_errors.append(f"Invalid API port: {self._config.api.port}")
        
        if not self._config.api.base_url:
            self._validation_errors.append("API base URL not configured")
    
    def _validate_cors_config(self):
        """Validate CORS configuration."""
        if len(self._config.cors.origins) == 0:
            self._validation_errors.append("No CORS origins configured - may block frontend requests")
        
        # Check for wildcard in production
        if (self._config.environment == 'production' and 
            '*' in self._config.cors.origins):
            self._validation_errors.append("CORS wildcard (*) not recommended for production")
        
        # Validate origin formats
        for origin in self._config.cors.origins:
            try:
                parsed = urlparse(origin)
                if not parsed.scheme or not parsed.netloc:
                    self._validation_errors.append(f"Invalid CORS origin format: {origin}")
            except Exception:
                self._validation_errors.append(f"Invalid CORS origin: {origin}")
    
    def _validate_security_config(self):
        """Validate security configuration."""
        if self._config.environment == 'production':
            if not self._config.security.ssl_enabled:
                self._validation_errors.append("SSL not enabled in production")
            
            if self._config.security.secret_key in [
                'REPLACE-ME-IN-PRODUCTION', 
                'your-secret-key-here',
                'INSECURE-DEFAULT-CHANGE-ME'
            ]:
                self._validation_errors.append("Using insecure default secret key in production")
            
            if self._config.features.debug_mode:
                self._validation_errors.append("Debug mode enabled in production")
    
    def _log_configuration_summary(self):
        """Log configuration summary."""
        if not self._config:
            return
            
        logger.info("📊 Configuration Summary:")
        logger.info(f"  Environment: {self._config.environment}")
        logger.info(f"  Platform: {self._config.platform}")
        logger.info(f"  API Base URL: {self._config.api.base_url}")
        logger.info(f"  CORS Origins: {len(self._config.cors.origins)} configured")
        logger.info(f"  SSL Enabled: {self._config.security.ssl_enabled}")
        logger.info(f"  Debug Mode: {self._config.features.debug_mode}")
        logger.info(f"  Network - Internal: {self._config.network.internal_ip}")
        logger.info(f"  Network - External: {self._config.network.external_ip}")
    
    # Public API methods
    
    def get_config(self) -> UnifiedConfig:
        """Get current configuration."""
        if not self._config:
            raise RuntimeError("Configuration not initialized. Call initialize() first.")
        return self._config
    
    def get_validation_errors(self) -> List[str]:
        """Get configuration validation errors."""
        return self._validation_errors.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        if not self._config:
            return {}
        return asdict(self._config)
    
    async def refresh(self) -> UnifiedConfig:
        """Refresh configuration (re-detect and reload)."""
        self._config = None
        self._network_info = None
        self._validation_errors = []
        return await self.initialize()

# Global configuration manager instance
config_manager = ConfigurationManager()

async def get_unified_config() -> UnifiedConfig:
    """Get the unified configuration instance."""
    return await config_manager.initialize()

async def get_cors_origins() -> List[str]:
    """Get CORS origins for FastAPI middleware."""
    config = await get_unified_config()
    return config.cors.origins

async def get_api_config() -> APIConfiguration:
    """Get API configuration.""" 
    config = await get_unified_config()
    return config.api

async def get_security_config() -> SecurityConfiguration:
    """Get security configuration."""
    config = await get_unified_config()
    return config.security

async def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    config = await get_unified_config()
    return config.features.debug_mode

async def is_production() -> bool:
    """Check if running in production environment."""
    config = await get_unified_config()
    return config.environment == 'production'