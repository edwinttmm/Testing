# Performance Test Strategy - AI Model Validation Platform

## Overview

Performance testing ensures the AI Model Validation Platform can handle expected load conditions while maintaining acceptable response times and system stability. This strategy covers load testing, stress testing, volume testing, and performance monitoring across all system components.

## Performance Testing Objectives

### Primary Goals
1. **Validate System Capacity** - Ensure system handles expected concurrent user load
2. **Identify Performance Bottlenecks** - Find and address performance constraints
3. **Establish Performance Baselines** - Set benchmarks for regression testing
4. **Verify Scalability** - Test system behavior under increasing load
5. **Ensure Resource Optimization** - Validate efficient use of system resources

### Key Performance Indicators (KPIs)
- **Response Time**: 95th percentile < 200ms for API endpoints
- **Throughput**: Support 100+ concurrent users
- **Video Processing**: < 60 seconds per minute of video content
- **Memory Usage**: < 2GB peak usage during normal operations
- **CPU Utilization**: < 80% under normal load
- **Error Rate**: < 0.1% of requests under normal load

## Performance Test Types

### 1. Load Testing

#### API Endpoint Load Testing
```python
# tests/performance/api_load_tests.py

import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any
import requests
import pytest

@dataclass
class LoadTestResult:
    """Results from load testing."""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    percentile_95_response_time: float
    percentile_99_response_time: float
    max_response_time: float
    min_response_time: float
    requests_per_second: float
    error_rate: float

class APILoadTester:
    """Load tester for API endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None
    
    def authenticate(self, email: str = "test@example.com", password: str = "password"):
        """Authenticate and store token."""
        response = self.session.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            self.auth_token = response.json()["access_token"]
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a single request and measure performance."""
        start_time = time.perf_counter()
        
        try:
            response = self.session.request(
                method, 
                f"{self.base_url}{endpoint}",
                timeout=30,
                **kwargs
            )
            end_time = time.perf_counter()
            
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "content_length": len(response.content),
                "error": None
            }
        except Exception as e:
            end_time = time.perf_counter()
            return {
                "success": False,
                "status_code": 0,
                "response_time": end_time - start_time,
                "content_length": 0,
                "error": str(e)
            }
    
    def run_load_test(
        self, 
        method: str, 
        endpoint: str, 
        concurrent_users: int = 10,
        requests_per_user: int = 10,
        **request_kwargs
    ) -> LoadTestResult:
        """Run load test against specific endpoint."""
        
        total_requests = concurrent_users * requests_per_user
        results = []
        
        def user_simulation(user_id: int):
            """Simulate a single user's requests."""
            user_results = []
            for _ in range(requests_per_user):
                result = self.make_request(method, endpoint, **request_kwargs)
                user_results.append(result)
                # Small delay between requests
                time.sleep(0.1)
            return user_results
        
        # Execute load test
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [
                executor.submit(user_simulation, user_id)
                for user_id in range(concurrent_users)
            ]
            
            for future in as_completed(futures):
                results.extend(future.result())
        
        end_time = time.perf_counter()
        total_duration = end_time - start_time
        
        # Calculate metrics
        successful_requests = sum(1 for r in results if r["success"])
        failed_requests = total_requests - successful_requests
        response_times = [r["response_time"] for r in results if r["success"]]
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
            max_response_time = max(response_times)
            min_response_time = min(response_times)
        else:
            avg_response_time = p95_response_time = p99_response_time = 0
            max_response_time = min_response_time = 0
        
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return LoadTestResult(
            endpoint=endpoint,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=avg_response_time,
            percentile_95_response_time=p95_response_time,
            percentile_99_response_time=p99_response_time,
            max_response_time=max_response_time,
            min_response_time=min_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate
        )

@pytest.mark.performance
class TestAPILoadPerformance:
    """API load performance tests."""
    
    def setup_method(self):
        """Setup load tester."""
        self.load_tester = APILoadTester()
        self.load_tester.authenticate()
    
    def test_projects_list_load_performance(self):
        """Test projects list endpoint under load."""
        result = self.load_tester.run_load_test(
            method="GET",
            endpoint="/api/projects",
            concurrent_users=50,
            requests_per_user=20
        )
        
        # Performance assertions
        assert result.error_rate < 0.01, f"Error rate too high: {result.error_rate * 100:.2f}%"
        assert result.percentile_95_response_time < 0.2, f"95th percentile response time too slow: {result.percentile_95_response_time:.3f}s"
        assert result.requests_per_second > 100, f"Throughput too low: {result.requests_per_second:.2f} RPS"
        
        # Log performance metrics
        print(f"Projects List Load Test Results:")
        print(f"  Total Requests: {result.total_requests}")
        print(f"  Success Rate: {(result.successful_requests/result.total_requests)*100:.2f}%")
        print(f"  Average Response Time: {result.average_response_time:.3f}s")
        print(f"  95th Percentile: {result.percentile_95_response_time:.3f}s")
        print(f"  Throughput: {result.requests_per_second:.2f} RPS")
    
    def test_project_creation_load_performance(self):
        """Test project creation under load."""
        project_data = {
            "name": "Load Test Project",
            "camera_model": "FLIR Blackfly S",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        result = self.load_tester.run_load_test(
            method="POST",
            endpoint="/api/projects",
            concurrent_users=20,
            requests_per_user=5,
            json=project_data
        )
        
        # Performance assertions for write operations (more lenient)
        assert result.error_rate < 0.05, f"Error rate too high: {result.error_rate * 100:.2f}%"
        assert result.percentile_95_response_time < 0.5, f"95th percentile response time too slow: {result.percentile_95_response_time:.3f}s"
        
        print(f"Project Creation Load Test Results:")
        print(f"  Total Requests: {result.total_requests}")
        print(f"  Success Rate: {(result.successful_requests/result.total_requests)*100:.2f}%")
        print(f"  Average Response Time: {result.average_response_time:.3f}s")
        print(f"  95th Percentile: {result.percentile_95_response_time:.3f}s")
```

#### Video Processing Load Testing
```python
# tests/performance/video_processing_load.py

import asyncio
import time
import psutil
import threading
from pathlib import Path
from typing import List, Dict
import numpy as np
import cv2

class VideoProcessingLoadTester:
    """Load tester for video processing operations."""
    
    def __init__(self):
        self.results = []
        self.system_metrics = []
        self.monitoring_active = False
    
    def create_test_video(self, output_path: Path, duration: int = 60, fps: int = 30):
        """Create test video file for processing."""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        height, width = 720, 1280
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        
        total_frames = duration * fps
        for frame_idx in range(total_frames):
            # Create realistic frame with moving objects
            frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            
            # Add moving objects to simulate real-world complexity
            num_objects = np.random.randint(1, 5)
            for _ in range(num_objects):
                x = np.random.randint(0, width - 100)
                y = np.random.randint(0, height - 100)
                w = np.random.randint(50, 100)
                h = np.random.randint(50, 100)
                color = tuple(np.random.randint(0, 255, 3).tolist())
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)
            
            out.write(frame)
        
        out.release()
    
    def monitor_system_resources(self, interval: float = 1.0):
        """Monitor system resources during load test."""
        while self.monitoring_active:
            metrics = {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_used_gb': psutil.virtual_memory().used / (1024**3),
                'disk_io_read': psutil.disk_io_counters().read_bytes,
                'disk_io_write': psutil.disk_io_counters().write_bytes,
                'network_sent': psutil.net_io_counters().bytes_sent,
                'network_recv': psutil.net_io_counters().bytes_recv
            }
            self.system_metrics.append(metrics)
            time.sleep(interval)
    
    async def process_video_simulation(self, video_path: Path, session_id: str):
        """Simulate video processing with performance tracking."""
        start_time = time.perf_counter()
        
        try:
            # Simulate video analysis (replace with actual processing)
            cap = cv2.VideoCapture(str(video_path))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            
            processed_frames = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Simulate processing work (object detection, etc.)
                await asyncio.sleep(0.001)  # Simulate processing time per frame
                processed_frames += 1
                
                # Simulate progress updates
                if processed_frames % 100 == 0:
                    progress = (processed_frames / frame_count) * 100
                    print(f"Session {session_id}: {progress:.1f}% complete")
            
            cap.release()
            
            end_time = time.perf_counter()
            processing_time = end_time - start_time
            
            return {
                'session_id': session_id,
                'success': True,
                'duration': duration,
                'processing_time': processing_time,
                'processed_frames': processed_frames,
                'fps_processed': processed_frames / processing_time,
                'realtime_factor': duration / processing_time,
                'error': None
            }
            
        except Exception as e:
            end_time = time.perf_counter()
            processing_time = end_time - start_time
            
            return {
                'session_id': session_id,
                'success': False,
                'duration': 0,
                'processing_time': processing_time,
                'processed_frames': 0,
                'fps_processed': 0,
                'realtime_factor': 0,
                'error': str(e)
            }
    
    async def run_concurrent_video_processing_test(
        self,
        video_paths: List[Path],
        concurrent_sessions: int = 5
    ):
        """Run concurrent video processing load test."""
        
        # Start system monitoring
        self.monitoring_active = True
        monitor_thread = threading.Thread(target=self.monitor_system_resources)
        monitor_thread.start()
        
        # Create processing tasks
        tasks = []
        for i in range(concurrent_sessions):
            video_path = video_paths[i % len(video_paths)]
            session_id = f"session_{i:03d}"
            task = self.process_video_simulation(video_path, session_id)
            tasks.append(task)
        
        # Execute concurrent processing
        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.perf_counter()
        
        # Stop monitoring
        self.monitoring_active = False
        monitor_thread.join()
        
        total_time = end_time - start_time
        
        # Analyze results
        successful_sessions = [r for r in results if isinstance(r, dict) and r['success']]
        failed_sessions = [r for r in results if isinstance(r, dict) and not r['success']]
        
        analysis = {
            'total_sessions': concurrent_sessions,
            'successful_sessions': len(successful_sessions),
            'failed_sessions': len(failed_sessions),
            'total_test_time': total_time,
            'success_rate': len(successful_sessions) / concurrent_sessions,
            'average_processing_time': np.mean([r['processing_time'] for r in successful_sessions]) if successful_sessions else 0,
            'average_realtime_factor': np.mean([r['realtime_factor'] for r in successful_sessions]) if successful_sessions else 0,
            'system_metrics': self.analyze_system_metrics()
        }
        
        return analysis
    
    def analyze_system_metrics(self) -> Dict:
        """Analyze collected system metrics."""
        if not self.system_metrics:
            return {}
        
        cpu_values = [m['cpu_percent'] for m in self.system_metrics]
        memory_values = [m['memory_percent'] for m in self.system_metrics]
        memory_gb_values = [m['memory_used_gb'] for m in self.system_metrics]
        
        return {
            'cpu_usage': {
                'max': max(cpu_values),
                'average': np.mean(cpu_values),
                'p95': np.percentile(cpu_values, 95)
            },
            'memory_usage': {
                'max_percent': max(memory_values),
                'average_percent': np.mean(memory_values),
                'max_gb': max(memory_gb_values),
                'average_gb': np.mean(memory_gb_values)
            }
        }

@pytest.mark.performance
@pytest.mark.slow
class TestVideoProcessingPerformance:
    """Video processing performance tests."""
    
    def setup_method(self):
        """Setup test videos and load tester."""
        self.test_dir = Path("tests/fixtures/performance_videos")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.load_tester = VideoProcessingLoadTester()
        
        # Create test videos of different sizes
        self.video_paths = []
        for i, (duration, name) in enumerate([(30, "short"), (60, "medium"), (120, "long")]):
            video_path = self.test_dir / f"test_video_{name}.mp4"
            if not video_path.exists():
                self.load_tester.create_test_video(video_path, duration=duration)
            self.video_paths.append(video_path)
    
    @pytest.mark.asyncio
    async def test_concurrent_video_processing_performance(self):
        """Test concurrent video processing performance."""
        
        # Test with different concurrency levels
        for concurrent_sessions in [1, 3, 5, 8]:
            print(f"\nTesting {concurrent_sessions} concurrent sessions...")
            
            analysis = await self.load_tester.run_concurrent_video_processing_test(
                video_paths=self.video_paths,
                concurrent_sessions=concurrent_sessions
            )
            
            # Performance assertions
            assert analysis['success_rate'] >= 0.8, f"Success rate too low: {analysis['success_rate'] * 100:.1f}%"
            assert analysis['system_metrics']['cpu_usage']['max'] < 95, f"CPU usage too high: {analysis['system_metrics']['cpu_usage']['max']:.1f}%"
            assert analysis['system_metrics']['memory_usage']['max_gb'] < 4.0, f"Memory usage too high: {analysis['system_metrics']['memory_usage']['max_gb']:.1f}GB"
            
            # Log performance metrics
            print(f"Concurrent Sessions: {concurrent_sessions}")
            print(f"  Success Rate: {analysis['success_rate'] * 100:.1f}%")
            print(f"  Average Processing Time: {analysis['average_processing_time']:.2f}s")
            print(f"  Average Realtime Factor: {analysis['average_realtime_factor']:.2f}x")
            print(f"  Peak CPU Usage: {analysis['system_metrics']['cpu_usage']['max']:.1f}%")
            print(f"  Peak Memory Usage: {analysis['system_metrics']['memory_usage']['max_gb']:.2f}GB")
```

### 2. Stress Testing

#### System Stress Testing
```python
# tests/performance/stress_tests.py

import asyncio
import time
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import psutil
import pytest

class StressTester:
    """Comprehensive system stress testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.system_metrics = []
        self.monitoring_active = False
    
    def monitor_system_health(self, interval: float = 0.5):
        """Monitor system health during stress test."""
        while self.monitoring_active:
            try:
                metrics = {
                    'timestamp': time.time(),
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'memory_available_gb': psutil.virtual_memory().available / (1024**3),
                    'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
                    'connections': len(psutil.net_connections()),
                    'processes': len(psutil.pids())
                }
                self.system_metrics.append(metrics)
            except Exception as e:
                print(f"Error collecting metrics: {e}")
            
            time.sleep(interval)
    
    def stress_api_endpoints(self, duration_seconds: int = 300, max_concurrent: int = 200):
        """Stress test API endpoints with gradually increasing load."""
        
        endpoints = [
            {"method": "GET", "path": "/api/projects", "weight": 0.4},
            {"method": "GET", "path": "/api/test-sessions", "weight": 0.3},
            {"method": "POST", "path": "/api/projects", "weight": 0.2, 
             "data": {"name": "Stress Test", "camera_model": "Test", "camera_view": "Front-facing VRU", "signal_type": "GPIO"}},
            {"method": "GET", "path": "/health", "weight": 0.1}
        ]
        
        # Start monitoring
        self.monitoring_active = True
        monitor_thread = threading.Thread(target=self.monitor_system_health)
        monitor_thread.start()
        
        def make_weighted_request():
            """Make a weighted random request."""
            import random
            weights = [ep["weight"] for ep in endpoints]
            endpoint = random.choices(endpoints, weights=weights)[0]
            
            try:
                start_time = time.perf_counter()
                
                if endpoint["method"] == "GET":
                    response = requests.get(f"{self.base_url}{endpoint['path']}", timeout=10)
                elif endpoint["method"] == "POST":
                    response = requests.post(
                        f"{self.base_url}{endpoint['path']}", 
                        json=endpoint.get("data"), 
                        timeout=10
                    )
                
                end_time = time.perf_counter()
                
                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "endpoint": endpoint["path"]
                }
            except Exception as e:
                end_time = time.perf_counter()
                return {
                    "success": False,
                    "status_code": 0,
                    "response_time": end_time - start_time,
                    "endpoint": endpoint["path"],
                    "error": str(e)
                }
        
        # Gradually increase load
        start_time = time.time()
        results = []
        
        while (time.time() - start_time) < duration_seconds:
            elapsed_ratio = (time.time() - start_time) / duration_seconds
            current_concurrent = min(int(max_concurrent * elapsed_ratio * 2), max_concurrent)
            
            if current_concurrent < 1:
                current_concurrent = 1
            
            # Execute requests for this interval
            with ThreadPoolExecutor(max_workers=current_concurrent) as executor:
                interval_start = time.time()
                futures = []
                
                # Submit requests for 10 second intervals
                while (time.time() - interval_start) < 10 and (time.time() - start_time) < duration_seconds:
                    future = executor.submit(make_weighted_request)
                    futures.append(future)
                    time.sleep(0.1 / current_concurrent)  # Pace requests
                
                # Collect results
                for future in futures:
                    try:
                        result = future.result(timeout=15)
                        results.append(result)
                    except Exception as e:
                        results.append({
                            "success": False,
                            "status_code": 0,
                            "response_time": 15.0,
                            "endpoint": "unknown",
                            "error": str(e)
                        })
            
            print(f"Stress test progress: {elapsed_ratio*100:.1f}%, Current load: {current_concurrent} concurrent")
        
        # Stop monitoring
        self.monitoring_active = False
        monitor_thread.join()
        
        return self.analyze_stress_results(results)
    
    def analyze_stress_results(self, results):
        """Analyze stress test results."""
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r["success"])
        
        if successful_requests > 0:
            successful_results = [r for r in results if r["success"]]
            avg_response_time = sum(r["response_time"] for r in successful_results) / len(successful_results)
            response_times = [r["response_time"] for r in successful_results]
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
        else:
            avg_response_time = 0
            p95_response_time = 0
        
        # System metrics analysis
        if self.system_metrics:
            max_cpu = max(m["cpu_percent"] for m in self.system_metrics)
            max_memory = max(m["memory_percent"] for m in self.system_metrics)
            min_memory_available = min(m["memory_available_gb"] for m in self.system_metrics)
        else:
            max_cpu = max_memory = min_memory_available = 0
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_rate": (total_requests - successful_requests) / total_requests if total_requests > 0 else 1,
            "average_response_time": avg_response_time,
            "p95_response_time": p95_response_time,
            "max_cpu_usage": max_cpu,
            "max_memory_usage": max_memory,
            "min_memory_available_gb": min_memory_available,
            "system_remained_stable": max_cpu < 95 and min_memory_available > 0.5
        }

@pytest.mark.performance
@pytest.mark.stress
class TestSystemStress:
    """System stress tests."""
    
    def test_api_stress_under_high_load(self):
        """Test API stability under high load."""
        stress_tester = StressTester()
        
        # Run 5-minute stress test with up to 150 concurrent users
        results = stress_tester.stress_api_endpoints(
            duration_seconds=300,
            max_concurrent=150
        )
        
        # Stress test assertions (more lenient than load tests)
        assert results["error_rate"] < 0.05, f"Error rate too high under stress: {results['error_rate'] * 100:.2f}%"
        assert results["system_remained_stable"], "System became unstable during stress test"
        assert results["p95_response_time"] < 2.0, f"Response time degraded too much: {results['p95_response_time']:.3f}s"
        
        print(f"Stress Test Results:")
        print(f"  Total Requests: {results['total_requests']}")
        print(f"  Error Rate: {results['error_rate'] * 100:.2f}%")
        print(f"  Average Response Time: {results['average_response_time']:.3f}s")
        print(f"  95th Percentile Response Time: {results['p95_response_time']:.3f}s")
        print(f"  Max CPU Usage: {results['max_cpu_usage']:.1f}%")
        print(f"  Max Memory Usage: {results['max_memory_usage']:.1f}%")
        print(f"  System Stable: {results['system_remained_stable']}")
```

### 3. Volume Testing

#### Database Volume Testing
```python
# tests/performance/volume_tests.py

import time
import random
from typing import List
import pytest
from sqlalchemy.orm import Session
from models import User, Project, Video, TestSession, DetectionEvent
from database import SessionLocal
from utils.factories import UserFactory, ProjectFactory, VideoFactory

class VolumeTestDataGenerator:
    """Generate large volumes of test data."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def generate_users(self, count: int = 1000) -> List[User]:
        """Generate large number of users."""
        print(f"Generating {count} users...")
        
        users = []
        batch_size = 100
        
        for i in range(0, count, batch_size):
            batch = []
            current_batch_size = min(batch_size, count - i)
            
            for j in range(current_batch_size):
                user = UserFactory.build()
                batch.append(user)
            
            # Bulk insert batch
            self.db.bulk_save_objects(batch)
            self.db.commit()
            
            users.extend(batch)
            
            if (i + batch_size) % 500 == 0:
                print(f"  Generated {i + batch_size} users...")
        
        print(f"Generated {len(users)} users total")
        return users
    
    def generate_projects_for_users(self, users: List[User], projects_per_user: int = 5) -> List[Project]:
        """Generate projects for users."""
        total_projects = len(users) * projects_per_user
        print(f"Generating {total_projects} projects...")
        
        projects = []
        batch_size = 100
        
        for i, user in enumerate(users):
            user_projects = []
            
            for j in range(projects_per_user):
                project = ProjectFactory.build(owner_id=user.id)
                user_projects.append(project)
            
            projects.extend(user_projects)
            
            # Insert in batches
            if len(projects) >= batch_size:
                self.db.bulk_save_objects(projects[-batch_size:])
                self.db.commit()
            
            if (i + 1) % 100 == 0:
                print(f"  Generated projects for {i + 1} users...")
        
        # Insert remaining projects
        remaining = len(projects) % batch_size
        if remaining > 0:
            self.db.bulk_save_objects(projects[-remaining:])
            self.db.commit()
        
        print(f"Generated {len(projects)} projects total")
        return projects
    
    def generate_detection_events(self, test_sessions: List[TestSession], events_per_session: int = 100):
        """Generate large volume of detection events."""
        total_events = len(test_sessions) * events_per_session
        print(f"Generating {total_events} detection events...")
        
        batch_size = 1000
        current_batch = []
        
        for i, session in enumerate(test_sessions):
            for j in range(events_per_session):
                event = DetectionEvent(
                    test_session_id=session.id,
                    timestamp=random.uniform(0, 300),  # 0-5 minutes
                    confidence=random.uniform(0.5, 1.0),
                    class_label=random.choice(["pedestrian", "cyclist", "vehicle", "distracted_driver"]),
                    validation_result=random.choice(["TP", "FP", "FN"])
                )
                current_batch.append(event)
                
                if len(current_batch) >= batch_size:
                    self.db.bulk_save_objects(current_batch)
                    self.db.commit()
                    current_batch = []
            
            if (i + 1) % 50 == 0:
                print(f"  Generated events for {i + 1} sessions...")
        
        # Insert remaining events
        if current_batch:
            self.db.bulk_save_objects(current_batch)
            self.db.commit()
        
        print(f"Generated {total_events} detection events total")

@pytest.mark.performance
@pytest.mark.volume
class TestDatabaseVolumePerformance:
    """Database volume performance tests."""
    
    @pytest.fixture(scope="class")
    def large_dataset(self, test_db_session):
        """Create large dataset for volume testing."""
        generator = VolumeTestDataGenerator(test_db_session)
        
        # Generate data volumes
        users = generator.generate_users(count=500)
        projects = generator.generate_projects_for_users(users, projects_per_user=3)
        
        # Create test sessions for projects
        test_sessions = []
        for project in projects[:100]:  # Create sessions for first 100 projects
            session = TestSession(
                name=f"Volume Test Session {len(test_sessions)}",
                project_id=project.id,
                video_id=None,  # Skip video for performance
                tolerance_ms=100,
                status="completed"
            )
            test_sessions.append(session)
        
        test_db_session.bulk_save_objects(test_sessions)
        test_db_session.commit()
        
        # Generate detection events
        generator.generate_detection_events(test_sessions, events_per_session=200)
        
        return {
            "users": users,
            "projects": projects,
            "test_sessions": test_sessions
        }
    
    def test_large_dataset_query_performance(self, large_dataset, test_db_session):
        """Test query performance with large dataset."""
        
        # Test 1: User projects query
        start_time = time.perf_counter()
        user_id = large_dataset["users"][0].id
        projects = test_db_session.query(Project).filter_by(owner_id=user_id).all()
        query_time = time.perf_counter() - start_time
        
        assert query_time < 0.1, f"User projects query too slow: {query_time:.3f}s"
        print(f"User projects query time: {query_time:.3f}s ({len(projects)} projects)")
        
        # Test 2: Project with sessions query
        start_time = time.perf_counter()
        project_with_sessions = (
            test_db_session.query(Project)
            .join(TestSession)
            .filter(Project.id == large_dataset["projects"][0].id)
            .first()
        )
        query_time = time.perf_counter() - start_time
        
        assert query_time < 0.1, f"Project with sessions query too slow: {query_time:.3f}s"
        print(f"Project with sessions query time: {query_time:.3f}s")
        
        # Test 3: Detection events aggregation
        start_time = time.perf_counter()
        session_id = large_dataset["test_sessions"][0].id
        event_counts = (
            test_db_session.query(
                DetectionEvent.validation_result,
                test_db_session.query(DetectionEvent).filter_by(test_session_id=session_id).count()
            )
            .filter_by(test_session_id=session_id)
            .group_by(DetectionEvent.validation_result)
            .all()
        )
        query_time = time.perf_counter() - start_time
        
        assert query_time < 0.5, f"Event aggregation query too slow: {query_time:.3f}s"
        print(f"Event aggregation query time: {query_time:.3f}s")
        
        # Test 4: Pagination performance
        start_time = time.perf_counter()
        paginated_projects = (
            test_db_session.query(Project)
            .offset(100)
            .limit(50)
            .all()
        )
        query_time = time.perf_counter() - start_time
        
        assert query_time < 0.1, f"Pagination query too slow: {query_time:.3f}s"
        print(f"Pagination query time: {query_time:.3f}s ({len(paginated_projects)} projects)")
    
    def test_concurrent_database_operations(self, large_dataset, test_db_session):
        """Test concurrent database operations performance."""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def query_worker(worker_id: int):
            """Worker thread for database queries."""
            session = SessionLocal()
            try:
                start_time = time.perf_counter()
                
                # Perform various queries
                user = session.query(User).offset(worker_id * 10).first()
                projects = session.query(Project).filter_by(owner_id=user.id).all()
                
                if projects:
                    sessions = session.query(TestSession).filter_by(project_id=projects[0].id).all()
                
                end_time = time.perf_counter()
                
                results_queue.put({
                    "worker_id": worker_id,
                    "success": True,
                    "duration": end_time - start_time
                })
            except Exception as e:
                results_queue.put({
                    "worker_id": worker_id,
                    "success": False,
                    "error": str(e),
                    "duration": time.perf_counter() - start_time
                })
            finally:
                session.close()
        
        # Run concurrent queries
        num_workers = 20
        threads = []
        
        start_time = time.perf_counter()
        
        for i in range(num_workers):
            thread = threading.Thread(target=query_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.perf_counter() - start_time
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        successful_queries = [r for r in results if r["success"]]
        failed_queries = [r for r in results if not r["success"]]
        
        # Performance assertions
        success_rate = len(successful_queries) / len(results)
        avg_query_time = sum(r["duration"] for r in successful_queries) / len(successful_queries) if successful_queries else 0
        
        assert success_rate >= 0.95, f"Database concurrency success rate too low: {success_rate * 100:.1f}%"
        assert avg_query_time < 0.5, f"Average concurrent query time too slow: {avg_query_time:.3f}s"
        
        print(f"Concurrent database operations:")
        print(f"  Workers: {num_workers}")
        print(f"  Success rate: {success_rate * 100:.1f}%")
        print(f"  Average query time: {avg_query_time:.3f}s")
        print(f"  Total test time: {total_time:.3f}s")
```

## Performance Monitoring and Reporting

### Continuous Performance Monitoring
```python
# tests/performance/monitoring.py

import time
import json
import psutil
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    timestamp: float
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str] = None

class PerformanceMonitor:
    """Continuous performance monitoring."""
    
    def __init__(self, output_file: str = "performance_metrics.jsonl"):
        self.output_file = output_file
        self.metrics: List[PerformanceMetric] = []
        self.baseline_metrics: Dict[str, float] = {}
    
    def record_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a performance metric."""
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        self.metrics.append(metric)
    
    def record_response_time(self, endpoint: str, response_time: float, status_code: int = 200):
        """Record API response time."""
        self.record_metric(
            name="api_response_time",
            value=response_time,
            unit="seconds",
            tags={
                "endpoint": endpoint,
                "status_code": str(status_code)
            }
        )
    
    def record_throughput(self, operation: str, requests_per_second: float):
        """Record throughput metric."""
        self.record_metric(
            name="throughput",
            value=requests_per_second,
            unit="rps",
            tags={"operation": operation}
        )
    
    def record_resource_usage(self):
        """Record current system resource usage."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.record_metric("cpu_usage", cpu_percent, "percent")
        
        # Memory usage
        memory = psutil.virtual_memory()
        self.record_metric("memory_usage_percent", memory.percent, "percent")
        self.record_metric("memory_usage_gb", memory.used / (1024**3), "gb")
        
        # Disk I/O
        disk_io = psutil.disk_io_counters()
        self.record_metric("disk_read_rate", disk_io.read_bytes, "bytes")
        self.record_metric("disk_write_rate", disk_io.write_bytes, "bytes")
        
        # Network I/O
        network_io = psutil.net_io_counters()
        self.record_metric("network_sent_rate", network_io.bytes_sent, "bytes")
        self.record_metric("network_recv_rate", network_io.bytes_recv, "bytes")
    
    def set_baseline(self, baseline_file: str = "performance_baseline.json"):
        """Set performance baseline from file."""
        try:
            with open(baseline_file, 'r') as f:
                self.baseline_metrics = json.load(f)
        except FileNotFoundError:
            print(f"Baseline file {baseline_file} not found. Creating new baseline.")
            self.baseline_metrics = {}
    
    def save_baseline(self, baseline_file: str = "performance_baseline.json"):
        """Save current metrics as baseline."""
        baseline_data = self.calculate_summary_metrics()
        with open(baseline_file, 'w') as f:
            json.dump(baseline_data, f, indent=2)
        print(f"Baseline saved to {baseline_file}")
    
    def calculate_summary_metrics(self) -> Dict[str, float]:
        """Calculate summary metrics from recorded data."""
        if not self.metrics:
            return {}
        
        summary = {}
        
        # Group metrics by name
        metric_groups = {}
        for metric in self.metrics:
            if metric.metric_name not in metric_groups:
                metric_groups[metric.metric_name] = []
            metric_groups[metric.metric_name].append(metric.value)
        
        # Calculate statistics for each metric
        for metric_name, values in metric_groups.items():
            if values:
                summary[f"{metric_name}_avg"] = sum(values) / len(values)
                summary[f"{metric_name}_max"] = max(values)
                summary[f"{metric_name}_min"] = min(values)
                if len(values) > 1:
                    sorted_values = sorted(values)
                    p95_index = int(len(values) * 0.95)
                    summary[f"{metric_name}_p95"] = sorted_values[p95_index]
        
        return summary
    
    def detect_regressions(self, threshold_percent: float = 10.0) -> List[Dict[str, Any]]:
        """Detect performance regressions compared to baseline."""
        current_metrics = self.calculate_summary_metrics()
        regressions = []
        
        for metric_name, current_value in current_metrics.items():
            if metric_name in self.baseline_metrics:
                baseline_value = self.baseline_metrics[metric_name]
                
                if baseline_value > 0:  # Avoid division by zero
                    change_percent = ((current_value - baseline_value) / baseline_value) * 100
                    
                    # Check if it's a regression (depending on metric type)
                    is_regression = False
                    if "response_time" in metric_name or "cpu_usage" in metric_name or "memory_usage" in metric_name:
                        # Higher is worse for these metrics
                        is_regression = change_percent > threshold_percent
                    elif "throughput" in metric_name:
                        # Lower is worse for throughput
                        is_regression = change_percent < -threshold_percent
                    
                    if is_regression:
                        regressions.append({
                            "metric": metric_name,
                            "baseline_value": baseline_value,
                            "current_value": current_value,
                            "change_percent": change_percent,
                            "severity": "critical" if abs(change_percent) > 25 else "warning"
                        })
        
        return regressions
    
    def save_metrics(self):
        """Save metrics to file."""
        with open(self.output_file, 'w') as f:
            for metric in self.metrics:
                f.write(json.dumps(asdict(metric)) + '\n')
    
    def generate_performance_report(self) -> str:
        """Generate human-readable performance report."""
        summary = self.calculate_summary_metrics()
        regressions = self.detect_regressions()
        
        report = []
        report.append("# Performance Test Report")
        report.append(f"Generated at: {datetime.now().isoformat()}")
        report.append(f"Total metrics collected: {len(self.metrics)}")
        report.append("")
        
        # Summary metrics
        report.append("## Summary Metrics")
        if summary:
            for metric, value in summary.items():
                unit = ""
                if "response_time" in metric:
                    unit = "s"
                elif "cpu_usage" in metric or "memory_usage_percent" in metric:
                    unit = "%"
                elif "throughput" in metric:
                    unit = "rps"
                elif "memory_usage_gb" in metric:
                    unit = "GB"
                
                report.append(f"- {metric}: {value:.3f}{unit}")
        else:
            report.append("No metrics available")
        
        report.append("")
        
        # Regressions
        report.append("## Performance Regressions")
        if regressions:
            for regression in regressions:
                severity = regression["severity"].upper()
                report.append(f"- [{severity}] {regression['metric']}")
                report.append(f"  Baseline: {regression['baseline_value']:.3f}")
                report.append(f"  Current: {regression['current_value']:.3f}")
                report.append(f"  Change: {regression['change_percent']:+.1f}%")
        else:
            report.append("No performance regressions detected")
        
        return "\n".join(report)

# Global performance monitor instance
performance_monitor = PerformanceMonitor()
```

This comprehensive performance test strategy provides thorough coverage of all performance aspects of the AI Model Validation Platform, ensuring the system can handle production workloads while maintaining acceptable performance characteristics.