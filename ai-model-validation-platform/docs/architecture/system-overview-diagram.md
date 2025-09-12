# AI Model Validation Platform - System Overview Architecture

## High-Level System Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        WEB[React Frontend Application]
        MOBILE[Mobile/Tablet Interface]
        API_DOC[API Documentation]
    end
    
    subgraph "API Gateway Layer"
        LB[Load Balancer/Nginx]
        CORS[CORS Middleware]
        AUTH_MW[Authentication Middleware]
        RATE_LIMIT[Rate Limiting]
    end
    
    subgraph "Application Service Layer"
        subgraph "FastAPI Backend Services"
            MAIN_API[Main FastAPI Application]
            AUTH_API[Authentication API]
            TEST_API[Test Execution API]
            GT_API[Ground Truth API]
            RESULT_API[Results API]
            WS_API[WebSocket API]
        end
        
        subgraph "Business Logic Services"
            PROJECT_SVC[Project Management Service]
            VIDEO_SVC[Video Processing Service]
            DETECTION_SVC[Detection Pipeline Service]
            VALIDATION_SVC[Validation Service]
            REPORT_SVC[Report Generation Service]
        end
    end
    
    subgraph "Real-Time Communication"
        SOCKETIO[Socket.IO Server]
        WS_MGR[WebSocket Manager]
        ROOM_MGR[Room Management]
        NOTIFICATION[Notification Service]
    end
    
    subgraph "Processing Pipeline"
        subgraph "ML/AI Processing"
            YOLO[YOLOv8 Detection Engine]
            ML_PIPELINE[ML Processing Pipeline]
            GT_PROCESSOR[Ground Truth Processor]
            RESULT_ANALYZER[Result Analysis Engine]
        end
        
        subgraph "Hardware Integration"
            LABJACK[LabJack Hardware Service]
            SIGNAL_PROC[Signal Processing]
            TIMING_SVC[Precision Timing Service]
        end
    end
    
    subgraph "Data Persistence Layer"
        subgraph "Databases"
            MAIN_DB[(SQLite/PostgreSQL<br/>Primary Database)]
            REDIS[(Redis Cache<br/>Session & Queue)]
            TSDB[(Time Series DB<br/>Detection Events)]
        end
        
        subgraph "File Storage"
            VIDEO_STORE[Video File Storage]
            GT_STORE[Ground Truth Storage]
            REPORT_STORE[Report Storage]
            LOG_STORE[Log Storage]
        end
    end
    
    subgraph "External Integrations"
        CVAT[CVAT Annotation Tool]
        CLOUD_STORAGE[Cloud Storage (S3/GCS)]
        MONITORING[Monitoring Services]
        EMAIL[Email/Notification Services]
    end
    
    %% User Interface Connections
    WEB --> LB
    MOBILE --> LB
    
    %% API Gateway Connections
    LB --> CORS
    CORS --> AUTH_MW
    AUTH_MW --> RATE_LIMIT
    RATE_LIMIT --> MAIN_API
    
    %% Main API Connections
    MAIN_API --> AUTH_API
    MAIN_API --> TEST_API
    MAIN_API --> GT_API
    MAIN_API --> RESULT_API
    MAIN_API --> WS_API
    
    %% Service Layer Connections
    TEST_API --> PROJECT_SVC
    TEST_API --> VIDEO_SVC
    TEST_API --> DETECTION_SVC
    GT_API --> VALIDATION_SVC
    RESULT_API --> REPORT_SVC
    
    %% Real-time Communication
    WS_API --> SOCKETIO
    SOCKETIO --> WS_MGR
    WS_MGR --> ROOM_MGR
    ROOM_MGR --> NOTIFICATION
    
    %% Processing Pipeline Connections
    VIDEO_SVC --> YOLO
    DETECTION_SVC --> ML_PIPELINE
    VALIDATION_SVC --> GT_PROCESSOR
    REPORT_SVC --> RESULT_ANALYZER
    
    %% Hardware Integration
    DETECTION_SVC --> LABJACK
    LABJACK --> SIGNAL_PROC
    SIGNAL_PROC --> TIMING_SVC
    
    %% Database Connections
    PROJECT_SVC --> MAIN_DB
    VIDEO_SVC --> MAIN_DB
    DETECTION_SVC --> MAIN_DB
    VALIDATION_SVC --> MAIN_DB
    REPORT_SVC --> MAIN_DB
    
    %% Cache Connections
    AUTH_API --> REDIS
    WS_MGR --> REDIS
    SOCKETIO --> REDIS
    
    %% Time Series Data
    DETECTION_SVC --> TSDB
    TIMING_SVC --> TSDB
    
    %% File Storage Connections
    VIDEO_SVC --> VIDEO_STORE
    VALIDATION_SVC --> GT_STORE
    REPORT_SVC --> REPORT_STORE
    PROJECT_SVC --> LOG_STORE
    
    %% External Integration Connections
    GT_API --> CVAT
    REPORT_SVC --> CLOUD_STORAGE
    MAIN_API --> MONITORING
    NOTIFICATION --> EMAIL
    
    %% Styling
    classDef frontend fill:#e1f5fe
    classDef api fill:#f3e5f5
    classDef service fill:#e8f5e8
    classDef realtime fill:#fff3e0
    classDef processing fill:#fce4ec
    classDef storage fill:#f1f8e9
    classDef external fill:#f5f5f5
    
    class WEB,MOBILE,API_DOC frontend
    class LB,CORS,AUTH_MW,RATE_LIMIT,MAIN_API,AUTH_API,TEST_API,GT_API,RESULT_API,WS_API api
    class PROJECT_SVC,VIDEO_SVC,DETECTION_SVC,VALIDATION_SVC,REPORT_SVC service
    class SOCKETIO,WS_MGR,ROOM_MGR,NOTIFICATION realtime
    class YOLO,ML_PIPELINE,GT_PROCESSOR,RESULT_ANALYZER,LABJACK,SIGNAL_PROC,TIMING_SVC processing
    class MAIN_DB,REDIS,TSDB,VIDEO_STORE,GT_STORE,REPORT_STORE,LOG_STORE storage
    class CVAT,CLOUD_STORAGE,MONITORING,EMAIL external
```

## System Architecture Layers

### 1. User Interface Layer
- **React Frontend**: Modern TypeScript/React application with Material-UI
- **Mobile Interface**: Responsive design supporting tablets and mobile devices
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

### 2. API Gateway Layer
- **Load Balancer**: Nginx reverse proxy for high availability
- **CORS Middleware**: Cross-origin resource sharing configuration
- **Authentication Middleware**: JWT token validation and user authentication
- **Rate Limiting**: API request throttling and DDoS protection

### 3. Application Service Layer

#### FastAPI Backend Services
- **Main API**: Central FastAPI application serving as the primary endpoint
- **Authentication API**: User management, login, and security
- **Test Execution API**: Automated test workflow management
- **Ground Truth API**: Annotation and validation data management
- **Results API**: Test results processing and reporting
- **WebSocket API**: Real-time communication endpoints

#### Business Logic Services
- **Project Management**: Project lifecycle and configuration management
- **Video Processing**: Video upload, validation, and preprocessing
- **Detection Pipeline**: AI model execution and result processing  
- **Validation Service**: Ground truth comparison and accuracy calculation
- **Report Generation**: Automated report creation and export

### 4. Real-Time Communication Layer
- **Socket.IO Server**: Bidirectional real-time communication
- **WebSocket Manager**: Connection lifecycle and message routing
- **Room Management**: Session-based channel management
- **Notification Service**: Real-time status updates and alerts

### 5. Processing Pipeline Layer

#### ML/AI Processing
- **YOLOv8 Detection Engine**: Computer vision model for object detection
- **ML Processing Pipeline**: Data preprocessing and model inference
- **Ground Truth Processor**: Annotation data processing and validation
- **Result Analysis Engine**: Statistical analysis and performance metrics

#### Hardware Integration
- **LabJack Hardware Service**: Hardware interface for precision timing
- **Signal Processing**: Digital signal analysis and validation
- **Precision Timing Service**: High-accuracy timestamp management

### 6. Data Persistence Layer

#### Databases
- **Primary Database**: SQLite (development) / PostgreSQL (production)
- **Redis Cache**: Session storage, queues, and real-time data
- **Time Series Database**: High-frequency detection event storage

#### File Storage
- **Video Storage**: Raw and processed video file management
- **Ground Truth Storage**: Annotation files and validation data
- **Report Storage**: Generated reports and analysis results
- **Log Storage**: Application logs and audit trails

### 7. External Integrations
- **CVAT Integration**: Computer Vision Annotation Tool for data labeling
- **Cloud Storage**: AWS S3/Google Cloud Storage for scalable file storage
- **Monitoring Services**: Application performance monitoring and alerting
- **Email/Notification**: External communication and alert systems

## Key Architectural Principles

### 1. Microservices Architecture
- Services are loosely coupled and independently deployable
- Each service has a single responsibility
- Inter-service communication via well-defined APIs

### 2. Event-Driven Architecture  
- Real-time updates through WebSocket connections
- Asynchronous processing for long-running tasks
- Event-based communication between components

### 3. Layered Architecture
- Clear separation of concerns across layers
- Dependencies flow downward through layers
- Each layer provides services to the layer above

### 4. Scalable Design
- Horizontal scaling capability at each layer
- Stateless service design where possible
- Load balancing and caching strategies

### 5. Security-First Approach
- Authentication and authorization at multiple levels
- Input validation and sanitization
- Secure communication protocols (HTTPS/WSS)

## Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| Frontend | React 18, TypeScript, Material-UI, Socket.IO Client |
| Backend API | FastAPI, Python 3.11+, Pydantic, SQLAlchemy |
| Real-time | Socket.IO, WebSocket, Redis |
| ML/AI | YOLOv8, OpenCV, NumPy, PyTorch |
| Database | SQLite/PostgreSQL, Redis, InfluxDB (optional) |
| Hardware | LabJack U3/U6, GPIO, Serial Communication |
| Infrastructure | Docker, Nginx, SSL/TLS, Cloud Storage |
| Monitoring | Prometheus, Grafana, Application Logs |

## Deployment Architecture

The system supports multiple deployment scenarios:

1. **Development**: Single-machine deployment with SQLite
2. **Staging**: Multi-container deployment with PostgreSQL
3. **Production**: Kubernetes cluster with load balancing and redundancy
4. **Cloud**: Managed services deployment on AWS/GCP/Azure

This architecture provides a robust, scalable foundation for AI model validation with comprehensive real-time monitoring, hardware integration, and automated testing capabilities.