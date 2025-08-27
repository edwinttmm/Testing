#!/usr/bin/env python3
"""
VRU Performance Optimizer - SPARC Implementation
Advanced query optimization and caching for VRU database operations

SPARC Architecture:
- Specification: Performance requirements for real-time VRU detection
- Pseudocode: Optimized query algorithms with caching strategies
- Architecture: Multi-layer optimization system
- Refinement: Production-optimized with monitoring
- Completion: Ready for high-throughput VRU processing
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from functools import wraps, lru_cache
import json
import hashlib
from pathlib import Path

# Caching and optimization imports
from collections import defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor
import weakref

# Database imports
from sqlalchemy import text, func, and_, or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql import text as sql_text

# Add backend root to path
import sys
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from unified_database import get_database_manager
    from models import (
        Video, Project, DetectionEvent, Annotation, TestSession, 
        GroundTruthObject, TestResult, DetectionComparison
    )
    from src.vru_enhanced_models import (
        MLInferenceSession, FrameDetection, ObjectDetection,
        VideoQualityMetrics, SystemPerformanceLog
    )
    from src.vru_database_integration_layer import get_vru_integration_layer
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logging.error(f"Performance optimizer dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    """Cache configuration settings"""
    enable_query_cache: bool = True
    enable_result_cache: bool = True
    query_cache_size: int = 1000
    result_cache_size: int = 500
    cache_ttl_seconds: int = 300  # 5 minutes
    warm_cache_on_startup: bool = True

@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_hash: str
    execution_time_ms: float
    result_count: int
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class QueryCache:
    """Thread-safe query result cache"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache = {}
        self._access_times = {}
        self._lock = threading.RLock()
    
    def _generate_key(self, query: str, params: Dict[str, Any]) -> str:
        """Generate cache key from query and parameters"""
        key_data = f"{query}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _is_expired(self, timestamp: datetime) -> bool:
        """Check if cache entry is expired"""
        return (datetime.now(timezone.utc) - timestamp).total_seconds() > self.ttl_seconds
    
    def _evict_expired(self):
        """Remove expired entries"""
        current_time = datetime.now(timezone.utc)
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if self._is_expired(timestamp)
        ]
        
        for key in expired_keys:
            del self._cache[key]
            self._access_times.pop(key, None)
    
    def _evict_lru(self):
        """Evict least recently used entries"""
        if len(self._cache) <= self.max_size:
            return
        
        # Sort by access time and remove oldest
        sorted_by_access = sorted(
            self._access_times.items(),
            key=lambda x: x[1]
        )
        
        entries_to_remove = len(self._cache) - self.max_size + 1
        for key, _ in sorted_by_access[:entries_to_remove]:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def get(self, query: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached result"""
        with self._lock:
            key = self._generate_key(query, params)
            
            if key not in self._cache:
                return None
            
            result, timestamp = self._cache[key]
            
            if self._is_expired(timestamp):
                del self._cache[key]
                self._access_times.pop(key, None)
                return None
            
            # Update access time
            self._access_times[key] = datetime.now(timezone.utc)
            return result
    
    def set(self, query: str, params: Dict[str, Any], result: Any):
        """Set cache result"""
        with self._lock:
            self._evict_expired()
            
            key = self._generate_key(query, params)
            self._cache[key] = (result, datetime.now(timezone.utc))
            self._access_times[key] = datetime.now(timezone.utc)
            
            self._evict_lru()
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                "entries": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "memory_usage_estimate": len(str(self._cache))
            }

class VRUPerformanceOptimizer:
    """VRU Performance Optimization System"""
    
    def __init__(self, config: CacheConfig = None):
        """Initialize the performance optimizer"""
        if not DEPENDENCIES_AVAILABLE:
            raise RuntimeError("Performance optimizer dependencies not available")
        
        self.config = config or CacheConfig()
        self.db_manager = get_database_manager()
        self.integration_layer = get_vru_integration_layer()
        
        # Initialize caches
        self.query_cache = QueryCache(
            max_size=self.config.query_cache_size,
            ttl_seconds=self.config.cache_ttl_seconds
        ) if self.config.enable_query_cache else None
        
        self.result_cache = QueryCache(
            max_size=self.config.result_cache_size,
            ttl_seconds=self.config.cache_ttl_seconds
        ) if self.config.enable_result_cache else None
        
        # Performance tracking
        self.query_metrics = []
        self.performance_stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "average_query_time": 0.0,
            "slow_queries": []
        }
        
        # Thread pool for async operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        logger.info("VRU Performance Optimizer initialized")
        
        if self.config.warm_cache_on_startup:
            asyncio.create_task(self.warm_cache())
    
    def cached_query(self, cache_key: str = None, ttl: int = None):
        """Decorator for cached queries"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.query_cache:
                    return await func(*args, **kwargs)
                
                # Generate cache key
                key = cache_key or f"{func.__name__}_{str(args)}_{str(kwargs)}"
                
                # Check cache
                cached_result = self.query_cache.get(key, {})
                if cached_result is not None:
                    self.performance_stats["cache_hits"] += 1
                    return cached_result
                
                # Execute query
                start_time = time.time()
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                # Cache result
                self.query_cache.set(key, {}, result)
                
                # Track metrics
                self._track_query_metrics(key, execution_time, len(result) if isinstance(result, list) else 1, False)
                
                return result
            return wrapper
        return decorator
    
    def _track_query_metrics(self, query_hash: str, execution_time: float, 
                           result_count: int, cache_hit: bool):
        """Track query performance metrics"""
        self.performance_stats["total_queries"] += 1
        
        if cache_hit:
            self.performance_stats["cache_hits"] += 1
        
        # Update average query time
        total_time = (self.performance_stats["average_query_time"] * 
                     (self.performance_stats["total_queries"] - 1) + execution_time)
        self.performance_stats["average_query_time"] = total_time / self.performance_stats["total_queries"]
        
        # Track slow queries (> 1000ms)
        if execution_time > 1000:
            self.performance_stats["slow_queries"].append({
                "query_hash": query_hash,
                "execution_time": execution_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Keep only last 100 slow queries
            if len(self.performance_stats["slow_queries"]) > 100:
                self.performance_stats["slow_queries"] = self.performance_stats["slow_queries"][-100:]
        
        # Store detailed metrics
        metrics = QueryMetrics(
            query_hash=query_hash,
            execution_time_ms=execution_time,
            result_count=result_count,
            cache_hit=cache_hit
        )
        
        self.query_metrics.append(metrics)
        
        # Keep only last 1000 metrics
        if len(self.query_metrics) > 1000:
            self.query_metrics = self.query_metrics[-1000:]
    
    @cached_query()
    async def get_project_detection_summary(self, project_id: str, 
                                          days_back: int = 30) -> Dict[str, Any]:
        """Get optimized project detection summary"""
        try:
            with self.db_manager.get_session() as session:
                # Optimized query with proper joins and indexing
                start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
                
                # Main detection statistics
                detection_stats = session.query(
                    func.count(DetectionEvent.id).label('total_detections'),
                    func.avg(DetectionEvent.confidence).label('avg_confidence'),
                    func.count(DetectionEvent.id).filter(DetectionEvent.validation_result == 'TP').label('true_positives'),
                    func.count(DetectionEvent.id).filter(DetectionEvent.validation_result == 'FP').label('false_positives')
                ).join(TestSession).filter(
                    and_(
                        TestSession.project_id == project_id,
                        DetectionEvent.created_at >= start_date
                    )
                ).first()
                
                # VRU type distribution with optimized grouping
                vru_distribution = session.query(
                    DetectionEvent.vru_type,
                    func.count(DetectionEvent.id).label('count'),
                    func.avg(DetectionEvent.confidence).label('avg_confidence')
                ).join(TestSession).filter(
                    and_(
                        TestSession.project_id == project_id,
                        DetectionEvent.created_at >= start_date
                    )
                ).group_by(DetectionEvent.vru_type).all()
                
                # Model performance comparison
                model_performance = session.query(
                    DetectionEvent.model_version,
                    func.count(DetectionEvent.id).label('count'),
                    func.avg(DetectionEvent.confidence).label('avg_confidence'),
                    func.avg(DetectionEvent.processing_time_ms).label('avg_processing_time')
                ).join(TestSession).filter(
                    and_(
                        TestSession.project_id == project_id,
                        DetectionEvent.created_at >= start_date
                    )
                ).group_by(DetectionEvent.model_version).all()
                
                return {
                    "project_id": project_id,
                    "period_days": days_back,
                    "summary": {
                        "total_detections": detection_stats.total_detections or 0,
                        "average_confidence": float(detection_stats.avg_confidence or 0),
                        "true_positives": detection_stats.true_positives or 0,
                        "false_positives": detection_stats.false_positives or 0,
                        "accuracy": (
                            (detection_stats.true_positives or 0) / 
                            max((detection_stats.true_positives or 0) + (detection_stats.false_positives or 0), 1)
                        )
                    },
                    "vru_distribution": [
                        {
                            "vru_type": vru.vru_type,
                            "count": vru.count,
                            "average_confidence": float(vru.avg_confidence)
                        }
                        for vru in vru_distribution
                    ],
                    "model_performance": [
                        {
                            "model_version": model.model_version or "unknown",
                            "detection_count": model.count,
                            "average_confidence": float(model.avg_confidence),
                            "average_processing_time_ms": float(model.avg_processing_time or 0)
                        }
                        for model in model_performance
                    ]
                }
                
        except Exception as e:
            logger.error(f"Failed to get project detection summary: {e}")
            return {"error": str(e)}
    
    @cached_query()
    async def get_video_processing_efficiency(self, video_id: str) -> Dict[str, Any]:
        """Get video processing efficiency metrics"""
        try:
            with self.db_manager.get_session() as session:
                # Video metadata with processing stats
                video_stats = session.query(
                    Video.duration,
                    Video.fps,
                    func.count(DetectionEvent.id).label('total_detections'),
                    func.avg(DetectionEvent.processing_time_ms).label('avg_processing_time'),
                    func.min(DetectionEvent.created_at).label('first_detection'),
                    func.max(DetectionEvent.created_at).label('last_detection')
                ).outerjoin(
                    TestSession, Video.id == TestSession.video_id
                ).outerjoin(
                    DetectionEvent, TestSession.id == DetectionEvent.test_session_id
                ).filter(Video.id == video_id).first()
                
                if not video_stats:
                    return {"error": "Video not found"}
                
                # Calculate processing efficiency
                total_frames = int((video_stats.duration or 0) * (video_stats.fps or 30))
                processing_duration = None
                
                if video_stats.first_detection and video_stats.last_detection:
                    processing_duration = (
                        video_stats.last_detection - video_stats.first_detection
                    ).total_seconds()
                
                # Detection density analysis
                detection_density = session.query(
                    func.floor(DetectionEvent.timestamp / 10).label('time_bucket'),
                    func.count(DetectionEvent.id).label('detections_per_10s')
                ).join(TestSession).filter(
                    TestSession.video_id == video_id
                ).group_by(func.floor(DetectionEvent.timestamp / 10)).all()
                
                return {
                    "video_id": video_id,
                    "video_metrics": {
                        "duration_seconds": video_stats.duration or 0,
                        "fps": video_stats.fps or 30,
                        "estimated_frames": total_frames
                    },
                    "processing_metrics": {
                        "total_detections": video_stats.total_detections or 0,
                        "average_processing_time_ms": float(video_stats.avg_processing_time or 0),
                        "processing_duration_seconds": processing_duration,
                        "detections_per_second": (
                            (video_stats.total_detections or 0) / max(video_stats.duration or 1, 1)
                        ),
                        "processing_efficiency": (
                            (video_stats.duration or 0) / max(processing_duration or 1, 1)
                            if processing_duration else None
                        )
                    },
                    "temporal_distribution": [
                        {
                            "time_bucket_start": int(bucket.time_bucket * 10),
                            "detections_count": bucket.detections_per_10s
                        }
                        for bucket in detection_density
                    ]
                }
                
        except Exception as e:
            logger.error(f"Failed to get video processing efficiency: {e}")
            return {"error": str(e)}
    
    async def optimize_database_indexes(self) -> Dict[str, Any]:
        """Optimize database indexes for better performance"""
        optimization_results = {
            "indexes_analyzed": 0,
            "indexes_created": 0,
            "indexes_optimized": 0,
            "recommendations": []
        }
        
        try:
            with self.db_manager.get_session() as session:
                # Analyze query patterns and suggest indexes
                slow_queries = [
                    {
                        "table": "detection_events",
                        "columns": ["test_session_id", "timestamp", "vru_type"],
                        "index_name": "idx_detection_events_session_temporal_vru"
                    },
                    {
                        "table": "annotations", 
                        "columns": ["video_id", "validated", "timestamp"],
                        "index_name": "idx_annotations_video_validated_temporal"
                    },
                    {
                        "table": "videos",
                        "columns": ["project_id", "processing_status", "ground_truth_generated"],
                        "index_name": "idx_videos_project_processing_gt"
                    }
                ]
                
                for index_info in slow_queries:
                    try:
                        # Check if index exists
                        index_check = session.execute(text(f"""
                            SELECT 1 FROM pg_indexes 
                            WHERE indexname = '{index_info['index_name']}'
                        """ if not self.db_manager.settings.is_sqlite() else f"""
                            SELECT 1 FROM sqlite_master 
                            WHERE type = 'index' AND name = '{index_info['index_name']}'
                        """)).fetchone()
                        
                        if not index_check:
                            # Create index
                            columns_str = ", ".join(index_info['columns'])
                            create_index_sql = f"""
                                CREATE INDEX IF NOT EXISTS {index_info['index_name']} 
                                ON {index_info['table']} ({columns_str})
                            """
                            
                            session.execute(text(create_index_sql))
                            optimization_results["indexes_created"] += 1
                            
                            logger.info(f"✅ Created index: {index_info['index_name']}")
                        
                        optimization_results["indexes_analyzed"] += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to create index {index_info['index_name']}: {e}")
                        optimization_results["recommendations"].append(
                            f"Manual creation needed for {index_info['index_name']}: {e}"
                        )
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            optimization_results["error"] = str(e)
        
        return optimization_results
    
    async def warm_cache(self):
        """Warm up caches with frequently accessed data"""
        try:
            logger.info("🔥 Warming up performance caches...")
            
            with self.db_manager.get_session() as session:
                # Get active projects for cache warming
                active_projects = session.query(Project.id).filter(
                    Project.status == "Active"
                ).limit(10).all()
                
                # Warm cache with project summaries
                for project in active_projects:
                    try:
                        await self.get_project_detection_summary(project.id)
                    except Exception as e:
                        logger.warning(f"Cache warming failed for project {project.id}: {e}")
                
                logger.info(f"✅ Cache warmed with {len(active_projects)} projects")
                
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        try:
            cache_stats = {}
            if self.query_cache:
                cache_stats["query_cache"] = self.query_cache.stats()
            if self.result_cache:
                cache_stats["result_cache"] = self.result_cache.stats()
            
            # Recent query performance
            recent_metrics = self.query_metrics[-100:] if self.query_metrics else []
            avg_recent_time = (
                sum(m.execution_time_ms for m in recent_metrics) / len(recent_metrics)
                if recent_metrics else 0
            )
            
            return {
                "optimizer_config": {
                    "query_cache_enabled": self.config.enable_query_cache,
                    "result_cache_enabled": self.config.enable_result_cache,
                    "cache_ttl_seconds": self.config.cache_ttl_seconds
                },
                "cache_statistics": cache_stats,
                "query_performance": {
                    "total_queries": self.performance_stats["total_queries"],
                    "cache_hits": self.performance_stats["cache_hits"],
                    "cache_hit_rate": (
                        self.performance_stats["cache_hits"] / max(self.performance_stats["total_queries"], 1)
                    ),
                    "average_query_time_ms": self.performance_stats["average_query_time"],
                    "recent_average_time_ms": avg_recent_time,
                    "slow_query_count": len(self.performance_stats["slow_queries"])
                },
                "recommendations": self._generate_performance_recommendations()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}")
            return {"error": str(e)}
    
    def _generate_performance_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # Cache hit rate analysis
        if self.performance_stats["total_queries"] > 100:
            hit_rate = (
                self.performance_stats["cache_hits"] / self.performance_stats["total_queries"]
            )
            
            if hit_rate < 0.3:
                recommendations.append(
                    "Low cache hit rate detected. Consider increasing cache TTL or size."
                )
            elif hit_rate > 0.8:
                recommendations.append(
                    "Excellent cache performance! Consider expanding cache to more queries."
                )
        
        # Slow query analysis
        if len(self.performance_stats["slow_queries"]) > 10:
            recommendations.append(
                f"Found {len(self.performance_stats['slow_queries'])} slow queries. "
                "Consider adding database indexes or query optimization."
            )
        
        # Average query time analysis
        if self.performance_stats["average_query_time"] > 500:
            recommendations.append(
                "High average query time detected. Consider database optimization or query refactoring."
            )
        
        return recommendations
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.query_cache:
                self.query_cache.clear()
            if self.result_cache:
                self.result_cache.clear()
            
            self.thread_pool.shutdown(wait=True)
            
            logger.info("✅ Performance optimizer cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

# =============================================================================
# GLOBAL OPTIMIZER INSTANCE
# =============================================================================

_optimizer = None

def get_performance_optimizer(config: CacheConfig = None) -> VRUPerformanceOptimizer:
    """Get or create global performance optimizer instance"""
    global _optimizer
    if _optimizer is None:
        _optimizer = VRUPerformanceOptimizer(config)
    return _optimizer

if __name__ == "__main__":
    # Test performance optimizer
    async def test_optimizer():
        print("🚀 Testing VRU Performance Optimizer")
        print("=" * 50)
        
        if not DEPENDENCIES_AVAILABLE:
            print("❌ Dependencies not available")
            return
        
        try:
            # Create optimizer
            config = CacheConfig(
                enable_query_cache=True,
                enable_result_cache=True,
                cache_ttl_seconds=60
            )
            
            optimizer = VRUPerformanceOptimizer(config)
            
            # Test cache functionality
            print("✅ Optimizer initialized")
            
            # Test performance report
            report = await optimizer.get_performance_report()
            print(f"✅ Performance report generated: {len(report)} sections")
            
            # Test database optimization
            optimization_results = await optimizer.optimize_database_indexes()
            print(f"✅ Database optimization: {optimization_results['indexes_analyzed']} indexes analyzed")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        
        print("=" * 50)
    
    # Run test
    asyncio.run(test_optimizer())