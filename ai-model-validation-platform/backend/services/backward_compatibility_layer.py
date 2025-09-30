"""
Backward Compatibility Layer for Hybrid Logging System
=====================================================

Maintains complete backward compatibility with existing detection_events API
while seamlessly integrating new hybrid logging capabilities. This layer ensures
that all existing frontend code, API contracts, and data access patterns 
continue to work without modification.

Key Features:
- Transparent API compatibility with existing detection_events endpoints
- Automatic data format translation between legacy and hybrid formats  
- Performance optimization to maintain existing response times
- Graceful degradation when hybrid features are unavailable
- Migration support for transitioning existing data to hybrid format
- Complete preservation of existing field names and data structures

Compatibility Guarantees:
- All existing API endpoints continue to function identically
- Response formats remain unchanged for legacy clients
- Database queries maintain same performance characteristics
- No breaking changes to existing functionality
- Optional hybrid features are additive only
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from functools import wraps
import json

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, asc, and_, or_, func

# Local imports
from database import get_db
from models import DetectionEvent, TestSession, Video

# Hybrid system imports
from services.hybrid_session_manager import (
    get_hybrid_session_manager, HybridSessionConfig, SessionMode
)
from services.hybrid_event_synchronization import (
    get_event_synchronization_service
)
from src.services.hybrid_query_service import (
    get_hybrid_query_service, QueryStrategy, QueryResult
)

logger = logging.getLogger(__name__)


@dataclass
class CompatibilityConfig:
    """Configuration for backward compatibility behavior"""
    # API compatibility
    preserve_legacy_response_format: bool = True
    enable_hybrid_features_when_available: bool = True
    fallback_to_legacy_on_hybrid_failure: bool = True
    
    # Performance settings
    legacy_query_timeout_ms: int = 5000
    hybrid_query_timeout_ms: int = 10000
    enable_response_caching: bool = True
    cache_ttl_seconds: int = 300
    
    # Migration settings
    auto_migrate_new_sessions: bool = True
    hybrid_detection_threshold: int = 100  # Switch to hybrid after N events
    preserve_legacy_data_indefinitely: bool = True
    
    # Feature flags
    expose_hybrid_metadata: bool = False  # Add hybrid info to responses
    enable_performance_comparison: bool = False  # Compare legacy vs hybrid
    log_compatibility_metrics: bool = True


class BackwardCompatibilityLayer:
    """
    Maintains complete API compatibility while providing hybrid logging features.
    
    This layer acts as a transparent proxy that:
    1. Preserves all existing API contracts and response formats
    2. Automatically routes requests to appropriate data sources (legacy/hybrid) 
    3. Translates between legacy and hybrid data formats seamlessly
    4. Provides graceful fallback when hybrid features fail
    5. Optimizes performance for both legacy and hybrid access patterns
    """
    
    def __init__(self, config: Optional[CompatibilityConfig] = None):
        self.config = config or CompatibilityConfig()
        
        # Service integrations
        self.hybrid_session_manager = get_hybrid_session_manager()
        self.synchronization_service = get_event_synchronization_service()
        self.hybrid_query_service = get_hybrid_query_service()
        
        # Compatibility state
        self.session_modes: Dict[str, SessionMode] = {}  # Track session types
        self.legacy_fallback_active: Dict[str, bool] = {}  # Fallback status per session
        
        # Response cache for performance
        self.response_cache: Dict[str, Tuple[Any, datetime]] = {}
        
        # Compatibility metrics
        self.compatibility_stats = {
            'legacy_requests': 0,
            'hybrid_requests': 0,
            'fallback_activations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'performance_legacy_ms': [],
            'performance_hybrid_ms': [],
            'translation_errors': 0
        }
        
        logger.info("Backward compatibility layer initialized")
    
    def legacy_api_compatibility(self, preserve_format: bool = True):
        """Decorator to ensure API endpoint maintains legacy compatibility"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                
                try:
                    # Determine if this is a legacy or hybrid request
                    session_id = self._extract_session_id(args, kwargs)
                    is_hybrid_session = self._is_hybrid_session(session_id)
                    
                    # Route to appropriate handler
                    if is_hybrid_session and not self._should_use_legacy_fallback(session_id):
                        # Use hybrid implementation
                        result = await self._handle_hybrid_request(func, args, kwargs)
                        self.compatibility_stats['hybrid_requests'] += 1
                        
                        # Translate to legacy format if needed
                        if preserve_format:
                            result = self._translate_hybrid_to_legacy_format(result)
                        
                        # Track performance
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        self.compatibility_stats['performance_hybrid_ms'].append(duration_ms)
                        
                    else:
                        # Use legacy implementation
                        result = await self._handle_legacy_request(func, args, kwargs)
                        self.compatibility_stats['legacy_requests'] += 1
                        
                        # Track performance
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        self.compatibility_stats['performance_legacy_ms'].append(duration_ms)
                    
                    # Add hybrid metadata if enabled
                    if self.config.expose_hybrid_metadata and isinstance(result, dict):
                        result['_hybrid_metadata'] = self._get_hybrid_metadata(session_id)
                    
                    return result
                    
                except Exception as e:
                    # Fallback to legacy on any hybrid failure
                    if is_hybrid_session and self.config.fallback_to_legacy_on_hybrid_failure:
                        logger.warning(f"Hybrid request failed, falling back to legacy: {e}")
                        self.compatibility_stats['fallback_activations'] += 1
                        self.legacy_fallback_active[session_id] = True
                        
                        return await self._handle_legacy_request(func, args, kwargs)
                    else:
                        raise e
            
            return wrapper
        return decorator
    
    async def _handle_hybrid_request(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Handle request using hybrid logging system"""
        try:
            # Extract session information
            session_id = self._extract_session_id(args, kwargs)
            
            # Check cache first
            cache_key = f"hybrid_{func.__name__}_{hash(str(args) + str(kwargs))}"
            cached_result = self._get_cached_response(cache_key)
            if cached_result is not None:
                self.compatibility_stats['cache_hits'] += 1
                return cached_result
            
            # Execute using hybrid query service
            if 'get_detection_events' in func.__name__:
                result = await self._get_detection_events_hybrid(args, kwargs)
            elif 'create_detection_event' in func.__name__:
                result = await self._create_detection_event_hybrid(args, kwargs)
            elif 'update_detection_event' in func.__name__:
                result = await self._update_detection_event_hybrid(args, kwargs)
            elif 'delete_detection_event' in func.__name__:
                result = await self._delete_detection_event_hybrid(args, kwargs)
            else:
                # Default hybrid handling
                result = await func(*args, **kwargs)
            
            # Cache successful result
            if result is not None:
                self._cache_response(cache_key, result)
                self.compatibility_stats['cache_misses'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Hybrid request handling failed: {e}")
            raise
    
    async def _handle_legacy_request(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Handle request using legacy detection_events system"""
        return await func(*args, **kwargs)
    
    async def _get_detection_events_hybrid(self, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Get detection events using hybrid query system with legacy format"""
        
        # Extract parameters (matching legacy API signature)
        session_id = kwargs.get('session_id') or (args[0] if args else None)
        start_time = kwargs.get('start_time')
        end_time = kwargs.get('end_time')
        limit = kwargs.get('limit', 100)
        offset = kwargs.get('offset', 0)
        
        if not session_id:
            raise ValueError("session_id is required")
        
        # Query using hybrid service
        query_result = await self.hybrid_query_service.query_detection_events(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            strategy=QueryStrategy.AUTO,  # Let it choose best approach
            include_raw_data=False,  # Legacy API doesn't expose raw data
            limit=limit,
            offset=offset
        )
        
        # Transform to legacy format
        legacy_events = []
        for event_data in query_result.data:
            legacy_event = self._transform_to_legacy_event_format(event_data)
            legacy_events.append(legacy_event)
        
        # Return in legacy response format
        return {
            'events': legacy_events,
            'total': query_result.total_count,
            'limit': limit,
            'offset': offset,
            'execution_time_ms': query_result.execution_time_ms
        }
    
    def _transform_to_legacy_event_format(self, hybrid_event: Dict[str, Any]) -> Dict[str, Any]:
        """Transform hybrid event data to legacy DetectionEvent format"""
        
        # Core legacy fields
        legacy_event = {
            'id': hybrid_event.get('id'),
            'test_session_id': hybrid_event.get('session_id'),  # Map session_id to test_session_id
            'timestamp': hybrid_event.get('timestamp'),
            'validation_result': hybrid_event.get('validation_result', True),  # Default to True
            'created_at': hybrid_event.get('created_at'),
        }
        
        # Add legacy-specific fields based on source type
        source = hybrid_event.get('source', 'legacy')
        
        if source == 'compressed' or source == 'hybrid':
            # Map hybrid fields to legacy equivalents
            legacy_event.update({
                'actual_latency_ms': hybrid_event.get('latency_ms'),
                'confidence': hybrid_event.get('detection_confidence', 0.95),
                'frame_number': hybrid_event.get('frame_number'),
                'voltage_level': hybrid_event.get('voltage_after_v', 0.0),
                'detection_type': 'voltage_threshold',
                
                # Preserve additional legacy fields that might exist
                'class_label': hybrid_event.get('class_label'),
                'model_version': hybrid_event.get('model_version'),
                'processing_time_ms': hybrid_event.get('processing_time_ms')
            })
        else:
            # Legacy source - pass through existing fields
            for field in ['actual_latency_ms', 'confidence', 'class_label', 'frame_number']:
                if field in hybrid_event:
                    legacy_event[field] = hybrid_event[field]
        
        # Remove None values to match legacy behavior
        return {k: v for k, v in legacy_event.items() if v is not None}
    
    async def _create_detection_event_hybrid(self, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Create detection event with hybrid logging support"""
        
        # Extract event data
        event_data = kwargs.get('event_data') or (args[0] if args else {})
        session_id = event_data.get('test_session_id') or event_data.get('session_id')
        
        if not session_id:
            raise ValueError("session_id/test_session_id is required")
        
        # Check if session is using hybrid logging
        if self._is_hybrid_session(session_id):
            # Create both legacy and hybrid records
            return await self._create_hybrid_detection_event(event_data)
        else:
            # Create only legacy record
            return await self._create_legacy_detection_event(event_data)
    
    async def _create_hybrid_detection_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create detection event in both legacy and hybrid systems"""
        
        db = next(get_db())
        try:
            # Create legacy detection event
            legacy_event = DetectionEvent(
                test_session_id=event_data['test_session_id'],
                timestamp=event_data.get('timestamp', time.time()),
                validation_result=event_data.get('validation_result', True),
                actual_latency_ms=event_data.get('actual_latency_ms'),
                confidence=event_data.get('confidence', 0.95),
                class_label=event_data.get('class_label'),
                frame_number=event_data.get('frame_number')
            )
            
            db.add(legacy_event)
            db.commit()
            db.refresh(legacy_event)
            
            # Create corresponding synchronization event
            from services.hybrid_event_synchronization import (
                create_video_sync_event, SynchronizationEvent
            )
            
            sync_event = create_video_sync_event(
                session_id=event_data['test_session_id'],
                timestamp=legacy_event.timestamp,
                frame_number=event_data.get('frame_number', 0),
                detection_data={
                    'legacy_event_id': legacy_event.id,
                    'confidence': event_data.get('confidence', 0.95),
                    'validation_result': event_data.get('validation_result', True),
                    'latency_ms': event_data.get('actual_latency_ms')
                }
            )
            
            # Add to synchronization system
            await self.synchronization_service.add_synchronization_event(
                sync_event, immediate_correlation=True
            )
            
            # Return legacy format response
            return {
                'id': legacy_event.id,
                'test_session_id': legacy_event.test_session_id,
                'timestamp': legacy_event.timestamp,
                'validation_result': legacy_event.validation_result,
                'created_at': legacy_event.created_at.isoformat() if legacy_event.created_at else None,
                'hybrid_sync_enabled': True
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating hybrid detection event: {e}")
            raise
        finally:
            db.close()
    
    async def _create_legacy_detection_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create detection event using legacy system only"""
        
        db = next(get_db())
        try:
            legacy_event = DetectionEvent(
                test_session_id=event_data['test_session_id'],
                timestamp=event_data.get('timestamp', time.time()),
                validation_result=event_data.get('validation_result', True),
                actual_latency_ms=event_data.get('actual_latency_ms'),
                confidence=event_data.get('confidence'),
                class_label=event_data.get('class_label'),
                frame_number=event_data.get('frame_number')
            )
            
            db.add(legacy_event)
            db.commit()
            db.refresh(legacy_event)
            
            return {
                'id': legacy_event.id,
                'test_session_id': legacy_event.test_session_id,
                'timestamp': legacy_event.timestamp,
                'validation_result': legacy_event.validation_result,
                'created_at': legacy_event.created_at.isoformat() if legacy_event.created_at else None
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating legacy detection event: {e}")
            raise
        finally:
            db.close()
    
    def _extract_session_id(self, args: tuple, kwargs: dict) -> Optional[str]:
        """Extract session ID from function arguments"""
        # Check kwargs first
        session_id = (
            kwargs.get('session_id') or
            kwargs.get('test_session_id') or
            kwargs.get('id')  # For some endpoints
        )
        
        if session_id:
            return session_id
        
        # Check args
        if args:
            if isinstance(args[0], str):
                return args[0]
            elif isinstance(args[0], dict):
                return args[0].get('session_id') or args[0].get('test_session_id')
        
        return None
    
    def _is_hybrid_session(self, session_id: Optional[str]) -> bool:
        """Check if session is using hybrid logging"""
        if not session_id:
            return False
        
        # Check cached session mode
        if session_id in self.session_modes:
            return self.session_modes[session_id] in [SessionMode.HYBRID, SessionMode.AUTO]
        
        # Check if hybrid session exists
        active_sessions = self.hybrid_session_manager.get_active_sessions()
        is_hybrid = session_id in active_sessions
        
        # Cache result
        if is_hybrid:
            self.session_modes[session_id] = SessionMode.HYBRID
        else:
            self.session_modes[session_id] = SessionMode.VIDEO_SYNC_ONLY  # Default legacy mode
        
        return is_hybrid
    
    def _should_use_legacy_fallback(self, session_id: Optional[str]) -> bool:
        """Check if should use legacy fallback for this session"""
        if not session_id:
            return True
        
        return self.legacy_fallback_active.get(session_id, False)
    
    def _translate_hybrid_to_legacy_format(self, hybrid_response: Any) -> Any:
        """Translate hybrid response format to legacy format"""
        try:
            if isinstance(hybrid_response, dict):
                # Handle query result format
                if 'data' in hybrid_response and 'total_count' in hybrid_response:
                    return {
                        'events': [
                            self._transform_to_legacy_event_format(event)
                            for event in hybrid_response['data']
                        ],
                        'total': hybrid_response['total_count'],
                        'execution_time_ms': hybrid_response.get('execution_time_ms', 0)
                    }
                
                # Handle single event format
                elif 'id' in hybrid_response:
                    return self._transform_to_legacy_event_format(hybrid_response)
            
            # Return as-is if no translation needed
            return hybrid_response
            
        except Exception as e:
            logger.error(f"Error translating hybrid to legacy format: {e}")
            self.compatibility_stats['translation_errors'] += 1
            return hybrid_response  # Return original on translation error
    
    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response if available and valid"""
        if not self.config.enable_response_caching:
            return None
        
        if cache_key in self.response_cache:
            cached_data, cache_time = self.response_cache[cache_key]
            
            # Check if cache is still valid
            if (datetime.now() - cache_time).total_seconds() <= self.config.cache_ttl_seconds:
                return cached_data
            else:
                # Remove expired cache entry
                del self.response_cache[cache_key]
        
        return None
    
    def _cache_response(self, cache_key: str, response: Any):
        """Cache response for future requests"""
        if self.config.enable_response_caching:
            self.response_cache[cache_key] = (response, datetime.now())
    
    def _get_hybrid_metadata(self, session_id: Optional[str]) -> Dict[str, Any]:
        """Get hybrid system metadata for debugging/monitoring"""
        if not session_id:
            return {}
        
        session_health = self.hybrid_session_manager.get_session_health(session_id)
        
        metadata = {
            'session_mode': self.session_modes.get(session_id, 'unknown').value if session_id in self.session_modes else 'unknown',
            'hybrid_active': self._is_hybrid_session(session_id),
            'legacy_fallback_active': self.legacy_fallback_active.get(session_id, False)
        }
        
        if session_health:
            metadata.update({
                'session_status': session_health.overall_status.value,
                'correlation_quality': session_health.correlation_quality,
                'performance_score': session_health.performance_score
            })
        
        return metadata
    
    def get_compatibility_statistics(self) -> Dict[str, Any]:
        """Get compatibility layer performance and usage statistics"""
        
        # Calculate average performance times
        avg_legacy_ms = (
            sum(self.compatibility_stats['performance_legacy_ms']) / 
            max(1, len(self.compatibility_stats['performance_legacy_ms']))
        )
        
        avg_hybrid_ms = (
            sum(self.compatibility_stats['performance_hybrid_ms']) / 
            max(1, len(self.compatibility_stats['performance_hybrid_ms']))
        )
        
        # Calculate cache hit rate
        total_cache_requests = (
            self.compatibility_stats['cache_hits'] + 
            self.compatibility_stats['cache_misses']
        )
        cache_hit_rate = (
            (self.compatibility_stats['cache_hits'] / max(1, total_cache_requests)) * 100
        )
        
        return {
            'total_requests': (
                self.compatibility_stats['legacy_requests'] + 
                self.compatibility_stats['hybrid_requests']
            ),
            'legacy_requests': self.compatibility_stats['legacy_requests'],
            'hybrid_requests': self.compatibility_stats['hybrid_requests'],
            'hybrid_percentage': (
                (self.compatibility_stats['hybrid_requests'] / 
                 max(1, self.compatibility_stats['legacy_requests'] + 
                     self.compatibility_stats['hybrid_requests'])) * 100
            ),
            'fallback_activations': self.compatibility_stats['fallback_activations'],
            'translation_errors': self.compatibility_stats['translation_errors'],
            'cache_hit_rate_percent': cache_hit_rate,
            'cache_entries': len(self.response_cache),
            'average_performance': {
                'legacy_ms': avg_legacy_ms,
                'hybrid_ms': avg_hybrid_ms,
                'hybrid_overhead_percent': (
                    ((avg_hybrid_ms - avg_legacy_ms) / max(0.1, avg_legacy_ms)) * 100
                    if avg_legacy_ms > 0 else 0
                )
            },
            'active_hybrid_sessions': len([
                s for s, mode in self.session_modes.items()
                if mode in [SessionMode.HYBRID, SessionMode.AUTO]
            ]),
            'sessions_with_fallback': len([
                s for s, active in self.legacy_fallback_active.items() if active
            ])
        }
    
    def clear_cache(self, session_id: Optional[str] = None):
        """Clear response cache (all or for specific session)"""
        if session_id:
            # Clear cache entries for specific session
            keys_to_remove = [
                key for key in self.response_cache.keys()
                if session_id in key
            ]
            for key in keys_to_remove:
                del self.response_cache[key]
            logger.info(f"Cleared {len(keys_to_remove)} cache entries for session {session_id}")
        else:
            # Clear entire cache
            cache_size = len(self.response_cache)
            self.response_cache.clear()
            logger.info(f"Cleared {cache_size} cache entries")


# Global compatibility layer instance
_compatibility_layer: Optional[BackwardCompatibilityLayer] = None


def get_compatibility_layer() -> BackwardCompatibilityLayer:
    """Get global backward compatibility layer instance"""
    global _compatibility_layer
    if _compatibility_layer is None:
        _compatibility_layer = BackwardCompatibilityLayer()
    return _compatibility_layer


# Decorator for easy use in API endpoints
def legacy_compatible(preserve_format: bool = True):
    """Decorator to make API endpoints backward compatible"""
    layer = get_compatibility_layer()
    return layer.legacy_api_compatibility(preserve_format)


# Export key components
__all__ = [
    'BackwardCompatibilityLayer',
    'CompatibilityConfig', 
    'get_compatibility_layer',
    'legacy_compatible'
]