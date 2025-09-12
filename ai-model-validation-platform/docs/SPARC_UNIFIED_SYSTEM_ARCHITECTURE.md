# SPARC Architecture Phase: Unified System Architecture Design

## Executive Summary

This document presents the comprehensive system architecture redesign for the AI Model Validation Platform, addressing all identified root causes through a unified, scalable, and maintainable system design based on the complete SPARC pseudocode analysis.

## 1. ARCHITECTURAL OVERVIEW

### 1.1 System Architecture Principles

**Core Principles:**
- **Microservices Architecture**: Modular, scalable services with clear boundaries
- **Domain-Driven Design**: Service boundaries aligned with business domains
- **Event-Driven Architecture**: Asynchronous communication for scalability
- **Security-First Design**: Multi-layered security with zero-trust principles
- **Fail-Safe Design**: Circuit breakers, retries, and graceful degradation
- **Container-First**: Docker-native with Kubernetes orchestration
- **API-First**: RESTful APIs with OpenAPI specifications
- **Database Per Service**: Service-specific data stores with ACID compliance

### 1.2 High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer & API Gateway              │
│                     (Kong/Nginx + Rate Limiting)                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                     Authentication & Security Layer              │
│                  (JWT, OAuth2, MFA, RBAC, ABAC)                │
└─────────────┬───────────────────────────────────┬───────────────┘
              │                                   │
┌─────────────┴─────────────┐        ┌─────────────┴─────────────┐
│      Application Layer     │        │     Management Layer      │
│                           │        │                           │
│ ┌─────────────────────────┐│        │┌─────────────────────────┐│
│ │  Annotation Service     ││        ││  Project Service        ││
│ │  - CRUD Operations      ││        ││  - Project Management   ││
│ │  - Validation Engine    ││        ││  - User Management      ││
│ │  - Conflict Detection   ││        ││  - Configuration        ││
│ └─────────────────────────┘│        │└─────────────────────────┘│
│                           │        │                           │
│ ┌─────────────────────────┐│        │┌─────────────────────────┐│
│ │  Ground Truth Service   ││        ││  Security Service       ││
│ │  - ML Pipeline          ││        ││  - Audit Logging        ││
│ │  - Data Processing      ││        ││  - Threat Detection     ││
│ │  - Export Engine        ││        ││  - Anomaly Detection    ││
│ └─────────────────────────┘│        │└─────────────────────────┘│
│                           │        │                           │
│ ┌─────────────────────────┐│        │┌─────────────────────────┐│
│ │  Video Service          ││        ││  Notification Service   ││
│ │  - Upload Management    ││        ││  - WebSocket Server     ││
│ │  - Processing Pipeline  ││        ││  - Real-time Updates    ││
│ │  - Metadata Management  ││        ││  - Event Broadcasting   ││
│ └─────────────────────────┘│        │└─────────────────────────┘│
└─────────────┬─────────────┘        └─────────────┬─────────────┘
              │                                   │
┌─────────────┴─────────────────────────────────────┴───────────────┐
│                          Data Layer                              │
│                                                                  │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│ │ PostgreSQL  │ │   Redis     │ │ File System │ │  ML Models  ││
│ │ (Primary)   │ │  (Cache)    │ │  (Videos)   │ │ (YOLOv8)   ││
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
│                                                                  │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│ │   Backup    │ │ Message     │ │ Monitoring  │ │   Logs     ││
│ │ Storage     │ │ Queue       │ │ Metrics     │ │ Storage    ││
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## 2. SERVICE ARCHITECTURE DESIGN

### 2.1 Annotation Service Architecture

**Purpose**: Handle all annotation CRUD operations with validation and security

```typescript
// Service Structure
annotation-service/
├── src/
│   ├── controllers/
│   │   ├── annotation.controller.ts
│   │   ├── validation.controller.ts
│   │   └── export.controller.ts
│   ├── services/
│   │   ├── annotation.service.ts
│   │   ├── validation.service.ts
│   │   ├── conflict-detection.service.ts
│   │   └── sanitization.service.ts
│   ├── repositories/
│   │   ├── annotation.repository.ts
│   │   └── annotation-session.repository.ts
│   ├── models/
│   │   ├── annotation.model.ts
│   │   ├── detection.model.ts
│   │   └── validation-result.model.ts
│   ├── middleware/
│   │   ├── authentication.middleware.ts
│   │   ├── authorization.middleware.ts
│   │   ├── validation.middleware.ts
│   │   └── rate-limiting.middleware.ts
│   ├── utils/
│   │   ├── geometry.utils.ts
│   │   ├── validation.utils.ts
│   │   └── security.utils.ts
│   └── config/
│       ├── database.config.ts
│       ├── security.config.ts
│       └── validation.config.ts
├── migrations/
├── tests/
├── Dockerfile
└── docker-compose.yml
```

**API Endpoints:**
```yaml
# Annotation CRUD Operations
POST   /api/v1/annotations              # Create annotation
GET    /api/v1/annotations/:id          # Get annotation by ID
PUT    /api/v1/annotations/:id          # Update annotation
DELETE /api/v1/annotations/:id          # Delete annotation
GET    /api/v1/videos/:videoId/annotations  # Get annotations for video

# Validation Operations
POST   /api/v1/annotations/validate     # Validate annotation data
POST   /api/v1/annotations/bulk-validate # Bulk validation
GET    /api/v1/annotations/:id/conflicts # Check conflicts

# Export Operations
POST   /api/v1/annotations/export       # Export annotations
GET    /api/v1/exports/:exportId        # Get export status
```

### 2.2 Ground Truth Service Architecture

**Purpose**: ML pipeline, data processing, and ground truth management

```typescript
// Service Structure
ground-truth-service/
├── src/
│   ├── controllers/
│   │   ├── processing.controller.ts
│   │   ├── export.controller.ts
│   │   └── validation.controller.ts
│   ├── services/
│   │   ├── ml-inference.service.ts
│   │   ├── ground-truth-processing.service.ts
│   │   ├── export.service.ts
│   │   └── quality-validation.service.ts
│   ├── ml/
│   │   ├── yolo-inference.engine.ts
│   │   ├── model-loader.ts
│   │   └── detection-pipeline.ts
│   ├── exporters/
│   │   ├── coco.exporter.ts
│   │   ├── yolo.exporter.ts
│   │   ├── pascal-voc.exporter.ts
│   │   └── csv.exporter.ts
│   ├── processors/
│   │   ├── video.processor.ts
│   │   ├── frame.processor.ts
│   │   └── detection.processor.ts
│   └── utils/
│       ├── video.utils.ts
│       ├── geometry.utils.ts
│       └── format.utils.ts
├── models/          # ML model files
├── temp/           # Processing temporary files
├── Dockerfile
└── requirements.txt
```

### 2.3 Security Service Architecture

**Purpose**: Authentication, authorization, audit logging, and threat detection

```typescript
// Service Structure
security-service/
├── src/
│   ├── controllers/
│   │   ├── auth.controller.ts
│   │   ├── user.controller.ts
│   │   └── audit.controller.ts
│   ├── services/
│   │   ├── authentication.service.ts
│   │   ├── authorization.service.ts
│   │   ├── mfa.service.ts
│   │   ├── audit.service.ts
│   │   ├── threat-detection.service.ts
│   │   └── anomaly-detection.service.ts
│   ├── guards/
│   │   ├── jwt-auth.guard.ts
│   │   ├── roles.guard.ts
│   │   └── permissions.guard.ts
│   ├── strategies/
│   │   ├── jwt.strategy.ts
│   │   ├── oauth2.strategy.ts
│   │   └── mfa.strategy.ts
│   ├── models/
│   │   ├── user.model.ts
│   │   ├── role.model.ts
│   │   ├── permission.model.ts
│   │   └── audit-log.model.ts
│   └── utils/
│       ├── crypto.utils.ts
│       ├── validation.utils.ts
│       └── risk-assessment.utils.ts
```

### 2.4 Video Service Architecture

**Purpose**: Video upload, processing, and metadata management

```typescript
// Service Structure
video-service/
├── src/
│   ├── controllers/
│   │   ├── upload.controller.ts
│   │   ├── video.controller.ts
│   │   └── metadata.controller.ts
│   ├── services/
│   │   ├── upload.service.ts
│   │   ├── video-processing.service.ts
│   │   ├── metadata.service.ts
│   │   └── validation.service.ts
│   ├── processors/
│   │   ├── video-analyzer.ts
│   │   ├── thumbnail-generator.ts
│   │   └── format-converter.ts
│   ├── validators/
│   │   ├── file-validator.ts
│   │   ├── format-validator.ts
│   │   └── size-validator.ts
│   └── storage/
│       ├── file-system.storage.ts
│       ├── s3.storage.ts (future)
│       └── storage.interface.ts
```

## 3. DATABASE ARCHITECTURE

### 3.1 Database Schema Design

**Primary Database: PostgreSQL with optimized schema**

```sql
-- Core Tables
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    
    CONSTRAINT fk_projects_owner FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    duration DECIMAL(10,3),
    fps DECIMAL(6,3),
    width INTEGER,
    height INTEGER,
    format VARCHAR(50),
    processing_status VARCHAR(50) DEFAULT 'pending',
    ground_truth_generated BOOLEAN DEFAULT FALSE,
    uploaded_by UUID NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_videos_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_videos_uploader FOREIGN KEY (uploaded_by) REFERENCES users(id),
    
    INDEX idx_videos_project (project_id),
    INDEX idx_videos_status (processing_status),
    INDEX idx_videos_ground_truth (ground_truth_generated)
);

CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    detection_id VARCHAR(100) NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp DECIMAL(10,3) NOT NULL,
    end_timestamp DECIMAL(10,3),
    vru_type VARCHAR(50) NOT NULL,
    x DECIMAL(8,6) NOT NULL,
    y DECIMAL(8,6) NOT NULL,
    width DECIMAL(8,6) NOT NULL,
    height DECIMAL(8,6) NOT NULL,
    confidence DECIMAL(5,3),
    occluded BOOLEAN DEFAULT FALSE,
    truncated BOOLEAN DEFAULT FALSE,
    difficult BOOLEAN DEFAULT FALSE,
    notes TEXT,
    annotator UUID NOT NULL,
    validator UUID,
    validated BOOLEAN DEFAULT FALSE,
    validation_score DECIMAL(5,3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_annotations_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    CONSTRAINT fk_annotations_annotator FOREIGN KEY (annotator) REFERENCES users(id),
    CONSTRAINT fk_annotations_validator FOREIGN KEY (validator) REFERENCES users(id),
    
    -- Performance indexes
    INDEX idx_annotations_video_frame (video_id, frame_number),
    INDEX idx_annotations_video_timestamp (video_id, timestamp),
    INDEX idx_annotations_vru_type (vru_type),
    INDEX idx_annotations_annotator (annotator),
    INDEX idx_annotations_validated (validated),
    
    -- Unique constraint for detection IDs
    UNIQUE(video_id, detection_id)
);

CREATE TABLE ground_truth_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp DECIMAL(10,3) NOT NULL,
    class_label VARCHAR(50) NOT NULL,
    x DECIMAL(8,6) NOT NULL,
    y DECIMAL(8,6) NOT NULL,
    width DECIMAL(8,6) NOT NULL,
    height DECIMAL(8,6) NOT NULL,
    confidence DECIMAL(5,3) NOT NULL,
    validated BOOLEAN DEFAULT FALSE,
    difficult BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_gt_objects_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    
    INDEX idx_gt_objects_video_frame (video_id, frame_number),
    INDEX idx_gt_objects_class (class_label),
    INDEX idx_gt_objects_confidence (confidence),
    INDEX idx_gt_objects_validated (validated)
);

-- Security Tables
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    status VARCHAR(50) DEFAULT 'active',
    failed_login_attempts INTEGER DEFAULT 0,
    last_login_attempt TIMESTAMP,
    locked_until TIMESTAMP,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_status (status)
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_token (token_hash),
    INDEX idx_sessions_expires (expires_at)
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    risk_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES users(id),
    
    INDEX idx_audit_logs_user (user_id),
    INDEX idx_audit_logs_action (action),
    INDEX idx_audit_logs_created (created_at),
    INDEX idx_audit_logs_metadata USING gin(metadata)
) PARTITION BY RANGE (created_at);

-- Audit log partitioning (monthly)
CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

### 3.2 Database Performance Optimization

**Connection Pooling Configuration:**
```yaml
database:
  postgresql:
    primary:
      host: localhost
      port: 5432
      database: ai_model_validation
      connection_pool:
        min_size: 10
        max_size: 100
        idle_timeout: 300
        connection_timeout: 30
    read_replicas:
      - host: replica1.localhost
        weight: 50
      - host: replica2.localhost
        weight: 50
  
  redis:
    cache:
      host: localhost
      port: 6379
      db: 0
      max_connections: 50
      ttl_default: 300
    sessions:
      host: localhost
      port: 6379
      db: 1
      max_connections: 30
```

## 4. API ARCHITECTURE

### 4.1 API Gateway Configuration

**Kong/Nginx API Gateway with plugins:**

```yaml
# API Gateway Configuration
api_gateway:
  plugins:
    - name: rate-limiting
      config:
        minute: 1000
        hour: 10000
        policy: local
    
    - name: cors
      config:
        origins: ["http://localhost:3000", "https://app.domain.com"]
        methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        headers: ["Authorization", "Content-Type", "X-Request-ID"]
    
    - name: request-id
      config:
        header_name: X-Request-ID
    
    - name: prometheus
      config:
        per_consumer: true
    
    - name: jwt
      config:
        secret_is_base64: false
        claims_to_verify: ["exp", "iat"]

  routes:
    - name: annotation-service
      hosts: ["api.domain.com"]
      paths: ["/api/v1/annotations", "/api/v1/videos/*/annotations"]
      service: annotation-service
    
    - name: ground-truth-service
      hosts: ["api.domain.com"]
      paths: ["/api/v1/ground-truth", "/api/v1/processing"]
      service: ground-truth-service
    
    - name: auth-service
      hosts: ["api.domain.com"]
      paths: ["/api/v1/auth", "/api/v1/users"]
      service: auth-service
```

### 4.2 OpenAPI Specification Structure

```yaml
openapi: 3.0.3
info:
  title: AI Model Validation Platform API
  version: 1.0.0
  description: Comprehensive API for video annotation and ML model validation

servers:
  - url: https://api.domain.com/v1
    description: Production API
  - url: http://localhost:8080/v1
    description: Development API

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    
    oauth2:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://auth.domain.com/oauth/authorize
          tokenUrl: https://auth.domain.com/oauth/token
          scopes:
            read: Read access
            write: Write access
            admin: Administrative access

  schemas:
    Error:
      type: object
      required: [error_code, message]
      properties:
        error_code:
          type: string
        message:
          type: string
        details:
          type: object
        timestamp:
          type: string
          format: date-time
        request_id:
          type: string
        
    ValidationError:
      allOf:
        - $ref: '#/components/schemas/Error'
        - type: object
          properties:
            field_errors:
              type: array
              items:
                type: object
                properties:
                  field:
                    type: string
                  code:
                    type: string
                  message:
                    type: string
```

## 5. SECURITY ARCHITECTURE

### 5.1 Multi-Layer Security Design

```typescript
// Security Layer Stack
interface SecurityStack {
  layers: {
    network: {
      firewall: 'iptables/UFW';
      ddos_protection: 'CloudFlare';
      ssl_termination: 'nginx';
    };
    
    application: {
      authentication: 'JWT + OAuth2';
      authorization: 'RBAC + ABAC';
      input_validation: 'Joi + custom validators';
      output_sanitization: 'DOMPurify + custom sanitizers';
    };
    
    data: {
      encryption_at_rest: 'AES-256';
      encryption_in_transit: 'TLS 1.3';
      data_masking: 'PII detection + masking';
      backup_encryption: 'GPG + AES-256';
    };
    
    monitoring: {
      threat_detection: 'ML-based anomaly detection';
      audit_logging: 'Comprehensive audit trail';
      intrusion_detection: 'SIEM integration';
      vulnerability_scanning: 'Automated security scans';
    };
  };
}
```

### 5.2 Authentication Flow Architecture

```typescript
// Multi-Factor Authentication Flow
interface MFAFlow {
  primary_authentication: {
    method: 'password' | 'oauth2';
    validation: {
      password_complexity: boolean;
      account_lockout: boolean;
      rate_limiting: boolean;
    };
  };
  
  risk_assessment: {
    factors: {
      geographical_location: number;
      device_fingerprint: number;
      behavioral_patterns: number;
      time_of_access: number;
    };
    threshold: {
      low: 0.3;
      medium: 0.6;
      high: 0.8;
    };
  };
  
  mfa_requirements: {
    low_risk: ['none'];
    medium_risk: ['totp'];
    high_risk: ['totp', 'sms'];
    critical_risk: ['totp', 'sms', 'admin_approval'];
  };
}
```

## 6. CONTAINERIZATION ARCHITECTURE

### 6.1 Docker Multi-Stage Builds

```dockerfile
# Annotation Service Dockerfile
FROM node:18-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build && npm run test

FROM node:18-alpine AS production
WORKDIR /app
COPY --from=base /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package*.json ./

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001
USER nextjs

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

CMD ["npm", "start"]
```

### 6.2 Docker Compose Orchestration

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  # Database Services
  postgresql:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ai_model_validation
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Application Services
  api-gateway:
    image: kong:3.0-alpine
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong.yml
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
    volumes:
      - ./config/kong.yml:/kong.yml
    ports:
      - "8080:8000"
      - "8443:8443"
      - "8001:8001"
    depends_on:
      - annotation-service
      - ground-truth-service
      - security-service

  annotation-service:
    build:
      context: ./annotation-service
      dockerfile: Dockerfile
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgresql:5432/ai_model_validation
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      postgresql:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3

  ground-truth-service:
    build:
      context: ./ground-truth-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgresql:5432/ai_model_validation
      REDIS_URL: redis://redis:6379/1
      ML_MODEL_PATH: /app/models
    volumes:
      - ml_models:/app/models
      - video_storage:/app/videos
    depends_on:
      postgresql:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'

  security-service:
    build:
      context: ./security-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgresql:5432/ai_model_validation
      REDIS_URL: redis://redis:6379/2
      JWT_SECRET: ${JWT_SECRET}
      MFA_SECRET: ${MFA_SECRET}
    depends_on:
      postgresql:
        condition: service_healthy

  # Monitoring Services
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3001:3000"

volumes:
  postgres_data:
  redis_data:
  ml_models:
  video_storage:
  prometheus_data:
  grafana_data:

networks:
  default:
    driver: bridge
```

## 7. ERROR HANDLING & RECOVERY ARCHITECTURE

### 7.1 Circuit Breaker Pattern Implementation

```typescript
// Circuit Breaker Configuration
interface CircuitBreakerConfig {
  services: {
    database: {
      failure_threshold: 5;
      recovery_timeout: 60000;
      half_open_max_calls: 3;
    };
    ml_inference: {
      failure_threshold: 3;
      recovery_timeout: 30000;
      half_open_max_calls: 1;
    };
    external_api: {
      failure_threshold: 10;
      recovery_timeout: 120000;
      half_open_max_calls: 5;
    };
  };
  
  fallback_strategies: {
    database_failure: 'return_cached_data';
    ml_inference_failure: 'queue_for_retry';
    api_failure: 'degrade_gracefully';
  };
}
```

### 7.2 Retry Mechanism Design

```typescript
// Exponential Backoff Retry Configuration
interface RetryConfig {
  max_attempts: 5;
  base_delay: 1000;
  max_delay: 30000;
  backoff_multiplier: 2;
  jitter: true;
  
  retry_conditions: {
    http_status_codes: [500, 502, 503, 504];
    exceptions: [
      'ConnectionError',
      'TimeoutError',
      'ServiceUnavailableError'
    ];
  };
}
```

## 8. DEPLOYMENT ARCHITECTURE

### 8.1 Production Deployment Strategy

```yaml
# Kubernetes Deployment (Future)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: annotation-service
  labels:
    app: annotation-service
    version: v1.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: annotation-service
  template:
    metadata:
      labels:
        app: annotation-service
        version: v1.0.0
    spec:
      containers:
      - name: annotation-service
        image: annotation-service:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 8.2 Environment Configuration

```yaml
# Environment-specific configurations
environments:
  development:
    database:
      host: localhost
      port: 5432
      ssl: false
    logging:
      level: debug
    security:
      cors_origins: ["http://localhost:3000"]
      rate_limiting: false
    
  staging:
    database:
      host: staging-db.internal
      port: 5432
      ssl: true
    logging:
      level: info
    security:
      cors_origins: ["https://staging.domain.com"]
      rate_limiting: true
      
  production:
    database:
      host: prod-db.internal
      port: 5432
      ssl: true
      connection_pool: 50
    logging:
      level: warn
    security:
      cors_origins: ["https://app.domain.com"]
      rate_limiting: true
      threat_detection: true
```

## 9. MONITORING & OBSERVABILITY

### 9.1 Metrics Collection Architecture

```yaml
# Prometheus Metrics Configuration
metrics:
  application_metrics:
    - http_requests_total
    - http_request_duration_seconds
    - database_query_duration_seconds
    - ml_inference_duration_seconds
    - annotation_operations_total
    - ground_truth_processing_duration
    - security_events_total
    - circuit_breaker_state
  
  business_metrics:
    - active_users_total
    - annotations_created_total
    - videos_processed_total
    - ground_truth_objects_generated_total
    - api_usage_by_endpoint
  
  infrastructure_metrics:
    - cpu_usage_percent
    - memory_usage_bytes
    - disk_usage_percent
    - network_io_bytes
    - container_restarts_total
```

### 9.2 Logging Architecture

```yaml
# Structured Logging Configuration
logging:
  format: json
  level: info
  
  fields:
    mandatory:
      - timestamp
      - level
      - message
      - service_name
      - version
      - request_id
    
    contextual:
      - user_id
      - session_id
      - operation
      - resource_id
      - duration_ms
  
  destinations:
    - type: stdout
      level: info
    - type: file
      level: warn
      path: /var/log/app/error.log
    - type: elasticsearch
      level: info
      index: ai-validation-logs
  
  security_logging:
    enabled: true
    audit_events: true
    pii_masking: true
    retention_days: 2555  # 7 years
```

## 10. IMPLEMENTATION ROADMAP

### Phase 1: Core Infrastructure (Week 1-2)
1. Database schema implementation and migrations
2. Docker containerization for all services
3. Basic API gateway setup with Kong/Nginx
4. Authentication and authorization service
5. Logging and monitoring infrastructure

### Phase 2: Core Services (Week 3-4)
1. Annotation service with CRUD operations
2. Video service with upload and processing
3. Ground truth service with ML pipeline
4. Security service with threat detection
5. WebSocket service for real-time updates

### Phase 3: Advanced Features (Week 5-6)
1. Advanced form validation and sanitization
2. Export functionality for multiple formats
3. Comprehensive error handling and recovery
4. Performance optimization and caching
5. Advanced security features (MFA, ABAC)

### Phase 4: Production Readiness (Week 7-8)
1. Load testing and performance optimization
2. Security penetration testing
3. Disaster recovery procedures
4. Production deployment and monitoring
5. Documentation and training

## 11. CONCLUSION

This unified system architecture addresses all identified root causes through:

1. **Modular Design**: Clear service boundaries with single responsibilities
2. **Scalable Infrastructure**: Container-based deployment with orchestration
3. **Security-First Approach**: Multi-layer security with comprehensive audit trails
4. **Robust Error Handling**: Circuit breakers, retries, and graceful degradation
5. **Performance Optimization**: Caching, connection pooling, and query optimization
6. **Operational Excellence**: Comprehensive monitoring, logging, and alerting

The architecture supports the complete SPARC methodology implementation with clear pathways for the Refinement phase to implement each component systematically.