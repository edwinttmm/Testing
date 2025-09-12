# Swarm Coordination Protocol for Dataset Annotations & Screenshots

## Coordination Architecture

### Hierarchical Mesh Hybrid Structure
```
                    [Coordinator]
                         |
        ┌────────────────┼────────────────┐
        │                │                │
   [Backend-API]    [Frontend-UI]    [Database]
        │                │                │
        └────────── [Cleanup-Agent] ──────┘
```

### Communication Channels
- **Memory**: Shared state and progress tracking
- **Hooks**: Pre/during/post task notifications
- **Events**: Real-time status updates
- **Artifacts**: Deliverable sharing

## Memory Management Protocol

### Memory Namespace Structure
```
swarm/
├── coordination/
│   ├── session_id: "dataset-annotations-2025-01-15"
│   ├── active_agents: []
│   ├── task_queue: []
│   └── completion_status: {}
├── shared_state/
│   ├── current_video_context: {}
│   ├── annotation_schemas: {}
│   ├── screenshot_formats: {}
│   └── api_contracts: {}
├── agent_memory/
│   ├── backend-api/
│   ├── frontend-ui/
│   ├── database/
│   └── cleanup/
└── artifacts/
    ├── api_documentation/
    ├── component_specs/
    ├── database_scripts/
    └── cleanup_reports/
```

### Memory Access Patterns
- **Read-Only**: Configuration, schemas, contracts
- **Write-Exclusive**: Agent progress, individual deliverables
- **Shared-Write**: Integration test results, cross-agent data
- **Event-Driven**: Status changes, error notifications

## Agent Communication Protocols

### 1. Pre-Task Coordination Hook
```bash
# Each agent executes before starting work
swarm_hook_pre_task() {
    local task_id=$1
    local dependencies=$2
    
    # Register task intent
    memory_write "swarm/coordination/task_queue/$task_id" "{
        \"agent\": \"$AGENT_ID\",
        \"status\": \"registered\",
        \"dependencies\": $dependencies,
        \"estimated_duration\": \"$ESTIMATED_TIME\"
    }"
    
    # Validate dependencies
    check_dependency_completion $dependencies
    
    # Reserve resources
    reserve_agent_resources $task_id
    
    # Notify other agents
    broadcast_event "TASK_STARTED" $task_id $AGENT_ID
}
```

### 2. During-Task Progress Hook
```bash
# Periodic progress updates during task execution
swarm_hook_progress_update() {
    local task_id=$1
    local completion_percent=$2
    local current_subtask=$3
    
    # Update progress
    memory_write "swarm/coordination/task_progress/$task_id" "{
        \"completion_percent\": $completion_percent,
        \"current_subtask\": \"$current_subtask\",
        \"last_update\": \"$(date -Iseconds)\",
        \"status\": \"in_progress\"
    }"
    
    # Share intermediate results if available
    if has_intermediate_results; then
        share_intermediate_artifacts $task_id
    fi
    
    # Check for blocking issues
    if is_blocked; then
        escalate_blocking_issue $task_id
    fi
}
```

### 3. Post-Task Validation Hook
```bash
# Task completion and integration validation
swarm_hook_post_task() {
    local task_id=$1
    local deliverables=$2
    
    # Mark task complete
    memory_write "swarm/coordination/task_completion/$task_id" "{
        \"status\": \"completed\",
        \"completion_time\": \"$(date -Iseconds)\",
        \"deliverables\": $deliverables,
        \"validation_status\": \"pending\"
    }"
    
    # Upload deliverables to shared artifacts
    upload_artifacts $task_id $deliverables
    
    # Run integration tests
    run_integration_tests $task_id
    
    # Notify dependent agents
    notify_dependent_agents_completion $task_id
    
    # Release resources
    release_agent_resources $task_id
}
```

## Task Orchestration Protocol

### Phase-Based Execution
1. **Initialization Phase**
   - All agents register and validate environment
   - Shared memory initialized with base configuration
   - Dependencies mapped and validated

2. **Analysis Phase**
   - Agents perform initial analysis in parallel
   - Results stored in shared memory
   - Cross-agent validation of analysis findings

3. **Implementation Phase**
   - Tasks executed based on dependency graph
   - Real-time progress monitoring
   - Automatic conflict detection and resolution

4. **Integration Phase**
   - Cross-agent integration testing
   - Performance validation
   - Final cleanup and documentation

### Conflict Resolution Protocol

#### Schema Conflicts
```
Priority Order: Database Agent > Backend Agent > Frontend Agent > Cleanup Agent
Resolution: Database agent makes final decision on schema changes
Process:
1. Conflicting agents pause implementation
2. Database agent reviews conflict in memory
3. Database agent posts resolution decision
4. Other agents adapt to decision
5. Implementation resumes
```

#### API Contract Disputes
```
Priority Order: Backend Agent > Frontend Agent > Database Agent
Resolution: Backend agent defines API contracts
Process:
1. Frontend agent raises contract concern
2. Backend agent reviews and posts revised contract
3. Frontend agent adapts implementation
4. Database agent updates queries if needed
```

#### Resource Conflicts
```
Resolution: First-come-first-served with escalation
Process:
1. Agent requests resource lock
2. If unavailable, agent queues request
3. If blocking critical path, escalate to coordinator
4. Coordinator may override resource allocation
```

## Error Handling & Recovery

### Error Classification
- **Blocking**: Prevents agent from continuing
- **Warning**: Agent can continue but with degraded functionality
- **Info**: Notification only, no action required

### Recovery Strategies
1. **Automatic Retry**: For transient failures (3 attempts)
2. **Fallback Implementation**: For non-critical features
3. **Graceful Degradation**: Disable feature rather than fail
4. **Escalation**: Notify coordinator for manual intervention

### Error Reporting Protocol
```bash
swarm_report_error() {
    local error_level=$1
    local error_message=$2
    local task_id=$3
    
    memory_write "swarm/errors/$AGENT_ID/$(date +%s)" "{
        \"level\": \"$error_level\",
        \"message\": \"$error_message\",
        \"task_id\": \"$task_id\",
        \"timestamp\": \"$(date -Iseconds)\",
        \"agent_id\": \"$AGENT_ID\"
    }"
    
    if [ "$error_level" = "blocking" ]; then
        broadcast_event "BLOCKING_ERROR" $task_id $AGENT_ID "$error_message"
        pause_dependent_tasks $task_id
    fi
}
```

## Performance Monitoring

### Metrics Collection
- Task completion times
- Resource utilization
- Cross-agent communication latency
- Memory usage patterns
- Error frequencies

### Performance Thresholds
- Maximum task duration: 2 hours
- Memory usage limit: 1GB per agent
- Cross-agent response time: <5 seconds
- Integration test completion: <30 minutes

## Quality Assurance Protocol

### Code Quality Gates
1. **Syntax Validation**: All code must pass linting
2. **Type Safety**: TypeScript types must be complete
3. **Test Coverage**: Minimum 80% test coverage
4. **Performance**: No degradation in key metrics
5. **Documentation**: All public APIs documented

### Integration Validation
1. **API Contract Compliance**: Frontend calls match backend contracts
2. **Database Consistency**: All data relationships maintained
3. **UI/UX Standards**: Consistent user experience
4. **Error Handling**: Graceful error recovery
5. **Security**: No introduction of security vulnerabilities

## Success Criteria

### Phase-Level Success
- **Analysis**: All agents complete analysis within 30 minutes
- **Implementation**: All tasks complete without blocking errors
- **Integration**: All integration tests pass
- **Cleanup**: No duplicate code or obsolete components remain

### Overall Success Metrics
- Dataset page displays annotations with screenshots correctly
- Performance maintains acceptable response times
- No regression in existing functionality
- Code quality standards maintained
- All documentation updated

## Session Management

### Session Initialization
```bash
# Initialize new swarm session
swarm_init_session() {
    local session_id="dataset-annotations-$(date +%Y%m%d-%H%M%S)"
    
    memory_write "swarm/coordination/session_id" "$session_id"
    memory_write "swarm/coordination/start_time" "$(date -Iseconds)"
    memory_write "swarm/coordination/active_agents" "[]"
    
    echo "Swarm session $session_id initialized"
}
```

### Session Cleanup
```bash
# Clean up session resources
swarm_cleanup_session() {
    local session_id=$(memory_read "swarm/coordination/session_id")
    
    # Archive session data
    archive_session_data $session_id
    
    # Release all resources
    release_all_resources
    
    # Generate final report
    generate_session_report $session_id
    
    echo "Swarm session $session_id completed successfully"
}
```