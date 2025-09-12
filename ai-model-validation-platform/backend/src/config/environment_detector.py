#!/usr/bin/env python3
"""
UnifiedEnvironmentDetector - SPARC Architecture Component
Detects Docker vs Local environments with comprehensive fallback strategies
Part of the unified environment-aware configuration system
"""

import os
import sys
import socket
import subprocess
import logging
import platform
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EnvironmentType(Enum):
    """Environment deployment types"""
    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"
    WSL = "wsl"

class ServiceMode(Enum):
    """Service operation modes"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

@dataclass
class EnvironmentInfo:
    """Complete environment detection information"""
    environment_type: EnvironmentType
    service_mode: ServiceMode
    platform: str
    python_version: str
    is_containerized: bool
    is_wsl: bool
    has_docker: bool
    network_info: Dict[str, Any]
    filesystem_info: Dict[str, Any]
    process_info: Dict[str, Any]
    confidence_score: float  # 0.0 to 1.0 confidence in detection

class UnifiedEnvironmentDetector:
    """
    Comprehensive environment detection with multiple strategies
    Provides fallback detection methods for maximum reliability
    """
    
    def __init__(self):
        self.detection_methods = [
            self._detect_docker_primary,
            self._detect_docker_secondary,
            self._detect_kubernetes,
            self._detect_cloud_providers,
            self._detect_wsl,
            self._detect_local_fallback
        ]
        self._cached_detection: Optional[EnvironmentInfo] = None
        
    def detect_environment(self, force_refresh: bool = False) -> EnvironmentInfo:
        """
        Detect current environment with caching
        
        Args:
            force_refresh: Force re-detection instead of using cache
            
        Returns:
            EnvironmentInfo with complete detection results
        """
        if self._cached_detection and not force_refresh:
            return self._cached_detection
            
        logger.info("🔍 Starting unified environment detection...")
        
        # Initialize base detection info
        detection_results = {
            'docker_indicators': 0,
            'local_indicators': 0,
            'cloud_indicators': 0,
            'k8s_indicators': 0,
            'wsl_indicators': 0
        }
        
        # Run all detection methods
        for method in self.detection_methods:
            try:
                method_results = method()
                for key, value in method_results.items():
                    if key in detection_results:
                        detection_results[key] += value
                logger.debug(f"Detection method {method.__name__} completed")
            except Exception as e:
                logger.warning(f"Detection method {method.__name__} failed: {e}")
                
        # Determine environment type based on indicator scores
        env_type, confidence = self._determine_environment_type(detection_results)
        
        # Detect service mode
        service_mode = self._detect_service_mode()
        
        # Gather additional information
        network_info = self._gather_network_info()
        filesystem_info = self._gather_filesystem_info()
        process_info = self._gather_process_info()
        
        # Create environment info
        env_info = EnvironmentInfo(
            environment_type=env_type,
            service_mode=service_mode,
            platform=platform.platform(),
            python_version=platform.python_version(),
            is_containerized=env_type in [EnvironmentType.DOCKER, EnvironmentType.KUBERNETES],
            is_wsl=env_type == EnvironmentType.WSL,
            has_docker=self._check_docker_availability(),
            network_info=network_info,
            filesystem_info=filesystem_info,
            process_info=process_info,
            confidence_score=confidence
        )
        
        # Cache the result
        self._cached_detection = env_info
        
        logger.info(f"✅ Environment detected: {env_type.value} ({service_mode.value}) - Confidence: {confidence:.2f}")
        return env_info
    
    def _detect_docker_primary(self) -> Dict[str, int]:
        """Primary Docker detection method using well-known indicators"""
        indicators = 0
        
        # Check for .dockerenv file (most reliable)
        if os.path.exists('/.dockerenv'):
            indicators += 3
            logger.debug("Found /.dockerenv file")
            
        # Check for Docker environment variables
        docker_env_vars = [
            'DOCKER',
            'DOCKER_HOST',
            'DOCKER_CONTAINER',
            'CONTAINER',
            'HOSTNAME'
        ]
        
        for var in docker_env_vars:
            if os.getenv(var):
                indicators += 1
                logger.debug(f"Found Docker environment variable: {var}")
                
        # Check hostname patterns
        hostname = os.getenv('HOSTNAME', socket.gethostname())
        if hostname and len(hostname) == 12 and hostname.isalnum():
            indicators += 2  # Docker containers often have 12-character alphanumeric hostnames
            logger.debug(f"Docker-style hostname detected: {hostname}")
            
        return {'docker_indicators': indicators}
    
    def _detect_docker_secondary(self) -> Dict[str, int]:
        """Secondary Docker detection using process and filesystem analysis"""
        indicators = 0
        
        try:
            # Check /proc/1/cgroup for container indicators
            if os.path.exists('/proc/1/cgroup'):
                with open('/proc/1/cgroup', 'r') as f:
                    cgroup_content = f.read()
                    if 'docker' in cgroup_content or 'containerd' in cgroup_content:
                        indicators += 2
                        logger.debug("Docker indicators found in /proc/1/cgroup")
                        
            # Check for container-specific mount points
            if os.path.exists('/proc/mounts'):
                with open('/proc/mounts', 'r') as f:
                    mounts_content = f.read()
                    if 'overlay' in mounts_content and 'docker' in mounts_content:
                        indicators += 2
                        logger.debug("Docker overlay filesystem detected")
                        
            # Check for limited process tree (containers typically have fewer processes)
            try:
                proc_count = len(os.listdir('/proc'))
                if proc_count < 50:  # Container typically has fewer processes
                    indicators += 1
                    logger.debug(f"Limited process count suggests container: {proc_count}")
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Secondary Docker detection failed: {e}")
            
        return {'docker_indicators': indicators}
    
    def _detect_kubernetes(self) -> Dict[str, int]:
        """Detect Kubernetes environment"""
        indicators = 0
        
        # Check for Kubernetes service account
        if os.path.exists('/var/run/secrets/kubernetes.io'):
            indicators += 3
            logger.debug("Kubernetes service account detected")
            
        # Check for Kubernetes environment variables
        k8s_env_vars = [
            'KUBERNETES_SERVICE_HOST',
            'KUBERNETES_SERVICE_PORT',
            'K8S_NAMESPACE',
            'KUBE_NAMESPACE'
        ]
        
        for var in k8s_env_vars:
            if os.getenv(var):
                indicators += 1
                logger.debug(f"Found Kubernetes environment variable: {var}")
                
        return {'k8s_indicators': indicators}
    
    def _detect_cloud_providers(self) -> Dict[str, int]:
        """Detect cloud provider environments"""
        indicators = 0
        
        # AWS detection
        aws_indicators = [
            'AWS_REGION',
            'AWS_DEFAULT_REGION',
            'AWS_EXECUTION_ENV',
            'AWS_LAMBDA_FUNCTION_NAME',
            'ECS_CONTAINER_METADATA_URI'
        ]
        
        for var in aws_indicators:
            if os.getenv(var):
                indicators += 1
                logger.debug(f"Found AWS indicator: {var}")
                
        # Google Cloud detection
        gcp_indicators = [
            'GOOGLE_CLOUD_PROJECT',
            'GCP_PROJECT',
            'CLOUD_RUN_SERVICE',
            'GAE_APPLICATION'
        ]
        
        for var in gcp_indicators:
            if os.getenv(var):
                indicators += 1
                logger.debug(f"Found GCP indicator: {var}")
                
        # Azure detection
        azure_indicators = [
            'AZURE_RESOURCE_GROUP',
            'AZURE_CLIENT_ID',
            'AZURE_SUBSCRIPTION_ID',
            'WEBSITE_SITE_NAME'  # Azure App Service
        ]
        
        for var in azure_indicators:
            if os.getenv(var):
                indicators += 1
                logger.debug(f"Found Azure indicator: {var}")
                
        return {'cloud_indicators': indicators}
    
    def _detect_wsl(self) -> Dict[str, int]:
        """Detect Windows Subsystem for Linux"""
        indicators = 0
        
        try:
            # Check /proc/version for WSL
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    version_content = f.read().lower()
                    if 'microsoft' in version_content or 'wsl' in version_content:
                        indicators += 3
                        logger.debug("WSL detected in /proc/version")
                        
            # Check for WSL environment variables
            if os.getenv('WSL_DISTRO_NAME') or os.getenv('WSLENV'):
                indicators += 2
                logger.debug("WSL environment variables detected")
                
            # Check for Windows filesystem access
            if os.path.exists('/mnt/c') or os.path.exists('/c'):
                indicators += 1
                logger.debug("Windows filesystem mount detected")
                
        except Exception as e:
            logger.debug(f"WSL detection failed: {e}")
            
        return {'wsl_indicators': indicators}
    
    def _detect_local_fallback(self) -> Dict[str, int]:
        """Fallback local environment detection"""
        indicators = 0
        
        # Check for typical local development indicators
        local_indicators = [
            os.path.exists(os.path.expanduser('~/.bashrc')),
            os.path.exists(os.path.expanduser('~/.profile')),
            os.path.exists('/usr/local'),
            os.path.exists('/home'),
            platform.system() in ['Linux', 'Darwin', 'Windows']
        ]
        
        indicators = sum(1 for indicator in local_indicators if indicator)
        logger.debug(f"Local environment indicators: {indicators}")
        
        return {'local_indicators': indicators}
    
    def _determine_environment_type(self, results: Dict[str, int]) -> Tuple[EnvironmentType, float]:
        """Determine environment type from detection results with confidence score"""
        
        total_indicators = sum(results.values())
        if total_indicators == 0:
            return EnvironmentType.LOCAL, 0.3  # Low confidence fallback
        
        # Calculate confidence scores for each environment type
        scores = {
            EnvironmentType.KUBERNETES: results['k8s_indicators'] / max(total_indicators, 1),
            EnvironmentType.DOCKER: results['docker_indicators'] / max(total_indicators, 1),
            EnvironmentType.CLOUD: results['cloud_indicators'] / max(total_indicators, 1),
            EnvironmentType.WSL: results['wsl_indicators'] / max(total_indicators, 1),
            EnvironmentType.LOCAL: results['local_indicators'] / max(total_indicators, 1)
        }
        
        # Determine winner
        max_score = max(scores.values())
        winner = max(scores, key=scores.get)
        
        # Apply minimum confidence thresholds
        if max_score < 0.2:
            return EnvironmentType.LOCAL, max_score
            
        return winner, max_score
    
    def _detect_service_mode(self) -> ServiceMode:
        """Detect service operation mode"""
        
        # Check environment variables in order of priority
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
                    return ServiceMode.PRODUCTION
                elif env_lower in ['staging', 'stage']:
                    return ServiceMode.STAGING
                elif env_lower in ['test', 'testing']:
                    return ServiceMode.TESTING
                elif env_lower in ['development', 'dev', 'local']:
                    return ServiceMode.DEVELOPMENT
                    
        # Check for production indicators
        prod_indicators = [
            os.getenv('DEBUG', '').lower() == 'false',
            os.getenv('SSL_ENABLED', '').lower() == 'true',
            os.getenv('MONITORING_ENABLED', '').lower() == 'true',
            os.getenv('PRODUCTION', '').lower() == 'true'
        ]
        
        if any(prod_indicators):
            return ServiceMode.PRODUCTION
            
        # Default to development
        return ServiceMode.DEVELOPMENT
    
    def _gather_network_info(self) -> Dict[str, Any]:
        """Gather network configuration information"""
        try:
            network_info = {
                'hostname': socket.gethostname(),
                'fqdn': socket.getfqdn(),
                'local_ip': None,
                'interfaces': []
            }
            
            # Get local IP
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    network_info['local_ip'] = s.getsockname()[0]
            except:
                network_info['local_ip'] = '127.0.0.1'
                
            # Get network interfaces
            try:
                import netifaces
                network_info['interfaces'] = netifaces.interfaces()
            except ImportError:
                logger.debug("netifaces not available for interface detection")
                
            return network_info
            
        except Exception as e:
            logger.warning(f"Network info gathering failed: {e}")
            return {'hostname': 'localhost', 'local_ip': '127.0.0.1'}
    
    def _gather_filesystem_info(self) -> Dict[str, Any]:
        """Gather filesystem information"""
        try:
            fs_info = {
                'working_directory': os.getcwd(),
                'home_directory': os.path.expanduser('~'),
                'temp_directory': os.path.expanduser('~'),
                'is_root_user': os.getuid() == 0 if hasattr(os, 'getuid') else False,
                'filesystem_type': None
            }
            
            # Detect filesystem type
            if os.path.exists('/proc/mounts'):
                try:
                    with open('/proc/mounts', 'r') as f:
                        mounts = f.read()
                        if 'overlay' in mounts:
                            fs_info['filesystem_type'] = 'overlay'
                        elif 'ext4' in mounts:
                            fs_info['filesystem_type'] = 'ext4'
                        elif 'btrfs' in mounts:
                            fs_info['filesystem_type'] = 'btrfs'
                except:
                    pass
                    
            return fs_info
            
        except Exception as e:
            logger.warning(f"Filesystem info gathering failed: {e}")
            return {'working_directory': os.getcwd()}
    
    def _gather_process_info(self) -> Dict[str, Any]:
        """Gather process information"""
        try:
            process_info = {
                'pid': os.getpid(),
                'ppid': os.getppid() if hasattr(os, 'getppid') else None,
                'process_count': None,
                'init_process': None
            }
            
            # Get process count
            try:
                process_info['process_count'] = len(os.listdir('/proc'))
            except:
                pass
                
            # Check init process
            try:
                if os.path.exists('/proc/1/comm'):
                    with open('/proc/1/comm', 'r') as f:
                        process_info['init_process'] = f.read().strip()
            except:
                pass
                
            return process_info
            
        except Exception as e:
            logger.warning(f"Process info gathering failed: {e}")
            return {'pid': os.getpid()}
    
    def _check_docker_availability(self) -> bool:
        """Check if Docker is available on the system"""
        try:
            result = subprocess.run(['docker', '--version'], 
                                 capture_output=True, 
                                 text=True, 
                                 timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def get_environment_summary(self) -> Dict[str, Any]:
        """Get a comprehensive environment summary"""
        env_info = self.detect_environment()
        
        return {
            'environment_type': env_info.environment_type.value,
            'service_mode': env_info.service_mode.value,
            'platform': env_info.platform,
            'python_version': env_info.python_version,
            'is_containerized': env_info.is_containerized,
            'is_wsl': env_info.is_wsl,
            'has_docker': env_info.has_docker,
            'confidence_score': env_info.confidence_score,
            'network': {
                'hostname': env_info.network_info.get('hostname'),
                'local_ip': env_info.network_info.get('local_ip')
            },
            'filesystem': {
                'working_directory': env_info.filesystem_info.get('working_directory'),
                'filesystem_type': env_info.filesystem_info.get('filesystem_type')
            }
        }

# Global detector instance
environment_detector = UnifiedEnvironmentDetector()

def detect_environment(force_refresh: bool = False) -> EnvironmentInfo:
    """Convenience function to get environment detection"""
    return environment_detector.detect_environment(force_refresh=force_refresh)

def get_environment_type() -> EnvironmentType:
    """Get just the environment type"""
    return environment_detector.detect_environment().environment_type

def get_service_mode() -> ServiceMode:
    """Get just the service mode"""
    return environment_detector.detect_environment().service_mode

def is_containerized() -> bool:
    """Check if running in a container"""
    return environment_detector.detect_environment().is_containerized

def is_docker() -> bool:
    """Check if running in Docker"""
    return get_environment_type() == EnvironmentType.DOCKER

def is_local() -> bool:
    """Check if running locally"""
    return get_environment_type() == EnvironmentType.LOCAL

def is_production() -> bool:
    """Check if running in production mode"""
    return get_service_mode() == ServiceMode.PRODUCTION

if __name__ == "__main__":
    # Test the detector
    import json
    detector = UnifiedEnvironmentDetector()
    summary = detector.get_environment_summary()
    print(json.dumps(summary, indent=2))