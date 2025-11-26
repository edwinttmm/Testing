# HIL Timing Fix - Quick Reference Card

## 🔴 Problem

**LabJack LED turns ON before video plays, turns OFF before video ends**

Result: Negative latencies (-6ms), invalid timing, broken HIL validation

---

## ✅ Solution

**Wait for video to actually start before beginning LabJack monitoring**

---

## 🚀 Quick Implementation (TL;DR)

### 1. Create Video Lifecycle Handler (NEW FILE)

```python
# File: routers/video_lifecycle_api.py

@router.post("/{session_id}/started")
async def handle_video_started(session_id: str, event: VideoStartedEvent, db: Session):
    # 1. Capture T1 (video start time)
    session.video_playback_start_time = event.timestamp

    # 2. NOW start monitoring (synchronized!)
    await start_hil_monitoring(session_id, hil_config)

    return {"success": True, "monitoring_started": True}
```

### 2. Modify Test Session Start

```python
# File: routers/test_sessions.py, line 1089-1144

# BEFORE (WRONG):
session.video_playback_start_time = session.started_at.timestamp()
await start_hil_monitoring(session_id, config)  # TOO EARLY!

# AFTER (CORRECT):
# DON'T set video_playback_start_time here - wait for video!
session.configuration['hil_config'] = config  # Store for later
# Monitoring will start when video_started event arrives
```

### 3. Update Detection Timestamp Calculation

```python
# File: services/dedicated_labjack_monitor.py

def _handle_detection_with_video_sync(session_id, event):
    video_start_time = session_data['video_start_time']  # T1 from video
    relative_timestamp = event.timestamp - video_start_time  # Correct!
    event.video_relative_timestamp = relative_timestamp  # Always positive!
```

### 4. Frontend: Emit Video Events

```javascript
// File: VideoPlayer.tsx

video.addEventListener('playing', async () => {
  await fetch(`/api/video-lifecycle/${sessionId}/started`, {
    method: 'POST',
    body: JSON.stringify({ timestamp: Date.now() / 1000 })
  });
});
```

---

## 📊 Timeline Comparison

### Before (BROKEN)

```
T=10ms    : POST /start
T=25ms    : LabJack LED ON ← TOO EARLY!
T=200ms   : Video starts playing
T=500ms   : Video ends
T=550ms   : LabJack LED OFF ← TOO LATE!
Result    : Latencies = -6ms (WRONG!)
```

### After (FIXED)

```
T=10ms    : POST /start
T=200ms   : Video starts playing
T=210ms   : video_started event → LabJack LED ON ← CORRECT!
T=500ms   : Video ends
T=510ms   : video_ended event → LabJack LED OFF ← CORRECT!
Result    : Latencies = +35ms (CORRECT!)
```

---

## 🧪 Quick Test

```bash
# 1. Start session (monitoring should NOT start yet)
curl -X POST http://localhost:8000/api/test-sessions/{id}/start
# Check: LED should be OFF

# 2. Trigger video_started event (NOW monitoring starts)
curl -X POST http://localhost:8000/api/video-lifecycle/{id}/started \
  -d '{"timestamp": 1700000000.5, "video_id": "test"}'
# Check: LED should turn ON now

# 3. Verify no negative latencies
curl http://localhost:8000/api/test-sessions/{id}/events
# Check: All video_relative_timestamp >= 0
```

---

## 📁 Files to Change

| Priority | File | Action |
|----------|------|--------|
| ⭐⭐⭐ | `routers/video_lifecycle_api.py` | CREATE new file |
| ⭐⭐⭐ | `routers/test_sessions.py` | MODIFY lines 1089-1187 |
| ⭐⭐ | `services/dedicated_labjack_monitor.py` | MODIFY timestamp baseline |
| ⭐⭐ | Frontend video player | ADD event emission |
| ⭐ | `main.py` | REGISTER new router |

---

## ⚠️ Common Pitfalls

### ❌ DON'T

```python
# DON'T set video_playback_start_time at session start
session.video_playback_start_time = session.started_at.timestamp()

# DON'T start monitoring immediately
await start_hil_monitoring(session_id, config)
```

### ✅ DO

```python
# DO wait for video_started event
session.configuration['hil_config'] = config  # Store for later

# DO start monitoring in video lifecycle handler
# (see routers/video_lifecycle_api.py)
```

---

## 🎯 Success Checklist

- [ ] LabJack LED turns ON **after** video starts
- [ ] LabJack LED turns OFF **after** video ends
- [ ] No negative latencies in detection events
- [ ] `video_playback_start_time` matches video start, not session start
- [ ] T1-T0 delay is 200-500ms (video initialization time)

---

## 📚 Full Documentation

- **Root Cause Analysis**: `/docs/hil_timing_synchronization_analysis.md`
- **Implementation Guide**: `/docs/hil_timing_fix_implementation.md`
- **Executive Summary**: `/docs/SUMMARY_HIL_TIMING_ANALYSIS.md`

---

## 🆘 Need Help?

1. Read sequence diagrams in root cause analysis
2. Follow step-by-step implementation guide
3. Test with provided test cases
4. Check LED timing with hardware validation

---

**Estimated Implementation Time**: 1-3 days
**Risk Level**: Low (backward compatible)
**Testing Required**: Unit + Integration + Hardware

**Status**: Ready for Implementation ✅
