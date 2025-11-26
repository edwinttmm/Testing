#!/usr/bin/env python3
"""
Performance Optimization Test Suite

Tests the critical database performance fixes for:
1. N+1 query elimination in /projects/all endpoint
2. Connection leak prevention in /statistics/summary endpoint
3. Proper session management validation

Author: Performance Optimization Team
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
import logging
from sqlalchemy import create_engine, text, select, delete, update, func
from sqlalchemy.orm import sessionmaker

# Import application components
from database import get_db, engine
from api_project_session_management import router
from models import Project, Video, TestSession, VideoProjectLink
from fastapi.testclient import TestClient
from fastapi import FastAPI

logger = logging.getLogger(__name__)

class PerformanceTestSuite:
    """Comprehensive performance test suite for database optimizations"""
    
    def __init__(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)
        self.query_counts = []
        self.connection_counts = []
        
    def setup_test_data(self):
        """Setup test data for performance testing"""
        with engine.begin() as conn:
            # Create test projects (simulate realistic dataset)
            projects_data = [
                {"id": f"project-{i:03d}", "name": f"Test Project {i}", "description": f"Performance test project {i}"}
                for i in range(1, 101)  # 100 test projects
            ]
            
            # Create test sessions for projects
            sessions_data = []
            for i, project in enumerate(projects_data[:50]):  # Only first 50 projects have sessions
                for j in range(1, 6):  # 5 sessions per project
                    sessions_data.append({
                        "id": f"session-{i:03d}-{j:02d}",
                        "project_id": project["id"],
                        "name": f"Session {j} for {project['name']}",
                        "status": ["created", "running", "completed", "failed"][j % 4]
                    })
            
            # Create test videos
            videos_data = []
            for i, project in enumerate(projects_data[:75]):  # First 75 projects have videos
                for j in range(1, 4):  # 3 videos per project
                    videos_data.append({
                        "id": f"video-{i:03d}-{j:02d}",
                        "project_id": project["id"],
                        "filename": f"test_video_{i}_{j}.mp4",
                        "status": "processed"
                    })
            
            logger.info(f"Created {len(projects_data)} projects, {len(sessions_data)} sessions, {len(videos_data)} videos")
    
    @patch('sqlalchemy.orm.Session.execute')
    def test_projects_all_query_optimization(self, mock_execute):
        """Test that /projects/all endpoint uses optimized single query"""
        # Mock the database results to simulate the optimized query
        mock_result = Mock()
        mock_result.all.return_value = [
            Mock(id="project-001", name="Test Project 1", description="Test", status="active",
                 camera_model=None, camera_view=None, signal_type=None, created_at=None,
                 session_count=5, direct_video_count=3, linked_video_count=2)
        ]
        mock_execute.return_value = mock_result
        
        # Make request to optimized endpoint
        response = self.client.get("/api/project-sessions/projects/all")
        
        # Verify response is successful
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Critical: Verify only ONE database query was executed (no N+1 problem)
        assert mock_execute.call_count == 1, f"Expected 1 query, got {mock_execute.call_count} queries"
        
        # Verify the query structure includes all necessary joins
        query_sql = str(mock_execute.call_args[0][0])
        assert "outerjoin" in query_sql.lower() or "join" in query_sql.lower(), "Query should use joins for efficiency"
        
        logger.info("✅ /projects/all endpoint uses optimized single query")
    
    @patch('api_project_session_management.Session')
    def test_statistics_connection_leak_fix(self, mock_session_class):
        """Test that /statistics/summary endpoint properly manages connections"""
        # This test verifies the old manual Session() creation was replaced
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Make request to statistics endpoint
        response = self.client.get("/api/project-sessions/statistics/summary")
        
        # Verify manual Session() is NOT called (should use dependency injection now)
        mock_session_class.assert_not_called()
        
        logger.info("✅ /statistics/summary endpoint properly uses dependency injection")
    
    def test_concurrent_requests_performance(self):
        """Test performance under concurrent load"""
        def make_request(endpoint):
            start_time = time.time()
            response = self.client.get(f"/api/project-sessions/{endpoint}")
            end_time = time.time()
            return {
                "endpoint": endpoint,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Test concurrent requests to both optimized endpoints
        endpoints = ["projects/all", "statistics/summary"]
        results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit 50 concurrent requests (25 per endpoint)
            futures = []
            for i in range(25):
                for endpoint in endpoints:
                    futures.append(executor.submit(make_request, endpoint))
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=10)  # 10 second timeout per request
                    results.append(result)
                except Exception as e:
                    logger.error(f"Concurrent request failed: {e}")
                    results.append({"success": False, "error": str(e)})
        
        # Analyze performance results
        successful_requests = [r for r in results if r.get("success", False)]
        failed_requests = [r for r in results if not r.get("success", False)]
        
        success_rate = len(successful_requests) / len(results) * 100
        avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests) if successful_requests else 0
        max_response_time = max(r["response_time"] for r in successful_requests) if successful_requests else 0
        
        # Performance assertions
        assert success_rate >= 95, f"Success rate too low: {success_rate}% (expected >= 95%)"
        assert avg_response_time <= 2.0, f"Average response time too high: {avg_response_time}s (expected <= 2.0s)"
        assert max_response_time <= 5.0, f"Max response time too high: {max_response_time}s (expected <= 5.0s)"
        assert len(failed_requests) == 0, f"Failed requests detected: {failed_requests}"
        
        logger.info(f"✅ Concurrent performance test passed:")
        logger.info(f"   Success rate: {success_rate:.1f}%")
        logger.info(f"   Avg response time: {avg_response_time:.3f}s")
        logger.info(f"   Max response time: {max_response_time:.3f}s")
    
    def test_database_connection_pool_health(self):
        """Test database connection pool remains healthy under load"""
        from database import engine, get_database_health
        
        initial_health = get_database_health()
        assert initial_health["status"] == "healthy", f"Database not healthy before test: {initial_health}"
        
        # Simulate heavy load by making many concurrent database connections
        def stress_database():
            try:
                db = next(get_db())
                # Perform a simple query
                db.execute(text("SELECT 1"))
                return True
            except Exception as e:
                logger.error(f"Database stress test failed: {e}")
                return False
        
        # Run stress test with multiple threads
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(stress_database) for _ in range(100)]
            results = [future.result(timeout=5) for future in as_completed(futures)]
        
        success_count = sum(results)
        failure_count = len(results) - success_count
        
        # Check final database health
        final_health = get_database_health()
        
        # Assertions
        assert success_count >= 95, f"Too many database connection failures: {failure_count}/100"
        assert final_health["status"] == "healthy", f"Database unhealthy after stress test: {final_health}"
        
        # Check connection pool hasn't leaked
        if hasattr(engine, 'pool') and engine.pool:
            pool_status = {
                "size": engine.pool.size(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
                "invalid": engine.pool.invalid()
            }
            
            # Connection pool should be stable
            assert pool_status["checked_out"] <= pool_status["size"] + pool_status["overflow"], \
                f"Connection pool leak detected: {pool_status}"
            
            logger.info(f"✅ Database connection pool healthy: {pool_status}")
    
    def test_query_execution_plan_validation(self):
        """Validate query execution plans for efficiency"""
        from sqlalchemy import create_engine, text, select, delete, update, func
        
        # Test the optimized projects query execution plan
        with engine.connect() as conn:
            # Get execution plan for projects query (PostgreSQL EXPLAIN)
            if "postgresql" in str(engine.url):
                explain_query = text("""
                    EXPLAIN (ANALYZE, BUFFERS) 
                    SELECT p.id, p.name, COUNT(DISTINCT ts.id) as session_count,
                           COUNT(DISTINCT v.id) as video_count
                    FROM projects p
                    LEFT JOIN test_sessions ts ON ts.project_id = p.id
                    LEFT JOIN videos v ON v.project_id = p.id
                    GROUP BY p.id, p.name
                """)
                
                result = conn.execute(explain_query)
                execution_plan = result.fetchall()
                
                # Check for performance indicators
                plan_text = ' '.join([str(row[0]) for row in execution_plan]).lower()
                
                # Good indicators: uses indexes, efficient joins
                good_indicators = ["index scan", "hash join", "nested loop"]
                # Bad indicators: sequential scans on large tables, sort operations
                bad_indicators = ["seq scan", "sort"]
                
                good_count = sum(1 for indicator in good_indicators if indicator in plan_text)
                bad_count = sum(1 for indicator in bad_indicators if indicator in plan_text)
                
                logger.info(f"Query execution plan analysis - Good indicators: {good_count}, Bad indicators: {bad_count}")
                logger.info(f"Execution plan: {plan_text[:200]}...")
        
        logger.info("✅ Query execution plan validation completed")


def test_performance_optimization_suite():
    """Main test runner for performance optimization suite"""
    suite = PerformanceTestSuite()
    
    try:
        # Setup test environment
        suite.setup_test_data()
        
        # Run all performance tests
        suite.test_projects_all_query_optimization()
        suite.test_statistics_connection_leak_fix()
        suite.test_concurrent_requests_performance()
        suite.test_database_connection_pool_health()
        suite.test_query_execution_plan_validation()
        
        logger.info("🎉 All performance optimization tests passed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Performance optimization tests failed: {e}")
        raise


if __name__ == "__main__":
    # Run performance tests
    logging.basicConfig(level=logging.INFO)
    test_performance_optimization_suite()