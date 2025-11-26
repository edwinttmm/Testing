# Instrumented Test Script - Debug Documentation

## Overview
This script captures **ACTUAL runtime data** to prove root causes of the recall calculation bug.

## What It Captures

### 1. Method Execution Data
- Return value of `_get_actual_ground_truth_count()`
- Exception traces if method fails
- Method type and signature verification

### 2. Database Verification
- Direct GT count from database query
- Actual GT records with MAC addresses and channels
- Session TP/FP/FN/TN values from database

### 3. Mismatch Detection
- Compares method return vs direct query
- Identifies discrepancies immediately
- Logs exact values for debugging

### 4. Calculation Verification
- Expected recall: TP / actual_GT_count
- Formula recall: TP / (TP + FN)
- Precision: TP / (TP + FP)
- Shows which formula is being used incorrectly

## How to Run

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 scripts/instrumented_test.py
```

## Output Locations

1. **Console**: Real-time debug output
2. **Log File**: `/tmp/instrumented_test.log` (detailed trace)

## Expected Results

### Success Indicators
✅ Method returns GT count matching database
✅ TP/FN values are correct
✅ Recall calculation uses correct formula

### Failure Indicators
❌ Method returns None or wrong count
❌ Mismatch between method and database
❌ TP + FN ≠ actual GT count
❌ Recall uses wrong denominator

## Interpreting Results

### Scenario 1: Method Returns Wrong Count
```
[TRACE] Original method returned: 10
[TRACE] Direct GT query returned: 15
[MISMATCH] Method:10 != Query:15
```
**Diagnosis**: `_get_actual_ground_truth_count()` is broken

### Scenario 2: TP + FN ≠ GT Count
```
[SESSION] TP: 12
[SESSION] FN: 2
[TRACE] Direct GT query returned: 20
[CALC] Expected recall: 12/20 = 0.6000
[CALC] Formula recall: 12/(12+2) = 0.8571
```
**Diagnosis**: FN is not being updated correctly

### Scenario 3: Method Returns None
```
[TRACE] Original method raised exception: NoneType
```
**Diagnosis**: Method implementation is completely broken

## What Happens Next

Based on results:

1. **If method is broken** → Fix `_get_actual_ground_truth_count()`
2. **If FN tracking is broken** → Fix false negative updates
3. **If formula is wrong** → Change to use actual GT count
4. **If all correct** → Bug is elsewhere (likely precision)

## Verification Checklist

After running the test:

- [ ] Check `/tmp/instrumented_test.log` for full trace
- [ ] Verify GT count matches database
- [ ] Verify TP + FN matches GT count
- [ ] Verify recall calculation is correct
- [ ] Document actual root cause found

## Example Output

```
[TRACE] _get_actual_ground_truth_count called for session: 2c9a93f6-...
[TRACE] Original method returned: 15
[TRACE] Direct GT query returned: 15
[TRACE] Session TP: 12
[TRACE] Session FN: 3
[CALC] Expected recall: 12/15 = 0.8000
[CALC] Formula recall: 12/(12+3) = 0.8000
✅ All values match - recall is correct
```

## Troubleshooting

### Script Won't Run
```bash
# Check Python path
which python3

# Check dependencies
cd /home/rigade/Testing/ai-model-validation-platform/backend
pip list | grep -i sqlalchemy
```

### Session Not Found
```bash
# List all sessions
sqlite3 test_database.db "SELECT id, name FROM test_sessions;"

# Update test_session_id in script
```

### Database Locked
```bash
# Check for other processes
lsof | grep test_database.db

# Kill if necessary
```

## Next Steps

1. Run the instrumented test
2. Analyze the log file
3. Identify the EXACT root cause
4. Create targeted fix based on evidence
5. Re-run test to verify fix

---

**Remember**: This test provides EVIDENCE, not hypotheses. Use the actual values to drive the fix.
