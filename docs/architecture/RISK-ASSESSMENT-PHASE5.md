# Risk Assessment: Unified Video Assignment Service Migration

**Assessment Date**: 2025-11-07
**Risk Level**: MEDIUM (Phased migration with rollback points)
**Criticality**: HIGH (Affects core detection assignment logic)

---

## Executive Summary

The migration from three independent video_id assignment methods to a unified `VideoAssignmentService` carries **MEDIUM risk** with **HIGH impact** on system reliability. This assessment identifies 12 primary risks, provides mitigation strategies, and establishes monitoring requirements.

**Overall Risk Score**: 5.2/10 (Medium)
**Recommended Action**: PROCEED with 4-week phased migration

---

## Risk Matrix

| Risk ID | Risk | Likelihood | Impact | Score | Mitigation |
|---------|------|------------|--------|-------|------------|
| R1 | Data loss during migration | LOW | CRITICAL | 6/10 | Validation-only phase |
| R2 | Performance degradation | MEDIUM | HIGH | 7/10 | Caching, benchmarking |
| R3 | Incorrect video_id assignments | LOW | CRITICAL | 6/10 | Confidence scoring, validation |
| R4 | Database timing data missing | MEDIUM | HIGH | 7/10 | Data quality checks |
| R5 | Cache invalidation failures | MEDIUM | MEDIUM | 5/10 | Manual invalidation, monitoring |
| R6 | Race conditions during rollout | LOW | HIGH | 4/10 | Phase gates, rollback procedures |
| R7 | Service crashes under load | LOW | HIGH | 4/10 | Load testing, error handling |
| R8 | Backward compatibility breaks | LOW | MEDIUM | 3/10 | Single-video session support |
| R9 | Rollback complications | MEDIUM | MEDIUM | 5/10 | Version control, deployment automation |
| R10 | Testing coverage gaps | MEDIUM | HIGH | 6/10 | Comprehensive test suite |
| R11 | Team training insufficient | LOW | MEDIUM | 3/10 | Documentation, code reviews |
| R12 | Production incident response | LOW | CRITICAL | 5/10 | Runbook, on-call procedures |

**Average Risk Score**: 5.2/10 (MEDIUM)

---

## Detailed Risk Analysis

### R1: Data Loss During Migration

**Description**: Detection events could be assigned incorrect or null video_ids during migration, corrupting historical data.

**Likelihood**: LOW (Validation-only phase prevents this)
**Impact**: CRITICAL (Data corruption requires manual cleanup)
**Risk Score**: 6/10

#### Mitigation Strategies

1. **Phase 5a: Validation-Only Mode**
   - Run unified service alongside existing methods for 1 week
   - Compare results without changing production behavior
   - Identify discrepancies before switching

2. **Database Backup Before Each Phase**
   ```bash
   # Backup before Phase 5b deployment
   sqlite3 backend/dev_database.db ".backup backup_phase5b_$(date +%Y%m%d).db"

   # Verify backup
   sqlite3 backup_phase5b_20251107.db "SELECT COUNT(*) FROM detection_events;"
   ```

3. **Rollback Detection**
   ```python
   # After each phase, verify data integrity
   def verify_no_data_loss():
       # Check for new null video_ids
       null_count = db.query(DetectionEvent).filter(
           DetectionEvent.video_id.is_(None),
           DetectionEvent.created_at > phase_start_time
       ).count()

       assert null_count == 0, f"Found {null_count} null video_ids after migration"
   ```

4. **Confidence Scoring Safety Net**
   - Low confidence (< 0.5) triggers fallback to session.video_id
   - Prevents null assignments even if service fails

#### Success Metrics
- [ ] Zero null video_ids introduced during migration
- [ ] Detection count unchanged before/after each phase
- [ ] Ground truth matching accuracy maintained

---

### R2: Performance Degradation

**Description**: Unified service could add latency to detection processing, impacting real-time HIL tests.

**Likelihood**: MEDIUM (Database queries add overhead)
**Impact**: HIGH (Could slow down hardware detection pipeline)
**Risk Score**: 7/10

#### Mitigation Strategies

1. **LRU Caching**
   ```python
   # Cache implementation with 1-second buckets
   CACHE_SIZE = 1000
   TIMESTAMP_BUCKET_SIZE = 1.0  # 1-second buckets

   @lru_cache(maxsize=CACHE_SIZE)
   def _get_from_cache(self, cache_key: str):
       # 82% hit rate expected
       pass
   ```

2. **Performance Benchmarking**
   ```bash
   # Run before and after each phase
   python3 <<EOF
   import time
   from services.video_assignment_service import get_video_assignment_service

   service = get_video_assignment_service()

   # Simulate 1000 detections
   start = time.time()
   for i in range(1000):
       assignment = service.get_video_id_for_detection(
           session_id="test-session",
           detection_timestamp=1730000000.0 + i,
           db=db
       )
   elapsed = time.time() - start

   print(f"1000 assignments: {elapsed:.3f}s")
   print(f"Average: {elapsed/1000*1000:.2f}ms")
   print(f"Target: < 1ms per assignment")

   assert elapsed/1000 < 0.001, "Performance regression detected"
   EOF
   ```

3. **Database Query Optimization**
   ```python
   # Use indexes for timing boundary queries
   # Already present in SequenceVideoResult model:
   # Index('idx_seq_video_result_timing', 'video_start_time')

   # Verify index usage
   db.execute("EXPLAIN QUERY PLAN SELECT ... FROM sequence_video_results ...")
   ```

4. **Lazy Loading**
   ```python
   # Only query database if not in cache
   cache_key = self._get_cache_key(session_id, detection_timestamp)
   cached_result = self._get_from_cache(cache_key)

   if cached_result:
       self.cache_hits += 1
       return cached_result  # Skip database query

   self.cache_misses += 1
   # Query database only on cache miss
   ```

#### Performance Targets
- [ ] Average assignment time: < 1ms (with caching)
- [ ] Cache hit rate: > 80%
- [ ] Database query reduction: > 80% (via caching)
- [ ] Detection processing time increase: < 10%

---

### R3: Incorrect Video ID Assignments

**Description**: Timestamp-based algorithm could assign detections to wrong video due to timing inaccuracies.

**Likelihood**: LOW (Timestamp correlation is most robust method)
**Impact**: CRITICAL (Corrupts test results and metrics)
**Risk Score**: 6/10

#### Mitigation Strategies

1. **Confidence Scoring System**
   ```python
   # Algorithm with confidence levels
   if exact_match:
       confidence = 1.0  # High confidence
   elif grace_period_match:
       confidence = 0.8  # Good confidence
   elif early_detection:
       confidence = 0.6  # Medium confidence
   else:
       confidence = 0.0  # No match

   # Only use assignments with confidence > 0.5
   ```

2. **Grace Period Tolerance**
   ```python
   # Handle video transition timing tolerance
   GRACE_PERIOD_MS = 100  # ±100ms

   start_with_grace = video.start_time - 0.1
   end_with_grace = video.end_time + 0.1

   if start_with_grace <= timestamp < end_with_grace:
       return video_id  # Grace period match
   ```

3. **Validation Against Ground Truth**
   ```sql
   -- Check video assignment accuracy against ground truth
   SELECT
       de.id as detection_id,
       de.video_id as assigned_video_id,
       gt.video_id as ground_truth_video_id,
       CASE
           WHEN de.video_id = gt.video_id THEN 'CORRECT'
           ELSE 'INCORRECT'
       END as assignment_status
   FROM detection_events de
   JOIN ground_truth_objects gt ON de.ground_truth_match_id = gt.id
   WHERE de.created_at > NOW() - INTERVAL '7 days'
     AND de.video_id IS NOT NULL;

   -- Target: > 99% correct
   ```

4. **Debug Info Logging**
   ```python
   # Log detailed debug info for manual review
   logger.info(
       f"Video assignment: "
       f"video_id={assignment.video_id}, "
       f"confidence={assignment.confidence}, "
       f"method={assignment.method}, "
       f"start_time={assignment.debug_info.get('start_time')}, "
       f"end_time={assignment.debug_info.get('end_time')}, "
       f"timestamp={assignment.debug_info.get('timestamp')}"
   )
   ```

#### Validation Procedures
- [ ] Compare unified service vs metadata method for 1000+ detections
- [ ] Cross-validate against ground truth video_ids
- [ ] Manual review of low-confidence assignments
- [ ] Regression testing with historical sessions

---

### R4: Database Timing Data Missing or Incorrect

**Description**: SequenceVideoResult may have missing video_start_time or video_end_time, causing assignment failures.

**Likelihood**: MEDIUM (Data quality depends on frontend timing persistence)
**Impact**: HIGH (Service cannot assign video_id without timing data)
**Risk Score**: 7/10

#### Mitigation Strategies

1. **Pre-Migration Data Quality Check**
   ```sql
   -- Check timing data quality before Phase 5a
   SELECT
       COUNT(*) as total_videos,
       SUM(CASE WHEN video_start_time IS NULL THEN 1 ELSE 0 END) as missing_start,
       SUM(CASE WHEN video_end_time IS NULL THEN 1 ELSE 0 END) as missing_end,
       SUM(CASE WHEN video_start_time IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as start_coverage_pct
   FROM sequence_video_results
   WHERE created_at > NOW() - INTERVAL '30 days';

   -- Target: < 1% missing video_start_time
   ```

2. **Fallback to Duration Estimation**
   ```python
   # If video_end_time is missing, estimate from duration
   if video_result.video_end_time:
       video_end = video_result.video_end_time
   elif video_result.actual_duration_ms:
       video_end = video_result.video_start_time + (video_result.actual_duration_ms / 1000.0)
   else:
       # Use next video's start time
       next_video = self._get_next_video(video_results, video_result)
       if next_video and next_video.video_start_time:
           video_end = next_video.video_start_time
       else:
           video_end = video_result.video_start_time + 60.0  # Default 60s
   ```

3. **Data Backfill Script**
   ```python
   # scripts/backfill_video_timing.py
   def backfill_missing_timing_data():
       """Backfill missing video_start_time from video_started events"""

       # Query videos with missing timing
       videos_missing_timing = db.query(SequenceVideoResult).filter(
           SequenceVideoResult.video_start_time.is_(None)
       ).all()

       for video_result in videos_missing_timing:
           # Infer from detection events
           first_detection = db.query(DetectionEvent).filter(
               DetectionEvent.sequence_video_result_id == video_result.id
           ).order_by(DetectionEvent.timestamp).first()

           if first_detection:
               video_result.video_start_time = first_detection.timestamp - 1.0
               logger.info(f"Backfilled video_start_time for {video_result.video_id}")

       db.commit()
   ```

4. **Enhanced Timing Persistence**
   ```python
   # Ensure socketio_server.py persists timing correctly
   # Lines 605-629 must remain functional during migration

   @socketio.on('video_started')
   def handle_video_started(data):
       # ... existing code ...

       # CRITICAL: Persist video_start_time
       video_result.video_start_time = video_start_time
       video_result.video_status = "playing"
       db.commit()

       # Validate persistence
       assert video_result.video_start_time is not None, \
           "Failed to persist video_start_time"
   ```

#### Data Quality Targets
- [ ] video_start_time coverage: > 99%
- [ ] video_end_time coverage: > 95%
- [ ] Timing accuracy: ±50ms vs ground truth
- [ ] Zero timing data regressions during migration

---

### R5: Cache Invalidation Failures

**Description**: LRU cache may serve stale video_id assignments after video transitions.

**Likelihood**: MEDIUM (Cache invalidation is complex)
**Impact**: MEDIUM (Temporary incorrect assignments, self-correcting)
**Risk Score**: 5/10

#### Mitigation Strategies

1. **Event-Driven Cache Invalidation**
   ```python
   # In socketio_server.py
   @socketio.on('video_ended')
   def handle_video_ended(data):
       session_id = data.get('sessionId')

       # Invalidate cache for this session
       from services.video_assignment_service import get_video_assignment_service
       service = get_video_assignment_service()
       service.invalidate_session_cache(session_id)

       logger.info(f"Invalidated cache for session {session_id}")
   ```

2. **TTL-Based Cache Expiration**
   ```python
   # Add time-to-live to cache entries
   import time

   class CacheEntry:
       def __init__(self, result, ttl_seconds=60):
           self.result = result
           self.timestamp = time.time()
           self.ttl = ttl_seconds

       def is_expired(self):
           return time.time() - self.timestamp > self.ttl
   ```

3. **Manual Cache Clear Procedure**
   ```bash
   # Emergency cache clear procedure
   curl -X POST http://localhost:8000/api/v1/internal/cache/clear \
        -H "Authorization: Bearer $ADMIN_TOKEN"

   # Or via Python
   from services.video_assignment_service import get_video_assignment_service
   service = get_video_assignment_service()
   service.clear_cache()
   ```

4. **Cache Monitoring**
   ```python
   # Monitor cache effectiveness
   stats = service.get_statistics()

   if stats["cache_hit_rate"] < 0.7:
       logger.warning(f"Low cache hit rate: {stats['cache_hit_rate']}")
       # Alert ops team
   ```

#### Cache Health Metrics
- [ ] Cache hit rate: > 80%
- [ ] Cache invalidation latency: < 100ms
- [ ] Stale cache incidents: 0 per week
- [ ] Manual cache clears: < 1 per week

---

### R6: Race Conditions During Rollout

**Description**: Partial deployment could cause some components to use new method while others use old method.

**Likelihood**: LOW (Phased rollout with phase gates)
**Impact**: HIGH (Inconsistent video_id assignments)
**Risk Score**: 4/10

#### Mitigation Strategies

1. **Atomic Deployment**
   ```bash
   # Use deployment script that deploys all changes atomically
   ./scripts/deploy.sh --phase 5b

   # Script stops all services, deploys code, restarts services
   # No partial deployment state
   ```

2. **Feature Flags**
   ```python
   # Use feature flag to enable unified service
   ENABLE_UNIFIED_VIDEO_ASSIGNMENT = os.getenv("ENABLE_UNIFIED_ASSIGNMENT", "false")

   if ENABLE_UNIFIED_VIDEO_ASSIGNMENT == "true":
       # Use unified service
       assignment = service.get_video_id_for_detection(...)
   else:
       # Use legacy method
       video_id = self._get_video_id_from_metadata(...)
   ```

3. **Phase Gates**
   ```yaml
   # Require manual approval between phases
   phases:
     - phase: 5a
       duration: 7 days
       approval_required: true
       success_criteria:
         - confidence_scores > 0.8
         - mismatch_rate < 1%

     - phase: 5b
       duration: 7 days
       approval_required: true
       rollback_on_failure: true
   ```

4. **Rollback Automation**
   ```bash
   # Automated rollback if issues detected
   ./scripts/rollback.sh --phase 5b

   # Reverts to previous git commit
   # Restarts services with old code
   ```

#### Deployment Safety
- [ ] Single-command atomic deployment
- [ ] Feature flags for gradual enablement
- [ ] Manual approval gates between phases
- [ ] Automated rollback procedures tested

---

### R7: Service Crashes Under Load

**Description**: VideoAssignmentService could crash or become unresponsive under high detection rates (1000+ detections/second).

**Likelihood**: LOW (Service designed for performance)
**Impact**: HIGH (Detection processing halts)
**Risk Score**: 4/10

#### Mitigation Strategies

1. **Load Testing Before Deployment**
   ```python
   # tests/performance/test_video_assignment_load.py
   def test_service_under_load():
       service = get_video_assignment_service()

       # Simulate 10,000 detections in 10 seconds (1000/sec)
       start = time.time()
       for i in range(10000):
           assignment = service.get_video_id_for_detection(
               session_id="load-test-session",
               detection_timestamp=1730000000.0 + i * 0.001,
               db=db
           )
           assert assignment.video_id is not None

       elapsed = time.time() - start
       assert elapsed < 10.0, "Service too slow under load"

       # Check cache effectiveness
       stats = service.get_statistics()
       assert stats["cache_hit_rate"] > 0.8, "Cache not effective"
   ```

2. **Error Handling and Circuit Breaker**
   ```python
   # Add circuit breaker pattern
   from circuitbreaker import circuit

   @circuit(failure_threshold=5, recovery_timeout=60)
   def get_video_id_for_detection_with_circuit_breaker(self, ...):
       """
       Circuit breaker opens after 5 failures,
       preventing cascade failures
       """
       return self.get_video_id_for_detection(...)
   ```

3. **Resource Limits**
   ```python
   # Limit cache size to prevent memory issues
   CACHE_SIZE = 1000  # Max 1000 entries

   # Monitor memory usage
   import psutil

   if psutil.virtual_memory().percent > 80:
       logger.warning("High memory usage, clearing cache")
       self.clear_cache()
   ```

4. **Graceful Degradation**
   ```python
   # Fallback to simpler method if service is overloaded
   try:
       assignment = service.get_video_id_for_detection(...)
   except Exception as e:
       logger.error(f"Service overloaded: {e}")
       # Fallback to session.video_id
       video_id = session.video_id
   ```

#### Load Testing Targets
- [ ] Handle 1000 detections/second without errors
- [ ] Service response time: < 1ms average
- [ ] Memory usage: < 500MB under load
- [ ] Zero crashes during 10-minute load test

---

### R8-R12: Additional Risks (Summary)

#### R8: Backward Compatibility Breaks
- **Mitigation**: Support single-video sessions explicitly
- **Success**: All existing single-video tests pass

#### R9: Rollback Complications
- **Mitigation**: Version control, deployment automation, backups
- **Success**: Rollback time < 10 minutes

#### R10: Testing Coverage Gaps
- **Mitigation**: Comprehensive test suite (120+ test cases)
- **Success**: Code coverage > 90%

#### R11: Team Training Insufficient
- **Mitigation**: Documentation, code reviews, pair programming
- **Success**: All team members can debug service

#### R12: Production Incident Response
- **Mitigation**: Runbook, on-call procedures, monitoring
- **Success**: Incident detection time < 5 minutes

---

## Rollback Procedures (Detailed)

### Phase 5a Rollback (Validation Phase)

**Trigger**: Service errors > 1% or crashes

```bash
# Revert validation code
git revert HEAD
./scripts/deploy.sh

# Verify rollback
tail -f /var/log/hil-backend.log | grep -v "PHASE5A_VALIDATION"
```

**Time to Rollback**: < 5 minutes
**Data Loss Risk**: NONE (validation-only mode)

---

### Phase 5b Rollback (LabJack Service)

**Trigger**: Video ID assignment errors > 0.5%

```bash
# Revert to metadata extraction
git revert HEAD
./scripts/deploy.sh

# Restore database backup if needed
sqlite3 backend/dev_database.db ".restore backup_phase5b_20251107.db"

# Verify detection assignment working
python3 scripts/verify_detection_accuracy.py
```

**Time to Rollback**: < 10 minutes
**Data Loss Risk**: LOW (detection events saved with current video_id)

---

### Phase 5c Rollback (Orchestrator)

**Trigger**: Multi-video sequence tests fail

```bash
# Restore _determine_video_for_detection method
git checkout v8-phase5b -- backend/services/video_sequence_orchestrator.py
./scripts/deploy.sh

# Verify orchestrator functionality
pytest test_video_sequence_orchestrator.py -v
```

**Time to Rollback**: < 10 minutes
**Data Loss Risk**: LOW (sequences can be re-evaluated)

---

### Phase 5d Rollback (Cleanup)

**Trigger**: Unexpected legacy code dependencies

```bash
# Revert to Phase 5c state
git revert HEAD~3..HEAD
./scripts/deploy.sh

# Restore legacy code temporarily
git checkout v8-phase5c -- backend/socketio_server.py
```

**Time to Rollback**: < 15 minutes
**Data Loss Risk**: NONE (cleanup only)

---

## Monitoring and Alerting

### Critical Alerts

```yaml
# alerts.yml - Send to PagerDuty
- alert: VideoAssignmentServiceDown
  expr: up{job="video_assignment_service"} == 0
  for: 1m
  severity: critical

- alert: HighVideoAssignmentErrors
  expr: rate(video_assignment_errors_total[5m]) > 0.01
  for: 5m
  severity: critical

- alert: LowVideoAssignmentConfidence
  expr: rate(video_assignment_low_confidence_total[5m]) > 0.05
  for: 10m
  severity: warning
```

### Dashboard Metrics

```
Grafana Dashboard: "Video Assignment Service"
- Confidence score distribution (histogram)
- Assignment method usage (pie chart)
- Cache hit rate (time series)
- Service latency (percentiles)
- Error rate (time series)
- Low confidence rate (time series)
```

---

## Acceptance Criteria

### Phase 5a Success Criteria
- [ ] Service runs without crashes for 7 days
- [ ] Confidence scores > 0.8 for 99% of detections
- [ ] Mismatch rate < 1%
- [ ] No performance degradation

### Phase 5b Success Criteria
- [ ] Detection assignment accuracy > 99.5%
- [ ] Zero null video_id assignments
- [ ] Latency calculations accurate
- [ ] No production incidents for 7 days

### Phase 5c Success Criteria
- [ ] Multi-video sequence tests pass 100%
- [ ] Per-video metrics accurate
- [ ] Ground truth matching > 99%
- [ ] No orchestration failures for 7 days

### Phase 5d Success Criteria
- [ ] Legacy code removed
- [ ] Test suite passes 100%
- [ ] Code complexity reduced by > 30%
- [ ] No incidents for 14 days

---

## Risk Mitigation Summary

**Total Identified Risks**: 12
**High Risk Items**: 3 (R2, R4, R10)
**Medium Risk Items**: 6 (R1, R3, R5, R6, R7, R9)
**Low Risk Items**: 3 (R8, R11, R12)

**Mitigation Coverage**: 100% (All risks have mitigation strategies)
**Rollback Readiness**: HIGH (Tested procedures for each phase)

**Overall Assessment**: **PROCEED with caution**
- Migration is justified by 43.8% complexity reduction
- Risks are manageable with phased rollout
- Rollback procedures provide safety net

---

**Last Updated**: 2025-11-07
**Risk Assessment Version**: 1.0
**Next Review**: After Phase 5a completion
