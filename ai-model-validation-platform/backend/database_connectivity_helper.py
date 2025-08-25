"""
Database Connectivity Helper
Handles PostgreSQL connection issues for both Docker and non-Docker environments
"""
import os
import socket
import time
import logging
from typing import Optional, Dict, Any
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError

logger = logging.getLogger(__name__)

class DatabaseConnectivityHelper:
    """Helper class to manage database connectivity issues"""
    
    def __init__(self):
        self.docker_mode = os.getenv("AIVALIDATION_DOCKER_MODE", "false").lower() == "true"
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "vru_validation")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "secure_password_change_me")
        self.postgres_host = self._determine_postgres_host()
        
    def _determine_postgres_host(self) -> str:
        """Determine the correct PostgreSQL host based on environment"""
        if self.docker_mode:
            # Inside Docker, use the service name
            return "postgres"
        else:
            # Outside Docker, try localhost first, then check environment
            host_candidates = [
                os.getenv("POSTGRES_HOST", "localhost"),
                "localhost",
                "127.0.0.1"
            ]
            
            for host in host_candidates:
                if self._can_connect_to_host(host):
                    logger.info(f"Using PostgreSQL host: {host}")
                    return host
            
            logger.warning(f"Cannot connect to any PostgreSQL host candidates: {host_candidates}")
            return "localhost"  # Fallback
    
    def _can_connect_to_host(self, host: str, timeout: int = 5) -> bool:
        """Check if we can connect to a PostgreSQL host"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, self.postgres_port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Cannot connect to {host}:{self.postgres_port}: {e}")
            return False
    
    def get_database_url(self) -> str:
        """Get the appropriate database URL for the current environment"""
        # Check if custom DATABASE_URL is set
        custom_url = os.getenv("DATABASE_URL") or os.getenv("AIVALIDATION_DATABASE_URL")
        if custom_url and not custom_url.startswith("sqlite"):
            # Validate the custom URL can connect
            if self._test_database_url(custom_url):
                return custom_url
            else:
                logger.warning(f"Custom DATABASE_URL failed connectivity test: {custom_url}")
        
        # Build PostgreSQL URL with detected host
        db_url = f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        
        if self._test_database_url(db_url):
            return db_url
        else:
            logger.error(f"Cannot connect to PostgreSQL at {self.postgres_host}. Falling back to SQLite.")
            return "sqlite:///./fallback_database.db"
    
    def _test_database_url(self, url: str, timeout: int = 10) -> bool:
        """Test if a database URL is connectable"""
        if url.startswith("sqlite"):
            return True  # SQLite doesn't require network connectivity
        
        try:
            engine = create_engine(
                url, 
                pool_pre_ping=True,
                pool_timeout=timeout,
                connect_args={"connect_timeout": timeout}
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return True
        except Exception as e:
            logger.debug(f"Database URL test failed for {url}: {e}")
            return False
    
    def wait_for_database(self, max_attempts: int = 30, delay: int = 2) -> bool:
        """Wait for database to become available"""
        db_url = self.get_database_url()
        
        if db_url.startswith("sqlite"):
            return True  # SQLite is always available
        
        logger.info(f"Waiting for database to become available at {self.postgres_host}...")
        
        for attempt in range(max_attempts):
            if self._test_database_url(db_url):
                logger.info(f"Database connection successful after {attempt + 1} attempts")
                return True
            
            if attempt < max_attempts - 1:
                logger.info(f"Database not ready (attempt {attempt + 1}/{max_attempts}), retrying in {delay}s...")
                time.sleep(delay)
        
        logger.error(f"Database failed to become available after {max_attempts} attempts")
        return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for debugging"""
        return {
            "docker_mode": self.docker_mode,
            "postgres_host": self.postgres_host,
            "postgres_port": self.postgres_port,
            "postgres_db": self.postgres_db,
            "postgres_user": self.postgres_user,
            "database_url": self.get_database_url().replace(self.postgres_password, "***"),
            "host_connectivity": self._can_connect_to_host(self.postgres_host),
        }
    
    def diagnose_connectivity(self) -> Dict[str, Any]:
        """Comprehensive connectivity diagnosis"""
        diagnosis = {
            "environment": {
                "docker_mode": self.docker_mode,
                "env_vars": {
                    "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
                    "AIVALIDATION_DATABASE_URL": bool(os.getenv("AIVALIDATION_DATABASE_URL")),
                    "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
                    "AIVALIDATION_DOCKER_MODE": os.getenv("AIVALIDATION_DOCKER_MODE"),
                }
            },
            "connectivity": {
                "postgres_host": self.postgres_host,
                "postgres_port": self.postgres_port,
                "host_reachable": self._can_connect_to_host(self.postgres_host),
            },
            "database": {
                "url": self.get_database_url().replace(self.postgres_password, "***"),
                "connection_test": self._test_database_url(self.get_database_url()),
            },
            "recommendations": []
        }
        
        # Add recommendations based on diagnosis
        if not diagnosis["connectivity"]["host_reachable"]:
            if self.docker_mode:
                diagnosis["recommendations"].append(
                    "PostgreSQL container may not be running or not in same Docker network"
                )
            else:
                diagnosis["recommendations"].append(
                    "PostgreSQL server may not be running on localhost:5432"
                )
        
        if not diagnosis["database"]["connection_test"]:
            diagnosis["recommendations"].append(
                "Check PostgreSQL credentials and database existence"
            )
        
        return diagnosis

# Global helper instance
db_helper = DatabaseConnectivityHelper()

def get_enhanced_database_url() -> str:
    """Get database URL with enhanced connectivity handling"""
    return db_helper.get_database_url()

def wait_for_database_startup(max_attempts: int = 30) -> bool:
    """Wait for database to be ready during startup"""
    return db_helper.wait_for_database(max_attempts)

def diagnose_database_connectivity() -> Dict[str, Any]:
    """Get comprehensive database connectivity diagnosis"""
    return db_helper.diagnose_connectivity()