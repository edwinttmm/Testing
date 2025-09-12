# AI Model Validation Platform - Component Relationships & Dependencies

## Component Dependency Graph

```mermaid
graph TB
    subgraph "Frontend Components"
        App[App.tsx<br/>Main Application]
        Dashboard[Dashboard<br/>Main Dashboard]
        Projects[Projects<br/>Project Management]
        GroundTruth[GroundTruth<br/>Annotation Management]
        TestExecution[TestExecution<br/>Test Runner]
        Results[Results<br/>Results Viewer]
        DatasetVideos[DatasetVideos<br/>Video Management]
        
        subgraph "Shared Components"
            VideoPlayer[VideoPlayer<br/>Video Playback]
            AnnotationCanvas[AnnotationCanvas<br/>Annotation UI]
            WebSocketHook[useWebSocket<br/>Real-time Updates]
            ApiService[API Service<br/>HTTP Client]
        end
        
        subgraph "UI Components"
            Sidebar[Sidebar<br/>Navigation]
            Header[Header<br/>Top Bar]
            ErrorBoundary[ErrorBoundary<br/>Error Handling]
        end
    end
    
    subgraph "Backend Services"
        MainAPI[main.py<br/>FastAPI Application]
        
        subgraph "API Routers"
            AuthRouter[auth_endpoints.py<br/>Authentication]
            TestRouter[api_enhanced_test.py<br/>Test Execution]
            GTRouter[ground_truth_routes.py<br/>Ground Truth API]
            ResultsRouter[api_comprehensive_results.py<br/>Results API]
        end
        
        subgraph "Business Services"
            ProjectService[Project Service<br/>Project Logic]
            VideoService[Video Service<br/>Video Processing]
            DetectionService[Detection Service<br/>ML Pipeline]
            ValidationService[Validation Service<br/>GT Validation]
            ReportService[Report Service<br/>Report Generation]
        end
        
        subgraph "Core Services"
            DatabaseService[Database Service<br/>ORM Layer]
            AuthService[Auth Service<br/>Security]
            SocketIOService[SocketIO Service<br/>WebSocket Server]
        end
    end
    
    subgraph "Data Layer"
        Models[models.py<br/>SQLAlchemy Models]
        Schemas[schemas.py<br/>Pydantic Schemas]
        CRUD[crud.py<br/>Database Operations]
        Database[(Database<br/>SQLite/PostgreSQL)]
        Redis[(Redis<br/>Cache & Sessions)]
    end
    
    subgraph "External Dependencies"
        YOLOv8[YOLOv8<br/>ML Model]
        LabJack[LabJack<br/>Hardware Interface]
        CVAT[CVAT<br/>Annotation Tool]
    end
    
    %% Frontend Dependencies
    App --> Dashboard
    App --> Projects
    App --> GroundTruth
    App --> TestExecution
    App --> Results
    App --> DatasetVideos
    App --> Sidebar
    App --> Header
    App --> ErrorBoundary
    
    Dashboard --> ApiService
    Projects --> ApiService
    GroundTruth --> ApiService
    GroundTruth --> VideoPlayer
    GroundTruth --> AnnotationCanvas
    TestExecution --> ApiService
    TestExecution --> WebSocketHook
    Results --> ApiService
    DatasetVideos --> ApiService
    DatasetVideos --> VideoPlayer
    
    VideoPlayer --> ApiService
    WebSocketHook --> SocketIOService
    
    %% Backend Dependencies
    MainAPI --> AuthRouter
    MainAPI --> TestRouter
    MainAPI --> GTRouter
    MainAPI --> ResultsRouter
    MainAPI --> SocketIOService
    
    AuthRouter --> AuthService
    TestRouter --> ProjectService
    TestRouter --> VideoService
    TestRouter --> DetectionService
    GTRouter --> ValidationService
    ResultsRouter --> ReportService
    
    ProjectService --> DatabaseService
    VideoService --> DatabaseService
    DetectionService --> DatabaseService
    ValidationService --> DatabaseService
    ReportService --> DatabaseService
    
    DatabaseService --> Models
    DatabaseService --> CRUD
    DatabaseService --> Database
    
    AuthService --> Redis
    SocketIOService --> Redis
    
    %% Schema Dependencies
    AuthRouter --> Schemas
    TestRouter --> Schemas
    GTRouter --> Schemas
    ResultsRouter --> Schemas
    
    Models --> Database
    CRUD --> Models
    CRUD --> Database
    
    %% External Dependencies
    DetectionService --> YOLOv8
    DetectionService --> LabJack
    ValidationService --> CVAT
    
    %% API Communication
    ApiService -.->|HTTP/HTTPS| MainAPI
    WebSocketHook -.->|WebSocket| SocketIOService
    
    style App fill:#e1f5fe
    style MainAPI fill:#f3e5f5
    style Database fill:#f1f8e9
    style YOLOv8 fill:#fce4ec
```

## Detailed Component Dependencies

### 1. Frontend Component Hierarchy

#### Core Application Components

```typescript
// App.tsx - Root component dependencies
App
├── ThemeProvider (Material-UI)
├── BrowserRouter (React Router)
├── ErrorBoundary (Error handling)
├── GlobalErrorHandler (Error management)
├── ApiConnectionStatus (Connection monitoring)
└── Routes
    ├── Dashboard
    ├── Projects  
    ├── GroundTruth
    ├── TestExecution
    ├── Results
    └── DatasetVideos
```

#### Shared Component Dependencies

```typescript
// VideoPlayer component dependencies
VideoPlayer
├── useVideoState (Custom hook)
├── useWebSocket (Real-time updates)
├── Material-UI components
├── HTML5 Video API
└── Custom controls

// AnnotationCanvas component dependencies  
AnnotationCanvas
├── Canvas API
├── Mouse/Touch event handlers
├── Zoom and pan utilities
├── Bounding box utilities
└── WebSocket integration

// useWebSocket hook dependencies
useWebSocket
├── Socket.IO client
├── React useEffect/useState
├── Error handling
├── Reconnection logic
└── Event management
```

### 2. Backend Service Dependencies

#### FastAPI Application Structure

```python
# main.py - Central FastAPI application
main.py
├── FastAPI app instance
├── CORS middleware
├── Authentication middleware  
├── Static file serving
├── Router registration
│   ├── auth_endpoints
│   ├── api_enhanced_test
│   ├── ground_truth_routes
│   └── api_comprehensive_results
├── SocketIO integration
├── Database initialization
└── Startup/shutdown events
```

#### Service Layer Dependencies

```python
# Business service dependencies
ProjectService
├── models.Project (SQLAlchemy model)
├── crud.py (Database operations)
├── schemas.py (Validation)
└── database.py (Session management)

VideoService  
├── models.Video
├── File system operations
├── Video processing utilities
├── ML pipeline integration
└── WebSocket notifications

DetectionService
├── YOLOv8 model integration
├── LabJack hardware interface
├── OpenCV image processing
├── NumPy array operations
└── Result storage

ValidationService
├── Ground truth loading
├── Bounding box matching
├── IoU calculations
├── Performance metrics
└── Report generation
```

### 3. Database Model Relationships

```mermaid
erDiagram
    AuthUser {
        string id PK
        string email UK
        string username UK
        string hashed_password
        boolean is_active
        datetime created_at
    }
    
    UserSession {
        string id PK
        string user_id FK
        string session_token UK
        datetime expires_at
        boolean is_active
    }
    
    Project {
        string id PK
        string name
        string description
        string camera_model
        string camera_view
        string signal_type
        string status
        string owner_id FK
        datetime created_at
    }
    
    Video {
        string id PK
        string filename
        string file_path
        string project_id FK
        string status
        integer duration
        integer frame_count
        datetime uploaded_at
    }
    
    TestSession {
        string id PK
        string project_id FK
        string name
        string status
        json config
        datetime start_time
        datetime end_time
    }
    
    DetectionEvent {
        string id PK
        string video_id FK
        string test_session_id FK
        integer frame_number
        float timestamp
        float confidence
        json bounding_box
        string object_class
    }
    
    GroundTruthObject {
        string id PK
        string video_id FK
        integer frame_number
        float timestamp
        json bounding_box
        string object_class
        string source
    }
    
    Annotation {
        string id PK
        string video_id FK
        string session_id FK
        integer frame_number
        json annotation_data
        string annotator_id
        datetime created_at
    }
    
    AnnotationSession {
        string id PK
        string project_id FK
        string name
        string status
        string annotator_id FK
        datetime created_at
    }
    
    TestResult {
        string id PK
        string test_session_id FK
        string video_id FK
        integer true_positives
        integer false_positives
        integer false_negatives
        float precision
        float recall
        float f1_score
    }
    
    AuthUser ||--o{ UserSession : has
    AuthUser ||--o{ Project : owns
    Project ||--o{ Video : contains
    Project ||--o{ TestSession : runs
    Project ||--o{ AnnotationSession : annotates
    Video ||--o{ DetectionEvent : generates
    Video ||--o{ GroundTruthObject : validated_by
    Video ||--o{ Annotation : annotated_with
    TestSession ||--o{ DetectionEvent : records
    TestSession ||--o{ TestResult : produces
    AnnotationSession ||--o{ Annotation : contains
```

### 4. API Endpoint Dependencies

#### Authentication Flow Dependencies

```python
# Authentication endpoint dependencies
@app.post("/auth/login")
├── UserLoginSchema (Request validation)
├── AuthService.authenticate_user()
│   ├── models.AuthUser
│   ├── Password verification
│   └── Database query
├── JWT token generation
├── Redis session storage
└── UserResponseSchema (Response serialization)

@app.get("/auth/me") 
├── JWT token validation (Dependency)
├── Database user lookup
└── Current user serialization
```

#### Test Execution Dependencies

```python
# Test execution endpoint dependencies  
@app.post("/api/enhanced-test/start-workflow")
├── WorkflowConfigSchema (Validation)
├── Authentication dependency
├── ProjectService.get_project()
├── VideoService.get_project_videos()
├── TestWorkflowOrchestrator.start()
│   ├── DetectionService
│   ├── ValidationService  
│   ├── WebSocket notifications
│   └── Background task creation
└── WorkflowResponseSchema (Response)
```

### 5. Real-Time Communication Dependencies

#### WebSocket Architecture

```python
# Socket.IO server dependencies
socketio_server.py
├── Socket.IO AsyncServer
├── FastAPI integration
├── CORS configuration
├── Authentication middleware
├── Room management
├── Event handlers
│   ├── connect/disconnect
│   ├── start_test_session
│   ├── progress_update
│   └── error_notification
└── Redis adapter (for scaling)
```

#### WebSocket Event Flow

```mermaid
sequenceDiagram
    participant Client as Frontend Client
    participant WS as WebSocket Server  
    participant Service as Backend Service
    participant Redis as Redis Cache
    participant DB as Database
    
    Note over Client, DB: Connection & Room Management
    Client->>WS: Connect with auth token
    WS->>Redis: Validate session
    WS->>Client: Connection confirmed
    Client->>WS: Join project room
    WS->>Redis: Add to room
    
    Note over Client, DB: Real-time Updates
    Service->>DB: Update test progress
    Service->>WS: Emit progress event
    WS->>Redis: Cache event
    WS->>Client: Broadcast to room
    
    Note over Client, DB: Bidirectional Communication
    Client->>WS: Send command
    WS->>Service: Process command
    Service->>WS: Send response
    WS->>Client: Forward response
```

### 6. External Integration Dependencies

#### YOLOv8 ML Model Integration

```python
# Detection service YOLOv8 dependencies
DetectionService
├── ultralytics.YOLO (Model loading)
├── OpenCV (Image preprocessing)
├── PIL (Image handling)
├── NumPy (Array operations)
├── PyTorch (Model inference)
├── CUDA (GPU acceleration - optional)
└── Custom result processing
```

#### LabJack Hardware Integration

```python
# Hardware service dependencies
LabJackService
├── labjack.ljm (LabJack driver)
├── Serial communication
├── GPIO pin management
├── Timing synchronization
├── Error handling
└── Mock implementation (development)
```

### 7. Configuration and Environment Dependencies

#### Configuration Hierarchy

```python
# Configuration dependencies
config.py
├── pydantic.BaseSettings
├── Environment variable loading
├── .env file parsing
├── Default value definitions
├── Validation rules
└── Type conversion

# Environment-specific configs
├── .env.development
├── .env.production  
├── .env.docker
└── .env.example
```

### 8. Testing Dependencies

#### Test Infrastructure

```python
# Test dependencies
conftest.py
├── pytest fixtures
├── Test database setup
├── Mock services
├── Test client creation
└── Cleanup utilities

# Frontend testing
├── Jest test runner
├── React Testing Library
├── MSW (API mocking)
├── WebSocket mocking
└── Component test utilities
```

## Dependency Management Strategies

### 1. Dependency Injection
- Services are injected through FastAPI's dependency system
- Database sessions are provided via dependency injection
- Authentication is enforced through dependencies

### 2. Interface Abstractions
- Abstract base classes define service interfaces
- Mock implementations for testing
- Environment-specific implementations

### 3. Configuration Management
- Centralized configuration through Pydantic settings
- Environment-based configuration overrides
- Runtime configuration validation

### 4. Error Boundary Isolation
- Component-level error boundaries in React
- Service-level exception handling in Python
- Circuit breaker patterns for external dependencies

### 5. State Management
- React Context for global state
- Redux for complex state management
- Server state managed by React Query

This comprehensive component relationship analysis shows how every part of the AI Model Validation Platform connects together, from the smallest UI components to the largest backend services, providing a complete picture of the system's interdependencies.