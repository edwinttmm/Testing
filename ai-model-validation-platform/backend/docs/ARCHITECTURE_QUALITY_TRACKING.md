# Architecture Documentation - Quality Tracking System

**Version**: 1.0.0
**Last Updated**: 2025-11-19
**System**: AI Model Validation Platform - Quality Tracking Module

---

## Executive Summary

The Quality Tracking System extends the AI Model Validation Platform with automatic monitoring of timing accuracy and validation usability. It provides real-time quality metrics, configurable alerts, and comprehensive monitoring capabilities.

**Key Features**:
- Automatic quality tracking for all test sessions
- Real-time detection quality monitoring
- Configurable alert system (email, Slack, webhook)
- Background health monitoring
- Performance-optimized database queries
- Zero-downtime deployment support

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (React + TypeScript)                │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │  HIL Results │  │   Quality   │  │  Quality Metrics     │  │
│  │     Page     │  │  Dashboard  │  │     Components       │  │
│  └──────┬───────┘  └──────┬──────┘  └──────────┬───────────┘  │
└─────────┼──────────────────┼──────────────────────┼──────────────┘
          │                  │                      │
          │ HTTP/WebSocket   │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application (Python)                 │
├─────────────────────────────────────────────────────────────────┤
│  Middleware Layer                                                │
│  ├─ AutoMetricsMiddleware (optional - automatic metrics)        │
│  └─ AutoSecurityMiddleware (optional - UUID validation, rate limiting) │
├─────────────────────────────────────────────────────────────────┤
│  Router Layer                                                    │
│  ├─ /api/monitoring/* (9 endpoints)                             │
│  ├─ /api/test-sessions/* (enhanced with quality)                │
│  └─ Other routers (projects, videos, etc.)                      │
├─────────────────────────────────────────────────────────────────┤
│  Service Layer                                                   │
│  ├─ MonitoringService (metrics & alerts)                        │
│  ├─ BackgroundMonitoring (continuous health checks)             │
│  ├─ QualityResponseWrapper (auto-enhance responses)             │
│  └─ AlertManager (handle alert distribution)                    │
├─────────────────────────────────────────────────────────────────┤
│  Data Access Layer                                               │
│  ├─ SQLAlchemy ORM                                               │
│  ├─ Pydantic Models (validation & serialization)                │
│  └─ Database Connection Pool                                     │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database (PostgreSQL/SQLite)                  │
│  ┌───────────────┐  ┌─────────────────┐                        │
│  │ test_sessions │  │ detection_events│                        │
│  ├───────────────┤  ├─────────────────┤                        │
│  │ +timing_degraded│ │ +usable_for_validation                  │
│  │ +timing_verified│ │ +timing_degraded                        │
│  └───────────────┘  └─────────────────┘                        │
│                                                                  │
│  Indexes: 6 performance indexes for quality queries            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Monitoring Router (`/api/monitoring/*`)

**Purpose**: Expose quality metrics and monitoring endpoints

**Endpoints**:
- `GET /metrics/global` - System-wide quality metrics
- `GET /metrics/session/{id}` - Session-specific quality
- `GET /metrics/sessions/recent` - Recent sessions with quality
- `GET /health/database` - Database pool health
- `GET /alerts` - Alert history
- `GET /alerts/thresholds` - Alert configuration
- `POST /alerts/test` - Test alert system
- `POST /alerts/check-thresholds` - Manual threshold check
- `GET /status` - Overall system status

**Architecture**:
```python
Router (monitoring.py)
    ├─ Depends on: MonitoringService
    ├─ Depends on: AlertManager
    └─ Depends on: SessionLocal (database)

MonitoringService
    ├─ Metrics collection
    ├─ Quality calculation
    └─ Statistics aggregation

AlertManager
    ├─ Alert generation
    ├─ Handler management
    └─ Alert history
```

---

### 2. Background Monitoring Service

**Purpose**: Continuous health monitoring without blocking main application

**Architecture**:
```python
BackgroundMonitoring (daemon thread)
    │
    ├─ Pool Health Monitor (every 60s)
    │   ├─ Check active connections
    │   ├─ Check pool utilization
    │   └─ Generate alerts if needed
    │
    ├─ Metrics Logger (every 5min)
    │   ├─ Log global metrics
    │   ├─ Log quality trends
    │   └─ Update statistics
    │
    └─ Threshold Checker (every 10min)
        ├─ Check degradation rate
        ├─ Check validation rate
        ├─ Check pool usage
        └─ Generate alerts
```

**Threading Model**:
- Runs in daemon thread (doesn't prevent shutdown)
- Uses separate database connections
- Graceful shutdown support
- Automatic restart on failure

---

### 3. Alert System Architecture

**Purpose**: Multi-channel alert distribution with configurable handlers

```
AlertManager
    │
    ├─ Alert Generation
    │   ├─ Quality threshold breaches
    │   ├─ Performance degradation
    │   ├─ Database issues
    │   └─ System health events
    │
    ├─ Alert Distribution
    │   ├─ ConsoleHandler (always active)
    │   ├─ FileHandler (configurable)
    │   ├─ EmailHandler (configurable)
    │   ├─ WebhookHandler (configurable)
    │   └─ SlackHandler (configurable)
    │
    └─ Alert History
        ├─ Store recent alerts
        ├─ Prevent alert flooding
        └─ Provide alert API
```

**Alert Flow**:
```
Trigger Event
    ↓
Generate Alert
    ↓
Check Severity Filters
    ↓
Distribute to Handlers (parallel)
    ├─ Console → logs/backend.log
    ├─ File → logs/alerts.log
    ├─ Email → SMTP server
    ├─ Webhook → HTTP POST
    └─ Slack → Webhook
```

---

### 4. Quality Response Wrapper

**Purpose**: Automatically enhance API responses with quality information

**Architecture**:
```python
enhance_session_response(session_dict, session_id, db)
    │
    ├─ Query quality metrics from database
    │   ├─ Count usable detections
    │   ├─ Count degraded detections
    │   └─ Calculate percentages
    │
    ├─ Generate quality warnings
    │   ├─ Check degradation threshold
    │   ├─ Check validation threshold
    │   └─ Create warning messages
    │
    ├─ Generate recommendations
    │   ├─ Based on quality level
    │   └─ Actionable suggestions
    │
    └─ Inject quality field into response
        {
          ...session_data,
          "quality": {
            "quality_level": "high|medium|low",
            "validation_statistics": {...},
            "warnings": [...],
            "recommendations": [...]
          }
        }
```

---

## Database Schema

### Schema Changes

```sql
-- test_sessions table additions
ALTER TABLE test_sessions ADD COLUMN timing_degraded BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE test_sessions ADD COLUMN timing_verified BOOLEAN NOT NULL DEFAULT FALSE;

-- detection_events table additions
ALTER TABLE detection_events ADD COLUMN usable_for_validation BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE detection_events ADD COLUMN timing_degraded BOOLEAN NOT NULL DEFAULT FALSE;
```

### Index Strategy

```sql
-- Single-column indexes for filtering
CREATE INDEX idx_test_sessions_timing_degraded ON test_sessions(timing_degraded);
CREATE INDEX idx_test_sessions_timing_verified ON test_sessions(timing_verified);
CREATE INDEX idx_detection_events_usable ON detection_events(usable_for_validation);
CREATE INDEX idx_detection_events_timing_degraded ON detection_events(timing_degraded);

-- Composite indexes for complex queries
CREATE INDEX idx_test_sessions_quality
  ON test_sessions(timing_degraded, timing_verified, status);

CREATE INDEX idx_detection_quality_session
  ON detection_events(test_session_id, usable_for_validation, timing_degraded);
```

**Index Usage**:
- **idx_test_sessions_timing_degraded**: Filter sessions with quality issues
- **idx_test_sessions_quality**: Dashboard queries (quality + status)
- **idx_detection_quality_session**: Session-specific quality metrics

---

## Data Flow Diagrams

### Quality Metrics Collection Flow

```
Test Session Created
    ↓
Detections Generated
    ↓
Timing Analysis (existing component)
    ├─ Calculate timing accuracy
    ├─ Detect synchronization issues
    └─ Set quality flags
        ├─ detection.usable_for_validation
        └─ detection.timing_degraded
    ↓
Session Aggregation
    ├─ Count usable detections
    ├─ Count degraded detections
    ├─ Calculate percentages
    └─ Set session flags
        ├─ session.timing_degraded
        └─ session.timing_verified
    ↓
Quality Metrics Available
    ├─ API: /api/monitoring/metrics/session/{id}
    ├─ Enhanced session response
    └─ Dashboard display
```

---

### Alert Generation Flow

```
Scheduled Check (background monitoring)
    ↓
Query Quality Metrics
    ├─ Global degradation rate
    ├─ Global validation rate
    ├─ Database pool usage
    └─ Session timing issues
    ↓
Compare Against Thresholds
    ├─ degradation_rate > ALERT_DEGRADATION_THRESHOLD?
    ├─ validation_rate < ALERT_VALIDATION_THRESHOLD?
    ├─ pool_usage > ALERT_POOL_UTILIZATION?
    └─ timing_issues > ALERT_TIMING_THRESHOLD?
    ↓
Generate Alerts (if thresholds breached)
    ├─ Create alert object
    ├─ Set severity level
    ├─ Include context/details
    └─ Add to alert history
    ↓
Distribute to Handlers (parallel execution)
    ├─ Filter by minimum severity
    ├─ Format for each handler
    └─ Send via configured channels
```

---

## Security Architecture

### Authentication & Authorization

**Current**: No authentication required (development)

**Production Recommendations**:
```python
# JWT-based authentication
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@router.get("/api/monitoring/metrics/global")
async def get_metrics(credentials: HTTPAuthorizationCredentials = Security(security)):
    # Verify JWT token
    # Check user permissions
    # Return metrics
```

---

### Input Validation

**UUID Validation** (via AutoSecurityMiddleware):
```python
# All path/query parameters with "id" automatically validated
GET /api/test-sessions/{session_id}  # UUID validated
GET /api/monitoring/metrics/session/{id}  # UUID validated
```

**Rate Limiting** (via AutoSecurityMiddleware):
```python
# Per-IP address rate limiting
100 requests per 60 seconds (configurable)
Exempt paths: ["/health", "/docs"]
```

---

### Data Security

**Database**:
- Parameterized queries (SQL injection proof)
- ORM validation via SQLAlchemy
- Connection pooling with timeouts

**Sensitive Data**:
- Alert credentials stored in environment variables
- Never logged or exposed in API responses
- Secure SMTP/webhook connections (TLS)

---

## Performance Architecture

### Query Optimization

**Without Indexes** (baseline):
```sql
-- Full table scan
SELECT * FROM detection_events
WHERE test_session_id = 'abc123'
  AND usable_for_validation = true;

-- Time: ~200ms for 100K rows
```

**With Indexes** (optimized):
```sql
-- Index scan using idx_detection_quality_session
SELECT * FROM detection_events
WHERE test_session_id = 'abc123'
  AND usable_for_validation = true;

-- Time: ~5ms for 100K rows (40x faster!)
```

---

### Caching Strategy

**Response Caching** (frontend):
```typescript
// Cache global metrics for 60 seconds
const metrics = await cachedFetch('/api/monitoring/metrics/global', {
  ttl: 60000
});

// Cache session metrics for 5 minutes (if completed)
const sessionMetrics = await cachedFetch(`/api/monitoring/metrics/session/${id}`, {
  ttl: sessionCompleted ? 300000 : 0
});
```

**Database Connection Pooling**:
```python
# SQLAlchemy pool configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Number of connections to keep open
    max_overflow=20,        # Additional connections when pool exhausted
    pool_timeout=30,        # Seconds to wait for connection
    pool_recycle=3600       # Recycle connections after 1 hour
)
```

---

### Scalability Considerations

**Horizontal Scaling**:
- Stateless API design (can run multiple instances)
- Database connection pooling per instance
- Alert distribution can be load balanced

**Vertical Scaling**:
- Increase database pool size
- Add more worker processes (uvicorn workers)
- Increase background monitoring intervals

**Database Scaling**:
- Read replicas for reporting queries
- Connection pooling optimization
- Query result caching

---

## Deployment Architecture

### Development

```
Local Machine
    ├─ SQLite database (file-based)
    ├─ FastAPI (uvicorn, single process)
    ├─ Console/file alerts only
    └─ Auto-restart on code changes
```

### Production

```
┌──────────────────────────────────────────────────┐
│  Load Balancer (Nginx/HAProxy)                   │
└────────────┬─────────────────────────────────────┘
             │
      ┌──────┴────────┐
      ▼               ▼
┌───────────┐   ┌───────────┐
│ App       │   │ App       │
│ Instance 1│   │ Instance 2│
│ (Gunicorn)│   │ (Gunicorn)│
└─────┬─────┘   └─────┬─────┘
      │               │
      └──────┬────────┘
             ▼
┌────────────────────────────┐
│ PostgreSQL Primary         │
│  ├─ Connection pool        │
│  └─ Quality indexes        │
└────────┬───────────────────┘
         │
         ├─ Read Replica 1 (reporting)
         └─ Read Replica 2 (backup)

Alert Channels:
    ├─ Email (SMTP)
    ├─ Slack (webhook)
    └─ Monitoring System (webhook)
```

---

## Integration Points

### Frontend Integration

```typescript
// HIL Results Page
import { QualityWarningBanner } from '@/components/quality/QualityWarningBanner';
import { QualityFilterDropdown } from '@/components/quality/QualityFilterDropdown';

function HILResultsPage() {
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [qualityFilter, setQualityFilter] = useState<QualityFilter>('all');

  // Fetch sessions with quality filter
  useEffect(() => {
    apiService.getTestSessions({ quality_filter: qualityFilter })
      .then(setSessions);
  }, [qualityFilter]);

  return (
    <>
      <QualityWarningBanner session={currentSession} />
      <QualityFilterDropdown
        value={qualityFilter}
        onChange={setQualityFilter}
      />
      {/* ... */}
    </>
  );
}
```

### WebSocket Integration

```python
# Emit quality updates via WebSocket
@sio.event
async def detection_created(detection):
    await sio.emit('detection_quality', {
        'detection_id': detection.id,
        'usable_for_validation': detection.usable_for_validation,
        'timing_degraded': detection.timing_degraded,
        'quality_score': calculate_quality_score(detection)
    })
```

---

## Monitoring & Observability

### Metrics Collection

```python
# Automatic metrics via AutoMetricsMiddleware
@app.middleware("http")
async def auto_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Auto-collect metrics from endpoint patterns
    if '/test-sessions' in request.url.path:
        metrics_collector.record('session_operations', {
            'duration_ms': duration * 1000,
            'status_code': response.status_code
        })

    return response
```

### Health Checks

```python
# Application health endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "database": check_database_connection(),
        "monitoring": check_monitoring_system()
    }
```

---

## Technology Stack

### Backend
- **FastAPI**: Web framework
- **SQLAlchemy**: ORM and database toolkit
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server
- **Python 3.8+**: Runtime

### Database
- **PostgreSQL 12+**: Production database (recommended)
- **SQLite 3.30+**: Development database

### Monitoring
- **Custom monitoring service**: Quality metrics
- **Background threads**: Continuous health checks
- **SMTP**: Email alerts
- **Webhooks**: Slack/custom integrations

---

## Future Enhancements

### Short-term
- GraphQL API for flexible querying
- Prometheus metrics export
- Real-time quality dashboards (WebSocket)
- Advanced caching layer (Redis)

### Long-term
- Machine learning for quality prediction
- Anomaly detection algorithms
- Automated quality remediation
- Multi-tenant support

---

**Architecture Version**: 1.0.0
**Last Updated**: 2025-11-19
**Next Review**: 2026-02-19
