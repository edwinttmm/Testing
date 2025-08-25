#!/usr/bin/env python3

"""
Health Check Endpoint for Docker Container
This module provides health check functionality for the backend container
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and health"""
    try:
        from database import engine, get_database_health
        from sqlalchemy import text
        
        # Test basic connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            
        # Get detailed health info
        health_info = get_database_health()
        
        return {
            "status": "healthy",
            "database": health_info.get("database", "connected"),
            "details": health_info
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and health"""
    try:
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
            "redis": "connected"
        }
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy", 
            "redis": "disconnected",
            "error": str(e)
        }

def check_file_system_health() -> Dict[str, Any]:
    """Check file system and required directories"""
    try:
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
            "directories": dir_status
        }
        
    except Exception as e:
        logger.error(f"File system health check failed: {e}")
        return {
            "status": "unhealthy",
            "filesystem": "error",
            "error": str(e)
        }

def check_network_connectivity() -> Dict[str, Any]:
    """Check network connectivity to other services"""
    try:
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
            "services": connectivity_status
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

def comprehensive_health_check() -> Dict[str, Any]:
    """Run comprehensive health check"""
    logger.info("Starting comprehensive health check...")
    
    # Individual health checks
    database_health = check_database_health()
    redis_health = check_redis_health()
    filesystem_health = check_file_system_health()
    network_health = check_network_connectivity()
    system_info = get_system_info()
    
    # Determine overall health
    all_checks = [database_health, redis_health, filesystem_health, network_health]
    healthy_checks = [check for check in all_checks if check.get("status") == "healthy"]
    degraded_checks = [check for check in all_checks if check.get("status") == "degraded"]
    
    if len(healthy_checks) == len(all_checks):
        overall_status = "healthy"
        overall_message = "All systems operational"
    elif len(healthy_checks) + len(degraded_checks) == len(all_checks):
        overall_status = "degraded"
        overall_message = "Some systems have issues but service is functional"
    else:
        overall_status = "unhealthy"
        overall_message = "Critical systems are down"
    
    # Build response
    health_response = {
        "status": overall_status,
        "message": overall_message,
        "timestamp": str(asyncio.get_event_loop().time()),
        "checks": {
            "database": database_health,
            "redis": redis_health,
            "filesystem": filesystem_health,
            "network": network_health
        },
        "system": system_info,
        "environment": {
            "docker_mode": os.getenv('AIVALIDATION_DOCKER_MODE', 'false'),
            "app_environment": os.getenv('AIVALIDATION_APP_ENVIRONMENT', 'development'),
        }
    }
    
    logger.info(f"Health check completed: {overall_status}")
    return health_response

# FastAPI app for health endpoint (if this file is imported by main.py)
def add_health_routes(app: FastAPI):
    """Add health check routes to FastAPI app"""
    
    @app.get("/health")
    async def health_check():
        """Basic health check endpoint"""
        try:
            health_data = comprehensive_health_check()
            
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
    try:
        health_data = comprehensive_health_check()
        
        # Print results
        import json
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