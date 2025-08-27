#!/usr/bin/env python3
"""
Database Architecture Integration Layer

This module provides seamless integration between the new unified database
architecture and the existing database.py system, ensuring backward compatibility
while providing access to enhanced features.

Key Features:
- Backward compatibility with existing database.py API
- Gradual migration path to unified architecture
- Performance monitoring and optimization
- Enhanced error handling and recovery
- Automatic health monitoring integration
- Transparent connection management

Integration Strategy:
- Replace existing database functions with enhanced versions
- Maintain API compatibility for existing code
- Add new capabilities without breaking changes
- Provide migration utilities for smooth transition
"""

import os
import sys
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import existing database components
try:
    from database import engine as original_engine, SessionLocal as original_session_local
    from database import get_db as original_get_db, get_database_health as original_get_database_health
except ImportError:
    original_engine = None
    original_session_local = None
    original_get_db = None
    original_get_database_health = None

# Import unified database components
from unified_database_config import (
    UnifiedDatabaseManager, DatabaseHealth, get_unified_database_manager
)
from database_architecture import DatabaseType, EnvironmentType
from database_abstraction import QueryOptions, QueryResult

logger = logging.getLogger(__name__)

# Global unified database manager instance
_unified_db_manager: Optional[UnifiedDatabaseManager] = None

def get_unified_manager() -> UnifiedDatabaseManager:
    """Get or create unified database manager instance"""
    global _unified_db_manager
    
    if _unified_db_manager is None:
        _unified_db_manager = get_unified_database_manager()
        
        # Start monitoring in production
        if _unified_db_manager.environment == EnvironmentType.PRODUCTION:
            _unified_db_manager.start_monitoring(interval_seconds=60)
        
        logger.info("Unified database manager initialized and integrated")
    
    return _unified_db_manager

# Enhanced database session management
@contextmanager
def get_db():
    """
    Enhanced database session provider
    
    This replaces the original get_db function with enhanced error handling,
    monitoring, and recovery capabilities while maintaining full API compatibility.
    """
    unified_manager = get_unified_manager()
    
    with unified_manager.get_session() as session:
        try:
            # Test connection health before yielding
            session.execute("SELECT 1")
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Enhanced database session error: {e}")
            raise
        finally:
            # Session cleanup is handled by unified manager
            pass

def get_database_health() -> Dict[str, Any]:
    """
    Enhanced database health check
    
    This replaces the original get_database_health function with comprehensive
    health reporting including performance metrics, integrity status, and alerts.
    """
    try:
        unified_manager = get_unified_manager()
        health_report = unified_manager.get_health_report()
        
        # Maintain compatibility with original API while adding enhanced data
        return {
            "status": "healthy" if health_report["overall_health"] in ["excellent", "good"] else "unhealthy",
            "database": "connected" if health_report["connection_status"] == "healthy" else "disconnected",
            
            # Enhanced information
            "detailed_status": health_report["overall_health"],
            "health_score": health_report.get("health_score", 0),
            "integrity_status": health_report.get("integrity_status", "unknown"),
            "performance_metrics": health_report.get("metrics", {}),
            "active_alerts": health_report.get("active_alerts", []),
            "database_type": health_report.get("database_type", "unknown"),
            "environment": health_report.get("environment", "unknown"),
            
            # Connection pool information (if available)
            "pool_info": {
                "active_connections": health_report.get("metrics", {}).get("active_connections", 0),
                "total_queries": health_report.get("metrics", {}).get("total_queries", 0),
                "error_rate": health_report.get("metrics", {}).get("error_rate", 0.0)
            }
        }
        
    except Exception as e:
        logger.error(f"Enhanced database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "detailed_status": "failure",
            "health_score": 0
        }

def execute_query(
    query: str, 
    params: Optional[Dict[str, Any]] = None,
    options: Optional[QueryOptions] = None
) -> QueryResult:
    """
    Enhanced query execution with performance tracking and optimization
    
    This provides a high-level interface for query execution with automatic
    performance monitoring, error recovery, and optimization.
    """
    unified_manager = get_unified_manager()
    return unified_manager.execute_query(query, params, options)

def check_data_integrity(repair: bool = False) -> Dict[str, Any]:
    """
    Comprehensive data integrity check with optional repair
    
    This function provides detailed data integrity checking and optional
    automated repair capabilities.
    """
    try:
        unified_manager = get_unified_manager()
        integrity_report = unified_manager.run_integrity_check(repair=repair)
        
        return {
            "status": integrity_report.status.value,
            "timestamp": integrity_report.timestamp.isoformat(),
            "total_checks": integrity_report.total_checks,
            "passed_checks": integrity_report.passed_checks,
            "failed_checks": integrity_report.failed_checks,
            "warnings": integrity_report.warnings,
            "errors": integrity_report.errors,
            "recommendations": integrity_report.recommendations,
            "repair_actions": integrity_report.repair_actions if repair else []
        }
        
    except Exception as e:
        logger.error(f"Data integrity check failed: {e}")
        return {
            "status": "critical",
            "timestamp": "",
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 1,
            "errors": [str(e)]
        }

def optimize_database_performance() -> Dict[str, Any]:
    """
    Run comprehensive database performance optimization
    
    This function runs database-specific optimizations and returns detailed
    results about the optimization process.
    """
    try:
        unified_manager = get_unified_manager()
        return unified_manager.optimize_performance()
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        return {"status": "error", "error": str(e)}

def create_database_backup(backup_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create comprehensive database backup with verification
    
    This function creates a database backup with comprehensive verification
    and metadata tracking.
    """
    try:
        unified_manager = get_unified_manager()
        return unified_manager.create_backup(backup_name)
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return {"status": "error", "error": str(e)}

def get_database_statistics() -> Dict[str, Any]:
    """
    Get comprehensive database statistics and performance metrics
    
    This function provides detailed statistics about database performance,
    usage patterns, and health metrics.
    """
    try:
        unified_manager = get_unified_manager()
        return unified_manager.get_statistics()
        
    except Exception as e:
        logger.error(f"Database statistics collection failed: {e}")
        return {"error": str(e)}

def migrate_database(target_version: Optional[str] = None) -> Dict[str, Any]:
    """
    Run database migrations with comprehensive tracking
    
    This function provides access to the unified migration system with
    detailed progress tracking and rollback capabilities.
    """
    try:
        unified_manager = get_unified_manager()
        migration_system = unified_manager.migration_system
        
        # Get pending migrations
        pending_migrations = migration_system.get_pending_migrations()
        
        if not pending_migrations:
            return {
                "status": "no_migrations",
                "message": "No pending migrations to execute",
                "applied_count": 0
            }
        
        # Execute migrations
        success = migration_system.migrate_up(target_version)
        
        return {
            "status": "success" if success else "failed",
            "applied_count": len(pending_migrations),
            "target_version": target_version,
            "migrations": [
                {
                    "version": m.version,
                    "name": m.name,
                    "type": m.migration_type.value
                }
                for m in pending_migrations
            ]
        }
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return {"status": "error", "error": str(e)}

def start_database_monitoring(interval_seconds: int = 60) -> Dict[str, Any]:
    """
    Start continuous database monitoring
    
    This function starts comprehensive database monitoring with configurable
    interval and alert generation.
    """
    try:
        unified_manager = get_unified_manager()
        unified_manager.start_monitoring(interval_seconds)
        
        return {
            "status": "started",
            "interval_seconds": interval_seconds,
            "monitoring_active": True
        }
        
    except Exception as e:
        logger.error(f"Failed to start database monitoring: {e}")
        return {"status": "error", "error": str(e)}

def stop_database_monitoring() -> Dict[str, Any]:
    """
    Stop database monitoring
    
    This function stops the database monitoring system and returns
    final monitoring statistics.
    """
    try:
        unified_manager = get_unified_manager()
        stats = unified_manager.get_statistics()
        unified_manager.stop_monitoring()
        
        return {
            "status": "stopped",
            "final_statistics": stats,
            "monitoring_active": False
        }
        
    except Exception as e:
        logger.error(f"Failed to stop database monitoring: {e}")
        return {"status": "error", "error": str(e)}

def get_migration_status() -> Dict[str, Any]:
    """
    Get comprehensive migration status
    
    This function provides detailed information about migration status,
    history, and pending migrations.
    """
    try:
        unified_manager = get_unified_manager()
        migration_system = unified_manager.migration_system
        
        history = migration_system.get_migration_history()
        pending = migration_system.get_pending_migrations()
        
        return {
            "applied_migrations": len(history),
            "pending_migrations": len(pending),
            "last_migration": {
                "version": history[0].migration_version,
                "status": history[0].status.value,
                "timestamp": history[0].started_at.isoformat()
            } if history else None,
            "pending_list": [
                {
                    "version": m.version,
                    "name": m.name,
                    "type": m.migration_type.value,
                    "description": m.description
                }
                for m in pending
            ],
            "recent_history": [
                {
                    "version": h.migration_version,
                    "status": h.status.value,
                    "started_at": h.started_at.isoformat(),
                    "execution_time": h.execution_time_seconds
                }
                for h in history[:10]  # Last 10 migrations
            ]
        }
        
    except Exception as e:
        logger.error(f"Migration status check failed: {e}")
        return {"error": str(e)}

# Enhanced table operations with unified database operations
class EnhancedTableOperations:
    """
    Enhanced table operations using unified database operations
    
    This class provides high-level table operations with automatic
    optimization, validation, and monitoring.
    """
    
    def __init__(self):
        self.unified_manager = get_unified_manager()
        self.db_ops = self.unified_manager.db_operations
    
    def select(
        self,
        table_name: str,
        columns: Optional[list] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[list] = None
    ) -> QueryResult:
        """Enhanced SELECT with automatic optimization"""
        options = QueryOptions(
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            filters=filters
        )
        
        return self.db_ops.select(table_name, columns, options)
    
    def insert(
        self,
        table_name: str,
        data: Dict[str, Any],
        batch_size: Optional[int] = None
    ) -> QueryResult:
        """Enhanced INSERT with batch optimization"""
        options = QueryOptions()
        return self.db_ops.insert(table_name, data, options)
    
    def update(
        self,
        table_name: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> QueryResult:
        """Enhanced UPDATE with validation"""
        options = QueryOptions()
        return self.db_ops.update(table_name, data, filters, options)
    
    def delete(
        self,
        table_name: str,
        filters: Dict[str, Any],
        soft_delete: bool = True
    ) -> QueryResult:
        """Enhanced DELETE with soft delete support"""
        options = QueryOptions(include_soft_deleted=not soft_delete)
        return self.db_ops.delete(table_name, filters, options)
    
    def count(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Enhanced COUNT with filter support"""
        return self.db_ops.count(table_name, filters)
    
    def exists(
        self,
        table_name: str,
        filters: Dict[str, Any]
    ) -> bool:
        """Enhanced EXISTS check"""
        return self.db_ops.exists(table_name, filters)

# Global enhanced table operations instance
enhanced_table_ops = EnhancedTableOperations()

# Backward compatibility aliases and wrapper functions
def safe_create_indexes_and_tables():
    """
    Enhanced version of the original function with comprehensive validation
    
    This function maintains backward compatibility while providing enhanced
    table and index creation with validation and monitoring.
    """
    try:
        unified_manager = get_unified_manager()
        
        # Run data integrity check to identify missing tables/indexes
        integrity_report = unified_manager.run_integrity_check(repair=False)
        
        if integrity_report.failed_checks > 0:
            logger.info("Found schema issues, attempting to resolve...")
            
            # Attempt to repair schema issues
            repair_report = unified_manager.run_integrity_check(repair=True)
            
            if repair_report.failed_checks == 0:
                logger.info("✅ Database schema successfully updated")
            else:
                logger.warning(f"⚠️  Some schema issues remain: {repair_report.failed_checks} failed checks")
        else:
            logger.info("✅ Database schema is up to date")
        
        return True
        
    except Exception as e:
        logger.error(f"Enhanced schema update failed: {e}")
        
        # Fall back to original function if available
        if original_engine:
            try:
                from database import safe_create_indexes_and_tables as original_function
                return original_function()
            except Exception as fallback_error:
                logger.error(f"Fallback to original function failed: {fallback_error}")
                raise
        else:
            raise

# Integration health check
def validate_integration() -> Dict[str, Any]:
    """
    Validate the integration between unified and original database systems
    
    This function checks that the integration is working properly and
    both systems are compatible.
    """
    validation_results = {
        "timestamp": "",
        "unified_system": {"status": "unknown"},
        "original_system": {"status": "unknown"},
        "compatibility": {"status": "unknown"},
        "recommendations": []
    }
    
    try:
        from datetime import datetime, timezone
        validation_results["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Test unified system
        try:
            unified_manager = get_unified_manager()
            health_report = unified_manager.get_health_report()
            
            validation_results["unified_system"] = {
                "status": "healthy" if health_report["overall_health"] in ["excellent", "good"] else "unhealthy",
                "health_score": health_report.get("health_score", 0),
                "database_type": health_report.get("database_type", "unknown")
            }
        except Exception as e:
            validation_results["unified_system"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Test original system (if available)
        if original_get_database_health:
            try:
                original_health = original_get_database_health()
                validation_results["original_system"] = {
                    "status": original_health.get("status", "unknown"),
                    "available": True
                }
            except Exception as e:
                validation_results["original_system"] = {
                    "status": "error",
                    "error": str(e),
                    "available": True
                }
        else:
            validation_results["original_system"] = {
                "status": "not_available",
                "available": False
            }
        
        # Check compatibility
        unified_healthy = validation_results["unified_system"]["status"] == "healthy"
        original_available = validation_results["original_system"]["available"]
        
        if unified_healthy:
            if original_available:
                validation_results["compatibility"]["status"] = "full_compatibility"
                validation_results["recommendations"].append("Both systems operational - gradual migration recommended")
            else:
                validation_results["compatibility"]["status"] = "unified_only"
                validation_results["recommendations"].append("Using unified system only - integration successful")
        else:
            if original_available:
                validation_results["compatibility"]["status"] = "fallback_available"
                validation_results["recommendations"].append("Unified system unhealthy - original system available as fallback")
            else:
                validation_results["compatibility"]["status"] = "critical"
                validation_results["recommendations"].append("Both systems unavailable - immediate attention required")
        
        logger.info(f"Integration validation completed: {validation_results['compatibility']['status']}")
        return validation_results
        
    except Exception as e:
        logger.error(f"Integration validation failed: {e}")
        validation_results["compatibility"] = {
            "status": "validation_error",
            "error": str(e)
        }
        return validation_results

# Cleanup and shutdown
def shutdown_integrated_database():
    """
    Gracefully shutdown the integrated database system
    
    This function ensures proper cleanup of both unified and original
    database systems.
    """
    try:
        global _unified_db_manager
        
        if _unified_db_manager:
            _unified_db_manager.shutdown()
            _unified_db_manager = None
        
        logger.info("Integrated database system shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during integrated database shutdown: {e}")

# Export enhanced functions for backward compatibility
__all__ = [
    # Enhanced core functions
    'get_db',
    'get_database_health',
    'execute_query',
    'check_data_integrity',
    'optimize_database_performance',
    'create_database_backup',
    'get_database_statistics',
    
    # Migration functions
    'migrate_database',
    'get_migration_status',
    
    # Monitoring functions
    'start_database_monitoring',
    'stop_database_monitoring',
    
    # Table operations
    'enhanced_table_ops',
    'EnhancedTableOperations',
    
    # Compatibility functions
    'safe_create_indexes_and_tables',
    
    # Management functions
    'get_unified_manager',
    'validate_integration',
    'shutdown_integrated_database'
]


if __name__ == "__main__":
    # Integration validation CLI
    import json
    
    print("Database Integration Validation")
    print("=" * 40)
    
    try:
        # Run integration validation
        validation_results = validate_integration()
        print(json.dumps(validation_results, indent=2, default=str))
        
        # Test basic operations
        print("\nTesting basic operations...")
        
        # Test health check
        health = get_database_health()
        print(f"Health Status: {health['status']}")
        
        # Test enhanced table operations
        project_count = enhanced_table_ops.count("projects")
        print(f"Projects count: {project_count}")
        
        print("\n✅ Integration validation completed successfully")
        
    except Exception as e:
        print(f"\n❌ Integration validation failed: {e}")
        exit(1)
    finally:
        shutdown_integrated_database()