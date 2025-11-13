# API Schema Standardization - Deployment Guide

**Date:** 2025-11-11
**Sprint:** Schema Cleanup
**Assignee:** API Schema Standardization Specialist

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Access to database migrations
- Access to backend and frontend code

### Phase 1: Backend Deployment (COMPLETED ✅)

```bash
# 1. Install humps package
cd ai-model-validation-platform/backend
source venv/bin/activate
pip install humps

# 2. Verify schemas exist
ls -l schemas/hil_results.py

# 3. Run backend tests (if available)
pytest tests/test_schema_standardization.py
```

**Status:** ✅ COMPLETE
- humps installed
- `/backend/schemas/hil_results.py` created with all response models
- CamelCaseModel configured with proper alias generation

### Phase 2: Endpoint Integration (TODO)

```bash
# 1. Update enhanced HIL results endpoint
# File: /backend/src/api/enhanced_hil_results_endpoints.py

# 2. Import new schemas
from schemas.hil_results import (
    EnhancedHILResultsResponse,
    GroundTruthComparison,
    DetectionEventSchema,
    PerVideoResult
)

# 3. Update endpoint to use response_model
@router.get(
    "/test-sessions/{session_id}/corrected-results",
    response_model=EnhancedHILResultsResponse
)
def get_enhanced_hil_results(...):
    # Return Pydantic model instead of dict
    return EnhancedHILResultsResponse(...)

# 4. Restart backend
sudo systemctl restart hil-backend
```

### Phase 3: Frontend Cleanup (TODO)

```bash
cd ai-model-validation-platform/frontend

# 1. Remove normalization file
rm src/utils/hilResultsNormalization.ts

# 2. Update API service
# File: src/services/api.ts
# Remove: return normalizeHILResults(data);
# Replace with: return data;

# 3. Update imports
# Remove: import { normalizeHILResults } from '../utils/hilResultsNormalization';

# 4. Rebuild frontend
npm run build

# 5. Restart frontend
npm start
```

### Phase 4: Database Migration (TODO)

```bash
cd ai-model-validation-platform/backend

# 1. Create migration file
alembic revision -m "add_approval_workflow_fields"

# 2. Edit migration file
# Add:
ALTER TABLE test_sessions ADD COLUMN outcome VARCHAR(20);
ALTER TABLE test_sessions ADD COLUMN outcome_reasons JSON;
ALTER TABLE test_sessions ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE test_sessions ADD COLUMN approved_by VARCHAR(255);
ALTER TABLE test_sessions ADD COLUMN approved_at TIMESTAMP;

# 3. Run migration
alembic upgrade head
```

## Testing Checklist

### Backend Tests

```bash
# Test 1: Verify camelCase serialization
curl http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results | jq .

# Expected: Only camelCase fields
{
  "sessionId": "...",
  "groundTruthComparison": {
    "truePositives": 10,
    "falsePositives": 2,
    "falseNegatives": 1,
    "precision": 0.83,
    "recall": 0.91,
    "f1Score": 0.87
  }
}

# Test 2: Verify NO snake_case duplicates
curl http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results | jq 'keys[]' | grep '_'

# Expected: No output (no snake_case fields)

# Test 3: Response size check
curl -w "%{size_download}\n" http://localhost:8000/api/enhanced-hil/test-sessions/{session_id}/corrected-results

# Expected: ~50% smaller than before
```

### Frontend Tests

```bash
# Test 1: Verify no normalization imports
grep -r "normalizeHILResults" frontend/src/

# Expected: No matches

# Test 2: Build success
cd frontend && npm run build

# Expected: No TypeScript errors

# Test 3: Runtime test
# Open browser DevTools
# Navigate to HIL Results page
# Verify: No console errors about missing fields
```

### Integration Tests

```python
# tests/test_schema_standardization.py

def test_no_duplicate_fields():
    """Verify API response contains ONLY camelCase fields"""
    response = client.get("/api/enhanced-hil/test-sessions/{id}/corrected-results")
    data = response.json()

    # Check for snake_case duplicates
    assert "session_id" not in data
    assert "ground_truth_comparison" not in data

    # Check camelCase fields exist
    assert "sessionId" in data
    assert "groundTruthComparison" in data

def test_new_approval_fields():
    """Verify new approval workflow fields present"""
    response = client.get("/api/enhanced-hil/test-sessions/{id}/corrected-results")
    data = response.json()

    assert "outcome" in data
    assert "outcomeReasons" in data
    assert "approvalStatus" in data
```

## Rollback Plan

If issues arise:

### Backend Rollback

```bash
# 1. Revert to previous endpoint code
git checkout HEAD~1 backend/src/api/enhanced_hil_results_endpoints.py

# 2. Restart backend
sudo systemctl restart hil-backend
```

### Frontend Rollback

```bash
# 1. Restore normalization file
git checkout HEAD~1 frontend/src/utils/hilResultsNormalization.ts
git checkout HEAD~1 frontend/src/services/api.ts

# 2. Rebuild
npm run build

# 3. Restart
npm start
```

## Performance Monitoring

### Metrics to Track

| Metric | Before | Target | Monitor |
|--------|--------|--------|---------|
| Response Size | ~2.5KB | ~1.3KB | Network tab |
| Field Count | 50+ | 25 | JSON keys |
| Parse Time | ~5ms | ~2ms | Performance API |
| Memory Usage | ~500KB | ~250KB | Chrome DevTools |

### Monitoring Commands

```bash
# Response size
curl -w "%{size_download} bytes\n" -o /dev/null -s \
  http://localhost:8000/api/enhanced-hil/test-sessions/{id}/corrected-results

# Field count
curl -s http://localhost:8000/api/enhanced-hil/test-sessions/{id}/corrected-results | \
  jq '[paths(scalars)] | length'

# Latency
curl -w "Time: %{time_total}s\n" -o /dev/null -s \
  http://localhost:8000/api/enhanced-hil/test-sessions/{id}/corrected-results
```

## Troubleshooting

### Issue 1: "Field not found" errors in frontend

**Symptom:** Console errors about missing fields

**Solution:**
```typescript
// Check field names in API response
console.log(Object.keys(data));

// Verify camelCase usage
// Wrong: data.session_id
// Right: data.sessionId
```

### Issue 2: Pydantic validation errors

**Symptom:** 422 Unprocessable Entity

**Solution:**
```python
# Check model field types match database
# Verify alias configuration
model_config = ConfigDict(
    alias_generator=snake_to_camel,
    populate_by_name=True,
    by_alias=True
)
```

### Issue 3: Database migration fails

**Symptom:** Column already exists error

**Solution:**
```sql
-- Check existing columns
SELECT column_name FROM information_schema.columns
WHERE table_name = 'test_sessions';

-- Drop duplicate columns if needed
ALTER TABLE test_sessions DROP COLUMN IF EXISTS outcome;
```

## Production Deployment

### Pre-deployment Checklist

- [ ] All tests passing
- [ ] Backend schemas created
- [ ] Endpoints updated
- [ ] Frontend normalization removed
- [ ] Database migration ready
- [ ] Rollback plan verified
- [ ] Monitoring configured

### Deployment Steps

1. **Deploy database migration**
   ```bash
   alembic upgrade head
   ```

2. **Deploy backend**
   ```bash
   git pull origin main
   sudo systemctl restart hil-backend
   ```

3. **Deploy frontend**
   ```bash
   git pull origin main
   npm run build
   npm start
   ```

4. **Smoke test**
   ```bash
   curl http://production-url/api/enhanced-hil/test-sessions/{id}/corrected-results
   ```

5. **Monitor logs**
   ```bash
   tail -f /var/log/hil-backend.log
   tail -f /var/log/hil-frontend.log
   ```

## Success Criteria

✅ **Backend:**
- API returns ONLY camelCase fields
- No snake_case duplicates in responses
- All tests passing
- Response size reduced by ~48%

✅ **Frontend:**
- No normalization code present
- TypeScript compilation successful
- UI renders correctly
- No console errors

✅ **Integration:**
- End-to-end workflow functional
- Performance improved
- No regressions

## Documentation Updates

After successful deployment, update:

1. API documentation (OpenAPI spec)
2. Frontend type definitions
3. Developer onboarding guides
4. Architecture decision records

## Support

**Questions:** Escalate to Backend API Developer or Tech Lead

**Issues:** Create ticket in issue tracker with label `schema-standardization`

**Emergency:** Use rollback plan immediately
