# AI Model Validation Platform - Data Flow Diagrams

## 1. Complete User Workflow Data Flow

```mermaid
sequenceDiagram
    participant User as User (Frontend)
    participant Auth as Authentication
    participant API as FastAPI Backend
    participant WS as WebSocket Server
    participant DB as Database
    participant ML as ML Pipeline
    participant HW as LabJack Hardware
    participant Storage as File Storage
    
    Note over User, Storage: Project Creation and Setup
    User->>Auth: Login Request
    Auth->>DB: Validate Credentials
    DB->>Auth: User Data
    Auth->>User: JWT Token
    
    User->>API: Create Project
    API->>DB: Store Project Data
    DB->>API: Project ID
    API->>User: Project Created
    
    Note over User, Storage: Video Upload and Processing
    User->>API: Upload Video Files
    API->>Storage: Store Video Files
    Storage->>API: File Paths
    API->>DB: Store Video Metadata
    API->>ML: Extract Video Properties
    ML->>DB: Store Video Analysis
    API->>User: Upload Complete
    
    Note over User, Storage: Ground Truth Annotation
    User->>API: Request Ground Truth Upload
    API->>Storage: Store Annotation Files
    API->>ML: Process Annotations
    ML->>DB: Store Ground Truth Data
    API->>User: Ground Truth Processed
    
    Note over User, Storage: Test Execution Workflow
    User->>API: Start Test Execution
    API->>WS: Join Test Session Room
    WS->>User: Real-time Connection
    
    loop For Each Video
        API->>ML: Start Detection Pipeline
        ML->>Storage: Load Video File
        ML->>ML: Run YOLOv8 Detection
        ML->>HW: Trigger Timing Signals
        HW->>ML: Precision Timestamps
        ML->>DB: Store Detection Results
        ML->>API: Detection Complete
        API->>WS: Progress Update
        WS->>User: Real-time Progress
    end
    
    API->>ML: Compare with Ground Truth
    ML->>DB: Load Ground Truth Data
    ML->>DB: Store Comparison Results
    API->>Storage: Generate Reports
    Storage->>API: Report Files
    API->>WS: Test Complete
    WS->>User: Final Results
```

## 2. Video Processing Pipeline Data Flow

```mermaid
flowchart TD
    START([User Uploads Video]) --> UPLOAD[Video Upload API]
    UPLOAD --> VALIDATE{Video Validation}
    
    VALIDATE -->|Valid| STORE[Store in File System]
    VALIDATE -->|Invalid| ERROR[Return Error]
    
    STORE --> METADATA[Extract Metadata]
    METADATA --> DB_META[(Store Video Metadata)]
    
    DB_META --> QUEUE[Add to Processing Queue]
    QUEUE --> FRAME_EXTRACT[Frame Extraction]
    
    FRAME_EXTRACT --> YOLO[YOLOv8 Detection]
    YOLO --> DETECTION_RESULTS[(Store Detection Events)]
    
    DETECTION_RESULTS --> TIMING[LabJack Timing Analysis]
    TIMING --> PRECISION_DB[(Store Timing Data)]
    
    PRECISION_DB --> STATUS_UPDATE[Update Video Status]
    STATUS_UPDATE --> WEBSOCKET[Broadcast Progress]
    WEBSOCKET --> FRONTEND[Update UI]
    
    ERROR --> FRONTEND
    
    subgraph "Parallel Processing"
        THUMBNAIL[Generate Thumbnails]
        QUALITY[Quality Assessment]
        PREVIEW[Preview Generation]
    end
    
    FRAME_EXTRACT --> THUMBNAIL
    FRAME_EXTRACT --> QUALITY
    FRAME_EXTRACT --> PREVIEW
    
    THUMBNAIL --> THUMB_STORE[(Thumbnail Storage)]
    QUALITY --> QUALITY_DB[(Quality Metrics)]
    PREVIEW --> PREVIEW_STORE[(Preview Storage)]
    
    style UPLOAD fill:#e1f5fe
    style YOLO fill:#fce4ec
    style DETECTION_RESULTS fill:#f1f8e9
    style WEBSOCKET fill:#fff3e0
```

## 3. Real-Time Communication Data Flow

```mermaid
sequenceDiagram
    participant Client as React Client
    participant WS as WebSocket Server
    participant Room as Room Manager
    participant Redis as Redis Cache
    participant Service as Backend Service
    participant DB as Database
    
    Note over Client, DB: Connection Establishment
    Client->>WS: Connect with Auth Token
    WS->>Redis: Validate Session
    Redis->>WS: Session Data
    WS->>Room: Join Project Room
    Room->>Client: Connection Confirmed
    
    Note over Client, DB: Real-time Updates
    Service->>DB: Update Detection Progress
    DB->>Service: Confirmation
    Service->>WS: Emit Progress Event
    WS->>Room: Broadcast to Room
    Room->>Redis: Cache Message
    Room->>Client: Real-time Update
    
    Note over Client, DB: Bidirectional Communication
    Client->>WS: Start Test Command
    WS->>Service: Process Command
    Service->>DB: Create Test Session
    DB->>Service: Session ID
    Service->>WS: Acknowledge Start
    WS->>Client: Test Started
    
    loop Test Execution
        Service->>WS: Progress Updates
        WS->>Room: Broadcast Progress
        Room->>Client: Real-time Progress
        
        Client->>WS: Status Request
        WS->>Service: Get Current Status
        Service->>DB: Query Status
        DB->>Service: Status Data
        Service->>WS: Status Response
        WS->>Client: Current Status
    end
    
    Service->>WS: Test Complete
    WS->>Room: Broadcast Completion
    Room->>Client: Final Results
    
    Note over Client, DB: Cleanup
    Client->>WS: Disconnect
    WS->>Room: Leave Room
    Room->>Redis: Clean Session
```

## 4. Authentication and Authorization Data Flow

```mermaid
flowchart LR
    subgraph "Authentication Flow"
        LOGIN[Login Request] --> VALIDATE[Validate Credentials]
        VALIDATE --> HASH{Password Check}
        HASH -->|Valid| JWT[Generate JWT]
        HASH -->|Invalid| AUTH_ERROR[Authentication Error]
        JWT --> TOKEN_RESPONSE[Return Token]
    end
    
    subgraph "Authorization Flow"
        API_REQUEST[API Request] --> TOKEN_CHECK[Extract JWT Token]
        TOKEN_CHECK --> TOKEN_VALIDATE{Validate Token}
        TOKEN_VALIDATE -->|Valid| DECODE[Decode User Claims]
        TOKEN_VALIDATE -->|Invalid| AUTH_FAIL[401 Unauthorized]
        DECODE --> PERM_CHECK[Check Permissions]
        PERM_CHECK -->|Authorized| PROCESS[Process Request]
        PERM_CHECK -->|Denied| PERM_FAIL[403 Forbidden]
    end
    
    subgraph "Session Management"
        TOKEN_RESPONSE --> REDIS_SESSION[(Redis Session Store)]
        REDIS_SESSION --> SESSION_TRACK[Track Active Sessions]
        SESSION_TRACK --> EXPIRE_CHECK[Check Expiration]
        EXPIRE_CHECK -->|Valid| CONTINUE[Continue Session]
        EXPIRE_CHECK -->|Expired| REFRESH[Refresh Token]
    end
    
    subgraph "Database Integration"
        VALIDATE --> USER_DB[(User Database)]
        USER_DB --> USER_DATA[User Profile Data]
        USER_DATA --> ROLE_DATA[User Roles & Permissions]
        ROLE_DATA --> AUDIT_LOG[(Audit Log)]
    end
    
    style LOGIN fill:#e1f5fe
    style JWT fill:#e8f5e8
    style REDIS_SESSION fill:#fff3e0
    style USER_DB fill:#f1f8e9
```

## 5. Ground Truth Processing Data Flow

```mermaid
flowchart TB
    START([Ground Truth Upload]) --> FORMAT_CHECK{Format Validation}
    
    FORMAT_CHECK -->|COCO JSON| COCO_PARSER[COCO Parser]
    FORMAT_CHECK -->|YOLO TXT| YOLO_PARSER[YOLO Parser]
    FORMAT_CHECK -->|CVAT XML| CVAT_PARSER[CVAT Parser]
    FORMAT_CHECK -->|Custom JSON| CUSTOM_PARSER[Custom Parser]
    FORMAT_CHECK -->|Invalid| FORMAT_ERROR[Format Error]
    
    COCO_PARSER --> NORMALIZE[Normalize Annotations]
    YOLO_PARSER --> NORMALIZE
    CVAT_PARSER --> NORMALIZE
    CUSTOM_PARSER --> NORMALIZE
    
    NORMALIZE --> VALIDATE_BOUNDS[Validate Bounding Boxes]
    VALIDATE_BOUNDS --> VALIDATE_CLASSES[Validate Object Classes]
    VALIDATE_CLASSES --> FRAME_MAPPING[Map to Video Frames]
    
    FRAME_MAPPING --> STORE_GT[(Store Ground Truth)]
    STORE_GT --> INDEX_SPATIAL[Create Spatial Indices]
    INDEX_SPATIAL --> INDEX_TEMPORAL[Create Temporal Indices]
    
    INDEX_TEMPORAL --> READY[Ground Truth Ready]
    
    subgraph "Quality Checks"
        QC_OVERLAP[Check Overlapping Boxes]
        QC_SIZE[Check Box Sizes]
        QC_COMPLETENESS[Check Completeness]
    end
    
    VALIDATE_BOUNDS --> QC_OVERLAP
    QC_OVERLAP --> QC_SIZE
    QC_SIZE --> QC_COMPLETENESS
    QC_COMPLETENESS --> QUALITY_REPORT[Generate Quality Report]
    
    subgraph "Statistical Analysis"
        CLASS_DIST[Class Distribution]
        SIZE_DIST[Size Distribution]
        TEMPORAL_DIST[Temporal Distribution]
    end
    
    STORE_GT --> CLASS_DIST
    CLASS_DIST --> SIZE_DIST
    SIZE_DIST --> TEMPORAL_DIST
    TEMPORAL_DIST --> STATS_REPORT[Statistics Report]
    
    FORMAT_ERROR --> ERROR_RESPONSE[Return Error]
    
    style FORMAT_CHECK fill:#e1f5fe
    style NORMALIZE fill:#e8f5e8
    style STORE_GT fill:#f1f8e9
    style QUALITY_REPORT fill:#fce4ec
```

## 6. Detection Result Comparison Data Flow

```mermaid
sequenceDiagram
    participant API as Detection API
    participant Loader as Data Loader
    participant GT as Ground Truth DB
    participant Det as Detection Results DB
    participant Matcher as Box Matcher
    participant Calc as Metrics Calculator
    participant Report as Report Generator
    participant Storage as File Storage
    
    API->>Loader: Request Comparison
    Loader->>GT: Load Ground Truth
    GT->>Loader: Ground Truth Boxes
    Loader->>Det: Load Detection Results
    Det->>Loader: Detection Boxes
    
    Loader->>Matcher: Match Boxes (IoU Threshold)
    Matcher->>Matcher: Calculate IoU Matrix
    Matcher->>Matcher: Apply Hungarian Algorithm
    Matcher->>Calc: Matched Pairs + Unmatched
    
    Calc->>Calc: Calculate True Positives
    Calc->>Calc: Calculate False Positives
    Calc->>Calc: Calculate False Negatives
    Calc->>Calc: Calculate Precision
    Calc->>Calc: Calculate Recall
    Calc->>Calc: Calculate F1-Score
    
    Calc->>Report: Metrics Data
    Report->>Report: Generate Visualization
    Report->>Report: Create Summary Tables
    Report->>Storage: Save Report Files
    Storage->>Report: File Paths
    
    Report->>Det: Store Comparison Results
    Det->>API: Comparison Complete
    
    Note over API, Storage: Box Matching Algorithm
    Note over Matcher: IoU >= 0.5 = Match
    Note over Matcher: Multiple matches -> Best IoU
    Note over Matcher: Unmatched GT = False Negative
    Note over Matcher: Unmatched Det = False Positive
```

## 7. File Storage and Retrieval Data Flow

```mermaid
flowchart LR
    subgraph "Upload Flow"
        UPLOAD_REQ[Upload Request] --> VALIDATE_FILE[File Validation]
        VALIDATE_FILE --> CHECK_SIZE{Size Check}
        CHECK_SIZE -->|OK| CHECK_TYPE{Type Check}
        CHECK_SIZE -->|Too Large| SIZE_ERROR[Size Error]
        CHECK_TYPE -->|Valid| STORE_FILE[Store File]
        CHECK_TYPE -->|Invalid| TYPE_ERROR[Type Error]
        STORE_FILE --> GEN_PATH[Generate File Path]
        GEN_PATH --> UPDATE_DB[(Update Database)]
        UPDATE_DB --> UPLOAD_SUCCESS[Upload Success]
    end
    
    subgraph "Retrieval Flow"
        RETRIEVE_REQ[Retrieve Request] --> AUTH_CHECK[Authorization Check]
        AUTH_CHECK -->|Authorized| LOAD_METADATA[(Load Metadata)]
        AUTH_CHECK -->|Unauthorized| ACCESS_DENIED[Access Denied]
        LOAD_METADATA --> FILE_EXISTS{File Exists?}
        FILE_EXISTS -->|Yes| SERVE_FILE[Serve File]
        FILE_EXISTS -->|No| FILE_NOT_FOUND[File Not Found]
        SERVE_FILE --> CACHE_HEADERS[Set Cache Headers]
        CACHE_HEADERS --> STREAM_RESPONSE[Stream Response]
    end
    
    subgraph "Background Processing"
        UPLOAD_SUCCESS --> BG_QUEUE[Background Queue]
        BG_QUEUE --> THUMBNAIL[Generate Thumbnail]
        BG_QUEUE --> METADATA_EXTRACT[Extract Metadata]
        BG_QUEUE --> VIRUS_SCAN[Virus Scan]
        THUMBNAIL --> THUMB_STORE[(Thumbnail Storage)]
        METADATA_EXTRACT --> META_DB[(Metadata Database)]
        VIRUS_SCAN --> SCAN_RESULT[(Scan Results)]
    end
    
    style UPLOAD_REQ fill:#e1f5fe
    style STORE_FILE fill:#e8f5e8
    style UPDATE_DB fill:#f1f8e9
    style BG_QUEUE fill:#fff3e0
```

## 8. Error Handling and Recovery Data Flow

```mermaid
flowchart TD
    ERROR_OCCUR[Error Occurs] --> ERROR_TYPE{Error Type}
    
    ERROR_TYPE -->|Validation Error| VALIDATION_HANDLER[Validation Handler]
    ERROR_TYPE -->|Database Error| DB_HANDLER[Database Handler]
    ERROR_TYPE -->|Network Error| NETWORK_HANDLER[Network Handler]
    ERROR_TYPE -->|Processing Error| PROCESSING_HANDLER[Processing Handler]
    ERROR_TYPE -->|Unknown Error| GENERIC_HANDLER[Generic Handler]
    
    VALIDATION_HANDLER --> LOG_ERROR[(Log Error)]
    DB_HANDLER --> RETRY_LOGIC{Retry Available?}
    NETWORK_HANDLER --> CIRCUIT_BREAKER[Circuit Breaker]
    PROCESSING_HANDLER --> CLEANUP[Cleanup Resources]
    GENERIC_HANDLER --> LOG_ERROR
    
    RETRY_LOGIC -->|Yes| RETRY_OPERATION[Retry Operation]
    RETRY_LOGIC -->|No| LOG_ERROR
    RETRY_OPERATION --> SUCCESS{Success?}
    SUCCESS -->|Yes| RECOVERY_SUCCESS[Recovery Success]
    SUCCESS -->|No| FALLBACK[Use Fallback]
    
    CIRCUIT_BREAKER --> CIRCUIT_STATE{Circuit State}
    CIRCUIT_STATE -->|Closed| ALLOW_REQUEST[Allow Request]
    CIRCUIT_STATE -->|Open| REJECT_REQUEST[Reject Request]
    CIRCUIT_STATE -->|Half-Open| TEST_REQUEST[Test Request]
    
    CLEANUP --> RELEASE_RESOURCES[Release Resources]
    RELEASE_RESOURCES --> LOG_ERROR
    
    LOG_ERROR --> NOTIFY_USER[Notify User]
    FALLBACK --> NOTIFY_USER
    RECOVERY_SUCCESS --> NOTIFY_USER
    REJECT_REQUEST --> NOTIFY_USER
    
    NOTIFY_USER --> ERROR_RESPONSE[Error Response]
    
    subgraph "Monitoring"
        ERROR_RESPONSE --> METRICS[Update Metrics]
        METRICS --> ALERT{Alert Threshold?}
        ALERT -->|Yes| SEND_ALERT[Send Alert]
        ALERT -->|No| MONITOR_CONTINUE[Continue Monitoring]
    end
    
    style ERROR_OCCUR fill:#ffebee
    style LOG_ERROR fill:#fff3e0
    style RECOVERY_SUCCESS fill:#e8f5e8
    style SEND_ALERT fill:#fce4ec
```

## Data Flow Summary

### Key Data Transformation Points

1. **Input Validation**: All external data is validated at API boundaries
2. **Format Normalization**: Different input formats are normalized to common schemas
3. **Processing Pipelines**: Data flows through sequential processing stages
4. **Real-time Broadcasting**: Status updates are broadcast to connected clients
5. **Result Aggregation**: Individual results are aggregated into comprehensive reports
6. **Error Recovery**: Failed operations are retried with exponential backoff
7. **Audit Logging**: All significant operations are logged for compliance

### Performance Considerations

- **Asynchronous Processing**: Long-running tasks are processed asynchronously
- **Caching**: Frequently accessed data is cached in Redis
- **Streaming**: Large files are streamed rather than loaded entirely into memory
- **Connection Pooling**: Database connections are pooled for efficiency
- **Background Tasks**: Non-critical operations are performed in background threads

### Security Considerations

- **Authentication**: All API requests require valid JWT tokens
- **Authorization**: User permissions are checked before data access
- **Input Sanitization**: All user inputs are sanitized before processing
- **Data Encryption**: Sensitive data is encrypted at rest and in transit
- **Audit Trails**: All data modifications are logged with user attribution

This comprehensive data flow documentation shows how information moves through every layer of the AI Model Validation Platform, from user interaction to final result delivery.