# System Improvements - Phase 3 Implementation Guide

## Overview

This document covers performance optimizations, user experience improvements, and system hardening that should be implemented after the critical fixes and core functionality are complete.

## Pre-Implementation Checklist

- [ ] Phase 1 (Critical Fixes) completed
- [ ] Phase 2 (Core Functionality) completed  
- [ ] System is stable and all tests pass
- [ ] Performance baseline established

---

## Improvement 1: Performance Optimization

**Priority**: MEDIUM  
**Estimated Time**: 3-4 days  
**Risk Level**: Low  

### Problem Analysis

Current performance issues:
- API response times > 5 seconds for large datasets
- Frontend memory leaks causing browser crashes
- Inefficient database queries
- Large JavaScript bundle sizes
- No caching layer implemented

### Performance Baseline

Before implementing improvements, establish baseline metrics:

```bash
# Create performance test script
# backend/tests/performance_baseline.py

import time
import requests
import psutil
import json
from concurrent.futures import ThreadPoolExecutor
import statistics

class PerformanceBaseline:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = {}
    
    def measure_api_performance(self):
        """Measure API endpoint performance"""
        
        endpoints = [
            "/api/projects",
            "/api/videos", 
            "/auth/me",
            "/api/dashboard/stats"
        ]
        
        for endpoint in endpoints:
            response_times = []
            
            for _ in range(10):  # 10 requests per endpoint
                start_time = time.time()
                try:
                    response = requests.get(f"{self.base_url}{endpoint}")
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        response_times.append(response_time)
                        
                except Exception as e:
                    print(f"Error testing {endpoint}: {e}")
            
            if response_times:
                self.results[endpoint] = {
                    "avg_response_time": statistics.mean(response_times),
                    "min_response_time": min(response_times),
                    "max_response_time": max(response_times),
                    "median_response_time": statistics.median(response_times)
                }
    
    def measure_concurrent_load(self):
        """Test concurrent request handling"""
        
        def make_request():
            start_time = time.time()
            response = requests.get(f"{self.base_url}/api/projects")
            return time.time() - start_time, response.status_code
        
        # Test with 10, 20, 50 concurrent requests
        for concurrent_users in [10, 20, 50]:
            with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
                futures = [executor.submit(make_request) for _ in range(concurrent_users)]
                results = [future.result() for future in futures]
                
                response_times = [r[0] for r in results if r[1] == 200]
                success_rate = len(response_times) / len(results) * 100
                
                self.results[f"concurrent_{concurrent_users}"] = {
                    "success_rate": success_rate,
                    "avg_response_time": statistics.mean(response_times) if response_times else None,
                    "max_response_time": max(response_times) if response_times else None
                }
    
    def measure_memory_usage(self):
        """Measure current memory usage"""
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        self.results["memory"] = {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent()
        }
    
    def run_all_tests(self):
        """Run all performance tests"""
        print("Running performance baseline tests...")
        
        print("Testing API performance...")
        self.measure_api_performance()
        
        print("Testing concurrent load...")
        self.measure_concurrent_load()
        
        print("Measuring memory usage...")
        self.measure_memory_usage()
        
        # Save results
        with open("performance_baseline_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print("Performance baseline complete!")
        print(json.dumps(self.results, indent=2))

if __name__ == "__main__":
    baseline = PerformanceBaseline()
    baseline.run_all_tests()
```

### Implementation Plan

#### Step 1: Database Query Optimization

Create `backend/optimized_queries.py`:

```python
from sqlalchemy import text, Index
from sqlalchemy.orm import selectinload, joinedload
from database import engine, SessionLocal

class QueryOptimizer:
    def __init__(self):
        self.db = SessionLocal()
    
    async def create_missing_indexes(self):
        """Create performance-critical indexes"""
        
        indexes = [
            # Video queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_project_status_created ON videos(project_id, status, created_at DESC);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_filename_search ON videos USING gin(to_tsvector('english', filename));",
            
            # Annotation queries  
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_annotations_video_frame_vru ON annotations(video_id, frame_number, vru_type);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_annotations_validated_created ON annotations(validated, created_at DESC);",
            
            # Detection events
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detection_events_session_timestamp ON detection_events(test_session_id, timestamp);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detection_events_video_timestamp ON detection_events(video_id, timestamp);",
            
            # User and session queries
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auth_users_active_created ON auth_users(is_active, created_at DESC);",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_test_sessions_project_status ON test_sessions(project_id, status, created_at DESC);"
        ]
        
        for index_sql in indexes:
            try:
                await self.db.execute(text(index_sql))
                print(f"✓ Created index")
            except Exception as e:
                print(f"⚠ Index creation failed: {e}")
        
        await self.db.commit()
    
    def get_optimized_project_videos(self, project_id: str, page: int = 1, per_page: int = 50):
        """Optimized query for project videos with metadata"""
        
        offset = (page - 1) * per_page
        
        # Use raw SQL for complex queries
        query = text("""
            SELECT 
                v.*,
                COUNT(DISTINCT a.id) as annotation_count,
                COUNT(DISTINCT gt.id) as ground_truth_count,
                AVG(a.confidence) as avg_annotation_confidence
            FROM videos v
            LEFT JOIN annotations a ON v.id = a.video_id AND a.validated = true
            LEFT JOIN ground_truth_objects gt ON v.id = gt.video_id
            WHERE v.project_id = :project_id
            AND v.status != 'deleted'
            GROUP BY v.id
            ORDER BY v.created_at DESC
            LIMIT :per_page OFFSET :offset
        """)
        
        result = self.db.execute(query, {
            "project_id": project_id,
            "per_page": per_page,
            "offset": offset
        })
        
        return result.fetchall()
    
    def get_video_analytics_summary(self, video_id: str):
        """Get comprehensive video analytics in single query"""
        
        query = text("""
            WITH video_stats AS (
                SELECT 
                    v.*,
                    COUNT(DISTINCT a.id) as total_annotations,
                    COUNT(DISTINCT CASE WHEN a.validated THEN a.id END) as validated_annotations,
                    COUNT(DISTINCT a.vru_type) as unique_vru_types,
                    COUNT(DISTINCT gt.id) as ground_truth_count,
                    COUNT(DISTINCT de.id) as detection_events_count
                FROM videos v
                LEFT JOIN annotations a ON v.id = a.video_id
                LEFT JOIN ground_truth_objects gt ON v.id = gt.video_id  
                LEFT JOIN detection_events de ON v.id = de.video_id
                WHERE v.id = :video_id
                GROUP BY v.id
            ),
            frame_coverage AS (
                SELECT 
                    COUNT(DISTINCT frame_number) as annotated_frames,
                    MIN(frame_number) as first_annotated_frame,
                    MAX(frame_number) as last_annotated_frame
                FROM annotations 
                WHERE video_id = :video_id
            )
            SELECT 
                vs.*,
                fc.annotated_frames,
                fc.first_annotated_frame,
                fc.last_annotated_frame,
                CASE 
                    WHEN vs.total_frames > 0 
                    THEN (fc.annotated_frames * 100.0 / vs.total_frames)
                    ELSE 0 
                END as frame_coverage_percent
            FROM video_stats vs
            CROSS JOIN frame_coverage fc
        """)
        
        result = self.db.execute(query, {"video_id": video_id})
        return result.fetchone()

# Repository pattern for optimized queries
class OptimizedVideoRepository:
    def __init__(self, db_session):
        self.db = db_session
    
    async def get_videos_with_stats(
        self, 
        project_id: str, 
        filters: dict = None, 
        page: int = 1, 
        per_page: int = 50
    ):
        """Get videos with pre-computed statistics"""
        
        # Build dynamic query based on filters
        base_query = self.db.query(Video).options(
            # Use selectinload for collections to avoid N+1 queries
            selectinload(Video.annotations),
            selectinload(Video.ground_truth_objects)
        ).filter(
            Video.project_id == project_id,
            Video.status != 'deleted'
        )
        
        # Apply filters
        if filters:
            if filters.get('status'):
                base_query = base_query.filter(Video.status == filters['status'])
            
            if filters.get('has_annotations'):
                base_query = base_query.join(Video.annotations)
            
            if filters.get('min_duration'):
                base_query = base_query.filter(Video.duration >= filters['min_duration'])
        
        # Get total count for pagination
        total_count = base_query.count()
        
        # Get paginated results
        videos = base_query.order_by(Video.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        return {
            "videos": videos,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "has_next": (page * per_page) < total_count
        }
```

#### Step 2: API Caching Layer

Create `backend/caching.py`:

```python
import redis
import json
import asyncio
from typing import Any, Optional, Callable
from functools import wraps
import hashlib
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = 300  # 5 minutes
        
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = f"{prefix}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            cached_value = self.redis_client.get(key)
            if cached_value:
                return json.loads(cached_value)
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL"""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache pattern invalidation failed for {pattern}: {e}")

# Cache decorator
cache_manager = CacheManager()

def cached(ttl: int = 300, key_prefix: str = "api"):
    """Decorator to cache function results"""
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_manager._generate_cache_key(
                f"{key_prefix}:{func.__name__}", *args, **kwargs
            )
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {cache_key}")
            
            return result
        
        return wrapper
    return decorator

# Apply caching to API endpoints
@cached(ttl=600, key_prefix="projects")
async def get_project_with_stats(project_id: str):
    """Cached project data with statistics"""
    # Implementation would go here
    pass

@cached(ttl=300, key_prefix="videos")
async def get_video_annotations(video_id: str, frame_range: tuple = None):
    """Cached video annotations"""
    # Implementation would go here
    pass
```

#### Step 3: Frontend Performance Optimization

Create `frontend/src/hooks/usePerformanceOptimization.ts`:

```typescript
import { useCallback, useMemo, useRef, useEffect } from 'react';
import { debounce, throttle } from 'lodash';

// Memory management hook
export const useMemoryManager = () => {
  const resourcesRef = useRef<Set<() => void>>(new Set());
  
  const addCleanupResource = useCallback((cleanup: () => void) => {
    resourcesRef.current.add(cleanup);
  }, []);
  
  const removeCleanupResource = useCallback((cleanup: () => void) => {
    resourcesRef.current.delete(cleanup);
  }, []);
  
  useEffect(() => {
    return () => {
      // Clean up all resources on unmount
      resourcesRef.current.forEach(cleanup => {
        try {
          cleanup();
        } catch (error) {
          console.warn('Cleanup function failed:', error);
        }
      });
      resourcesRef.current.clear();
    };
  }, []);
  
  return { addCleanupResource, removeCleanupResource };
};

// Optimized video loading hook
export const useOptimizedVideoLoading = () => {
  const videoCache = useRef<Map<string, HTMLVideoElement>>(new Map());
  const { addCleanupResource } = useMemoryManager();
  
  const preloadVideo = useCallback((videoUrl: string) => {
    if (videoCache.current.has(videoUrl)) {
      return videoCache.current.get(videoUrl)!;
    }
    
    const video = document.createElement('video');
    video.src = videoUrl;
    video.preload = 'metadata';
    video.load();
    
    videoCache.current.set(videoUrl, video);
    
    // Add cleanup
    const cleanup = () => {
      video.src = '';
      video.load();
      videoCache.current.delete(videoUrl);
    };
    
    addCleanupResource(cleanup);
    
    return video;
  }, [addCleanupResource]);
  
  const getVideoElement = useCallback((videoUrl: string) => {
    return videoCache.current.get(videoUrl);
  }, []);
  
  const clearCache = useCallback(() => {
    videoCache.current.forEach((video, url) => {
      video.src = '';
      video.load();
    });
    videoCache.current.clear();
  }, []);
  
  return { preloadVideo, getVideoElement, clearCache };
};

// Debounced API calls hook
export const useOptimizedApiCalls = () => {
  const pendingRequests = useRef<Map<string, AbortController>>(new Map());
  
  const debouncedApiCall = useMemo(() => 
    debounce(async (key: string, apiCall: () => Promise<any>) => {
      // Cancel previous request
      const existingController = pendingRequests.current.get(key);
      if (existingController) {
        existingController.abort();
      }
      
      // Create new abort controller
      const controller = new AbortController();
      pendingRequests.current.set(key, controller);
      
      try {
        const result = await apiCall();
        pendingRequests.current.delete(key);
        return result;
      } catch (error) {
        if (error.name !== 'AbortError') {
          pendingRequests.current.delete(key);
          throw error;
        }
      }
    }, 300)
  , []);
  
  const throttledApiCall = useMemo(() =>
    throttle(async (key: string, apiCall: () => Promise<any>) => {
      return apiCall();
    }, 1000)
  , []);
  
  useEffect(() => {
    return () => {
      // Abort all pending requests on cleanup
      pendingRequests.current.forEach((controller) => {
        controller.abort();
      });
      pendingRequests.current.clear();
    };
  }, []);
  
  return { debouncedApiCall, throttledApiCall };
};

// Virtual scrolling for large lists
export const useVirtualScrolling = (
  itemCount: number,
  itemHeight: number,
  containerHeight: number
) => {
  const [scrollTop, setScrollTop] = useState(0);
  
  const visibleItems = useMemo(() => {
    const startIndex = Math.floor(scrollTop / itemHeight);
    const visibleCount = Math.ceil(containerHeight / itemHeight) + 2; // Buffer
    const endIndex = Math.min(startIndex + visibleCount, itemCount);
    
    return {
      startIndex: Math.max(0, startIndex),
      endIndex,
      visibleCount: endIndex - startIndex
    };
  }, [scrollTop, itemHeight, containerHeight, itemCount]);
  
  const handleScroll = useCallback(
    throttle((event: React.UIEvent<HTMLDivElement>) => {
      setScrollTop(event.currentTarget.scrollTop);
    }, 16), // ~60fps
    []
  );
  
  return {
    visibleItems,
    handleScroll,
    totalHeight: itemCount * itemHeight
  };
};
```

#### Step 4: Bundle Size Optimization

Create `frontend/webpack.optimization.js`:

```javascript
const path = require('path');
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;
const CompressionPlugin = require('compression-webpack-plugin');

module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        // Vendor libraries
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
        },
        
        // Material-UI separate chunk
        mui: {
          test: /[\\/]node_modules[\\/]@mui[\\/]/,
          name: 'mui',
          chunks: 'all',
        },
        
        // Chart libraries
        charts: {
          test: /[\\/]node_modules[\\/](chart\.js|react-chartjs-2|recharts)[\\/]/,
          name: 'charts',
          chunks: 'all',
        },
        
        // Video processing libraries
        video: {
          test: /[\\/]node_modules[\\/](video\.js|hls\.js)[\\/]/,
          name: 'video',
          chunks: 'all',
        },
        
        // Common components
        common: {
          name: 'common',
          minChunks: 2,
          chunks: 'all',
          enforce: true,
        },
      },
    },
    
    // Runtime chunk
    runtimeChunk: {
      name: 'runtime',
    },
    
    // Minimize
    minimize: true,
    minimizer: [
      new TerserPlugin({
        terserOptions: {
          parse: {
            ecma: 8,
          },
          compress: {
            ecma: 5,
            warnings: false,
            comparisons: false,
            inline: 2,
            drop_console: process.env.NODE_ENV === 'production',
          },
          mangle: {
            safari10: true,
          },
          output: {
            ecma: 5,
            comments: false,
            ascii_only: true,
          },
        },
      }),
    ],
  },
  
  plugins: [
    // Gzip compression
    new CompressionPlugin({
      algorithm: 'gzip',
      test: /\.(js|css|html|svg)$/,
      threshold: 8192,
      minRatio: 0.8,
    }),
    
    // Bundle analyzer (only in analysis mode)
    process.env.ANALYZE && new BundleAnalyzerPlugin(),
  ].filter(Boolean),
  
  resolve: {
    alias: {
      // Optimize imports
      '@mui/icons-material': '@mui/icons-material/esm',
      
      // Tree shaking for lodash
      'lodash': 'lodash-es',
    },
  },
  
  module: {
    rules: [
      {
        test: /\.(js|jsx|ts|tsx)$/,
        use: [
          {
            loader: 'babel-loader',
            options: {
              presets: [
                ['@babel/preset-env', { modules: false }],
                '@babel/preset-react',
                '@babel/preset-typescript',
              ],
              plugins: [
                // Tree shaking for Material-UI
                ['babel-plugin-import', {
                  libraryName: '@mui/material',
                  libraryDirectory: '',
                  camel2DashComponentName: false,
                }, 'core'],
                ['babel-plugin-import', {
                  libraryName: '@mui/icons-material',
                  libraryDirectory: '',
                  camel2DashComponentName: false,
                }, 'icons'],
                
                // Optimize lodash imports
                'lodash',
              ],
            },
          },
        ],
        exclude: /node_modules/,
      },
    ],
  },
};
```

#### Step 5: Performance Monitoring

Create `backend/monitoring.py`:

```python
import time
import psutil
from functools import wraps
from typing import Dict, List
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            "api_calls": [],
            "slow_queries": [],
            "memory_usage": [],
            "error_rates": {}
        }
        self.slow_query_threshold = 1.0  # seconds
    
    def record_api_call(self, endpoint: str, duration: float, status_code: int):
        """Record API call metrics"""
        self.metrics["api_calls"].append({
            "endpoint": endpoint,
            "duration": duration,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only recent data (last 1000 calls)
        if len(self.metrics["api_calls"]) > 1000:
            self.metrics["api_calls"] = self.metrics["api_calls"][-1000:]
    
    def record_slow_query(self, query: str, duration: float, params: Dict = None):
        """Record slow database queries"""
        if duration > self.slow_query_threshold:
            self.metrics["slow_queries"].append({
                "query": query[:200] + "..." if len(query) > 200 else query,
                "duration": duration,
                "params": str(params) if params else None,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Keep only recent slow queries (last 100)
            if len(self.metrics["slow_queries"]) > 100:
                self.metrics["slow_queries"] = self.metrics["slow_queries"][-100:]
    
    def record_memory_usage(self):
        """Record current memory usage"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        self.metrics["memory_usage"].append({
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last hour of data
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.metrics["memory_usage"] = [
            m for m in self.metrics["memory_usage"]
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]
    
    def get_performance_summary(self) -> Dict:
        """Get performance metrics summary"""
        api_calls = self.metrics["api_calls"]
        
        if not api_calls:
            return {"message": "No data available"}
        
        # Calculate API metrics
        recent_calls = [call for call in api_calls 
                      if datetime.fromisoformat(call["timestamp"]) > 
                      datetime.utcnow() - timedelta(minutes=10)]
        
        durations = [call["duration"] for call in recent_calls]
        error_calls = [call for call in recent_calls if call["status_code"] >= 400]
        
        summary = {
            "api_performance": {
                "total_calls_last_10min": len(recent_calls),
                "avg_response_time": sum(durations) / len(durations) if durations else 0,
                "max_response_time": max(durations) if durations else 0,
                "error_rate": len(error_calls) / len(recent_calls) if recent_calls else 0,
                "slow_calls": len([d for d in durations if d > 2.0])
            },
            "database": {
                "slow_queries_count": len(self.metrics["slow_queries"]),
                "avg_slow_query_time": sum(q["duration"] for q in self.metrics["slow_queries"]) / 
                                     len(self.metrics["slow_queries"]) if self.metrics["slow_queries"] else 0
            },
            "memory": {
                "current_usage_mb": self.metrics["memory_usage"][-1]["rss_mb"] if self.metrics["memory_usage"] else 0,
                "peak_usage_mb": max(m["rss_mb"] for m in self.metrics["memory_usage"]) if self.metrics["memory_usage"] else 0
            }
        }
        
        return summary

# Global monitor instance
performance_monitor = PerformanceMonitor()

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Record successful call
            endpoint = getattr(func, '__name__', 'unknown')
            performance_monitor.record_api_call(endpoint, duration, 200)
            
            if duration > 2.0:  # Log slow calls
                logger.warning(f"Slow API call: {endpoint} took {duration:.2f}s")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            endpoint = getattr(func, '__name__', 'unknown')
            performance_monitor.record_api_call(endpoint, duration, 500)
            raise
    
    return wrapper

# Add monitoring endpoint
from fastapi import APIRouter
router = APIRouter()

@router.get("/api/monitoring/performance")
async def get_performance_metrics():
    """Get current performance metrics"""
    
    # Record current memory usage
    performance_monitor.record_memory_usage()
    
    # Get summary
    summary = performance_monitor.get_performance_summary()
    
    return APIResponse.success_response(data=summary)

@router.get("/api/monitoring/health")
async def health_check():
    """Enhanced health check with performance data"""
    
    try:
        # Check database connection
        db_status = "healthy"
        db_response_time = 0
        
        start_time = time.time()
        # Test database query
        # db.execute("SELECT 1")  # Uncomment when database is available
        db_response_time = time.time() - start_time
        
        # Check memory usage
        process = psutil.Process()
        memory_percent = process.memory_percent()
        
        # Determine overall health
        health_status = "healthy"
        if memory_percent > 80:
            health_status = "warning"
        if memory_percent > 95 or db_response_time > 5:
            health_status = "critical"
        
        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": {
                    "status": db_status,
                    "response_time_ms": db_response_time * 1000
                },
                "memory": {
                    "status": "healthy" if memory_percent < 80 else "warning",
                    "usage_percent": memory_percent
                }
            },
            "performance_summary": performance_monitor.get_performance_summary()
        }
        
    except Exception as e:
        return {
            "status": "critical",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
```

---

## Improvement 2: User Experience Enhancement

**Priority**: MEDIUM  
**Estimated Time**: 2-3 days  
**Risk Level**: Low  

### Problem Analysis

Current UX issues:
- No loading states or progress indicators
- Error messages are technical and unhelpful
- No keyboard shortcuts or accessibility features
- Mobile experience is poor
- No user guidance or onboarding

### Implementation Plan

#### Step 1: Loading States and Progress Indicators

Create `frontend/src/components/UI/LoadingStates.tsx`:

```typescript
import React from 'react';
import { CircularProgress, LinearProgress, Skeleton } from '@mui/material';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ 
  size = 'medium', 
  message 
}) => {
  const sizeMap = {
    small: 20,
    medium: 40,
    large: 60
  };

  return (
    <div className="loading-spinner" style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      gap: '16px' 
    }}>
      <CircularProgress size={sizeMap[size]} />
      {message && <p>{message}</p>}
    </div>
  );
};

interface ProgressBarProps {
  progress: number;
  label?: string;
  showPercentage?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  label,
  showPercentage = true
}) => {
  return (
    <div className="progress-bar-container" style={{ width: '100%' }}>
      {label && <div className="progress-label">{label}</div>}
      <LinearProgress 
        variant="determinate" 
        value={progress} 
        style={{ height: '8px', borderRadius: '4px' }}
      />
      {showPercentage && (
        <div className="progress-percentage" style={{ textAlign: 'right', marginTop: '4px' }}>
          {progress.toFixed(1)}%
        </div>
      )}
    </div>
  );
};

export const VideoListSkeleton: React.FC<{ count?: number }> = ({ count = 5 }) => {
  return (
    <div className="video-list-skeleton">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
          <Skeleton variant="rectangular" width={120} height={80} />
          <div style={{ flex: 1 }}>
            <Skeleton variant="text" width="60%" height={24} />
            <Skeleton variant="text" width="40%" height={20} />
            <Skeleton variant="text" width="80%" height={20} />
          </div>
        </div>
      ))}
    </div>
  );
};

export const ProjectCardSkeleton: React.FC<{ count?: number }> = ({ count = 3 }) => {
  return (
    <div className="project-cards-skeleton" style={{ 
      display: 'grid', 
      gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
      gap: '16px' 
    }}>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} style={{ padding: '16px', border: '1px solid #e0e0e0', borderRadius: '8px' }}>
          <Skeleton variant="text" width="70%" height={28} />
          <Skeleton variant="text" width="50%" height={20} style={{ margin: '8px 0' }} />
          <Skeleton variant="text" width="100%" height={60} />
          <Skeleton variant="rectangular" width="100%" height={40} style={{ marginTop: '16px' }} />
        </div>
      ))}
    </div>
  );
};
```

#### Step 2: Enhanced Error Handling and User Feedback

Create `frontend/src/components/UI/ErrorHandling.tsx`:

```typescript
import React from 'react';
import { Alert, AlertTitle, Button, Snackbar } from '@mui/material';
import { RefreshOutlined, ReportProblemOutlined } from '@mui/icons-material';

interface ErrorMessageProps {
  error: Error | string;
  onRetry?: () => void;
  severity?: 'error' | 'warning' | 'info';
  showDetails?: boolean;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  error,
  onRetry,
  severity = 'error',
  showDetails = false
}) => {
  const errorMessage = typeof error === 'string' ? error : error.message;
  
  const getUserFriendlyMessage = (message: string): string => {
    // Convert technical errors to user-friendly messages
    const errorMappings: Record<string, string> = {
      'Network Error': 'Unable to connect to the server. Please check your internet connection.',
      'Unauthorized': 'Your session has expired. Please log in again.',
      'Forbidden': 'You don\'t have permission to perform this action.',
      'Not Found': 'The requested resource could not be found.',
      'Internal Server Error': 'Something went wrong on our end. Please try again later.',
      'Bad Request': 'There was an issue with your request. Please check your input.',
      'Service Unavailable': 'The service is temporarily unavailable. Please try again later.',
      'Request Timeout': 'The request took too long to complete. Please try again.',
      'File too large': 'The file you selected is too large. Please choose a smaller file.',
      'Unsupported file format': 'The file format is not supported. Please use a different file type.',
    };
    
    for (const [technical, friendly] of Object.entries(errorMappings)) {
      if (message.includes(technical)) {
        return friendly;
      }
    }
    
    return message;
  };

  const friendlyMessage = getUserFriendlyMessage(errorMessage);

  return (
    <Alert 
      severity={severity}
      action={
        onRetry && (
          <Button 
            color="inherit" 
            size="small" 
            onClick={onRetry}
            startIcon={<RefreshOutlined />}
          >
            Retry
          </Button>
        )
      }
    >
      <AlertTitle>
        {severity === 'error' ? 'Error' : 
         severity === 'warning' ? 'Warning' : 'Information'}
      </AlertTitle>
      {friendlyMessage}
      {showDetails && (
        <details style={{ marginTop: '8px' }}>
          <summary>Technical details</summary>
          <pre style={{ fontSize: '12px', marginTop: '8px' }}>
            {typeof error === 'string' ? error : error.stack || error.message}
          </pre>
        </details>
      )}
    </Alert>
  );
};

interface NotificationProps {
  open: boolean;
  message: string;
  severity?: 'success' | 'error' | 'warning' | 'info';
  onClose: () => void;
  autoHideDuration?: number;
}

export const Notification: React.FC<NotificationProps> = ({
  open,
  message,
  severity = 'info',
  onClose,
  autoHideDuration = 6000
}) => {
  return (
    <Snackbar
      open={open}
      autoHideDuration={autoHideDuration}
      onClose={onClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
    >
      <Alert onClose={onClose} severity={severity} sx={{ width: '100%' }}>
        {message}
      </Alert>
    </Snackbar>
  );
};

// Global notification context
interface NotificationContextType {
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
  showWarning: (message: string) => void;
  showInfo: (message: string) => void;
}

const NotificationContext = React.createContext<NotificationContextType | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Array<{
    id: string;
    message: string;
    severity: 'success' | 'error' | 'warning' | 'info';
  }>>([]);

  const addNotification = (message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    const id = Date.now().toString();
    setNotifications(prev => [...prev, { id, message, severity }]);
    
    // Auto remove after 6 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 6000);
  };

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const contextValue: NotificationContextType = {
    showSuccess: (message: string) => addNotification(message, 'success'),
    showError: (message: string) => addNotification(message, 'error'),
    showWarning: (message: string) => addNotification(message, 'warning'),
    showInfo: (message: string) => addNotification(message, 'info'),
  };

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      <div style={{ position: 'fixed', top: 24, right: 24, zIndex: 9999 }}>
        {notifications.map(notification => (
          <Notification
            key={notification.id}
            open={true}
            message={notification.message}
            severity={notification.severity}
            onClose={() => removeNotification(notification.id)}
          />
        ))}
      </div>
    </NotificationContext.Provider>
  );
};

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};
```

#### Step 3: Keyboard Shortcuts and Accessibility

Create `frontend/src/hooks/useKeyboardShortcuts.ts`:

```typescript
import { useEffect, useCallback } from 'react';

interface KeyboardShortcut {
  key: string;
  metaKey?: boolean;
  ctrlKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  action: () => void;
  description: string;
  disabled?: boolean;
}

export const useKeyboardShortcuts = (shortcuts: KeyboardShortcut[]) => {
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Don't trigger shortcuts if user is typing in an input
    if (event.target instanceof HTMLInputElement || 
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement) {
      return;
    }

    const matchingShortcut = shortcuts.find(shortcut => {
      if (shortcut.disabled) return false;
      
      return (
        shortcut.key.toLowerCase() === event.key.toLowerCase() &&
        !!shortcut.metaKey === event.metaKey &&
        !!shortcut.ctrlKey === event.ctrlKey &&
        !!shortcut.altKey === event.altKey &&
        !!shortcut.shiftKey === event.shiftKey
      );
    });

    if (matchingShortcut) {
      event.preventDefault();
      matchingShortcut.action();
    }
  }, [shortcuts]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);

  return shortcuts;
};

// Common shortcuts component
export const KeyboardShortcutsHelp: React.FC<{ 
  shortcuts: KeyboardShortcut[];
  open: boolean;
  onClose: () => void;
}> = ({ shortcuts, open, onClose }) => {
  const formatShortcut = (shortcut: KeyboardShortcut): string => {
    const parts = [];
    
    if (shortcut.metaKey) parts.push('Cmd');
    if (shortcut.ctrlKey) parts.push('Ctrl');
    if (shortcut.altKey) parts.push('Alt');
    if (shortcut.shiftKey) parts.push('Shift');
    parts.push(shortcut.key.toUpperCase());
    
    return parts.join(' + ');
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Keyboard Shortcuts</DialogTitle>
      <DialogContent>
        <List>
          {shortcuts.map((shortcut, index) => (
            <ListItem key={index}>
              <ListItemText
                primary={shortcut.description}
                secondary={formatShortcut(shortcut)}
              />
            </ListItem>
          ))}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

// Usage example for video player
export const useVideoPlayerShortcuts = (videoRef: React.RefObject<HTMLVideoElement>) => {
  const shortcuts: KeyboardShortcut[] = [
    {
      key: ' ',
      action: () => {
        if (videoRef.current) {
          if (videoRef.current.paused) {
            videoRef.current.play();
          } else {
            videoRef.current.pause();
          }
        }
      },
      description: 'Play/Pause video'
    },
    {
      key: 'ArrowLeft',
      action: () => {
        if (videoRef.current) {
          videoRef.current.currentTime -= 5;
        }
      },
      description: 'Skip backward 5 seconds'
    },
    {
      key: 'ArrowRight',
      action: () => {
        if (videoRef.current) {
          videoRef.current.currentTime += 5;
        }
      },
      description: 'Skip forward 5 seconds'
    },
    {
      key: 'm',
      action: () => {
        if (videoRef.current) {
          videoRef.current.muted = !videoRef.current.muted;
        }
      },
      description: 'Mute/Unmute'
    },
    {
      key: 'f',
      action: () => {
        if (videoRef.current) {
          if (document.fullscreenElement) {
            document.exitFullscreen();
          } else {
            videoRef.current.requestFullscreen();
          }
        }
      },
      description: 'Toggle fullscreen'
    }
  ];

  return useKeyboardShortcuts(shortcuts);
};
```

This completes the system improvements documentation. The implementation includes performance optimizations, user experience enhancements, and system monitoring capabilities.