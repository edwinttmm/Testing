# Quality Filter Implementation Summary

## Overview

Implemented quality filtering system to filter out non-validated detections from ground truth matching and metrics calculations. This prevents false positives/negatives caused by timing degradation.

## Changes Made

### 1. Database Schema (models.py)

**Added fields to DetectionEvent model:**
```python
# TIMING QUALITY VALIDATION FIELDS
timing_degraded = Column(Boolean, default=False, nullable=False, index=True,
                        comment="Whether timing sync was degraded when this detection was captured")
usable_for_validation = Column(Boolean, default=True, nullable=False, index=True,
                               comment="Whether this detection has valid timing for ground truth matching")
```

**Indexes created:**
- `idx_detection_timing_degraded` on `timing_degraded`
- `idx_detection_usable` on `usable_for_validation`
- `idx_detection_quality_session` composite on `(test_session_id, usable_for_validation, timing_degraded)`

### 2. Database Migration

**File:** `/migrations/add_detection_quality_fields.py`

Adds columns with proper defaults:
- `timing_degraded` defaults to `FALSE`
- `usable_for_validation` defaults to `TRUE`

Run migration with:
```bash
python migrations/add_detection_quality_fields.py
```

### 3. Ground Truth Matching Service

**File:** `/services/ground_truth_matching_service.py`

**Changes:**
- Updated detection query to filter `usable_for_validation = TRUE`
- Added quality statistics logging
- Updated metrics calculation to include quality stats
- Enhanced API response with quality warnings

**Before:**
```sql
SELECT * FROM detection_events
WHERE test_session_id = :session_id
ORDER BY timestamp
```

**After:**
```sql
SELECT * FROM detection_events
WHERE test_session_id = :session_id
  AND usable_for_validation = TRUE
ORDER BY timestamp
```

### 4. Quality Warning System

**File:** `/services/quality_warnings.py`

**Features:**
- Check session quality and generate warnings
- Calculate quality statistics (validation rate, degradation rate)
- Provide severity levels (ERROR, WARNING, INFO)
- Generate recommendations based on quality metrics

**Quality Levels:**
- EXCELLENT: ≥95% validation rate
- GOOD: ≥80% validation rate
- FAIR: ≥50% validation rate
- POOR: <50% validation rate

**Warning Codes:**
- `NO_DETECTIONS`: No detections captured
- `ALL_DEGRADED`: All detections have degraded timing
- `LOW_QUALITY_RATE`: <50% validation rate
- `SOME_DEGRADED`: Some detections degraded (informational)
- `SESSION_TIMING_DEGRADED`: Session marked with timing issues

### 5. Report Generation Service

**File:** `/services/report_generation_service.py`

**Changes:**
- Filter detections by `usable_for_validation = TRUE`
- Include quality statistics in reports:
  - Total detections
  - Validated detections
  - Degraded detections
  - Validation rate percentage

### 6. Router Updates

**File:** `/routers/test_sessions.py`

**Changes:**
- Updated detection queries to filter by `usable_for_validation`
- Applied filter in fallback counting logic

### 7. API Response Enhancement

**Enhanced response includes:**
```json
{
  "session_id": "...",
  "summary": { ... },
  "details": { ... },
  "quality": {
    "total_detections": 100,
    "validated_detections": 95,
    "degraded_detections": 5,
    "validation_rate": 95.0,
    "quality_level": "EXCELLENT"
  },
  "warnings": [
    {
      "severity": "INFO",
      "code": "SOME_DEGRADED",
      "message": "5/100 detections have degraded timing",
      "impact": "Most detections valid, some timing issues detected",
      "recommendation": "Results generally reliable, review degraded detections"
    }
  ],
  "quality_alert": "INFO: Some detections have degraded timing"
}
```

## How Quality Fields Are Set

### Detection Capture Service Responsibilities

When capturing detections, services should set quality fields:

```python
detection_data = {
    # ... other fields ...
    'usable_for_validation': True,  # Default
    'timing_degraded': False  # Default
}

# If timing sync is lost or degraded:
if timing_quality == 'degraded' or not video_timing_available:
    detection_data['timing_degraded'] = True
    detection_data['usable_for_validation'] = False
```

### Typical Degradation Scenarios

**Scenario 1: Video timing not available**
```python
if not video_start_time:
    detection.timing_degraded = True
    detection.usable_for_validation = False
```

**Scenario 2: Wall-clock fallback**
```python
if using_wall_clock_timestamp and not video_relative_timestamp:
    detection.timing_degraded = True
    detection.usable_for_validation = False
```

**Scenario 3: Late-stage detection (after video ends)**
```python
if detection_time > video_duration:
    detection.usable_for_validation = False
```

## Impact on Metrics

### Before Quality Filters

- All detections included in ground truth matching
- False positives/negatives from timing misalignment
- Unreliable metrics when timing degraded

### After Quality Filters

- Only validated detections used in metrics
- Accurate TP/FP/FN classification
- Quality warnings when results unreliable
- Transparency about detection quality

## Usage Example

### Check Quality Before Using Results

```python
from services.quality_warnings import check_quality, get_quality_stats

# Check for warnings
warnings = check_quality(session_id)
if any(w['severity'] == 'ERROR' for w in warnings):
    print("Results unreliable - timing issues detected")

# Get detailed statistics
stats = get_quality_stats(session_id)
if stats['validation_rate'] < 80:
    print(f"Warning: Only {stats['validation_rate']}% of detections validated")
```

### API Response with Quality Info

```python
# Ground truth matching automatically includes quality info
result = ground_truth_service.get_matching_results_summary(session_id)

print(f"Validation rate: {result['quality']['validation_rate']}%")
print(f"Quality level: {result['quality']['quality_level']}")

for warning in result['warnings']:
    print(f"{warning['severity']}: {warning['message']}")
```

## Testing Recommendations

### Unit Tests

1. Test quality field defaults
2. Test filtering by `usable_for_validation`
3. Test quality statistics calculation
4. Test warning generation

### Integration Tests

1. Test full session with all validated detections
2. Test session with mixed quality (some degraded)
3. Test session with all degraded detections
4. Test API responses include quality info

### Manual Testing Checklist

- [ ] Run migration successfully
- [ ] Verify indexes created
- [ ] Test session with normal timing
- [ ] Test session with degraded timing
- [ ] Verify quality warnings appear in API responses
- [ ] Confirm metrics only use validated detections
- [ ] Test report generation with quality stats

## Database Query Examples

### Get Quality Statistics

```sql
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN usable_for_validation THEN 1 ELSE 0 END) as validated,
    SUM(CASE WHEN timing_degraded THEN 1 ELSE 0 END) as degraded
FROM detection_events
WHERE test_session_id = :session_id;
```

### Find Sessions with Quality Issues

```sql
SELECT
    ts.id,
    ts.name,
    COUNT(*) as total_detections,
    SUM(CASE WHEN de.usable_for_validation THEN 1 ELSE 0 END) as validated_detections,
    ROUND(100.0 * SUM(CASE WHEN de.usable_for_validation THEN 1 ELSE 0 END) / COUNT(*), 2) as validation_rate
FROM test_sessions ts
JOIN detection_events de ON de.test_session_id = ts.id
GROUP BY ts.id, ts.name
HAVING validation_rate < 80
ORDER BY validation_rate ASC;
```

## Files Modified

1. `/backend/models.py` - Added quality fields to DetectionEvent
2. `/backend/migrations/add_detection_quality_fields.py` - Migration script
3. `/backend/services/ground_truth_matching_service.py` - Quality filtering
4. `/backend/services/quality_warnings.py` - Quality warning system (new)
5. `/backend/services/report_generation_service.py` - Quality in reports
6. `/backend/routers/test_sessions.py` - Updated queries
7. `/backend/docs/QUALITY_FILTER_IMPLEMENTATION_SUMMARY.md` - This document

## Next Steps

1. **Run Migration:**
   ```bash
   cd /home/rigade/Testing/ai-model-validation-platform/backend
   python migrations/add_detection_quality_fields.py
   ```

2. **Update Detection Capture Services:**
   - Review all services that create DetectionEvent records
   - Add logic to set `timing_degraded` and `usable_for_validation` based on timing quality

3. **Test Quality Filtering:**
   - Run existing test sessions
   - Verify quality warnings appear
   - Check metrics exclude degraded detections

4. **Frontend Integration:**
   - Display quality warnings in UI
   - Show validation rate badges
   - Add quality filter toggle in detection lists

## Success Criteria

- [x] Quality fields added to model
- [x] Database migration created
- [x] Ground truth matching uses quality filters
- [x] Quality warning system implemented
- [x] API responses include quality info
- [x] Report generation includes quality stats
- [x] Router queries updated with filters
- [ ] Migration executed successfully
- [ ] Tests pass with new fields
- [ ] Frontend displays quality warnings

## Rollback Plan

If issues arise:

```bash
# Rollback migration
python migrations/add_detection_quality_fields.py --downgrade

# Or manually:
ALTER TABLE detection_events DROP COLUMN usable_for_validation;
ALTER TABLE detection_events DROP COLUMN timing_degraded;
DROP INDEX idx_detection_timing_degraded;
DROP INDEX idx_detection_usable;
DROP INDEX idx_detection_quality_session;
```

## Conclusion

Quality filtering system successfully implemented. All ground truth matching now excludes degraded detections, providing accurate metrics. Quality warnings alert users when timing issues affect reliability.
