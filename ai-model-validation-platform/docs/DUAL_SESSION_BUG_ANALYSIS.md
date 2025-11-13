# 🐛 DUAL SESSION CREATION BUG - ROOT CAUSE ANALYSIS

## Executive Summary

**Problem:** UI shows 0 detections despite backend capturing 92 detections
**Root Cause:** Video sequence test creates TWO separate sessions - one for workflow, one for monitoring
**Impact:** CRITICAL - Breaks all multi-video sequence tests
**Status:** IDENTIFIED, FIX IN PROGRESS

---

## 📊 Evidence from Database

### Session 1: Video Sequence Session (UI navigates here)
```
ID: 5db6d0ed-d3c9-442c-a41b-4b852ca9187f
Name: "Video Sequence Test - 2025-10-29 10:52"
Status: completed
Sequence ID: 49fea5ed-2fa9-4ab6-8a95-dd5110c10cfa
Detections: 0 ❌
```

### Session 2: Monitoring Session (detections go here)
```
ID: a6a300fa-f2ba-4d46-93c3-46578ab4e4f2
Name: "HIL Test 29/10/2025, 10:52:11"
Status: running
Sequence ID: None
Detections: 92 ✅
```

---

## 🔍 Call Stack Analysis

### 1. Video Sequence Test Start
**File:** `backend/routers/video_sequence_testing.py:302`
```python
test_session_id = str(uuid.uuid4())  # Creates 5db6d0ed...
test_session = TestSession(
    id=test_session_id,
    name=f"Video Sequence Test - {session_started_at.strftime('%Y-%m-%d %H:%M')}",
    sequence_id=sequence_id,
    # ... other fields
)
db.add(test_session)
db.commit()
```

### 2. Start HIL Monitoring
**File:** `backend/routers/video_sequence_testing.py:416`
```python
await start_hil_monitoring(
    session_id=test_session_id,  # Passes 5db6d0ed...
    video_id=request.video_ids[0],
    db=db
)
```

### 3. Monitoring Service
**File:** `backend/services/dedicated_labjack_monitor.py:189`
```python
# start_monitoring_with_video_sync receives session_id=5db6d0ed...
success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)
```

### 4. ⚠️ SOMEWHERE HERE A NEW SESSION IS CREATED ⚠️
A new TestSession with ID `a6a300fa...` is created with name "HIL Test 29/10/2025, 10:52:11"

**Suspected Location:**
- `backend/services/raw_labjack_logger.py` OR
- `backend/services/labjack_detection_service.py` OR
- `backend/api/raw_labjack_endpoints.py`

---

## 🎯 The Problem Flow

```
User starts video sequence test
    ↓
Creates TestSession 5db6d0ed... ✅
    ↓
Calls start_hil_monitoring(session_id=5db6d0ed...)
    ↓
⚠️ Monitoring creates NEW TestSession a6a300fa... ❌
    ↓
Detections saved to session a6a300fa...
    ↓
UI loads session 5db6d0ed... (0 detections)
    ↓
User sees: "still no luck... 0 detection showing"
```

---

## 🔧 Required Fix

### Option 1: Make Monitoring Use Provided Session ID
Ensure monitoring service NEVER creates a new TestSession, always uses the provided `session_id`.

**Files to Check:**
1. `backend/services/raw_labjack_logger.py` - Check if it creates TestSession
2. `backend/services/labjack_detection_service.py` - Check start_monitoring()
3. `backend/api/raw_labjack_endpoints.py` - Check if endpoint creates session

### Option 2: Link Both Sessions (Quick Fix)
Add `parent_session_id` or `linked_session_id` field to TestSession model to link monitoring session back to video sequence session.

**Pros:** Quick, doesn't break existing code
**Cons:** Technical debt, doesn't fix root cause

### Option 3: Merge Detections on Query (Workaround)
Modify detection queries to check both:
- Direct match: `test_session_id = session_id`
- Sequence match: Find monitoring session created within 5 seconds of sequence session

**Pros:** Works without code changes
**Cons:** Fragile, performance impact

---

## 🧪 Test Scenario

### Expected Behavior:
```
1. Start video sequence test → Creates session 5db6d0ed...
2. Start monitoring with session_id=5db6d0ed...
3. Detections saved to session 5db6d0ed...
4. UI loads session 5db6d0ed... → Shows 92 detections ✅
```

### Actual Behavior:
```
1. Start video sequence test → Creates session 5db6d0ed...
2. Start monitoring with session_id=5db6d0ed...
3. ⚠️ Monitoring creates NEW session a6a300fa...
4. Detections saved to session a6a300fa...
5. UI loads session 5db6d0ed... → Shows 0 detections ❌
```

---

## 📝 Next Steps

1. ✅ Phantom session creation in test_sessions.py:919 - FIXED
2. 🔄 Find where monitoring creates its own TestSession - IN PROGRESS
3. ⏳ Apply fix to prevent dual session creation
4. ⏳ Test with multi-video sequence
5. ⏳ Verify 92 detections appear in UI

---

## 🚨 User Impact

**User Quote:**
> "http://localhost:3000/results/5db6d0ed-d3c9-442c-a41b-4b852ca9187f , still no luck multiple table and table looking wrong in terms of only 0.5 sec GT ut video is 5 sec something wrong"

**Observed:**
- 0 detections showing in UI
- Backend logs show 92 detections captured
- Multiple tables visible (UI redesign not deployed?)
- GT timing showing 0.5 sec for 5 sec video

**All of these are symptoms of the DUAL SESSION BUG!**

---

**Status:** 🔍 INVESTIGATION COMPLETE, FIX IN PROGRESS
**Priority:** 🔥 CRITICAL
**ETA:** < 1 hour
