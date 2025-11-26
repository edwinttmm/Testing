# Architecture Decision Record: Timing Quality Tracking

## Status
**ACCEPTED** - 2025-11-19

## Context

The AI Model Validation Platform performs ground truth matching between hardware detection events (LabJack) and video-based ground truth annotations. The accuracy of this matching depends critically on timing precision.

### Problems Identified

1. **Data Corruption Risk**: When timing data is degraded (e.g., using wall clock instead of hardware timestamps), ground truth matching produces invalid results
2. **No Quality Indicators**: System had no way to track whether timing was reliable
3. **Blind Trust**: All timing data was treated as equally valid, regardless of source
4. **Debugging Difficulty**: When validation failed, no way to determine if timing was the cause

### Example Failure Scenario

```
Video Event:    timestamp = 1000.500 (wall clock)
Hardware Event: timestamp = 1000.512 (LabJack precise)
Tolerance:      ±100ms

Problem: Wall clock may have 10-50ms error
Result: False positive match OR false negative miss
Impact: Corrupted validation results
```

## Decision

Add timing quality tracking columns to TestSession and DetectionEvent tables to:

1. **Track timing source quality** - Distinguish precision hardware timing from degraded wall clock
2. **Enable validation filtering** - Exclude degraded data from ground truth matching
3. **Provide audit trail** - Historical record of timing quality
4. **Support verification** - Flag when timing has been cross-validated

### Schema Changes

#### TestSession
- `timing_degraded: Boolean` - Indicates degraded timing (wall clock vs precision)
- `timing_verified: Boolean` - Indicates timing has been database-verified

#### DetectionEvent
- `usable_for_validation: Boolean` - Master flag for validation eligibility
- `timing_degraded: Boolean` - Per-detection timing quality

## Rationale

### Why Boolean Flags?

**Alternatives Considered:**
1. **Enum field** (quality: high/medium/low)
   - ❌ Harder to query
   - ❌ More complex to maintain
   - ❌ Over-engineering for binary decision (use/don't use)

2. **Timestamp accuracy field** (error_ms: float)
   - ❌ Requires complex threshold logic
   - ❌ Harder to interpret
   - ❌ No clear pass/fail criteria

3. **Quality score** (score: 0.0-1.0)
   - ❌ Arbitrary scoring
   - ❌ Threshold ambiguity
   - ❌ Over-engineering

**Why Booleans Won:**
- ✅ Simple and clear
- ✅ Fast queries (indexed)
- ✅ Binary decision matches use case
- ✅ Easy to understand and maintain

### Why Two Flags on TestSession?

**`timing_degraded`**:
- Tracks whether timing source was degraded at capture time
- Permanent quality indicator
- Cannot be changed after session completion

**`timing_verified`**:
- Tracks whether timing has been cross-validated post-capture
- Can be updated after verification process
- Indicates confidence level in timing data

**Rationale**: Separating source quality from verification status enables:
1. Quick filtering of known-bad data (`timing_degraded=true`)
2. Identification of unverified data (`timing_verified=false`)
3. Progressive verification without modifying source quality

### Why Additional Flag on DetectionEvent?

**`usable_for_validation`**:
- Master flag controlling validation eligibility
- May be false even if timing is good (e.g., other quality issues)
- Provides override capability

**Rationale**: Validation eligibility depends on multiple factors:
- Timing quality
- Detection confidence
- Hardware signal quality
- Manual review results

Having a master flag simplifies queries and allows holistic quality control.

## Trade-offs

### Storage Cost
- **Impact**: +4 bytes per test_session, +2 bytes per detection_event
- **Mitigation**: Negligible for typical deployments (<1% increase)
- **Benefit**: Far outweighs storage cost

### Migration Complexity
- **Challenge**: Updating existing records without downtime
- **Solution**: Conservative defaults (mark as degraded until verified)
- **Risk**: Low (additive changes, backward compatible)

### Query Complexity
- **Before**: `SELECT * FROM detection_events WHERE test_session_id = ?`
- **After**: `SELECT * FROM detection_events WHERE test_session_id = ? AND usable_for_validation = true`
- **Mitigation**: Defaults ensure backward compatibility
- **Benefit**: Explicit quality control

## Consequences

### Positive

1. **Data Integrity**: Prevents corruption from degraded timing
2. **Debuggability**: Clear indicators when timing is suspect
3. **Confidence**: Explicit verification tracking
4. **Performance**: Indexed filtering for fast queries
5. **Backward Compatible**: Defaults preserve existing behavior

### Negative

1. **Manual Work**: Requires verifying existing sessions
2. **Code Updates**: Need to set flags in new code
3. **Monitoring**: New metrics to track
4. **Training**: Team needs to understand flags

### Mitigation Strategies

**For Manual Work**:
- Provide migration script with conservative defaults
- Create verification tools
- Automate verification where possible

**For Code Updates**:
- Add to documentation
- Include in templates
- Code review checklist

**For Monitoring**:
- Add dashboard metrics
- Alert on high degraded percentage
- Regular reporting

**For Training**:
- Documentation and examples
- Code comments
- Team review meeting

## Implementation Notes

### Migration Strategy

**Phase 1**: Schema Changes
```bash
alembic upgrade head
```
- Add columns with defaults
- Create indexes
- Zero downtime

**Phase 2**: Data Migration
```bash
python scripts/migrate_existing_sessions.py
```
- Mark existing sessions as degraded (conservative)
- Mark existing detections as usable (preserve history)
- Verify results

**Phase 3**: Code Updates
- Update session creation code
- Update detection creation code
- Add filtering to validation queries

**Phase 4**: Verification
- Review flagged sessions
- Update verified sessions
- Monitor metrics

### Usage Pattern

```python
# Creating a session with quality tracking
session = TestSession(
    name="HIL Test",
    timing_degraded=False,      # Precision timing used
    timing_verified=True,       # Already verified
    precision_timing_enabled=True
)

# Creating a detection with quality tracking
detection = DetectionEvent(
    timestamp=1234.567,
    usable_for_validation=True,  # Valid for matching
    timing_degraded=False,       # Precision timing
    labjack_timestamp=1234.567   # Hardware timestamp available
)

# Querying with quality filters
validated_sessions = db.query(TestSession).filter(
    TestSession.timing_verified == True,
    TestSession.timing_degraded == False
).all()
```

## Alternatives Considered

### Alternative 1: Timing Quality Score (0.0-1.0)

**Pros**:
- Granular quality indication
- Can track continuous improvement
- More information

**Cons**:
- Ambiguous threshold for filtering
- Complex calculation logic
- Harder to query efficiently
- Over-engineering for binary use case

**Decision**: Rejected - Too complex for the problem

### Alternative 2: Timing Source Enum

**Pros**:
- Explicit source tracking (hardware/wall clock/interpolated)
- Future extensible

**Cons**:
- Requires mapping to pass/fail
- More database types to manage
- Harder to filter
- Unnecessary granularity

**Decision**: Rejected - Boolean sufficient

### Alternative 3: Separate Validation Tables

**Pros**:
- Clean separation of concerns
- Audit trail separate from core data
- Historical tracking

**Cons**:
- Join complexity
- Query performance impact
- Over-engineering
- Migration complexity

**Decision**: Rejected - Denormalized flags simpler

### Alternative 4: Do Nothing

**Pros**:
- No migration needed
- No code changes
- Zero effort

**Cons**:
- Data corruption continues
- No debugging capability
- Trust issues persist
- Validation unreliable

**Decision**: Rejected - Unacceptable risk

## Success Criteria

The implementation will be considered successful if:

1. **Data Integrity**: Zero data corruption from timing issues after deployment
2. **Visibility**: 100% of sessions have timing quality tracked
3. **Performance**: No measurable query performance degradation
4. **Adoption**: Team consistently uses flags in new code
5. **Migration**: Clean migration with no data loss

## Monitoring & Validation

### Key Metrics

```sql
-- Timing quality distribution
SELECT
    timing_degraded,
    timing_verified,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
FROM test_sessions
GROUP BY timing_degraded, timing_verified;

-- Unusable detections
SELECT
    COUNT(*) as unusable_count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM detection_events) as percentage
FROM detection_events
WHERE usable_for_validation = false;

-- Verification progress
SELECT COUNT(*) as unverified_count
FROM test_sessions
WHERE timing_verified = false;
```

### Alerts

- **Alert**: >10% sessions marked as degraded
- **Alert**: >5% detections marked unusable
- **Warning**: >100 unverified sessions older than 7 days

## Related Decisions

- **ADR-001**: Precision Timing Implementation
- **ADR-002**: Ground Truth Matching Algorithm
- **ADR-003**: LabJack Integration Architecture

## References

- [Timing Quality Implementation Summary](/docs/TIMING_QUALITY_IMPLEMENTATION_SUMMARY.md)
- [Database Migration Guide](/docs/DATABASE_MIGRATION_GUIDE.md)
- [Models Documentation](/models.py)

---

**Decision made by**: System Architecture Designer
**Date**: 2025-11-19
**Reviewers**: Database Team, Validation Team, QA Team
**Status**: Accepted and Implemented
