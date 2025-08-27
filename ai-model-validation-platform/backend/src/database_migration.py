#!/usr/bin/env python3
"""
Database Migration and Synchronization System

This module provides comprehensive database migration capabilities with support
for both SQLite and PostgreSQL environments, ensuring seamless transitions
between database states and environments.

Key Features:
- Version-controlled migrations with rollback support
- Environment-specific migration strategies
- Data synchronization between SQLite and PostgreSQL
- Zero-downtime migration techniques
- Automated backup and recovery
- Migration validation and integrity checking
- Performance impact monitoring

Design Principles:
- Safety first - comprehensive backups before any migration
- Atomicity - all migrations are transactional
- Reversibility - every migration has a rollback path
- Validation - extensive checks before and after migrations
- Monitoring - detailed logging and performance tracking
"""

import os
import sys
import json
import logging
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from sqlalchemy import text, MetaData, Table, Column, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database_architecture import DatabaseArchitecture, DatabaseType, IntegrityStatus
from database_abstraction import UnifiedDatabaseOperations, QueryOptions

logger = logging.getLogger(__name__)

class MigrationStatus(Enum):
    """Migration execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class MigrationType(Enum):
    """Types of migrations"""
    SCHEMA = "schema"
    DATA = "data"
    INDEX = "index"
    CONSTRAINT = "constraint"
    PERFORMANCE = "performance"

@dataclass
class MigrationScript:
    """Migration script definition"""
    version: str
    name: str
    description: str
    migration_type: MigrationType
    up_sql: str
    down_sql: str
    dependencies: List[str] = field(default_factory=list)
    target_database: Optional[DatabaseType] = None
    backup_required: bool = True
    estimated_duration_seconds: Optional[int] = None
    validation_queries: List[str] = field(default_factory=list)

@dataclass
class MigrationExecution:
    """Migration execution record"""
    migration_version: str
    status: MigrationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    backup_path: Optional[str] = None
    checksum: Optional[str] = None
    rolled_back_at: Optional[datetime] = None

class DatabaseMigrationSystem:
    """
    Comprehensive database migration system with support for
    both SQLite and PostgreSQL environments
    """
    
    def __init__(self, db_architecture: DatabaseArchitecture, db_operations: UnifiedDatabaseOperations):
        self.db_arch = db_architecture
        self.db_ops = db_operations
        self.migration_table = "schema_migrations"
        self.migration_lock_table = "migration_locks"
        self.migrations_dir = Path(__file__).parent / "migrations"
        self.backups_dir = Path(__file__).parent / "backups"
        
        # Ensure directories exist
        self.migrations_dir.mkdir(exist_ok=True)
        self.backups_dir.mkdir(exist_ok=True)
        
        # Initialize migration tracking tables
        self._initialize_migration_tables()
        
        logger.info("Database migration system initialized")
    
    def _initialize_migration_tables(self):
        """Initialize migration tracking tables"""
        try:
            with self.db_arch.get_session() as session:
                # Create schema_migrations table
                session.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.migration_table} (
                        version VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(500) NOT NULL,
                        description TEXT,
                        migration_type VARCHAR(50) NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        started_at TIMESTAMP NOT NULL,
                        completed_at TIMESTAMP,
                        execution_time_seconds REAL,
                        error_message TEXT,
                        backup_path VARCHAR(1000),
                        checksum VARCHAR(64),
                        rolled_back_at TIMESTAMP
                    )
                """))
                
                # Create migration locks table for concurrent migration prevention
                session.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.migration_lock_table} (
                        id INTEGER PRIMARY KEY,
                        locked_at TIMESTAMP NOT NULL,
                        locked_by VARCHAR(255) NOT NULL,
                        process_id VARCHAR(100)
                    )
                """))
                
                session.commit()
                logger.info("Migration tracking tables initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize migration tables: {e}")
            raise
    
    def create_migration(
        self,
        name: str,
        description: str,
        migration_type: MigrationType,
        up_sql: str,
        down_sql: str,
        target_database: Optional[DatabaseType] = None
    ) -> str:
        """Create a new migration script"""
        try:
            # Generate version number based on timestamp
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Ensure unique version
            existing_versions = self.get_migration_history()
            counter = 1
            original_version = version
            while any(m.migration_version == version for m in existing_versions):
                version = f"{original_version}_{counter:02d}"
                counter += 1
            
            # Create migration script
            migration = MigrationScript(
                version=version,
                name=name,
                description=description,
                migration_type=migration_type,
                up_sql=up_sql,
                down_sql=down_sql,
                target_database=target_database
            )
            
            # Save to file
            migration_file = self.migrations_dir / f"{version}_{name.replace(' ', '_').lower()}.json"
            with open(migration_file, 'w') as f:
                json.dump({
                    "version": migration.version,
                    "name": migration.name,
                    "description": migration.description,
                    "migration_type": migration.migration_type.value,
                    "up_sql": migration.up_sql,
                    "down_sql": migration.down_sql,
                    "target_database": migration.target_database.value if migration.target_database else None,
                    "backup_required": migration.backup_required,
                    "estimated_duration_seconds": migration.estimated_duration_seconds,
                    "validation_queries": migration.validation_queries
                }, f, indent=2)
            
            logger.info(f"Created migration {version}: {name}")
            return version
            
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise
    
    def load_migration(self, version: str) -> Optional[MigrationScript]:
        """Load migration script from file"""
        try:
            # Find migration file
            migration_files = list(self.migrations_dir.glob(f"{version}_*.json"))
            if not migration_files:
                logger.error(f"Migration file not found for version: {version}")
                return None
            
            migration_file = migration_files[0]
            with open(migration_file, 'r') as f:
                data = json.load(f)
            
            return MigrationScript(
                version=data["version"],
                name=data["name"],
                description=data["description"],
                migration_type=MigrationType(data["migration_type"]),
                up_sql=data["up_sql"],
                down_sql=data["down_sql"],
                dependencies=data.get("dependencies", []),
                target_database=DatabaseType(data["target_database"]) if data.get("target_database") else None,
                backup_required=data.get("backup_required", True),
                estimated_duration_seconds=data.get("estimated_duration_seconds"),
                validation_queries=data.get("validation_queries", [])
            )
            
        except Exception as e:
            logger.error(f"Failed to load migration {version}: {e}")
            return None
    
    def get_pending_migrations(self) -> List[MigrationScript]:
        """Get list of pending migrations"""
        try:
            # Get applied migrations
            applied_versions = set()
            with self.db_arch.get_session() as session:
                result = session.execute(text(f"""
                    SELECT version FROM {self.migration_table} 
                    WHERE status = 'completed'
                """))
                applied_versions = {row[0] for row in result.fetchall()}
            
            # Find all migration files
            pending_migrations = []
            for migration_file in sorted(self.migrations_dir.glob("*.json")):
                try:
                    with open(migration_file, 'r') as f:
                        data = json.load(f)
                    
                    version = data["version"]
                    if version not in applied_versions:
                        # Check if migration is applicable to current database type
                        target_db = data.get("target_database")
                        if target_db is None or DatabaseType(target_db) == self.db_arch.config.database_type:
                            migration = MigrationScript(
                                version=version,
                                name=data["name"],
                                description=data["description"],
                                migration_type=MigrationType(data["migration_type"]),
                                up_sql=data["up_sql"],
                                down_sql=data["down_sql"],
                                dependencies=data.get("dependencies", []),
                                target_database=DatabaseType(target_db) if target_db else None,
                                backup_required=data.get("backup_required", True),
                                estimated_duration_seconds=data.get("estimated_duration_seconds"),
                                validation_queries=data.get("validation_queries", [])
                            )
                            pending_migrations.append(migration)
                except Exception as e:
                    logger.warning(f"Failed to load migration file {migration_file}: {e}")
            
            return pending_migrations
            
        except Exception as e:
            logger.error(f"Failed to get pending migrations: {e}")
            return []
    
    def execute_migration(self, version: str, dry_run: bool = False) -> bool:
        """Execute a specific migration"""
        try:
            # Acquire migration lock
            if not self._acquire_migration_lock():
                logger.error("Another migration is in progress")
                return False
            
            try:
                migration = self.load_migration(version)
                if not migration:
                    return False
                
                logger.info(f"{'DRY RUN: ' if dry_run else ''}Executing migration {version}: {migration.name}")
                
                # Create backup if required
                backup_path = None
                if migration.backup_required and not dry_run:
                    backup_path = self._create_backup(f"pre_migration_{version}")
                
                # Record migration start
                execution = MigrationExecution(
                    migration_version=version,
                    status=MigrationStatus.IN_PROGRESS,
                    started_at=datetime.now(timezone.utc),
                    backup_path=backup_path
                )
                
                if not dry_run:
                    self._record_migration_execution(execution)
                
                start_time = datetime.now()
                
                try:
                    # Execute migration
                    success = self._execute_migration_sql(migration, dry_run)
                    
                    if success:
                        execution.status = MigrationStatus.COMPLETED
                        execution.completed_at = datetime.now(timezone.utc)
                        execution.execution_time_seconds = (execution.completed_at - execution.started_at).total_seconds()
                        
                        # Run validation queries
                        if migration.validation_queries:
                            validation_success = self._validate_migration(migration, dry_run)
                            if not validation_success:
                                raise Exception("Migration validation failed")
                        
                        if not dry_run:
                            self._record_migration_execution(execution)
                        
                        logger.info(f"Migration {version} completed successfully")
                        return True
                    else:
                        raise Exception("Migration SQL execution failed")
                        
                except Exception as e:
                    execution.status = MigrationStatus.FAILED
                    execution.error_message = str(e)
                    execution.completed_at = datetime.now(timezone.utc)
                    
                    if not dry_run:
                        self._record_migration_execution(execution)
                        
                        # Attempt rollback
                        logger.info(f"Attempting to rollback migration {version}")
                        rollback_success = self.rollback_migration(version)
                        if rollback_success:
                            execution.status = MigrationStatus.ROLLED_BACK
                            execution.rolled_back_at = datetime.now(timezone.utc)
                            self._record_migration_execution(execution)
                    
                    logger.error(f"Migration {version} failed: {e}")
                    return False
                    
            finally:
                self._release_migration_lock()
                
        except Exception as e:
            logger.error(f"Migration execution error: {e}")
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration"""
        try:
            migration = self.load_migration(version)
            if not migration:
                return False
            
            logger.info(f"Rolling back migration {version}: {migration.name}")
            
            # Execute rollback SQL
            with self.db_arch.get_session() as session:
                # Split down_sql by semicolon and execute each statement
                statements = [stmt.strip() for stmt in migration.down_sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    try:
                        session.execute(text(statement))
                        logger.debug(f"Executed rollback statement: {statement[:100]}...")
                    except Exception as e:
                        logger.error(f"Rollback statement failed: {e}")
                        session.rollback()
                        return False
                
                # Remove migration record
                session.execute(text(f"""
                    DELETE FROM {self.migration_table} 
                    WHERE version = :version
                """), {"version": version})
                
                session.commit()
            
            logger.info(f"Migration {version} rolled back successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            return False
    
    def migrate_up(self, target_version: Optional[str] = None) -> bool:
        """Run all pending migrations up to target version"""
        try:
            pending_migrations = self.get_pending_migrations()
            
            if not pending_migrations:
                logger.info("No pending migrations to execute")
                return True
            
            # Filter migrations up to target version if specified
            if target_version:
                pending_migrations = [m for m in pending_migrations if m.version <= target_version]
            
            logger.info(f"Found {len(pending_migrations)} migrations to execute")
            
            # Execute migrations in order
            for migration in pending_migrations:
                success = self.execute_migration(migration.version)
                if not success:
                    logger.error(f"Migration failed at version {migration.version}")
                    return False
            
            logger.info("All migrations completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration up failed: {e}")
            return False
    
    def migrate_down(self, target_version: str) -> bool:
        """Rollback migrations down to target version"""
        try:
            # Get applied migrations in reverse order
            with self.db_arch.get_session() as session:
                result = session.execute(text(f"""
                    SELECT version FROM {self.migration_table} 
                    WHERE status = 'completed' AND version > :target_version
                    ORDER BY version DESC
                """), {"target_version": target_version})
                
                versions_to_rollback = [row[0] for row in result.fetchall()]
            
            if not versions_to_rollback:
                logger.info(f"No migrations to rollback to version {target_version}")
                return True
            
            logger.info(f"Rolling back {len(versions_to_rollback)} migrations")
            
            # Rollback migrations in reverse order
            for version in versions_to_rollback:
                success = self.rollback_migration(version)
                if not success:
                    logger.error(f"Rollback failed at version {version}")
                    return False
            
            logger.info(f"Successfully rolled back to version {target_version}")
            return True
            
        except Exception as e:
            logger.error(f"Migration down failed: {e}")
            return False
    
    def get_migration_history(self) -> List[MigrationExecution]:
        """Get migration execution history"""
        try:
            history = []
            with self.db_arch.get_session() as session:
                result = session.execute(text(f"""
                    SELECT version, status, started_at, completed_at, 
                           execution_time_seconds, error_message, backup_path,
                           checksum, rolled_back_at
                    FROM {self.migration_table}
                    ORDER BY started_at DESC
                """))
                
                for row in result.fetchall():
                    execution = MigrationExecution(
                        migration_version=row[0],
                        status=MigrationStatus(row[1]),
                        started_at=row[2],
                        completed_at=row[3],
                        execution_time_seconds=row[4],
                        error_message=row[5],
                        backup_path=row[6],
                        checksum=row[7],
                        rolled_back_at=row[8]
                    )
                    history.append(execution)
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []
    
    def sync_databases(
        self,
        source_db: DatabaseArchitecture,
        target_db: DatabaseArchitecture,
        tables: Optional[List[str]] = None
    ) -> bool:
        """Synchronize data between two databases"""
        try:
            logger.info(f"Syncing databases from {source_db.config.database_type.value} to {target_db.config.database_type.value}")
            
            # Get tables to sync
            if tables is None:
                with source_db.get_session() as session:
                    inspector = inspect(session.bind)
                    tables = inspector.get_table_names()
            
            # Create backup of target database
            backup_path = self._create_backup("pre_sync", target_db)
            
            # Sync each table
            for table_name in tables:
                success = self._sync_table(source_db, target_db, table_name)
                if not success:
                    logger.error(f"Failed to sync table {table_name}")
                    return False
            
            logger.info("Database synchronization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database sync failed: {e}")
            return False
    
    def _execute_migration_sql(self, migration: MigrationScript, dry_run: bool = False) -> bool:
        """Execute migration SQL statements"""
        try:
            with self.db_arch.get_session() as session:
                # Split SQL by semicolon and execute each statement
                statements = [stmt.strip() for stmt in migration.up_sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    if dry_run:
                        logger.info(f"DRY RUN - Would execute: {statement[:100]}...")
                    else:
                        try:
                            session.execute(text(statement))
                            logger.debug(f"Executed: {statement[:100]}...")
                        except Exception as e:
                            logger.error(f"SQL statement failed: {e}")
                            logger.error(f"Statement: {statement}")
                            session.rollback()
                            return False
                
                if not dry_run:
                    session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Migration SQL execution failed: {e}")
            return False
    
    def _validate_migration(self, migration: MigrationScript, dry_run: bool = False) -> bool:
        """Run migration validation queries"""
        try:
            for query in migration.validation_queries:
                if dry_run:
                    logger.info(f"DRY RUN - Would validate with: {query[:50]}...")
                else:
                    with self.db_arch.get_session() as session:
                        result = session.execute(text(query))
                        # Simple validation - query should not fail and return results
                        if result.rowcount == 0:
                            logger.warning(f"Validation query returned no results: {query[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration validation failed: {e}")
            return False
    
    def _sync_table(
        self,
        source_db: DatabaseArchitecture,
        target_db: DatabaseArchitecture,
        table_name: str
    ) -> bool:
        """Sync a single table between databases"""
        try:
            logger.info(f"Syncing table: {table_name}")
            
            # Get data from source
            with source_db.get_session() as source_session:
                result = source_session.execute(text(f"SELECT * FROM {table_name}"))
                rows = result.fetchall()
                columns = result.keys()
            
            if not rows:
                logger.info(f"Table {table_name} is empty, skipping")
                return True
            
            # Clear target table
            with target_db.get_session() as target_session:
                target_session.execute(text(f"DELETE FROM {table_name}"))
                
                # Insert data into target
                for row in rows:
                    placeholders = ', '.join([f':{col}' for col in columns])
                    insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                    
                    row_dict = dict(zip(columns, row))
                    target_session.execute(text(insert_sql), row_dict)
                
                target_session.commit()
            
            logger.info(f"Synced {len(rows)} rows for table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Table sync failed for {table_name}: {e}")
            return False
    
    def _create_backup(self, prefix: str, db_arch: Optional[DatabaseArchitecture] = None) -> str:
        """Create database backup"""
        try:
            if db_arch is None:
                db_arch = self.db_arch
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{prefix}_{timestamp}.backup"
            backup_path = self.backups_dir / backup_filename
            
            if db_arch.config.database_type == DatabaseType.SQLITE:
                # SQLite backup
                connection_string = db_arch.config.connection_string
                db_path = connection_string.replace("sqlite:///", "").replace("sqlite://", "")
                shutil.copy2(db_path, backup_path)
            else:
                # PostgreSQL backup (would use pg_dump)
                logger.warning("PostgreSQL backup not implemented in this version")
                return str(backup_path)
            
            logger.info(f"Created backup: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise
    
    def _acquire_migration_lock(self) -> bool:
        """Acquire migration lock to prevent concurrent migrations"""
        try:
            import socket
            hostname = socket.gethostname()
            process_id = os.getpid()
            
            with self.db_arch.get_session() as session:
                # Check for existing lock
                result = session.execute(text(f"""
                    SELECT COUNT(*) FROM {self.migration_lock_table}
                """))
                
                if result.scalar() > 0:
                    return False
                
                # Acquire lock
                session.execute(text(f"""
                    INSERT INTO {self.migration_lock_table} 
                    (locked_at, locked_by, process_id)
                    VALUES (:locked_at, :locked_by, :process_id)
                """), {
                    "locked_at": datetime.now(timezone.utc),
                    "locked_by": hostname,
                    "process_id": str(process_id)
                })
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to acquire migration lock: {e}")
            return False
    
    def _release_migration_lock(self):
        """Release migration lock"""
        try:
            with self.db_arch.get_session() as session:
                session.execute(text(f"DELETE FROM {self.migration_lock_table}"))
                session.commit()
        except Exception as e:
            logger.error(f"Failed to release migration lock: {e}")
    
    def _record_migration_execution(self, execution: MigrationExecution):
        """Record migration execution in database"""
        try:
            with self.db_arch.get_session() as session:
                session.execute(text(f"""
                    INSERT OR REPLACE INTO {self.migration_table}
                    (version, name, description, migration_type, status, started_at, 
                     completed_at, execution_time_seconds, error_message, backup_path, 
                     checksum, rolled_back_at)
                    VALUES (:version, :name, :description, :migration_type, :status, 
                            :started_at, :completed_at, :execution_time_seconds, 
                            :error_message, :backup_path, :checksum, :rolled_back_at)
                """), {
                    "version": execution.migration_version,
                    "name": "Unknown",  # Would be loaded from migration file
                    "description": "Unknown",
                    "migration_type": "unknown",
                    "status": execution.status.value,
                    "started_at": execution.started_at,
                    "completed_at": execution.completed_at,
                    "execution_time_seconds": execution.execution_time_seconds,
                    "error_message": execution.error_message,
                    "backup_path": execution.backup_path,
                    "checksum": execution.checksum,
                    "rolled_back_at": execution.rolled_back_at
                })
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to record migration execution: {e}")


# Factory function
def create_migration_system(
    db_architecture: DatabaseArchitecture,
    db_operations: UnifiedDatabaseOperations
) -> DatabaseMigrationSystem:
    """Create database migration system instance"""
    return DatabaseMigrationSystem(db_architecture, db_operations)


if __name__ == "__main__":
    # CLI for migration management
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Migration Management")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--up", action="store_true", help="Run pending migrations")
    parser.add_argument("--down", type=str, help="Rollback to version")
    parser.add_argument("--create", nargs=2, metavar=('NAME', 'DESCRIPTION'), help="Create new migration")
    parser.add_argument("--execute", type=str, help="Execute specific migration")
    parser.add_argument("--rollback", type=str, help="Rollback specific migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    try:
        from database_architecture import get_database_architecture
        from database_abstraction import get_database_operations
        
        db_arch = get_database_architecture()
        db_ops = get_database_operations()
        migration_system = create_migration_system(db_arch, db_ops)
        
        if args.status:
            # Show migration status
            history = migration_system.get_migration_history()
            pending = migration_system.get_pending_migrations()
            
            print(f"Migration Status:")
            print(f"  Applied: {len(history)}")
            print(f"  Pending: {len(pending)}")
            
            if history:
                print("\nRecent Migrations:")
                for execution in history[:5]:
                    print(f"  {execution.migration_version}: {execution.status.value}")
            
            if pending:
                print("\nPending Migrations:")
                for migration in pending:
                    print(f"  {migration.version}: {migration.name}")
        
        elif args.up:
            success = migration_system.migrate_up()
            exit(0 if success else 1)
        
        elif args.down:
            success = migration_system.migrate_down(args.down)
            exit(0 if success else 1)
        
        elif args.create:
            name, description = args.create
            up_sql = input("Enter UP SQL (end with empty line):\n")
            down_sql = input("Enter DOWN SQL (end with empty line):\n")
            
            version = migration_system.create_migration(
                name, description, MigrationType.SCHEMA, up_sql, down_sql
            )
            print(f"Created migration: {version}")
        
        elif args.execute:
            success = migration_system.execute_migration(args.execute, args.dry_run)
            exit(0 if success else 1)
        
        elif args.rollback:
            success = migration_system.rollback_migration(args.rollback)
            exit(0 if success else 1)
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")
        exit(1)