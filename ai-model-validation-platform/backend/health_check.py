#!/usr/bin/env python3

"""
Unified Health Check System - SPARC Architecture Component
Environment-aware health checking with intelligent service discovery
Integrates with the unified configuration architecture
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import traceback
import time

# Import unified architecture components
try:
    from src.config.environment_detector import detect_environment, EnvironmentType, ServiceMode
    from src.config.service_discovery import service_discovery, ServiceType, ServiceStatus
    from src.config.path_resolver import path_resolver, PathType
    from src.config.port_manager import port_manager
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import unified architecture components: {e}")
    # Fallback imports for backwards compatibility
    detect_environment = None
    service_discovery = None
    path_resolver = None
    port_manager = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnifiedHealthChecker:
    """
    Unified health checker using SPARC architecture components
    Provides environment-aware health checking with service discovery
    """
    
    def __init__(self):
        self.env_info = detect_environment() if detect_environment else None
        self.health_cache = {}
        self.cache_ttl = 30  # 30 seconds
        
    async def check_environment_health(self) -> Dict[str, Any]:
        """Check environment configuration and detection"""
        try:
            if not self.env_info:
                return {
                    "status": "degraded",
                    "environment": "detection_failed",
                    "message": "Environment detection not available"
                }
            
            return {
                "status": "healthy",
                "environment": "detected",
                "details": {
                    "environment_type": self.env_info.environment_type.value,
                    "service_mode": self.env_info.service_mode.value,
                    "is_containerized": self.env_info.is_containerized,
                    "confidence_score": self.env_info.confidence_score,
                    "platform": self.env_info.platform
                }
            }
        except Exception as e:
            logger.error(f"Environment health check failed: {e}")
            return {
                "status": "unhealthy",
                "environment": "error",
                "error": str(e)
            }
    
    async def check_service_discovery_health(self) -> Dict[str, Any]:
        """Check service discovery functionality"""
        try:
            if not service_discovery:
                return {
                    "status": "degraded", 
                    "service_discovery": "not_available",
                    "message": "Service discovery not available"
                }
            
            # Test service discovery for key services
            services_to_test = [
                ("postgres", ServiceType.DATABASE),
                ("redis", ServiceType.REDIS)
            ]
            
            discovery_results = {}
            healthy_count = 0
            
            for service_name, service_type in services_to_test:
                try:
                    service_info = await service_discovery.discover_service(service_name, service_type)
                    discovery_results[service_name] = {
                        "status": service_info.status.value,
                        "endpoint": service_info.endpoint.to_url(),
                        "response_time_ms": service_info.response_time_ms
                    }
                    if service_info.status == ServiceStatus.AVAILABLE:
                        healthy_count += 1
                except Exception as e:
                    discovery_results[service_name] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            overall_status = "healthy" if healthy_count == len(services_to_test) else "degraded"
            
            return {
                "status": overall_status,
                "service_discovery": "operational",
                "services": discovery_results
            }
            
        except Exception as e:
            logger.error(f"Service discovery health check failed: {e}")
            return {
                "status": "unhealthy",
                "service_discovery": "error",
                "error": str(e)
            }
    
    async def check_path_resolution_health(self) -> Dict[str, Any]:
        """Check path resolution functionality"""
        try:
            if not path_resolver:
                return {
                    "status": "degraded",
                    "path_resolution": "not_available", 
                    "message": "Path resolver not available"
                }
            
            # Validate critical paths
            validation_results = path_resolver.validate_paths()
            
            critical_paths = ['upload_directory', 'log_directory', 'temp_directory']
            critical_issues = [
                error for error in validation_results['errors']
                if any(path in error for path in critical_paths)
            ]
            
            if critical_issues:
                status = "unhealthy"
            elif validation_results['errors']:
                status = "degraded"
            else:
                status = "healthy"
            
            return {
                "status": status,
                "path_resolution": "operational",
                "paths": validation_results['paths'],
                "warnings": validation_results['warnings'][:5],  # Limit output
                "errors": validation_results['errors'][:5]
            }
            
        except Exception as e:
            logger.error(f"Path resolution health check failed: {e}")
            return {
                "status": "unhealthy",
                "path_resolution": "error",
                "error": str(e)
            }
    
    async def check_port_management_health(self) -> Dict[str, Any]:
        """Check port management functionality"""
        try:
            if not port_manager:
                return {
                    "status": "degraded",
                    "port_management": "not_available",
                    "message": "Port manager not available"
                }
            
            # Check common service ports
            port_report = port_manager.get_port_usage_report([8000, 8001, 5432, 6379, 3000])
            
            # Count conflicts (occupied ports that could be problematic)
            conflicts = len([
                port for port in port_report['occupied_ports']
                if port['port'] in [8000, 8001] and not port['can_terminate']
            ])
            
            status = "healthy" if conflicts == 0 else "degraded"
            
            return {
                "status": status,
                "port_management": "operational",
                "available_ports": len(port_report['available_ports']),
                "occupied_ports": len(port_report['occupied_ports']),
                "port_conflicts": conflicts
            }
            
        except Exception as e:
            logger.error(f"Port management health check failed: {e}")
            return {
                "status": "unhealthy",
                "port_management": "error", 
                "error": str(e)
            }

# Create global health checker instance
unified_health_checker = UnifiedHealthChecker()

async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity with service discovery and enhanced error handling"""
    try:
        # Use service discovery if available
        if service_discovery:
            try:
                service_info = await service_discovery.discover_service("postgres", ServiceType.DATABASE)
                if service_info.status == ServiceStatus.AVAILABLE:
                    # Validate actual database connectivity beyond just network reachability
                    from database import get_database_health
                    detailed_health = get_database_health()
                    
                    return {
                        "status": detailed_health.get("status", "healthy"),
                        "database": detailed_health.get("database", "connected"),
                        "endpoint": service_info.endpoint.to_url(),
                        "response_time_ms": service_info.response_time_ms,
                        "discovery_method": "service_discovery",
                        "details": detailed_health
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "database": "unreachable",
                        "endpoint": service_info.endpoint.to_url(),
                        "discovery_method": "service_discovery",
                        "error": f"Service status: {service_info.status.value}"
                    }
            except Exception as discovery_error:
                logger.warning(f"Service discovery failed, falling back to traditional: {discovery_error}")
        
        # Fallback to traditional method with enhanced validation
        from database import engine, get_database_health, DATABASE_URL
        from sqlalchemy import text
        import os
        
        # Check environment variable configuration first
        env_check = {
            "VRU_DATABASE_URL": os.getenv("VRU_DATABASE_URL"),
            "DATABASE_URL": os.getenv("DATABASE_URL"), 
            "AIVALIDATION_DATABASE_URL": os.getenv("AIVALIDATION_DATABASE_URL")
        }
        
        configured_vars = {k: v for k, v in env_check.items() if v is not None}
        
        if not configured_vars:
            return {
                "status": "unhealthy",
                "database": "misconfigured",
                "error": "No database environment variables configured",
                "suggestion": "Set VRU_DATABASE_URL, DATABASE_URL, or AIVALIDATION_DATABASE_URL",
                "discovery_method": "traditional"
            }
        
        # Test basic connection with timeout
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1 as connection_test"))
                test_value = result.fetchone()[0]
                if test_value != 1:
                    raise Exception("Database connection test query failed")
        except Exception as conn_error:
            return {
                "status": "unhealthy",
                "database": "connection_failed",
                "error": str(conn_error),
                "configured_url": next(iter(configured_vars.values())) if configured_vars else None,
                "configured_vars": list(configured_vars.keys()),
                "discovery_method": "traditional"
            }
            
        # Get detailed health info if connection successful
        detailed_health = get_database_health()
        
        return {
            "status": detailed_health.get("status", "healthy"),
            "database": detailed_health.get("database", "connected"),
            "details": detailed_health,
            "configured_vars": list(configured_vars.keys()),
            "discovery_method": "traditional"
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        import os
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "env_vars_present": {
                "VRU_DATABASE_URL": bool(os.getenv("VRU_DATABASE_URL")),
                "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
                "AIVALIDATION_DATABASE_URL": bool(os.getenv("AIVALIDATION_DATABASE_URL"))
            }
        }

async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity with service discovery"""
    try:
        # Use service discovery if available
        if service_discovery:
            service_info = await service_discovery.discover_service("redis", ServiceType.REDIS)
            if service_info.status == ServiceStatus.AVAILABLE:
                # Test actual Redis functionality
                import redis
                redis_url = service_info.endpoint.to_url()
                r = redis.from_url(redis_url, decode_responses=True)
                r.ping()
                
                return {
                    "status": "healthy",
                    "redis": "connected",
                    "endpoint": redis_url,
                    "response_time_ms": service_info.response_time_ms,
                    "discovery_method": "service_discovery"
                }
            else:
                return {
                    "status": "unhealthy",
                    "redis": "unreachable", 
                    "endpoint": service_info.endpoint.to_url(),
                    "discovery_method": "service_discovery"
                }
        
        # Fallback to traditional method
        import redis
        
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic connectivity
        r.ping()
        
        # Test basic operations
        test_key = 'health_check'
        r.set(test_key, 'ok', ex=10)
        value = r.get(test_key)
        r.delete(test_key)
        
        if value != 'ok':
            raise Exception("Redis set/get test failed")
            
        return {
            "status": "healthy",
            "redis": "connected",
            "discovery_method": "traditional"
        }
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy", 
            "redis": "disconnected",
            "error": str(e)
        }

async def check_file_system_health() -> Dict[str, Any]:
    """Check file system with path resolution"""
    try:
        if path_resolver:
            # Use path resolver for environment-aware directory checking
            critical_paths = [
                PathType.UPLOAD_DIRECTORY,
                PathType.LOG_DIRECTORY,
                PathType.TEMP_DIRECTORY
            ]
            
            dir_status = {}
            all_accessible = True
            
            for path_type in critical_paths:
                resolved = path_resolver.resolve_path(path_type, ensure_exists=True)
                dir_status[path_type.value] = {
                    "path": resolved.path,
                    "exists": resolved.exists,
                    "writable": resolved.is_writable,
                    "readable": resolved.is_readable
                }
                
                if not (resolved.exists and resolved.is_writable):
                    all_accessible = False
            
            return {
                "status": "healthy" if all_accessible else "degraded",
                "filesystem": "accessible" if all_accessible else "issues_detected",
                "directories": dir_status,
                "resolution_method": "path_resolver"
            }
        
        # Fallback to traditional method
        required_dirs = ['/app', '/app/uploads', '/app/models']
        dir_status = {}
        
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                # Check if writable
                test_file = os.path.join(dir_path, '.write_test')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    dir_status[dir_path] = "accessible"
                except:
                    dir_status[dir_path] = "read_only"
            else:
                dir_status[dir_path] = "missing"
        
        all_accessible = all(status == "accessible" for status in dir_status.values())
        
        return {
            "status": "healthy" if all_accessible else "degraded",
            "filesystem": "accessible" if all_accessible else "issues_detected",
            "directories": dir_status,
            "resolution_method": "traditional"
        }
        
    except Exception as e:
        logger.error(f"File system health check failed: {e}")
        return {
            "status": "unhealthy",
            "filesystem": "error",
            "error": str(e)
        }

async def check_network_connectivity() -> Dict[str, Any]:
    """Check network connectivity with service discovery"""
    try:
        if service_discovery:
            # Use service discovery for intelligent connectivity checking
            services_to_check = [
                ("postgres", ServiceType.DATABASE),
                ("redis", ServiceType.REDIS)
            ]
            
            connectivity_status = {}
            all_connected = True
            
            for service_name, service_type in services_to_check:
                try:
                    service_info = await service_discovery.discover_service(service_name, service_type)
                    connectivity_status[service_name] = {
                        "status": service_info.status.value,
                        "endpoint": service_info.endpoint.to_url(),
                        "response_time_ms": service_info.response_time_ms
                    }
                    if service_info.status != ServiceStatus.AVAILABLE:
                        all_connected = False
                except Exception as e:
                    connectivity_status[service_name] = {
                        "status": "error",
                        "error": str(e)
                    }
                    all_connected = False
            
            return {
                "status": "healthy" if all_connected else "degraded",
                "network": "connected" if all_connected else "issues_detected",
                "services": connectivity_status,
                "discovery_method": "service_discovery"
            }
        
        # Fallback to traditional method
        import socket
        
        services_to_check = [
            ("postgres", 5432),
            ("redis", 6379)
        ]
        
        connectivity_status = {}
        
        for hostname, port in services_to_check:
            try:
                # Test DNS resolution
                ip = socket.gethostbyname(hostname)
                
                # Test TCP connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((hostname, port))
                sock.close()
                
                if result == 0:
                    connectivity_status[f"{hostname}:{port}"] = {"status": "connected", "ip": ip}
                else:
                    connectivity_status[f"{hostname}:{port}"] = {"status": "unreachable", "ip": ip}
                    
            except socket.gaierror:
                connectivity_status[f"{hostname}:{port}"] = {"status": "dns_failed", "ip": None}
            except Exception as e:
                connectivity_status[f"{hostname}:{port}"] = {"status": "error", "error": str(e)}
        
        all_connected = all(
            status.get("status") == "connected" 
            for status in connectivity_status.values()
        )
        
        return {
            "status": "healthy" if all_connected else "degraded",
            "network": "connected" if all_connected else "issues_detected",
            "services": connectivity_status,
            "discovery_method": "traditional"
        }
        
    except Exception as e:
        logger.error(f"Network connectivity check failed: {e}")
        return {
            "status": "unhealthy",
            "network": "error", 
            "error": str(e)
        }

def get_system_info() -> Dict[str, Any]:
    """Get basic system information"""
    try:
        import platform
        import psutil
        
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent_used": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent_used": psutil.disk_usage('/').percent
            }
        }
    except ImportError:
        # psutil not available
        import platform
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count()
        }
    except Exception as e:
        logger.error(f"System info check failed: {e}")
        return {"error": str(e)}

async def comprehensive_health_check() -> Dict[str, Any]:
    """Run comprehensive unified health check"""
    logger.info("🏥 Starting comprehensive unified health check...")
    
    try:
        # Run all health checks concurrently for better performance
        health_checks = await asyncio.gather(
            # Traditional checks (with service discovery integration)
            check_database_health(),
            check_redis_health(),
            check_file_system_health(),
            check_network_connectivity(),
            # New unified architecture checks
            unified_health_checker.check_environment_health(),
            unified_health_checker.check_service_discovery_health(),
            unified_health_checker.check_path_resolution_health(),
            unified_health_checker.check_port_management_health(),
            return_exceptions=True
        )
        
        # Unpack results
        (database_health, redis_health, filesystem_health, network_health,
         environment_health, service_discovery_health, path_resolution_health, 
         port_management_health) = health_checks
        
        # Handle any exceptions
        all_checks = {
            "database": database_health if not isinstance(database_health, Exception) else {"status": "error", "error": str(database_health)},
            "redis": redis_health if not isinstance(redis_health, Exception) else {"status": "error", "error": str(redis_health)},
            "filesystem": filesystem_health if not isinstance(filesystem_health, Exception) else {"status": "error", "error": str(filesystem_health)},
            "network": network_health if not isinstance(network_health, Exception) else {"status": "error", "error": str(network_health)},
            "environment": environment_health if not isinstance(environment_health, Exception) else {"status": "error", "error": str(environment_health)},
            "service_discovery": service_discovery_health if not isinstance(service_discovery_health, Exception) else {"status": "error", "error": str(service_discovery_health)},
            "path_resolution": path_resolution_health if not isinstance(path_resolution_health, Exception) else {"status": "error", "error": str(path_resolution_health)},
            "port_management": port_management_health if not isinstance(port_management_health, Exception) else {"status": "error", "error": str(port_management_health)}
        }
        
        # Calculate overall health status
        status_counts = {"healthy": 0, "degraded": 0, "unhealthy": 0, "error": 0}
        
        for check_name, check_result in all_checks.items():
            status = check_result.get("status", "error")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Determine overall status with weighted importance
        critical_checks = ["database", "environment", "filesystem"]
        critical_issues = [
            check_name for check_name in critical_checks 
            if all_checks[check_name].get("status") in ["unhealthy", "error"]
        ]
        
        if critical_issues:
            overall_status = "unhealthy"
            overall_message = f"Critical systems down: {', '.join(critical_issues)}"
        elif status_counts["unhealthy"] > 0:
            overall_status = "unhealthy" 
            overall_message = "Some systems are down"
        elif status_counts["degraded"] > 0:
            overall_status = "degraded"
            overall_message = "Some systems have issues but service is functional"
        else:
            overall_status = "healthy"
            overall_message = "All systems operational"
        
        # Get system info
        system_info = get_system_info()
        
        # Build comprehensive response
        health_response = {
            "status": overall_status,
            "message": overall_message,
            "timestamp": time.time(),
            "architecture": "unified_sparc",
            "checks": {
                "traditional": {
                    "database": all_checks["database"],
                    "redis": all_checks["redis"],
                    "filesystem": all_checks["filesystem"],
                    "network": all_checks["network"]
                },
                "unified_architecture": {
                    "environment": all_checks["environment"],
                    "service_discovery": all_checks["service_discovery"], 
                    "path_resolution": all_checks["path_resolution"],
                    "port_management": all_checks["port_management"]
                }
            },
            "system": system_info,
            "environment_info": {
                "detected_type": unified_health_checker.env_info.environment_type.value if unified_health_checker.env_info else "unknown",
                "service_mode": unified_health_checker.env_info.service_mode.value if unified_health_checker.env_info else "unknown",
                "is_containerized": unified_health_checker.env_info.is_containerized if unified_health_checker.env_info else False,
                "confidence_score": unified_health_checker.env_info.confidence_score if unified_health_checker.env_info else 0.0
            },
            "statistics": {
                "total_checks": len(all_checks),
                "healthy_checks": status_counts["healthy"],
                "degraded_checks": status_counts["degraded"],
                "unhealthy_checks": status_counts["unhealthy"],
                "error_checks": status_counts["error"]
            }
        }
        
        logger.info(f"✅ Health check completed: {overall_status} "
                   f"({status_counts['healthy']}/{len(all_checks)} healthy)")
        
        return health_response
        
    except Exception as e:
        logger.error(f"❌ Comprehensive health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": "Health check system failure",
            "error": str(e),
            "timestamp": time.time(),
            "traceback": traceback.format_exc()
        }

# FastAPI app for health endpoint (if this file is imported by main.py)
def add_health_routes(app: FastAPI):
    """Add health check routes to FastAPI app"""
    
    @app.get("/health")
    async def health_check():
        """Basic health check endpoint"""
        try:
            health_data = await comprehensive_health_check()
            
            if health_data["status"] == "unhealthy":
                return JSONResponse(
                    status_code=503,
                    content=health_data
                )
            elif health_data["status"] == "degraded":
                return JSONResponse(
                    status_code=200,
                    content=health_data
                )
            else:
                return JSONResponse(
                    status_code=200,
                    content=health_data
                )
                
        except Exception as e:
            logger.error(f"Health check endpoint failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "Health check failed",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            )
    
    @app.get("/health/simple")
    async def simple_health_check():
        """Simple health check that just returns OK"""
        return {"status": "ok", "message": "Service is running"}

# Standalone execution for testing
if __name__ == "__main__":
    import asyncio
    import json
    import sys
    import traceback

    try:
        health_data = asyncio.run(comprehensive_health_check())
        
        # Print results
        print(json.dumps(health_data, indent=2, default=str))
        
        # Exit with appropriate code
        if health_data["status"] == "unhealthy":
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Health check script failed: {e}")
        traceback.print_exc()
        sys.exit(1)