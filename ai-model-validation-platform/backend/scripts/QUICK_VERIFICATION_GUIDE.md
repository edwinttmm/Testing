# Quick Verification Guide

## TL;DR - Run This Command

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate
./scripts/verify_all_fixes.sh
```

---

## What Does This Check?

### 1. Detection Sources ✓
- **Expected**: Only ONE source (either 'labjack' OR 'dedicated_labjack_monitor')
- **Current**: TWO sources with 167 each = 334 total (100% duplication)
- **Status**: ❌ FAILING

### 2. GT Aggregation ✓
- **Expected**: 257 total GT objects (Video 1: 131 + Video 2: 126)
- **Current**: 131 (only Video 1)
- **Status**: ❌ FAILING

### 3. Video 2 Matching ✓
- **Expected**: ≥20% coverage (25+ of 126 GT matched)
- **Current**: 0.8% coverage (1 of 126)
- **Status**: ❌ FAILING

### 4. Metrics Calculation ✓
- **Expected**: Metrics calculated from correct counts
- **Current**: Unknown until above fixes applied
- **Status**: ⏳ PENDING

---

## Expected Output When All Fixed

```
================================================================================
COMPREHENSIVE VERIFICATION SCRIPT FOR ALL FIXES
================================================================================

================================================================================
1. DETECTION SOURCE VERIFICATION
================================================================================
✅ PASS: Only ONE detection source is active

================================================================================
2. GROUND TRUTH AGGREGATION VERIFICATION
================================================================================
✅ PASS: GT count is 257 (correctly aggregated across all videos)

================================================================================
3. VIDEO 2 TIMESTAMP MATCHING VERIFICATION
================================================================================
✅ PASS: Video 2 coverage >= 20%

================================================================================
4. OVERALL METRICS CALCULATION VERIFICATION
================================================================================
✅ PASS: Metrics calculated correctly

================================================================================
VERIFICATION SUMMARY
================================================================================
1. Detection Source Check:     ✅ PASS
2. GT Aggregation Check:       ✅ PASS
3. Video 2 Matching Check:     ✅ PASS
4. Metrics Calculation Check:  ✅ PASS

================================================================================
ALL FIXES VERIFIED SUCCESSFULLY!
================================================================================
```

---

## Current Output (Before Fixes)

```
================================================================================
1. DETECTION SOURCE VERIFICATION
================================================================================
❌ FAIL: TWO sources with EQUAL counts detected
   This indicates 100% duplication of detections
   Both sources wrote 167 detections

Detection Sources in Database:
  Source: labjack
  Count: 167
  First: 1763677080.302
  Last:  1763677094.077

  Source: dedicated_labjack_monitor
  Count: 167
  First: 1763677080.302
  Last:  1763677094.077
```

---

## Manual Verification (If Script Fails)

```bash
# Check detection sources
python3 << 'EOF'
from sqlalchemy import create_engine, text
from config_settings import Settings
engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    sources = conn.execute(text("""
        SELECT source, COUNT(*) FROM detection_events
        WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
        GROUP BY source
    """)).fetchall()
    print("Sources:", sources)
    print("Expected: 1 source with count=167")
    print("Result:", "PASS" if len(sources) == 1 else "FAIL")
EOF

# Check GT aggregation
python3 << 'EOF'
from sqlalchemy import create_engine, text
from config_settings import Settings
engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    gt_count = conn.execute(text("""
        SELECT COUNT(*) FROM ground_truth_objects
        WHERE video_id IN (
            SELECT DISTINCT video_id FROM video_test_sequences
            WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
        )
    """)).scalar()
    print(f"GT Count: {gt_count}")
    print("Expected: 257")
    print("Result:", "PASS" if gt_count == 257 else "FAIL")
EOF

# Check Video 2 matching
python3 << 'EOF'
from sqlalchemy import create_engine, text
from config_settings import Settings
engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    video2_stats = conn.execute(text("""
        SELECT
            COUNT(*) as total_gt,
            SUM(CASE WHEN dc.is_match = 1 THEN 1 ELSE 0 END) as matched_gt
        FROM ground_truth_objects gt
        LEFT JOIN detection_comparisons dc ON gt.id = dc.ground_truth_id
        WHERE gt.video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
    """)).fetchone()
    total, matched = video2_stats[0], video2_stats[1] or 0
    coverage = (matched / total * 100) if total > 0 else 0
    print(f"Video 2 Coverage: {coverage:.2f}%")
    print("Expected: ≥20%")
    print("Result:", "PASS" if coverage >= 20 else "FAIL")
EOF
```

---

## Troubleshooting

### Script Permission Denied
```bash
chmod +x /home/rigade/Testing/ai-model-validation-platform/backend/scripts/verify_all_fixes.sh
```

### Virtual Environment Not Found
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database Connection Error
Check database is running:
```bash
docker ps | grep postgres
```

### Import Errors
Install dependencies:
```bash
pip install sqlalchemy psycopg2-binary
```

---

## Related Documentation

- **Verification Plan**: `/backend/docs/VERIFICATION_PLAN.md`
- **Code Review Summary**: `/backend/docs/CODE_REVIEW_SUMMARY.md`
- **Verification Script**: `/backend/scripts/verify_all_fixes.sh`

---

## Quick Decision Matrix

| Check Result | Action |
|--------------|--------|
| All PASS ✅ | Deploy to production |
| 1-2 FAIL ❌ | Review coder agent's fixes |
| 3+ FAIL ❌ | Roll back and re-implement |
| WARNINGS ⚠️ | Manual review required |

---

**Last Updated**: 2025-11-21
**Test Session**: `e8e108b0-cb20-4cba-a2db-fc29f21efd16`
