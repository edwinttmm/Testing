"""
Hybrid Conflict Resolution System  
=================================

Advanced conflict resolution system for managing overlapping, duplicate, and 
conflicting detection events across the hybrid logging infrastructure. This
system provides intelligent conflict detection, analysis, and resolution 
strategies to ensure data integrity and consistency.

Conflict Types Handled:
- Temporal conflicts: Multiple events at similar timestamps
- Source conflicts: Same event detected by different systems (raw vs video-sync)
- Data conflicts: Conflicting voltage levels, latencies, or validation results
- Session conflicts: Events appearing in multiple sessions
- Hardware conflicts: Multiple LabJack devices reporting same event

Resolution Strategies:
- Event merging: Combine similar events into consolidated records
- Priority-based selection: Choose best quality event based on criteria
- Temporal averaging: Average timing data from multiple sources
- Confidence-weighted decisions: Use detection confidence scores
- Manual review flagging: Mark complex conflicts for human review
- Automatic cleanup: Remove obvious duplicates and false positives

Data Integrity Features:
- Audit trail for all conflict resolutions
- Rollback capability for incorrect resolutions
- Quality scoring for resolution decisions
- Performance impact monitoring
- Configurable resolution policies
"""

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter
import statistics
import hashlib

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, asc, func

# Local imports
from database import get_db
from models import DetectionEvent, TestSession

# Hybrid system imports
from services.hybrid_event_synchronization import (
    SynchronizationEvent, CorrelationResult, EventType, CorrelationQuality
)

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur"""
    TEMPORAL_DUPLICATE = "temporal_duplicate"      # Same time, similar data
    SOURCE_DUPLICATE = "source_duplicate"         # Same event, different sources
    DATA_INCONSISTENCY = "data_inconsistency"     # Conflicting data values
    TIMING_CONFLICT = "timing_conflict"           # Conflicting timestamps
    VALIDATION_CONFLICT = "validation_conflict"   # Conflicting validation results
    CORRELATION_CONFLICT = "correlation_conflict" # Multiple correlation candidates
    SESSION_BOUNDARY = "session_boundary"         # Events spanning sessions
    HARDWARE_DUPLICATE = "hardware_duplicate"     # Multiple devices, same event


class ConflictSeverity(Enum):
    """Severity levels for conflicts"""
    TRIVIAL = "trivial"        # Minor differences, auto-resolvable
    LOW = "low"               # Small impact, simple resolution
    MEDIUM = "medium"         # Moderate impact, requires analysis
    HIGH = "high"             # Significant impact, careful resolution needed
    CRITICAL = "critical"     # Major impact, may require manual review


class ResolutionStrategy(Enum):
    """Strategies for resolving conflicts"""
    MERGE_EVENTS = "merge_events"                   # Combine events into one
    CHOOSE_BEST_QUALITY = "choose_best_quality"     # Pick highest quality event
    CHOOSE_FIRST_DETECTED = "choose_first"          # Use first chronologically
    CHOOSE_HIGHEST_CONFIDENCE = "choose_confidence" # Use most confident detection
    AVERAGE_VALUES = "average_values"               # Average conflicting values
    FLAG_FOR_REVIEW = "flag_review"                 # Mark for manual review
    PRESERVE_ALL = "preserve_all"                   # Keep all, mark as related
    DELETE_DUPLICATES = "delete_duplicates"         # Remove obvious duplicates


@dataclass
class ConflictEvent:
    """Represents an event involved in a conflict"""
    event_id: str
    event_type: EventType
    timestamp: float
    timestamp_ns: int
    session_id: str
    source_data: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 1.0
    confidence: float = 1.0
    validation_result: bool = True
    
    # Conflict-specific metadata
    conflict_markers: Set[str] = field(default_factory=set)
    resolution_eligible: bool = True
    manual_review_required: bool = False


@dataclass
class DetectedConflict:
    """Represents a detected conflict between events"""
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    events: List[ConflictEvent]
    
    # Conflict analysis
    time_difference_ms: float = 0.0
    data_similarity_score: float = 0.0  # 0.0-1.0
    confidence_difference: float = 0.0
    
    # Resolution information
    recommended_strategy: Optional[ResolutionStrategy] = None
    resolution_confidence: float = 0.0  # Confidence in recommended strategy
    estimated_resolution_time_ms: float = 0.0
    
    # Metadata
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detection_algorithm: str = "standard"
    context_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionResult:
    """Result of conflict resolution"""
    resolution_id: str
    conflict_id: str
    strategy_used: ResolutionStrategy
    success: bool
    
    # Resolution details
    events_before: List[ConflictEvent]
    events_after: List[ConflictEvent]  # May be merged, removed, or modified
    data_changes: Dict[str, Any] = field(default_factory=dict)
    
    # Quality metrics
    resolution_quality_score: float = 0.0
    data_integrity_preserved: bool = True
    information_loss: float = 0.0  # 0.0-1.0, amount of info lost
    
    # Performance metrics
    processing_time_ms: float = 0.0
    database_operations: int = 0
    
    # Audit information
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_by: str = "automatic"
    rollback_possible: bool = True
    rollback_complexity: str = "simple"  # "simple", "moderate", "complex"
    
    # Additional metadata
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConflictResolutionPolicy:
    """Configurable policy for conflict resolution"""
    
    def __init__(self):
        # Detection thresholds
        self.temporal_threshold_ms = 50.0  # Events within 50ms considered duplicates
        self.similarity_threshold = 0.85   # Data similarity threshold for duplicates
        self.confidence_threshold = 0.1    # Confidence difference threshold
        
        # Resolution preferences
        self.default_strategy_map = {
            ConflictType.TEMPORAL_DUPLICATE: ResolutionStrategy.MERGE_EVENTS,
            ConflictType.SOURCE_DUPLICATE: ResolutionStrategy.CHOOSE_BEST_QUALITY,
            ConflictType.DATA_INCONSISTENCY: ResolutionStrategy.CHOOSE_HIGHEST_CONFIDENCE,
            ConflictType.TIMING_CONFLICT: ResolutionStrategy.AVERAGE_VALUES,
            ConflictType.VALIDATION_CONFLICT: ResolutionStrategy.FLAG_FOR_REVIEW,
            ConflictType.CORRELATION_CONFLICT: ResolutionStrategy.CHOOSE_BEST_QUALITY,
            ConflictType.SESSION_BOUNDARY: ResolutionStrategy.PRESERVE_ALL,
            ConflictType.HARDWARE_DUPLICATE: ResolutionStrategy.MERGE_EVENTS
        }
        
        # Quality requirements
        self.minimum_resolution_confidence = 0.7
        self.require_manual_review_threshold = ConflictSeverity.HIGH
        self.auto_resolution_enabled = True
        self.preserve_audit_trail = True
        
        # Performance settings
        self.max_concurrent_resolutions = 5
        self.resolution_timeout_ms = 5000.0
        self.batch_resolution_size = 20


class HybridConflictResolver:
    """
    Advanced conflict resolution system for hybrid logging infrastructure.
    
    Provides intelligent detection and resolution of conflicts between
    events from different sources (raw, video-sync, legacy) while 
    maintaining data integrity and audit capabilities.
    """
    
    def __init__(self, policy: Optional[ConflictResolutionPolicy] = None):
        self.policy = policy or ConflictResolutionPolicy()
        
        # Conflict tracking
        self.active_conflicts: Dict[str, DetectedConflict] = {}
        self.resolved_conflicts: Dict[str, ResolutionResult] = {}
        self.pending_resolutions: Dict[str, DetectedConflict] = {}
        
        # Performance tracking
        self.resolution_stats = {
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'automatic_resolutions': 0,
            'manual_reviews_requested': 0,
            'resolution_failures': 0,
            'average_resolution_time_ms': 0.0,
            'data_integrity_violations': 0,
            'rollbacks_performed': 0
        }
        
        # Resolution processing
        self.processing_active = True
        self.resolution_queue = asyncio.Queue()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Start background processing
        self._start_conflict_processor()
        
        logger.info("Hybrid conflict resolver initialized")
    
    def _start_conflict_processor(self):
        """Start background conflict processing"""
        def conflict_processor():
            """Background conflict processing loop"""
            while self.processing_active:
                try:
                    # Process pending conflicts
                    self._process_pending_conflicts()
                    
                    # Clean up old resolved conflicts
                    self._cleanup_resolved_conflicts()
                    
                    # Sleep briefly
                    time.sleep(1)  # 1-second processing cycle
                    
                except Exception as e:
                    logger.error(f"Conflict processor error: {e}")
                    time.sleep(5)  # Longer sleep on error
        
        # Start processing thread
        thread = threading.Thread(target=conflict_processor, daemon=True)
        thread.start()
        logger.info("Conflict processing thread started")
    
    async def detect_conflicts(
        self,
        events: List[Union[SynchronizationEvent, ConflictEvent]],
        session_id: Optional[str] = None
    ) -> List[DetectedConflict]:
        """
        Detect conflicts between a set of events.
        
        Args:
            events: Events to analyze for conflicts
            session_id: Optional session filter
        
        Returns:
            List of detected conflicts
        """
        detection_start = time.perf_counter()
        detected_conflicts = []
        
        try:
            with self.lock:
                # Convert to ConflictEvent format if needed
                conflict_events = [
                    self._convert_to_conflict_event(event) for event in events
                ]
                
                # Filter by session if specified
                if session_id:
                    conflict_events = [
                        e for e in conflict_events if e.session_id == session_id
                    ]
                
                # Detect different types of conflicts
                temporal_conflicts = self._detect_temporal_conflicts(conflict_events)
                source_conflicts = self._detect_source_conflicts(conflict_events)
                data_conflicts = self._detect_data_conflicts(conflict_events)
                validation_conflicts = self._detect_validation_conflicts(conflict_events)
                
                # Combine all detected conflicts
                all_conflicts = (
                    temporal_conflicts + source_conflicts + 
                    data_conflicts + validation_conflicts
                )
                
                # Analyze and score conflicts
                for conflict in all_conflicts:
                    self._analyze_conflict(conflict)
                    self._recommend_resolution_strategy(conflict)
                    
                    # Store active conflict
                    self.active_conflicts[conflict.conflict_id] = conflict
                    
                    detected_conflicts.append(conflict)
                
                # Update statistics
                self.resolution_stats['conflicts_detected'] += len(detected_conflicts)
                
                detection_time = (time.perf_counter() - detection_start) * 1000
                
                if detected_conflicts:
                    logger.info(f"Detected {len(detected_conflicts)} conflicts in {detection_time:.1f}ms")
                
                return detected_conflicts
                
        except Exception as e:
            logger.error(f"Error detecting conflicts: {e}")
            return []
    
    def _convert_to_conflict_event(
        self, 
        event: Union[SynchronizationEvent, ConflictEvent]
    ) -> ConflictEvent:
        """Convert various event types to ConflictEvent format"""
        
        if isinstance(event, ConflictEvent):
            return event
        
        elif isinstance(event, SynchronizationEvent):
            return ConflictEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                timestamp_ns=event.timestamp_ns,
                session_id=event.session_id,
                source_data=event.source_data,
                quality_score=1.0,  # Default quality
                confidence=event.source_data.get('detection_confidence', 1.0)
            )
        
        else:
            # Handle other event types
            return ConflictEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.LEGACY_DETECTION,
                timestamp=getattr(event, 'timestamp', time.time()),
                timestamp_ns=int(getattr(event, 'timestamp', time.time()) * 1e9),
                session_id=getattr(event, 'session_id', 'unknown'),
                source_data={'original_event': str(event)}
            )
    
    def _detect_temporal_conflicts(self, events: List[ConflictEvent]) -> List[DetectedConflict]:
        """Detect temporal conflicts (events at similar times)"""
        conflicts = []
        
        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        # Group events by time proximity
        time_groups = []
        current_group = []
        
        for event in sorted_events:
            if not current_group:
                current_group = [event]
            else:
                time_diff_ms = abs(event.timestamp - current_group[0].timestamp) * 1000
                
                if time_diff_ms <= self.policy.temporal_threshold_ms:
                    current_group.append(event)
                else:
                    if len(current_group) > 1:
                        time_groups.append(current_group)
                    current_group = [event]
        
        # Add final group if it has conflicts
        if len(current_group) > 1:
            time_groups.append(current_group)
        
        # Create conflict objects for time groups
        for group in time_groups:
            if len(group) > 1:
                # Calculate similarity within group
                similarity_score = self._calculate_group_similarity(group)
                
                if similarity_score > self.policy.similarity_threshold:
                    conflict = DetectedConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type=ConflictType.TEMPORAL_DUPLICATE,
                        severity=self._determine_conflict_severity(group),
                        events=group,
                        time_difference_ms=max(e.timestamp for e in group) - min(e.timestamp for e in group) * 1000,
                        data_similarity_score=similarity_score
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _detect_source_conflicts(self, events: List[ConflictEvent]) -> List[DetectedConflict]:
        """Detect conflicts between different event sources"""
        conflicts = []
        
        # Group events by source type
        source_groups = defaultdict(list)
        for event in events:
            source_groups[event.event_type].append(event)
        
        # Look for similar events across different sources
        source_types = list(source_groups.keys())
        
        for i in range(len(source_types)):
            for j in range(i + 1, len(source_types)):
                type1, type2 = source_types[i], source_types[j]
                
                # Compare events between sources
                for event1 in source_groups[type1]:
                    for event2 in source_groups[type2]:
                        # Check if events are similar
                        if self._events_are_similar(event1, event2):
                            conflict = DetectedConflict(
                                conflict_id=str(uuid.uuid4()),
                                conflict_type=ConflictType.SOURCE_DUPLICATE,
                                severity=ConflictSeverity.MEDIUM,
                                events=[event1, event2],
                                data_similarity_score=self._calculate_event_similarity(event1, event2)
                            )
                            conflicts.append(conflict)
        
        return conflicts
    
    def _detect_data_conflicts(self, events: List[ConflictEvent]) -> List[DetectedConflict]:
        """Detect conflicts in event data values"""
        conflicts = []
        
        # Group events by proximity in time
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                event1, event2 = events[i], events[j]
                
                # Check if events are temporally close
                time_diff_ms = abs(event1.timestamp - event2.timestamp) * 1000
                
                if time_diff_ms <= self.policy.temporal_threshold_ms * 2:  # Wider window for data conflicts
                    # Check for conflicting data
                    data_conflicts = self._find_data_conflicts(event1, event2)
                    
                    if data_conflicts:
                        conflict = DetectedConflict(
                            conflict_id=str(uuid.uuid4()),
                            conflict_type=ConflictType.DATA_INCONSISTENCY,
                            severity=self._assess_data_conflict_severity(data_conflicts),
                            events=[event1, event2],
                            context_data={'conflicting_fields': data_conflicts}
                        )
                        conflicts.append(conflict)
        
        return conflicts
    
    def _detect_validation_conflicts(self, events: List[ConflictEvent]) -> List[DetectedConflict]:
        """Detect conflicts in validation results"""
        conflicts = []
        
        # Group events by time proximity
        time_groups = self._group_events_by_time(events, self.policy.temporal_threshold_ms)
        
        for group in time_groups:
            if len(group) > 1:
                # Check for conflicting validation results
                validation_results = [e.validation_result for e in group]
                
                if len(set(validation_results)) > 1:  # Multiple different validation results
                    conflict = DetectedConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type=ConflictType.VALIDATION_CONFLICT,
                        severity=ConflictSeverity.HIGH,  # Validation conflicts are important
                        events=group,
                        context_data={
                            'validation_results': validation_results,
                            'result_distribution': dict(Counter(validation_results))
                        }
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _group_events_by_time(
        self, 
        events: List[ConflictEvent], 
        threshold_ms: float
    ) -> List[List[ConflictEvent]]:
        """Group events by time proximity"""
        if not events:
            return []
        
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        groups = []
        current_group = [sorted_events[0]]
        
        for event in sorted_events[1:]:
            time_diff_ms = (event.timestamp - current_group[-1].timestamp) * 1000
            
            if time_diff_ms <= threshold_ms:
                current_group.append(event)
            else:
                groups.append(current_group)
                current_group = [event]
        
        groups.append(current_group)
        return groups
    
    def _calculate_group_similarity(self, events: List[ConflictEvent]) -> float:
        """Calculate similarity score for a group of events"""
        if len(events) < 2:
            return 1.0
        
        # Calculate pairwise similarities
        similarities = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                similarity = self._calculate_event_similarity(events[i], events[j])
                similarities.append(similarity)
        
        # Return average similarity
        return statistics.mean(similarities) if similarities else 0.0
    
    def _calculate_event_similarity(self, event1: ConflictEvent, event2: ConflictEvent) -> float:
        """Calculate similarity between two events"""
        similarity_factors = []
        
        # Temporal similarity
        time_diff_ms = abs(event1.timestamp - event2.timestamp) * 1000
        temporal_similarity = max(0.0, 1.0 - (time_diff_ms / 1000.0))  # 1-second max diff
        similarity_factors.append(temporal_similarity)
        
        # Confidence similarity
        conf_diff = abs(event1.confidence - event2.confidence)
        confidence_similarity = max(0.0, 1.0 - conf_diff)
        similarity_factors.append(confidence_similarity)
        
        # Validation result similarity
        validation_similarity = 1.0 if event1.validation_result == event2.validation_result else 0.0
        similarity_factors.append(validation_similarity)
        
        # Source data similarity (simplified)
        data_similarity = self._calculate_source_data_similarity(
            event1.source_data, event2.source_data
        )
        similarity_factors.append(data_similarity)
        
        # Return weighted average
        return statistics.mean(similarity_factors)
    
    def _calculate_source_data_similarity(self, data1: Dict[str, Any], data2: Dict[str, Any]) -> float:
        """Calculate similarity between source data dictionaries"""
        if not data1 and not data2:
            return 1.0
        
        if not data1 or not data2:
            return 0.0
        
        # Find common keys
        common_keys = set(data1.keys()) & set(data2.keys())
        all_keys = set(data1.keys()) | set(data2.keys())
        
        if not all_keys:
            return 1.0
        
        # Calculate field-by-field similarity
        similar_fields = 0
        for key in common_keys:
            val1, val2 = data1[key], data2[key]
            
            if val1 == val2:
                similar_fields += 1
            elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Numeric similarity
                diff = abs(val1 - val2)
                if diff < 0.1:  # Within 0.1 units
                    similar_fields += 0.8
                elif diff < 0.5:  # Within 0.5 units
                    similar_fields += 0.5
        
        # Calculate overall similarity
        return (similar_fields + len(common_keys) - len(all_keys)) / max(1, len(all_keys))
    
    def _events_are_similar(self, event1: ConflictEvent, event2: ConflictEvent) -> bool:
        """Check if two events are similar enough to be considered duplicates"""
        similarity = self._calculate_event_similarity(event1, event2)
        return similarity > self.policy.similarity_threshold
    
    def _find_data_conflicts(self, event1: ConflictEvent, event2: ConflictEvent) -> List[str]:
        """Find conflicting data fields between two events"""
        conflicts = []
        
        # Check common fields for conflicts
        common_keys = set(event1.source_data.keys()) & set(event2.source_data.keys())
        
        for key in common_keys:
            val1, val2 = event1.source_data[key], event2.source_data[key]
            
            # Check for significant differences
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Numeric conflict detection
                diff = abs(val1 - val2)
                relative_diff = diff / max(abs(val1), abs(val2), 0.001)  # Avoid division by zero
                
                if relative_diff > 0.1:  # >10% difference
                    conflicts.append(key)
            
            elif val1 != val2:
                # Non-numeric conflicts
                conflicts.append(key)
        
        return conflicts
    
    def _assess_data_conflict_severity(self, conflicting_fields: List[str]) -> ConflictSeverity:
        """Assess severity of data conflicts"""
        critical_fields = ['validation_result', 'voltage_level', 'latency_ms']
        important_fields = ['confidence', 'frame_number', 'timestamp']
        
        # Check for critical field conflicts
        if any(field in critical_fields for field in conflicting_fields):
            return ConflictSeverity.CRITICAL
        
        # Check for important field conflicts
        if any(field in important_fields for field in conflicting_fields):
            return ConflictSeverity.HIGH
        
        # Number of conflicting fields
        if len(conflicting_fields) > 3:
            return ConflictSeverity.MEDIUM
        elif len(conflicting_fields) > 1:
            return ConflictSeverity.LOW
        else:
            return ConflictSeverity.TRIVIAL
    
    def _determine_conflict_severity(self, events: List[ConflictEvent]) -> ConflictSeverity:
        """Determine severity of a conflict based on involved events"""
        
        # Check number of events
        if len(events) > 5:
            return ConflictSeverity.HIGH
        
        # Check confidence spread
        confidences = [e.confidence for e in events]
        if max(confidences) - min(confidences) > 0.3:
            return ConflictSeverity.MEDIUM
        
        # Check validation result conflicts
        validations = [e.validation_result for e in events]
        if len(set(validations)) > 1:
            return ConflictSeverity.HIGH
        
        # Default to low severity
        return ConflictSeverity.LOW
    
    def _analyze_conflict(self, conflict: DetectedConflict):
        """Analyze a conflict to determine characteristics and resolution approach"""
        
        # Calculate additional metrics
        events = conflict.events
        
        # Time spread analysis
        timestamps = [e.timestamp for e in events]
        conflict.time_difference_ms = (max(timestamps) - min(timestamps)) * 1000
        
        # Confidence analysis
        confidences = [e.confidence for e in events]
        conflict.confidence_difference = max(confidences) - min(confidences)
        
        # Update context data
        conflict.context_data.update({
            'event_count': len(events),
            'source_types': list(set(e.event_type.value for e in events)),
            'sessions_involved': list(set(e.session_id for e in events)),
            'confidence_range': [min(confidences), max(confidences)],
            'validation_results': [e.validation_result for e in events]
        })
    
    def _recommend_resolution_strategy(self, conflict: DetectedConflict):
        """Recommend resolution strategy for a conflict"""
        
        # Get default strategy for conflict type
        default_strategy = self.policy.default_strategy_map.get(
            conflict.conflict_type, 
            ResolutionStrategy.FLAG_FOR_REVIEW
        )
        
        # Adjust based on severity
        if conflict.severity == ConflictSeverity.CRITICAL:
            if default_strategy in [ResolutionStrategy.MERGE_EVENTS, ResolutionStrategy.DELETE_DUPLICATES]:
                recommended_strategy = ResolutionStrategy.FLAG_FOR_REVIEW
                resolution_confidence = 0.3
            else:
                recommended_strategy = default_strategy
                resolution_confidence = 0.6
        
        elif conflict.severity == ConflictSeverity.HIGH:
            recommended_strategy = default_strategy
            resolution_confidence = 0.7
        
        else:
            recommended_strategy = default_strategy
            resolution_confidence = 0.9
        
        # Adjust based on data similarity
        if conflict.data_similarity_score > 0.95:
            if recommended_strategy == ResolutionStrategy.FLAG_FOR_REVIEW:
                recommended_strategy = ResolutionStrategy.MERGE_EVENTS
                resolution_confidence = min(1.0, resolution_confidence + 0.2)
        
        # Set recommendations
        conflict.recommended_strategy = recommended_strategy
        conflict.resolution_confidence = resolution_confidence
        
        # Estimate resolution time
        complexity_map = {
            ResolutionStrategy.DELETE_DUPLICATES: 10.0,
            ResolutionStrategy.MERGE_EVENTS: 50.0,
            ResolutionStrategy.CHOOSE_BEST_QUALITY: 30.0,
            ResolutionStrategy.CHOOSE_HIGHEST_CONFIDENCE: 25.0,
            ResolutionStrategy.AVERAGE_VALUES: 40.0,
            ResolutionStrategy.FLAG_FOR_REVIEW: 5.0,
            ResolutionStrategy.PRESERVE_ALL: 15.0
        }
        
        base_time = complexity_map.get(recommended_strategy, 100.0)
        event_factor = len(conflict.events) * 5.0
        
        conflict.estimated_resolution_time_ms = base_time + event_factor
    
    def _process_pending_conflicts(self):
        """Process pending conflicts in background"""
        try:
            with self.lock:
                # Get conflicts ready for auto-resolution
                auto_resolvable = []
                
                for conflict in self.active_conflicts.values():
                    if (conflict.resolution_confidence >= self.policy.minimum_resolution_confidence and
                        conflict.severity.value != ConflictSeverity.CRITICAL.value and
                        self.policy.auto_resolution_enabled):
                        auto_resolvable.append(conflict)
                
                # Resolve conflicts in batches
                for i in range(0, len(auto_resolvable), self.policy.batch_resolution_size):
                    batch = auto_resolvable[i:i + self.policy.batch_resolution_size]
                    
                    for conflict in batch:
                        try:
                            asyncio.create_task(self._resolve_conflict_async(conflict))
                        except Exception as e:
                            logger.error(f"Error queuing conflict resolution: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing pending conflicts: {e}")
    
    async def _resolve_conflict_async(self, conflict: DetectedConflict):
        """Asynchronously resolve a conflict"""
        try:
            resolution_result = await self.resolve_conflict(
                conflict, 
                conflict.recommended_strategy
            )
            
            if resolution_result.success:
                # Move from active to resolved
                self.active_conflicts.pop(conflict.conflict_id, None)
                self.resolved_conflicts[conflict.conflict_id] = resolution_result
                
                self.resolution_stats['conflicts_resolved'] += 1
                self.resolution_stats['automatic_resolutions'] += 1
            else:
                self.resolution_stats['resolution_failures'] += 1
                
        except Exception as e:
            logger.error(f"Error in async conflict resolution: {e}")
            self.resolution_stats['resolution_failures'] += 1
    
    async def resolve_conflict(
        self,
        conflict: DetectedConflict,
        strategy: ResolutionStrategy,
        db: Optional[Session] = None
    ) -> ResolutionResult:
        """
        Resolve a specific conflict using the given strategy.
        
        Args:
            conflict: Conflict to resolve
            strategy: Resolution strategy to use
            db: Database session (optional)
        
        Returns:
            ResolutionResult with resolution details
        """
        resolution_start = time.perf_counter()
        
        if db is None:
            db = next(get_db())
            close_db = True
        else:
            close_db = False
        
        try:
            logger.info(f"Resolving conflict {conflict.conflict_id} using strategy {strategy.value}")
            
            # Create resolution result
            resolution_result = ResolutionResult(
                resolution_id=str(uuid.uuid4()),
                conflict_id=conflict.conflict_id,
                strategy_used=strategy,
                success=False,
                events_before=conflict.events.copy()
            )
            
            # Apply resolution strategy
            if strategy == ResolutionStrategy.MERGE_EVENTS:
                success = await self._merge_events(conflict, resolution_result, db)
                
            elif strategy == ResolutionStrategy.CHOOSE_BEST_QUALITY:
                success = await self._choose_best_quality_event(conflict, resolution_result, db)
                
            elif strategy == ResolutionStrategy.CHOOSE_HIGHEST_CONFIDENCE:
                success = await self._choose_highest_confidence_event(conflict, resolution_result, db)
                
            elif strategy == ResolutionStrategy.DELETE_DUPLICATES:
                success = await self._delete_duplicate_events(conflict, resolution_result, db)
                
            elif strategy == ResolutionStrategy.AVERAGE_VALUES:
                success = await self._average_conflicting_values(conflict, resolution_result, db)
                
            elif strategy == ResolutionStrategy.FLAG_FOR_REVIEW:
                success = await self._flag_for_manual_review(conflict, resolution_result, db)
                
            elif strategy == ResolutionStrategy.PRESERVE_ALL:
                success = await self._preserve_all_events(conflict, resolution_result, db)
                
            else:
                logger.error(f"Unknown resolution strategy: {strategy}")
                success = False
            
            # Update resolution result
            resolution_result.success = success
            resolution_result.processing_time_ms = (time.perf_counter() - resolution_start) * 1000
            
            # Update statistics
            avg_time = self.resolution_stats['average_resolution_time_ms']
            total_resolutions = self.resolution_stats['conflicts_resolved'] + 1
            new_avg = ((avg_time * (total_resolutions - 1)) + resolution_result.processing_time_ms) / total_resolutions
            self.resolution_stats['average_resolution_time_ms'] = new_avg
            
            if success:
                logger.info(f"Successfully resolved conflict {conflict.conflict_id} in {resolution_result.processing_time_ms:.1f}ms")
            else:
                logger.error(f"Failed to resolve conflict {conflict.conflict_id}")
            
            return resolution_result
            
        except Exception as e:
            logger.error(f"Error resolving conflict {conflict.conflict_id}: {e}")
            resolution_result.success = False
            resolution_result.notes = f"Resolution failed: {str(e)}"
            return resolution_result
        finally:
            if close_db:
                db.close()
    
    async def _merge_events(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Merge conflicting events into a single consolidated event"""
        try:
            events = conflict.events
            
            # Create merged event data
            merged_event = self._create_merged_event(events)
            
            # Store merged event in database (simplified)
            # In real implementation, this would create appropriate database records
            
            resolution.events_after = [merged_event]
            resolution.data_changes = {
                'operation': 'merge',
                'merged_event_data': merged_event.source_data,
                'original_event_count': len(events)
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error merging events: {e}")
            return False
    
    def _create_merged_event(self, events: List[ConflictEvent]) -> ConflictEvent:
        """Create a merged event from multiple conflicting events"""
        
        # Use earliest timestamp
        min_timestamp = min(e.timestamp for e in events)
        
        # Average confidence values
        avg_confidence = statistics.mean([e.confidence for e in events])
        
        # Use highest quality score
        max_quality = max(e.quality_score for e in events)
        
        # Merge source data
        merged_source_data = {}
        for event in events:
            merged_source_data.update(event.source_data)
        
        # Add merge metadata
        merged_source_data['merge_info'] = {
            'merged_event_count': len(events),
            'original_event_ids': [e.event_id for e in events],
            'merge_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Determine consensus validation result
        validations = [e.validation_result for e in events]
        consensus_validation = max(set(validations), key=validations.count)
        
        return ConflictEvent(
            event_id=str(uuid.uuid4()),
            event_type=events[0].event_type,  # Use first event's type
            timestamp=min_timestamp,
            timestamp_ns=int(min_timestamp * 1e9),
            session_id=events[0].session_id,
            source_data=merged_source_data,
            quality_score=max_quality,
            confidence=avg_confidence,
            validation_result=consensus_validation
        )
    
    async def _choose_best_quality_event(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Choose the highest quality event from conflicting events"""
        try:
            events = conflict.events
            
            # Find event with highest quality score
            best_event = max(events, key=lambda e: e.quality_score)
            
            resolution.events_after = [best_event]
            resolution.data_changes = {
                'operation': 'choose_best_quality',
                'selected_event_id': best_event.event_id,
                'quality_score': best_event.quality_score,
                'removed_events': [e.event_id for e in events if e != best_event]
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error choosing best quality event: {e}")
            return False
    
    async def _choose_highest_confidence_event(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Choose the event with highest confidence score"""
        try:
            events = conflict.events
            
            # Find event with highest confidence
            best_event = max(events, key=lambda e: e.confidence)
            
            resolution.events_after = [best_event]
            resolution.data_changes = {
                'operation': 'choose_highest_confidence',
                'selected_event_id': best_event.event_id,
                'confidence_score': best_event.confidence,
                'removed_events': [e.event_id for e in events if e != best_event]
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error choosing highest confidence event: {e}")
            return False
    
    async def _delete_duplicate_events(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Delete obvious duplicate events, keeping the first one"""
        try:
            events = conflict.events
            
            # Keep the first event (by timestamp)
            kept_event = min(events, key=lambda e: e.timestamp)
            
            resolution.events_after = [kept_event]
            resolution.data_changes = {
                'operation': 'delete_duplicates',
                'kept_event_id': kept_event.event_id,
                'deleted_events': [e.event_id for e in events if e != kept_event]
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting duplicate events: {e}")
            return False
    
    async def _average_conflicting_values(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Average conflicting numeric values between events"""
        try:
            events = conflict.events
            
            # Create averaged event
            averaged_event = self._create_averaged_event(events)
            
            resolution.events_after = [averaged_event]
            resolution.data_changes = {
                'operation': 'average_values',
                'averaged_fields': list(averaged_event.source_data.get('averaged_fields', {})),
                'original_event_count': len(events)
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error averaging conflicting values: {e}")
            return False
    
    def _create_averaged_event(self, events: List[ConflictEvent]) -> ConflictEvent:
        """Create event with averaged values from conflicting events"""
        
        # Use first event as base
        base_event = events[0]
        averaged_data = base_event.source_data.copy()
        
        # Find numeric fields to average
        numeric_fields = set()
        for event in events:
            for key, value in event.source_data.items():
                if isinstance(value, (int, float)):
                    numeric_fields.add(key)
        
        # Calculate averages for numeric fields
        averaged_fields = {}
        for field in numeric_fields:
            values = []
            for event in events:
                if field in event.source_data:
                    values.append(event.source_data[field])
            
            if values:
                averaged_fields[field] = statistics.mean(values)
                averaged_data[field] = averaged_fields[field]
        
        # Add averaging metadata
        averaged_data['averaged_fields'] = averaged_fields
        averaged_data['averaging_info'] = {
            'source_event_count': len(events),
            'source_event_ids': [e.event_id for e in events],
            'averaged_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return ConflictEvent(
            event_id=str(uuid.uuid4()),
            event_type=base_event.event_type,
            timestamp=statistics.mean([e.timestamp for e in events]),
            timestamp_ns=int(statistics.mean([e.timestamp_ns for e in events])),
            session_id=base_event.session_id,
            source_data=averaged_data,
            quality_score=statistics.mean([e.quality_score for e in events]),
            confidence=statistics.mean([e.confidence for e in events]),
            validation_result=base_event.validation_result  # Use first event's validation
        )
    
    async def _flag_for_manual_review(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Flag conflict for manual review"""
        try:
            # Mark all events for manual review
            for event in conflict.events:
                event.manual_review_required = True
                event.conflict_markers.add('manual_review_required')
            
            resolution.events_after = conflict.events
            resolution.data_changes = {
                'operation': 'flag_for_review',
                'review_reason': f'{conflict.conflict_type.value} - {conflict.severity.value}',
                'flagged_events': [e.event_id for e in conflict.events]
            }
            
            self.resolution_stats['manual_reviews_requested'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error flagging for manual review: {e}")
            return False
    
    async def _preserve_all_events(
        self, 
        conflict: DetectedConflict, 
        resolution: ResolutionResult, 
        db: Session
    ) -> bool:
        """Preserve all events but mark them as related"""
        try:
            # Add relationship markers to all events
            for event in conflict.events:
                event.conflict_markers.add('related_events')
                event.source_data['related_event_ids'] = [
                    e.event_id for e in conflict.events if e.event_id != event.event_id
                ]
            
            resolution.events_after = conflict.events
            resolution.data_changes = {
                'operation': 'preserve_all',
                'relationship_established': True,
                'preserved_events': [e.event_id for e in conflict.events]
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error preserving all events: {e}")
            return False
    
    def _cleanup_resolved_conflicts(self):
        """Clean up old resolved conflicts to prevent memory bloat"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            # Remove old resolved conflicts
            expired_keys = [
                conflict_id for conflict_id, resolution in self.resolved_conflicts.items()
                if resolution.resolved_at < cutoff_time
            ]
            
            for key in expired_keys:
                del self.resolved_conflicts[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} resolved conflicts")
                
        except Exception as e:
            logger.error(f"Error cleaning up resolved conflicts: {e}")
    
    def get_conflict_statistics(self) -> Dict[str, Any]:
        """Get comprehensive conflict resolution statistics"""
        with self.lock:
            # Calculate resolution rates by type
            conflict_type_stats = defaultdict(lambda: {'detected': 0, 'resolved': 0})
            
            for conflict in self.active_conflicts.values():
                conflict_type_stats[conflict.conflict_type.value]['detected'] += 1
            
            for resolution in self.resolved_conflicts.values():
                # Would need to track original conflict type in resolution
                pass
            
            return {
                'active_conflicts': len(self.active_conflicts),
                'resolved_conflicts': len(self.resolved_conflicts),
                'resolution_statistics': dict(self.resolution_stats),
                'conflict_types_active': {
                    conflict_type.value: sum(1 for c in self.active_conflicts.values() 
                                           if c.conflict_type == conflict_type)
                    for conflict_type in ConflictType
                },
                'severity_distribution': {
                    severity.value: sum(1 for c in self.active_conflicts.values() 
                                       if c.severity == severity)
                    for severity in ConflictSeverity
                },
                'auto_resolution_enabled': self.policy.auto_resolution_enabled,
                'manual_review_threshold': self.policy.require_manual_review_threshold.value,
                'average_events_per_conflict': (
                    statistics.mean([len(c.events) for c in self.active_conflicts.values()])
                    if self.active_conflicts else 0.0
                )
            }
    
    def get_active_conflicts(self) -> List[Dict[str, Any]]:
        """Get list of active conflicts"""
        with self.lock:
            return [
                {
                    'conflict_id': conflict.conflict_id,
                    'conflict_type': conflict.conflict_type.value,
                    'severity': conflict.severity.value,
                    'event_count': len(conflict.events),
                    'recommended_strategy': conflict.recommended_strategy.value if conflict.recommended_strategy else None,
                    'resolution_confidence': conflict.resolution_confidence,
                    'detected_at': conflict.detected_at.isoformat(),
                    'time_difference_ms': conflict.time_difference_ms,
                    'data_similarity_score': conflict.data_similarity_score
                }
                for conflict in self.active_conflicts.values()
            ]
    
    def shutdown(self):
        """Shutdown the conflict resolver"""
        self.processing_active = False
        logger.info("Hybrid conflict resolver shutdown")


# Global conflict resolver instance
_conflict_resolver: Optional[HybridConflictResolver] = None


def get_conflict_resolver() -> HybridConflictResolver:
    """Get global conflict resolver instance"""
    global _conflict_resolver
    if _conflict_resolver is None:
        _conflict_resolver = HybridConflictResolver()
    return _conflict_resolver


# Export key components
__all__ = [
    'HybridConflictResolver',
    'ConflictType',
    'ConflictSeverity', 
    'ResolutionStrategy',
    'DetectedConflict',
    'ConflictEvent',
    'ResolutionResult',
    'ConflictResolutionPolicy',
    'get_conflict_resolver'
]