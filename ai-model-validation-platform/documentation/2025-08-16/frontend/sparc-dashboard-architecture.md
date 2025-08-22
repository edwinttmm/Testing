# SPARC+TDD Dashboard Fix Architecture

## 🏗️ **A**rchitecture Phase - System Design

### 1. Overall System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Application                     │
├─────────────────────────────────────────────────────────────┤
│  React Components Layer                                     │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │   Pages     │ Components  │   Layouts   │     UI      │ │
│  │ Dashboard   │  ErrorBnd   │  Sidebar    │   Cards     │ │
│  │ Projects    │  Loading    │  Header     │  Buttons    │ │
│  │ Videos      │  Forms      │  Main       │  Dialogs    │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  State Management Layer                                     │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │   Context   │   Hooks     │   Cache     │  Storage    │ │
│  │ AppContext  │ useApi      │ ApiCache    │ LocalStore  │ │
│  │ ErrorCtx    │ useWS       │ QueryCache  │ SessionStr  │ │
│  │ ThemeCtx    │ useUpload   │ MemCache    │ IndexedDB   │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Services Layer                                             │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │ API Service │ WebSocket   │ Upload Svc  │ Error Svc   │ │
│  │ HttpClient  │ RealtimeWS  │ FileUpload  │ ErrorLog    │ │
│  │ RetryLogic  │ Heartbeat   │ Progress    │ Analytics   │ │
│  │ Interceptor │ Reconnect   │ Validation  │ Monitoring  │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Utilities Layer                                            │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │ Error Utils │ Cache Utils │ Date Utils  │ Validation  │ │
│  │ ErrorTypes  │ LRU Cache   │ Formatters  │ Schemas     │ │
│  │ Boundaries  │ Persistence │ Timezone    │ Sanitizers  │ │
│  │ Reporting   │ Compression │ Relative    │ Types       │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
└─────────────────────────────────────────────────────────────┘

                          ↕ HTTP/WebSocket ↕

┌─────────────────────────────────────────────────────────────┐
│                     Backend Services                        │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│  │ REST API    │ WebSocket   │ File Server │ Database    │ │
│  │ FastAPI     │ Socket.IO   │ Upload API  │ PostgreSQL  │ │
│  │ /api/v1/*   │ /ws/*       │ /files/*    │ Tables      │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2. Component Architecture Diagram

```
App.tsx
├── ErrorBoundary (App Level)
│   ├── ThemeProvider
│   │   ├── Router
│   │   │   ├── ErrorBoundary (Router Level)
│   │   │   │   ├── Layout
│   │   │   │   │   ├── Sidebar (ErrorBoundary wrapped)
│   │   │   │   │   ├── Header (ErrorBoundary wrapped) 
│   │   │   │   │   └── MainContent
│   │   │   │   │       └── Routes
│   │   │   │   │           ├── Dashboard (ErrorBoundary wrapped)
│   │   │   │   │           ├── Projects (ErrorBoundary wrapped)
│   │   │   │   │           ├── GroundTruth (ErrorBoundary wrapped)
│   │   │   │   │           ├── TestExecution (ErrorBoundary wrapped)
│   │   │   │   │           ├── Results (ErrorBoundary wrapped)
│   │   │   │   │           └── Datasets (ErrorBoundary wrapped)
```

### 3. Data Flow Architecture

#### 3.1 Request Flow
```
Component → Hook → Service → API → Backend
    ↓        ↓       ↓       ↓       ↓
  Render   State   Cache   HTTP   Database
    ↑        ↑       ↑       ↑       ↑  
Component ← Hook ← Service ← API ← Backend
```

#### 3.2 Error Flow
```
Error Occurrence
    ↓
Error Boundary (Component Level)
    ↓
Error Classification & Logging
    ↓
Recovery Strategy Decision
    ├── Retry (Transient Errors)
    ├── Fallback (Service Errors) 
    ├── User Action (Input Errors)
    └── Report (Critical Errors)
```

#### 3.3 State Management Flow
```
User Action
    ↓
Component Event Handler
    ↓
Custom Hook
    ├── Local State Update
    ├── Cache Update
    ├── API Request (if needed)
    └── Context Update (if global)
    ↓
Component Re-render
    ↓
UI Update
```

### 4. Service Layer Design

#### 4.1 API Service Architecture
```typescript
interface ApiServiceArchitecture {
  // Core HTTP Client
  httpClient: AxiosInstance
  
  // Request/Response Processing
  interceptors: {
    request: RequestInterceptor[]
    response: ResponseInterceptor[]
  }
  
  // Error Handling
  errorHandler: ErrorHandlerService
  
  // Caching Layer
  cache: {
    memory: MemoryCache
    storage: PersistentCache
    strategy: CacheStrategy
  }
  
  // Retry Logic
  retry: {
    maxRetries: number
    backoffStrategy: BackoffStrategy
    retryableErrors: ErrorCode[]
  }
  
  // Request Deduplication
  deduplication: {
    pendingRequests: Map<string, Promise>
    keyGenerator: (config) => string
  }
}
```

#### 4.2 WebSocket Service Architecture
```typescript
interface WebSocketServiceArchitecture {
  // Connection Management
  connection: {
    instance: WebSocket
    state: ConnectionState
    url: string
    protocols: string[]
  }
  
  // Reconnection Logic
  reconnection: {
    maxAttempts: number
    currentAttempts: number
    backoffStrategy: BackoffStrategy
    lastDisconnectTime: number
  }
  
  // Message Handling
  messaging: {
    subscribers: Map<string, Set<Function>>
    messageQueue: Message[]
    acknowledgments: Map<string, Function>
  }
  
  // Health Monitoring
  health: {
    heartbeatInterval: number
    heartbeatTimer: Timer
    lastPingTime: number
    lastPongTime: number
  }
}
```

### 5. Error Handling Architecture

#### 5.1 Error Hierarchy
```
AppError (Base)
├── NetworkError
│   ├── ConnectionError
│   ├── TimeoutError
│   └── DNSError
├── ApiError
│   ├── ClientError (4xx)
│   ├── ServerError (5xx)
│   └── ValidationError
├── WebSocketError
│   ├── ConnectionLostError
│   ├── MessageError
│   └── ProtocolError
├── FileError
│   ├── UploadError
│   ├── ValidationError
│   └── StorageError
└── ComponentError
    ├── RenderError
    ├── StateError
    └── PropsError
```

#### 5.2 Error Boundary Levels
```
App Level (Catches All)
├── Router Level (Navigation Errors)
├── Layout Level (UI Structure Errors)
└── Component Level (Feature-Specific Errors)
    ├── Page Level (Page-Specific Errors)
    └── Widget Level (Component-Specific Errors)
```

### 6. Caching Architecture

#### 6.1 Multi-Layer Cache Strategy
```
Request
    ↓
Memory Cache (L1) - Immediate access
    ↓ (miss)
Session Storage (L2) - Tab persistence
    ↓ (miss)
Local Storage (L3) - Cross-session persistence
    ↓ (miss)
IndexedDB (L4) - Large data persistence
    ↓ (miss)
Network Request
    ↓
Update all cache layers
```

#### 6.2 Cache Invalidation Strategy
```typescript
interface CacheInvalidationStrategy {
  // Time-based
  ttl: {
    default: 5 * 60 * 1000,     // 5 minutes
    dashboard: 2 * 60 * 1000,   // 2 minutes
    projects: 10 * 60 * 1000,   // 10 minutes
    static: 24 * 60 * 60 * 1000 // 24 hours
  }
  
  // Event-based
  triggers: {
    'project.created': ['projects', 'dashboard'],
    'project.updated': ['projects/:id', 'dashboard'],
    'project.deleted': ['projects', 'dashboard'],
    'video.uploaded': ['projects/:id', 'videos', 'dashboard']
  }
  
  // Pattern-based
  patterns: {
    invalidatePattern: (pattern: string) => void
    invalidateByTag: (tag: string) => void
  }
}
```

### 7. File Upload Architecture

#### 7.1 Upload Flow
```
File Selection
    ↓
Client-side Validation
    ├── File Type Check
    ├── File Size Check  
    ├── File Name Validation
    └── Security Scan (Future)
    ↓
Chunk Creation (Large Files)
    ↓
Upload Queue Management
    ├── Parallel Uploads (Limited)
    ├── Priority Queue
    └── Retry Queue
    ↓
Progress Tracking
    ├── Individual File Progress
    ├── Overall Progress
    └── Speed Calculation
    ↓ 
Server Processing
    ├── File Storage
    ├── Metadata Extraction
    ├── Validation
    └── Database Update
    ↓
Client Notification
    ├── Success Callback
    ├── Error Handling
    └── UI Update
```

### 8. Real-time Communication Architecture

#### 8.1 WebSocket Event Flow
```
Client Event Emission
    ↓
WebSocket Send
    ↓
Server Event Handler
    ↓
Business Logic Processing
    ↓
Database Update (if needed)
    ↓
Server Event Broadcast
    ↓
Client Event Reception
    ↓
State Update
    ↓
Component Re-render
```

#### 8.2 Event Types & Routing
```typescript
interface RealtimeEventArchitecture {
  // System Events
  system: {
    'connection.established': ConnectionInfo
    'connection.lost': DisconnectionReason
    'heartbeat.ping': Timestamp
    'heartbeat.pong': Timestamp
  }
  
  // Dashboard Events  
  dashboard: {
    'stats.updated': DashboardStats
    'chart.updated': ChartData
    'alert.triggered': AlertInfo
  }
  
  // Project Events
  projects: {
    'project.created': Project
    'project.updated': ProjectUpdate
    'project.deleted': ProjectId
  }
  
  // Test Execution Events
  testing: {
    'test.started': TestSession
    'test.progress': TestProgress
    'test.completed': TestResults
    'detection.found': DetectionEvent
  }
}
```

### 9. Testing Architecture

#### 9.1 Test Pyramid Structure
```
E2E Tests (Few)
├── Dashboard Full Flow
├── Project Creation Flow
├── Video Upload Flow
└── Test Execution Flow

Integration Tests (Some)
├── API Integration
├── WebSocket Integration
├── File Upload Integration
└── Error Handling Integration

Unit Tests (Many)
├── Component Tests
├── Hook Tests  
├── Service Tests
├── Utility Tests
└── Error Boundary Tests
```

#### 9.2 Test Data Management
```
Test Data Architecture
├── Fixtures (Static Data)
├── Factories (Dynamic Data Generation)
├── Mocks (External Dependencies)
├── Stubs (Controlled Responses)
└── Test Database (Integration Tests)
```

### 10. Performance Architecture

#### 10.1 Loading Strategy
```
Initial Load
├── Critical CSS (Inline)
├── Essential JS Bundle
└── Core UI Components

Progressive Enhancement
├── Secondary Features (Code Splitting)
├── Heavy Dependencies (Lazy Loading)
├── Non-Critical Assets (Defer)
└── Analytics & Tracking (Async)

Background Loading
├── Route Prefetching
├── Data Prefetching
├── Asset Preloading
└── Service Worker Caching
```

#### 10.2 Rendering Optimization
```
Component Optimization
├── React.memo (Pure Components)
├── useMemo (Expensive Calculations)
├── useCallback (Stable References)
├── Virtualization (Large Lists)
└── Suspense (Async Components)

State Optimization
├── State Colocation
├── Context Splitting
├── Reducer Patterns
├── Immutable Updates
└── Selective Subscriptions
```

### 11. Security Architecture

#### 11.1 Client-side Security
```
Input Validation
├── Form Validation
├── File Type Validation
├── Size Limitations
└── Content Sanitization

XSS Prevention
├── Content Security Policy
├── Output Encoding
├── DOM Sanitization
└── Trusted Types (Future)

Data Protection
├── Sensitive Data Masking
├── Local Storage Encryption
├── Memory Cleanup
└── Debug Information Filtering
```

### 12. Monitoring & Observability

#### 12.1 Error Monitoring
```
Error Collection
├── JavaScript Errors
├── Promise Rejections
├── Network Failures
└── Performance Issues

Error Analysis
├── Error Categorization
├── Impact Assessment  
├── Root Cause Analysis
└── Resolution Tracking

Error Response
├── Automatic Recovery
├── User Notifications
├── Support Escalation
└── Fix Deployment
```

---

**Next Phase**: SPARC Refinement - TDD implementation and optimization strategies