# Project Workflow Management System Architecture

## Overview

Complete project workflow management system for AI model validation platform, built using SPARC methodology with comprehensive workflow orchestration, progress tracking, and API integration.

## System Components

### 1. Core Components

#### ProjectWorkflowManager (`project_workflow_manager.py`)
- **Main orchestration system** that coordinates all workflow operations
- Integrates with existing ProjectManager, VideoAssignmentSystem, and PassFailCriteriaEngine
- Provides unified interface for project lifecycle management
- Manages memory coordination with namespace `vru-project-workflow`

#### WorkflowOrchestrator
- **Advanced workflow execution engine** with multiple strategies:
  - **Sequential**: Tasks executed in order
  - **Parallel**: Independent tasks executed concurrently  
  - **Adaptive**: Strategy chosen based on project complexity
  - **Hybrid**: Critical tasks sequential, independent tasks parallel
- Built-in task registry with 9 default tasks + custom task support
- Concurrent workflow execution with progress tracking

#### ProgressTracker
- **Real-time progress monitoring** with callback system
- Component-level progress tracking
- Overall progress calculation across multiple components
- Memory-coordinated state persistence
- Performance metrics collection

#### TestExecutionOrchestrator
- **Comprehensive test execution planning and orchestration**
- Creates execution plans with dependency analysis
- Resource requirement estimation
- Sequential and parallel test execution
- Result collection and analysis

### 2. Configuration Components

#### WorkflowConfiguration
- Complete workflow configuration with:
  - Execution strategy selection
  - Priority levels (LOW, NORMAL, HIGH, CRITICAL)
  - Timeout and retry settings
  - Auto-recovery configuration
  - Custom parameters support

#### LatencyThreshold
- **6 configurable latency thresholds**:
  - Detection latency (default: 100ms)
  - Processing latency (default: 500ms)
  - End-to-end latency (default: 1000ms)
  - Signal processing latency (default: 50ms)
  - Warning threshold (default: 80ms)
  - Critical threshold (default: 150ms)

#### PassFailCriteria
- **8 configurable pass/fail criteria**:
  - Precision, Recall, F1-score thresholds
  - Latency limits
  - False positive rate limits
  - Detection confidence requirements
  - Accuracy requirements
  - Required detection counts

### 3. API Layer

#### WorkflowAPIIntegration (`workflow_endpoints.py`)
- **Complete FastAPI integration** with 10+ endpoints
- Pydantic models for request/response validation
- Background task support for long-running operations
- Comprehensive error handling and status codes

#### Key Endpoints:
- `POST /api/v1/workflow/projects/create` - Create project workflow
- `POST /api/v1/workflow/tests/execute` - Execute project tests
- `GET /api/v1/workflow/projects/{id}/status` - Get project status
- `POST /api/v1/workflow/projects/{id}/latency-thresholds` - Configure latency
- `POST /api/v1/workflow/projects/{id}/assign-videos` - Assign videos
- `GET /api/v1/workflow/projects/{id}/progress` - Get progress
- `GET /api/v1/workflow/workflows/active` - Get active workflows
- `GET /api/v1/workflow/health` - System health check

### 4. Integration Layer

#### WorkflowIntegrationManager (`workflow_integration.py`)
- **Complete system integration** with FastAPI lifespan management
- Background monitoring tasks for health and progress
- Custom task registration for VRU-specific operations
- Graceful startup and shutdown procedures

## Workflow States

12 comprehensive workflow states:
- **INITIALIZED** - Workflow created and ready
- **PLANNING** - Resource planning and task scheduling
- **RESOURCE_ALLOCATION** - Allocating system resources
- **VIDEO_ASSIGNMENT** - Assigning videos to project
- **GROUND_TRUTH_GENERATION** - Generating ground truth data
- **TEST_CONFIGURATION** - Configuring test parameters
- **EXECUTION** - Running validation tests
- **MONITORING** - Active monitoring of test execution
- **ANALYSIS** - Analyzing test results
- **VALIDATION** - Validating results against criteria
- **COMPLETED** - Workflow successfully completed
- **FAILED/CANCELLED/PAUSED** - Error or control states

## Memory Coordination

### Namespace: `vru-project-workflow`

Coordinated memory storage for:
- **Workflow configurations** - Persistent across sessions
- **Progress data** - Real-time progress tracking
- **Test results** - Complete result storage
- **Video assignments** - Assignment history and metadata
- **Latency thresholds** - Per-project configuration
- **System health** - Health monitoring data

### Memory Keys:
```
workflow_config:{project_id} - Workflow configuration
workflow_status:{project_id} - Current workflow status  
test_results:{project_id} - Test execution results
video_assignments:{project_id} - Video assignment data
latency_thresholds:{project_id} - Latency configuration
health_metrics - System health data
system_init - System initialization data
```

## Integration Points

### Existing Services Integration
- **ProjectManager** - Project lifecycle and status management
- **VideoAssignmentSystem** - Intelligent video-to-project mapping
- **PassFailCriteriaEngine** - Configurable evaluation criteria
- **ResourceAllocationManager** - System resource management

### Database Integration
- **Project Model** - Core project entity
- **Video Model** - Video management and metadata
- **TestSession Model** - Test execution tracking
- **DetectionEvent Model** - Detection results storage

## Execution Strategies

### 1. Sequential Execution
```python
tasks = [validate, allocate, assign, test, analyze]
for task in tasks:
    await execute_task(task)
```

### 2. Parallel Execution
```python
independent_tasks = group_by_dependencies(tasks)
for group in independent_tasks:
    await asyncio.gather(*[execute_task(t) for t in group])
```

### 3. Adaptive Execution
```python
complexity = analyze_project_complexity(project)
if complexity < 0.3:
    strategy = Sequential
elif complexity > 0.7:
    strategy = Parallel
else:
    strategy = Hybrid
```

### 4. Hybrid Execution
```python
critical_tasks = [validate, allocate]  # Sequential
independent_tasks = [assign, configure, monitor]  # Parallel

for task in critical_tasks:
    await execute_task(task)

await asyncio.gather(*[execute_task(t) for t in independent_tasks])
```

## Performance Features

### Concurrent Execution
- Multiple workflows can run simultaneously
- Configurable concurrency limits per workflow
- Resource-aware task scheduling

### Progress Tracking
- Real-time progress updates
- Component-level granularity
- Callback system for notifications
- Performance metrics collection

### Memory Optimization
- Namespace isolation prevents conflicts
- Efficient data structures for progress tracking
- Configurable memory limits

## Error Handling

### Retry Mechanisms
- Configurable retry attempts (default: 3)
- Exponential backoff for transient failures
- Task-specific retry policies

### Auto-Recovery
- Automatic workflow recovery from failures
- State persistence for resumable workflows
- Health monitoring and self-healing

### Graceful Degradation
- Fallback execution strategies
- Partial success handling
- Comprehensive error logging

## API Examples

### Create Project Workflow
```json
POST /api/v1/workflow/projects/create
{
  "name": "VRU Detection Project",
  "camera_model": "Test Camera",
  "camera_view": "Front-facing VRU",
  "signal_type": "GPIO",
  "workflow_config": {
    "execution_strategy": "adaptive",
    "priority": "high",
    "max_concurrent_tasks": 3,
    "latency_thresholds": {
      "detection_latency_ms": 80.0,
      "processing_latency_ms": 400.0
    },
    "pass_fail_criteria": {
      "min_precision": 0.95,
      "min_recall": 0.90
    }
  }
}
```

### Execute Tests
```json
POST /api/v1/workflow/tests/execute
{
  "project_id": "project_123",
  "workflow_config": {
    "execution_strategy": "parallel",
    "max_concurrent_tasks": 5
  }
}
```

### Get Project Status
```json
GET /api/v1/workflow/projects/project_123/status

Response:
{
  "success": true,
  "project_id": "project_123",
  "status": {
    "basic_progress": {
      "overall_progress": 75.0,
      "videos": {"total": 10, "processed": 8},
      "tests": {"total": 5, "completed": 3}
    },
    "detailed_progress": {
      "components": {
        "video_assignment": {"progress": 100.0},
        "test_execution": {"progress": 60.0},
        "analysis": {"progress": 25.0}
      }
    },
    "workflow_status": {
      "status": "execution",
      "current_task": "test_execution"
    }
  }
}
```

## Testing Coverage

### Unit Tests (`test_project_workflow_manager.py`)
- **50+ test cases** covering all components
- Configuration validation and conversion
- Progress tracking functionality
- Workflow orchestration logic
- Memory coordination testing

### Integration Tests
- FastAPI endpoint testing
- Database integration validation
- Service layer integration
- Error handling scenarios

### Performance Tests
- Concurrent workflow execution
- Memory performance validation
- Progress tracking scalability
- Load testing scenarios

## Deployment Integration

### FastAPI Integration
```python
from workflow_integration import integrate_workflow_management

app = FastAPI()
app = integrate_workflow_management(app)
```

### Standalone Deployment
```python
from workflow_integration import create_integrated_app

app = create_integrated_app()
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Architecture Benefits

### 1. Scalability
- Concurrent workflow execution
- Resource-aware scheduling
- Horizontal scaling ready

### 2. Reliability  
- Comprehensive error handling
- Auto-recovery mechanisms
- State persistence

### 3. Maintainability
- Modular component design
- Clear separation of concerns
- Comprehensive testing

### 4. Extensibility
- Custom task registration
- Pluggable execution strategies
- Configuration-driven behavior

### 5. Observability
- Real-time progress tracking
- Health monitoring
- Performance metrics
- Comprehensive logging

## Memory Coordination Benefits

### 1. State Persistence
- Workflows survive system restarts
- Progress preserved across sessions
- Configuration persistence

### 2. Component Coordination
- Shared state between components
- Event-driven updates
- Consistent data access

### 3. Namespace Isolation
- No conflicts with other systems
- Clean data organization
- Secure access control

This architecture provides a complete, production-ready project workflow management system that integrates seamlessly with the existing AI model validation platform while providing comprehensive workflow orchestration, progress tracking, and API integration capabilities.