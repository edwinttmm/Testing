# HIL Test Retest Instructions
## Complete Validation Procedure for Timestamp Fixes

**Target Session**: New HIL test (previous: e8e108b0-cb20-4cba-a2db-fc29f21efd16)
**Expected Outcome**: Zero duplicates, F1/Precision/Recall ≥ 0.70

---

## Prerequisites

### 1. Verify Fixes Are In Place

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Check temporal expansion has None confidence fix
grep -n "confidence_raw" src/services/temporal_expansion.py
# Should show line 136-137 with None handling

# Check timestamp compensation service exists
ls -lh src/services/timestamp_compensation_service.py

# Check duplicate detection WebSocket fix
grep -n "room='detections'" socketio_server.py
# Should return NO results (lines removed)
```

**Expected**: All files exist and contain fixes

---

## Step 1: Start Backend Server

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate

# Verify database connection (fix credentials if needed)
export DATABASE_URL="postgresql://YOUR_USER:YOUR_PASS@localhost:5432/ai_model_validation"

# Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Monitor logs for**:
- "Timestamp Compensation Service initialized"
- "Application startup complete"

---

## Step 2: Run HIL Test

```bash
# In new terminal
cd /home/rigade/Testing/hil-validation-for-ai-model

# Run hardware-in-the-loop test
# (Follow HIL test specific instructions)
```

**During test, monitor backend logs for**:
```
✓ Temporal expansion complete: N → M detections (expansion factor: 13.0×)
✓ Compensated N detections ... with drift=X.XXms
✓ Detection synchronized: t_rel=X.XXXXXXs, frame=N
```

---

## Step 3: Capture Test Session ID

After test completes, note the **new session ID**:

```bash
# Query latest session
python -c "
from sqlalchemy import create_engine, text
import os
os.environ['DATABASE_URL'] = 'postgresql://YOUR_USER:YOUR_PASS@localhost/ai_model_validation'

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT id, started_at, video_id
        FROM test_sessions
        ORDER BY started_at DESC
        LIMIT 1
    '''))
    row = result.fetchone()
    print(f'Latest Session ID: {row[0]}')
    print(f'Started At: {row[1]}')
    print(f'Video ID: {row[2]}')
"
```

**Save this session ID** for all subsequent queries.

---

## Step 4: Verify No Duplicate Detections

```bash
export SESSION_ID="[your_session_id_here]"

python -c "
from sqlalchemy import create_engine, text
import os
os.environ['DATABASE_URL'] = 'postgresql://YOUR_USER:YOUR_PASS@localhost/ai_model_validation'

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Count total vs unique timestamps
    result = conn.execute(text(f'''
        SELECT
            COUNT(*) as total_detections,
            COUNT(DISTINCT timestamp) as unique_timestamps,
            COUNT(*) - COUNT(DISTINCT timestamp) as duplicates
        FROM detection_events
        WHERE test_session_id = '{os.environ['SESSION_ID']}'
    '''))
    row = result.fetchone()

    print(f'Total Detections: {row[0]}')
    print(f'Unique Timestamps: {row[1]}')
    print(f'Duplicates: {row[2]}')

    if row[2] == 0:
        print('✅ PASS: No duplicates detected')
    else:
        print(f'❌ FAIL: {row[2]} duplicate detections found')

    # Show example duplicates if any
    if row[2] > 0:
        result = conn.execute(text(f'''
            SELECT timestamp, COUNT(*) as count
            FROM detection_events
            WHERE test_session_id = '{os.environ['SESSION_ID']}'
            GROUP BY timestamp
            HAVING COUNT(*) > 1
            LIMIT 5
        '''))
        print('\nExample duplicates:')
        for dup in result:
            print(f'  Timestamp {dup[0]}: {dup[1]} occurrences')
"
```

**Expected**: `Duplicates: 0` ✅

---

## Step 5: Verify Temporal Expansion

```bash
python -c "
from sqlalchemy import create_engine, text
import os
os.environ['DATABASE_URL'] = 'postgresql://YOUR_USER:YOUR_PASS@localhost/ai_model_validation'
os.environ['SESSION_ID'] = '[your_session_id]'

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Check for virtual IDs (if stored) or expansion logs
    result = conn.execute(text(f'''
        SELECT COUNT(*) as detection_count,
               MIN(timestamp) as first_detection,
               MAX(timestamp) as last_detection,
               MAX(timestamp) - MIN(timestamp) as duration_seconds
        FROM detection_events
        WHERE test_session_id = '{os.environ['SESSION_ID']}'
    '''))
    row = result.fetchone()

    print(f'Detection Count: {row[0]}')
    print(f'First Detection: {row[1]:.6f}s')
    print(f'Last Detection: {row[2]:.6f}s')
    print(f'Duration: {row[3]:.3f}s')

    # Check if expansion was used (look for logs or check matching results)
    print('\n⚠️ Temporal expansion happens in-memory during matching')
    print('Check backend logs for \"Temporal expansion complete\" messages')
"
```

**Check backend logs**:
```bash
grep "Temporal expansion complete" backend.log
# Should show: "Temporal expansion complete: N → M detections (expansion factor: 13.0×)"
```

---

## Step 6: Verify Timestamp Compensation

```bash
python -c "
from sqlalchemy import create_engine, text
import os
os.environ['DATABASE_URL'] = 'postgresql://YOUR_USER:YOUR_PASS@localhost/ai_model_validation'
os.environ['SESSION_ID'] = '[your_session_id]'

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Check if detections have compensation metadata
    result = conn.execute(text(f'''
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN video_relative_timestamp IS NOT NULL THEN 1 END) as with_relative_ts,
            AVG(video_relative_timestamp) as avg_relative_ts
        FROM detection_events
        WHERE test_session_id = '{os.environ['SESSION_ID']}'
    '''))
    row = result.fetchone()

    print(f'Total Detections: {row[0]}')
    print(f'With Relative Timestamps: {row[1]}')
    print(f'Avg Relative Timestamp: {row[2]:.3f}s')

    if row[1] == row[0]:
        print('✅ PASS: All detections have relative timestamps')
    else:
        print(f'⚠️ WARNING: {row[0] - row[1]} detections missing relative timestamps')
"
```

**Check backend logs**:
```bash
grep "Compensated.*detections" backend.log
# Should show: "Compensated N/N detections for session ... with drift=X.XXms"
```

---

## Step 7: Verify Ground Truth Matching Metrics

```bash
python -c "
from sqlalchemy import create_engine, text
import os
os.environ['DATABASE_URL'] = 'postgresql://YOUR_USER:YOUR_PASS@localhost/ai_model_validation'
os.environ['SESSION_ID'] = '[your_session_id]'

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Get matching metrics
    result = conn.execute(text(f'''
        SELECT
            accuracy_f1_score,
            accuracy_precision,
            accuracy_recall,
            detection_count,
            ground_truth_count,
            matched_detections,
            false_positives,
            false_negatives
        FROM test_sessions
        WHERE id = '{os.environ['SESSION_ID']}'
    '''))
    row = result.fetchone()

    if not row:
        print('❌ Session not found')
    else:
        f1 = row[0] or 0.0
        precision = row[1] or 0.0
        recall = row[2] or 0.0

        print(f'F1 Score: {f1:.4f} (target: ≥0.70)')
        print(f'Precision: {precision:.4f} (target: ≥0.70)')
        print(f'Recall: {recall:.4f} (target: ≥0.70)')
        print(f'\nDetection Count: {row[3]}')
        print(f'Ground Truth Count: {row[4]}')
        print(f'Matched (TP): {row[5]}')
        print(f'False Positives: {row[6]}')
        print(f'False Negatives: {row[7]}')

        # Validation
        passed = True
        if f1 < 0.70:
            print(f'❌ FAIL: F1 Score {f1:.4f} < 0.70')
            passed = False
        if precision < 0.70:
            print(f'❌ FAIL: Precision {precision:.4f} < 0.70')
            passed = False
        if recall < 0.70:
            print(f'❌ FAIL: Recall {recall:.4f} < 0.70')
            passed = False

        if passed:
            print('\n✅ PASS: All metrics meet target thresholds')
        else:
            print('\n❌ FAIL: Some metrics below target')
"
```

**Expected**: All metrics ≥ 0.70 ✅

---

## Step 8: Frontend Verification (Optional)

```bash
# Start frontend development server
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm start

# Navigate to:
# http://localhost:3000/results/[your_session_id]
```

**Verify**:
- [ ] F1 score displayed correctly
- [ ] Precision displayed correctly
- [ ] Recall displayed correctly
- [ ] Timeline shows no duplicate detections
- [ ] Matched detections count is reasonable

---

## Step 9: Generate Verification Report

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

python -c "
import json
from datetime import datetime
from sqlalchemy import create_engine, text
import os

os.environ['DATABASE_URL'] = 'postgresql://YOUR_USER:YOUR_PASS@localhost/ai_model_validation'
os.environ['SESSION_ID'] = '[your_session_id]'

engine = create_engine(os.environ['DATABASE_URL'])

report = {
    'verification_date': datetime.utcnow().isoformat(),
    'session_id': os.environ['SESSION_ID'],
    'status': 'PENDING',
    'checks': {}
}

with engine.connect() as conn:
    # Check duplicates
    result = conn.execute(text(f'''
        SELECT COUNT(*) - COUNT(DISTINCT timestamp) as duplicates
        FROM detection_events
        WHERE test_session_id = '{os.environ['SESSION_ID']}'
    '''))
    duplicates = result.fetchone()[0]
    report['checks']['no_duplicates'] = {
        'status': 'PASS' if duplicates == 0 else 'FAIL',
        'duplicates_found': duplicates
    }

    # Check metrics
    result = conn.execute(text(f'''
        SELECT accuracy_f1_score, accuracy_precision, accuracy_recall
        FROM test_sessions
        WHERE id = '{os.environ['SESSION_ID']}'
    '''))
    row = result.fetchone()
    f1, prec, rec = row[0] or 0, row[1] or 0, row[2] or 0

    report['checks']['metrics'] = {
        'f1_score': {'value': f1, 'status': 'PASS' if f1 >= 0.70 else 'FAIL'},
        'precision': {'value': prec, 'status': 'PASS' if prec >= 0.70 else 'FAIL'},
        'recall': {'value': rec, 'status': 'PASS' if rec >= 0.70 else 'FAIL'}
    }

# Determine overall status
all_passed = (
    report['checks']['no_duplicates']['status'] == 'PASS' and
    report['checks']['metrics']['f1_score']['status'] == 'PASS' and
    report['checks']['metrics']['precision']['status'] == 'PASS' and
    report['checks']['metrics']['recall']['status'] == 'PASS'
)

report['status'] = 'PASS' if all_passed else 'FAIL'
report['production_ready'] = all_passed

# Save report
with open('docs/HIL_RETEST_REPORT.json', 'w') as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
print(f'\n✅ Report saved to docs/HIL_RETEST_REPORT.json')
"
```

---

## Success Criteria Checklist

- [ ] **No Duplicate Detections** (database query shows 0 duplicates)
- [ ] **F1 Score ≥ 0.70** (test_sessions.accuracy_f1_score)
- [ ] **Precision ≥ 0.70** (test_sessions.accuracy_precision)
- [ ] **Recall ≥ 0.70** (test_sessions.accuracy_recall)
- [ ] **Temporal Expansion Visible** (logs show expansion factor ~13x)
- [ ] **Timestamp Compensation Applied** (logs show compensation messages)
- [ ] **No Backend Errors** (no exceptions in logs)
- [ ] **Frontend Displays Correctly** (optional, but recommended)

---

## Troubleshooting

### Issue: Still seeing duplicate detections

**Check**:
1. Verify WebSocket fix applied: `grep "room='detections'" socketio_server.py` should return nothing
2. Clear browser cache and reconnect
3. Check if client subscribes to multiple rooms

### Issue: F1/Precision/Recall still low

**Check**:
1. Temporal expansion logs: `grep "Temporal expansion complete" backend.log`
2. Verify expansion factor is ~13x (500ms / 40ms)
3. Check ground truth data quality
4. Verify timestamp compensation applied

### Issue: Negative relative timestamps

**Check**:
1. Video lifecycle timing implementation
2. Verify T1 (video start) captured correctly
3. Check LabJack monitoring starts AFTER video starts

### Issue: Database connection errors

**Fix credentials**:
```bash
export DATABASE_URL="postgresql://correct_user:correct_pass@localhost:5432/ai_model_validation"
```

---

## Expected Timeline

- **Step 1-2**: 5 minutes (start servers)
- **Step 2**: 10-20 minutes (run HIL test)
- **Step 3-7**: 10 minutes (verification queries)
- **Step 8**: 5 minutes (frontend check, optional)
- **Step 9**: 5 minutes (generate report)

**Total**: ~35-45 minutes

---

## Next Steps After Successful Retest

1. **Archive Results**:
   ```bash
   cp docs/HIL_RETEST_REPORT.json docs/HIL_RETEST_REPORT_$(date +%Y%m%d_%H%M%S).json
   ```

2. **Update Production Docs**:
   - Mark fixes as validated
   - Update deployment status
   - Archive coordination documents

3. **Deploy to Production** (if all checks pass):
   - Tag release version
   - Deploy backend updates
   - Monitor production metrics

4. **Long-term Monitoring**:
   - Set up alerts for duplicate detections
   - Monitor F1/Precision/Recall trends
   - Track timestamp compensation accuracy

---

**Last Updated**: 2025-11-20
**Document Version**: 1.0
**Maintainer**: QA Validation Team
