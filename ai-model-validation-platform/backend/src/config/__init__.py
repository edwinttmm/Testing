#!/usr/bin/env python3
"""
SPARC Configuration Module - Unified Environment-Aware Configuration
Provides centralized, intelligent configuration management for the AI Validation Platform

This module implements the SPARC (Specification, Pseudocode, Architecture, Refinement, Completion) 
methodology for robust, environment-aware configuration management.

Key Components:
- EnvironmentDetector: Detects Docker vs Local vs Cloud environments
- ServiceDiscovery: Adaptive endpoint resolution with fallback strategies  
- PathResolver: Environment-aware filesystem path management
- PortManager: Dynamic port conflict detection and resolution

Usage:
    from src.config import detect_environment, service_discovery, path_resolver, port_manager
    
    # Detect environment
    env_info = detect_environment()
    print(f"Running in: {env_info.environment_type.value}")
    
    # Discover services
    db_service = await service_discovery.discover_service("postgres", ServiceType.DATABASE)
    redis_service = await service_discovery.discover_service("redis", ServiceType.REDIS)
    
    # Resolve paths
    upload_dir = path_resolver.resolve_upload_directory()
    log_dir = path_resolver.resolve_log_directory()
    
    # Manage ports
    available_port = port_manager.find_available_port(8000)
"""

import logging
import sys
from typing import Dict, Any, Optional

# Configure logging for the config module
logger = logging.getLogger(__name__)

# Version information
__version__ = "1.0.0"
__author__ = "SPARC Development Team"
__description__ = "Unified Environment-Aware Configuration System"

# Import core components
try:
    from .environment_detector import (
        UnifiedEnvironmentDetector,
        EnvironmentType,
        ServiceMode,
        EnvironmentInfo,
        detect_environment,
        get_environment_type,
        get_service_mode,
        is_containerized,
        is_docker,
        is_local,
        is_production,
        environment_detector
    )
    
    from .service_discovery import (
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
    
    from .path_resolver import (
        PathResolver,
        PathType,
        ResolvedPath,
        path_resolver,
        resolve_upload_directory,
        resolve_log_directory,
        resolve_data_directory,
        ensure_directory_structure,
        get_path_summary
    )
    
    from .port_manager import (
        PortManager,
        PortStatus,
        ProcessType,
        PortInfo,
        port_manager,
        find_available_port,
        check_port_available,
        resolve_port_conflict,
        kill_processes_on_port,
        cleanup_stale_processes
    )
    
    # Module initialization successful
    logger.info(f"✅ SPARC Configuration Module v{__version__} initialized successfully")
    
    # Initialize components
    _initialization_status = {
        'environment_detector': True,
        'service_discovery': True,
        'path_resolver': True,
        'port_manager': True,
        'errors': []
    }
    
except ImportError as e:
    logger.error(f"❌ Failed to import core configuration components: {e}")
    _initialization_status = {
        'environment_detector': False,
        'service_discovery': False,
        'path_resolver': False,
        'port_manager': False,
        'errors': [str(e)]
    }
    
    # Create fallback components to prevent complete failure
    class _FallbackComponent:
        """Fallback component that logs warnings about unavailability"""
        def __init__(self, component_name):
            self.component_name = component_name
            
        def __getattr__(self, name):
            logger.warning(f"⚠️ {self.component_name} not available - fallback mode")
            return lambda *args, **kwargs: None
    
    # Create fallback instances
    environment_detector = _FallbackComponent("EnvironmentDetector")
    service_discovery = _FallbackComponent("ServiceDiscovery") 
    path_resolver = _FallbackComponent("PathResolver")
    port_manager = _FallbackComponent("PortManager")

def get_initialization_status() -> Dict[str, Any]:
    """
    Get the initialization status of all configuration components
    
    Returns:
        Dictionary with component status and any errors
    """
    return _initialization_status.copy()

def validate_configuration() -> Dict[str, Any]:
    """
    Validate the entire configuration system
    
    Returns:
        Validation report with component health and recommendations
    """
    logger.info("🔍 Validating SPARC configuration system...")
    
    validation_report = {
        'timestamp': None,
        'overall_status': 'healthy',
        'components': {},
        'warnings': [],
        'errors': [],
        'recommendations': []
    }
    
    import time
    validation_report['timestamp'] = time.time()
    
    try:
        # Validate environment detector
        if _initialization_status['environment_detector']:
            try:
                env_info = detect_environment()
                validation_report['components']['environment_detector'] = {
                    'status': 'healthy',
                    'environment_type': env_info.environment_type.value,
                    'service_mode': env_info.service_mode.value,
                    'confidence_score': env_info.confidence_score
                }
                
                if env_info.confidence_score < 0.7:
                    validation_report['warnings'].append(
                        f"Environment detection confidence low: {env_info.confidence_score:.2f}"
                    )
                    
            except Exception as e:
                validation_report['components']['environment_detector'] = {
                    'status': 'error',
                    'error': str(e)
                }
                validation_report['errors'].append(f"Environment detector failed: {e}")
        else:
            validation_report['components']['environment_detector'] = {
                'status': 'unavailable'
            }
            validation_report['errors'].append("Environment detector not initialized")
        
        # Validate service discovery
        if _initialization_status['service_discovery']:
            try:
                cache_info = service_discovery.get_cache_info()
                validation_report['components']['service_discovery'] = {
                    'status': 'healthy',
                    'cache_size': cache_info['cache_size'],
                    'environment_type': cache_info['environment_type']
                }
            except Exception as e:
                validation_report['components']['service_discovery'] = {
                    'status': 'error',
                    'error': str(e)
                }
                validation_report['errors'].append(f"Service discovery failed: {e}")
        else:
            validation_report['components']['service_discovery'] = {
                'status': 'unavailable'
            }
            validation_report['errors'].append("Service discovery not initialized")
        
        # Validate path resolver
        if _initialization_status['path_resolver']:
            try:
                path_validation = path_resolver.validate_paths()
                validation_report['components']['path_resolver'] = {
                    'status': 'healthy' if not path_validation['errors'] else 'degraded',
                    'paths_validated': len(path_validation['paths']),
                    'warnings': len(path_validation['warnings']),
                    'errors': len(path_validation['errors'])
                }
                
                validation_report['warnings'].extend(path_validation['warnings'])
                validation_report['errors'].extend(path_validation['errors'])
                
            except Exception as e:
                validation_report['components']['path_resolver'] = {
                    'status': 'error',
                    'error': str(e)
                }
                validation_report['errors'].append(f"Path resolver failed: {e}")
        else:
            validation_report['components']['path_resolver'] = {
                'status': 'unavailable'
            }
            validation_report['errors'].append("Path resolver not initialized")
        
        # Validate port manager
        if _initialization_status['port_manager']:
            try:
                port_report = port_manager.get_port_usage_report([8000, 8001, 3000, 5000])
                conflicts = sum(1 for port in port_report['occupied_ports'] if not port['can_terminate'])
                
                validation_report['components']['port_manager'] = {
                    'status': 'healthy' if conflicts == 0 else 'degraded',
                    'ports_checked': port_report['ports_checked'],
                    'available_ports': len(port_report['available_ports']),
                    'port_conflicts': conflicts
                }
                
                if conflicts > 0:
                    validation_report['warnings'].append(f"Port conflicts detected: {conflicts}")
                    
            except Exception as e:
                validation_report['components']['port_manager'] = {
                    'status': 'error', 
                    'error': str(e)
                }
                validation_report['errors'].append(f"Port manager failed: {e}")
        else:
            validation_report['components']['port_manager'] = {
                'status': 'unavailable'
            }
            validation_report['errors'].append("Port manager not initialized")
        
        # Determine overall status
        component_statuses = [comp.get('status') for comp in validation_report['components'].values()]
        
        if 'error' in component_statuses:
            validation_report['overall_status'] = 'unhealthy'
        elif 'degraded' in component_statuses or validation_report['warnings']:
            validation_report['overall_status'] = 'degraded'
        elif 'unavailable' in component_statuses:
            validation_report['overall_status'] = 'degraded'
        else:
            validation_report['overall_status'] = 'healthy'
        
        # Generate recommendations
        if validation_report['errors']:
            validation_report['recommendations'].append(
                "Address configuration errors before deployment"
            )
        
        if validation_report['warnings']:
            validation_report['recommendations'].append(
                "Review configuration warnings for potential issues"
            )
        
        if any(comp.get('status') == 'unavailable' for comp in validation_report['components'].values()):
            validation_report['recommendations'].append(
                "Reinstall missing configuration components"
            )
        
        logger.info(f"✅ Configuration validation completed: {validation_report['overall_status']}")
        
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        validation_report['overall_status'] = 'unhealthy'
        validation_report['errors'].append(f"Validation system error: {e}")
    
    return validation_report

async def initialize_unified_configuration() -> Dict[str, Any]:
    """
    Initialize the unified configuration system with full component setup
    
    Returns:
        Initialization report with status and configuration details
    """
    logger.info("🚀 Initializing SPARC unified configuration system...")
    
    init_report = {
        'timestamp': None,
        'initialization_successful': True,
        'components_initialized': [],
        'environment_info': {},
        'service_endpoints': {},
        'resolved_paths': {},
        'port_status': {},
        'errors': []
    }
    
    import time
    init_report['timestamp'] = time.time()
    
    try:
        # Initialize environment detection
        if _initialization_status['environment_detector']:
            try:
                env_info = detect_environment()
                init_report['components_initialized'].append('environment_detector')
                init_report['environment_info'] = {
                    'environment_type': env_info.environment_type.value,
                    'service_mode': env_info.service_mode.value,
                    'is_containerized': env_info.is_containerized,
                    'confidence_score': env_info.confidence_score,
                    'platform': env_info.platform
                }
                logger.info(f"✅ Environment detected: {env_info.environment_type.value}")
            except Exception as e:
                init_report['errors'].append(f"Environment detector initialization failed: {e}")
                logger.error(f"❌ Environment detector failed: {e}")
        
        # Initialize service discovery
        if _initialization_status['service_discovery']:
            try:
                # Test discovery of key services
                db_service = await service_discovery.discover_service("postgres", ServiceType.DATABASE)
                redis_service = await service_discovery.discover_service("redis", ServiceType.REDIS)
                
                init_report['components_initialized'].append('service_discovery')
                init_report['service_endpoints'] = {
                    'database': {
                        'endpoint': db_service.endpoint.to_url(),
                        'status': db_service.status.value,
                        'response_time_ms': db_service.response_time_ms
                    },
                    'redis': {
                        'endpoint': redis_service.endpoint.to_url(),
                        'status': redis_service.status.value,
                        'response_time_ms': redis_service.response_time_ms
                    }
                }
                logger.info(f"✅ Service discovery initialized")
            except Exception as e:
                init_report['errors'].append(f"Service discovery initialization failed: {e}")
                logger.error(f"❌ Service discovery failed: {e}")
        
        # Initialize path resolution
        if _initialization_status['path_resolver']:
            try:
                directory_structure = ensure_directory_structure()
                init_report['components_initialized'].append('path_resolver')
                init_report['resolved_paths'] = {
                    path_type: {
                        'path': resolved.path,
                        'exists': resolved.exists,
                        'writable': resolved.is_writable
                    }
                    for path_type, resolved in directory_structure.items()
                }
                logger.info(f"✅ Path resolver initialized")
            except Exception as e:
                init_report['errors'].append(f"Path resolver initialization failed: {e}")
                logger.error(f"❌ Path resolver failed: {e}")
        
        # Initialize port management
        if _initialization_status['port_manager']:
            try:
                available_port = find_available_port(8000)
                port_report = port_manager.get_port_usage_report([8000, 8001, 3000, 5000])
                
                init_report['components_initialized'].append('port_manager')
                init_report['port_status'] = {
                    'available_port': available_port,
                    'ports_checked': port_report['ports_checked'],
                    'available_count': len(port_report['available_ports']),
                    'occupied_count': len(port_report['occupied_ports'])
                }
                logger.info(f"✅ Port manager initialized")
            except Exception as e:
                init_report['errors'].append(f"Port manager initialization failed: {e}")
                logger.error(f"❌ Port manager failed: {e}")
        
        # Check if initialization was successful
        expected_components = ['environment_detector', 'service_discovery', 'path_resolver', 'port_manager']
        initialized_components = set(init_report['components_initialized'])
        
        if len(initialized_components) < len(expected_components):
            init_report['initialization_successful'] = False
            missing = set(expected_components) - initialized_components
            logger.warning(f"⚠️ Some components not initialized: {missing}")
        
        if init_report['errors']:
            init_report['initialization_successful'] = False
            logger.warning(f"⚠️ Initialization completed with {len(init_report['errors'])} errors")
        else:
            logger.info("✅ SPARC unified configuration system initialized successfully")
        
    except Exception as e:
        init_report['initialization_successful'] = False
        init_report['errors'].append(f"System initialization error: {e}")
        logger.error(f"❌ Configuration system initialization failed: {e}")
    
    return init_report

def get_configuration_summary() -> Dict[str, Any]:
    """
    Get a comprehensive summary of the current configuration state
    
    Returns:
        Configuration summary with all component states
    """
    summary = {
        'module_info': {
            'version': __version__,
            'description': __description__,
            'author': __author__
        },
        'initialization_status': get_initialization_status(),
        'components_available': {}
    }
    
    # Check component availability
    if _initialization_status['environment_detector']:
        try:
            env_info = detect_environment()
            summary['components_available']['environment_detector'] = {
                'available': True,
                'environment_type': env_info.environment_type.value,
                'service_mode': env_info.service_mode.value
            }
        except:
            summary['components_available']['environment_detector'] = {'available': False}
    else:
        summary['components_available']['environment_detector'] = {'available': False}
    
    if _initialization_status['service_discovery']:
        try:
            cache_info = service_discovery.get_cache_info()
            summary['components_available']['service_discovery'] = {
                'available': True,
                'cached_services': cache_info['cache_size']
            }
        except:
            summary['components_available']['service_discovery'] = {'available': False}
    else:
        summary['components_available']['service_discovery'] = {'available': False}
    
    if _initialization_status['path_resolver']:
        try:
            path_summary = get_path_summary()
            summary['components_available']['path_resolver'] = {
                'available': True,
                'paths_resolved': len(path_summary)
            }
        except:
            summary['components_available']['path_resolver'] = {'available': False}
    else:
        summary['components_available']['path_resolver'] = {'available': False}
    
    if _initialization_status['port_manager']:
        try:
            port_manager.check_port_status(8000)  # Test call
            summary['components_available']['port_manager'] = {
                'available': True,
                'reserved_ports': len(port_manager.get_reserved_ports())
            }
        except:
            summary['components_available']['port_manager'] = {'available': False}
    else:
        summary['components_available']['port_manager'] = {'available': False}
    
    return summary

# Export all public components
__all__ = [
    # Core classes
    'UnifiedEnvironmentDetector',
    'ServiceDiscoveryManager', 
    'PathResolver',
    'PortManager',
    
    # Enums
    'EnvironmentType',
    'ServiceMode',
    'ServiceType',
    'ServiceStatus',
    'PathType',
    'PortStatus',
    'ProcessType',
    
    # Data classes
    'EnvironmentInfo',
    'ServiceEndpoint',
    'ServiceInfo',
    'ResolvedPath',
    'PortInfo',
    
    # Global instances
    'environment_detector',
    'service_discovery',
    'path_resolver', 
    'port_manager',
    
    # Convenience functions
    'detect_environment',
    'get_environment_type',
    'get_service_mode',
    'is_containerized',
    'is_docker',
    'is_local',
    'is_production',
    'discover_database',
    'discover_redis',
    'get_database_url',
    'get_redis_url',
    'resolve_upload_directory',
    'resolve_log_directory',
    'resolve_data_directory',
    'ensure_directory_structure',
    'get_path_summary',
    'find_available_port',
    'check_port_available',
    'resolve_port_conflict',
    'kill_processes_on_port',
    'cleanup_stale_processes',
    
    # Module functions
    'get_initialization_status',
    'validate_configuration',
    'initialize_unified_configuration',
    'get_configuration_summary',
    
    # Module metadata
    '__version__',
    '__author__',
    '__description__'
]

# Log successful module initialization
logger.info(f"📦 SPARC Configuration Module ready - {len(__all__)} exports available")