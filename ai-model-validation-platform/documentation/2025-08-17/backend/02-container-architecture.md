# VRU Detection System - Container Architecture (C4 Level 2)

## System Containers

```mermaid
graph TB
    subgraph External Users
        USR[System Users]
        ADM[Administrators]
    end
    
    subgraph External Systems
        CAM[Vehicle Cameras]
        SIG[Signal Generators]
        STOR[Cloud Storage]
    end
    
    subgraph VRU Detection Platform
        subgraph Frontend Layer
            WEB[Web Application<br/>React + TypeScript]
            API_GW[API Gateway<br/>NGINX + Auth]
        end
        
        subgraph Backend Services
            MAIN[Main API Service<br/>FastAPI + Python]
            DETECT[Detection Engine<br/>PyTorch + YOLOv8]
            SIGNAL[Signal Processor<br/>Real-time I/O]
            VALID[Validation Service<br/>Metrics + Analytics]
        end
        
        subgraph Data Layer
            DB[(Primary Database<br/>PostgreSQL)]
            CACHE[(Redis Cache<br/>Session + Temp Data)]
            FILES[(File Storage<br/>S3 Compatible)]
        end
        
        subgraph Infrastructure
            QUEUE[Message Queue<br/>RabbitMQ]
            MON[Monitoring<br/>Prometheus + Grafana]
            LOG[Logging<br/>ELK Stack)]
        end
    end
    
    USR --> WEB
    ADM --> WEB
    WEB --> API_GW
    API_GW --> MAIN
    
    CAM --> DETECT
    SIG --> SIGNAL
    
    MAIN --> DB
    MAIN --> CACHE
    MAIN --> FILES
    MAIN --> QUEUE
    
    DETECT --> QUEUE
    DETECT --> CACHE
    SIGNAL --> QUEUE
    VALID --> DB
    
    QUEUE --> VALID
    
    MAIN --> MON
    DETECT --> MON
    SIGNAL --> MON
    VALID --> MON
    
    ALL --> LOG
    
    FILES --> STOR
```

## Container Responsibilities

### Frontend Layer

#### Web Application
- **Technology**: React 18, TypeScript, Material-UI
- **Responsibilities**:
  - User interface for all system interactions
  - Real-time dashboard updates via WebSocket
  - Video player with annotation overlay
  - Project and test management interfaces
- **Key Features**:
  - Responsive design for desktop/tablet
  - Accessibility compliance (WCAG 2.1)
  - Progressive web app capabilities
  - Offline-first for critical operations

#### API Gateway
- **Technology**: NGINX with Auth modules
- **Responsibilities**:
  - Request routing and load balancing
  - Authentication and authorization
  - Rate limiting and throttling
  - SSL termination
- **Security Features**:
  - JWT token validation
  - IP whitelisting for admin functions
  - Request logging and monitoring
  - CORS policy enforcement

### Backend Services

#### Main API Service
- **Technology**: FastAPI, Python 3.9+, SQLAlchemy
- **Responsibilities**:
  - Core business logic and data management
  - Project and video lifecycle management
  - User authentication and authorization
  - RESTful API endpoints
- **Key Endpoints**:
  ```
  /api/v1/projects/* - Project management
  /api/v1/videos/* - Video library operations
  /api/v1/test-sessions/* - Test execution
  /api/v1/results/* - Validation results
  /api/v1/admin/* - System administration
  ```

#### Detection Engine
- **Technology**: PyTorch, YOLOv8, OpenCV
- **Responsibilities**:
  - Real-time video processing
  - VRU detection and classification
  - Bounding box generation
  - Confidence scoring
- **Performance Requirements**:
  - Process 30+ FPS for HD video
  - <50ms latency for real-time streams
  - Support for multiple video formats
  - GPU acceleration required

#### Signal Processor
- **Technology**: Python, AsyncIO, GPIO libraries
- **Responsibilities**:
  - Real-time signal capture (GPIO/Network/Serial)
  - Signal timestamping with microsecond precision
  - Signal correlation with video timestamps
  - Hardware interface management
- **Supported Interfaces**:
  - GPIO pins (Raspberry Pi compatible)
  - Network packets (UDP/TCP)
  - Serial communication (RS232/485)

#### Validation Service
- **Technology**: Python, NumPy, SciPy
- **Responsibilities**:
  - Detection accuracy calculation
  - Statistical analysis and reporting
  - Performance metrics computation
  - Test result validation
- **Metrics Calculated**:
  - Precision, Recall, F1-Score
  - Latency measurements
  - False positive/negative rates
  - Temporal accuracy analysis

### Data Layer

#### Primary Database
- **Technology**: PostgreSQL 14+
- **Responsibilities**:
  - Persistent data storage
  - ACID transaction support
  - Complex query optimization
  - Data integrity enforcement
- **Key Tables**:
  - Projects, Videos, TestSessions
  - DetectionEvents, GroundTruthObjects
  - AuditLogs, Users, Configurations

#### Cache Layer
- **Technology**: Redis 6+
- **Responsibilities**:
  - Session data caching
  - Temporary computation results
  - Real-time data buffering
  - Pub/Sub messaging
- **Use Cases**:
  - User session management
  - Detection result caching
  - WebSocket connection state
  - Rate limiting counters

#### File Storage
- **Technology**: S3-compatible object storage
- **Responsibilities**:
  - Video file storage and retrieval
  - Backup and archival
  - Content delivery optimization
  - Metadata preservation
- **Organization**:
  ```
  /videos/{project_id}/{video_id}/
    - original.mp4 (source video)
    - processed.mp4 (annotated)
    - thumbnails/ (preview images)
    - metadata.json (file properties)
  ```

### Infrastructure

#### Message Queue
- **Technology**: RabbitMQ
- **Responsibilities**:
  - Asynchronous task processing
  - Service decoupling
  - Load balancing
  - Retry mechanisms
- **Queue Types**:
  - detection.requests (video processing)
  - validation.tasks (result calculation)
  - notifications.alerts (system events)

#### Monitoring
- **Technology**: Prometheus + Grafana
- **Responsibilities**:
  - System metrics collection
  - Performance monitoring
  - Alerting and notifications
  - Capacity planning
- **Metrics Tracked**:
  - API response times
  - Detection throughput
  - Resource utilization
  - Error rates

#### Logging
- **Technology**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Responsibilities**:
  - Centralized log aggregation
  - Log analysis and search
  - Security event monitoring
  - Compliance reporting

## Communication Patterns

### Synchronous Communications
- **Frontend ↔ API Gateway**: HTTPS/REST
- **API Gateway ↔ Main API**: HTTP/REST
- **Main API ↔ Database**: TCP/SQL
- **Main API ↔ Cache**: TCP/Redis Protocol

### Asynchronous Communications
- **Detection Engine ↔ Message Queue**: AMQP
- **Signal Processor ↔ Message Queue**: AMQP
- **Validation Service ↔ Message Queue**: AMQP
- **Frontend ↔ Backend**: WebSocket (real-time updates)

## Deployment Considerations

### Container Orchestration
- **Platform**: Kubernetes or Docker Swarm
- **Scaling Strategy**: Horizontal scaling for stateless services
- **Resource Requirements**:
  - Detection Engine: GPU-enabled nodes
  - Database: High I/O, persistent storage
  - Cache: Memory-optimized instances

### Network Architecture
- **Load Balancer**: External traffic distribution
- **Service Mesh**: Internal service communication
- **Network Policies**: Security isolation between services
- **Ingress Controllers**: External access management

### Data Flow Security
- **Encryption**: TLS 1.3 for all communications
- **Authentication**: JWT tokens with refresh mechanism
- **Authorization**: RBAC with fine-grained permissions
- **Audit Trail**: Complete request/response logging

## Scalability Strategy

### Horizontal Scaling
- **Web Application**: Multiple replicas behind load balancer
- **API Services**: Auto-scaling based on CPU/memory usage
- **Detection Engine**: Queue-based scaling with GPU resources
- **Database**: Read replicas for query distribution

### Performance Optimization
- **Caching Strategy**: Multi-level caching (browser, CDN, Redis)
- **Database Optimization**: Connection pooling, query optimization
- **Content Delivery**: CDN for static assets and videos
- **Resource Management**: CPU/GPU resource allocation