# API Contract Documentation - Frontend-Backend Integration

**Generated**: 2025-11-19
**Integration Agent**: Integration Specialist
**Status**: Verification Complete

## Overview

This document defines the contract between the frontend React application and the FastAPI backend, with focus on quality-enhanced endpoints for the AI Model Validation Platform.

---

## 1. Base Configuration

### Backend Base URL
```
Development: http://localhost:8000
Production: Configure via REACT_APP_API_URL
```

### Frontend Configuration
```typescript
// Frontend: src/services/enhancedApiService.ts (line 44)
baseURL: getConfigValueSync('REACT_APP_API_URL', 'http://localhost:8000')
```

### CORS Configuration
```python
# Backend: main.py (detected)
CORSMiddleware configured with:
- allowed_origins: From settings.cors_origins
- allow_credentials: settings.cors_credentials
- allow_methods: settings.cors_methods
- allow_headers: settings.cors_headers
```

**Status**: ✅ CORS properly configured

---

## 2. Test Results Endpoints

### GET /api/results

**Purpose**: Fetch basic test session results for Results page

**Backend Implementation**: `/backend/src/api/results_endpoints.py:56-116`

**Request**:
```typescript
GET /api/results?limit=10&status=completed
```

**Backend Response Model** (`BasicTestSession`):
```python
{
  "id": "string (UUID)",
  "name": "string",
  "project_id": "string | null",
  "project_name": "string | null",
  "status": "string",  # completed|running|failed
  "started_at": "string (ISO) | null",
  "completed_at": "string (ISO) | null",
  "results_count": "integer",
  "detection_events": "integer",
  "has_results": "boolean"
}
```

**Frontend Expected Types**:
```typescript
// Frontend: src/services/types.ts:650-656
interface TestResult {
  id: string;
  sessionId: string;
  videoId: string;
  videoName?: string;
  status: 'success' | 'failed' | 'pending' | 'processing';
  timestamp: string | Date;
  processingTime?: number;
  confidence?: number;
  details?: string;
  detections?: Detection[];
  metadata?: Record<string, unknown>;
}
```

**Contract Match**: ⚠️ **PARTIAL MISMATCH**

**Issues**:
1. Backend returns `test_session` data, frontend expects `test_result` data
2. Field name differences:
   - Backend: `results_count` vs Frontend: expects metric fields
   - Backend: `detection_events` vs Frontend: `totalDetections`

---

### GET /api/results/enhanced

**Purpose**: Get enhanced test results with detailed metrics

**Backend Implementation**: `/backend/src/api/results_endpoints.py:118-206`

**Backend Response Model** (`EnhancedSessionResults`):
```python
{
  "session_id": "string",
  "session_name": "string",
  "project_name": "string | null",
  "status": "string",
  "started_at": "string (ISO) | null",
  "completed_at": "string (ISO) | null",
  "metrics": {
    "accuracy": "float | null",      # percentage (0-100)
    "precision": "float | null",     # percentage (0-100)
    "recall": "float | null",        # percentage (0-100)
    "f1_score": "float | null",      # percentage (0-100)
    "success_rate": "float"          # percentage (0-100)
  },
  "detection_summary": {
    "total_detections": "integer",
    "passed_detections": "integer",
    "failed_detections": "integer",
    "detection_types": {
      "<type>": "integer count"
    }
  },
  "statistics": {
    "test_results_count": "integer",
    "detection_events_count": "integer",
    "processing_time": "float | null"  # seconds
  }
}
```

**Frontend Expected Types**:
```typescript
// Frontend expects similar structure via enhancedApiService
// No specific interface defined in types.ts for this endpoint
```

**Contract Match**: ✅ **COMPATIBLE** - Frontend can consume this structure

---

### GET /api/results/{session_id}

**Purpose**: Get detailed results for specific session

**Backend Implementation**: `/backend/src/api/results_endpoints.py:208-292`

**Response**: Same as `/api/results/enhanced` but for single session

**Contract Match**: ✅ **COMPATIBLE**

---

## 3. Test Session Endpoints

### GET /api/test-sessions

**Frontend Usage**: `src/services/enhancedApiService.ts:575-578`

```typescript
async getTestSessions(projectId?: string): Promise<TestSession[]>
```

**Frontend Expected Response**:
```typescript
interface TestSession {
  id: string;
  projectId: string;
  videoId?: string;
  videoIds?: string[];
  name: string;
  description?: string;
  status: 'created' | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  toleranceMs?: number;
  expectedDetections?: number;
  actualDetections?: number;
  passFailResult?: string;
  overallScore?: number;
  // ... many more fields (types.ts:586-628)
}
```

**Backend Implementation**: Needs verification from backend routes

**Contract Match**: ⚠️ **NEEDS VERIFICATION**

---

### GET /api/test-sessions/{sessionId}/results

**Frontend Usage**: `src/services/enhancedApiService.ts:588-590`

```typescript
async getTestResults(sessionId: string): Promise<any>
```

**Contract Match**: ⚠️ **NEEDS TYPE DEFINITION**

**Recommendation**: Define proper TypeScript interface for results

---

## 4. Project Endpoints

### GET /api/projects

**Frontend Usage**: `src/services/enhancedApiService.ts:498-502`

```typescript
async getProjects(skip: number = 0, limit: number = 100): Promise<Project[]>
```

**Frontend Expected Response**:
```typescript
interface Project {
  id: string;
  name: string;
  description?: string;
  cameraModel: string;
  cameraView: CameraType;
  signalType: SignalType;
  lensType?: string;
  resolution?: string;
  frameRate?: number;
  createdAt: string;
  updatedAt?: string;
  status: ProjectStatus;
  testsCount?: number;
  videoCount?: number;
  totalAnnotations?: number;
  averageAccuracy?: number;
  ownerId: string;
}
```

**Contract Match**: ✅ **COMPATIBLE** - Assuming backend uses camelCase serialization

---

## 5. Dashboard Endpoints

### GET /api/dashboard/stats

**Frontend Usage**: `src/services/enhancedApiService.ts:593-595`

```typescript
async getDashboardStats(): Promise<DashboardStats>
```

**Frontend Expected Response**:
```typescript
interface DashboardStats {
  projectCount: number;
  videoCount: number;
  testSessionCount: number;
  detectionEventCount: number;
  averageAccuracy: number;
  activeTests: number;
  totalDetections: number;
}
```

**Backend Implementation**: Needs verification

**Contract Match**: ⚠️ **NEEDS VERIFICATION**

---

## 6. Quality Endpoints (Proposed)

**Note**: These endpoints are NOT currently implemented but are needed for quality features:

### GET /api/test-sessions/{session_id}/quality

**Purpose**: Get quality metrics for a test session

**Proposed Response**:
```json
{
  "session_id": "uuid",
  "quality_level": "high" | "medium" | "low",
  "warnings": [
    {
      "type": "timing_degraded" | "low_confidence" | "detection_gap",
      "severity": "warning" | "error",
      "message": "string",
      "affected_items": 10
    }
  ],
  "statistics": {
    "usable_detections": 95,
    "total_detections": 100,
    "usability_percentage": 95.0,
    "average_confidence": 0.87,
    "timing_issues_count": 5
  }
}
```

**Status**: 🔴 **NOT IMPLEMENTED** - Needs backend development

---

## 7. Detection Endpoints

### POST /api/detections

**Frontend Usage**: Detected in detection services

**Expected Behavior**: Create new detection events

**Contract Match**: ⚠️ **NEEDS VERIFICATION**

---

## 8. Video Endpoints

### POST /api/projects/{projectId}/videos

**Frontend Usage**: `src/services/enhancedApiService.ts:535-558`

```typescript
async uploadVideo(
  projectId: string,
  file: File,
  onProgress?: (progress: number) => void
): Promise<VideoFile>
```

**Request**:
```
Content-Type: multipart/form-data
Body: FormData with 'file' field
```

**Frontend Expected Response**:
```typescript
interface VideoFile {
  id: string;
  filename: string;
  filePath?: string;
  fileSize: number;
  status: VideoValidationStatus;
  validationStatus: ValidationStatus;
  validationType?: ValidationType;
  hilTestingReady: boolean;
  groundTruthGenerated: boolean;
  groundTruthCount: number;
  detectionCount: number;
  annotationCount: number;
  // ... many more fields (types.ts:160-223)
}
```

**Contract Match**: ⚠️ **NEEDS VERIFICATION** - Check backend video response structure

---

## 9. WebSocket Integration

### Socket.IO Configuration

**Backend**: Socket.IO server detected in `socketio_server.py`

**Frontend**: `src/services/websocketService.ts`

**Events**:
- `detection_update`
- `detection_completed`
- `detection_failed`
- `annotation_created`
- `signal_received`

**Contract Match**: ⚠️ **NEEDS VERIFICATION** - Ensure quality data flows through WebSocket

---

## 10. Error Handling Contract

### Backend Error Response Format

**Expected**:
```python
HTTPException(
  status_code=400,
  detail={
    "error": "ValidationError",
    "message": "Invalid UUID format",
    "code": "INVALID_UUID"
  }
)
```

### Frontend Error Handling

**Implementation**: `src/services/enhancedApiService.ts:260-394`

```typescript
interface ApiError {
  message: string;
  code?: string;
  status: number;
  details?: Record<string, unknown>;
}
```

**Contract Match**: ✅ **COMPATIBLE**

---

## 11. Serialization Convention

### Backend Convention
- **Detected**: Mixed snake_case and camelCase
- **Recommended**: Use Pydantic aliases for camelCase output
- **Example**: `model_dump(by_alias=True)`

### Frontend Convention
- **Standard**: camelCase throughout
- **API calls**: Expect camelCase

**Current Status**: ⚠️ **INCONSISTENT** - Needs backend serializer review

---

## 12. Contract Violations & Fixes

### High Priority Issues

1. **Test Results Endpoint Mismatch**
   - **Issue**: Backend returns session data, frontend expects result data
   - **Fix**: Create adapter layer or update backend response model
   - **File**: `/backend/src/api/results_endpoints.py`

2. **Quality Endpoints Missing**
   - **Issue**: Frontend expects quality data, no backend endpoints
   - **Fix**: Implement `/api/test-sessions/{id}/quality` endpoint
   - **Priority**: HIGH

3. **Type Definitions Missing**
   - **Issue**: `getTestResults()` returns `any`
   - **Fix**: Define `TestResultsResponse` interface
   - **File**: `frontend/src/services/types.ts`

### Medium Priority Issues

4. **Serialization Inconsistency**
   - **Issue**: Mixed snake_case/camelCase in responses
   - **Fix**: Add Pydantic aliases to all models
   - **Files**: All backend model files

5. **WebSocket Quality Events**
   - **Issue**: Quality data not emitted via WebSocket
   - **Fix**: Add quality fields to detection events
   - **File**: `/backend/socketio_server.py`

---

## 13. Testing Checklist

- [ ] Test `/api/results` endpoint returns expected structure
- [ ] Test `/api/results/enhanced` with quality data
- [ ] Test `/api/test-sessions/{id}/results` response matches frontend types
- [ ] Test CORS headers on all endpoints
- [ ] Test error responses match frontend error handler
- [ ] Test WebSocket connection and event payloads
- [ ] Test file upload endpoints with large files
- [ ] Test pagination on list endpoints
- [ ] Test filter parameters on all GET endpoints
- [ ] Test authentication/authorization if enabled

---

## 14. Recommendations

### Immediate Actions

1. **Add Quality Endpoints**
   ```python
   @router.get("/api/test-sessions/{session_id}/quality")
   async def get_session_quality(session_id: str, db: Session = Depends(get_db)):
       # Calculate quality metrics
       # Return QualityInfo structure
   ```

2. **Standardize Serialization**
   ```python
   class TestSessionResponse(BaseModel):
       id: str = Field(alias="id")
       project_id: str = Field(alias="projectId")
       # Use aliases throughout

       class Config:
           populate_by_name = True
   ```

3. **Add TypeScript Definitions**
   ```typescript
   interface SessionQualityResponse {
     sessionId: string;
     qualityLevel: 'high' | 'medium' | 'low';
     warnings: QualityWarning[];
     statistics: QualityStatistics;
   }
   ```

### Long-term Improvements

1. **API Versioning**: Add `/api/v1/` prefix
2. **OpenAPI Documentation**: Generate TypeScript types from OpenAPI spec
3. **Contract Testing**: Add Pact or similar for contract tests
4. **GraphQL**: Consider GraphQL for flexible frontend queries

---

## 15. Environment Variables

### Backend Required
```bash
DATABASE_URL=postgresql://user:pass@localhost/dbname
CORS_ORIGINS=["http://localhost:3000"]
ENABLE_MONITORING=true
ALERT_EMAIL_TO=admin@example.com
```

### Frontend Required
```bash
REACT_APP_API_URL=http://localhost:8000
REACT_APP_ENABLE_QUALITY_FEATURES=true
REACT_APP_WEBSOCKET_URL=http://localhost:8000
```

---

## Appendix: API Endpoint Summary

| Method | Endpoint | Status | Quality Support |
|--------|----------|--------|-----------------|
| GET | /api/results | ✅ Implemented | ❌ No |
| GET | /api/results/enhanced | ✅ Implemented | ❌ No |
| GET | /api/results/{id} | ✅ Implemented | ❌ No |
| GET | /api/test-sessions | ⚠️ Needs Verification | ❌ No |
| GET | /api/test-sessions/{id}/results | ⚠️ Needs Verification | ❌ No |
| GET | /api/test-sessions/{id}/quality | 🔴 Not Implemented | ✅ Planned |
| GET | /api/projects | ✅ Implemented | N/A |
| GET | /api/dashboard/stats | ⚠️ Needs Verification | ❌ No |
| POST | /api/projects/{id}/videos | ✅ Implemented | N/A |

**Legend**:
- ✅ Implemented and verified
- ⚠️ Implemented but needs verification
- 🔴 Not implemented
- ❌ No quality support
- ✅ Quality support included
- N/A = Not applicable

---

**Next Steps**: Proceed with endpoint testing and integration test creation.
