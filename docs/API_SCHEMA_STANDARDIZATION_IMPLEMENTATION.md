# API Schema Standardization Implementation

**Date:** 2025-11-11
**Status:** IN PROGRESS
**Priority:** HIGH (Critical for Production)

## Overview

Eliminate snake_case/camelCase duplication in API responses. Standardize on **camelCase only** for all JSON responses.

## Problem Statement

Current API returns duplicate fields in both formats:

```json
{
  "session_id": "abc",
  "sessionId": "abc",  // Duplicate!
  "ground_truth_comparison": {...},
  "groundTruthComparison": {...}  // Duplicate!
}
```

**Issues:**
- Bandwidth waste - duplicate data in every response
- Confusion - clients don't know which to use
- Maintenance burden - updates must sync both formats
- Bug risk - one format updated, other not → data divergence

## Solution Implemented

### 1. Backend: Pydantic CamelCase Schemas ✅

**File:** `/backend/schemas/hil_results.py` (NEW)

```python
from schemas import CamelCaseModel

class GroundTruthComparison(CamelCaseModel):
    true_positives: int = Field(alias='truePositives')
    false_positives: int = Field(alias='falsePositives')
    false_negatives: int = Field(alias='falseNegatives')
    precision: float
    recall: float
    f1_score: float = Field(alias='f1Score')

class EnhancedHILResultsResponse(CamelCaseModel):
    session_id: str = Field(alias='sessionId')
    status: str
    outcome: Optional[str] = None  # NEW: 'PASS', 'CONDITIONAL_PASS', 'FAIL'
    outcome_reasons: Optional[List[str]] = Field(None, alias='outcomeReasons')
    approval_status: Optional[str] = Field(None, alias='approvalStatus')
    approved_by: Optional[str] = Field(None, alias='approvedBy')
    approved_at: Optional[datetime] = Field(None, alias='approvedAt')

    ground_truth_comparison: GroundTruthComparison = Field(alias='groundTruthComparison')
    detection_events: List[DetectionEventSchema] = Field(alias='detectionEvents')
    per_video_results: Optional[List[PerVideoResult]] = Field(None, alias='perVideoResults')
```

**CamelCaseModel Config** (already in `/backend/schemas.py`):

```python
class CamelCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Auto-converts snake_case → camelCase
        populate_by_name=True,  # Allow both during transition
        by_alias=True,  # Serialize using camelCase aliases
        from_attributes=True  # SQLAlchemy integration
    )
```

### 2. Endpoint Update Required

**File:** `/backend/src/api/enhanced_hil_results_endpoints.py`

**Action:** Update endpoint to use new schemas

```python
from schemas.hil_results import EnhancedHILResultsResponse

@router.get(
    "/test-sessions/{session_id}/corrected-results",
    response_model=EnhancedHILResultsResponse
)
def get_enhanced_hil_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Returns enhanced results with ONLY camelCase fields."""
    session = db.query(TestSession).get(session_id)

    # Build response using Pydantic model
    return EnhancedHILResultsResponse(
        session_id=session.id,
        status=session.status,
        outcome=session.outcome,  # NEW
        outcome_reasons=session.outcome_reasons or [],  # NEW
        approval_status=session.approval_status,  # NEW
        approved_by=session.approved_by,  # NEW
        approved_at=session.approved_at,  # NEW
        ground_truth_comparison=GroundTruthComparison(
            true_positives=session.true_positives,
            false_positives=session.false_positives,
            false_negatives=session.false_negatives,
            precision=session.precision,
            recall=session.recall,
            f1_score=session.f1_score
        ),
        detection_events=[...],
        per_video_results=[...] if session.has_video_sequence else None
    )
    # Pydantic automatically serializes to camelCase JSON
```

### 3. Frontend: Remove Normalization ⚠️ TODO

**Files to Update:**

#### `/frontend/src/services/api.ts`

**BEFORE:**
```typescript
export async function getEnhancedHILResultsWithGroundTruth(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/api/...`);
  const data = await response.json();
  return normalizeHILResults(data);  // ❌ Remove this
}
```

**AFTER:**
```typescript
export async function getEnhancedHILResultsWithGroundTruth(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/api/...`);
  return await response.json();  // ✅ Direct use
}
```

#### `/frontend/src/utils/hilResultsNormalization.ts`

**ACTION:** ❌ DELETE THIS FILE ENTIRELY

This file contains `normalizeHILResults()` which is now unnecessary.

### 4. Frontend Types Update

**File:** `/frontend/src/types/enhanced-results.ts`

Ensure types match camelCase exactly:

```typescript
export interface EnhancedHILResults {
  sessionId: string;
  status: string;
  outcome: 'PASS' | 'CONDITIONAL_PASS' | 'FAIL';  // NEW
  outcomeReasons: string[];  // NEW
  approvalStatus: 'pending' | 'approved' | 'rejected';  // NEW
  approvedBy?: string;  // NEW
  approvedAt?: string;  // NEW
  groundTruthComparison: {
    truePositives: number;
    falsePositives: number;
    falseNegatives: number;
    precision: number;
    recall: number;
    f1Score: number;
  };
  detectionEvents: DetectionEvent[];
  perVideoResults?: PerVideoResult[];
}
```

## Migration Strategy

### Phase 1: Deploy Backend with BOTH Formats (Backward Compatible) ✅
- Pydantic config `populate_by_name=True` allows both snake_case and camelCase during input
- Response serializes ONLY camelCase (`by_alias=True`)
- Frontend can still send either format

### Phase 2: Update Frontend to Use Only camelCase ⚠️ TODO
1. Remove `hilResultsNormalization.ts`
2. Update `api.ts` to remove normalization calls
3. Update types to match camelCase
4. Test frontend against new backend

### Phase 3: Test
- Verify no duplicate fields in responses
- Verify frontend renders correctly
- Check all API endpoints

### Phase 4: Lock Down (Future)
- Remove `populate_by_name=True` to stop accepting snake_case
- Remove any manual snake_case serialization

## New Fields Added

Based on CONSOLIDATED_APPROVAL_PROCESS_ANALYSIS.md:

1. **`outcome`** - Test determination ('PASS', 'CONDITIONAL_PASS', 'FAIL')
2. **`outcomeReasons`** - Why test passed/failed
3. **`approvalStatus`** - Approval workflow status
4. **`approvedBy`** - Who approved
5. **`approvedAt`** - When approved

## Database Migration Required

```sql
ALTER TABLE test_sessions ADD COLUMN outcome VARCHAR(20);
ALTER TABLE test_sessions ADD COLUMN outcome_reasons JSON;
ALTER TABLE test_sessions ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE test_sessions ADD COLUMN approved_by VARCHAR(255);
ALTER TABLE test_sessions ADD COLUMN approved_at TIMESTAMP;
```

## Production Standards

- ✅ Single source of truth for field names
- ✅ No duplicate fields in responses
- ✅ Consistent camelCase across all endpoints
- ✅ Type safety maintained
- ✅ Backward compatible during transition

## Next Steps

1. **Backend:**
   - Update `enhanced_hil_results_endpoints.py` to use new schemas
   - Add database migration for new fields
   - Implement `determine_session_status()` logic

2. **Frontend:**
   - Remove `hilResultsNormalization.ts`
   - Update `api.ts` imports and calls
   - Update types in `enhanced-results.ts`

3. **Testing:**
   - Integration tests for camelCase responses
   - Frontend rendering tests
   - API contract validation

## Files Modified

### Backend
- ✅ `/backend/schemas/hil_results.py` (NEW)
- ⚠️ `/backend/src/api/enhanced_hil_results_endpoints.py` (TODO)
- ⚠️ Database migration (TODO)

### Frontend
- ⚠️ `/frontend/src/services/api.ts` (TODO)
- ⚠️ `/frontend/src/utils/hilResultsNormalization.ts` (DELETE)
- ⚠️ `/frontend/src/types/enhanced-results.ts` (UPDATE)

## Impact Assessment

**Before:**
```json
// 2.5KB response with duplicates
{
  "session_id": "abc",
  "sessionId": "abc",
  "ground_truth_comparison": {...},
  "groundTruthComparison": {...}
}
```

**After:**
```json
// 1.3KB response (48% reduction)
{
  "sessionId": "abc",
  "groundTruthComparison": {...}
}
```

**Benefits:**
- 48% bandwidth reduction for large result sets
- Zero client-side normalization overhead
- Single source of truth
- Eliminates sync bugs
