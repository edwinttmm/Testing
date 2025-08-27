#!/usr/bin/env python3
"""
Unified Database Architecture for VRU AI Model Validation Platform
Supports both SQLite and PostgreSQL with unified configuration
"""

import os
import logging
from typing import Generator, Dict, Any, Optional, List
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

# Import unified configuration
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from config.vru_settings import get_settings, DatabaseType
except ImportError:
    # Fallback import paths
    try:
        config_path = project_root / "config"
        sys.path.insert(0, str(config_path))
        from vru_settings import get_settings, DatabaseType
    except ImportError:
        # Final fallback - create minimal settings
        from enum import Enum
        
        class DatabaseType(Enum):
            SQLITE = "sqlite"
            POSTGRESQL = "postgresql"
        
        class MinimalSettings:
            def __init__(self):
                self.database_url = os.getenv("DATABASE_URL", "sqlite:///./dev_database.db")
                self.database_type = DatabaseType.SQLITE if self.database_url.startswith("sqlite") else DatabaseType.POSTGRESQL
                self.database_echo = False
                self.database_pool_size = 10
                self.database_max_overflow = 20
            
            def is_sqlite(self):
                return self.database_type == DatabaseType.SQLITE
        
        def get_settings():
            return MinimalSettings()

logger = logging.getLogger(__name__)

class UnifiedDatabaseManager:
    """Unified database manager supporting both SQLite and PostgreSQL"""
    
    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._session_factory = None
        self._setup_database()
    
    def _setup_database(self):
        """Setup database engine and session factory"""
        database_url = self.settings.database_url
        
        if self.settings.is_sqlite():
            # SQLite specific configuration
            engine_kwargs = {
                "poolclass": StaticPool,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 30,
                },
                "echo": self.settings.database_echo,
                "echo_pool": False,
            }
            
            # Ensure database directory exists
            db_path = database_url.replace('sqlite:///', '')
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
        else:  # PostgreSQL
            # PostgreSQL specific configuration
            engine_kwargs = {
                "pool_size": self.settings.database_pool_size,
                "max_overflow": self.settings.database_max_overflow,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "echo": self.settings.database_echo,
                "echo_pool": False,
            }
        
        self._engine = create_engine(database_url, **engine_kwargs)
        
        # Setup SQLite optimizations
        if self.settings.is_sqlite():
            self._setup_sqlite_optimizations()
        
        # Create session factory
        self._session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine
        )
        
        logger.info(f"Database configured: {self.settings.database_type.value} at {database_url}")
    
    def _setup_sqlite_optimizations(self):
        """Setup SQLite performance optimizations"""
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            # Increase cache size (negative value = KB)
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Enable memory-mapped I/O
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
            # Optimize synchronous mode
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")
            # Optimize temp storage
            cursor.execute("PRAGMA temp_store=memory")
            cursor.close()
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with proper error handling"""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()
    
    def get_engine(self) -> Engine:
        """Get database engine"""
        return self._engine
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return health info"""
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1")).fetchone()
                
                # Get database info
                info = {
                    "status": "healthy",
                    "database_type": self.settings.database_type.value,
                    "database_url": self.settings.database_url.split('@')[-1] if '@' in self.settings.database_url else self.settings.database_url,
                    "connection_test": "passed" if result and result[0] == 1 else "failed",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                # Add database-specific info
                if self.settings.is_sqlite():
                    info.update(self._get_sqlite_info(session))
                else:
                    info.update(self._get_postgresql_info(session))
                
                return info
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_type": self.settings.database_type.value,
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _get_sqlite_info(self, session: Session) -> Dict[str, Any]:
        """Get SQLite-specific information"""
        try:
            pragma_queries = [
                ("journal_mode", "PRAGMA journal_mode"),
                ("cache_size", "PRAGMA cache_size"),
                ("synchronous", "PRAGMA synchronous"),
                ("foreign_keys", "PRAGMA foreign_keys"),
            ]
            
            info = {}
            for key, query in pragma_queries:
                result = session.execute(text(query)).fetchone()
                info[f"sqlite_{key}"] = result[0] if result else "unknown"
            
            return info
        except Exception as e:
            logger.warning(f"Failed to get SQLite info: {str(e)}")
            return {}
    
    def _get_postgresql_info(self, session: Session) -> Dict[str, Any]:
        """Get PostgreSQL-specific information"""
        try:
            version_result = session.execute(text("SELECT version()")).fetchone()
            return {
                "postgresql_version": version_result[0] if version_result else "unknown"
            }
        except Exception as e:
            logger.warning(f"Failed to get PostgreSQL info: {str(e)}")
            return {}
    
    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        try:
            inspector = inspect(self._engine)
            return inspector.get_table_names()
        except Exception as e:
            logger.error(f"Failed to get table list: {str(e)}")
            return []
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute raw query and return results"""
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params or {})
                if result.returns_rows:
                    return [dict(row._mapping) for row in result]
                return []
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise


# Global database manager instance
_db_manager = None

def get_database_manager() -> UnifiedDatabaseManager:
    """Get or create global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = UnifiedDatabaseManager()
    return _db_manager

# Backward compatibility functions
def get_db() -> Generator[Session, None, None]:
    """Backward compatible database session getter"""
    db_manager = get_database_manager()
    with db_manager.get_session() as session:
        yield session

def get_database_health() -> Dict[str, Any]:
    """Get database health status"""
    db_manager = get_database_manager()
    return db_manager.test_connection()

def get_database_engine():
    """Get database engine for advanced operations"""
    db_manager = get_database_manager()
    return db_manager.get_engine()


if __name__ == "__main__":
    # Test database connection
    print("🔧 Testing Unified Database Connection")
    print("=" * 50)
    
    db_manager = get_database_manager()
    health = db_manager.test_connection()
    
    print(f"Status: {health['status']}")
    print(f"Database Type: {health['database_type']}")
    print(f"Connection Test: {health.get('connection_test', 'N/A')}")
    
    if health['status'] == 'healthy':
        tables = db_manager.get_tables()
        print(f"Tables: {', '.join(tables) if tables else 'None found'}")
        
        # Test query
        try:
            print("\n🔍 Testing Query Execution...")
            results = db_manager.execute_query("SELECT COUNT(*) as count FROM projects")
            if results:
                print(f"Projects count: {results[0]['count']}")
            else:
                print("No results returned")
        except Exception as e:
            print(f"Query test failed: {str(e)}")
    else:
        print(f"Error: {health.get('error', 'Unknown error')}")
    
    print("=" * 50)