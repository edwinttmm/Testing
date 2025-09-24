"""
Performance Benchmark Tests for HIL Ground Truth Matching

Tests performance characteristics of the HIL ground truth matching system
under various load conditions and data scenarios.

Benchmark Coverage:
- Ground truth matching performance with large datasets
- Video timing conversion speed
- Session completion processing time
- Database query optimization validation
- Memory usage during processing
- Concurrent operation handling
"""

import pytest
import sys
import time
import threading
import concurrent.futures
import psutil
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the models and services
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    GroundTruthObject, Base
)
from src.services.session_completion_service import SessionCompletionService
from src.services.ground_truth_service import GroundTruthService


class TestPerformanceBenchmarks:
    """Performance benchmark test suite for HIL system"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def performance_project(self, db_session: Session):
        """Create a project for performance testing"""
        project = Project(
            name="Performance Test Project",
            description="High-load performance testing",
            camera_model="Performance Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db_session.add(project)
        db_session.commit()
        return project
    
    @pytest.fixture
    def performance_video(self, db_session: Session, performance_project):
        """Create a video for performance testing"""
        video = Video(
            filename="performance_test.mp4",
            file_path="/test/performance_test.mp4",
            file_size=100000000,  # 100MB file
            duration=120.0,       # 2 minute video
            fps=60.0,
            resolution="1920x1080",
            status="validated",
            project_id=performance_project.id,
            ground_truth_count=1000  # Large ground truth dataset
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    def create_large_ground_truth_dataset(self, db_session: Session, video, count: int = 1000):
        """Create large ground truth dataset for performance testing"""
        ground_truth_objects = []
        
        # Create ground truth objects with realistic distribution
        vru_types = ["pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"]
        
        for i in range(count):
            timestamp = (i / count) * video.duration  # Distribute across video duration
            vru_type = vru_types[i % len(vru_types)]
            
            gt = GroundTruthObject(
                video_id=video.id,
                tracking_id=f"perf_vru_{i}",
                frame_number=int(timestamp * video.fps),
                timestamp=timestamp,
                class_label=vru_type,
                x=100 + (i % 50) * 20,  # Distribute across image
                y=200 + (i % 20) * 30,
                width=60 + (i % 20) * 2,   # Varying sizes
                height=120 + (i % 30) * 3,
                confidence=0.80 + (i % 20) * 0.01,  # Varying confidence
                validated=True,
                difficult=(i % 10 == 0)  # 10% difficult detections
            )
            ground_truth_objects.append(gt)
            
            # Batch insert for performance
            if len(ground_truth_objects) >= 100:
                db_session.add_all(ground_truth_objects)
                db_session.commit()
                ground_truth_objects = []
        
        # Insert remaining objects
        if ground_truth_objects:
            db_session.add_all(ground_truth_objects)
            db_session.commit()
        
        return count
    
    def create_large_detection_dataset(self, db_session: Session, session_id: str, 
                                     video_start_time: datetime, count: int = 5000):
        """Create large detection event dataset"""
        detection_events = []
        
        for i in range(count):
            # Distribute detections across time period
            time_offset = (i / count) * 120.0  # 2 minutes
            detection_time = video_start_time + timedelta(seconds=time_offset)
            
            # Add some jitter for realism
            jitter_ms = (i % 100) - 50  # ±50ms jitter
            detection_time += timedelta(milliseconds=jitter_ms)
            
            detection = DetectionEvent(
                test_session_id=session_id,
                timestamp=detection_time,
                signal_type="GPIO",
                signal_value=1,
                gpio_pin=2,
                validation_result=None,  # To be calculated
                latency_ms=None,
                event_metadata={
                    "performance_test": True,
                    "detection_index": i,
                    "expected_jitter_ms": jitter_ms
                }
            )
            detection_events.append(detection)
            
            # Batch insert for performance
            if len(detection_events) >= 500:
                db_session.add_all(detection_events)
                db_session.commit()
                detection_events = []
        
        # Insert remaining events
        if detection_events:
            db_session.add_all(detection_events)
            db_session.commit()
        
        return count
    
    def measure_memory_usage(self):
        """Get current memory usage"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size in MB
            "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size in MB
            "percent": process.memory_percent()
        }
    
    def test_ground_truth_matching_performance_large_dataset(self, db_session: Session, 
                                                           performance_project, performance_video):
        """
        Benchmark: Ground truth matching with 1000 ground truth objects and 5000 detections
        Requirements: Processing time < 5 seconds, Memory usage < 500MB
        """
        # Create large datasets
        gt_count = self.create_large_ground_truth_dataset(db_session, performance_video, 1000)
        
        # Create test session
        session_start_time = datetime.utcnow()
        session = TestSession(
            name="Large Dataset Performance Test",
            project_id=performance_project.id,
            status="running",
            started_at=session_start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": session_start_time.timestamp(),
                    "video_id": performance_video.id,
                    "fps": performance_video.fps,
                    "duration_seconds": performance_video.duration
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,
                    "enabled": True
                },
                "performance_test": {
                    "ground_truth_count": gt_count,
                    "detection_count": 5000
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Create large detection dataset
        detection_count = self.create_large_detection_dataset(db_session, session.id, session_start_time, 5000)
        
        # Measure initial memory usage\n        initial_memory = self.measure_memory_usage()
        
        # Benchmark session completion
        start_time = time.perf_counter()
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        end_time = time.perf_counter()
        
        processing_time = end_time - start_time
        final_memory = self.measure_memory_usage()
        memory_increase = final_memory["rss_mb"] - initial_memory["rss_mb"]
        
        # Performance assertions
        assert result["success"] is True, "Large dataset processing should succeed"
        assert processing_time < 5.0, f"Processing time {processing_time:.2f}s exceeds 5s limit"
        assert memory_increase < 500, f"Memory increase {memory_increase:.1f}MB exceeds 500MB limit"
        
        # Verify processing accuracy
        test_result = db_session.query(TestResult).filter(TestResult.test_session_id == session.id).first()
        assert test_result.total_detections == detection_count
        assert test_result.avg_latency_ms is not None
        
        print(f"Large Dataset Performance:")
        print(f"  Ground Truth Objects: {gt_count}")
        print(f"  Detection Events: {detection_count}")
        print(f"  Processing Time: {processing_time:.2f}s")
        print(f"  Memory Increase: {memory_increase:.1f}MB")
        print(f"  Success Rate: {test_result.pass_rate:.1f}%")
        print(f"  Average Latency: {test_result.avg_latency_ms:.1f}ms")
        
        return {
            "processing_time": processing_time,
            "memory_increase": memory_increase,
            "ground_truth_count": gt_count,
            "detection_count": detection_count,
            "success_rate": test_result.pass_rate
        }
    
    def test_video_timing_conversion_speed(self, db_session: Session):
        """
        Benchmark: Video timing conversion operations
        Requirements: 10,000 conversions in < 100ms
        """
        base_timestamp = datetime.utcnow().timestamp()
        conversion_count = 10000
        
        # Benchmark timestamp conversions
        start_time = time.perf_counter()
        
        for i in range(conversion_count):
            # Simulate video-relative to Unix conversion
            video_time = i * 0.01  # 10ms intervals
            unix_time = base_timestamp + video_time
            
            # Simulate Unix to video-relative conversion
            back_to_video_time = unix_time - base_timestamp
            
            # Simple validation
            assert abs(back_to_video_time - video_time) < 0.001
        
        end_time = time.perf_counter()
        conversion_time = end_time - start_time
        
        # Performance requirements
        assert conversion_time < 0.1, f"Conversion time {conversion_time:.3f}s exceeds 100ms limit"
        
        conversions_per_second = conversion_count / conversion_time
        assert conversions_per_second > 100000, f"Conversion rate {conversions_per_second:.0f}/s too slow"
        
        print(f"Video Timing Conversion Performance:")
        print(f"  Conversions: {conversion_count}")
        print(f"  Total Time: {conversion_time:.3f}s")
        print(f"  Rate: {conversions_per_second:.0f} conversions/second")
        
        return conversion_time
    
    def test_database_query_performance(self, db_session: Session, performance_project, performance_video):
        """
        Benchmark: Database query performance with large datasets
        Requirements: Complex queries complete in < 500ms
        """
        # Create moderate dataset for query testing
        gt_count = self.create_large_ground_truth_dataset(db_session, performance_video, 500)
        
        # Create test session with detections
        session_start_time = datetime.utcnow()
        session = TestSession(
            name="Query Performance Test",
            project_id=performance_project.id,
            status="running",
            started_at=session_start_time
        )
        db_session.add(session)
        db_session.commit()
        
        # Create detection events
        detection_count = self.create_large_detection_dataset(db_session, session.id, session_start_time, 1000)
        
        # Benchmark various database queries
        query_benchmarks = {}
        
        # Query 1: Get all ground truth objects for video
        start_time = time.perf_counter()
        ground_truth_objects = db_session.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == performance_video.id
        ).all()
        query_benchmarks["ground_truth_query"] = time.perf_counter() - start_time
        
        # Query 2: Get all detection events for session
        start_time = time.perf_counter()
        detection_events = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).all()
        query_benchmarks["detection_query"] = time.perf_counter() - start_time
        
        # Query 3: Complex join query with filtering
        start_time = time.perf_counter()
        complex_query = db_session.query(DetectionEvent).join(
            TestSession, DetectionEvent.test_session_id == TestSession.id
        ).filter(
            TestSession.project_id == performance_project.id,
            DetectionEvent.signal_type == "GPIO"
        ).all()
        query_benchmarks["complex_join_query"] = time.perf_counter() - start_time
        
        # Query 4: Aggregate query for metrics
        start_time = time.perf_counter()
        from sqlalchemy import func
        stats = db_session.query(
            func.count(DetectionEvent.id).label('total_count'),
            func.avg(DetectionEvent.latency_ms).label('avg_latency')
        ).filter(DetectionEvent.test_session_id == session.id).first()
        query_benchmarks["aggregate_query"] = time.perf_counter() - start_time
        
        # Performance assertions
        for query_name, query_time in query_benchmarks.items():
            assert query_time < 0.5, f"{query_name} took {query_time:.3f}s, exceeds 500ms limit"
        
        print(f"Database Query Performance (with {gt_count} GT objects, {detection_count} detections):")
        for query_name, query_time in query_benchmarks.items():
            print(f"  {query_name}: {query_time:.3f}s")
        
        return query_benchmarks
    
    def test_concurrent_session_completion_performance(self, db_session: Session, performance_project):
        """
        Benchmark: Concurrent session completion operations
        Requirements: Handle 5 concurrent sessions without significant slowdown
        """
        # Create multiple test videos and sessions
        sessions = []
        videos = []
        
        for i in range(5):
            video = Video(
                filename=f"concurrent_test_{i}.mp4",
                file_path=f"/test/concurrent_test_{i}.mp4",
                file_size=10000000,
                duration=30.0,
                fps=30.0,
                resolution="1920x1080",
                status="validated",
                project_id=performance_project.id,
                ground_truth_count=100
            )
            videos.append(video)
            db_session.add(video)
        
        db_session.commit()
        
        # Create ground truth and sessions
        for i, video in enumerate(videos):
            # Create smaller dataset for concurrent testing
            self.create_large_ground_truth_dataset(db_session, video, 100)
            
            session_start_time = datetime.utcnow()
            session = TestSession(
                name=f"Concurrent Test Session {i}",
                project_id=performance_project.id,
                status="running",
                started_at=session_start_time,
                configuration={
                    "video_timing": {
                        "video_start_unix_time": session_start_time.timestamp(),
                        "video_id": video.id,
                        "fps": video.fps,
                        "duration_seconds": video.duration
                    }
                }
            )
            sessions.append(session)
            db_session.add(session)
        
        db_session.commit()
        
        # Create detection events for each session
        for session in sessions:
            self.create_large_detection_dataset(db_session, session.id, session.started_at, 500)
        
        # Benchmark concurrent completion
        def complete_session(session_id):
            # Each thread needs its own database session
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            engine = create_engine("sqlite:///:memory:", echo=False)
            Base.metadata.create_all(engine)
            ThreadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            thread_session = ThreadSessionLocal()
            
            try:
                completion_service = SessionCompletionService(thread_session)
                start_time = time.perf_counter()
                result = completion_service.complete_test_session(session_id)
                end_time = time.perf_counter()
                
                return {
                    "session_id": session_id,
                    "success": result["success"],
                    "processing_time": end_time - start_time
                }
            finally:
                thread_session.close()
        
        # Execute concurrent completions
        start_time = time.perf_counter()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(complete_session, session.id) for session in sessions]
            results = concurrent.futures.as_completed(futures, timeout=30)
            completion_results = [future.result() for future in results]
        
        total_time = time.perf_counter() - start_time
        
        # Verify all sessions completed successfully
        successful_completions = [r for r in completion_results if r["success"]]
        assert len(successful_completions) == 5, "All concurrent sessions should complete successfully"
        
        # Check performance requirements
        max_individual_time = max(r["processing_time"] for r in completion_results)
        avg_individual_time = sum(r["processing_time"] for r in completion_results) / len(completion_results)
        
        assert total_time < 15.0, f"Total concurrent processing time {total_time:.2f}s too high"
        assert max_individual_time < 5.0, f"Slowest individual session {max_individual_time:.2f}s too slow"
        
        print(f"Concurrent Session Completion Performance:")
        print(f"  Sessions: {len(sessions)}")
        print(f"  Total Time: {total_time:.2f}s")
        print(f"  Average Individual Time: {avg_individual_time:.2f}s")
        print(f"  Max Individual Time: {max_individual_time:.2f}s")
        print(f"  Concurrent Efficiency: {(avg_individual_time * 5) / total_time:.1f}x")
        
        return {
            "total_time": total_time,
            "avg_individual_time": avg_individual_time,
            "max_individual_time": max_individual_time,
            "sessions_completed": len(successful_completions)
        }
    
    def test_memory_usage_stability(self, db_session: Session, performance_project, performance_video):
        """
        Benchmark: Memory usage stability during extended processing
        Requirements: Memory usage should not grow significantly over multiple operations
        """
        initial_memory = self.measure_memory_usage()
        memory_readings = [initial_memory["rss_mb"]]
        
        # Perform multiple processing cycles
        for cycle in range(10):
            # Create ground truth dataset
            gt_count = self.create_large_ground_truth_dataset(db_session, performance_video, 200)
            
            # Create session
            session_start_time = datetime.utcnow()
            session = TestSession(
                name=f"Memory Test Cycle {cycle}",
                project_id=performance_project.id,
                status="running",
                started_at=session_start_time,
                configuration={
                    "video_timing": {
                        "video_start_unix_time": session_start_time.timestamp(),
                        "video_id": performance_video.id
                    }
                }
            )
            db_session.add(session)
            db_session.commit()
            
            # Create detections and complete session
            detection_count = self.create_large_detection_dataset(db_session, session.id, session_start_time, 1000)
            
            completion_service = SessionCompletionService(db_session)
            result = completion_service.complete_test_session(session.id)
            
            # Measure memory after each cycle
            current_memory = self.measure_memory_usage()
            memory_readings.append(current_memory["rss_mb"])
            
            # Clean up to prevent accumulation
            db_session.query(DetectionEvent).filter(DetectionEvent.test_session_id == session.id).delete()
            db_session.query(GroundTruthObject).filter(GroundTruthObject.video_id == performance_video.id).delete()
            db_session.query(TestSession).filter(TestSession.id == session.id).delete()
            db_session.commit()
        
        final_memory = self.measure_memory_usage()
        
        # Analyze memory stability
        max_memory = max(memory_readings)
        min_memory = min(memory_readings)
        memory_range = max_memory - min_memory
        memory_growth = final_memory["rss_mb"] - initial_memory["rss_mb"]
        
        # Memory stability requirements
        assert memory_range < 100, f"Memory range {memory_range:.1f}MB indicates instability"
        assert memory_growth < 50, f"Memory growth {memory_growth:.1f}MB indicates memory leak"
        
        print(f"Memory Usage Stability (10 cycles):")
        print(f"  Initial Memory: {initial_memory['rss_mb']:.1f}MB")
        print(f"  Final Memory: {final_memory['rss_mb']:.1f}MB")
        print(f"  Memory Growth: {memory_growth:.1f}MB")
        print(f"  Memory Range: {memory_range:.1f}MB")
        print(f"  Max Memory: {max_memory:.1f}MB")
        
        return {
            "initial_memory_mb": initial_memory["rss_mb"],
            "final_memory_mb": final_memory["rss_mb"],
            "memory_growth_mb": memory_growth,
            "memory_range_mb": memory_range,
            "max_memory_mb": max_memory
        }
    
    def test_latency_calculation_performance(self, db_session: Session):
        """
        Benchmark: Latency calculation operations
        Requirements: Calculate latencies for 10,000 detection pairs in < 200ms
        """
        # Create test timestamp pairs for latency calculation
        base_time = datetime.utcnow()
        test_pairs = []
        
        for i in range(10000):
            ground_truth_time = base_time + timedelta(seconds=i * 0.1)
            detection_time = ground_truth_time + timedelta(milliseconds=i % 200)  # 0-200ms latency
            test_pairs.append((ground_truth_time, detection_time))
        
        # Benchmark latency calculations
        start_time = time.perf_counter()
        
        calculated_latencies = []
        for gt_time, det_time in test_pairs:
            latency_ms = (det_time - gt_time).total_seconds() * 1000
            calculated_latencies.append(latency_ms)
        
        end_time = time.perf_counter()
        calculation_time = end_time - start_time
        
        # Performance requirements
        assert calculation_time < 0.2, f"Latency calculation time {calculation_time:.3f}s exceeds 200ms limit"
        
        # Verify calculation accuracy
        assert len(calculated_latencies) == 10000
        assert all(0 <= latency <= 200 for latency in calculated_latencies)
        
        calculations_per_second = 10000 / calculation_time
        
        print(f"Latency Calculation Performance:")
        print(f"  Calculations: 10,000")
        print(f"  Total Time: {calculation_time:.3f}s")
        print(f"  Rate: {calculations_per_second:.0f} calculations/second")
        
        return calculation_time


if __name__ == "__main__":
    # Run performance benchmarks
    pytest.main([__file__, "-v", "--tb=short", "-s"])