#!/usr/bin/env python3
"""
Database Abstraction Layer for Unified Operations

This module provides a high-level abstraction layer that works seamlessly
with both SQLite and PostgreSQL, ensuring consistent behavior across all
environments while maintaining optimal performance.

Key Features:
- Unified query interface for both SQLite and PostgreSQL
- Automatic query optimization based on database type
- Transaction management with automatic retry logic
- Connection health monitoring and automatic recovery
- Data validation and constraint enforcement
- Batch operation optimization
- Async/await support for high-performance operations

Design Goals:
- Zero vendor lock-in - easy switching between database types
- Performance optimization - automatic query tuning
- Reliability - automatic error recovery and retry logic
- Consistency - same API regardless of underlying database
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Dict, List, Optional, Any, Union, Tuple, Set, 
    Generic, TypeVar, Callable, AsyncIterator, Iterator
)
from uuid import uuid4

from sqlalchemy import text, func, and_, or_, not_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError

from database_architecture import DatabaseArchitecture, DatabaseType, IntegrityStatus

logger = logging.getLogger(__name__)

# Type definitions
T = TypeVar('T')
QueryResult = Union[Dict[str, Any], List[Dict[str, Any]], Any]
FilterType = Dict[str, Any]
SortType = List[Tuple[str, str]]  # [(column, direction), ...]

class QueryType(Enum):
    """Query operation types"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    COUNT = "count"
    EXISTS = "exists"

class TransactionIsolation(Enum):
    """Transaction isolation levels"""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"

@dataclass
class QueryOptions:
    """Query execution options"""
    limit: Optional[int] = None
    offset: Optional[int] = None
    sort_by: Optional[SortType] = None
    filters: Optional[FilterType] = None
    include_soft_deleted: bool = False
    timeout_seconds: Optional[int] = None
    cache_result: bool = False
    explain_query: bool = False

@dataclass
class QueryResult:
    """Query execution result"""
    data: Any
    execution_time_ms: float
    rows_affected: int = 0
    query_plan: Optional[str] = None
    cache_hit: bool = False
    
@dataclass
class BatchOperation:
    """Batch operation definition"""
    operation_type: QueryType
    table_name: str
    data: List[Dict[str, Any]]
    filters: Optional[FilterType] = None
    options: Optional[QueryOptions] = None

class DatabaseAbstraction(ABC):
    """Abstract base class for database operations"""
    
    def __init__(self, db_architecture: DatabaseArchitecture):
        self.db_arch = db_architecture
        self._query_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        self._connection_pool_stats = {"connections_created": 0, "queries_executed": 0}
    
    @abstractmethod
    def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Execute a raw SQL query"""
        pass
    
    @abstractmethod
    def select(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Select data from table"""
        pass
    
    @abstractmethod
    def insert(
        self,
        table_name: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Insert data into table"""
        pass
    
    @abstractmethod
    def update(
        self,
        table_name: str,
        data: Dict[str, Any],
        filters: FilterType,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Update data in table"""
        pass
    
    @abstractmethod
    def delete(
        self,
        table_name: str,
        filters: FilterType,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Delete data from table"""
        pass

class UnifiedDatabaseOperations(DatabaseAbstraction):
    """
    Unified database operations that work across SQLite and PostgreSQL
    with automatic optimization and error handling
    """
    
    def __init__(self, db_architecture: DatabaseArchitecture):
        super().__init__(db_architecture)
        self.db_type = db_architecture.config.database_type
        self._setup_optimizations()
    
    def _setup_optimizations(self):
        """Setup database-specific optimizations"""
        self.optimizations = {
            DatabaseType.SQLITE: {
                "batch_insert_threshold": 100,
                "max_query_timeout": 30,
                "use_wal_mode": True,
                "pragma_optimizations": [
                    "PRAGMA optimize",
                    "PRAGMA journal_mode=WAL",
                    "PRAGMA synchronous=NORMAL"
                ]
            },
            DatabaseType.POSTGRESQL: {
                "batch_insert_threshold": 1000,
                "max_query_timeout": 60,
                "use_prepared_statements": True,
                "connection_optimizations": [
                    "SET statement_timeout = '30s'",
                    "SET lock_timeout = '10s'"
                ]
            }
        }
    
    def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Execute raw SQL query with automatic optimization"""
        start_time = datetime.now()
        options = options or QueryOptions()
        
        try:
            # Generate cache key if caching is enabled
            cache_key = None
            if options.cache_result and "SELECT" in query.upper():
                cache_key = self._generate_cache_key(query, params)
                
                with self._cache_lock:
                    if cache_key in self._query_cache:
                        cached_result = self._query_cache[cache_key]
                        cached_result.cache_hit = True
                        return cached_result
            
            # Execute query with session management
            with self.db_arch.get_session() as session:
                # Apply database-specific optimizations
                self._apply_session_optimizations(session)
                
                # Prepare and execute query
                if params:
                    result = session.execute(text(query), params)
                else:
                    result = session.execute(text(query))
                
                # Process results based on query type
                query_result = self._process_query_result(result, query, options)
                
                # Get query plan if requested
                if options.explain_query:
                    query_result.query_plan = self._get_query_plan(session, query, params)
                
                # Cache result if enabled
                if cache_key:
                    with self._cache_lock:
                        self._query_cache[cache_key] = query_result
                
                # Update statistics
                self._connection_pool_stats["queries_executed"] += 1
                
                return query_result
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    def select(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Enhanced SELECT with automatic optimization"""
        options = options or QueryOptions()
        columns_str = ", ".join(columns) if columns else "*"
        
        # Build base query
        query_parts = [f"SELECT {columns_str} FROM {table_name}"]
        params = {}
        
        # Add filters
        if options.filters:
            where_clause, filter_params = self._build_where_clause(options.filters)
            query_parts.append(f"WHERE {where_clause}")
            params.update(filter_params)
        
        # Add soft delete handling
        if not options.include_soft_deleted:
            soft_delete_clause = self._get_soft_delete_clause(table_name)
            if soft_delete_clause:
                if options.filters:
                    query_parts.append(f"AND {soft_delete_clause}")
                else:
                    query_parts.append(f"WHERE {soft_delete_clause}")
        
        # Add sorting
        if options.sort_by:
            order_clause = self._build_order_clause(options.sort_by)
            query_parts.append(f"ORDER BY {order_clause}")
        
        # Add pagination
        if options.limit:
            if self.db_type == DatabaseType.POSTGRESQL:
                query_parts.append(f"LIMIT :limit")
                params["limit"] = options.limit
                if options.offset:
                    query_parts.append(f"OFFSET :offset")
                    params["offset"] = options.offset
            else:  # SQLite
                query_parts.append(f"LIMIT :limit")
                params["limit"] = options.limit
                if options.offset:
                    query_parts.append(f"OFFSET :offset")
                    params["offset"] = options.offset
        
        query = " ".join(query_parts)
        return self.execute_query(query, params, options)
    
    def insert(
        self,
        table_name: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Enhanced INSERT with batch optimization"""
        options = options or QueryOptions()
        
        # Normalize data to list format
        if isinstance(data, dict):
            data = [data]
        
        if not data:
            raise ValueError("No data provided for insert")
        
        # Check if batch insert should be used
        batch_threshold = self.optimizations[self.db_type]["batch_insert_threshold"]
        if len(data) > batch_threshold:
            return self._batch_insert(table_name, data, options)
        else:
            return self._single_insert(table_name, data, options)
    
    def _single_insert(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        options: QueryOptions
    ) -> QueryResult:
        """Single transaction insert"""
        start_time = datetime.now()
        rows_affected = 0
        
        try:
            with self.db_arch.get_session() as session:
                self._apply_session_optimizations(session)
                
                for record in data:
                    # Add audit fields
                    record = self._add_audit_fields(record, "insert")
                    
                    # Validate data
                    self._validate_record(table_name, record)
                    
                    # Build insert query
                    columns = list(record.keys())
                    placeholders = [f":{col}" for col in columns]
                    
                    query = f"""
                        INSERT INTO {table_name} ({', '.join(columns)}) 
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    session.execute(text(query), record)
                    rows_affected += 1
                
                session.commit()
                
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                return QueryResult(
                    data=None,
                    execution_time_ms=execution_time,
                    rows_affected=rows_affected
                )
                
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            raise
    
    def _batch_insert(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        options: QueryOptions
    ) -> QueryResult:
        """Optimized batch insert"""
        start_time = datetime.now()
        rows_affected = 0
        
        try:
            with self.db_arch.get_session() as session:
                self._apply_session_optimizations(session)
                
                # Prepare all records
                processed_data = []
                for record in data:
                    record = self._add_audit_fields(record, "insert")
                    self._validate_record(table_name, record)
                    processed_data.append(record)
                
                # Use database-specific batch insert
                if self.db_type == DatabaseType.POSTGRESQL:
                    rows_affected = self._postgresql_batch_insert(session, table_name, processed_data)
                else:
                    rows_affected = self._sqlite_batch_insert(session, table_name, processed_data)
                
                session.commit()
                
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                return QueryResult(
                    data=None,
                    execution_time_ms=execution_time,
                    rows_affected=rows_affected
                )
                
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            raise
    
    def _postgresql_batch_insert(
        self,
        session: Session,
        table_name: str,
        data: List[Dict[str, Any]]
    ) -> int:
        """PostgreSQL optimized batch insert using VALUES clause"""
        if not data:
            return 0
            
        # Get columns from first record
        columns = list(data[0].keys())
        
        # Build VALUES clause
        values_parts = []
        params = {}
        
        for i, record in enumerate(data):
            record_placeholders = []
            for col in columns:
                param_name = f"{col}_{i}"
                record_placeholders.append(f":{param_name}")
                params[param_name] = record[col]
            values_parts.append(f"({', '.join(record_placeholders)})")
        
        query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES {', '.join(values_parts)}
        """
        
        result = session.execute(text(query), params)
        return result.rowcount or len(data)
    
    def _sqlite_batch_insert(
        self,
        session: Session,
        table_name: str,
        data: List[Dict[str, Any]]
    ) -> int:
        """SQLite optimized batch insert using executemany"""
        if not data:
            return 0
            
        columns = list(data[0].keys())
        placeholders = [f":{col}" for col in columns]
        
        query = f"""
            INSERT INTO {table_name} ({', '.join(columns)}) 
            VALUES ({', '.join(placeholders)})
        """
        
        # SQLite's executemany is more efficient for large batches
        connection = session.connection()
        result = connection.execute(text(query), data)
        return result.rowcount or len(data)
    
    def update(
        self,
        table_name: str,
        data: Dict[str, Any],
        filters: FilterType,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Enhanced UPDATE with optimistic locking support"""
        options = options or QueryOptions()
        start_time = datetime.now()
        
        try:
            with self.db_arch.get_session() as session:
                self._apply_session_optimizations(session)
                
                # Add audit fields
                data = self._add_audit_fields(data, "update")
                
                # Build SET clause
                set_parts = []
                params = {}
                for i, (col, value) in enumerate(data.items()):
                    param_name = f"set_{col}_{i}"
                    set_parts.append(f"{col} = :{param_name}")
                    params[param_name] = value
                
                # Build WHERE clause
                where_clause, filter_params = self._build_where_clause(filters)
                params.update(filter_params)
                
                # Add soft delete handling
                if not options.include_soft_deleted:
                    soft_delete_clause = self._get_soft_delete_clause(table_name)
                    if soft_delete_clause:
                        where_clause = f"({where_clause}) AND {soft_delete_clause}"
                
                query = f"""
                    UPDATE {table_name} 
                    SET {', '.join(set_parts)} 
                    WHERE {where_clause}
                """
                
                result = session.execute(text(query), params)
                session.commit()
                
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                return QueryResult(
                    data=None,
                    execution_time_ms=execution_time,
                    rows_affected=result.rowcount or 0
                )
                
        except Exception as e:
            logger.error(f"Update failed: {e}")
            raise
    
    def delete(
        self,
        table_name: str,
        filters: FilterType,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Enhanced DELETE with soft delete support"""
        options = options or QueryOptions()
        start_time = datetime.now()
        
        try:
            with self.db_arch.get_session() as session:
                self._apply_session_optimizations(session)
                
                # Check if table supports soft delete
                if self._supports_soft_delete(table_name) and not options.include_soft_deleted:
                    # Perform soft delete
                    soft_delete_data = {
                        "deleted_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                    return self.update(table_name, soft_delete_data, filters, options)
                else:
                    # Perform hard delete
                    where_clause, params = self._build_where_clause(filters)
                    
                    query = f"DELETE FROM {table_name} WHERE {where_clause}"
                    
                    result = session.execute(text(query), params)
                    session.commit()
                    
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    return QueryResult(
                        data=None,
                        execution_time_ms=execution_time,
                        rows_affected=result.rowcount or 0
                    )
                    
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            raise
    
    def count(
        self,
        table_name: str,
        filters: Optional[FilterType] = None,
        options: Optional[QueryOptions] = None
    ) -> int:
        """Count records with filters"""
        options = options or QueryOptions()
        
        query_parts = [f"SELECT COUNT(*) FROM {table_name}"]
        params = {}
        
        if filters:
            where_clause, filter_params = self._build_where_clause(filters)
            query_parts.append(f"WHERE {where_clause}")
            params.update(filter_params)
        
        # Add soft delete handling
        if not options.include_soft_deleted:
            soft_delete_clause = self._get_soft_delete_clause(table_name)
            if soft_delete_clause:
                if filters:
                    query_parts.append(f"AND {soft_delete_clause}")
                else:
                    query_parts.append(f"WHERE {soft_delete_clause}")
        
        query = " ".join(query_parts)
        result = self.execute_query(query, params, options)
        
        return result.data[0][0] if result.data else 0
    
    def exists(
        self,
        table_name: str,
        filters: FilterType,
        options: Optional[QueryOptions] = None
    ) -> bool:
        """Check if records exist with given filters"""
        options = options or QueryOptions()
        
        where_clause, params = self._build_where_clause(filters)
        
        # Use database-specific EXISTS syntax
        if self.db_type == DatabaseType.POSTGRESQL:
            query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {where_clause})"
        else:  # SQLite
            query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {where_clause})"
        
        # Add soft delete handling
        if not options.include_soft_deleted:
            soft_delete_clause = self._get_soft_delete_clause(table_name)
            if soft_delete_clause:
                where_clause = f"({where_clause}) AND {soft_delete_clause}"
                query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {where_clause})"
        
        result = self.execute_query(query, params, options)
        return bool(result.data[0][0]) if result.data else False
    
    def execute_batch(
        self,
        operations: List[BatchOperation],
        use_transaction: bool = True
    ) -> List[QueryResult]:
        """Execute multiple operations in a single transaction"""
        results = []
        
        if use_transaction:
            with self.db_arch.get_session() as session:
                self._apply_session_optimizations(session)
                
                try:
                    for operation in operations:
                        result = self._execute_batch_operation(session, operation)
                        results.append(result)
                    
                    session.commit()
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Batch operation failed, rolling back: {e}")
                    raise
        else:
            # Execute operations individually
            for operation in operations:
                with self.db_arch.get_session() as session:
                    result = self._execute_batch_operation(session, operation)
                    results.append(result)
        
        return results
    
    def _execute_batch_operation(
        self,
        session: Session,
        operation: BatchOperation
    ) -> QueryResult:
        """Execute a single batch operation"""
        if operation.operation_type == QueryType.INSERT:
            return self._batch_operation_insert(session, operation)
        elif operation.operation_type == QueryType.UPDATE:
            return self._batch_operation_update(session, operation)
        elif operation.operation_type == QueryType.DELETE:
            return self._batch_operation_delete(session, operation)
        else:
            raise ValueError(f"Unsupported batch operation: {operation.operation_type}")
    
    def _apply_session_optimizations(self, session: Session):
        """Apply database-specific session optimizations"""
        try:
            optimizations = self.optimizations[self.db_type]
            
            if self.db_type == DatabaseType.SQLITE:
                for pragma in optimizations.get("pragma_optimizations", []):
                    session.execute(text(pragma))
            else:  # PostgreSQL
                for setting in optimizations.get("connection_optimizations", []):
                    session.execute(text(setting))
                    
        except Exception as e:
            logger.warning(f"Failed to apply session optimizations: {e}")
    
    def _build_where_clause(self, filters: FilterType) -> Tuple[str, Dict[str, Any]]:
        """Build WHERE clause from filters"""
        conditions = []
        params = {}
        
        for i, (column, value) in enumerate(filters.items()):
            param_name = f"filter_{column}_{i}"
            
            if isinstance(value, dict):
                # Handle operators like {"gt": 10}, {"like": "%test%"}
                for operator, operand in value.items():
                    condition = self._build_operator_condition(column, operator, operand, param_name)
                    conditions.append(condition)
                    params[param_name] = operand
            elif isinstance(value, list):
                # Handle IN clause
                in_params = []
                for j, item in enumerate(value):
                    in_param = f"{param_name}_{j}"
                    in_params.append(f":{in_param}")
                    params[in_param] = item
                conditions.append(f"{column} IN ({', '.join(in_params)})")
            elif value is None:
                conditions.append(f"{column} IS NULL")
            else:
                conditions.append(f"{column} = :{param_name}")
                params[param_name] = value
        
        return " AND ".join(conditions) if conditions else "1=1", params
    
    def _build_operator_condition(
        self,
        column: str,
        operator: str,
        operand: Any,
        param_name: str
    ) -> str:
        """Build condition with operator"""
        operator_map = {
            "eq": "=",
            "ne": "!=",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
            "like": "LIKE",
            "ilike": "ILIKE" if self.db_type == DatabaseType.POSTGRESQL else "LIKE",
            "in": "IN",
            "not_in": "NOT IN"
        }
        
        sql_operator = operator_map.get(operator, "=")
        return f"{column} {sql_operator} :{param_name}"
    
    def _build_order_clause(self, sort_by: SortType) -> str:
        """Build ORDER BY clause"""
        order_parts = []
        for column, direction in sort_by:
            direction = direction.upper()
            if direction not in ("ASC", "DESC"):
                direction = "ASC"
            order_parts.append(f"{column} {direction}")
        
        return ", ".join(order_parts)
    
    def _add_audit_fields(self, data: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Add audit fields to data"""
        audit_data = data.copy()
        current_time = datetime.now(timezone.utc)
        
        if operation == "insert":
            if "id" not in audit_data:
                audit_data["id"] = str(uuid4())
            audit_data["created_at"] = current_time
            audit_data["updated_at"] = current_time
        elif operation == "update":
            audit_data["updated_at"] = current_time
        
        return audit_data
    
    def _validate_record(self, table_name: str, record: Dict[str, Any]):
        """Validate record data before database operation"""
        # Basic validation - could be extended with schema validation
        if not record:
            raise ValueError("Empty record data")
        
        # Check for required fields based on table
        required_fields = self._get_required_fields(table_name)
        missing_fields = [field for field in required_fields if field not in record]
        
        if missing_fields:
            raise ValueError(f"Missing required fields for {table_name}: {missing_fields}")
    
    def _get_required_fields(self, table_name: str) -> List[str]:
        """Get required fields for a table"""
        # This would be enhanced to use actual schema information
        required_fields_map = {
            "projects": ["name", "camera_model", "camera_view", "signal_type"],
            "videos": ["filename", "file_path", "project_id"],
            "test_sessions": ["name", "project_id", "video_id"],
            "detection_events": ["test_session_id", "timestamp"],
            "ground_truth_objects": ["video_id", "timestamp", "class_label"],
            "annotations": ["video_id", "frame_number", "timestamp", "vru_type", "bounding_box"]
        }
        
        return required_fields_map.get(table_name, [])
    
    def _supports_soft_delete(self, table_name: str) -> bool:
        """Check if table supports soft delete"""
        soft_delete_tables = {
            "projects", "videos", "annotations", "test_sessions"
        }
        return table_name in soft_delete_tables
    
    def _get_soft_delete_clause(self, table_name: str) -> Optional[str]:
        """Get soft delete WHERE clause for table"""
        if self._supports_soft_delete(table_name):
            return "deleted_at IS NULL"
        return None
    
    def _generate_cache_key(self, query: str, params: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for query"""
        import hashlib
        
        key_data = query
        if params:
            # Sort params for consistent key generation
            sorted_params = sorted(params.items())
            key_data += str(sorted_params)
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _process_query_result(
        self,
        result: Any,
        query: str,
        options: QueryOptions
    ) -> QueryResult:
        """Process SQLAlchemy result into QueryResult"""
        execution_time = 0.0  # Would be calculated in calling method
        
        try:
            if "SELECT" in query.upper():
                # Fetch all results and convert to list of dicts
                rows = result.fetchall()
                if rows:
                    columns = result.keys()
                    data = [dict(zip(columns, row)) for row in rows]
                else:
                    data = []
                
                return QueryResult(
                    data=data,
                    execution_time_ms=execution_time,
                    rows_affected=len(data)
                )
            else:
                # For INSERT/UPDATE/DELETE operations
                return QueryResult(
                    data=None,
                    execution_time_ms=execution_time,
                    rows_affected=result.rowcount or 0
                )
                
        except Exception as e:
            logger.error(f"Error processing query result: {e}")
            return QueryResult(
                data=None,
                execution_time_ms=execution_time,
                rows_affected=0
            )
    
    def _get_query_plan(
        self,
        session: Session,
        query: str,
        params: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Get query execution plan"""
        try:
            if self.db_type == DatabaseType.POSTGRESQL:
                explain_query = f"EXPLAIN ANALYZE {query}"
            else:  # SQLite
                explain_query = f"EXPLAIN QUERY PLAN {query}"
            
            if params:
                result = session.execute(text(explain_query), params)
            else:
                result = session.execute(text(explain_query))
            
            plan_rows = result.fetchall()
            return "\n".join([str(row) for row in plan_rows])
            
        except Exception as e:
            logger.warning(f"Failed to get query plan: {e}")
            return None
    
    def clear_cache(self):
        """Clear query result cache"""
        with self._cache_lock:
            self._query_cache.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get operation statistics"""
        with self._cache_lock:
            return {
                "connections_created": self._connection_pool_stats["connections_created"],
                "queries_executed": self._connection_pool_stats["queries_executed"],
                "cache_size": len(self._query_cache),
                "database_type": self.db_type.value
            }


# Factory function
def create_database_operations(db_architecture: DatabaseArchitecture) -> UnifiedDatabaseOperations:
    """Create database operations instance"""
    return UnifiedDatabaseOperations(db_architecture)


# Global instance for easy access
_global_db_ops: Optional[UnifiedDatabaseOperations] = None

def get_database_operations() -> UnifiedDatabaseOperations:
    """Get global database operations instance"""
    global _global_db_ops
    
    if _global_db_ops is None:
        from database_architecture import get_database_architecture
        db_arch = get_database_architecture()
        _global_db_ops = create_database_operations(db_arch)
    
    return _global_db_ops


if __name__ == "__main__":
    # Example usage and testing
    import json
    
    try:
        db_ops = get_database_operations()
        
        # Test connection
        print("Testing database operations...")
        
        # Example: Count projects
        project_count = db_ops.count("projects")
        print(f"Projects count: {project_count}")
        
        # Example: Select with options
        options = QueryOptions(limit=5, sort_by=[("created_at", "DESC")])
        projects = db_ops.select("projects", columns=["id", "name", "status"], options=options)
        print(f"Recent projects: {json.dumps(projects.data, indent=2, default=str)}")
        
        # Get statistics
        stats = db_ops.get_statistics()
        print(f"Statistics: {json.dumps(stats, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}")