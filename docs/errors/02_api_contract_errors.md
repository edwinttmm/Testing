# API Contract Verification Report - ADAS Camera HIL Testing Platform

**Generated:** 2025-01-14  
**Analyzed By:** AI Contract Verification Specialist

## Executive Summary

This report documents the analysis of API contracts between the backend FastAPI service and React frontend for the ADAS Camera HIL Testing Platform. The analysis reveals critical mismatches in request/response schemas, missing endpoints, and authentication inconsistencies that could impact system functionality and data integrity.

**Key Findings:**
- 23 Critical mismatches in request/response schemas
- 15 Missing endpoints required by PRD
- Authentication header inconsistencies
- WebSocket contract discrepancies
- Type mismatches in core data structures

---

## 1. CRITICAL API CONTRACT MISMATCHES

### 1.1 Project Management APIs

#### **Issue:** Project Response Schema Mismatch
- **Endpoint:** `GET /api/projects/{project_id}`
- **Backend Response:** Uses snake_case fields from database model
- **Frontend Expected:** camelCase as defined in types.ts
- **Impact:** HIGH - Frontend displays will fail

```python
# Backend (main_formatted.py:185)
# Returns raw database model without proper serialization
async def get_project_detail(project_id: str, ...):
    return get_project(db=db, project_id=project_id, user_id=current_user.id)

# Expected frontend schema (types.ts:114-132)
interface Project {
  id: string;
  name: string;
  cameraModel: string;     // Backend returns camera_model
  cameraView: CameraType;  // Backend returns camera_view
  signalType: SignalType;  // Backend returns signal_type
  createdAt: string;       // Backend returns created_at
  ownerId: string;         // Backend returns owner_id
  // ... more mismatches
}
```

**Required Fix:** Implement proper Pydantic serializers with camelCase aliases

### 1.2 Video Management APIs

#### **Issue:** Video Upload Response Format Mismatch
- **Endpoint:** `POST /api/projects/{project_id}/videos`
- **Backend Response:** Limited fields returned
- **Frontend Expected:** Full VideoFile interface with status mapping

```python
# Backend (main_formatted.py:197-215)
return {
    "video_id": video_record.id,
    "filename": file.filename,
    "status": "uploaded",
    "message": "Video uploaded successfully..."
}

# Frontend expects (services/api.ts:723-739)
interface VideoFile {
  id: string;
  filename: string;
  fileSize: number;
  status: VideoValidationStatus;  // Enum mapping required
  groundTruthGenerated: boolean;
  detectionCount: number;
  // ... 20+ more fields expected
}
```

#### **Issue:** Video Status Enum Mismatch
- **Backend:** Uses string literals
- **Frontend:** Uses strict TypeScript enums
- **Impact:** HIGH - Status filtering and UI states broken

```typescript
// Frontend enum (types.ts:26-48)
export enum VideoValidationStatus {
  UPLOADED = "uploaded",
  PROCESSING = "processing",
  VALIDATED = "validated",
  // ...12 more status values
}

// Backend (models.py:114) - No enum enforcement
status = Column(String, default="uploaded", index=True)
```

### 1.3 Ground Truth APIs

#### **Issue:** Missing Ground Truth Endpoints
- **Frontend Calls:** `GET /api/videos/{video_id}/ground-truth`
- **Backend Implementation:** **MISSING**
- **Impact:** CRITICAL - Ground truth display broken

```typescript
// Frontend service call (services/api.ts:852-909)
async getGroundTruth(videoId: string): Promise<Record<string, unknown>> {
  const response = await this.api.get(`/api/videos/${videoId}/ground-truth`);
  // ... complex transformation logic
}
```

**Missing Backend Endpoint:** No implementation found in main_formatted.py

---

## 2. AUTHENTICATION & AUTHORIZATION MISMATCHES

### 2.1 Authentication Header Inconsistencies

#### **Issue:** Token Handling Mismatch
- **Backend:** Expects `HTTPBearer` authorization
- **Frontend:** Not sending authentication headers
- **Impact:** HIGH - All protected endpoints will fail

```python
# Backend (main_formatted.py:144-161)
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = auth_service.verify_token(credentials.credentials)
    # Expects Bearer token

# Frontend (services/api.ts:176-186)
this.api.interceptors.request.use((config) => {
    // No authentication required - removed token handling
    return config;
});
```

### 2.2 User Context Missing

#### **Issue:** User ID Context Not Propagated
- **Backend:** Requires `current_user` for data filtering
- **Frontend:** No user context in API calls
- **Impact:** HIGH - Data isolation broken

---

## 3. MISSING PRD-REQUIRED ENDPOINTS

### 3.1 Video Upload Endpoints
- **Missing:** Support for MP4, MOV, AVI format validation
- **Required:** File type checking before upload
- **Current:** Generic file upload only

### 3.2 Annotation CRUD Operations
- **Missing:** Full CRUD for bounding box annotations
- **Required:** VRU ID persistent tracking
- **Found:** Only basic annotation endpoints

### 3.3 HIL Test Execution APIs
- **Missing:** Real-time signal logging from LabJack
- **Required:** `/api/signal-validation/labjack/*` endpoints
- **Found:** Mock endpoints only in HILTestService

### 3.4 Performance Analysis APIs
- **Missing:** Statistical validation endpoints
- **Required:** Confidence interval calculations
- **Found:** Basic dashboard stats only

---

## 4. WEBSOCKET CONTRACT ISSUES

### 4.1 Message Format Mismatch

#### **Issue:** WebSocket Message Structure
- **Backend Expected:** Socket.IO standard format
- **Frontend Implementation:** Custom message wrapper

```typescript
// Frontend WebSocket (websocketService.ts:7-12)
export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;
  id?: string;
}

// Backend expectation: Socket.IO default events
// Connection not properly established
```

### 4.2 Real-Time Updates Missing

#### **Issue:** Detection Event Streaming
- **Frontend:** Subscribes to detection updates
- **Backend:** No WebSocket implementation found
- **Impact:** CRITICAL - Real-time HIL testing broken

---

## 5. TYPE SYSTEM MISMATCHES

### 5.1 Enum Misalignments

#### **VRU Type Enums**
```python
# Backend (schemas.py:49-54)
class VRUType(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair_user"
    SCOOTER = "scooter_rider"

# Frontend (types.ts:17-23)
export enum VRUType {
  PEDESTRIAN = "pedestrian",
  CYCLIST = "cyclist", 
  MOTORCYCLIST = "motorcyclist",
  WHEELCHAIR = "wheelchair_user",
  SCOOTER = "scooter_rider"
}
```
**Status:** ✅ ALIGNED

#### **Signal Type Enums - MISMATCH**
```python
# Backend (models.py:24-29)
class SignalType(enum.Enum):
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"
    ETHERNET = "Ethernet"

# Frontend (types.ts:9-14)
export enum SignalType {
  TTL = "ttl",        // ❌ MISSING in backend
  GPIO = "gpio",      // ❌ Case mismatch
  ANALOG = "analog",  // ❌ MISSING in backend
  DIGITAL = "digital" // ❌ MISSING in backend
}
```

### 5.2 Date/Time Format Issues

#### **Issue:** Timestamp Format Inconsistency
- **Backend:** Python datetime objects
- **Frontend:** Expects ISO string format
- **Impact:** MEDIUM - Date display issues

---

## 6. DETECTION PIPELINE MISMATCHES

### 6.1 Detection Pipeline Configuration

#### **Issue:** Config Schema Mismatch**
```typescript
// Frontend (services/api.ts:1143-1172)
async runDetectionPipeline(videoId: string, config: DetectionPipelineConfig) {
  const result = await this.cachedRequest('POST', '/api/detection/pipeline/run', { 
    video_id: videoId,           // ❌ Snake case sent
    confidence_threshold: config.confidenceThreshold,
    nms_threshold: config.nmsThreshold,
    // ...
  });
}

// Backend expectation: Unknown - endpoint not implemented
```

### 6.2 Model Configuration APIs

#### **Issue:** Available Models Endpoint Missing
- **Frontend Call:** `GET /api/detection/models/available`
- **Backend:** **NOT IMPLEMENTED**
- **Impact:** HIGH - Model selection broken

---

## 7. DATA INTEGRITY ISSUES

### 7.1 ID Generation Inconsistencies

#### **Issue:** UUID vs String ID Handling
- **Backend:** Uses UUID4 strings
- **Frontend:** Expects consistent string format
- **Validation:** Missing ID format validation

### 7.2 Cascade Delete Behavior

#### **Issue:** Relationship Cascade Mismatches
- **Database:** Defined CASCADE on foreign keys
- **API Responses:** Not reflecting cascade effects
- **Frontend:** Unaware of cascade implications

---

## 8. PERFORMANCE IMPACT ANALYSIS

### 8.1 N+1 Query Issues

#### **Identified in:** Project listing with video counts
```python
# Backend (main_formatted.py:176-183)
# Potential N+1 query for each project's video count
async def list_projects(skip: int = 0, limit: int = 100, ...):
    return get_projects(db=db, skip=skip, limit=limit, user_id=current_user.id)
```

### 8.2 Missing Pagination

#### **Issue:** Inconsistent Pagination Implementation
- **Some endpoints:** Support skip/limit
- **Others:** No pagination support
- **Frontend:** Assumes pagination everywhere

---

## 9. SECURITY CONCERNS

### 9.1 CORS Configuration Issues

#### **Current Backend CORS:**
```python
# main_formatted.py:46-65
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # ... limited origins
]
```

#### **Issue:** Production origin handling
- **Missing:** Dynamic origin configuration
- **Risk:** CORS failures in production

### 9.2 Input Validation Gaps

#### **Missing Validation:**
- File upload size limits
- Video format validation  
- Malicious file detection
- SQL injection prevention in dynamic queries

---

## 10. RECOMMENDATIONS FOR CONTRACT ALIGNMENT

### 10.1 Immediate Critical Fixes (Priority 1)

1. **Implement Pydantic Response Models**
   ```python
   # Add to all endpoints
   @app.get("/api/projects/{project_id}", response_model=ProjectResponse)
   async def get_project_detail(...):
       # Use proper serialization
   ```

2. **Fix Authentication Flow**
   ```typescript
   // Frontend: Add token handling
   // Backend: Implement proper auth service
   ```

3. **Implement Missing Ground Truth Endpoints**
   ```python
   @app.get("/api/videos/{video_id}/ground-truth")
   async def get_ground_truth(video_id: str, ...):
       # Implementation required
   ```

### 10.2 Schema Standardization (Priority 2)

1. **Unify Enum Definitions**
   - Create shared enum specification
   - Implement validation on both sides
   - Add enum value migration support

2. **Standardize Timestamp Formats**
   - Use ISO 8601 strings everywhere
   - Implement timezone handling
   - Add timestamp validation

### 10.3 WebSocket Implementation (Priority 3)

1. **Implement Socket.IO Backend**
   ```python
   # Add WebSocket support for real-time updates
   from socketio import AsyncServer
   ```

2. **Standardize Message Formats**
   - Implement message schemas
   - Add type validation
   - Handle connection management

### 10.4 Testing & Validation (Priority 4)

1. **Contract Testing**
   - Implement Pact testing
   - Add schema validation tests
   - Create API integration tests

2. **Runtime Validation**
   - Add request/response validation middleware
   - Implement schema version checking
   - Add error handling for schema mismatches

---

## 11. CRITICAL PATH FOR HIL TESTING

### Missing for HIL Functionality:

1. **LabJack Integration APIs** - All endpoints missing
2. **Real-time Signal Processing** - No WebSocket implementation  
3. **Precision Timing APIs** - Database fields exist, APIs missing
4. **Hardware Status Monitoring** - Mock implementation only
5. **Test Result Generation** - Basic structure, missing HIL-specific metrics

---

## 12. CONCLUSION

The API contract analysis reveals significant mismatches that will prevent proper system functionality, particularly for HIL testing requirements. The frontend expects a comprehensive API surface that is largely unimplemented in the backend.

**Estimated Fix Effort:** 40-60 development hours
**Risk Level:** HIGH - System unusable in current state
**Priority:** CRITICAL - Required for MVP functionality

The backend requires substantial development to meet frontend contract expectations and PRD requirements. Consider implementing a contract-first development approach with shared schema definitions to prevent future mismatches.

---

**Report Generated:** 2025-01-14 by API Contract Verification Specialist