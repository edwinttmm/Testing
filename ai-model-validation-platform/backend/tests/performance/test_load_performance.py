"""Load tests to verify performance optimizations"""
import pytest
import threading
import time
import uuid
from sqlalchemy import create_engine, select, delete, update, func
from sqlalchemy.orm import sessionmaker
from models import TestSession, DetectionEvent
from database import Base
import os


class TestConcurrentPerformance:
    """Test performance under concurrent load"""

    @pytest.fixture(scope="class")
    def perf_engine(self):
        """Create dedicated engine for performance tests"""
        db_url = os.getenv(
            "TEST_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/test_validation_db"
        )
        engine = create_engine(
            db_url,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True
        )
        yield engine
        engine.dispose()

    @pytest.fixture(scope="function")
    def perf_session(self, perf_engine):
        """Create session for performance tests"""
        Session = sessionmaker(bind=perf_engine)
        session = Session()
        yield session
        session.close()

    def test_concurrent_session_creation_no_degradation(self, perf_engine):
        """
        Test that 25 concurrent sessions don't cause 7x degradation.
        This verifies jitter reduction and connection management fixes.

        Target: Average time per session < 3x baseline
        """
        num_sessions = 25
        results = []
        errors = []

        def create_session(index):
            Session = sessionmaker(bind=perf_engine)
            session = Session()
            try:
                start = time.time()

                test_session = TestSession(
                    id=str(uuid.uuid4()),
                    project_id=str(uuid.uuid4()),
                    timing_degraded=False,
                    timing_verified=True
                )
                session.add(test_session)
                session.commit()

                duration = time.time() - start
                results.append(duration)
            except Exception as e:
                errors.append(str(e))
            finally:
                session.close()

        # Create threads
        threads = [
            threading.Thread(target=create_session, args=(i,))
            for i in range(num_sessions)
        ]

        # Start all
        overall_start = time.time()
        for t in threads:
            t.start()

        # Wait
        for t in threads:
            t.join()

        overall_time = time.time() - overall_start

        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == num_sessions

        avg_time = sum(results) / len(results)
        max_time = max(results)
        min_time = min(results)

        # Baseline expectation: ~0.1s per session
        baseline = 0.1

        # Should not have 7x degradation (was the original problem)
        assert avg_time < baseline * 3, f"Performance degradation: {avg_time/baseline:.1f}x (expected < 3x)"

        print(f"\n✅ Concurrent session creation performance:")
        print(f"   Total time: {overall_time:.2f}s")
        print(f"   Average: {avg_time:.3f}s (target: <{baseline*3:.3f}s)")
        print(f"   Min: {min_time:.3f}s, Max: {max_time:.3f}s")
        print(f"   Performance ratio: {avg_time/baseline:.1f}x baseline")

    def test_rapid_detection_events(self, perf_engine):
        """Test rapid detection event creation"""
        # Create session first
        Session = sessionmaker(bind=perf_engine)
        session = Session()

        session_id = str(uuid.uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid.uuid4())
        )
        session.add(test_session)
        session.commit()
        session.close()

        # Now create 100 detections rapidly
        num_detections = 100
        results = []

        def create_detection(index):
            Session = sessionmaker(bind=perf_engine)
            session = Session()
            try:
                start = time.time()

                detection = DetectionEvent(
                    test_session_id=session_id,
                    voltage=4.0 + (index % 10) * 0.1,
                    timestamp=time.time(),
                    usable_for_validation=True
                )
                session.add(detection)
                session.commit()

                duration = time.time() - start
                results.append(duration)
            finally:
                session.close()

        threads = [
            threading.Thread(target=create_detection, args=(i,))
            for i in range(num_detections)
        ]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.time() - start

        avg_time = sum(results) / len(results)

        print(f"\n✅ Rapid detection creation:")
        print(f"   {num_detections} detections in {total_time:.2f}s")
        print(f"   Average: {avg_time:.3f}s per detection")
        print(f"   Throughput: {num_detections/total_time:.1f} detections/sec")

        # Should handle at least 20 detections/sec
        assert num_detections/total_time > 20

    def test_connection_pool_efficiency(self, perf_engine):
        """Test that connection pool is used efficiently"""
        num_operations = 50
        results = []

        def db_operation(index):
            Session = sessionmaker(bind=perf_engine)
            session = Session()
            try:
                start = time.time()

                # Mix of operations
                session.execute(select(func.count()).select_from(TestSession)).scalar()

                test_session = TestSession(
                    id=str(uuid.uuid4()),
                    project_id=str(uuid.uuid4())
                )
                session.add(test_session)
                session.commit()

                session.execute(select(TestSession).where(
                    TestSession.id == test_session.id
                )).scalar_one_or_none()

                duration = time.time() - start
                results.append(duration)
            finally:
                session.close()

        threads = [
            threading.Thread(target=db_operation, args=(i,))
            for i in range(num_operations)
        ]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.time() - start

        avg_time = sum(results) / len(results)

        print(f"\n✅ Connection pool efficiency:")
        print(f"   {num_operations} mixed operations in {total_time:.2f}s")
        print(f"   Average: {avg_time:.3f}s per operation")

        # With good connection pooling, should be fast
        assert avg_time < 0.2


class TestQueryPerformance:
    """Test query performance"""

    def test_quality_filtered_query_performance(self, db_session):
        """Test performance of quality-filtered queries"""
        # Create test data
        project_id = str(uuid.uuid4())
        session_ids = []

        for i in range(20):
            session_id = str(uuid.uuid4())
            session = TestSession(
                id=session_id,
                project_id=project_id,
                timing_degraded=(i % 3 == 0),
                timing_verified=(i % 3 != 0)
            )
            db_session.add(session)
            session_ids.append(session_id)

        db_session.commit()

        # Add detections
        for session_id in session_ids:
            for j in range(10):
                detection = DetectionEvent(
                    test_session_id=session_id,
                    voltage=4.0 + j * 0.1,
                    timestamp=time.time(),
                    usable_for_validation=(j % 2 == 0)
                )
                db_session.add(detection)

        db_session.commit()

        # Test query performance
        start = time.time()

        # Complex filtered query
        high_quality = db_session.execute(select(TestSession).where(
            TestSession.project_id == project_id,
            TestSession.timing_degraded == False,
            TestSession.timing_verified == True
        )).scalars().all()

        session_ids = [s.id for s in high_quality]
        usable_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id.in_(session_ids),
            DetectionEvent.usable_for_validation == True
        ).all()

        duration = time.time() - start

        print(f"\n✅ Quality filtered query performance:")
        print(f"   Query time: {duration:.3f}s")
        print(f"   Found {len(high_quality)} sessions, {len(usable_detections)} detections")

        # Should be fast even with filtering
        assert duration < 0.5


class TestMemoryUsage:
    """Test memory usage under load"""

    def test_no_memory_leak_on_rapid_operations(self, db_session):
        """Test that rapid operations don't cause memory leaks"""
        import tracemalloc

        tracemalloc.start()
        initial = tracemalloc.get_traced_memory()[0]

        # Perform many operations
        for i in range(100):
            session = TestSession(
                id=str(uuid.uuid4()),
                project_id=str(uuid.uuid4())
            )
            db_session.add(session)

            if i % 10 == 0:
                db_session.commit()
                db_session.expire_all()

        db_session.commit()

        final = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()

        memory_increase = (final - initial) / 1024 / 1024  # MB

        print(f"\n✅ Memory usage test:")
        print(f"   Memory increase: {memory_increase:.2f} MB")

        # Should not use excessive memory
        assert memory_increase < 50  # Less than 50MB increase
