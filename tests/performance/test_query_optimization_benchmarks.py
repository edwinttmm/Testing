"""
Performance Benchmarks for Query Optimization
Tests query performance with new many-to-many structure,
validates image loading performance, and tests large dataset handling.
"""

import pytest
import asyncio
import time
import random
import uuid
import statistics
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor
import memory_profiler
import psutil
import os


class TestQueryOptimizationBenchmarks:
    """Performance benchmarks for database query optimization"""
    
    @pytest.fixture
    def performance_test_data(self):
        """Generate large dataset for performance testing"""
        # Generate test projects
        projects = []
        for i in range(100):
            projects.append({
                "id": str(uuid.uuid4()),
                "name": f"Performance Test Project {i:03d}",
                "description": f"Project for performance testing - batch {i // 10}",
                "camera_view": random.choice(["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]),
                "camera_model": f"TestCam-{random.choice(['Pro', 'Basic', 'Advanced'])}",
                "signal_type": random.choice(["GPIO", "Network Packet", "Serial"]),
                "status": random.choice(["Active", "Completed", "Draft"]),
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))
            })
        
        # Generate test videos
        videos = []
        for i in range(1000):
            videos.append({
                "id": str(uuid.uuid4()),
                "filename": f"test_video_{i:04d}.mp4",
                "file_path": f"/uploads/videos/test_video_{i:04d}.mp4",
                "duration": random.uniform(30.0, 300.0),
                "fps": random.choice([24, 30, 60]),
                "resolution": random.choice(["1920x1080", "1280x720", "3840x2160"]),
                "file_size": random.randint(10000000, 500000000),  # 10MB to 500MB
                "status": random.choice(["uploaded", "processing", "ready"]),
                "ground_truth_generated": random.choice([True, False]),
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180))
            })
        
        # Generate video-project links (many-to-many)
        links = []
        link_id_counter = 0
        
        for video in videos:
            # Each video linked to 1-5 projects
            num_projects = random.randint(1, 5)
            selected_projects = random.sample(projects, min(num_projects, len(projects)))
            
            for project in selected_projects:
                links.append({
                    "id": str(uuid.uuid4()),
                    "video_id": video["id"],
                    "project_id": project["id"],
                    "intelligent_match": random.choice([True, False]),
                    "confidence_score": random.uniform(0.6, 1.0),
                    "assignment_reason": f"Test assignment {link_id_counter}",
                    "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 90))
                })
                link_id_counter += 1
        
        return {
            "projects": projects,
            "videos": videos,
            "links": links,
            "total_projects": len(projects),
            "total_videos": len(videos),
            "total_links": len(links)
        }
    
    @pytest.fixture
    def mock_database_with_indexes(self, performance_test_data):
        """Mock database with proper indexing for performance testing"""
        class MockIndexedDatabase:
            def __init__(self, test_data):
                self.data = test_data
                
                # Create indexes for fast lookups
                self._create_indexes()
            
            def _create_indexes(self):
                """Create optimized indexes for common queries"""
                # Project indexes
                self.project_by_id = {p["id"]: p for p in self.data["projects"]}
                self.projects_by_status = {}
                self.projects_by_camera_view = {}
                
                for project in self.data["projects"]:
                    status = project["status"]
                    if status not in self.projects_by_status:
                        self.projects_by_status[status] = []
                    self.projects_by_status[status].append(project)
                    
                    camera_view = project["camera_view"]
                    if camera_view not in self.projects_by_camera_view:
                        self.projects_by_camera_view[camera_view] = []
                    self.projects_by_camera_view[camera_view].append(project)
                
                # Video indexes
                self.video_by_id = {v["id"]: v for v in self.data["videos"]}
                self.videos_by_status = {}
                self.videos_by_ground_truth = {"True": [], "False": []}
                
                for video in self.data["videos"]:
                    status = video["status"]
                    if status not in self.videos_by_status:
                        self.videos_by_status[status] = []
                    self.videos_by_status[status].append(video)
                    
                    gt_key = str(video["ground_truth_generated"])
                    self.videos_by_ground_truth[gt_key].append(video)
                
                # Link indexes (many-to-many optimization)
                self.links_by_project = {}
                self.links_by_video = {}
                self.links_by_confidence = {"high": [], "medium": [], "low": []}
                
                for link in self.data["links"]:
                    # Project-based index
                    project_id = link["project_id"]
                    if project_id not in self.links_by_project:
                        self.links_by_project[project_id] = []
                    self.links_by_project[project_id].append(link)
                    
                    # Video-based index
                    video_id = link["video_id"]
                    if video_id not in self.links_by_video:
                        self.links_by_video[video_id] = []
                    self.links_by_video[video_id].append(link)
                    
                    # Confidence-based index
                    confidence = link["confidence_score"]
                    if confidence >= 0.8:
                        self.links_by_confidence["high"].append(link)
                    elif confidence >= 0.6:
                        self.links_by_confidence["medium"].append(link)
                    else:
                        self.links_by_confidence["low"].append(link)
            
            def get_project_videos(self, project_id):
                """Optimized query: Get all videos for a project"""
                links = self.links_by_project.get(project_id, [])
                video_ids = [link["video_id"] for link in links]
                return [self.video_by_id[vid] for vid in video_ids if vid in self.video_by_id]
            
            def get_video_projects(self, video_id):
                """Optimized query: Get all projects for a video"""
                links = self.links_by_video.get(video_id, [])
                project_ids = [link["project_id"] for link in links]
                return [self.project_by_id[pid] for pid in project_ids if pid in self.project_by_id]
            
            def get_projects_by_filter(self, status=None, camera_view=None, limit=None):
                """Optimized query: Get projects with filters"""
                if status and camera_view:
                    # Intersection of both filters
                    status_projects = set(p["id"] for p in self.projects_by_status.get(status, []))
                    camera_projects = set(p["id"] for p in self.projects_by_camera_view.get(camera_view, []))
                    matching_ids = status_projects & camera_projects
                    results = [self.project_by_id[pid] for pid in matching_ids]
                elif status:
                    results = self.projects_by_status.get(status, [])
                elif camera_view:
                    results = self.projects_by_camera_view.get(camera_view, [])
                else:
                    results = self.data["projects"]
                
                return results[:limit] if limit else results
            
            def get_high_confidence_assignments(self, min_confidence=0.8):
                """Optimized query: Get high-confidence assignments"""
                return [link for link in self.links_by_confidence["high"] 
                       if link["confidence_score"] >= min_confidence]
            
            def get_project_statistics(self, project_id):
                """Complex aggregation query for project statistics"""
                project_videos = self.get_project_videos(project_id)
                
                if not project_videos:
                    return {"video_count": 0}
                
                total_duration = sum(video["duration"] for video in project_videos)
                total_size = sum(video["file_size"] for video in project_videos)
                gt_generated = sum(1 for video in project_videos if video["ground_truth_generated"])
                
                return {
                    "video_count": len(project_videos),
                    "total_duration_seconds": total_duration,
                    "total_size_bytes": total_size,
                    "ground_truth_coverage": gt_generated / len(project_videos) if project_videos else 0,
                    "avg_video_duration": total_duration / len(project_videos),
                    "avg_file_size": total_size / len(project_videos)
                }
        
        return MockIndexedDatabase(performance_test_data)
    
    @pytest.mark.asyncio
    async def test_many_to_many_query_performance(self, mock_database_with_indexes, performance_test_data):
        """Test query performance with many-to-many relationships"""
        db = mock_database_with_indexes
        
        # Performance test scenarios
        test_scenarios = [
            {
                "name": "get_project_videos",
                "description": "Retrieve all videos for a project",
                "iterations": 100,
                "max_time_ms": 10
            },
            {
                "name": "get_video_projects", 
                "description": "Retrieve all projects for a video",
                "iterations": 100,
                "max_time_ms": 10
            },
            {
                "name": "filtered_project_search",
                "description": "Search projects with multiple filters",
                "iterations": 50,
                "max_time_ms": 20
            },
            {
                "name": "high_confidence_assignments",
                "description": "Find high-confidence video assignments",
                "iterations": 20,
                "max_time_ms": 15
            },
            {
                "name": "project_statistics",
                "description": "Calculate complex project statistics",
                "iterations": 30,
                "max_time_ms": 50
            }
        ]
        
        benchmark_results = {}
        
        for scenario in test_scenarios:
            scenario_name = scenario["name"]
            times = []
            
            for i in range(scenario["iterations"]):
                start_time = time.perf_counter()
                
                if scenario_name == "get_project_videos":
                    project_id = random.choice(performance_test_data["projects"])["id"]
                    result = db.get_project_videos(project_id)
                    
                elif scenario_name == "get_video_projects":
                    video_id = random.choice(performance_test_data["videos"])["id"]
                    result = db.get_video_projects(video_id)
                    
                elif scenario_name == "filtered_project_search":
                    status = random.choice(["Active", "Completed", "Draft"])
                    camera_view = random.choice(["Front-facing VRU", "Rear-facing VRU"])
                    result = db.get_projects_by_filter(status=status, camera_view=camera_view, limit=20)
                    
                elif scenario_name == "high_confidence_assignments":
                    result = db.get_high_confidence_assignments(min_confidence=0.9)
                    
                elif scenario_name == "project_statistics":
                    project_id = random.choice(performance_test_data["projects"])["id"]
                    result = db.get_project_statistics(project_id)
                
                end_time = time.perf_counter()
                execution_time_ms = (end_time - start_time) * 1000
                times.append(execution_time_ms)
            
            # Calculate statistics
            avg_time = statistics.mean(times)
            median_time = statistics.median(times)
            max_time = max(times)
            min_time = min(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0
            
            benchmark_results[scenario_name] = {
                "avg_time_ms": avg_time,
                "median_time_ms": median_time,
                "max_time_ms": max_time,
                "min_time_ms": min_time,
                "std_dev_ms": std_dev,
                "iterations": scenario["iterations"],
                "passes_threshold": avg_time <= scenario["max_time_ms"]
            }
            
            # Assert performance requirements
            assert avg_time <= scenario["max_time_ms"], \
                f"{scenario_name} average time {avg_time:.2f}ms exceeds threshold {scenario['max_time_ms']}ms"
        
        # Overall performance summary
        total_avg_time = sum(result["avg_time_ms"] for result in benchmark_results.values())
        assert total_avg_time <= 100, f"Total query time {total_avg_time:.2f}ms exceeds 100ms threshold"
    
    @pytest.mark.asyncio
    async def test_concurrent_query_performance(self, mock_database_with_indexes, performance_test_data):
        """Test query performance under concurrent load"""
        db = mock_database_with_indexes
        
        async def concurrent_query_worker(worker_id, query_count):
            """Worker function for concurrent query testing"""
            results = []
            start_time = time.perf_counter()
            
            for i in range(query_count):
                query_type = random.choice([
                    "get_project_videos",
                    "get_video_projects", 
                    "filtered_search",
                    "statistics"
                ])
                
                query_start = time.perf_counter()
                
                if query_type == "get_project_videos":
                    project_id = random.choice(performance_test_data["projects"])["id"]
                    result = db.get_project_videos(project_id)
                    
                elif query_type == "get_video_projects":
                    video_id = random.choice(performance_test_data["videos"])["id"]
                    result = db.get_video_projects(video_id)
                    
                elif query_type == "filtered_search":
                    status = random.choice(["Active", "Completed"])
                    result = db.get_projects_by_filter(status=status, limit=10)
                    
                elif query_type == "statistics":
                    project_id = random.choice(performance_test_data["projects"])["id"]
                    result = db.get_project_statistics(project_id)
                
                query_time = (time.perf_counter() - query_start) * 1000
                results.append({
                    "worker_id": worker_id,
                    "query_type": query_type,
                    "time_ms": query_time
                })
            
            total_time = (time.perf_counter() - start_time) * 1000
            return {
                "worker_id": worker_id,
                "total_time_ms": total_time,
                "queries_completed": query_count,
                "avg_query_time_ms": total_time / query_count,
                "query_details": results
            }
        
        # Test concurrent load
        concurrent_workers = 10
        queries_per_worker = 50
        
        tasks = [
            concurrent_query_worker(worker_id, queries_per_worker)
            for worker_id in range(concurrent_workers)
        ]
        
        start_time = time.perf_counter()
        worker_results = await asyncio.gather(*tasks)
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Analyze concurrent performance
        total_queries = concurrent_workers * queries_per_worker
        avg_worker_time = statistics.mean([result["avg_query_time_ms"] for result in worker_results])
        max_worker_time = max([result["avg_query_time_ms"] for result in worker_results])
        
        throughput_qps = total_queries / (total_time / 1000)  # Queries per second
        
        # Performance assertions
        assert avg_worker_time <= 20, f"Average query time {avg_worker_time:.2f}ms under concurrent load exceeds 20ms"
        assert throughput_qps >= 100, f"Throughput {throughput_qps:.1f} QPS is below minimum 100 QPS"
        assert max_worker_time <= 50, f"Maximum worker time {max_worker_time:.2f}ms exceeds 50ms threshold"
    
    @pytest.mark.asyncio 
    async def test_image_loading_performance(self):
        """Test image loading performance for failure snapshots"""
        
        class MockImageLoadingService:
            def __init__(self):
                self.cache = {}
                self.cache_hits = 0
                self.cache_misses = 0
            
            async def load_image(self, image_path, use_cache=True):
                """Mock image loading with caching"""
                start_time = time.perf_counter()
                
                # Check cache
                if use_cache and image_path in self.cache:
                    self.cache_hits += 1
                    await asyncio.sleep(0.001)  # Cache hit - very fast
                    load_time = (time.perf_counter() - start_time) * 1000
                    return {
                        "path": image_path,
                        "load_time_ms": load_time,
                        "cache_hit": True,
                        "size_bytes": self.cache[image_path]["size"]
                    }
                
                # Cache miss - simulate network/disk load
                self.cache_misses += 1
                
                # Simulate image loading time based on size
                image_size = random.randint(50000, 2000000)  # 50KB to 2MB
                load_delay = (image_size / 1000000) * 0.1  # 0.1s per MB
                await asyncio.sleep(load_delay)
                
                # Store in cache
                if use_cache:
                    self.cache[image_path] = {
                        "size": image_size,
                        "loaded_at": time.time()
                    }
                
                load_time = (time.perf_counter() - start_time) * 1000
                return {
                    "path": image_path,
                    "load_time_ms": load_time,
                    "cache_hit": False,
                    "size_bytes": image_size
                }
            
            async def load_image_batch(self, image_paths, use_cache=True):
                """Load multiple images concurrently"""
                tasks = [self.load_image(path, use_cache) for path in image_paths]
                return await asyncio.gather(*tasks)
            
            def get_cache_stats(self):
                """Get cache performance statistics"""
                total_requests = self.cache_hits + self.cache_misses
                cache_hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
                
                return {
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses,
                    "hit_rate": cache_hit_rate,
                    "cached_images": len(self.cache)
                }
        
        image_service = MockImageLoadingService()
        
        # Generate test image paths
        test_images = [
            f"/uploads/screenshots/detection_{i:04d}_full.png" for i in range(100)
        ] + [
            f"/uploads/screenshots/detection_{i:04d}_zoom.png" for i in range(100)
        ]
        
        # Test 1: Sequential loading (cold cache)
        sequential_start = time.perf_counter()
        sequential_results = []
        for image_path in test_images[:20]:  # Test subset for reasonable test time
            result = await image_service.load_image(image_path, use_cache=True)
            sequential_results.append(result)
        sequential_time = (time.perf_counter() - sequential_start) * 1000
        
        # Test 2: Concurrent batch loading (cold cache)
        batch_test_images = test_images[20:40]  # Different subset
        batch_start = time.perf_counter()
        batch_results = await image_service.load_image_batch(batch_test_images, use_cache=True)
        batch_time = (time.perf_counter() - batch_start) * 1000
        
        # Test 3: Cache performance (warm cache)
        cached_test_images = test_images[:20]  # Same as sequential test
        cache_start = time.perf_counter()
        cache_results = await image_service.load_image_batch(cached_test_images, use_cache=True)
        cache_time = (time.perf_counter() - cache_start) * 1000
        
        # Performance analysis
        avg_sequential_time = statistics.mean([r["load_time_ms"] for r in sequential_results])
        avg_batch_time = statistics.mean([r["load_time_ms"] for r in batch_results])
        avg_cache_time = statistics.mean([r["load_time_ms"] for r in cache_results])
        
        cache_stats = image_service.get_cache_stats()
        
        # Performance assertions
        assert avg_cache_time < avg_sequential_time * 0.1, \
            f"Cache hits {avg_cache_time:.2f}ms should be much faster than cold load {avg_sequential_time:.2f}ms"
        
        assert batch_time < sequential_time * 0.8, \
            f"Batch loading {batch_time:.2f}ms should be faster than sequential {sequential_time:.2f}ms"
        
        assert cache_stats["hit_rate"] > 0.5, \
            f"Cache hit rate {cache_stats['hit_rate']:.2f} should be above 50%"
        
        # Verify concurrent loading is actually concurrent
        expected_concurrent_time = max([r["load_time_ms"] for r in batch_results])
        assert batch_time <= expected_concurrent_time * 1.2, \
            f"Batch time {batch_time:.2f}ms suggests non-concurrent loading"
    
    @pytest.mark.asyncio
    async def test_large_dataset_scalability(self, performance_test_data):
        """Test system performance with large datasets"""
        
        class MockScalabilityTestService:
            def __init__(self, test_data):
                self.data = test_data
                self.memory_usage = []
                self.query_times = []
            
            def measure_memory_usage(self):
                """Measure current memory usage"""
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                self.memory_usage.append({
                    "timestamp": time.time(),
                    "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                    "vms_mb": memory_info.vms / 1024 / 1024   # Virtual Memory Size
                })
            
            async def simulate_large_dataset_queries(self, dataset_multiplier=1):
                """Simulate queries on scaled dataset"""
                # Scale up the dataset
                scaled_projects = self.data["projects"] * dataset_multiplier
                scaled_videos = self.data["videos"] * dataset_multiplier
                scaled_links = self.data["links"] * dataset_multiplier
                
                self.measure_memory_usage()
                
                # Simulate various query patterns
                query_patterns = [
                    ("project_search", self._search_projects),
                    ("video_lookup", self._lookup_videos),
                    ("relationship_traversal", self._traverse_relationships),
                    ("aggregation", self._aggregate_statistics)
                ]
                
                for pattern_name, query_func in query_patterns:
                    start_time = time.perf_counter()
                    
                    # Execute query pattern multiple times
                    for _ in range(10):
                        await query_func(scaled_projects, scaled_videos, scaled_links)
                    
                    execution_time = (time.perf_counter() - start_time) * 1000
                    
                    self.query_times.append({
                        "pattern": pattern_name,
                        "dataset_size": len(scaled_projects),
                        "execution_time_ms": execution_time,
                        "avg_time_per_query_ms": execution_time / 10
                    })
                    
                    self.measure_memory_usage()
            
            async def _search_projects(self, projects, videos, links):
                """Simulate project search queries"""
                await asyncio.sleep(0.01)  # Simulate query time
                
                # Filter projects by various criteria
                active_projects = [p for p in projects if p["status"] == "Active"]
                front_facing = [p for p in active_projects if "Front-facing" in p["camera_view"]]
                return len(front_facing)
            
            async def _lookup_videos(self, projects, videos, links):
                """Simulate video lookup queries"""
                await asyncio.sleep(0.005)  # Simulate query time
                
                # Find videos with ground truth
                gt_videos = [v for v in videos if v["ground_truth_generated"]]
                large_files = [v for v in gt_videos if v["file_size"] > 100000000]  # > 100MB
                return len(large_files)
            
            async def _traverse_relationships(self, projects, videos, links):
                """Simulate many-to-many relationship traversals"""
                await asyncio.sleep(0.02)  # Simulate query time
                
                # Find projects with many videos
                project_video_counts = {}
                for link in links:
                    project_id = link["project_id"]
                    project_video_counts[project_id] = project_video_counts.get(project_id, 0) + 1
                
                large_projects = [pid for pid, count in project_video_counts.items() if count > 10]
                return len(large_projects)
            
            async def _aggregate_statistics(self, projects, videos, links):
                """Simulate complex aggregation queries"""
                await asyncio.sleep(0.03)  # Simulate query time
                
                # Calculate various statistics
                total_duration = sum(v["duration"] for v in videos)
                total_size = sum(v["file_size"] for v in videos)
                avg_confidence = sum(l["confidence_score"] for l in links) / len(links) if links else 0
                
                return {
                    "total_duration": total_duration,
                    "total_size": total_size,
                    "avg_confidence": avg_confidence
                }
            
            def get_scalability_metrics(self):
                """Get scalability analysis"""
                if not self.memory_usage or not self.query_times:
                    return {}
                
                # Memory analysis
                initial_memory = self.memory_usage[0]["rss_mb"]
                peak_memory = max(usage["rss_mb"] for usage in self.memory_usage)
                memory_growth = peak_memory - initial_memory
                
                # Query time analysis
                query_time_by_pattern = {}
                for query in self.query_times:
                    pattern = query["pattern"]
                    if pattern not in query_time_by_pattern:
                        query_time_by_pattern[pattern] = []
                    query_time_by_pattern[pattern].append(query["avg_time_per_query_ms"])
                
                return {
                    "memory_metrics": {
                        "initial_mb": initial_memory,
                        "peak_mb": peak_memory,
                        "growth_mb": memory_growth,
                        "growth_percentage": (memory_growth / initial_memory) * 100 if initial_memory > 0 else 0
                    },
                    "query_metrics": {
                        pattern: {
                            "avg_time_ms": statistics.mean(times),
                            "max_time_ms": max(times),
                            "min_time_ms": min(times)
                        }
                        for pattern, times in query_time_by_pattern.items()
                    }
                }
        
        # Test with increasing dataset sizes
        scalability_service = MockScalabilityTestService(performance_test_data)
        
        dataset_sizes = [1, 2, 5]  # 1x, 2x, 5x dataset size
        scalability_results = {}
        
        for multiplier in dataset_sizes:
            await scalability_service.simulate_large_dataset_queries(multiplier)
            
            metrics = scalability_service.get_scalability_metrics()
            scalability_results[f"{multiplier}x_dataset"] = metrics
            
            # Clear for next iteration
            scalability_service.memory_usage.clear()
            scalability_service.query_times.clear()
        
        # Analyze scalability trends
        for size_key, metrics in scalability_results.items():
            memory_metrics = metrics.get("memory_metrics", {})
            query_metrics = metrics.get("query_metrics", {})
            
            # Memory scalability assertions
            if "memory_metrics" in metrics:
                growth_percentage = memory_metrics.get("growth_percentage", 0)
                assert growth_percentage < 200, \
                    f"Memory growth {growth_percentage:.1f}% for {size_key} exceeds 200% threshold"
            
            # Query performance assertions
            for pattern, pattern_metrics in query_metrics.items():
                avg_time = pattern_metrics.get("avg_time_ms", 0)
                max_time = pattern_metrics.get("max_time_ms", 0)
                
                # Scale-dependent thresholds
                multiplier = int(size_key.split('x')[0])
                expected_max_time = 50 * multiplier  # Linear scaling expectation
                
                assert avg_time <= expected_max_time, \
                    f"Average query time {avg_time:.2f}ms for {pattern} in {size_key} exceeds {expected_max_time}ms"
    
    def test_index_effectiveness_analysis(self, mock_database_with_indexes, performance_test_data):
        """Test index effectiveness for common queries"""
        db = mock_database_with_indexes
        
        # Test index usage patterns
        index_tests = [
            {
                "name": "project_id_lookup",
                "description": "Single project lookup by ID",
                "query": lambda: db.project_by_id.get(random.choice(performance_test_data["projects"])["id"]),
                "expected_complexity": "O(1)"  # Hash table lookup
            },
            {
                "name": "video_id_lookup", 
                "description": "Single video lookup by ID",
                "query": lambda: db.video_by_id.get(random.choice(performance_test_data["videos"])["id"]),
                "expected_complexity": "O(1)"  # Hash table lookup
            },
            {
                "name": "project_videos_by_index",
                "description": "Get project videos using link index",
                "query": lambda: db.get_project_videos(random.choice(performance_test_data["projects"])["id"]),
                "expected_complexity": "O(k)"  # k = number of links for project
            },
            {
                "name": "filtered_projects_by_status",
                "description": "Get projects filtered by status",
                "query": lambda: db.get_projects_by_filter(status="Active"),
                "expected_complexity": "O(n)"  # n = number of active projects
            },
            {
                "name": "high_confidence_links",
                "description": "Get high-confidence assignments",
                "query": lambda: db.get_high_confidence_assignments(0.9),
                "expected_complexity": "O(m)"  # m = number of high-confidence links
            }
        ]
        
        index_performance = {}
        
        for test in index_tests:
            times = []
            
            # Run each test multiple times
            for _ in range(100):
                start_time = time.perf_counter()
                result = test["query"]()
                end_time = time.perf_counter()
                
                execution_time = (end_time - start_time) * 1000000  # microseconds for precision
                times.append(execution_time)
            
            # Calculate statistics
            avg_time = statistics.mean(times)
            median_time = statistics.median(times)
            p95_time = sorted(times)[int(0.95 * len(times))]
            
            index_performance[test["name"]] = {
                "description": test["description"],
                "avg_time_us": avg_time,
                "median_time_us": median_time,
                "p95_time_us": p95_time,
                "expected_complexity": test["expected_complexity"],
                "samples": len(times)
            }
        
        # Verify index effectiveness
        # ID lookups should be extremely fast (< 10 microseconds)
        assert index_performance["project_id_lookup"]["avg_time_us"] < 10, \
            "Project ID lookup should be sub-10 microsecond with proper indexing"
        
        assert index_performance["video_id_lookup"]["avg_time_us"] < 10, \
            "Video ID lookup should be sub-10 microsecond with proper indexing"
        
        # Relationship traversals should be fast (< 100 microseconds)
        assert index_performance["project_videos_by_index"]["avg_time_us"] < 100, \
            "Project-video relationship traversal should be sub-100 microsecond with indexing"
        
        # Filtered queries should be reasonable (< 1000 microseconds)
        assert index_performance["filtered_projects_by_status"]["avg_time_us"] < 1000, \
            "Status-filtered project queries should be sub-millisecond with indexing"
        
        # Confidence-based queries should be fast (< 500 microseconds)
        assert index_performance["high_confidence_links"]["avg_time_us"] < 500, \
            "Confidence-filtered queries should be sub-500 microsecond with indexing"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])