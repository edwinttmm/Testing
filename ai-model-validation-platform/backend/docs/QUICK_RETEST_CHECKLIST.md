# HIL Test Quick Retest Checklist
## 5-Minute Verification Guide

**Session ID**: _______________ (fill in after test)

---

## Pre-Test (2 minutes)

- [ ] Backend running on port 8000
- [ ] Database credentials correct
- [ ] Logs monitoring active

```bash
source venv/bin/activate
python -m uvicorn main:app --reload --port 8000 &
tail -f backend.log | grep -E "(Temporal expansion|Compensated|Detection synchronized)"
```

---

## Run Test (10-20 minutes)

- [ ] HIL test executed
- [ ] Session ID captured: _______________
- [ ] Logs show temporal expansion (~13x factor)
- [ ] Logs show timestamp compensation

---

## Verification (3 minutes)

### 1. Check Duplicates

```bash
export SESSION_ID="your_session_id"
export DATABASE_URL="postgresql://user:pass@localhost/ai_model_validation"

python -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    r = conn.execute(text(f\"SELECT COUNT(*)-COUNT(DISTINCT timestamp) FROM detection_events WHERE test_session_id='{os.environ['SESSION_ID']}'\"))
    dups = r.fetchone()[0]
    print(f'Duplicates: {dups}')
    print('✅ PASS' if dups == 0 else '❌ FAIL')
"
```

**Result**: _____ duplicates (expect 0)

---

### 2. Check Metrics

```bash
python -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    r = conn.execute(text(f\"SELECT accuracy_f1_score, accuracy_precision, accuracy_recall FROM test_sessions WHERE id='{os.environ['SESSION_ID']}'\"))
    row = r.fetchone()
    f1, prec, rec = row[0] or 0, row[1] or 0, row[2] or 0
    print(f'F1: {f1:.4f} (target: ≥0.70) {\"✅\" if f1 >= 0.70 else \"❌\"}')
    print(f'Precision: {prec:.4f} (target: ≥0.70) {\"✅\" if prec >= 0.70 else \"❌\"}')
    print(f'Recall: {rec:.4f} (target: ≥0.70) {\"✅\" if rec >= 0.70 else \"❌\"}')
"
```

**Results**:
- F1: _____ (≥0.70) [ ]
- Precision: _____ (≥0.70) [ ]
- Recall: _____ (≥0.70) [ ]

---

## Final Decision

**ALL CHECKS PASSED?** [ ] YES / [ ] NO

**If YES**: ✅ **GO** for production deployment
**If NO**: ❌ **NO-GO** - review logs and debug

---

**Date**: ___________
**Tester**: ___________
**Confidence**: _____%
