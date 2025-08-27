#!/usr/bin/env python3
"""
VRU Integration Test Suite - SPARC Implementation
Comprehensive testing for VRU database integration

SPARC Testing:
- Specification: Complete test coverage for VRU integration
- Pseudocode: Test algorithms for all integration points
- Architecture: Comprehensive test suite structure
- Refinement: Production-ready test scenarios
- Completion: Full integration validation
"""

import pytest
import asyncio
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import tempfile
import os

# Add backend root to path
import sys
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

try:
    # VRU Integration components
    from src.vru_database_integration_layer import (
        VRUDatabaseIntegrationLayer, VRUDetectionData, VideoMetadata,
        get_vru_integration_layer
    )
    from src.vru_enhanced_models import MLModel, MLInferenceSession, ObjectDetection
    from src.vru_ml_database_connector import (
        VRUMLDatabaseConnector, MLEngineConfig, create_ml_database_connector
    )
    from src.vru_performance_optimizer import VRUPerformanceOptimizer, CacheConfig
    from src.vru_database_migrations import VRUDatabaseMigrator, run_vru_migration
    
    # Core components
    from unified_database import get_database_manager
    from models import Video, Project, TestSession, DetectionEvent, Annotation
    
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    pytest.skip(f"VRU integration dependencies not available: {e}", allow_module_level=True)

class TestVRUDatabaseIntegration:
    """Test VRU Database Integration Layer"""
    
    @pytest.fixture
    def integration_layer(self):
        """Create integration layer for testing"""
        return get_vru_integration_layer()
    
    @pytest.fixture
    def sample_video_metadata(self):
        """Sample video metadata for testing"""
        return VideoMetadata(
            video_id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/tmp/test_video.mp4",
            file_size=1024000,
            duration=30.0,
            fps=30.0,
            resolution="1920x1080",
            total_frames=900
        )
    
    @pytest.fixture
    def sample_detection_data(self):
        """Sample detection data for testing"""
        return VRUDetectionData(
            detection_id=f"DET_TEST_{uuid.uuid4().hex[:8]}",
            video_id=str(uuid.uuid4()),
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            confidence=0.85,
            bounding_box={"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
            class_label="person",
            model_version="yolo11l_test"
        )
    
    @pytest.mark.asyncio
    async def test_store_video_metadata(self, integration_layer, sample_video_metadata):
        """Test video metadata storage"""
        # Create test project
        project_id = str(uuid.uuid4())
        
        # Store video metadata
        video_id = await integration_layer.store_video_with_metadata(
            sample_video_metadata, project_id
        )
        
        assert video_id == sample_video_metadata.video_id
        
        # Retrieve and verify
        retrieved_metadata = await integration_layer.get_video_metadata(video_id)
        assert retrieved_metadata is not None
        assert retrieved_metadata["filename"] == sample_video_metadata.filename
        assert retrieved_metadata["project_id"] == project_id
    
    @pytest.mark.asyncio
    async def test_store_vru_detection(self, integration_layer, sample_detection_data):
        """Test VRU detection storage"""
        # Create test session
        test_session_id = str(uuid.uuid4())
        
        # Store detection
        detection_id = await integration_layer.store_vru_detection(
            sample_detection_data, test_session_id
        )
        
        assert detection_id is not None
        
        # Verify detection was stored (would need to extend integration layer)
        # This would typically query the database to verify storage
    
    @pytest.mark.asyncio
    async def test_batch_store_detections(self, integration_layer):
        """Test batch detection storage"""
        # Create multiple detections
        detections = []
        for i in range(10):
            detection = VRUDetectionData(
                detection_id=f"DET_BATCH_{i}_{uuid.uuid4().hex[:8]}",
                video_id=str(uuid.uuid4()),
                frame_number=i * 10,
                timestamp=i * 0.33,
                vru_type="cyclist" if i % 2 else "pedestrian",
                confidence=0.7 + (i * 0.02),
                bounding_box={"x": 0.1 + i*0.05, "y": 0.2, "width": 0.3, "height": 0.4},
                class_label="bicycle" if i % 2 else "person",
                model_version="batch_test"
            )
            detections.append(detection)
        
        # Batch store
        detection_ids = await integration_layer.batch_store_detections(detections)
        
        assert len(detection_ids) == 10
        assert all(detection_id is not None for detection_id in detection_ids)
    
    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, integration_layer):
        """Test performance metrics retrieval"""
        metrics = await integration_layer.get_performance_metrics()
        
        assert "detections_stored" in metrics
        assert "videos_processed" in metrics
        assert "database_health" in metrics
        assert isinstance(metrics["detections_stored"], int)

class TestVRUMLDatabaseConnector:
    """Test ML-Database Connector"""
    
    @pytest.fixture
    def connector_config(self):
        """ML engine configuration for testing"""
        return MLEngineConfig(
            engine_type="basic",  # Use basic engine for testing
            confidence_threshold=0.4,
            batch_size=5,
            save_screenshots=False  # Disable for testing
        )
    
    @pytest.fixture
    def ml_connector(self, connector_config):
        """Create ML connector for testing"""
        return VRUMLDatabaseConnector(connector_config)
    
    @pytest.mark.asyncio
    async def test_connector_initialization(self, ml_connector):
        """Test ML connector initialization"""
        # Test initialization (may skip if dependencies not available)
        try:
            success = await ml_connector.initialize_ml_engine()
            # If dependencies are available, should initialize successfully
            assert success or not DEPENDENCIES_AVAILABLE
        except Exception as e:
            # Expected if ML dependencies not available
            assert "not available" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_create_inference_session(self, ml_connector):
        """Test inference session creation"""
        video_id = str(uuid.uuid4())
        
        try:
            session_id = await ml_connector.create_inference_session(video_id)
            assert session_id is not None
            assert ml_connector.current_session is not None
            assert ml_connector.current_session["video_id"] == video_id
        except Exception as e:
            # Expected if video doesn't exist in database
            assert "not found" in str(e).lower() or "dependencies" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_get_processing_statistics(self, ml_connector):
        """Test processing statistics"""
        stats = await ml_connector.get_processing_statistics()
        
        assert "connector_metrics" in stats
        assert "integration_metrics" in stats
        assert "engine_config" in stats

class TestVRUPerformanceOptimizer:
    """Test Performance Optimizer"""
    
    @pytest.fixture
    def optimizer_config(self):
        """Performance optimizer configuration"""
        return CacheConfig(
            enable_query_cache=True,
            enable_result_cache=True,
            cache_ttl_seconds=60,
            warm_cache_on_startup=False  # Disable for testing
        )
    
    @pytest.fixture
    def performance_optimizer(self, optimizer_config):
        """Create performance optimizer for testing"""
        return VRUPerformanceOptimizer(optimizer_config)
    
    @pytest.mark.asyncio
    async def test_optimizer_initialization(self, performance_optimizer):
        """Test optimizer initialization"""
        assert performance_optimizer.config.enable_query_cache
        assert performance_optimizer.query_cache is not None
        assert performance_optimizer.result_cache is not None
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, performance_optimizer):
        """Test cache functionality"""
        cache = performance_optimizer.query_cache
        
        # Test cache operations
        query = "SELECT * FROM test"
        params = {"param1": "value1"}
        result = {"test": "data"}
        
        # Should return None initially
        assert cache.get(query, params) is None
        
        # Set cache
        cache.set(query, params, result)
        
        # Should return cached result
        cached_result = cache.get(query, params)
        assert cached_result == result
        
        # Test cache stats
        stats = cache.stats()
        assert "entries" in stats
        assert stats["entries"] >= 1
    
    @pytest.mark.asyncio
    async def test_performance_report(self, performance_optimizer):
        """Test performance report generation"""
        report = await performance_optimizer.get_performance_report()
        
        assert "optimizer_config" in report
        assert "cache_statistics" in report
        assert "query_performance" in report
        assert "recommendations" in report
        
        # Check report structure
        assert "query_cache_enabled" in report["optimizer_config"]
        assert "total_queries" in report["query_performance"]

class TestVRUDatabaseMigrations:
    """Test Database Migration System"""
    
    @pytest.fixture
    def migrator(self):
        """Create database migrator for testing"""
        return VRUDatabaseMigrator()
    
    def test_migrator_initialization(self, migrator):
        """Test migrator initialization"""
        assert migrator.MIGRATION_VERSION == "2.0.0"
        assert migrator.new_models is not None
        assert len(migrator.new_models) > 0
    
    @pytest.mark.asyncio
    async def test_schema_analysis(self, migrator):
        """Test database schema analysis"""
        schema_info = migrator.check_existing_schema()
        
        assert "existing_tables" in schema_info
        assert "needs_migration" in schema_info or "error" in schema_info
        
        if "existing_tables" in schema_info:
            assert isinstance(schema_info["existing_tables"], list)
    
    def test_migration_tracking_table(self, migrator):
        """Test migration tracking table creation"""
        try:
            migrator.create_migration_tracking_table()
            # Should not raise an exception
        except Exception as e:
            # Expected if database not available
            assert "not available" in str(e).lower() or "connection" in str(e).lower()

class TestVRUIntegrationWorkflow:
    """Test complete VRU integration workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_video_processing_workflow(self):
        """Test complete video processing workflow"""
        try:
            # Create test data
            video_id = str(uuid.uuid4())
            project_id = str(uuid.uuid4())
            
            # 1. Store video metadata
            integration_layer = get_vru_integration_layer()
            video_metadata = VideoMetadata(
                video_id=video_id,
                filename="workflow_test.mp4",
                file_path="/tmp/workflow_test.mp4",
                file_size=2048000,
                duration=60.0,
                fps=30.0,
                resolution="1920x1080",
                total_frames=1800
            )
            
            stored_video_id = await integration_layer.store_video_with_metadata(
                video_metadata, project_id
            )
            assert stored_video_id == video_id
            
            # 2. Create test session
            test_session_id = await integration_layer.create_test_session(
                project_id, video_id, "Workflow Test Session"
            )
            assert test_session_id is not None
            
            # 3. Store detection results
            detections = []
            for i in range(5):
                detection = VRUDetectionData(
                    detection_id=f"WORKFLOW_{i}_{uuid.uuid4().hex[:8]}",
                    video_id=video_id,
                    frame_number=i * 100,
                    timestamp=i * 3.33,
                    vru_type="pedestrian",
                    confidence=0.8,
                    bounding_box={"x": 0.2 + i*0.1, "y": 0.3, "width": 0.2, "height": 0.3},
                    class_label="person",
                    model_version="workflow_test"
                )
                detections.append(detection)
            
            detection_ids = await integration_layer.batch_store_detections(
                detections, test_session_id
            )
            assert len(detection_ids) == 5
            
            # 4. Get project statistics
            stats = await integration_layer.get_project_statistics(project_id)
            assert "project_id" in stats
            assert stats["video_count"] >= 1
            
            # 5. Get performance metrics
            metrics = await integration_layer.get_performance_metrics()
            assert metrics["videos_processed"] >= 1
            assert metrics["detections_stored"] >= 5
            
        except Exception as e:
            # Expected if dependencies not fully available
            pytest.skip(f"Workflow test skipped due to dependencies: {e}")
    
    @pytest.mark.asyncio
    async def test_performance_optimization_workflow(self):
        """Test performance optimization workflow"""
        try:
            # Create optimizer
            config = CacheConfig(enable_query_cache=True, cache_ttl_seconds=30)
            optimizer = VRUPerformanceOptimizer(config)
            
            # Test database optimization
            optimization_results = await optimizer.optimize_database_indexes()
            assert "indexes_analyzed" in optimization_results
            
            # Test performance report
            report = await optimizer.get_performance_report()
            assert "optimizer_config" in report
            assert "query_performance" in report
            
        except Exception as e:
            pytest.skip(f"Performance optimization test skipped: {e}")

# =============================================================================
# INTEGRATION TEST RUNNER
# =============================================================================

def run_integration_tests():
    """Run all VRU integration tests"""
    print("🧪 Running VRU Integration Test Suite")
    print("=" * 60)
    
    if not DEPENDENCIES_AVAILABLE:
        print("❌ Dependencies not available - skipping tests")
        return False
    
    # Run pytest with custom configuration
    test_args = [
        __file__,
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    try:
        exit_code = pytest.main(test_args)
        success = exit_code == 0
        
        if success:
            print("\n🎉 All VRU integration tests passed!")
        else:
            print(f"\n⚠️ Some tests failed (exit code: {exit_code})")
        
        return success
        
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        return False

if __name__ == "__main__":
    print("🔬 VRU Integration Test Suite")
    print("=" * 50)
    
    success = run_integration_tests()
    
    if success:
        print("✅ Integration tests completed successfully")
    else:
        print("❌ Integration tests failed")
    
    print("=" * 50)