# AI Model Validation Platform - System Architecture Diagrams

## Current Architecture Problems - Data Flow Analysis

### 1. FRAGMENTED STATUS DETERMINATION ARCHITECTURE

```mermaid
graph TD
    A[Results Component] --> B{API Selection Logic}
    B -->|Enhanced API Available| C[getEnhancedTestSessions]
    B -->|Fallback| D[apiService.getTestSessions]
    
    C --> E[Enhanced API Response]
    D --> F[Standard API Response]
    
    E --> G{Results Summary Available?}
    G -->|Yes| H[Use Enhanced Results]
    G -->|No| I[Call apiService.getTestResults]
    
    F --> I
    
    I --> J{API Call Success?}
    J -->|Success| K[Transform Results]
    J -->|Error| L[Mock Data Fallback]
    
    K --> M[Status Mapping Logic]
    L --> N[Hardcoded 'completed' Status]
    
    M --> O{Status Determination}
    O -->|TestSession.status| P["created", "running", "completed", "failed"]
    O -->|DetectionEvent.validation_result| Q["pass", "fail", "error", "timeout"]
    O -->|DetectionEvent.latency_result| R["pass", "fail", "error", "timeout"]
    O -->|WebSocket Updates| S["Manual", "Automated", "Processing"]
    O -->|Fallback Logic| T["Manual" - DEFAULT VALUE]
    
    P --> U[UI Display Logic]
    Q --> U
    R --> U
    S --> U
    T --> U
    
    U --> V{Final Status Displayed}
    V --> W["Manual" - Persistent Display Issue]
```

### 2. DATABASE SCHEMA CONFLICTS

```mermaid
erDiagram
    TestSession ||--o{ DetectionEvent : has
    DetectionEvent }o--|| GroundTruthObject : matches
    TestSession ||--o{ TestResult : generates
    
    TestSession {
        string id
        string status "created|running|completed|failed"
        string session_type "user_created|auto_generated"
        datetime started_at
        datetime completed_at
    }
    
    DetectionEvent {
        string id
        string test_session_id
        float timestamp
        string validation_result "pass|fail|error|timeout"
        string latency_result "pass|fail|error|timeout"
        float latency_ms
        float labjack_timestamp
        string class_label "LEGACY_AI_FIELD"
        float confidence "LEGACY_AI_FIELD"
    }
    
    TestResult {
        string id
        string test_session_id
        float pass_rate "LabJack_Primary_Metric"
        float avg_latency_ms "LabJack_Primary_Metric"
        float accuracy "LEGACY_AI_Compatibility"
        float precision "LEGACY_AI_Compatibility"
        float recall "LEGACY_AI_Compatibility"
        float f1_score "LEGACY_AI_Compatibility"
    }
```

**PROBLEM**: Three different status systems in one database:
- `TestSession.status` (User workflow)
- `DetectionEvent.validation_result` (AI validation) 
- `DetectionEvent.latency_result` (LabJack timing)

### 3. API ENDPOINT CONFLICTS

```mermaid
sequenceDiagram
    participant UI as Results Component
    participant API1 as Standard API
    participant API2 as Enhanced API
    participant WS as WebSocket
    participant DB as Database
    
    UI->>API1: GET /api/test-sessions
    API1->>DB: Query TestSession.status
    DB-->>API1: "completed"
    API1-->>UI: {status: "completed"}
    
    UI->>API2: GET /api/results/sessions/{id}/detailed
    API2->>DB: Query DetectionEvent.validation_result
    DB-->>API2: "fail" 
    API2-->>UI: {validation_result: "fail"}
    
    WS->>UI: Real-time update
    WS-->>UI: {status: "Manual"}
    
    Note over UI: THREE DIFFERENT STATUSES!
    Note over UI: Which one to display?
    Note over UI: Default to "Manual" when confused
```

### 4. COMPONENT COUPLING ISSUES

```mermaid
graph LR
    subgraph "Results Component Dependencies"
        A[Results.tsx] --> B[apiService]
        A --> C[getEnhancedTestSessions]  
        A --> D[WebSocket Connection]
        A --> E[Mock Data Generator]
        A --> F[Error Handler]
        
        B --> G[/api/test-sessions]
        C --> H[/api/results/sessions/{id}/detailed]
        D --> I[/api/status-updates]
        
        G --> J[(Database)]
        H --> J
        I --> K[Real-time Service]
        
        F --> L[Fallback Logic]
        L --> M["Manual" Status Assignment]
    end
    
    subgraph "Status Resolution Chain"
        N[API Call] --> O{Success?}
        O -->|Yes| P[Transform Data]
        O -->|No| Q[Try Next API]
        Q --> R{More APIs?}
        R -->|Yes| N
        R -->|No| S[Use Mock Data]
        S --> T["completed" Status]
        P --> U{Valid Status?}
        U -->|Yes| V[Display Status]
        U -->|No| W["Manual" Fallback]
    end
```

### 5. PROPOSED UNIFIED ARCHITECTURE

```mermaid
graph TD
    subgraph "UNIFIED API LAYER"
        A[Results Component] --> B[Unified Status Service]
        B --> C[Status Determination Engine]
        
        C --> D[Business Logic Layer]
        D --> E{Test Type Detection}
        E -->|LabJack Timing| F[Timing-based Status Logic]
        E -->|AI Detection| G[ML-based Status Logic]
        E -->|Manual Testing| H[User-driven Status Logic]
        
        F --> I[LabJack Status Calculator]
        G --> J[AI Validation Calculator]
        H --> K[Manual Status Tracker]
        
        I --> L[(Unified Status Store)]
        J --> L
        K --> L
    end
    
    subgraph "DATA LAYER UNIFICATION"
        L --> M[Status Cache Manager]
        M --> N[(Primary Database)]
        M --> O[(Redis Cache)]
        M --> P[Real-time Sync Service]
        
        P --> Q[WebSocket Manager]
        Q --> R[Status Update Stream]
    end
    
    subgraph "FRONTEND INTEGRATION"
        R --> S[Unified Status Hook]
        S --> T[Results Display Component]
        T --> U[Status Indicator UI]
        
        U --> V{Status Type}
        V -->|PASS| W[Green Success State]
        V -->|FAIL| X[Red Failure State]  
        V -->|PROCESSING| Y[Yellow Processing State]
        V -->|ERROR| Z[Red Error State]
    end
```

### 6. UNIFIED DATA MODEL

```typescript
// SOLUTION: Single Status Interface
interface UnifiedTestStatus {
  // Core Identification
  sessionId: string;
  projectId: string;
  testType: 'labjack_timing' | 'ai_detection' | 'manual_testing';
  
  // Unified Status
  overallStatus: 'pending' | 'running' | 'completed' | 'failed' | 'error';
  
  // Test-Specific Results
  timingResults?: {
    status: 'pass' | 'fail' | 'timeout';
    averageLatency: number;
    passRate: number;
    threshold: number;
  };
  
  aiResults?: {
    status: 'pass' | 'fail' | 'partial';
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
  };
  
  // Metadata
  dataSource: 'api' | 'websocket' | 'cache' | 'computed';
  lastUpdated: string;
  confidence: number; // 0-1 confidence in status accuracy
  
  // Error Handling
  errors?: string[];
  warnings?: string[];
}
```

### 7. STATUS DETERMINATION FLOW

```mermaid
flowchart TD
    A[Status Request] --> B[Unified Status Service]
    B --> C{Test Type}
    
    C -->|LabJack| D[Query DetectionEvents]
    C -->|AI Detection| E[Query TestResults]
    C -->|Manual| F[Query TestSession]
    
    D --> G[Calculate Latency Metrics]
    E --> H[Calculate AI Metrics]
    F --> I[Get User Status]
    
    G --> J{All Timing Pass?}
    J -->|Yes| K[Status: COMPLETED_PASS]
    J -->|No| L[Status: COMPLETED_FAIL]
    J -->|Mixed| M[Status: COMPLETED_PARTIAL]
    J -->|No Data| N[Status: NO_DATA]
    
    H --> O{AI Metrics Good?}
    O -->|Yes| P[Status: AI_PASS]
    O -->|No| Q[Status: AI_FAIL]
    
    I --> R{User Completed?}
    R -->|Yes| S[Status: MANUAL_COMPLETED]
    R -->|No| T[Status: MANUAL_PENDING]
    
    K --> U[Unified Status Response]
    L --> U
    M --> U
    N --> U
    P --> U
    Q --> U
    S --> U
    T --> U
    
    U --> V[Cache Result]
    V --> W[Return to Frontend]
    W --> X[Display Consistent Status]
```

## IMPLEMENTATION STRATEGY

### Phase 1: Immediate Fix (1-2 days)
1. **Create Unified Status Endpoint**: `/api/unified-status/{session_id}`
2. **Update Results Component**: Single API call instead of multiple
3. **Remove Fallback Logic**: Eliminate "Manual" default assignments
4. **Add Proper Error Handling**: Show actual errors instead of hiding them

### Phase 2: Real-time Integration (3-5 days)  
1. **WebSocket Unification**: Single WebSocket for status updates
2. **Cache Strategy**: Unified cache invalidation
3. **State Management**: Centralized status state

### Phase 3: Complete Architecture (1-2 weeks)
1. **API Gateway**: Consolidate all APIs through unified gateway
2. **Business Logic Layer**: Centralized status determination
3. **Database Optimization**: Optimize queries for unified model
4. **Performance Testing**: Ensure sub-100ms response times

## CONCLUSION

The "Manual" status issue stems from **fundamental architectural fragmentation** where multiple systems compete to determine status, leading to inconsistent data flows and default fallback behaviors. The solution requires unified data models, centralized business logic, and elimination of graceful degradation patterns that hide real issues.