"""
Project Workflow Management System
Comprehensive workflow orchestration for AI model validation projects

SPARC Phase: Implementation
Component: Complete Project Lifecycle Management
Integration: Coordinates all system components via shared memory
Memory Namespace: vru-project-workflow
"""

from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid
import asyncio
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

# Core imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, get_db
from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject
from services.project_management_service import (
    ProjectManager, VideoAssignmentSystem, PassFailCriteriaEngine, 
    ResourceAllocationManager, ProjectStatus, TestVerdict, PassFailCriteria,
    TestResults, Assignment
)

logger = logging.getLogger(__name__)

class WorkflowState(Enum):
    """Comprehensive workflow states"""
    INITIALIZED = "initialized"
    PLANNING = "planning"
    RESOURCE_ALLOCATION = "resource_allocation"
    VIDEO_ASSIGNMENT = "video_assignment"
    GROUND_TRUTH_GENERATION = "ground_truth_generation"
    TEST_CONFIGURATION = "test_configuration"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class WorkflowPriority(Enum):
    """Workflow execution priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class ExecutionStrategy(Enum):
    """Workflow execution strategies"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"

@dataclass
class LatencyThreshold:
    """Latency threshold configuration"""
    detection_latency_ms: float = 100.0
    processing_latency_ms: float = 500.0
    end_to_end_latency_ms: float = 1000.0
    signal_processing_latency_ms: float = 50.0
    warning_threshold_ms: float = 80.0
    critical_threshold_ms: float = 150.0
    
    def to_dict(self) -> Dict:
        return {
            "detection_latency_ms": self.detection_latency_ms,
            "processing_latency_ms": self.processing_latency_ms,
            "end_to_end_latency_ms": self.end_to_end_latency_ms,
            "signal_processing_latency_ms": self.signal_processing_latency_ms,
            "warning_threshold_ms": self.warning_threshold_ms,
            "critical_threshold_ms": self.critical_threshold_ms
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LatencyThreshold':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class WorkflowConfiguration:
    """Complete workflow configuration"""
    project_id: str
    name: str
    description: str = ""
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    execution_strategy: ExecutionStrategy = ExecutionStrategy.ADAPTIVE
    max_concurrent_tasks: int = 5
    timeout_minutes: int = 120
    retry_attempts: int = 3
    auto_recovery: bool = True
    latency_thresholds: LatencyThreshold = field(default_factory=LatencyThreshold)
    pass_fail_criteria: PassFailCriteria = field(default_factory=PassFailCriteria)
    notification_config: Dict[str, Any] = field(default_factory=dict)
    custom_parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowTask:
    """Individual workflow task definition"""
    task_id: str
    name: str
    description: str
    task_type: str
    dependencies: List[str] = field(default_factory=list)
    estimated_duration_minutes: int = 30
    max_retries: int = 3
    timeout_minutes: int = 60
    required_resources: Dict[str, Any] = field(default_factory=dict)
    validation_criteria: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowProgress:
    """Comprehensive progress tracking"""
    workflow_id: str
    current_state: WorkflowState
    progress_percentage: float
    tasks_completed: int
    tasks_total: int
    current_task: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TestExecutionPlan:
    """Comprehensive test execution plan"""
    project_id: str
    test_sessions: List[str]
    execution_order: List[str]
    parallel_groups: List[List[str]]
    resource_requirements: Dict[str, Any]
    estimated_duration: timedelta
    success_criteria: Dict[str, Any]
    failure_handling: Dict[str, Any]

class WorkflowOrchestrator:
    """Advanced workflow orchestration engine"""
    
    def __init__(self):
        self.active_workflows: Dict[str, WorkflowProgress] = {}
        self.task_registry: Dict[str, Callable] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._register_built_in_tasks()
    
    def _register_built_in_tasks(self):
        """Register built-in workflow tasks"""
        self.task_registry.update({
            "project_validation": self._validate_project_task,
            "resource_allocation": self._allocate_resources_task,
            "video_assignment": self._assign_videos_task,
            "ground_truth_generation": self._generate_ground_truth_task,
            "test_configuration": self._configure_tests_task,
            "test_execution": self._execute_tests_task,
            "result_analysis": self._analyze_results_task,
            "report_generation": self._generate_report_task,
            "cleanup": self._cleanup_task
        })
    
    async def execute_workflow(self, config: WorkflowConfiguration) -> str:
        """Execute complete workflow with orchestration"""
        workflow_id = str(uuid.uuid4())
        
        # Initialize progress tracking
        progress = WorkflowProgress(
            workflow_id=workflow_id,
            current_state=WorkflowState.INITIALIZED,
            progress_percentage=0.0,
            tasks_completed=0,
            tasks_total=len(self._get_default_tasks())
        )
        
        self.active_workflows[workflow_id] = progress
        
        try:
            # Execute workflow based on strategy
            if config.execution_strategy == ExecutionStrategy.SEQUENTIAL:
                await self._execute_sequential_workflow(workflow_id, config)
            elif config.execution_strategy == ExecutionStrategy.PARALLEL:
                await self._execute_parallel_workflow(workflow_id, config)
            elif config.execution_strategy == ExecutionStrategy.ADAPTIVE:
                await self._execute_adaptive_workflow(workflow_id, config)
            else:
                await self._execute_hybrid_workflow(workflow_id, config)
            
            # Mark as completed
            progress.current_state = WorkflowState.COMPLETED
            progress.progress_percentage = 100.0
            
        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {str(e)}")
            progress.current_state = WorkflowState.FAILED
            progress.errors.append(str(e))
            raise
        
        return workflow_id
    
    async def _execute_sequential_workflow(self, workflow_id: str, config: WorkflowConfiguration):
        """Execute workflow tasks sequentially"""
        tasks = self._get_default_tasks()
        progress = self.active_workflows[workflow_id]
        
        for i, task in enumerate(tasks):
            try:
                progress.current_task = task.name
                progress.current_state = WorkflowState(task.task_type.lower())
                
                # Execute task
                await self._execute_task(task, config)
                
                # Update progress
                progress.tasks_completed = i + 1
                progress.progress_percentage = (i + 1) / len(tasks) * 100
                progress.last_update = datetime.utcnow()
                
            except Exception as e:
                if config.auto_recovery and task.max_retries > 0:
                    await self._retry_task(task, config, task.max_retries)
                else:
                    raise
    
    async def _execute_parallel_workflow(self, workflow_id: str, config: WorkflowConfiguration):
        """Execute workflow tasks in parallel where possible"""
        tasks = self._get_default_tasks()
        progress = self.active_workflows[workflow_id]
        
        # Group tasks by dependencies
        task_groups = self._group_tasks_by_dependencies(tasks)
        
        for group in task_groups:
            # Execute group in parallel
            futures = []
            for task in group:
                future = asyncio.create_task(self._execute_task(task, config))
                futures.append(future)
            
            # Wait for group completion
            await asyncio.gather(*futures)
            
            # Update progress
            completed_tasks = sum(len(g) for g in task_groups[:task_groups.index(group) + 1])
            progress.tasks_completed = completed_tasks
            progress.progress_percentage = completed_tasks / len(tasks) * 100
            progress.last_update = datetime.utcnow()
    
    async def _execute_adaptive_workflow(self, workflow_id: str, config: WorkflowConfiguration):
        """Adaptively choose execution strategy based on conditions"""
        # Analyze project complexity and choose strategy
        complexity_score = await self._analyze_project_complexity(config.project_id)
        
        if complexity_score < 0.3:
            await self._execute_sequential_workflow(workflow_id, config)
        elif complexity_score > 0.7:
            await self._execute_parallel_workflow(workflow_id, config)
        else:
            await self._execute_hybrid_workflow(workflow_id, config)
    
    async def _execute_hybrid_workflow(self, workflow_id: str, config: WorkflowConfiguration):
        """Execute workflow using hybrid approach"""
        # Critical tasks sequential, independent tasks parallel
        critical_tasks = self._get_critical_tasks()
        independent_tasks = self._get_independent_tasks()
        
        # Execute critical tasks first
        for task in critical_tasks:
            await self._execute_task(task, config)
        
        # Execute independent tasks in parallel
        if independent_tasks:
            futures = [self._execute_task(task, config) for task in independent_tasks]
            await asyncio.gather(*futures)
    
    def _get_default_tasks(self) -> List[WorkflowTask]:
        """Get default workflow tasks"""
        return [
            WorkflowTask("validate", "Project Validation", "Validate project configuration", "project_validation"),
            WorkflowTask("allocate", "Resource Allocation", "Allocate system resources", "resource_allocation", ["validate"]),
            WorkflowTask("assign", "Video Assignment", "Assign videos to project", "video_assignment", ["allocate"]),
            WorkflowTask("ground_truth", "Ground Truth Generation", "Generate ground truth data", "ground_truth_generation", ["assign"]),
            WorkflowTask("configure", "Test Configuration", "Configure test parameters", "test_configuration", ["ground_truth"]),
            WorkflowTask("execute", "Test Execution", "Execute validation tests", "test_execution", ["configure"]),
            WorkflowTask("analyze", "Result Analysis", "Analyze test results", "result_analysis", ["execute"]),
            WorkflowTask("report", "Report Generation", "Generate final report", "report_generation", ["analyze"]),
            WorkflowTask("cleanup", "Cleanup", "Clean up resources", "cleanup", ["report"])
        ]
    
    async def _execute_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Execute individual workflow task"""
        if task.task_type in self.task_registry:
            task_func = self.task_registry[task.task_type]
            await task_func(task, config)
        else:
            logger.warning(f"Task type {task.task_type} not registered")
    
    # Built-in task implementations
    async def _validate_project_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Validate project configuration"""
        logger.info(f"Validating project {config.project_id}")
        # Implementation would validate project setup
    
    async def _allocate_resources_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Allocate system resources"""
        logger.info(f"Allocating resources for project {config.project_id}")
        # Implementation would allocate resources
    
    async def _assign_videos_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Assign videos to project"""
        logger.info(f"Assigning videos for project {config.project_id}")
        # Implementation would assign videos
    
    async def _generate_ground_truth_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Generate ground truth data"""
        logger.info(f"Generating ground truth for project {config.project_id}")
        # Implementation would generate ground truth
    
    async def _configure_tests_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Configure test parameters"""
        logger.info(f"Configuring tests for project {config.project_id}")
        # Implementation would configure tests
    
    async def _execute_tests_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Execute validation tests"""
        logger.info(f"Executing tests for project {config.project_id}")
        # Implementation would execute tests
    
    async def _analyze_results_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Analyze test results"""
        logger.info(f"Analyzing results for project {config.project_id}")
        # Implementation would analyze results
    
    async def _generate_report_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Generate final report"""
        logger.info(f"Generating report for project {config.project_id}")
        # Implementation would generate report
    
    async def _cleanup_task(self, task: WorkflowTask, config: WorkflowConfiguration):
        """Clean up resources"""
        logger.info(f"Cleaning up resources for project {config.project_id}")
        # Implementation would clean up resources

class ProgressTracker:
    """Advanced progress tracking system"""
    
    def __init__(self):
        self.memory_store: Dict[str, Any] = {}
        self.progress_callbacks: List[Callable] = []
    
    def track_progress(self, project_id: str, component: str, progress: float, 
                      metadata: Optional[Dict] = None):
        """Track component progress"""
        key = f"{project_id}:{component}"
        
        progress_data = {
            "project_id": project_id,
            "component": component,
            "progress": progress,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        self.memory_store[key] = progress_data
        
        # Trigger callbacks
        for callback in self.progress_callbacks:
            try:
                callback(progress_data)
            except Exception as e:
                logger.error(f"Progress callback error: {str(e)}")
    
    def get_overall_progress(self, project_id: str) -> Dict[str, Any]:
        """Get overall project progress"""
        project_keys = [k for k in self.memory_store.keys() if k.startswith(f"{project_id}:")]
        
        if not project_keys:
            return {"project_id": project_id, "overall_progress": 0.0, "components": {}}
        
        component_progress = {}
        total_progress = 0.0
        
        for key in project_keys:
            data = self.memory_store[key]
            component_progress[data["component"]] = data
            total_progress += data["progress"]
        
        overall_progress = total_progress / len(project_keys)
        
        return {
            "project_id": project_id,
            "overall_progress": overall_progress,
            "components": component_progress,
            "last_update": max(data["timestamp"] for data in component_progress.values())
        }

class TestExecutionOrchestrator:
    """Comprehensive test execution orchestration"""
    
    def __init__(self):
        self.progress_tracker = ProgressTracker()
    
    def create_execution_plan(self, project_id: str, config: WorkflowConfiguration) -> TestExecutionPlan:
        """Create comprehensive test execution plan"""
        db = SessionLocal()
        try:
            # Get test sessions for project
            test_sessions = db.query(TestSession).filter(
                TestSession.project_id == project_id
            ).all()
            
            if not test_sessions:
                raise ValueError(f"No test sessions found for project {project_id}")
            
            # Analyze dependencies and create execution order
            execution_order = self._determine_execution_order(test_sessions)
            parallel_groups = self._identify_parallel_groups(test_sessions, execution_order)
            
            # Estimate resource requirements
            resource_requirements = self._estimate_resource_requirements(test_sessions, config)
            
            # Calculate estimated duration
            estimated_duration = self._estimate_execution_duration(test_sessions, parallel_groups)
            
            plan = TestExecutionPlan(
                project_id=project_id,
                test_sessions=[ts.id for ts in test_sessions],
                execution_order=execution_order,
                parallel_groups=parallel_groups,
                resource_requirements=resource_requirements,
                estimated_duration=estimated_duration,
                success_criteria=self._define_success_criteria(config),
                failure_handling=self._define_failure_handling(config)
            )
            
            return plan
            
        finally:
            db.close()
    
    async def execute_test_plan(self, plan: TestExecutionPlan, config: WorkflowConfiguration) -> Dict[str, Any]:
        """Execute comprehensive test plan"""
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            # Initialize execution tracking
            self.progress_tracker.track_progress(
                plan.project_id, "test_execution", 0.0,
                {"execution_id": execution_id, "start_time": start_time}
            )
            
            results = {}
            
            if config.execution_strategy == ExecutionStrategy.PARALLEL:
                results = await self._execute_parallel_tests(plan, config)
            else:
                results = await self._execute_sequential_tests(plan, config)
            
            # Calculate final metrics
            end_time = datetime.utcnow()
            duration = end_time - start_time
            
            final_results = {
                "execution_id": execution_id,
                "project_id": plan.project_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "test_results": results,
                "success": self._evaluate_overall_success(results, plan.success_criteria),
                "performance_metrics": self._calculate_performance_metrics(results, duration)
            }
            
            # Update final progress
            self.progress_tracker.track_progress(
                plan.project_id, "test_execution", 100.0,
                {"execution_id": execution_id, "completed": True, "results": final_results}
            )
            
            return final_results
            
        except Exception as e:
            logger.error(f"Test execution failed: {str(e)}")
            self.progress_tracker.track_progress(
                plan.project_id, "test_execution", 0.0,
                {"execution_id": execution_id, "failed": True, "error": str(e)}
            )
            raise
    
    def _determine_execution_order(self, test_sessions: List) -> List[str]:
        """Determine optimal test execution order"""
        # Simple implementation - would be enhanced with dependency analysis
        return [ts.id for ts in sorted(test_sessions, key=lambda x: x.created_at)]
    
    def _identify_parallel_groups(self, test_sessions: List, execution_order: List[str]) -> List[List[str]]:
        """Identify tests that can run in parallel"""
        # Simple implementation - would analyze dependencies
        return [[session_id] for session_id in execution_order]
    
    def _estimate_resource_requirements(self, test_sessions: List, config: WorkflowConfiguration) -> Dict[str, Any]:
        """Estimate resource requirements for test execution"""
        return {
            "cpu_cores": min(config.max_concurrent_tasks, len(test_sessions)),
            "memory_gb": len(test_sessions) * 2,  # 2GB per test session
            "disk_gb": len(test_sessions) * 10,   # 10GB per test session
            "gpu_required": any(getattr(ts, 'requires_gpu', False) for ts in test_sessions)
        }
    
    def _estimate_execution_duration(self, test_sessions: List, parallel_groups: List[List[str]]) -> timedelta:
        """Estimate total execution duration"""
        # Simple estimation - would be enhanced with historical data
        avg_duration_minutes = 30  # Average test duration
        total_groups = len(parallel_groups)
        return timedelta(minutes=total_groups * avg_duration_minutes)
    
    async def _execute_parallel_tests(self, plan: TestExecutionPlan, config: WorkflowConfiguration) -> Dict[str, Any]:
        """Execute tests in parallel"""
        results = {}
        
        for group_index, group in enumerate(plan.parallel_groups):
            # Execute group in parallel
            group_futures = []
            for session_id in group:
                future = asyncio.create_task(self._execute_single_test(session_id, config))
                group_futures.append((session_id, future))
            
            # Wait for group completion
            for session_id, future in group_futures:
                try:
                    result = await future
                    results[session_id] = result
                except Exception as e:
                    results[session_id] = {"error": str(e), "success": False}
            
            # Update progress
            progress = (group_index + 1) / len(plan.parallel_groups) * 100
            self.progress_tracker.track_progress(
                plan.project_id, "test_execution", progress,
                {"completed_groups": group_index + 1, "total_groups": len(plan.parallel_groups)}
            )
        
        return results
    
    async def _execute_sequential_tests(self, plan: TestExecutionPlan, config: WorkflowConfiguration) -> Dict[str, Any]:
        """Execute tests sequentially"""
        results = {}
        
        for index, session_id in enumerate(plan.execution_order):
            try:
                result = await self._execute_single_test(session_id, config)
                results[session_id] = result
            except Exception as e:
                results[session_id] = {"error": str(e), "success": False}
                
                # Handle failure based on configuration
                if not config.auto_recovery:
                    break
            
            # Update progress
            progress = (index + 1) / len(plan.execution_order) * 100
            self.progress_tracker.track_progress(
                plan.project_id, "test_execution", progress,
                {"completed_tests": index + 1, "total_tests": len(plan.execution_order)}
            )
        
        return results
    
    async def _execute_single_test(self, session_id: str, config: WorkflowConfiguration) -> Dict[str, Any]:
        """Execute single test session"""
        db = SessionLocal()
        try:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                raise ValueError(f"Test session {session_id} not found")
            
            # Simulate test execution (would integrate with actual test runner)
            start_time = datetime.utcnow()
            
            # Execute test logic here
            await asyncio.sleep(1)  # Simulated execution time
            
            end_time = datetime.utcnow()
            duration = end_time - start_time
            
            # Generate mock results (would be real test results)
            results = {
                "session_id": session_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration.total_seconds(),
                "success": True,
                "metrics": {
                    "precision": 0.95,
                    "recall": 0.92,
                    "f1_score": 0.935,
                    "latency_ms": 85.0
                }
            }
            
            return results
            
        finally:
            db.close()

class ProjectWorkflowManager:
    """Main Project Workflow Management System"""
    
    def __init__(self):
        self.project_manager = ProjectManager()
        self.orchestrator = WorkflowOrchestrator()
        self.progress_tracker = ProgressTracker()
        self.test_orchestrator = TestExecutionOrchestrator()
        self.memory_namespace = "vru-project-workflow"
    
    async def create_project_workflow(self, project_data: Dict, workflow_config: Optional[WorkflowConfiguration] = None) -> str:
        """Create complete project workflow"""
        try:
            # Create project
            project_id = self.project_manager.create_project_with_criteria(
                project_data, 
                workflow_config.pass_fail_criteria if workflow_config else None
            )
            
            # Create default workflow configuration if not provided
            if workflow_config is None:
                workflow_config = WorkflowConfiguration(
                    project_id=project_id,
                    name=f"Workflow for {project_data['name']}",
                    description=f"Automated workflow for project {project_data['name']}"
                )
            else:
                workflow_config.project_id = project_id
            
            # Store configuration in memory
            await self._store_workflow_config(project_id, workflow_config)
            
            # Execute workflow
            workflow_id = await self.orchestrator.execute_workflow(workflow_config)
            
            logger.info(f"Created project workflow: project_id={project_id}, workflow_id={workflow_id}")
            
            return {
                "project_id": project_id,
                "workflow_id": workflow_id,
                "status": "created",
                "config": workflow_config
            }
            
        except Exception as e:
            logger.error(f"Failed to create project workflow: {str(e)}")
            raise
    
    async def execute_project_tests(self, project_id: str, config: Optional[WorkflowConfiguration] = None) -> Dict[str, Any]:
        """Execute comprehensive project tests"""
        try:
            # Load or create configuration
            if config is None:
                config = await self._load_workflow_config(project_id)
            
            # Create execution plan
            execution_plan = self.test_orchestrator.create_execution_plan(project_id, config)
            
            # Execute tests
            results = await self.test_orchestrator.execute_test_plan(execution_plan, config)
            
            # Store results
            await self._store_test_results(project_id, results)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute project tests: {str(e)}")
            raise
    
    def configure_latency_thresholds(self, project_id: str, thresholds: LatencyThreshold) -> bool:
        """Configure project latency thresholds"""
        try:
            # Store in memory for coordination
            key = f"latency_thresholds:{project_id}"
            self._store_in_memory(key, thresholds.to_dict())
            
            logger.info(f"Configured latency thresholds for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure latency thresholds: {str(e)}")
            return False
    
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Get comprehensive project status"""
        try:
            # Get basic progress from project manager
            basic_progress = self.project_manager.get_project_progress(project_id)
            
            # Get detailed progress from tracker
            detailed_progress = self.progress_tracker.get_overall_progress(project_id)
            
            # Get workflow status if available
            workflow_status = self._get_workflow_status(project_id)
            
            # Combine all status information
            status = {
                "project_id": project_id,
                "basic_progress": basic_progress,
                "detailed_progress": detailed_progress,
                "workflow_status": workflow_status,
                "last_updated": datetime.utcnow()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get project status: {str(e)}")
            return {"project_id": project_id, "error": str(e)}
    
    async def assign_videos_intelligently(self, project_id: str, video_ids: Optional[List[str]] = None) -> List[Assignment]:
        """Assign videos using intelligent system"""
        try:
            # Use project manager's intelligent assignment
            assignments = self.project_manager.assign_videos_to_project(project_id, video_ids)
            
            # Track progress
            self.progress_tracker.track_progress(
                project_id, "video_assignment", 100.0,
                {"assigned_videos": len(assignments), "assignments": [a.__dict__ for a in assignments]}
            )
            
            # Store in memory for coordination
            await self._store_video_assignments(project_id, assignments)
            
            return assignments
            
        except Exception as e:
            logger.error(f"Failed to assign videos: {str(e)}")
            raise
    
    def update_workflow_status(self, project_id: str, status: WorkflowState, metadata: Optional[Dict] = None) -> bool:
        """Update workflow status"""
        try:
            status_data = {
                "project_id": project_id,
                "status": status.value,
                "timestamp": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            key = f"workflow_status:{project_id}"
            self._store_in_memory(key, status_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update workflow status: {str(e)}")
            return False
    
    # Memory coordination methods
    async def _store_workflow_config(self, project_id: str, config: WorkflowConfiguration):
        """Store workflow configuration in memory"""
        key = f"workflow_config:{project_id}"
        config_dict = {
            "project_id": config.project_id,
            "name": config.name,
            "description": config.description,
            "priority": config.priority.value,
            "execution_strategy": config.execution_strategy.value,
            "max_concurrent_tasks": config.max_concurrent_tasks,
            "timeout_minutes": config.timeout_minutes,
            "retry_attempts": config.retry_attempts,
            "auto_recovery": config.auto_recovery,
            "latency_thresholds": config.latency_thresholds.to_dict(),
            "pass_fail_criteria": config.pass_fail_criteria.to_dict(),
            "notification_config": config.notification_config,
            "custom_parameters": config.custom_parameters
        }
        self._store_in_memory(key, config_dict)
    
    async def _load_workflow_config(self, project_id: str) -> WorkflowConfiguration:
        """Load workflow configuration from memory"""
        key = f"workflow_config:{project_id}"
        config_dict = self._load_from_memory(key)
        
        if not config_dict:
            # Return default configuration
            return WorkflowConfiguration(
                project_id=project_id,
                name=f"Default workflow for {project_id}"
            )
        
        # Reconstruct configuration object
        config = WorkflowConfiguration(
            project_id=config_dict["project_id"],
            name=config_dict["name"],
            description=config_dict["description"],
            priority=WorkflowPriority(config_dict["priority"]),
            execution_strategy=ExecutionStrategy(config_dict["execution_strategy"]),
            max_concurrent_tasks=config_dict["max_concurrent_tasks"],
            timeout_minutes=config_dict["timeout_minutes"],
            retry_attempts=config_dict["retry_attempts"],
            auto_recovery=config_dict["auto_recovery"],
            latency_thresholds=LatencyThreshold.from_dict(config_dict["latency_thresholds"]),
            pass_fail_criteria=PassFailCriteria.from_dict(config_dict["pass_fail_criteria"]),
            notification_config=config_dict["notification_config"],
            custom_parameters=config_dict["custom_parameters"]
        )
        
        return config
    
    async def _store_test_results(self, project_id: str, results: Dict[str, Any]):
        """Store test results in memory"""
        key = f"test_results:{project_id}"
        self._store_in_memory(key, results)
    
    async def _store_video_assignments(self, project_id: str, assignments: List[Assignment]):
        """Store video assignments in memory"""
        key = f"video_assignments:{project_id}"
        assignments_dict = [
            {
                "video_id": a.video_id,
                "project_id": a.project_id,
                "compatibility_score": a.compatibility_score,
                "assigned_at": a.assigned_at.isoformat(),
                "assignment_reason": a.assignment_reason
            }
            for a in assignments
        ]
        self._store_in_memory(key, assignments_dict)
    
    def _get_workflow_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow status from memory"""
        key = f"workflow_status:{project_id}"
        return self._load_from_memory(key)
    
    def _store_in_memory(self, key: str, data: Any):
        """Store data in memory coordination system"""
        # This would integrate with the actual memory coordination system
        # For now, using simple in-memory storage
        if not hasattr(self, '_memory_store'):
            self._memory_store = {}
        self._memory_store[f"{self.memory_namespace}:{key}"] = data
    
    def _load_from_memory(self, key: str) -> Any:
        """Load data from memory coordination system"""
        if not hasattr(self, '_memory_store'):
            return None
        return self._memory_store.get(f"{self.memory_namespace}:{key}")

# API Integration Layer
class WorkflowAPIIntegration:
    """API integration layer for workflow management"""
    
    def __init__(self):
        self.workflow_manager = ProjectWorkflowManager()
    
    async def create_project_endpoint(self, project_data: Dict, workflow_config: Optional[Dict] = None):
        """API endpoint for creating project workflow"""
        try:
            # Convert dict to configuration object if provided
            config = None
            if workflow_config:
                config = self._dict_to_workflow_config(workflow_config)
            
            result = await self.workflow_manager.create_project_workflow(project_data, config)
            
            return {
                "success": True,
                "data": result,
                "message": "Project workflow created successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create project workflow"
            }
    
    async def execute_tests_endpoint(self, project_id: str, config: Optional[Dict] = None):
        """API endpoint for executing project tests"""
        try:
            workflow_config = None
            if config:
                workflow_config = self._dict_to_workflow_config(config)
            
            results = await self.workflow_manager.execute_project_tests(project_id, workflow_config)
            
            return {
                "success": True,
                "data": results,
                "message": "Tests executed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to execute tests"
            }
    
    def get_status_endpoint(self, project_id: str):
        """API endpoint for getting project status"""
        try:
            status = self.workflow_manager.get_project_status(project_id)
            
            return {
                "success": True,
                "data": status,
                "message": "Status retrieved successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get project status"
            }
    
    def configure_latency_endpoint(self, project_id: str, thresholds: Dict):
        """API endpoint for configuring latency thresholds"""
        try:
            threshold_config = LatencyThreshold.from_dict(thresholds)
            success = self.workflow_manager.configure_latency_thresholds(project_id, threshold_config)
            
            return {
                "success": success,
                "data": {"project_id": project_id, "thresholds": thresholds},
                "message": "Latency thresholds configured successfully" if success else "Failed to configure latency thresholds"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to configure latency thresholds"
            }
    
    def _dict_to_workflow_config(self, config_dict: Dict) -> WorkflowConfiguration:
        """Convert dictionary to WorkflowConfiguration object"""
        return WorkflowConfiguration(
            project_id=config_dict.get("project_id", ""),
            name=config_dict.get("name", "Unnamed Workflow"),
            description=config_dict.get("description", ""),
            priority=WorkflowPriority(config_dict.get("priority", "normal")),
            execution_strategy=ExecutionStrategy(config_dict.get("execution_strategy", "adaptive")),
            max_concurrent_tasks=config_dict.get("max_concurrent_tasks", 5),
            timeout_minutes=config_dict.get("timeout_minutes", 120),
            retry_attempts=config_dict.get("retry_attempts", 3),
            auto_recovery=config_dict.get("auto_recovery", True),
            latency_thresholds=LatencyThreshold.from_dict(config_dict.get("latency_thresholds", {})),
            pass_fail_criteria=PassFailCriteria.from_dict(config_dict.get("pass_fail_criteria", {})),
            notification_config=config_dict.get("notification_config", {}),
            custom_parameters=config_dict.get("custom_parameters", {})
        )

# Main instance for application use
workflow_manager = ProjectWorkflowManager()
api_integration = WorkflowAPIIntegration()

if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def main():
        # Create example project workflow
        project_data = {
            "name": "VRU Detection Test Project",
            "description": "Test project for VRU detection validation",
            "camera_model": "Test Camera",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        workflow_config = WorkflowConfiguration(
            project_id="",  # Will be set automatically
            name="Comprehensive VRU Validation Workflow",
            execution_strategy=ExecutionStrategy.ADAPTIVE,
            max_concurrent_tasks=3
        )
        
        try:
            result = await workflow_manager.create_project_workflow(project_data, workflow_config)
            print(f"Created workflow: {result}")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    # Run example
    asyncio.run(main())