"""
Hybrid Event Synchronization Service
===================================

Intelligent synchronization service that correlates raw LabJack data with 
video-synchronized detection events, providing unified temporal alignment
between microsecond-precision raw data and frame-based video events.

This service handles the complex task of correlating events across different
timing domains:
- Raw LabJack data at 1000Hz with microsecond precision timestamps
- Video-synchronized events at 24fps with frame-based timing
- Hardware signal detection events with various timing sources

Key Features:
- Temporal correlation with configurable tolerance windows
- Event matching across different timing domains
- Conflict resolution for overlapping or duplicate events  
- Performance optimization for real-time correlation
- Backward compatibility with existing detection_events
- Quality scoring for correlation confidence
"""

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import numpy as np

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, func

# Local imports
from database import get_db
from models import DetectionEvent, TestSession
from src.models.raw_labjack_models import (
    RawLabJackSession, RawLabJackBuffer
)

# Service imports
from services.video_timing_service import get_video_timing_service
from src.services.hybrid_query_service import get_hybrid_query_service

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the synchronization system"""
    RAW_VOLTAGE_TRANSITION = "raw_voltage_transition"
    VIDEO_SYNC_DETECTION = "video_sync_detection"
    LEGACY_DETECTION = "legacy_detection"
    CORRELATED_EVENT = "correlated_event"


class CorrelationQuality(Enum):
    """Quality levels for event correlation"""
    PERFECT = "perfect"      # Exact timestamp match within 1ms
    HIGH = "high"           # Match within 10ms
    GOOD = "good"           # Match within 50ms  
    FAIR = "fair"           # Match within 100ms
    POOR = "poor"           # Match within 500ms
    FAILED = "failed"       # No suitable match found


@dataclass
class SynchronizationEvent:
    """Unified event representation for synchronization"""
    event_id: str
    session_id: str
    event_type: EventType
    timestamp: float  # Unix timestamp
    timestamp_ns: int  # Nanosecond precision
    
    # Source-specific data
    source_data: Dict[str, Any] = field(default_factory=dict)
    
    # Timing metadata
    timing_accuracy_ns: Optional[int] = None
    video_relative_time: Optional[float] = None
    frame_number: Optional[int] = None
    
    # Correlation metadata
    correlation_candidates: List[str] = field(default_factory=list)
    correlated_event_id: Optional[str] = None
    correlation_quality: Optional[CorrelationQuality] = None
    correlation_distance_ms: Optional[float] = None
    
    # Processing metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed: bool = False
    processing_errors: List[str] = field(default_factory=list)


@dataclass
class CorrelationResult:
    """Result of event correlation attempt"""
    success: bool
    primary_event: SynchronizationEvent
    matched_events: List[SynchronizationEvent] = field(default_factory=list)
    correlation_quality: CorrelationQuality = CorrelationQuality.FAILED
    correlation_confidence: float = 0.0  # 0.0-1.0
    time_difference_ms: float = 0.0
    processing_time_ms: float = 0.0
    conflict_resolution_applied: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SynchronizationConfig:
    """Configuration for event synchronization"""
    # Timing tolerances
    perfect_match_threshold_ms: float = 1.0
    high_quality_threshold_ms: float = 10.0
    good_quality_threshold_ms: float = 50.0
    fair_quality_threshold_ms: float = 100.0
    max_correlation_distance_ms: float = 500.0
    
    # Correlation behavior
    enable_backwards_correlation: bool = True
    enable_predictive_correlation: bool = True
    correlation_window_size: int = 1000  # Number of events to maintain
    
    # Performance settings
    batch_correlation_size: int = 100
    correlation_timeout_ms: float = 50.0
    enable_async_correlation: bool = True
    
    # Conflict resolution
    conflict_resolution_strategy: str = "choose_best_quality"  # "choose_first", "choose_best_quality", "merge_events"
    duplicate_detection_enabled: bool = True
    duplicate_threshold_ms: float = 5.0
    
    # Quality requirements
    minimum_correlation_quality: CorrelationQuality = CorrelationQuality.POOR
    require_source_diversity: bool = True  # Require different event types for correlation


class HybridEventSynchronizationService:
    """
    Advanced event synchronization service for correlating multi-domain timing events.
    
    Provides intelligent correlation between raw LabJack data events and video-synchronized
    detection events while maintaining high performance and accuracy.
    """
    
    def __init__(self, config: Optional[SynchronizationConfig] = None):
        self.config = config or SynchronizationConfig()
        
        # Services integration
        self.video_timing_service = get_video_timing_service()
        self.query_service = get_hybrid_query_service()
        
        # Event management
        self.event_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.config.correlation_window_size))
        self.correlation_cache: Dict[str, CorrelationResult] = {}
        self.pending_correlations: Dict[str, Set[str]] = defaultdict(set)
        
        # Performance tracking
        self.correlation_stats = {
            'events_processed': 0,
            'successful_correlations': 0,
            'failed_correlations': 0,
            'duplicate_events_detected': 0,
            'conflicts_resolved': 0,
            'average_correlation_time_ms': 0.0,
            'correlation_quality_distribution': defaultdict(int)
        }
        
        # Synchronization
        self.lock = threading.RLock()
        self.processing_active = True
        
        # Start background correlation processing
        self._start_correlation_processor()
        
        logger.info("Hybrid event synchronization service initialized")
    
    def _start_correlation_processor(self):
        """Start background correlation processing thread"""
        def correlation_processor():
            """Background correlation processing loop"""
            while self.processing_active:
                try:
                    # Process pending correlations
                    self._process_pending_correlations()
                    
                    # Clean up old cache entries
                    self._cleanup_correlation_cache()
                    
                    # Brief sleep to prevent CPU spinning
                    time.sleep(0.01)  # 10ms processing cycle
                    
                except Exception as e:
                    logger.error(f"Correlation processor error: {e}")
                    time.sleep(0.1)  # Longer sleep on error
        
        # Start background thread
        thread = threading.Thread(target=correlation_processor, daemon=True)
        thread.start()
        logger.info("Background correlation processor started")
    
    async def add_synchronization_event(
        self,
        event: SynchronizationEvent,
        immediate_correlation: bool = False
    ) -> Optional[CorrelationResult]:
        """
        Add an event to the synchronization system.
        
        Args:
            event: Event to add for synchronization
            immediate_correlation: Whether to attempt immediate correlation
        
        Returns:
            CorrelationResult if immediate correlation requested and successful
        """
        correlation_start = time.perf_counter()
        
        try:
            with self.lock:
                # Add to event buffer
                session_buffer = self.event_buffer[event.session_id]
                session_buffer.append(event)
                
                # Update processing stats
                self.correlation_stats['events_processed'] += 1
                
                # Check for duplicates
                if self.config.duplicate_detection_enabled:
                    duplicate_detected = self._check_for_duplicates(event)
                    if duplicate_detected:
                        self.correlation_stats['duplicate_events_detected'] += 1
                        logger.debug(f"Duplicate event detected: {event.event_id}")
                        return None
                
                # Attempt immediate correlation if requested
                if immediate_correlation:
                    correlation_result = await self._correlate_event(event)
                    
                    processing_time = (time.perf_counter() - correlation_start) * 1000
                    self._update_correlation_stats(correlation_result, processing_time)
                    
                    return correlation_result
                else:
                    # Add to pending correlations for background processing
                    self.pending_correlations[event.session_id].add(event.event_id)
                    return None
                    
        except Exception as e:
            logger.error(f"Error adding synchronization event {event.event_id}: {e}")
            return None
    
    async def _correlate_event(self, target_event: SynchronizationEvent) -> CorrelationResult:
        """
        Correlate a single event with other events in the buffer.
        
        Args:
            target_event: Event to correlate
        
        Returns:
            CorrelationResult with correlation details
        """
        correlation_start = time.perf_counter()
        
        try:
            session_buffer = self.event_buffer[target_event.session_id]
            candidates = []
            
            # Find correlation candidates within time window
            target_time = target_event.timestamp
            
            for buffered_event in session_buffer:
                if buffered_event.event_id == target_event.event_id:
                    continue  # Skip self
                
                # Check if different event types (for source diversity)
                if self.config.require_source_diversity:
                    if buffered_event.event_type == target_event.event_type:
                        continue
                
                # Calculate time difference
                time_diff_ms = abs(buffered_event.timestamp - target_time) * 1000
                
                if time_diff_ms <= self.config.max_correlation_distance_ms:
                    candidates.append((buffered_event, time_diff_ms))
            
            # Sort candidates by time difference
            candidates.sort(key=lambda x: x[1])
            
            if not candidates:
                processing_time_ms = (time.perf_counter() - correlation_start) * 1000
                return CorrelationResult(
                    success=False,
                    primary_event=target_event,
                    correlation_quality=CorrelationQuality.FAILED,
                    processing_time_ms=processing_time_ms,
                    metadata={'reason': 'no_candidates_found'}
                )
            
            # Find best correlation match
            best_match, best_time_diff = candidates[0]
            correlation_quality = self._determine_correlation_quality(best_time_diff)
            
            # Check if correlation meets minimum quality requirements
            if correlation_quality.value < self.config.minimum_correlation_quality.value:
                processing_time_ms = (time.perf_counter() - correlation_start) * 1000
                return CorrelationResult(
                    success=False,
                    primary_event=target_event,
                    correlation_quality=correlation_quality,
                    processing_time_ms=processing_time_ms,
                    time_difference_ms=best_time_diff,
                    metadata={'reason': 'quality_below_threshold', 'best_match_id': best_match.event_id}
                )
            
            # Handle potential conflicts
            conflict_resolution_applied = False
            matched_events = [best_match]
            
            if len(candidates) > 1:
                # Check for conflicting correlations
                conflict_resolution_applied = await self._resolve_correlation_conflicts(
                    target_event, candidates
                )
            
            # Calculate correlation confidence
            correlation_confidence = self._calculate_correlation_confidence(
                target_event, best_match, best_time_diff
            )
            
            # Update event correlation metadata
            target_event.correlated_event_id = best_match.event_id
            target_event.correlation_quality = correlation_quality
            target_event.correlation_distance_ms = best_time_diff
            
            best_match.correlated_event_id = target_event.event_id
            best_match.correlation_quality = correlation_quality
            best_match.correlation_distance_ms = best_time_diff
            
            processing_time_ms = (time.perf_counter() - correlation_start) * 1000
            
            # Create successful correlation result
            correlation_result = CorrelationResult(
                success=True,
                primary_event=target_event,
                matched_events=matched_events,
                correlation_quality=correlation_quality,
                correlation_confidence=correlation_confidence,
                time_difference_ms=best_time_diff,
                processing_time_ms=processing_time_ms,
                conflict_resolution_applied=conflict_resolution_applied,
                metadata={
                    'total_candidates': len(candidates),
                    'correlation_algorithm': 'temporal_proximity',
                    'source_diversity': target_event.event_type.value != best_match.event_type.value
                }
            )
            
            # Cache the correlation result
            self.correlation_cache[target_event.event_id] = correlation_result
            
            logger.debug(
                f"Event correlation successful: {target_event.event_id} <-> {best_match.event_id}, "
                f"quality={correlation_quality.value}, time_diff={best_time_diff:.1f}ms"
            )
            
            return correlation_result
            
        except Exception as e:
            logger.error(f"Error correlating event {target_event.event_id}: {e}")
            processing_time_ms = (time.perf_counter() - correlation_start) * 1000
            return CorrelationResult(
                success=False,
                primary_event=target_event,
                correlation_quality=CorrelationQuality.FAILED,
                processing_time_ms=processing_time_ms,
                metadata={'error': str(e)}
            )
    
    def _determine_correlation_quality(self, time_difference_ms: float) -> CorrelationQuality:
        """Determine correlation quality based on time difference"""
        if time_difference_ms <= self.config.perfect_match_threshold_ms:
            return CorrelationQuality.PERFECT
        elif time_difference_ms <= self.config.high_quality_threshold_ms:
            return CorrelationQuality.HIGH
        elif time_difference_ms <= self.config.good_quality_threshold_ms:
            return CorrelationQuality.GOOD
        elif time_difference_ms <= self.config.fair_quality_threshold_ms:
            return CorrelationQuality.FAIR
        else:
            return CorrelationQuality.POOR
    
    def _calculate_correlation_confidence(
        self,
        event1: SynchronizationEvent,
        event2: SynchronizationEvent, 
        time_diff_ms: float
    ) -> float:
        """Calculate correlation confidence score (0.0-1.0)"""
        
        # Base confidence from temporal proximity
        max_time_diff = self.config.max_correlation_distance_ms
        temporal_confidence = 1.0 - (time_diff_ms / max_time_diff)
        
        # Bonus for source diversity
        source_diversity_bonus = 0.0
        if event1.event_type != event2.event_type:
            source_diversity_bonus = 0.1
        
        # Bonus for timing accuracy
        accuracy_bonus = 0.0
        if event1.timing_accuracy_ns and event1.timing_accuracy_ns <= 1000000:  # 1ms accuracy
            accuracy_bonus += 0.05
        if event2.timing_accuracy_ns and event2.timing_accuracy_ns <= 1000000:
            accuracy_bonus += 0.05
        
        # Combine factors
        confidence = min(1.0, temporal_confidence + source_diversity_bonus + accuracy_bonus)
        return confidence
    
    async def _resolve_correlation_conflicts(
        self,
        target_event: SynchronizationEvent,
        candidates: List[Tuple[SynchronizationEvent, float]]
    ) -> bool:
        """Resolve conflicts when multiple correlation candidates exist"""
        
        if self.config.conflict_resolution_strategy == "choose_first":
            # Use first (best time match) candidate
            return False
        
        elif self.config.conflict_resolution_strategy == "choose_best_quality":
            # Already sorted by time difference, so first is best quality
            return False
        
        elif self.config.conflict_resolution_strategy == "merge_events":
            # Advanced: attempt to merge similar events
            return await self._merge_conflicting_events(target_event, candidates)
        
        return False
    
    async def _merge_conflicting_events(
        self,
        target_event: SynchronizationEvent,
        candidates: List[Tuple[SynchronizationEvent, float]]
    ) -> bool:
        """Attempt to merge conflicting events (advanced conflict resolution)"""
        try:
            # Check if events are similar enough to merge
            similar_events = []
            
            for candidate_event, time_diff in candidates:
                # Check similarity criteria
                if (time_diff <= self.config.duplicate_threshold_ms and
                    self._events_are_similar(target_event, candidate_event)):
                    similar_events.append(candidate_event)
            
            if similar_events:
                # Merge events by combining their metadata
                merged_metadata = target_event.source_data.copy()
                
                for similar_event in similar_events:
                    merged_metadata.update(similar_event.source_data)
                
                target_event.source_data = merged_metadata
                target_event.processing_errors.append(
                    f"Merged with {len(similar_events)} similar events"
                )
                
                self.correlation_stats['conflicts_resolved'] += 1
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error merging conflicting events: {e}")
            return False
    
    def _events_are_similar(
        self,
        event1: SynchronizationEvent,
        event2: SynchronizationEvent
    ) -> bool:
        """Check if two events are similar enough to be considered duplicates"""
        
        # Check if from same session
        if event1.session_id != event2.session_id:
            return False
        
        # Check timing proximity
        time_diff_ms = abs(event1.timestamp - event2.timestamp) * 1000
        if time_diff_ms > self.config.duplicate_threshold_ms:
            return False
        
        # Check if source data indicates similar events
        # This could be extended with more sophisticated similarity checks
        source1_voltage = event1.source_data.get('voltage_level', 0)
        source2_voltage = event2.source_data.get('voltage_level', 0)
        
        voltage_diff = abs(source1_voltage - source2_voltage)
        if voltage_diff > 0.5:  # 500mV difference threshold
            return False
        
        return True
    
    def _check_for_duplicates(self, new_event: SynchronizationEvent) -> bool:
        """Check if event is a duplicate of existing events"""
        session_buffer = self.event_buffer[new_event.session_id]
        
        for existing_event in session_buffer:
            if existing_event.event_id == new_event.event_id:
                continue  # Skip self-comparison
            
            if self._events_are_similar(new_event, existing_event):
                logger.debug(f"Duplicate event detected: {new_event.event_id} similar to {existing_event.event_id}")
                return True
        
        return False
    
    def _process_pending_correlations(self):
        """Process pending correlations in background"""
        try:
            with self.lock:
                for session_id in list(self.pending_correlations.keys()):
                    event_ids = self.pending_correlations[session_id]
                    
                    if not event_ids:
                        continue
                    
                    # Process batch of events
                    batch_size = min(self.config.batch_correlation_size, len(event_ids))
                    batch_events = []
                    
                    # Find events to process
                    session_buffer = self.event_buffer[session_id]
                    for event in session_buffer:
                        if event.event_id in event_ids and not event.processed:
                            batch_events.append(event)
                            if len(batch_events) >= batch_size:
                                break
                    
                    # Process batch
                    for event in batch_events:
                        try:
                            # Async correlation in background
                            asyncio.create_task(self._correlate_and_update_event(event))
                            
                            # Remove from pending
                            event_ids.discard(event.event_id)
                            
                        except Exception as e:
                            logger.error(f"Error processing event {event.event_id}: {e}")
                    
                    # Clean up empty sets
                    if not event_ids:
                        del self.pending_correlations[session_id]
                        
        except Exception as e:
            logger.error(f"Error processing pending correlations: {e}")
    
    async def _correlate_and_update_event(self, event: SynchronizationEvent):
        """Correlate event and update statistics"""
        try:
            correlation_result = await self._correlate_event(event)
            
            # Update event processing status
            event.processed = True
            
            # Update statistics
            processing_time = correlation_result.processing_time_ms
            self._update_correlation_stats(correlation_result, processing_time)
            
        except Exception as e:
            logger.error(f"Error correlating and updating event {event.event_id}: {e}")
            event.processing_errors.append(str(e))
            event.processed = True
    
    def _update_correlation_stats(self, result: CorrelationResult, processing_time_ms: float):
        """Update correlation statistics"""
        if result.success:
            self.correlation_stats['successful_correlations'] += 1
        else:
            self.correlation_stats['failed_correlations'] += 1
        
        # Update quality distribution
        quality_key = result.correlation_quality.value
        self.correlation_stats['correlation_quality_distribution'][quality_key] += 1
        
        # Update average processing time
        total_correlations = (
            self.correlation_stats['successful_correlations'] + 
            self.correlation_stats['failed_correlations']
        )
        
        if total_correlations > 0:
            current_avg = self.correlation_stats['average_correlation_time_ms']
            new_avg = ((current_avg * (total_correlations - 1)) + processing_time_ms) / total_correlations
            self.correlation_stats['average_correlation_time_ms'] = new_avg
    
    def _cleanup_correlation_cache(self):
        """Clean up old correlation cache entries"""
        try:
            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(minutes=10)  # Keep cache for 10 minutes
            
            # Remove old cache entries
            expired_keys = []
            for event_id, result in self.correlation_cache.items():
                if result.primary_event.created_at < cutoff_time:
                    expired_keys.append(event_id)
            
            for key in expired_keys:
                del self.correlation_cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired correlation cache entries")
                
        except Exception as e:
            logger.error(f"Error cleaning up correlation cache: {e}")
    
    async def get_session_correlations(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        correlation_quality_filter: Optional[List[CorrelationQuality]] = None
    ) -> List[CorrelationResult]:
        """
        Get correlation results for a session.
        
        Args:
            session_id: Session to query
            start_time: Filter start time (optional)
            end_time: Filter end time (optional)
            correlation_quality_filter: Quality levels to include (optional)
        
        Returns:
            List of correlation results matching criteria
        """
        try:
            with self.lock:
                results = []
                
                # Filter cached correlation results
                for result in self.correlation_cache.values():
                    if result.primary_event.session_id != session_id:
                        continue
                    
                    # Apply time filters
                    if start_time and result.primary_event.created_at < start_time:
                        continue
                    if end_time and result.primary_event.created_at > end_time:
                        continue
                    
                    # Apply quality filter
                    if correlation_quality_filter and result.correlation_quality not in correlation_quality_filter:
                        continue
                    
                    results.append(result)
                
                # Sort by timestamp
                results.sort(key=lambda r: r.primary_event.timestamp)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting session correlations for {session_id}: {e}")
            return []
    
    def get_synchronization_statistics(self) -> Dict[str, Any]:
        """Get comprehensive synchronization statistics"""
        with self.lock:
            # Calculate quality distribution percentages
            total_correlations = sum(self.correlation_stats['correlation_quality_distribution'].values())
            quality_percentages = {}
            
            if total_correlations > 0:
                for quality, count in self.correlation_stats['correlation_quality_distribution'].items():
                    quality_percentages[quality] = (count / total_correlations) * 100
            
            # Calculate success rate
            successful = self.correlation_stats['successful_correlations']
            failed = self.correlation_stats['failed_correlations']
            total_attempts = successful + failed
            success_rate = (successful / max(1, total_attempts)) * 100
            
            return {
                'events_processed': self.correlation_stats['events_processed'],
                'total_correlation_attempts': total_attempts,
                'successful_correlations': successful,
                'failed_correlations': failed,
                'success_rate_percent': success_rate,
                'duplicate_events_detected': self.correlation_stats['duplicate_events_detected'],
                'conflicts_resolved': self.correlation_stats['conflicts_resolved'],
                'average_correlation_time_ms': self.correlation_stats['average_correlation_time_ms'],
                'correlation_quality_distribution': dict(self.correlation_stats['correlation_quality_distribution']),
                'correlation_quality_percentages': quality_percentages,
                'active_sessions': len(self.event_buffer),
                'cached_correlations': len(self.correlation_cache),
                'pending_correlations': sum(len(events) for events in self.pending_correlations.values()),
                'buffer_utilization': {
                    session_id: len(buffer) 
                    for session_id, buffer in self.event_buffer.items()
                }
            }
    
    def shutdown(self):
        """Shutdown the synchronization service"""
        self.processing_active = False
        logger.info("Hybrid event synchronization service shutdown")


# Global service instance
_synchronization_service: Optional[HybridEventSynchronizationService] = None
_service_lock = threading.Lock()


def get_event_synchronization_service() -> HybridEventSynchronizationService:
    """Get global event synchronization service instance (thread-safe singleton)"""
    global _synchronization_service
    
    if _synchronization_service is None:
        with _service_lock:
            if _synchronization_service is None:
                _synchronization_service = HybridEventSynchronizationService()
    
    return _synchronization_service


# Convenience functions for event creation
def create_raw_voltage_event(
    session_id: str,
    timestamp: float,
    voltage_data: Dict[str, float],
    **kwargs
) -> SynchronizationEvent:
    """Create synchronization event from raw voltage data"""
    return SynchronizationEvent(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        event_type=EventType.RAW_VOLTAGE_TRANSITION,
        timestamp=timestamp,
        timestamp_ns=int(timestamp * 1e9),
        source_data={
            'voltage_levels': voltage_data,
            'detection_type': 'raw_voltage',
            **kwargs
        }
    )


def create_video_sync_event(
    session_id: str,
    timestamp: float,
    frame_number: int,
    detection_data: Dict[str, Any],
    **kwargs
) -> SynchronizationEvent:
    """Create synchronization event from video-synchronized detection"""
    return SynchronizationEvent(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        event_type=EventType.VIDEO_SYNC_DETECTION,
        timestamp=timestamp,
        timestamp_ns=int(timestamp * 1e9),
        frame_number=frame_number,
        source_data={
            'frame_number': frame_number,
            'detection_data': detection_data,
            'detection_type': 'video_sync',
            **kwargs
        }
    )


# Export key components
__all__ = [
    'HybridEventSynchronizationService',
    'SynchronizationEvent',
    'CorrelationResult',
    'SynchronizationConfig',
    'EventType',
    'CorrelationQuality',
    'get_event_synchronization_service',
    'create_raw_voltage_event',
    'create_video_sync_event'
]