#!/usr/bin/env python3
"""
Environment Master Configuration - SPARC Root Cause Solution
Unified environment detection and configuration management
Addresses ALL identified environment configuration issues
"""

import os
import sys
import json
import logging
import asyncio
import socket
import subprocess
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import urlparse
from enum import Enum

logger = logging.getLogger(__name__)

class EnvironmentType(Enum):
    """Comprehensive environment types"""
    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes" 
    CLOUD = "cloud"
    WSL = "wsl"
    HYBRID = "hybrid"  # Mixed deployment

class DeploymentStrategy(Enum):
    """Deployment strategy types"""
    LOCALHOST_ONLY = "localhost_only"
    EXTERNAL_IP_ONLY = "external_ip_only"
    HYBRID_ACCESS = "hybrid_access"
    AUTO_DETECT = "auto_detect"

@dataclass
class ServiceEndpoint:
    """Unified service endpoint configuration"""
    name: str
    host: str
    port: int
    protocol: str = "http"
    internal_host: Optional[str] = None
    external_host: Optional[str] = None
    docker_hostname: Optional[str] = None
    
    def get_url(self, access_type: str = "auto") -> str:
        """Get URL based on access type"""
        if access_type == "internal" and self.internal_host:
            host = self.internal_host
        elif access_type == "external" and self.external_host:
            host = self.external_host
        elif access_type == "docker" and self.docker_hostname:
            host = self.docker_hostname
        else:
            host = self.host
        return f"{self.protocol}://{host}:{self.port}"

@dataclass
class EnvironmentConfig:
    """Master environment configuration"""
    # Environment detection
    environment_type: EnvironmentType
    deployment_strategy: DeploymentStrategy
    confidence_score: float
    
    # Network configuration
    internal_ip: str
    external_ip: Optional[str] = None
    hostname: str = "localhost"
    
    # Service endpoints
    backend_endpoint: ServiceEndpoint = None
    frontend_endpoint: ServiceEndpoint = None
    database_endpoint: ServiceEndpoint = None
    redis_endpoint: ServiceEndpoint = None
    
    # CORS configuration
    cors_origins: List[str] = field(default_factory=list)
    
    # Environment variables
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # Validation results
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

class EnvironmentMaster:
    """
    Master environment configuration system
    Solves ALL identified root causes:
    1. Environment detection confidence issues
    2. Configuration conflicts across files
    3. Service discovery failures
    4. CORS configuration chaos
    5. Environment variable naming conflicts
    """
    
    def __init__(self):
        self._config: Optional[EnvironmentConfig] = None
        self._detection_cache = {}
        
    async def initialize(self) -> EnvironmentConfig:
        """Initialize master environment configuration"""
        logger.info("🚀 Initializing Environment Master Configuration...")
        
        # Step 1: Detect environment with high confidence
        env_type, confidence = await self._detect_environment_comprehensive()
        
        # Step 2: Detect deployment strategy
        deployment_strategy = await self._detect_deployment_strategy()
        
        # Step 3: Detect network configuration
        internal_ip, external_ip, hostname = await self._detect_network_configuration()
        
        # Step 4: Configure service endpoints
        endpoints = await self._configure_service_endpoints(
            env_type, deployment_strategy, internal_ip, external_ip
        )
        
        # Step 5: Generate unified CORS configuration
        cors_origins = await self._generate_cors_configuration(
            internal_ip, external_ip, deployment_strategy
        )
        
        # Step 6: Generate unified environment variables
        env_vars = await self._generate_unified_env_vars(
            endpoints, cors_origins, env_type
        )
        
        # Create master configuration
        self._config = EnvironmentConfig(
            environment_type=env_type,
            deployment_strategy=deployment_strategy,
            confidence_score=confidence,
            internal_ip=internal_ip,
            external_ip=external_ip,
            hostname=hostname,
            backend_endpoint=endpoints['backend'],
            frontend_endpoint=endpoints['frontend'],
            database_endpoint=endpoints['database'],
            redis_endpoint=endpoints['redis'],
            cors_origins=cors_origins,
            env_vars=env_vars
        )
        
        # Step 7: Validate configuration
        await self._validate_configuration()
        
        logger.info(f"✅ Environment Master initialized with {confidence:.1%} confidence")
        return self._config
        
    async def _detect_environment_comprehensive(self) -> Tuple[EnvironmentType, float]:
        """Comprehensive environment detection with high confidence"""
        
        detection_scores = {
            'docker': 0,
            'wsl': 0,
            'kubernetes': 0,
            'cloud': 0,
            'local': 0,
            'hybrid': 0
        }
        
        # Docker detection (multiple strategies)
        docker_score = 0
        if os.path.exists('/.dockerenv'):
            docker_score += 30
        if os.getenv('DOCKER_CONTAINER') or os.getenv('CONTAINER'):
            docker_score += 20
        if self._is_docker_hostname():
            docker_score += 15
        if self._detect_docker_cgroups():
            docker_score += 20
        if self._detect_docker_overlay_fs():
            docker_score += 15
        detection_scores['docker'] = docker_score
        
        # WSL detection
        wsl_score = 0
        if self._detect_wsl_kernel():
            wsl_score += 25
        if os.getenv('WSL_DISTRO_NAME') or os.getenv('WSLENV'):
            wsl_score += 20
        if os.path.exists('/mnt/c') or os.path.exists('/c'):
            wsl_score += 10
        detection_scores['wsl'] = wsl_score
        
        # Kubernetes detection
        k8s_score = 0
        if os.path.exists('/var/run/secrets/kubernetes.io'):
            k8s_score += 40
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            k8s_score += 30
        detection_scores['kubernetes'] = k8s_score
        
        # Cloud detection
        cloud_score = 0
        cloud_vars = ['AWS_REGION', 'GOOGLE_CLOUD_PROJECT', 'AZURE_RESOURCE_GROUP']
        cloud_score += sum(10 for var in cloud_vars if os.getenv(var))
        detection_scores['cloud'] = cloud_score
        
        # Hybrid detection (mixed environment indicators)
        hybrid_score = 0
        # If we have both Docker and WSL indicators
        if detection_scores['docker'] > 0 and detection_scores['wsl'] > 0:
            hybrid_score = (detection_scores['docker'] + detection_scores['wsl']) * 0.8
        # If we have external IP but running in container-like environment  
        if self._has_external_ip_config() and detection_scores['docker'] > 0:
            hybrid_score += 20
        detection_scores['hybrid'] = hybrid_score
        
        # Local fallback
        detection_scores['local'] = 50 if all(score < 30 for score in detection_scores.values()) else 10
        
        # Determine winner with confidence
        max_score = max(detection_scores.values())
        winner = max(detection_scores, key=detection_scores.get)
        
        # Calculate confidence (higher scores = higher confidence)
        total_score = sum(detection_scores.values())
        confidence = min(0.95, max_score / max(total_score, 1)) if total_score > 0 else 0.5
        
        # Apply minimum confidence boost for clear winners
        if max_score >= 50:
            confidence = max(confidence, 0.85)
        elif max_score >= 30:
            confidence = max(confidence, 0.70)
        
        env_type = EnvironmentType(winner)
        
        logger.info(f"🔍 Environment Detection Results:")
        for env, score in detection_scores.items():
            logger.info(f"  {env}: {score} points")
        logger.info(f"  Winner: {winner} (confidence: {confidence:.1%})")
        
        return env_type, confidence
    
    def _is_docker_hostname(self) -> bool:
        """Check if hostname follows Docker container pattern"""
        hostname = socket.gethostname()
        return len(hostname) == 12 and hostname.isalnum()
    
    def _detect_docker_cgroups(self) -> bool:
        """Detect Docker via cgroups"""
        try:
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                return 'docker' in content or 'containerd' in content
        except:
            return False
    
    def _detect_docker_overlay_fs(self) -> bool:
        """Detect Docker overlay filesystem"""
        try:
            with open('/proc/mounts', 'r') as f:
                content = f.read()
                return 'overlay' in content and ('docker' in content or 'containerd' in content)
        except:
            return False
            
    def _detect_wsl_kernel(self) -> bool:
        """Detect WSL via kernel version"""
        try:
            with open('/proc/version', 'r') as f:
                version = f.read().lower()
                return 'microsoft' in version or 'wsl' in version
        except:
            return False
            
    def _has_external_ip_config(self) -> bool:
        """Check if external IP is configured"""
        external_ip_vars = [
            'EXTERNAL_IP', 'PUBLIC_IP', 'SERVER_IP',
            'REACT_APP_API_URL', 'VRU_EXTERNAL_IP'
        ]
        for var in external_ip_vars:
            value = os.getenv(var, '')
            if value and '155.138.239.131' in value:
                return True
        return False
    
    async def _detect_deployment_strategy(self) -> DeploymentStrategy:
        """Detect optimal deployment strategy"""
        
        # Check for explicit strategy configuration
        strategy_var = os.getenv('DEPLOYMENT_STRATEGY', '').lower()
        if strategy_var in [s.value for s in DeploymentStrategy]:
            return DeploymentStrategy(strategy_var)
        
        # Auto-detect based on environment
        has_external_ip = self._has_external_ip_config()
        is_containerized = self._config.environment_type in [
            EnvironmentType.DOCKER, EnvironmentType.KUBERNETES, EnvironmentType.HYBRID
        ] if self._config else False
        
        if has_external_ip and is_containerized:
            return DeploymentStrategy.HYBRID_ACCESS
        elif has_external_ip:
            return DeploymentStrategy.EXTERNAL_IP_ONLY
        elif is_containerized:
            return DeploymentStrategy.AUTO_DETECT
        else:
            return DeploymentStrategy.LOCALHOST_ONLY
    
    async def _detect_network_configuration(self) -> Tuple[str, Optional[str], str]:
        """Detect network configuration"""
        
        # Internal IP detection
        internal_ip = self._get_internal_ip()
        
        # External IP detection
        external_ip = await self._get_external_ip()
        
        # Hostname detection
        hostname = (
            os.getenv('HOSTNAME') or 
            os.getenv('COMPUTERNAME') or 
            socket.gethostname() or 
            'localhost'
        )
        
        return internal_ip, external_ip, hostname
        
    def _get_internal_ip(self) -> str:
        """Get internal IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"
    
    async def _get_external_ip(self) -> Optional[str]:
        """Get external IP from configuration or detection"""
        
        # Check configured external IPs
        configured_ips = [
            os.getenv('EXTERNAL_IP'),
            os.getenv('PUBLIC_IP'),
            os.getenv('SERVER_IP'),
            os.getenv('VRU_EXTERNAL_IP')
        ]
        
        for ip in configured_ips:
            if ip and self._is_valid_ip(ip):
                return ip
        
        # Extract from React app URL
        react_url = os.getenv('REACT_APP_API_URL', '')
        if react_url:
            try:
                parsed = urlparse(react_url)
                if parsed.hostname and self._is_valid_ip(parsed.hostname):
                    return parsed.hostname
            except:
                pass
        
        # Hardcoded known external IP (from analysis)
        if '155.138.239.131' in str(configured_ips):
            return '155.138.239.131'
            
        return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address"""
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    async def _configure_service_endpoints(self, 
                                         env_type: EnvironmentType,
                                         strategy: DeploymentStrategy, 
                                         internal_ip: str,
                                         external_ip: Optional[str]) -> Dict[str, ServiceEndpoint]:
        """Configure all service endpoints based on detected environment"""
        
        endpoints = {}
        
        # Backend endpoint
        backend_host = "localhost"
        backend_internal = internal_ip
        backend_external = external_ip or internal_ip
        backend_docker = "backend"
        
        endpoints['backend'] = ServiceEndpoint(
            name="backend",
            host=backend_host,
            port=8000,
            protocol="http",
            internal_host=backend_internal,
            external_host=backend_external,
            docker_hostname=backend_docker
        )
        
        # Frontend endpoint  
        frontend_host = "localhost"
        frontend_external = external_ip or internal_ip
        
        endpoints['frontend'] = ServiceEndpoint(
            name="frontend",
            host=frontend_host,
            port=3000,
            protocol="http",
            external_host=frontend_external
        )
        
        # Database endpoint
        db_host = "localhost"
        db_docker = "postgres"
        
        if env_type == EnvironmentType.DOCKER:
            db_host = "postgres"
            
        endpoints['database'] = ServiceEndpoint(
            name="database",
            host=db_host,
            port=5432,
            protocol="postgresql",
            docker_hostname=db_docker
        )
        
        # Redis endpoint
        redis_host = "localhost" 
        redis_docker = "redis"
        
        if env_type == EnvironmentType.DOCKER:
            redis_host = "redis"
            
        endpoints['redis'] = ServiceEndpoint(
            name="redis",
            host=redis_host,
            port=6379,
            protocol="redis",
            docker_hostname=redis_docker
        )
        
        return endpoints
    
    async def _generate_cors_configuration(self,
                                         internal_ip: str,
                                         external_ip: Optional[str],
                                         strategy: DeploymentStrategy) -> List[str]:
        """Generate unified CORS origins configuration"""
        
        origins = set()
        
        # Always include localhost for development
        origins.update([
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:3001', 
            'http://127.0.0.1:3001'
        ])
        
        # Add internal IP origins
        if internal_ip and internal_ip != '127.0.0.1':
            origins.update([
                f'http://{internal_ip}:3000',
                f'http://{internal_ip}:3001'
            ])
        
        # Add external IP origins
        if external_ip:
            origins.update([
                f'http://{external_ip}:3000',
                f'http://{external_ip}:3001',
                f'http://{external_ip}',
                f'https://{external_ip}:3000',
                f'https://{external_ip}:3001',
                f'https://{external_ip}'
            ])
        
        # Add configured origins from environment
        env_origins = []
        cors_env_vars = [
            'AIVALIDATION_CORS_ORIGINS',
            'CORS_ORIGINS',
            'ALLOWED_ORIGINS',
            'VRU_CORS_ORIGINS'
        ]
        
        for var in cors_env_vars:
            value = os.getenv(var, '')
            if value:
                # Handle both JSON array and comma-separated formats
                try:
                    if value.strip().startswith('['):
                        env_origins.extend(json.loads(value))
                    else:
                        env_origins.extend([o.strip() for o in value.split(',') if o.strip()])
                except:
                    env_origins.extend([o.strip() for o in value.split(',') if o.strip()])
        
        origins.update(env_origins)
        
        # Filter and validate origins
        valid_origins = []
        for origin in origins:
            if origin and origin not in ['http://', 'https://']:
                try:
                    parsed = urlparse(origin)
                    if parsed.scheme and parsed.netloc:
                        valid_origins.append(origin)
                except:
                    pass
        
        return sorted(valid_origins)
    
    async def _generate_unified_env_vars(self,
                                       endpoints: Dict[str, ServiceEndpoint],
                                       cors_origins: List[str],
                                       env_type: EnvironmentType) -> Dict[str, str]:
        """Generate unified environment variables for all components"""
        
        env_vars = {}
        
        # =================
        # UNIFIED NAMING CONVENTION: Use AIVALIDATION_ prefix for consistency
        # =================
        
        # Environment detection
        env_vars.update({
            'AIVALIDATION_ENVIRONMENT_TYPE': env_type.value,
            'AIVALIDATION_APP_ENVIRONMENT': 'development',
            'APP_ENV': 'development',
            'NODE_ENV': 'development'
        })
        
        # Backend configuration
        backend = endpoints['backend']
        env_vars.update({
            'AIVALIDATION_API_HOST': '0.0.0.0',
            'AIVALIDATION_API_PORT': str(backend.port),
            'AIVALIDATION_API_BASE_URL': backend.get_url(),
            'API_HOST': '0.0.0.0',
            'API_PORT': str(backend.port)
        })
        
        # Database configuration
        database = endpoints['database'] 
        if env_type == EnvironmentType.DOCKER:
            db_url = f"postgresql://postgres:secure_password_change_me@{database.docker_hostname}:5432/vru_validation"
        else:
            db_url = "sqlite:///./dev_database.db"
            
        env_vars.update({
            'AIVALIDATION_DATABASE_URL': db_url,
            'DATABASE_URL': db_url
        })
        
        # Redis configuration
        redis = endpoints['redis']
        if env_type == EnvironmentType.DOCKER:
            redis_url = f"redis://:secure_redis_password@{redis.docker_hostname}:6379"
        else:
            redis_url = f"redis://localhost:6379"
            
        env_vars.update({
            'AIVALIDATION_REDIS_URL': redis_url,
            'REDIS_URL': redis_url
        })
        
        # CORS configuration (JSON format for backend compatibility)
        cors_json = json.dumps(cors_origins)
        env_vars.update({
            'AIVALIDATION_CORS_ORIGINS': cors_json,
            'ALLOWED_ORIGINS': cors_json,
            'CORS_ORIGINS': ','.join(cors_origins)  # Comma-separated for legacy support
        })
        
        # Frontend configuration
        frontend = endpoints['frontend']
        backend_url = backend.get_url('external') if backend.external_host else backend.get_url()
        
        env_vars.update({
            'REACT_APP_API_URL': backend_url,
            'REACT_APP_WS_URL': backend_url.replace('http://', 'ws://').replace('https://', 'wss://'),
            'REACT_APP_SOCKETIO_URL': f"{backend_url.replace('8000', '8001')}",
            'REACT_APP_VIDEO_BASE_URL': backend_url,
            'REACT_APP_ENVIRONMENT': 'development',
            'REACT_APP_DEBUG': 'true'
        })
        
        # Docker configuration
        env_vars.update({
            'AIVALIDATION_DOCKER_MODE': str(env_type == EnvironmentType.DOCKER).lower(),
            'DOCKER': 'true' if env_type == EnvironmentType.DOCKER else 'false'
        })
        
        # Security
        env_vars.update({
            'AIVALIDATION_SECRET_KEY': 'GENERATE_SECURE_KEY_FOR_PRODUCTION'
        })
        
        return env_vars
    
    async def _validate_configuration(self):
        """Validate the complete configuration"""
        if not self._config:
            return
            
        errors = []
        
        # Validate endpoints
        for endpoint_name, endpoint in [
            ('backend', self._config.backend_endpoint),
            ('frontend', self._config.frontend_endpoint),
            ('database', self._config.database_endpoint),
            ('redis', self._config.redis_endpoint)
        ]:
            if not endpoint:
                errors.append(f"Missing {endpoint_name} endpoint configuration")
                continue
                
            if not endpoint.host:
                errors.append(f"Missing host for {endpoint_name} endpoint")
            if not endpoint.port or endpoint.port <= 0:
                errors.append(f"Invalid port for {endpoint_name} endpoint: {endpoint.port}")
        
        # Validate CORS origins
        if not self._config.cors_origins:
            errors.append("No CORS origins configured")
            
        # Validate network configuration
        if not self._config.internal_ip:
            errors.append("Missing internal IP configuration")
            
        # Update validation results
        self._config.validation_errors = errors
        self._config.is_valid = len(errors) == 0
        
        if errors:
            logger.warning("⚠️ Configuration validation warnings:")
            for error in errors:
                logger.warning(f"  - {error}")
        else:
            logger.info("✅ Configuration validation passed")
    
    def get_config(self) -> Optional[EnvironmentConfig]:
        """Get current configuration"""
        return self._config
    
    def export_env_file(self, filepath: str = '.env.unified'):
        """Export environment variables to .env file"""
        if not self._config:
            raise RuntimeError("Configuration not initialized")
            
        with open(filepath, 'w') as f:
            f.write("# Unified Environment Configuration\n")
            f.write("# Generated by Environment Master\n")
            f.write(f"# Environment: {self._config.environment_type.value}\n")
            f.write(f"# Deployment: {self._config.deployment_strategy.value}\n")
            f.write(f"# Confidence: {self._config.confidence_score:.1%}\n\n")
            
            for key, value in sorted(self._config.env_vars.items()):
                f.write(f"{key}={value}\n")
                
        logger.info(f"📁 Environment configuration exported to {filepath}")
    
    def export_docker_compose_env(self, filepath: str = '.env.docker'):
        """Export Docker Compose compatible environment"""
        if not self._config:
            raise RuntimeError("Configuration not initialized")
            
        with open(filepath, 'w') as f:
            f.write("# Docker Compose Environment Configuration\n")
            f.write("# Generated by Environment Master\n\n")
            
            # Docker-specific variables
            f.write("# Docker Configuration\n")
            f.write(f"COMPOSE_PROJECT_NAME=ai-model-validation\n")
            f.write(f"DOCKER_BUILDKIT=1\n")
            f.write(f"COMPOSE_DOCKER_CLI_BUILD=1\n\n")
            
            # Service configuration
            for key, value in sorted(self._config.env_vars.items()):
                # Skip React app variables in Docker compose env
                if not key.startswith('REACT_APP_'):
                    f.write(f"{key}={value}\n")
                    
        logger.info(f"🐳 Docker Compose environment exported to {filepath}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary"""
        if not self._config:
            return {'error': 'Configuration not initialized'}
            
        return {
            'environment_type': self._config.environment_type.value,
            'deployment_strategy': self._config.deployment_strategy.value,
            'confidence_score': f"{self._config.confidence_score:.1%}",
            'network': {
                'internal_ip': self._config.internal_ip,
                'external_ip': self._config.external_ip,
                'hostname': self._config.hostname
            },
            'endpoints': {
                'backend': self._config.backend_endpoint.get_url() if self._config.backend_endpoint else None,
                'frontend': self._config.frontend_endpoint.get_url() if self._config.frontend_endpoint else None,
                'database': self._config.database_endpoint.host if self._config.database_endpoint else None,
                'redis': self._config.redis_endpoint.host if self._config.redis_endpoint else None
            },
            'cors_origins_count': len(self._config.cors_origins),
            'env_vars_count': len(self._config.env_vars),
            'is_valid': self._config.is_valid,
            'validation_errors': self._config.validation_errors
        }

# Global instance
environment_master = EnvironmentMaster()

# Convenience functions
async def initialize_environment() -> EnvironmentConfig:
    """Initialize and get environment configuration"""
    return await environment_master.initialize()

async def get_environment_config() -> Optional[EnvironmentConfig]:
    """Get current environment configuration"""
    return environment_master.get_config()

def export_environment_files():
    """Export all environment configuration files"""
    environment_master.export_env_file('.env.unified')
    environment_master.export_docker_compose_env('.env.docker')

if __name__ == "__main__":
    # Test the environment master
    async def test_environment_master():
        import json
        
        config = await initialize_environment()
        summary = environment_master.get_summary()
        
        print("🔧 Environment Master Configuration Summary:")
        print(json.dumps(summary, indent=2))
        
        # Export configuration files
        export_environment_files()
        print("\n📁 Configuration files exported:")
        print("  - .env.unified")
        print("  - .env.docker")
    
    asyncio.run(test_environment_master())