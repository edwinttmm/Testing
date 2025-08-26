#!/usr/bin/env python3
"""
Docker-optimized database configuration
Solves SQLite access issues in Docker containers
"""
import os
import sys
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DockerDatabaseConfig:
    """Enhanced database configuration for Docker environments"""
    
    def __init__(self):
        self.database_path = "/app/dev_database.db"
        self.backup_path = "/app/dev_database.db.backup"
        self.is_docker = os.getenv('AIVALIDATION_DOCKER_MODE', 'false').lower() == 'true'
        
    def ensure_database_accessibility(self) -> bool:
        """Ensure the SQLite database is accessible in Docker"""
        try:
            logger.info("🔍 Checking database accessibility in Docker...")
            
            # Check if database file exists
            db_path = Path(self.database_path)
            if not db_path.exists():
                logger.warning(f"⚠️  Database file not found at {self.database_path}")
                
                # Try alternative locations
                alternative_paths = [
                    "/app/backend/dev_database.db",
                    "./dev_database.db",
                    "./backend/dev_database.db"
                ]
                
                for alt_path in alternative_paths:
                    if Path(alt_path).exists():
                        logger.info(f"📁 Found database at {alt_path}, creating symlink...")
                        db_path.symlink_to(Path(alt_path).resolve())
                        break
                else:
                    logger.warning("Creating new empty database file...")
                    self._create_empty_database()
            
            # Verify database is readable and writable
            if not self._test_database_rw():
                logger.error("❌ Database file is not readable/writable")
                return False
                
            logger.info("✅ Database accessibility verified")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database accessibility check failed: {e}")
            return False
    
    def _create_empty_database(self) -> None:
        """Create an empty SQLite database with proper structure"""
        try:
            # Create database file
            conn = sqlite3.connect(self.database_path)
            conn.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL;")  # Optimize for Docker
            conn.execute("PRAGMA cache_size=10000;")  # Increase cache size
            conn.execute("PRAGMA temp_store=MEMORY;")  # Use memory for temp tables
            conn.close()
            
            # Set proper permissions
            os.chmod(self.database_path, 0o664)
            logger.info(f"✅ Created empty database at {self.database_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create empty database: {e}")
            raise
    
    def _test_database_rw(self) -> bool:
        """Test database read/write access"""
        try:
            conn = sqlite3.connect(self.database_path)
            
            # Test write access
            conn.execute("CREATE TABLE IF NOT EXISTS docker_test (id INTEGER)")
            conn.execute("INSERT OR REPLACE INTO docker_test (id) VALUES (1)")
            conn.commit()
            
            # Test read access
            result = conn.execute("SELECT id FROM docker_test WHERE id = 1").fetchone()
            
            # Cleanup
            conn.execute("DROP TABLE IF EXISTS docker_test")
            conn.commit()
            conn.close()
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Database R/W test failed: {e}")
            return False
    
    def get_optimized_database_url(self) -> str:
        """Get optimized database URL for Docker environment"""
        if self.is_docker:
            # Use absolute path in Docker
            return f"sqlite:///{self.database_path}"
        else:
            # Use relative path for development
            return "sqlite:///./dev_database.db"
    
    def get_connection_args(self) -> Dict[str, Any]:
        """Get optimized connection arguments for SQLite in Docker"""
        return {
            "check_same_thread": False,
            "timeout": 30.0,  # Increase timeout for Docker I/O
            "isolation_level": None,  # Enable autocommit mode
        }
    
    def setup_database_pragmas(self, connection) -> None:
        """Set up SQLite pragmas for optimal Docker performance"""
        pragmas = [
            "PRAGMA journal_mode=WAL",        # Write-Ahead Logging for better concurrency
            "PRAGMA synchronous=NORMAL",       # Balanced safety/performance
            "PRAGMA cache_size=10000",        # 10MB cache
            "PRAGMA temp_store=MEMORY",       # Use memory for temporary tables
            "PRAGMA mmap_size=268435456",     # 256MB memory-mapped I/O
            "PRAGMA optimize",                # Optimize query planner
        ]
        
        for pragma in pragmas:
            try:
                connection.execute(pragma)
                logger.debug(f"Applied pragma: {pragma}")
            except Exception as e:
                logger.warning(f"Failed to apply pragma {pragma}: {e}")
    
    def diagnose_database_issues(self) -> Dict[str, Any]:
        """Comprehensive database diagnostics for Docker"""
        diagnosis = {
            "status": "unknown",
            "issues": [],
            "recommendations": [],
            "file_info": {},
            "connection_test": False,
        }
        
        try:
            # File system checks
            db_path = Path(self.database_path)
            if db_path.exists():
                stat = db_path.stat()
                diagnosis["file_info"] = {
                    "exists": True,
                    "size": stat.st_size,
                    "permissions": oct(stat.st_mode)[-3:],
                    "owner_uid": stat.st_uid,
                    "group_gid": stat.st_gid,
                    "readable": os.access(self.database_path, os.R_OK),
                    "writable": os.access(self.database_path, os.W_OK),
                }
            else:
                diagnosis["file_info"]["exists"] = False
                diagnosis["issues"].append("Database file does not exist")
            
            # Connection test
            if db_path.exists():
                diagnosis["connection_test"] = self._test_database_rw()
                if not diagnosis["connection_test"]:
                    diagnosis["issues"].append("Database connection test failed")
            
            # Docker-specific checks
            if self.is_docker:
                # Check container permissions
                try:
                    import pwd, grp
                    current_uid = os.getuid()
                    current_gid = os.getgid()
                    
                    diagnosis["container_info"] = {
                        "current_uid": current_uid,
                        "current_gid": current_gid,
                        "user_name": pwd.getpwuid(current_uid).pw_name,
                        "group_name": grp.getgrgid(current_gid).gr_name,
                    }
                    
                    # Check if container user matches file permissions
                    if db_path.exists():
                        file_uid = diagnosis["file_info"]["owner_uid"]
                        if file_uid != current_uid:
                            diagnosis["issues"].append(
                                f"File owner UID ({file_uid}) doesn't match container UID ({current_uid})"
                            )
                            diagnosis["recommendations"].append(
                                "Run container with --user $(id -u):$(id -g) or fix volume mounting"
                            )
                    
                except Exception as e:
                    diagnosis["issues"].append(f"Failed to check container permissions: {e}")
            
            # Determine overall status
            if not diagnosis["issues"]:
                diagnosis["status"] = "healthy"
            elif diagnosis["connection_test"]:
                diagnosis["status"] = "warning"
            else:
                diagnosis["status"] = "error"
                
        except Exception as e:
            diagnosis["status"] = "error"
            diagnosis["issues"].append(f"Diagnosis failed: {e}")
        
        return diagnosis

def get_docker_database_config() -> DockerDatabaseConfig:
    """Get Docker database configuration instance"""
    return DockerDatabaseConfig()

def validate_docker_database() -> bool:
    """Validate database configuration for Docker deployment"""
    config = get_docker_database_config()
    
    logger.info("🔍 Validating Docker database configuration...")
    
    # Run diagnostics
    diagnosis = config.diagnose_database_issues()
    
    # Log results
    logger.info(f"Database status: {diagnosis['status']}")
    
    if diagnosis["issues"]:
        logger.warning("Issues found:")
        for issue in diagnosis["issues"]:
            logger.warning(f"  ⚠️  {issue}")
    
    if diagnosis["recommendations"]:
        logger.info("Recommendations:")
        for rec in diagnosis["recommendations"]:
            logger.info(f"  💡 {rec}")
    
    # Ensure accessibility
    if diagnosis["status"] != "healthy":
        logger.info("Attempting to fix database accessibility...")
        if config.ensure_database_accessibility():
            logger.info("✅ Database accessibility fixed")
            return True
        else:
            logger.error("❌ Failed to fix database accessibility")
            return False
    
    logger.info("✅ Database configuration is valid for Docker")
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = validate_docker_database()
    sys.exit(0 if success else 1)