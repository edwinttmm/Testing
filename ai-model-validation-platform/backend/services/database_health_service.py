"""
Database Health Monitoring Service

Provides real-time monitoring of database connection health,
pool status, and connection management utilities.
"""

import logging
import time
from typing import Dict, Any, Optional
from sqlalchemy.exc import SQLAlchemyError, OperationalError, TimeoutError
from sqlalchemy import text
from database import engine, SessionLocal

logger = logging.getLogger(__name__)

class DatabaseHealthService:
    """Service for monitoring database health and managing connections"""
    
    def __init__(self):
        self.health_cache = {}
        self.last_check_time = 0
        self.cache_ttl = 30  # Cache health status for 30 seconds
        
    def get_connection_pool_status(self) -> Dict[str, Any]:
        """
        Get detailed connection pool status
        
        Returns:
            Dictionary with pool status information
        """
        try:
            pool_status = {
                "status": "healthy",
                "timestamp": time.time()
            }
            
            # Get pool information if available
            if hasattr(engine, 'pool') and engine.pool is not None:
                try:
                    pool = engine.pool
                    pool_status.update({
                        "pool_size": pool.size(),
                        "checked_out_connections": pool.checkedout(),
                        "overflow_connections": pool.overflow(),
                        "checked_in_connections": pool.checkedin(),
                        "invalid_connections": getattr(pool, '_invalidated', 0)
                    })
                    
                    # Calculate utilization
                    total_connections = pool_status["checked_out_connections"] + pool_status["checked_in_connections"]
                    max_connections = pool.size() + pool.overflow()
                    pool_status["utilization_percentage"] = (total_connections / max_connections * 100) if max_connections > 0 else 0
                    
                    # Health assessment
                    if pool_status["utilization_percentage"] > 90:
                        pool_status["status"] = "high_utilization"
                    elif pool_status["utilization_percentage"] > 70:
                        pool_status["status"] = "moderate_utilization"
                    else:
                        pool_status["status"] = "healthy"
                        
                except Exception as pool_error:
                    logger.warning(f"Could not get pool details: {pool_error}")
                    pool_status["status"] = "unknown"
                    pool_status["error"] = str(pool_error)
            else:
                pool_status["pool_type"] = "sqlite"
                pool_status["status"] = "healthy"
                
            return pool_status
            
        except Exception as e:
            logger.error(f"Failed to get connection pool status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def test_database_connectivity(self) -> Dict[str, Any]:
        """
        Test database connectivity with detailed diagnostics
        
        Returns:
            Dictionary with connectivity test results
        """
        start_time = time.time()
        
        try:
            # Test basic connection
            with engine.connect() as connection:
                # Simple query test
                result = connection.execute(text("SELECT 1"))
                query_time = time.time() - start_time
                
                # More comprehensive test
                tables_result = connection.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table'" if engine.url.drivername == 'sqlite'
                    else "SELECT table_name FROM information_schema.tables WHERE table_schema='public' LIMIT 5"
                ))
                tables = [row[0] for row in tables_result.fetchall()]
                
                return {
                    "status": "healthy",
                    "connection_time_ms": round(query_time * 1000, 2),
                    "query_successful": True,
                    "tables_accessible": len(tables) > 0,
                    "table_count": len(tables),
                    "timestamp": time.time()
                }
                
        except (OperationalError, TimeoutError) as conn_error:
            error_time = time.time() - start_time
            logger.error(f"Database connectivity test failed: {conn_error}")
            return {
                "status": "connection_failed",
                "error": str(conn_error),
                "connection_time_ms": round(error_time * 1000, 2),
                "query_successful": False,
                "timestamp": time.time()
            }
            
        except SQLAlchemyError as db_error:
            error_time = time.time() - start_time
            logger.error(f"Database query test failed: {db_error}")
            return {
                "status": "query_failed",
                "error": str(db_error),
                "connection_time_ms": round(error_time * 1000, 2),
                "query_successful": False,
                "timestamp": time.time()
            }
            
        except Exception as e:
            error_time = time.time() - start_time
            logger.error(f"Database connectivity test error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "connection_time_ms": round(error_time * 1000, 2),
                "query_successful": False,
                "timestamp": time.time()
            }
    
    def get_comprehensive_health_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive database health status with caching
        
        Args:
            force_refresh: Force refresh of cached status
            
        Returns:
            Dictionary with comprehensive health information
        """
        current_time = time.time()
        
        # Return cached status if still valid
        if not force_refresh and self.health_cache and (current_time - self.last_check_time) < self.cache_ttl:
            return self.health_cache
        
        logger.info("Performing comprehensive database health check")
        
        # Get connectivity status
        connectivity = self.test_database_connectivity()
        
        # Get pool status
        pool_status = self.get_connection_pool_status()
        
        # Combine into comprehensive status
        health_status = {
            "overall_status": "healthy",
            "connectivity": connectivity,
            "pool_status": pool_status,
            "timestamp": current_time,
            "cache_ttl_seconds": self.cache_ttl
        }
        
        # Determine overall status
        if connectivity["status"] != "healthy":
            health_status["overall_status"] = "unhealthy"
        elif pool_status["status"] == "high_utilization":
            health_status["overall_status"] = "degraded"
        elif pool_status["status"] in ["moderate_utilization", "unknown"]:
            health_status["overall_status"] = "warning"
        
        # Cache the result
        self.health_cache = health_status
        self.last_check_time = current_time
        
        return health_status
    
    def cleanup_stale_connections(self) -> Dict[str, Any]:
        """
        Attempt to cleanup stale database connections
        
        Returns:
            Dictionary with cleanup results
        """
        try:
            cleanup_result = {
                "cleanup_attempted": True,
                "timestamp": time.time()
            }
            
            if hasattr(engine, 'pool') and engine.pool is not None:
                # Get pre-cleanup status
                pre_cleanup = self.get_connection_pool_status()
                
                # Dispose of the pool to cleanup stale connections
                engine.pool.dispose()
                
                # Wait a moment for cleanup
                time.sleep(0.5)
                
                # Get post-cleanup status
                post_cleanup = self.get_connection_pool_status()
                
                cleanup_result.update({
                    "pre_cleanup_checked_out": pre_cleanup.get("checked_out_connections", 0),
                    "post_cleanup_checked_out": post_cleanup.get("checked_out_connections", 0),
                    "connections_cleaned": max(0, pre_cleanup.get("checked_out_connections", 0) - post_cleanup.get("checked_out_connections", 0)),
                    "cleanup_successful": True
                })
                
            else:
                cleanup_result["cleanup_successful"] = False
                cleanup_result["reason"] = "No connection pool available for cleanup"
            
            return cleanup_result
            
        except Exception as e:
            logger.error(f"Connection cleanup failed: {e}")
            return {
                "cleanup_attempted": True,
                "cleanup_successful": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def monitor_connection_leaks(self) -> Dict[str, Any]:
        """
        Monitor for potential connection leaks
        
        Returns:
            Dictionary with leak detection results
        """
        try:
            pool_status = self.get_connection_pool_status()
            
            leak_analysis = {
                "monitoring_enabled": True,
                "timestamp": time.time()
            }
            
            if "checked_out_connections" in pool_status:
                checked_out = pool_status["checked_out_connections"]
                utilization = pool_status.get("utilization_percentage", 0)
                
                # Simple leak detection heuristics
                if checked_out > 10 and utilization > 80:
                    leak_analysis["potential_leak"] = True
                    leak_analysis["severity"] = "high"
                    leak_analysis["recommendation"] = "Investigate connection usage patterns"
                elif checked_out > 5 and utilization > 60:
                    leak_analysis["potential_leak"] = True
                    leak_analysis["severity"] = "moderate"
                    leak_analysis["recommendation"] = "Monitor connection lifecycle"
                else:
                    leak_analysis["potential_leak"] = False
                    leak_analysis["severity"] = "none"
                
                leak_analysis.update({
                    "checked_out_connections": checked_out,
                    "utilization_percentage": utilization
                })
            else:
                leak_analysis["potential_leak"] = False
                leak_analysis["reason"] = "No pool information available"
            
            return leak_analysis
            
        except Exception as e:
            logger.error(f"Connection leak monitoring failed: {e}")
            return {
                "monitoring_enabled": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_database_diagnostics(self) -> Dict[str, Any]:
        """
        Get comprehensive database diagnostics
        
        Returns:
            Dictionary with diagnostic information
        """
        return {
            "health_status": self.get_comprehensive_health_status(),
            "leak_monitoring": self.monitor_connection_leaks(),
            "engine_info": {
                "driver": engine.driver,
                "dialect": str(engine.dialect),
                "url_database": engine.url.database,
                "url_drivername": engine.url.drivername
            }
        }

# Global instance
database_health_service = DatabaseHealthService()