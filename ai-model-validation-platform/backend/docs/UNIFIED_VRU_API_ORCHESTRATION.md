# Unified VRU API Orchestration Layer
## SPARC Implementation: Complete System Architecture

### Executive Summary

The Unified VRU API Orchestration Layer provides a comprehensive, production-ready API system that coordinates all VRU (Vulnerable Road User) services including ML inference, camera integration, validation engine, project workflow management, and ground truth management. The system is designed for external access via IP `155.138.239.131` with full WebSocket support and memory coordination.

### System Architecture

```mermaid
graph TB
    subgraph "External Access Layer"
        EXT[External IP: 155.138.239.131]
        LB[Load Balancer/Nginx]
        SSL[SSL/TLS Termination]
    end
    
    subgraph "Unified VRU API Orchestration"
        MAIN[unified_vru_api.py]
        COORD[service_coordination_middleware.py]
        WS[websocket_orchestration.py]
        ERROR[error_handling_monitoring.py]
    end
    
    subgraph "Core VRU Services"
        ML[ML Inference Engine]
        CAM[Camera Integration]
        VAL[Validation Engine]
        PROJ[Project Workflow]
        GT[Ground Truth Service]
    end
    
    subgraph "Data & Communication"
        DB[(Database)]
        MEM[Memory Coordination<br/>vru-api-orchestration]
        SOCKET[WebSocket Connections]
    end
    
    EXT --> LB
    LB --> SSL
    SSL --> MAIN
    
    MAIN --> COORD
    MAIN --> WS
    MAIN --> ERROR
    
    COORD --> ML
    COORD --> CAM
    COORD --> VAL
    COORD --> PROJ
    COORD --> GT
    
    WS --> SOCKET
    ERROR --> MEM
    
    ML --> DB
    CAM --> DB
    VAL --> DB
    PROJ --> DB
    GT --> DB
```

### Component Overview

| Component | File | Purpose | Key Features |
|-----------|------|---------|--------------|
| **Main Orchestrator** | `unified_vru_api.py` | Central API coordination | FastAPI integration, service routing, external IP support |
| **Service Coordination** | `service_coordination_middleware.py` | Service management | Load balancing, circuit breaker, health monitoring |
| **WebSocket Orchestration** | `websocket_orchestration.py` | Real-time communication | Connection management, message routing, broadcasting |
| **Error Handling & Monitoring** | `error_handling_monitoring.py` | System reliability | Error tracking, performance monitoring, alerting |
| **Integration Layer** | `main_integration.py` | Legacy compatibility | Seamless integration with existing main.py |
| **External Access Config** | `external_access_config.py` | Network configuration | External IP setup, firewall rules, SSL configuration |
| **Testing Suite** | `validation_testing_suite.py` | Quality assurance | Comprehensive API testing, performance validation |

### API Endpoints

#### Core Unified API Endpoints

```yaml
Base URL: http://155.138.239.131:8000/api/v1/

Health & Status:
  GET /health                    - System health check
  GET /api/unified/status        - Comprehensive system status
  GET /api/integration/health    - Integration layer health
  GET /api/coordination/status   - Service coordination status

ML Inference:
  POST /ml/process_video         - Process video for ML inference
  GET /ml/annotations/{video_id} - Get ML-generated annotations

Camera Integration:
  POST /camera/add              - Add camera configuration
  GET /camera/status            - Get camera status
  GET /camera/stats             - Get camera statistics

Validation:
  POST /validation/validate_session - Validate test session

Project Workflow:
  POST /projects/create         - Create project with workflow
  GET /projects/{id}/status     - Get project status
  POST /projects/{id}/execute_tests - Execute project tests

WebSocket:
  WS /ws                        - Main WebSocket endpoint
  WS /ws/camera                 - Camera-specific WebSocket
```

#### Request/Response Examples

**Health Check**
```http
GET /api/v1/health
```
```json
{
  "status": "healthy",
  "services": {
    "ml_inference": {"status": "healthy", "response_time_ms": 12.5},
    "camera_integration": {"status": "healthy", "response_time_ms": 8.3},
    "validation_engine": {"status": "healthy", "response_time_ms": 15.2},
    "project_workflow": {"status": "healthy", "response_time_ms": 9.7}
  },
  "external_ip": "155.138.239.131",
  "timestamp": "2025-08-27T07:45:00.000Z"
}
```

**ML Inference**
```http
POST /api/v1/ml/process_video
Content-Type: application/json

{
  "video_id": "video_123",
  "video_path": "/path/to/video.mp4",
  "processing_type": "ground_truth",
  "options": {
    "model_type": "yolo",
    "confidence_threshold": 0.8
  }
}
```
```json
{
  "video_id": "video_123",
  "status": "completed",
  "total_frames": 1500,
  "total_detections": 245,
  "processing_time_ms": 12500,
  "results": {
    "pedestrian_count": 120,
    "cyclist_count": 85,
    "motorcyclist_count": 40
  }
}
```

**Camera Configuration**
```http
POST /api/v1/camera/add
Content-Type: application/json

{
  "camera_id": "camera_001",
  "camera_type": "ip_camera",
  "connection_url": "155.138.239.131:8080",
  "format": "mjpeg",
  "resolution": [1920, 1080],
  "fps": 30,
  "external_ip": "155.138.239.131"
}
```
```json
{
  "success": true,
  "camera_id": "camera_001",
  "status": "configured",
  "message": "Camera added successfully"
}
```

### WebSocket Communication

#### Connection Setup
```javascript
const websocket = new WebSocket('ws://155.138.239.131:8000/api/v1/ws');

websocket.onopen = function(event) {
    console.log('Connected to VRU API WebSocket');
    
    // Subscribe to services
    websocket.send(JSON.stringify({
        type: 'subscribe',
        subscriptions: ['ml_inference', 'camera_updates', 'validation_results']
    }));
};
```

#### Message Types
```javascript
// Ping/Pong for connection health
{
    type: 'ping',
    timestamp: '2025-08-27T07:45:00.000Z'
}

// Service updates
{
    type: 'ml_inference_update',
    data: {
        video_id: 'video_123',
        progress: 75,
        detections_found: 180
    }
}

// Camera frame updates
{
    type: 'camera_frame_update',
    data: {
        camera_id: 'camera_001',
        timestamp: '2025-08-27T07:45:00.000Z',
        detection_count: 3,
        confidence_avg: 0.87
    }
}

// Validation results
{
    type: 'validation_result',
    data: {
        session_id: 'session_456',
        validation_status: 'passed',
        overall_score: 0.92,
        metrics: {
            precision: 0.89,
            recall: 0.85,
            f1_score: 0.87
        }
    }
}
```

### Service Coordination Patterns

#### Circuit Breaker Pattern
```python
# Circuit breaker configuration
circuit_breaker_config = {
    "failure_threshold": 5,      # Open after 5 failures
    "recovery_timeout": 60,      # Try recovery after 60 seconds
    "request_timeout": 30        # Request timeout in seconds
}

# States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
```

#### Load Balancing Strategies
```python
# Available strategies
strategies = {
    "round_robin": "Distribute requests evenly",
    "weighted_round_robin": "Distribute based on service weights",
    "least_connections": "Route to service with fewest connections", 
    "health_based": "Route to healthiest service (fastest response)",
    "random": "Random distribution"
}
```

#### Service Discovery
```python
# Service registration
service_instance = ServiceInstance(
    service_id="ml_inference_001",
    service_name="ml_inference",
    host="localhost",
    port=8000,
    health_endpoint="/api/v1/health",
    weight=10,
    metadata={"type": "ml", "capability": "yolo_detection"}
)
```

### Memory Coordination

#### Namespace: `vru-api-orchestration`

```python
# Store coordination data
memory_coordinator.store(
    key="service_status:ml_inference",
    value={
        "status": "healthy",
        "last_check": "2025-08-27T07:45:00.000Z",
        "response_time_ms": 12.5
    },
    ttl_seconds=300  # 5 minutes
)

# Retrieve coordination data
status = memory_coordinator.retrieve("service_status:ml_inference")
```

#### Key Patterns
- `service_status:{service_name}` - Service health status
- `request_response:{request_id}` - Request/response tracking
- `performance_metrics:{metric_type}` - Performance data
- `error_events:{error_id}` - Error tracking
- `websocket_connections:{connection_id}` - WebSocket state

### External Access Configuration

#### Network Setup for 155.138.239.131

**Firewall Rules (iptables)**
```bash
# Allow HTTP traffic
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Allow HTTPS traffic
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow API traffic
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

**Nginx Configuration**
```nginx
upstream vru_api_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name 155.138.239.131;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=1000r/m;
    
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://vru_api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # WebSocket support
    location /api/v1/ws {
        proxy_pass http://vru_api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

### Performance Characteristics

#### Response Time Targets
- Health endpoints: < 50ms
- ML inference: < 500ms (varies by video size)
- Camera operations: < 100ms
- Validation operations: < 200ms
- WebSocket messages: < 10ms

#### Throughput Targets
- API requests: 1,000 requests/minute
- WebSocket connections: 100 concurrent
- Camera streams: 10 concurrent at 30fps
- ML processing: 5 concurrent videos

#### Availability Targets
- System uptime: 99.9%
- Service availability: 99.5%
- Response success rate: 99%

### Error Handling Strategy

#### Error Categories
```python
class ErrorSeverity(Enum):
    LOW = "low"           # Logging, no immediate action
    MEDIUM = "medium"     # Warning alerts
    HIGH = "high"         # Error alerts, may affect service
    CRITICAL = "critical" # Immediate attention, system impact
```

#### Monitoring and Alerting
```python
# System metrics collected every 60 seconds
metrics = [
    "cpu_usage_percent",
    "memory_usage_percent", 
    "disk_usage_percent",
    "network_io",
    "request_rate",
    "error_rate",
    "response_time",
    "active_connections"
]

# Alert thresholds
alert_thresholds = {
    "cpu_usage_percent": 80,
    "memory_usage_percent": 80,
    "disk_usage_percent": 90,
    "error_rate_percent": 5,
    "response_time_ms": 1000
}
```

### Deployment Guide

#### Prerequisites
```bash
# System requirements
- Python 3.8+
- FastAPI
- PostgreSQL or SQLite
- Redis (optional, for caching)
- Nginx (for production)

# Python dependencies
pip install fastapi uvicorn sqlalchemy psutil aiohttp websockets
```

#### Installation Steps

1. **Clone and Setup**
```bash
cd /home/user/Testing/ai-model-validation-platform/backend/src/
```

2. **Configure Environment**
```bash
export DATABASE_URL="postgresql://user:pass@localhost/vru_api"
export EXTERNAL_IP="155.138.239.131"
export API_HOST="0.0.0.0"
export API_PORT="8000"
```

3. **Run Standalone VRU API**
```bash
python main_integration.py
```

4. **Or Integrate with Existing App**
```python
# In your existing main.py
from src.main_integration import integrate_with_existing_main

app = FastAPI(...)  # Your existing app
app = integrate_with_existing_main(app, "155.138.239.131")
```

#### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
EXPOSE 8000

CMD ["python", "src/main_integration.py"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  vru-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/vru_api
      - EXTERNAL_IP=155.138.239.131
    depends_on:
      - db
      
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=vru_api
      - POSTGRES_USER=postgres  
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Testing and Validation

#### Running the Test Suite
```bash
cd /home/user/Testing/ai-model-validation-platform/backend/src/
python validation_testing_suite.py
```

#### Test Categories
- **API Endpoint Tests**: Validate all REST endpoints
- **WebSocket Tests**: Test real-time communication
- **Performance Tests**: Load testing and response times
- **External Access Tests**: Validate external IP connectivity
- **Integration Tests**: End-to-end service coordination
- **Error Handling Tests**: Fault tolerance validation

#### Sample Test Output
```
✅ API Health Check: pass
✅ Unified Status Check: pass
✅ ML Inference API: pass
✅ Camera Integration API: pass
✅ WebSocket Connection: pass
❌ External IP Access: fail
✅ Performance Response Time: pass

Test suite completed: 6/7 tests passed (85.7%)
Average response time: 45.2ms
```

### Security Considerations

#### Authentication & Authorization
```python
# JWT token validation (example)
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(token: str = Depends(security)):
    # Implement token verification
    if not verify_jwt_token(token.credentials):
        raise HTTPException(status_code=401, detail="Invalid token")
    return token
```

#### Rate Limiting
```python
# Rate limiting configuration
rate_limits = {
    "default": "1000/minute",
    "ml_inference": "100/minute", 
    "camera_streams": "50/minute"
}
```

#### Input Validation
```python
# Pydantic models ensure type safety and validation
from pydantic import BaseModel, Field, validator

class VideoProcessingRequest(BaseModel):
    video_id: str = Field(..., regex="^[a-zA-Z0-9_-]+$")
    processing_type: str = Field(..., regex="^(ground_truth|inference)$")
    
    @validator('video_id')
    def validate_video_id(cls, v):
        if len(v) > 100:
            raise ValueError('video_id too long')
        return v
```

### Troubleshooting Guide

#### Common Issues

**1. External IP Not Accessible**
```bash
# Check network connectivity
ping 155.138.239.131

# Check port accessibility  
telnet 155.138.239.131 8000

# Check firewall rules
iptables -L -n
```

**2. WebSocket Connection Failures**
```bash
# Test WebSocket connectivity
wscat -c ws://155.138.239.131:8000/api/v1/ws

# Check server logs
tail -f /tmp/vru_api_integration.log
```

**3. Service Coordination Issues**
```python
# Check service health
curl http://155.138.239.131:8000/api/coordination/status

# Check memory coordination
curl http://155.138.239.131:8000/api/unified/status
```

#### Log Locations
- Application logs: `/tmp/vru_api_integration.log`
- Access logs: `/var/log/nginx/access.log` (if using nginx)
- Error logs: `/var/log/nginx/error.log`

### Future Enhancements

#### Planned Features
- [ ] Advanced ML model management
- [ ] Multi-camera synchronization
- [ ] Real-time analytics dashboard  
- [ ] Automated failover and scaling
- [ ] Enhanced security features
- [ ] Performance optimization
- [ ] Multi-tenant support

#### Scalability Considerations
- Horizontal scaling with multiple API instances
- Database read replicas for improved performance
- Redis clustering for memory coordination
- Load balancer health checks and auto-scaling
- Microservices decomposition for specific services

### Conclusion

The Unified VRU API Orchestration Layer provides a robust, scalable, and production-ready foundation for VRU detection and validation systems. With comprehensive service coordination, real-time communication, error handling, and external access capabilities, it enables reliable operation in production environments while maintaining flexibility for future enhancements.

The system is designed following SPARC methodology principles with clear specification, well-defined architecture, systematic implementation, and comprehensive validation through testing.

---

**Contact Information**
- Repository: `/home/user/Testing/ai-model-validation-platform/backend/src/`
- Memory Namespace: `vru-api-orchestration`
- External IP: `155.138.239.131`
- Default Port: `8000`