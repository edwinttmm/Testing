"""
Comprehensive Test Suite for Project Workflow Management System

SPARC Phase: Testing & Validation
Component: Complete test coverage for project workflow management
Integration: Tests all components with memory coordination
Memory Namespace: vru-project-workflow
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

from project_workflow_manager import (
    ProjectWorkflowManager,
    WorkflowOrchestrator,
    ProgressTracker,
    TestExecutionOrchestrator,
    WorkflowConfiguration,
    LatencyThreshold,
    PassFailCriteria,
    WorkflowState,
    WorkflowPriority,
    ExecutionStrategy,
    WorkflowTask,
    WorkflowProgress,
    TestExecutionPlan
)

from workflow_endpoints import router
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

# Test fixtures
@pytest.fixture
def app():
    """Create FastAPI app for testing"""
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)

@pytest.fixture
def workflow_manager():
    """Create workflow manager instance"""
    return ProjectWorkflowManager()

@pytest.fixture
def orchestrator():
    """Create workflow orchestrator instance"""
    return WorkflowOrchestrator()

@pytest.fixture
def progress_tracker():
    """Create progress tracker instance"""
    return ProgressTracker()

@pytest.fixture
def test_orchestrator():
    """Create test orchestrator instance"""
    return TestExecutionOrchestrator()

@pytest.fixture
def sample_project_data():
    """Sample project data for testing"""
    return {
        "name": "Test VRU Project",
        "description": "Test project for VRU detection validation",
        "camera_model": "Test Camera Model",
        "camera_view": "Front-facing VRU",
        "lens_type": "Standard",
        "resolution": "1920x1080",
        "frame_rate": 30,
        "signal_type": "GPIO",
        "owner_id": "test_user"
    }

@pytest.fixture
def sample_workflow_config():
    """Sample workflow configuration for testing"""
    return WorkflowConfiguration(
        project_id="test_project_123",
        name="Test Workflow",
        description="Test workflow configuration",
        priority=WorkflowPriority.HIGH,
        execution_strategy=ExecutionStrategy.ADAPTIVE,
        max_concurrent_tasks=3,
        timeout_minutes=60,
        retry_attempts=2,
        auto_recovery=True,
        latency_thresholds=LatencyThreshold(
            detection_latency_ms=80.0,
            processing_latency_ms=400.0,
            end_to_end_latency_ms=800.0
        ),
        pass_fail_criteria=PassFailCriteria(
            min_precision=0.95,
            min_recall=0.90,
            min_f1_score=0.92
        )
    )

# Unit Tests for Core Components

class TestWorkflowConfiguration:
    """Test workflow configuration components"""
    
    def test_latency_threshold_creation(self):
        """Test latency threshold creation and conversion"""
        thresholds = LatencyThreshold(
            detection_latency_ms=100.0,
            processing_latency_ms=500.0
        )
        
        assert thresholds.detection_latency_ms == 100.0
        assert thresholds.processing_latency_ms == 500.0
        
        # Test dict conversion
        threshold_dict = thresholds.to_dict()
        assert isinstance(threshold_dict, dict)
        assert threshold_dict["detection_latency_ms"] == 100.0
        
        # Test from dict
        new_thresholds = LatencyThreshold.from_dict(threshold_dict)
        assert new_thresholds.detection_latency_ms == 100.0

    def test_pass_fail_criteria_creation(self):
        """Test pass/fail criteria creation and conversion"""
        criteria = PassFailCriteria(
            min_precision=0.90,
            min_recall=0.85,
            max_latency_ms=100.0
        )
        
        assert criteria.min_precision == 0.90
        assert criteria.min_recall == 0.85
        assert criteria.max_latency_ms == 100.0
        
        # Test dict conversion
        criteria_dict = criteria.to_dict()
        assert isinstance(criteria_dict, dict)
        
        # Test from dict
        new_criteria = PassFailCriteria.from_dict(criteria_dict)
        assert new_criteria.min_precision == 0.90

    def test_workflow_configuration_creation(self, sample_workflow_config):
        """Test workflow configuration creation"""
        config = sample_workflow_config
        
        assert config.project_id == "test_project_123"
        assert config.name == "Test Workflow"
        assert config.priority == WorkflowPriority.HIGH
        assert config.execution_strategy == ExecutionStrategy.ADAPTIVE
        assert config.max_concurrent_tasks == 3
        assert config.auto_recovery is True
        assert isinstance(config.latency_thresholds, LatencyThreshold)
        assert isinstance(config.pass_fail_criteria, PassFailCriteria)

class TestProgressTracker:
    """Test progress tracking functionality"""
    
    def test_track_progress(self, progress_tracker):
        """Test progress tracking"""
        project_id = "test_project_123"
        component = "video_assignment"
        progress = 75.0
        metadata = {"assigned_videos": 15}
        
        progress_tracker.track_progress(project_id, component, progress, metadata)
        
        # Verify progress was stored
        key = f"{project_id}:{component}"
        assert key in progress_tracker.memory_store
        
        progress_data = progress_tracker.memory_store[key]
        assert progress_data["project_id"] == project_id
        assert progress_data["component"] == component
        assert progress_data["progress"] == progress
        assert progress_data["metadata"] == metadata

    def test_get_overall_progress(self, progress_tracker):
        """Test overall progress calculation"""
        project_id = "test_project_123"
        
        # Track progress for multiple components
        progress_tracker.track_progress(project_id, "video_assignment", 100.0)
        progress_tracker.track_progress(project_id, "ground_truth", 50.0)
        progress_tracker.track_progress(project_id, "test_execution", 25.0)
        
        overall_progress = progress_tracker.get_overall_progress(project_id)
        
        assert overall_progress["project_id"] == project_id
        assert overall_progress["overall_progress"] == (100.0 + 50.0 + 25.0) / 3
        assert len(overall_progress["components"]) == 3
        assert "video_assignment" in overall_progress["components"]
        assert "ground_truth" in overall_progress["components"]
        assert "test_execution" in overall_progress["components"]

    def test_progress_callbacks(self, progress_tracker):
        """Test progress callbacks"""
        callback_called = False
        callback_data = None
        
        def test_callback(data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = data
        
        progress_tracker.progress_callbacks.append(test_callback)
        
        project_id = "test_project_123"
        progress_tracker.track_progress(project_id, "test_component", 50.0)
        
        assert callback_called is True
        assert callback_data is not None
        assert callback_data["project_id"] == project_id
        assert callback_data["progress"] == 50.0

class TestWorkflowOrchestrator:
    """Test workflow orchestration functionality"""
    
    def test_task_registry(self, orchestrator):
        """Test built-in task registry"""
        assert "project_validation" in orchestrator.task_registry
        assert "resource_allocation" in orchestrator.task_registry
        assert "video_assignment" in orchestrator.task_registry
        assert "test_execution" in orchestrator.task_registry
        assert "cleanup" in orchestrator.task_registry
        
        # Test task function is callable
        task_func = orchestrator.task_registry["project_validation"]
        assert callable(task_func)

    def test_get_default_tasks(self, orchestrator):
        """Test default task creation"""
        tasks = orchestrator._get_default_tasks()
        
        assert len(tasks) >= 8  # Should have at least 8 default tasks
        assert all(isinstance(task, WorkflowTask) for task in tasks)
        
        # Check specific tasks exist
        task_names = [task.name for task in tasks]
        assert "Project Validation" in task_names
        assert "Resource Allocation" in task_names
        assert "Video Assignment" in task_names
        assert "Test Execution" in task_names

    @pytest.mark.asyncio
    async def test_execute_workflow(self, orchestrator, sample_workflow_config):
        """Test workflow execution"""
        # Mock the internal execution methods to avoid actual work
        orchestrator._execute_adaptive_workflow = AsyncMock()
        
        workflow_id = await orchestrator.execute_workflow(sample_workflow_config)
        
        assert isinstance(workflow_id, str)
        assert workflow_id in orchestrator.active_workflows
        
        progress = orchestrator.active_workflows[workflow_id]
        assert isinstance(progress, WorkflowProgress)
        assert progress.workflow_id == workflow_id
        assert progress.current_state == WorkflowState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_task(self, orchestrator, sample_workflow_config):
        """Test individual task execution"""
        task = WorkflowTask(
            task_id="test_task",
            name="Test Task",
            description="Test task description",
            task_type="project_validation"
        )
        
        # This should not raise an exception
        await orchestrator._execute_task(task, sample_workflow_config)

class TestTestExecutionOrchestrator:
    """Test test execution orchestration"""
    
    def test_create_execution_plan(self, test_orchestrator, sample_workflow_config):
        """Test execution plan creation"""
        project_id = "test_project_123"
        
        # Mock database query
        with patch('project_workflow_manager.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.__enter__ = Mock(return_value=mock_db)
            mock_db.__exit__ = Mock(return_value=None)
            
            # Mock test sessions
            mock_test_sessions = [
                Mock(id="session_1", created_at=datetime.utcnow()),
                Mock(id="session_2", created_at=datetime.utcnow())
            ]
            mock_db.query.return_value.filter.return_value.all.return_value = mock_test_sessions
            
            plan = test_orchestrator.create_execution_plan(project_id, sample_workflow_config)
            
            assert isinstance(plan, TestExecutionPlan)
            assert plan.project_id == project_id
            assert len(plan.test_sessions) == 2
            assert "session_1" in plan.test_sessions
            assert "session_2" in plan.test_sessions

    def test_determine_execution_order(self, test_orchestrator):
        """Test execution order determination"""
        mock_sessions = [
            Mock(id="session_2", created_at=datetime.utcnow() + timedelta(minutes=1)),
            Mock(id="session_1", created_at=datetime.utcnow()),
            Mock(id="session_3", created_at=datetime.utcnow() + timedelta(minutes=2))
        ]
        
        order = test_orchestrator._determine_execution_order(mock_sessions)
        
        # Should be ordered by creation time
        assert order == ["session_1", "session_2", "session_3"]

    def test_estimate_resource_requirements(self, test_orchestrator, sample_workflow_config):
        """Test resource requirement estimation"""
        mock_sessions = [Mock() for _ in range(3)]
        
        requirements = test_orchestrator._estimate_resource_requirements(
            mock_sessions, sample_workflow_config
        )
        
        assert isinstance(requirements, dict)
        assert "cpu_cores" in requirements
        assert "memory_gb" in requirements
        assert "disk_gb" in requirements
        assert requirements["cpu_cores"] <= sample_workflow_config.max_concurrent_tasks

    @pytest.mark.asyncio
    async def test_execute_single_test(self, test_orchestrator, sample_workflow_config):
        """Test single test execution"""
        session_id = "test_session_123"
        
        # Mock database query
        with patch('project_workflow_manager.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.__enter__ = Mock(return_value=mock_db)
            mock_db.__exit__ = Mock(return_value=None)
            
            mock_test_session = Mock(id=session_id)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_test_session
            
            result = await test_orchestrator._execute_single_test(session_id, sample_workflow_config)
            
            assert isinstance(result, dict)
            assert result["session_id"] == session_id
            assert result["success"] is True
            assert "metrics" in result
            assert "duration" in result

class TestProjectWorkflowManager:
    """Test main project workflow manager"""
    
    def test_initialization(self, workflow_manager):
        """Test workflow manager initialization"""
        assert hasattr(workflow_manager, 'project_manager')
        assert hasattr(workflow_manager, 'orchestrator')
        assert hasattr(workflow_manager, 'progress_tracker')
        assert hasattr(workflow_manager, 'test_orchestrator')
        assert workflow_manager.memory_namespace == "vru-project-workflow"

    @pytest.mark.asyncio
    async def test_create_project_workflow(self, workflow_manager, sample_project_data):
        """Test project workflow creation"""
        # Mock the project manager
        with patch.object(workflow_manager.project_manager, 'create_project_with_criteria') as mock_create:
            with patch.object(workflow_manager.orchestrator, 'execute_workflow') as mock_execute:
                mock_create.return_value = "test_project_123"
                mock_execute.return_value = "test_workflow_123"
                
                result = await workflow_manager.create_project_workflow(sample_project_data)
                
                assert isinstance(result, dict)
                assert result["project_id"] == "test_project_123"
                assert result["workflow_id"] == "test_workflow_123"
                assert result["status"] == "created"

    def test_configure_latency_thresholds(self, workflow_manager):
        """Test latency threshold configuration"""
        project_id = "test_project_123"
        thresholds = LatencyThreshold(
            detection_latency_ms=90.0,
            processing_latency_ms=450.0
        )
        
        success = workflow_manager.configure_latency_thresholds(project_id, thresholds)
        
        assert success is True
        
        # Verify stored in memory
        key = f"latency_thresholds:{project_id}"
        stored_data = workflow_manager._load_from_memory(key)
        assert stored_data is not None
        assert stored_data["detection_latency_ms"] == 90.0

    def test_get_project_status(self, workflow_manager):
        """Test project status retrieval"""
        project_id = "test_project_123"
        
        # Mock project manager get_project_progress
        with patch.object(workflow_manager.project_manager, 'get_project_progress') as mock_progress:
            mock_progress.return_value = {"project_id": project_id, "status": "active"}
            
            status = workflow_manager.get_project_status(project_id)
            
            assert isinstance(status, dict)
            assert status["project_id"] == project_id
            assert "basic_progress" in status
            assert "detailed_progress" in status

    def test_update_workflow_status(self, workflow_manager):
        """Test workflow status update"""
        project_id = "test_project_123"
        status = WorkflowState.EXECUTION
        metadata = {"current_task": "test_execution"}
        
        success = workflow_manager.update_workflow_status(project_id, status, metadata)
        
        assert success is True
        
        # Verify stored in memory
        key = f"workflow_status:{project_id}"
        stored_data = workflow_manager._load_from_memory(key)
        assert stored_data is not None
        assert stored_data["status"] == status.value
        assert stored_data["metadata"] == metadata

    def test_memory_coordination(self, workflow_manager):
        """Test memory coordination functionality"""
        key = "test_key"
        data = {"test": "data", "number": 123}
        
        # Test store
        workflow_manager._store_in_memory(key, data)
        
        # Test load
        loaded_data = workflow_manager._load_from_memory(key)
        assert loaded_data == data
        
        # Test non-existent key
        non_existent = workflow_manager._load_from_memory("non_existent_key")
        assert non_existent is None

# Integration Tests for API Endpoints

class TestWorkflowEndpoints:
    """Test FastAPI endpoints for workflow management"""
    
    def test_create_project_workflow_endpoint(self, client, sample_project_data):
        """Test project creation endpoint"""
        with patch('workflow_endpoints.workflow_api.create_project_endpoint') as mock_create:
            mock_create.return_value = {
                "success": True,
                "data": {
                    "project_id": "test_project_123",
                    "workflow_id": "test_workflow_123"
                },
                "message": "Project workflow created successfully"
            }
            
            response = client.post("/api/v1/workflow/projects/create", json=sample_project_data)
            
            assert response.status_code == 201
            result = response.json()
            assert result["success"] is True
            assert result["project_id"] == "test_project_123"
            assert result["workflow_id"] == "test_workflow_123"

    def test_get_project_status_endpoint(self, client):
        """Test project status endpoint"""
        project_id = "test_project_123"
        
        with patch('workflow_endpoints.workflow_api.get_status_endpoint') as mock_status:
            mock_status.return_value = {
                "success": True,
                "data": {
                    "project_id": project_id,
                    "progress": 75.0,
                    "status": "active"
                },
                "message": "Status retrieved successfully"
            }
            
            response = client.get(f"/api/v1/workflow/projects/{project_id}/status")
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["project_id"] == project_id

    def test_configure_latency_thresholds_endpoint(self, client):
        """Test latency threshold configuration endpoint"""
        project_id = "test_project_123"
        thresholds = {
            "detection_latency_ms": 90.0,
            "processing_latency_ms": 450.0,
            "end_to_end_latency_ms": 900.0
        }
        
        with patch('workflow_endpoints.workflow_api.configure_latency_endpoint') as mock_config:
            mock_config.return_value = {
                "success": True,
                "data": {
                    "project_id": project_id,
                    "thresholds": thresholds
                },
                "message": "Latency thresholds configured successfully"
            }
            
            response = client.post(
                f"/api/v1/workflow/projects/{project_id}/latency-thresholds",
                json=thresholds
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["project_id"] == project_id

    def test_execute_tests_endpoint(self, client):
        """Test test execution endpoint"""
        request_data = {
            "project_id": "test_project_123",
            "force_restart": False
        }
        
        with patch('workflow_endpoints.workflow_api.execute_tests_endpoint') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "data": {
                    "execution_id": "exec_123",
                    "project_id": "test_project_123",
                    "estimated_duration": "30 minutes"
                },
                "message": "Tests executed successfully"
            }
            
            response = client.post("/api/v1/workflow/tests/execute", json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["execution_id"] == "exec_123"

    def test_health_check_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/v1/workflow/health")
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "health" in result

    def test_get_active_workflows_endpoint(self, client):
        """Test active workflows endpoint"""
        response = client.get("/api/v1/workflow/workflows/active")
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "active_workflows" in result

    def test_assign_videos_endpoint(self, client):
        """Test video assignment endpoint"""
        project_id = "test_project_123"
        request_data = {
            "project_id": project_id,
            "video_ids": ["video_1", "video_2"]
        }
        
        with patch('workflow_endpoints.workflow_manager') as mock_manager:
            mock_assignment = Mock()
            mock_assignment.video_id = "video_1"
            mock_assignment.project_id = project_id
            mock_assignment.compatibility_score = 0.95
            mock_assignment.assigned_at = datetime.utcnow()
            mock_assignment.assignment_reason = "High compatibility"
            
            mock_manager.assign_videos_intelligently.return_value = [mock_assignment]
            
            response = client.post(
                f"/api/v1/workflow/projects/{project_id}/assign-videos",
                json=request_data
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert len(result["assignments"]) == 1

    def test_update_workflow_status_endpoint(self, client):
        """Test workflow status update endpoint"""
        project_id = "test_project_123"
        request_data = {
            "project_id": project_id,
            "status": "execution",
            "metadata": {"current_task": "test_execution"}
        }
        
        with patch('workflow_endpoints.workflow_manager') as mock_manager:
            mock_manager.update_workflow_status.return_value = True
            
            response = client.put(
                f"/api/v1/workflow/projects/{project_id}/workflow-status",
                json=request_data
            )
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["status"] == "execution"

    def test_get_project_progress_endpoint(self, client):
        """Test project progress endpoint"""
        project_id = "test_project_123"
        
        with patch('workflow_endpoints.workflow_manager') as mock_manager:
            mock_progress = {
                "project_id": project_id,
                "overall_progress": 75.0,
                "components": {
                    "video_assignment": {"progress": 100.0},
                    "test_execution": {"progress": 50.0}
                }
            }
            mock_manager.progress_tracker.get_overall_progress.return_value = mock_progress
            
            response = client.get(f"/api/v1/workflow/projects/{project_id}/progress")
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["progress"]["overall_progress"] == 75.0

# Performance and Load Tests

class TestWorkflowPerformance:
    """Test workflow system performance"""
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_execution(self, orchestrator):
        """Test concurrent workflow execution"""
        num_workflows = 5
        configs = []
        
        for i in range(num_workflows):
            config = WorkflowConfiguration(
                project_id=f"project_{i}",
                name=f"Workflow {i}",
                execution_strategy=ExecutionStrategy.PARALLEL,
                max_concurrent_tasks=2
            )
            configs.append(config)
        
        # Mock execution methods
        orchestrator._execute_parallel_workflow = AsyncMock()
        
        # Execute workflows concurrently
        tasks = [orchestrator.execute_workflow(config) for config in configs]
        workflow_ids = await asyncio.gather(*tasks)
        
        assert len(workflow_ids) == num_workflows
        assert len(orchestrator.active_workflows) == num_workflows

    def test_memory_performance(self, workflow_manager):
        """Test memory system performance"""
        import time
        
        # Store many items
        start_time = time.time()
        for i in range(1000):
            key = f"test_key_{i}"
            data = {"index": i, "data": f"test_data_{i}"}
            workflow_manager._store_in_memory(key, data)
        store_time = time.time() - start_time
        
        # Retrieve many items
        start_time = time.time()
        for i in range(1000):
            key = f"test_key_{i}"
            data = workflow_manager._load_from_memory(key)
            assert data is not None
            assert data["index"] == i
        load_time = time.time() - start_time
        
        # Performance should be reasonable (less than 1 second for 1000 operations)
        assert store_time < 1.0
        assert load_time < 1.0

    @pytest.mark.asyncio
    async def test_progress_tracking_performance(self, progress_tracker):
        """Test progress tracking performance"""
        import time
        
        project_ids = [f"project_{i}" for i in range(100)]
        components = ["video_assignment", "ground_truth", "test_execution", "analysis"]
        
        start_time = time.time()
        
        for project_id in project_ids:
            for component in components:
                progress_tracker.track_progress(project_id, component, 50.0)
        
        tracking_time = time.time() - start_time
        
        # Get overall progress for all projects
        start_time = time.time()
        for project_id in project_ids:
            progress = progress_tracker.get_overall_progress(project_id)
            assert progress["overall_progress"] == 50.0
        
        retrieval_time = time.time() - start_time
        
        # Performance should be reasonable
        assert tracking_time < 2.0
        assert retrieval_time < 2.0

# Error Handling Tests

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_workflow_execution_failure(self, orchestrator, sample_workflow_config):
        """Test workflow execution failure handling"""
        # Mock execution method to raise exception
        orchestrator._execute_adaptive_workflow = AsyncMock(side_effect=Exception("Test error"))
        
        with pytest.raises(Exception, match="Test error"):
            await orchestrator.execute_workflow(sample_workflow_config)
        
        # Should still track the workflow
        assert len(orchestrator.active_workflows) == 1
        workflow_id = list(orchestrator.active_workflows.keys())[0]
        progress = orchestrator.active_workflows[workflow_id]
        assert progress.current_state == WorkflowState.FAILED

    def test_invalid_project_data(self, workflow_manager):
        """Test handling of invalid project data"""
        invalid_data = {}  # Missing required fields
        
        with pytest.raises((ValueError, KeyError)):
            # This should fail due to missing required fields
            workflow_manager.project_manager.create_project_with_criteria(invalid_data)

    def test_nonexistent_project_status(self, workflow_manager):
        """Test getting status for non-existent project"""
        status = workflow_manager.get_project_status("non_existent_project")
        
        assert isinstance(status, dict)
        assert "error" in status

    def test_invalid_latency_thresholds(self, workflow_manager):
        """Test invalid latency threshold configuration"""
        project_id = "test_project_123"
        
        # Test with invalid threshold values
        invalid_thresholds = LatencyThreshold(detection_latency_ms=-10.0)  # Negative value
        
        # This should still work (the validation would be in the API layer)
        success = workflow_manager.configure_latency_thresholds(project_id, invalid_thresholds)
        assert success is True

# Integration with Memory Coordination

class TestMemoryCoordination:
    """Test memory coordination functionality"""
    
    def test_memory_namespace_isolation(self, workflow_manager):
        """Test that memory namespace provides isolation"""
        key = "test_key"
        data1 = {"source": "workflow_manager"}
        data2 = {"source": "other_system"}
        
        # Store in workflow manager (with namespace)
        workflow_manager._store_in_memory(key, data1)
        
        # Manually store without namespace
        workflow_manager._memory_store[key] = data2
        
        # Should get namespace-isolated data
        retrieved = workflow_manager._load_from_memory(key)
        assert retrieved == data1
        assert retrieved != data2

    @pytest.mark.asyncio
    async def test_workflow_config_persistence(self, workflow_manager, sample_workflow_config):
        """Test workflow configuration persistence in memory"""
        project_id = "test_project_123"
        config = sample_workflow_config
        config.project_id = project_id
        
        # Store configuration
        await workflow_manager._store_workflow_config(project_id, config)
        
        # Load configuration
        loaded_config = await workflow_manager._load_workflow_config(project_id)
        
        assert loaded_config.project_id == project_id
        assert loaded_config.name == config.name
        assert loaded_config.priority == config.priority
        assert loaded_config.execution_strategy == config.execution_strategy

    @pytest.mark.asyncio
    async def test_test_results_storage(self, workflow_manager):
        """Test test results storage in memory"""
        project_id = "test_project_123"
        results = {
            "execution_id": "exec_123",
            "project_id": project_id,
            "success": True,
            "metrics": {"precision": 0.95, "recall": 0.90}
        }
        
        # Store results
        await workflow_manager._store_test_results(project_id, results)
        
        # Verify storage
        key = f"test_results:{project_id}"
        stored_results = workflow_manager._load_from_memory(key)
        
        assert stored_results == results
        assert stored_results["execution_id"] == "exec_123"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])