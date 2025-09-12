# Dataset Page Annotations & Screenshots Swarm Coordination System

## Overview
This document establishes the MCP coordination system for implementing dataset page annotations and screenshots functionality across multiple specialized agents working in parallel.

## Swarm Topology: Hierarchical Mesh Hybrid
- **Coordinator**: Central orchestrator managing task distribution
- **Mesh Network**: Sub-agents collaborate peer-to-peer within domains
- **Hierarchical Oversight**: Domain leads report to coordinator

## Agent Definitions & Roles

### 1. Backend API Development Agent (`backend-api-agent`)
**Domain**: Server-side API development
**Responsibilities**:
- Implement annotation CRUD endpoints
- Create screenshot generation endpoints
- Add detection event screenshot storage
- Implement annotation search and filtering
- Create export functionality for annotations with screenshots

**Memory Keys**:
- `swarm/backend-api/annotation-endpoints`
- `swarm/backend-api/screenshot-endpoints`
- `swarm/backend-api/detection-integration`

**Coordination Hooks**:
- Notify frontend agent of new endpoint contracts
- Share database schema requirements with DB agent
- Coordinate with cleanup agent for deprecated endpoints

### 2. Frontend Component Development Agent (`frontend-ui-agent`)
**Domain**: React/TypeScript UI development
**Responsibilities**:
- Enhance DetectionResultsPanel for screenshot display
- Create AnnotationVisualization component
- Implement screenshot gallery/carousel
- Add annotation filtering and search UI
- Create screenshot zoom/modal functionality

**Memory Keys**:
- `swarm/frontend-ui/component-specs`
- `swarm/frontend-ui/screenshot-display`
- `swarm/frontend-ui/api-integration`

**Coordination Hooks**:
- Consume API contracts from backend agent
- Share component interfaces with DB integration agent
- Coordinate UI consistency with cleanup agent

### 3. Database Integration Agent (`database-schema-agent`)
**Domain**: Database schema and data relationships
**Responsibilities**:
- Ensure proper DetectionEvent screenshot field usage
- Verify Annotation table relationships
- Optimize queries for annotation/screenshot retrieval
- Validate data integrity constraints
- Create database migration scripts if needed

**Memory Keys**:
- `swarm/database/schema-changes`
- `swarm/database/query-optimization`
- `swarm/database/migration-scripts`

**Coordination Hooks**:
- Share schema requirements with backend API agent
- Validate data models with frontend UI agent
- Coordinate data cleanup strategies with cleanup agent

### 4. Code Cleanup Agent (`code-cleanup-agent`)
**Domain**: Code quality and duplication removal
**Responsibilities**:
- Remove duplicate annotation handling code
- Clean up unused screenshot-related imports
- Consolidate similar UI components
- Remove obsolete API endpoints
- Standardize error handling patterns

**Memory Keys**:
- `swarm/cleanup/duplicate-code`
- `swarm/cleanup/unused-imports`
- `swarm/cleanup/obsolete-endpoints`

**Coordination Hooks**:
- Coordinate with all agents to identify cleanup targets
- Share cleanup reports with coordinator
- Validate cleanup doesn't break functionality

## Memory Coordination Protocol

### Shared Memory Structure
```
swarm/
├── session-state/
│   ├── current-video-id
│   ├── selected-annotations
│   └── screenshot-display-mode
├── backend-api/
│   ├── annotation-endpoints
│   ├── screenshot-endpoints
│   └── api-contracts
├── frontend-ui/
│   ├── component-specs
│   ├── screenshot-display
│   └── user-interactions
├── database/
│   ├── schema-changes
│   ├── query-performance
│   └── data-integrity
└── cleanup/
    ├── removed-duplicates
    ├── consolidated-components
    └── cleanup-reports
```

### Cross-Agent Communication
- **API Contract Updates**: Backend → Frontend via memory
- **Schema Changes**: Database → Backend → Frontend via memory
- **Cleanup Reports**: Cleanup → All agents via memory
- **Progress Updates**: All agents → Coordinator via memory

## Task Orchestration Workflow

### Phase 1: Analysis & Planning
1. **Backend API Agent**: Analyze existing annotation endpoints
2. **Frontend UI Agent**: Review current screenshot display implementation
3. **Database Agent**: Audit current schema and relationships
4. **Cleanup Agent**: Identify duplicates and obsolete code

### Phase 2: Parallel Implementation
1. **Backend API Agent**: Implement enhanced annotation endpoints
2. **Frontend UI Agent**: Build screenshot display components
3. **Database Agent**: Optimize queries and create migrations
4. **Cleanup Agent**: Remove identified duplicates

### Phase 3: Integration & Testing
1. All agents coordinate integration testing
2. Cross-validate API contracts and data flow
3. Ensure UI responsiveness with database optimizations
4. Verify cleanup didn't break functionality

### Phase 4: Documentation & Handoff
1. Update API documentation
2. Document new UI components
3. Create database migration guides
4. Generate cleanup reports

## Agent Coordination Rules

### Communication Protocol
1. **Pre-Task**: Register intent and dependencies in memory
2. **During Work**: Update progress and share intermediate results
3. **Post-Task**: Validate integration points and notify dependents

### Conflict Resolution
1. Schema conflicts: Database agent has final authority
2. API contract disputes: Backend agent has final authority
3. UI consistency issues: Frontend agent has final authority
4. Code cleanup conflicts: Cleanup agent defers to domain experts

### Quality Gates
- Each agent must validate their work against integration tests
- Cross-agent integration must pass before proceeding to next phase
- All changes must maintain backward compatibility
- Performance impact must be measured and documented

## Success Metrics
- All annotation data properly displays with screenshots
- No duplicate code or obsolete components remain
- API response times maintain acceptable performance
- UI is responsive and intuitive for annotation management
- Database queries are optimized for screenshot retrieval

## Risk Mitigation
- **Integration Failures**: Staged rollback points at each phase
- **Performance Degradation**: Benchmark before/after measurements
- **Data Loss**: Full database backup before schema changes
- **UI Breakage**: Component-level testing with visual regression tests