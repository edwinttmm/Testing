"""
Hybrid Query Service for Raw Data Compression
============================================

Provides seamless query interface that works with both:
1. Legacy detection_events table (existing data)
2. New compressed raw data tables (new high-frequency data)

Key Features:
- Transparent query routing based on data type
- Performance optimization for different query patterns
- Backward compatibility with existing APIs
- Real-time compression data integration
- Unified result formatting

Query Types Supported:
- Temporal range queries (high performance)
- Detection correlation queries
- Compression statistics queries
- Hybrid legacy + compressed queries
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, and_, or_, func, desc, asc

# Local imports
from database import get_db
from models import DetectionEvent, TestSession
from src.models.labjack_raw_compression import (
    LabJackRawSession, VoltageTransition, VoltageRunPeriod,
    DetectionEventCompressed, CompressionStatistics
)

logger = logging.getLogger(__name__)


class QueryStrategy(Enum):
    """Query execution strategies"""
    LEGACY_ONLY = "legacy_only"           # Query only detection_events table
    COMPRESSED_ONLY = "compressed_only"   # Query only compressed tables
    HYBRID = "hybrid"                     # Query both legacy and compressed
    AUTO = "auto"                         # Automatically choose best strategy


@dataclass
class QueryPlan:
    """Query execution plan"""
    strategy: QueryStrategy
    estimated_rows: int
    use_indexes: List[str] = field(default_factory=list)
    execution_time_estimate_ms: float = 0.0
    data_sources: List[str] = field(default_factory=list)


@dataclass
class QueryResult:
    """Unified query result format"""
    data: List[Dict[str, Any]]
    total_count: int
    execution_time_ms: float
    data_sources: List[str]
    compression_info: Optional[Dict[str, Any]] = None


class HybridQueryService:
    """
    Intelligent query service that seamlessly works with both legacy
    and compressed data formats for optimal performance.
    """
    
    def __init__(self):
        # Query optimization settings
        self.auto_strategy_threshold = 10000  # Records threshold for strategy selection
        self.compression_data_preference = True  # Prefer compressed data when available
        
        # Performance tracking
        self.query_stats = {
            'legacy_queries': 0,
            'compressed_queries': 0,
            'hybrid_queries': 0,
            'total_execution_time_ms': 0.0
        }
        
        logger.info("Hybrid query service initialized")
    
    async def query_detection_events(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        strategy: QueryStrategy = QueryStrategy.AUTO,
        include_raw_data: bool = False,
        limit: int = 1000,
        offset: int = 0,
        db: Optional[Session] = None
    ) -> QueryResult:
        """
        Query detection events with intelligent routing between legacy and compressed data
        
        Args:
            session_id: Test session identifier
            start_time: Start of time range (optional)
            end_time: End of time range (optional)
            strategy: Query strategy (auto-selected if AUTO)
            include_raw_data: Include compressed raw data details
            limit: Maximum results to return
            offset: Result offset for pagination
            db: Database session (optional)
        
        Returns:
            QueryResult with unified data format
        """
        query_start = time.perf_counter()
        
        if db is None:
            db = next(get_db())
            close_db = True
        else:
            close_db = False
        
        try:
            # Plan query execution
            query_plan = await self._plan_query(
                session_id, start_time, end_time, strategy, db
            )
            
            logger.debug(f"Query plan: {query_plan.strategy.value}, estimated rows: {query_plan.estimated_rows}")
            
            # Execute query based on strategy
            if query_plan.strategy == QueryStrategy.LEGACY_ONLY:
                result = await self._query_legacy_only(
                    session_id, start_time, end_time, limit, offset, db
                )
                self.query_stats['legacy_queries'] += 1
                
            elif query_plan.strategy == QueryStrategy.COMPRESSED_ONLY:
                result = await self._query_compressed_only(
                    session_id, start_time, end_time, include_raw_data, limit, offset, db
                )
                self.query_stats['compressed_queries'] += 1
                
            elif query_plan.strategy == QueryStrategy.HYBRID:
                result = await self._query_hybrid(
                    session_id, start_time, end_time, include_raw_data, limit, offset, db
                )
                self.query_stats['hybrid_queries'] += 1
                
            else:
                raise ValueError(f"Unsupported query strategy: {query_plan.strategy}")
            
            # Calculate execution metrics
            execution_time_ms = (time.perf_counter() - query_start) * 1000
            result.execution_time_ms = execution_time_ms
            result.data_sources = query_plan.data_sources
            
            # Update performance tracking
            self.query_stats['total_execution_time_ms'] += execution_time_ms
            
            logger.debug(
                f"Query completed in {execution_time_ms:.1f}ms, "
                f"returned {len(result.data)} records"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
        finally:
            if close_db:
                db.close()
    
    async def _plan_query(
        self,
        session_id: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        strategy: QueryStrategy,
        db: Session
    ) -> QueryPlan:
        """Plan optimal query execution strategy"""
        
        if strategy != QueryStrategy.AUTO:
            # Use specified strategy
            return QueryPlan(
                strategy=strategy,
                estimated_rows=0,
                data_sources=[strategy.value]
            )
        
        # Auto-strategy selection based on data availability and volume
        
        # Check legacy data availability
        legacy_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        )
        if start_time:
            legacy_count = legacy_count.filter(DetectionEvent.timestamp >= start_time.timestamp())
        if end_time:
            legacy_count = legacy_count.filter(DetectionEvent.timestamp <= end_time.timestamp())
        legacy_count = legacy_count.count()
        
        # Check compressed data availability
        compressed_count = db.query(DetectionEventCompressed).filter(
            DetectionEventCompressed.test_session_id == session_id
        )
        if start_time:
            compressed_count = compressed_count.filter(
                DetectionEventCompressed.timestamp >= start_time.timestamp()
            )
        if end_time:
            compressed_count = compressed_count.filter(
                DetectionEventCompressed.timestamp <= end_time.timestamp()
            )
        compressed_count = compressed_count.count()
        
        # Strategy selection logic
        total_records = legacy_count + compressed_count
        
        if compressed_count > 0 and legacy_count == 0:
            # Only compressed data available
            selected_strategy = QueryStrategy.COMPRESSED_ONLY
            data_sources = ["compressed"]
            
        elif legacy_count > 0 and compressed_count == 0:
            # Only legacy data available
            selected_strategy = QueryStrategy.LEGACY_ONLY
            data_sources = ["legacy"]
            
        elif total_records > self.auto_strategy_threshold:
            # Large dataset - prefer compressed data if available
            if compressed_count > legacy_count * 0.1:  # At least 10% compressed
                selected_strategy = QueryStrategy.COMPRESSED_ONLY
                data_sources = ["compressed"]
            else:
                selected_strategy = QueryStrategy.LEGACY_ONLY
                data_sources = ["legacy"]
                
        else:
            # Small dataset or mixed data - use hybrid approach
            selected_strategy = QueryStrategy.HYBRID
            data_sources = ["legacy", "compressed"]
        
        logger.debug(
            f"Query strategy selected: {selected_strategy.value} "
            f"(legacy: {legacy_count}, compressed: {compressed_count})"
        )
        
        return QueryPlan(
            strategy=selected_strategy,
            estimated_rows=total_records,
            data_sources=data_sources
        )
    
    async def _query_legacy_only(
        self,
        session_id: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: int,
        offset: int,
        db: Session
    ) -> QueryResult:
        """Query only legacy detection_events table"""
        
        query = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        )
        
        # Apply time filters
        if start_time:
            query = query.filter(DetectionEvent.timestamp >= start_time.timestamp())
        if end_time:
            query = query.filter(DetectionEvent.timestamp <= end_time.timestamp())
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        results = query.order_by(DetectionEvent.timestamp).offset(offset).limit(limit).all()
        
        # Convert to unified format
        data = []
        for event in results:
            data.append({
                'id': event.id,
                'session_id': event.test_session_id,
                'timestamp': event.timestamp,
                'validation_result': event.validation_result,
                'latency_ms': getattr(event, 'actual_latency_ms', None),
                'source': 'legacy',
                'data_type': 'detection_event',
                'created_at': event.created_at.isoformat() if event.created_at else None,
                # Legacy-specific fields
                'confidence': getattr(event, 'confidence', None),
                'class_label': getattr(event, 'class_label', None),
                'frame_number': getattr(event, 'frame_number', None)
            })
        
        return QueryResult(
            data=data,
            total_count=total_count,
            execution_time_ms=0.0,  # Set by caller
            data_sources=['legacy']
        )
    
    async def _query_compressed_only(
        self,
        session_id: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        include_raw_data: bool,
        limit: int,
        offset: int,
        db: Session
    ) -> QueryResult:
        """Query only compressed data tables"""
        
        # Base query on compressed detection events
        query = db.query(DetectionEventCompressed).filter(
            DetectionEventCompressed.test_session_id == session_id
        )
        
        # Apply time filters
        if start_time:
            query = query.filter(DetectionEventCompressed.timestamp >= start_time.timestamp())
        if end_time:
            query = query.filter(DetectionEventCompressed.timestamp <= end_time.timestamp())
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        results = query.order_by(DetectionEventCompressed.timestamp).offset(offset).limit(limit).all()
        
        # Convert to unified format
        data = []
        for event in results:
            event_data = {
                'id': event.id,
                'session_id': event.test_session_id,
                'timestamp': event.timestamp,
                'validation_result': event.validation_result,
                'latency_ms': event.latency_ms,
                'source': 'compressed',
                'data_type': 'compressed_detection',
                'created_at': event.created_at.isoformat() if event.created_at else None,
                # Compressed-specific fields
                'timestamp_us': event.timestamp_us,
                'timing_precision_ns': event.timing_precision_ns,
                'voltage_before_v': event.voltage_before_v,
                'voltage_after_v': event.voltage_after_v,
                'transition_type': event.transition_type,
                'detection_confidence': event.detection_confidence
            }
            
            # Include raw data details if requested
            if include_raw_data and event.transition_id:
                transition = db.query(VoltageTransition).filter(
                    VoltageTransition.id == event.transition_id
                ).first()
                
                if transition:
                    event_data['raw_data'] = {
                        'transition_id': transition.id,
                        'channel': transition.channel,
                        'slope_v_per_s': transition.slope_v_per_s,
                        'signal_quality_score': transition.signal_quality_score,
                        'noise_level_v': transition.noise_level_v,
                        'samples_since_last_transition': transition.samples_since_last_transition
                    }
            
            data.append(event_data)
        
        # Get compression statistics for this session
        compression_info = await self._get_compression_info(session_id, db)
        
        return QueryResult(
            data=data,
            total_count=total_count,
            execution_time_ms=0.0,  # Set by caller
            data_sources=['compressed'],
            compression_info=compression_info
        )
    
    async def _query_hybrid(
        self,
        session_id: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        include_raw_data: bool,
        limit: int,
        offset: int,
        db: Session
    ) -> QueryResult:
        """Query both legacy and compressed data, merging results"""
        
        # Query legacy data
        legacy_result = await self._query_legacy_only(
            session_id, start_time, end_time, limit//2, offset//2, db
        )
        
        # Query compressed data
        compressed_result = await self._query_compressed_only(
            session_id, start_time, end_time, include_raw_data, limit//2, offset//2, db
        )
        
        # Merge results by timestamp
        merged_data = legacy_result.data + compressed_result.data
        merged_data.sort(key=lambda x: x['timestamp'])
        
        # Apply final limit
        final_data = merged_data[:limit]
        
        return QueryResult(
            data=final_data,
            total_count=legacy_result.total_count + compressed_result.total_count,
            execution_time_ms=0.0,  # Set by caller
            data_sources=['legacy', 'compressed'],
            compression_info=compressed_result.compression_info
        )
    
    async def _get_compression_info(self, session_id: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get compression statistics for a session"""
        try:
            # Get raw session info
            raw_session = db.query(LabJackRawSession).filter(
                LabJackRawSession.session_id == session_id
            ).first()
            
            if not raw_session:
                return None
            
            # Get recent compression statistics
            stats = db.query(CompressionStatistics).filter(
                CompressionStatistics.session_id == raw_session.id
            ).order_by(desc(CompressionStatistics.calculated_at)).first()
            
            compression_info = {
                'session_id': raw_session.id,
                'compression_ratio': raw_session.compression_ratio,
                'total_transitions': raw_session.total_transitions,
                'data_quality_score': raw_session.data_quality_score,
                'compression_status': raw_session.compression_status.value,
                'sample_rate_hz': raw_session.sample_rate_hz
            }
            
            if stats:
                compression_info.update({
                    'recent_throughput': stats.throughput_samples_per_second,
                    'signal_fidelity': stats.signal_fidelity_score,
                    'storage_efficiency': (
                        stats.compressed_data_size_bytes / 
                        max(1, stats.raw_data_size_bytes) * 100
                    )
                })
            
            return compression_info
            
        except Exception as e:
            logger.error(f"Failed to get compression info: {e}")
            return None
    
    async def query_voltage_transitions(
        self,
        session_id: str,
        start_time_us: Optional[int] = None,
        end_time_us: Optional[int] = None,
        channel: Optional[str] = None,
        transition_types: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 1000,
        db: Optional[Session] = None
    ) -> QueryResult:
        """
        Query voltage transitions directly from compressed data
        
        Provides high-performance access to raw transition data
        for detailed signal analysis.
        """
        query_start = time.perf_counter()
        
        if db is None:
            db = next(get_db())
            close_db = True
        else:
            close_db = False
        
        try:
            # Find raw session for the test session
            raw_session = db.query(LabJackRawSession).filter(
                LabJackRawSession.session_id == session_id
            ).first()
            
            if not raw_session:
                return QueryResult(
                    data=[],
                    total_count=0,
                    execution_time_ms=0.0,
                    data_sources=['compressed'],
                    compression_info={'error': 'No compressed data found for session'}
                )
            
            # Build transition query
            query = db.query(VoltageTransition).filter(
                VoltageTransition.session_id == raw_session.id
            )
            
            # Apply filters
            if start_time_us:
                query = query.filter(VoltageTransition.timestamp_us >= start_time_us)
            if end_time_us:
                query = query.filter(VoltageTransition.timestamp_us <= end_time_us)
            if channel:
                query = query.filter(VoltageTransition.channel == channel)
            if transition_types:
                query = query.filter(VoltageTransition.transition_type.in_(transition_types))
            if min_confidence > 0.0:
                query = query.filter(VoltageTransition.detection_confidence >= min_confidence)
            
            # Get total count
            total_count = query.count()
            
            # Apply ordering and limit
            results = query.order_by(VoltageTransition.timestamp_us).limit(limit).all()
            
            # Format results
            data = []
            for transition in results:
                data.append({
                    'id': transition.id,
                    'session_id': session_id,
                    'raw_session_id': raw_session.id,
                    'timestamp_us': transition.timestamp_us,
                    'channel': transition.channel,
                    'voltage_before_v': float(transition.voltage_before_v),
                    'voltage_after_v': float(transition.voltage_after_v),
                    'voltage_delta_v': float(transition.voltage_delta_v),
                    'transition_type': transition.transition_type.value,
                    'detection_confidence': transition.detection_confidence,
                    'signal_quality_score': transition.signal_quality_score,
                    'is_detection_event': transition.is_detection_event,
                    'slope_v_per_s': transition.slope_v_per_s,
                    'transition_duration_us': transition.transition_duration_us,
                    'sequence_number': transition.sequence_number
                })
            
            execution_time_ms = (time.perf_counter() - query_start) * 1000
            
            return QueryResult(
                data=data,
                total_count=total_count,
                execution_time_ms=execution_time_ms,
                data_sources=['compressed_transitions']
            )
            
        except Exception as e:
            logger.error(f"Voltage transition query failed: {e}")
            raise
        finally:
            if close_db:
                db.close()
    
    async def query_compression_statistics(
        self,
        time_range_hours: int = 24,
        session_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> QueryResult:
        """Query compression performance statistics"""
        
        if db is None:
            db = next(get_db())
            close_db = True
        else:
            close_db = False
        
        try:
            # Build statistics query
            query = db.query(CompressionStatistics)
            
            # Apply time range filter
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)
            query = query.filter(CompressionStatistics.calculated_at >= cutoff_time)
            
            # Apply session filter if specified
            if session_id:
                # Find raw session ID
                raw_session = db.query(LabJackRawSession).filter(
                    LabJackRawSession.session_id == session_id
                ).first()
                if raw_session:
                    query = query.filter(CompressionStatistics.session_id == raw_session.id)
            
            # Execute query
            results = query.order_by(desc(CompressionStatistics.calculated_at)).all()
            
            # Format results
            data = []
            for stat in results:
                data.append({
                    'id': stat.id,
                    'session_id': stat.session_id,
                    'window_start_us': stat.window_start_us,
                    'window_duration_us': stat.window_duration_us,
                    'raw_samples_processed': stat.raw_samples_processed,
                    'compression_ratio': stat.achieved_compression_ratio,
                    'throughput_samples_per_second': stat.throughput_samples_per_second,
                    'signal_fidelity_score': stat.signal_fidelity_score,
                    'storage_efficiency_percent': (
                        stat.compressed_data_size_bytes / 
                        max(1, stat.raw_data_size_bytes) * 100
                    ),
                    'transitions_generated': stat.transitions_generated,
                    'run_periods_generated': stat.run_periods_generated,
                    'calculated_at': stat.calculated_at.isoformat()
                })
            
            return QueryResult(
                data=data,
                total_count=len(data),
                execution_time_ms=0.0,
                data_sources=['compression_statistics']
            )
            
        except Exception as e:
            logger.error(f"Compression statistics query failed: {e}")
            raise
        finally:
            if close_db:
                db.close()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get query service performance metrics"""
        total_queries = (
            self.query_stats['legacy_queries'] + 
            self.query_stats['compressed_queries'] + 
            self.query_stats['hybrid_queries']
        )
        
        avg_execution_time = (
            self.query_stats['total_execution_time_ms'] / max(1, total_queries)
        )
        
        return {
            'total_queries': total_queries,
            'query_breakdown': {
                'legacy_queries': self.query_stats['legacy_queries'],
                'compressed_queries': self.query_stats['compressed_queries'],
                'hybrid_queries': self.query_stats['hybrid_queries']
            },
            'average_execution_time_ms': avg_execution_time,
            'total_execution_time_ms': self.query_stats['total_execution_time_ms'],
            'queries_per_second': total_queries / max(1, self.query_stats['total_execution_time_ms'] / 1000),
            'compression_preference_enabled': self.compression_data_preference
        }


# Global query service instance
_hybrid_query_service: Optional[HybridQueryService] = None


def get_hybrid_query_service() -> HybridQueryService:
    """Get global hybrid query service instance"""
    global _hybrid_query_service
    if _hybrid_query_service is None:
        _hybrid_query_service = HybridQueryService()
    return _hybrid_query_service


# Export key classes
__all__ = [
    'HybridQueryService',
    'QueryStrategy',
    'QueryResult',
    'QueryPlan',
    'get_hybrid_query_service'
]