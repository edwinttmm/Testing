# Backend/Frontend Discrepancies Analysis

## Critical Issues Found

### 1. Authentication System Mismatch
**Backend:**
- Has `AuthUser` model with full authentication infrastructure
- Has `UserSession` management table
- **BUT** all API endpoints use hardcoded `user_id="anonymous"`
- No authentication endpoints implemented (login, register, logout)

**Frontend:**
- Expects authentication tokens in API calls
- Has user management interfaces
- Missing actual auth integration

**Impact:** Complete authentication system non-functional

### 2. Missing CRUD Operations

#### Backend Missing Endpoints:
- **Annotations:** No UPDATE or DELETE endpoints
- **GroundTruthObject:** No CREATE, UPDATE, DELETE (read-only)
- **Users:** No registration, login, profile management
- **TestResults:** No detailed results management
- **DetectionComparison:** No management endpoints

#### Frontend Expecting:
- Full CRUD for annotations
- User authentication flow
- Test results visualization
- Detection comparison tools

### 3. Data Model Mismatches

#### Field Name Inconsistencies:
**Backend uses snake_case:**
- `camera_model`, `camera_view`, `signal_type`
- `frame_rate`, `created_at`, `updated_at`
- `ground_truth_generated`, `processing_status`

**Frontend uses camelCase:**
- `cameraModel`, `cameraView`, `signalType`
- `frameRate`, `createdAt`, `updatedAt`
- `groundTruthGenerated`, `processingStatus`

**Current Solution:** Frontend has duplicate fields for both formats (inefficient)

### 4. Database Schema Issues

#### Backend Tables:
1. **Redundant Fields:**
   - `DetectionEvent` has both normalized (x, y, width, height) and JSON (bounding_box) fields
   - Multiple timestamp formats (Float vs DateTime)

2. **Missing Relationships:**
   - No direct link between `DetectionEvent` and `Annotation`
   - `VideoProjectLink` not properly utilized

3. **Index Overload:**
   - 241 indexes across 13 tables (excessive)
   - Many composite indexes overlap

### 5. API Response Inconsistencies

**Backend Returns:**
```python
{
  "id": "uuid",
  "camera_model": "string",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Frontend Expects:**
```typescript
{
  "id": "string",
  "cameraModel": "string",
  "createdAt": "string"
}
```

### 6. WebSocket Integration Issues

**Backend:**
- Socket.IO server configured but events not properly emitted
- Missing real-time detection updates

**Frontend:**
- WebSocket service expects specific event formats
- Reconnection logic assumes authentication

### 7. File Upload Handling

**Backend:**
- Saves to local filesystem
- No cloud storage integration
- Basic file validation only

**Frontend:**
- Expects cloud URLs
- Assumes chunked upload support
- Progress tracking not synchronized

### 8. Test Session Workflow

**Backend:**
- Complex detection validation logic
- Statistical analysis in JSON fields

**Frontend:**
- Expects structured results
- Missing visualization components

## Required Fixes Priority

### Priority 1 (Critical):
1. Implement authentication endpoints
2. Fix field name consistency (use serializers)
3. Complete annotation CRUD operations
4. Fix WebSocket event emission

### Priority 2 (Important):
5. Implement user management
6. Add ground truth management endpoints
7. Standardize API responses
8. Fix file upload/URL generation

### Priority 3 (Enhancement):
9. Optimize database indexes
10. Add missing relationships
11. Implement proper error handling
12. Add comprehensive logging

## Implementation Plan

### Phase 1: Authentication (8 hours)
- [ ] Add /auth/register endpoint
- [ ] Add /auth/login endpoint
- [ ] Add /auth/logout endpoint
- [ ] Add JWT middleware
- [ ] Update all endpoints to use real user_id

### Phase 2: Data Consistency (6 hours)
- [ ] Create response serializers for snake_case to camelCase
- [ ] Update all endpoints to use serializers
- [ ] Remove duplicate fields from frontend

### Phase 3: Missing Features (12 hours)
- [ ] Complete annotation CRUD
- [ ] Add ground truth management
- [ ] Implement test results API
- [ ] Add detection comparison endpoints

### Phase 4: Real-time Features (4 hours)
- [ ] Fix Socket.IO event emission
- [ ] Add detection progress events
- [ ] Implement annotation collaboration

### Phase 5: File Management (4 hours)
- [ ] Add proper file URL generation
- [ ] Implement chunked uploads
- [ ] Add progress tracking

## TypeScript Issues Related to Discrepancies

Many of the 1275 TypeScript errors are caused by:
1. Type mismatches between API responses and interfaces
2. Optional vs required field conflicts
3. Duplicate field definitions
4. Missing error handling types
5. Incorrect WebSocket message types

## Recommendations

1. **Immediate Action:** Fix authentication to unblock user features
2. **Short Term:** Standardize API responses with proper serialization
3. **Medium Term:** Complete missing CRUD operations
4. **Long Term:** Refactor database schema to remove redundancy

## Estimated Time to Fix: 34 hours of focused development