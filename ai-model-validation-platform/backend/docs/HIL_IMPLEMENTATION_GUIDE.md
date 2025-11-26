# HIL System Implementation Guide - Practical Steps

**Goal**: Fix 0 detection issue and optimize HIL testing system

**Root Cause**: HIL Monitor + Detection Service = device conflict

**Solution**: Use dedicated_labjack_monitor.py properly

---

## Step 1: Verify Current Architecture (5 minutes)

### Check What's Running

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Check for running processes
ps aux | grep -E "(hil_video|labjack|dedicated)"

# Check API endpoints
grep -r "hil.*monitor" routers/
grep -r "dedicated.*monitor" routers/

# Check which services are imported
grep -r "from.*hil_video_frame_monitor" .
grep -r "from.*dedicated_labjack_monitor" .
```

### Expected Findings

✅ **Good**: `dedicated_labjack_monitor.py` imported and used
❌ **Bad**: `hil_video_frame_monitor.py` used directly for hardware
⚠️ **Warning**: Both services trying to access LabJack

---

## Step 2: Verify Connection Manager Exists (5 minutes)

```bash
# Check if connection manager is present
ls -la services/labjack_connection_manager.py

# Check if it's being used
grep -n "get_connection_manager" services/labjack_detection_service.py
```

### If Missing

Create `/backend/services/labjack_connection_manager.py`:

```python
"""
LabJack Connection Manager - Shared Hardware Access
Prevents "device in use" errors when multiple services need LabJack
"""
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LabJackConnectionManager:
    """Singleton connection manager for LabJack hardware"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        with self._lock:
            self.handle = None
            self.device_info = None
            self.is_connected = False
            self.active_sessions = set()
            self._initialized = True

        logger.info("✅ LabJack Connection Manager initialized")

    def acquire_connection(self, session_id: str) -> Optional[int]:
        """
        Acquire shared connection for a session
        Returns LabJack handle or None
        """
        with self._lock:
            if not self.is_connected:
                # Initialize connection
                try:
                    from services.labjack_service import get_labjack_service
                    service = get_labjack_service()
                    self.handle = service.handle
                    self.device_info = service.device_info
                    self.is_connected = True
                except Exception as e:
                    logger.error(f"Failed to initialize LabJack: {e}")
                    return None

            self.active_sessions.add(session_id)
            logger.info(f"✅ Session {session_id} acquired LabJack connection")
            logger.info(f"   Active sessions: {len(self.active_sessions)}")

            return self.handle

    def release_connection(self, session_id: str):
        """Release connection for a session (but keep hardware connected)"""
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
                logger.info(f"✅ Session {session_id} released LabJack connection")
                logger.info(f"   Active sessions: {len(self.active_sessions)}")

                # Only disconnect if no active sessions
                if len(self.active_sessions) == 0:
                    logger.info("ℹ️ No active sessions, but keeping connection alive")

    def get_status(self) -> dict:
        """Get connection manager status"""
        with self._lock:
            return {
                'is_connected': self.is_connected,
                'active_sessions': len(self.active_sessions),
                'device_info': self.device_info
            }

# Global instance
_connection_manager = None

def get_connection_manager() -> LabJackConnectionManager:
    """Get or create global connection manager"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = LabJackConnectionManager()
    return _connection_manager
```

---

## Step 3: Update Detection Service to Use Connection Manager (10 minutes)

### Edit `/backend/services/labjack_detection_service.py`

Find line ~182-189 and verify this code exists:

```python
# Use shared LabJack connection manager to prevent device conflicts
try:
    from services.labjack_connection_manager import get_connection_manager
    self.connection_manager = get_connection_manager()
    logger.info("✅ Using shared LabJack connection manager")
except ImportError:
    self.connection_manager = None
    logger.warning("⚠️ LabJack connection manager not available - may have device conflicts")
```

If missing, add it to the `__init__` method.

### Verify Connection Acquisition

Find the `start_monitoring` method (~line 335) and ensure it acquires connection:

```python
def start_monitoring(self, session_id: str, ...):
    # Acquire shared connection
    if self.connection_manager:
        handle = self.connection_manager.acquire_connection(session_id)
        if not handle:
            logger.error(f"❌ Failed to acquire LabJack connection for {session_id}")
            return False
        logger.info(f"✅ Using shared LabJack handle for {session_id}")

    # Rest of start_monitoring logic...
```

### Verify Connection Release

Find `stop_session_monitoring` (~line 445) and ensure it releases:

```python
def stop_session_monitoring(self, session_id: str) -> bool:
    # ... existing cleanup code ...

    # Release shared connection (but keep hardware alive)
    if self.connection_manager:
        self.connection_manager.release_connection(session_id)

    return True
```

---

## Step 4: Stop Direct HIL Monitor Usage (15 minutes)

### Find All Direct Hardware Access

```bash
# Find where HIL Monitor is used for hardware
grep -rn "HILVideoFrameMonitor" routers/
grep -rn "hil_video_frame_monitor" api/
grep -rn "start_hil_monitoring" routers/
```

### Replace Pattern

**❌ OLD (causes conflicts)**:
```python
from src.hil_video_frame_monitor import get_hil_video_monitor

@router.post("/api/hil/start")
async def start_hil_test(request: HILTestRequest):
    monitor = await get_hil_video_monitor()
    await monitor.start_hil_monitoring(
        session_id=request.session_id,
        video_path=request.video_path
    )
```

**✅ NEW (uses orchestration)**:
```python
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor

@router.post("/api/hil/start")
async def start_hil_test(request: HILTestRequest):
    monitor = DedicatedLabJackMonitor()
    await monitor.start_monitoring_with_video_sync(
        session_id=request.session_id,
        video_timing_config={
            'video_id': request.video_id,
            'fps': request.fps,
            'duration': request.duration,
            'channels': ['AIN0'],
            'voltage_threshold': 3.3,
            'sample_rate': 1000,
            'use_stream_mode': True  # ← CRITICAL for ±1-2ms accuracy
        }
    )
```

---

## Step 5: Add Frame Seeking Utility (20 minutes)

### Create `/backend/utils/video_frame_utils.py`

```python
"""
Video Frame Utilities - Extracted from HIL Monitor
Provides frame seeking and analysis without hardware access
"""
import cv2
import numpy as np
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoFrameUtils:
    """Utility functions for video frame operations"""

    @staticmethod
    def seek_to_frame(video_path: str, frame_number: int) -> Optional[np.ndarray]:
        """
        Seek to specific frame and return frame image

        Args:
            video_path: Path to video file
            frame_number: Frame number to seek to

        Returns:
            Frame as numpy array or None if failed
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return None

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_number < 0 or frame_number >= total_frames:
                logger.error(f"Frame {frame_number} out of range (0-{total_frames-1})")
                cap.release()
                return None

            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                logger.error(f"Failed to read frame {frame_number}")
                return None

            return frame

        except Exception as e:
            logger.error(f"Error seeking to frame: {e}")
            return None

    @staticmethod
    def get_video_info(video_path: str) -> dict:
        """Get video metadata"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {'error': 'Failed to open video'}

            info = {
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
            }
            cap.release()

            return info

        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def frame_at_timestamp(video_path: str, timestamp: float, fps: float) -> Optional[np.ndarray]:
        """
        Get frame at specific timestamp

        Args:
            video_path: Path to video
            timestamp: Time in seconds from video start
            fps: Video frame rate

        Returns:
            Frame image or None
        """
        frame_number = int(timestamp * fps)
        return VideoFrameUtils.seek_to_frame(video_path, frame_number)

# Global instance
_frame_utils = VideoFrameUtils()

def get_frame_utils() -> VideoFrameUtils:
    """Get frame utilities instance"""
    return _frame_utils
```

---

## Step 6: Add Frame Seeking API (15 minutes)

### Add to `/backend/routers/hil_testing.py`

```python
from utils.video_frame_utils import get_frame_utils
from services.video_id_resolver import get_video_path
import base64

@router.get("/api/hil/{session_id}/frame/{frame_number}")
async def get_detection_frame(
    session_id: str,
    frame_number: int,
    db: Session = Depends(get_db)
):
    """
    Get video frame at specific frame number

    Returns frame as base64-encoded JPEG for easy display
    """
    try:
        # Get session video path
        session = db.query(TestSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        video_path = get_video_path(session.video_id)
        if not video_path:
            raise HTTPException(status_code=404, detail="Video not found")

        # Seek to frame
        frame_utils = get_frame_utils()
        frame = frame_utils.seek_to_frame(video_path, frame_number)

        if frame is None:
            raise HTTPException(status_code=404, detail="Frame not found")

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')

        return {
            'session_id': session_id,
            'frame_number': frame_number,
            'frame_data': frame_base64,
            'content_type': 'image/jpeg'
        }

    except Exception as e:
        logger.error(f"Error getting frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/hil/{session_id}/detection/{detection_id}/frame")
async def get_detection_event_frame(
    session_id: str,
    detection_id: str,
    db: Session = Depends(get_db)
):
    """Get frame where specific detection occurred"""
    try:
        # Get detection event
        detection = db.query(DetectionEvent).filter_by(
            id=detection_id,
            test_session_id=session_id
        ).first()

        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")

        # Get frame at detection
        video_path = get_video_path(detection.video_id)
        frame_number = detection.video_frame_number

        frame_utils = get_frame_utils()
        frame = frame_utils.seek_to_frame(video_path, frame_number)

        if frame is None:
            raise HTTPException(status_code=404, detail="Frame not found")

        # Encode
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')

        return {
            'session_id': session_id,
            'detection_id': detection_id,
            'frame_number': frame_number,
            'timestamp': detection.video_relative_timestamp,
            'frame_data': frame_base64,
            'detection_info': {
                'voltage': detection.labjack_voltage,
                'channel': detection.detection_channel,
                'latency_ms': detection.actual_latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Error getting detection frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Step 7: Update Configuration (5 minutes)

### Create `/backend/config/hil_config.json`

```json
{
  "detection": {
    "sample_rate": 1000,
    "use_stream_mode": true,
    "voltage_threshold": 3.3,
    "debounce_ms": 100,
    "channels": ["AIN0"],
    "batch_commit_size": 100,
    "batch_commit_interval_s": 1.0,
    "use_connection_manager": true
  },
  "video": {
    "enable_frame_sync": true,
    "enable_ml_detection": false,
    "capture_screenshots": true,
    "fps_target": 24.0,
    "grace_period_ms": 2000
  },
  "ground_truth": {
    "enable_matching": true,
    "tolerance_ms": 100,
    "screenshot_zoom_factor": 2.0
  },
  "system": {
    "max_concurrent_sessions": 5,
    "enable_orphan_recovery": true,
    "log_level": "INFO"
  }
}
```

### Load Config in Services

Add to `/backend/services/dedicated_labjack_monitor.py`:

```python
import json
from pathlib import Path

def load_hil_config() -> dict:
    """Load HIL configuration"""
    config_path = Path(__file__).parent.parent / 'config' / 'hil_config.json'
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config, using defaults: {e}")
        return {
            'detection': {'use_stream_mode': True, 'sample_rate': 1000},
            'video': {'enable_frame_sync': True},
            'ground_truth': {'enable_matching': True}
        }

# In __init__:
self.config = load_hil_config()
```

---

## Step 8: Testing (30 minutes)

### Test 1: Connection Manager

```python
# Create test file: tests/test_connection_manager.py
from services.labjack_connection_manager import get_connection_manager

def test_connection_manager_singleton():
    """Test connection manager is singleton"""
    manager1 = get_connection_manager()
    manager2 = get_connection_manager()
    assert manager1 is manager2

def test_multi_session_acquisition():
    """Test multiple sessions can share connection"""
    manager = get_connection_manager()

    session1_handle = manager.acquire_connection("session_1")
    session2_handle = manager.acquire_connection("session_2")

    assert session1_handle is not None
    assert session2_handle is not None
    assert session1_handle == session2_handle  # Same hardware handle

    status = manager.get_status()
    assert status['active_sessions'] == 2

    manager.release_connection("session_1")
    status = manager.get_status()
    assert status['active_sessions'] == 1

    manager.release_connection("session_2")
    status = manager.get_status()
    assert status['active_sessions'] == 0
```

### Test 2: No Device Conflicts

```python
# Test concurrent access
import asyncio
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor

async def test_concurrent_sessions():
    """Test multiple sessions don't conflict"""
    monitor1 = DedicatedLabJackMonitor()
    monitor2 = DedicatedLabJackMonitor()

    # Start two sessions simultaneously
    config = {
        'video_id': 'test_video',
        'fps': 24,
        'sample_rate': 1000,
        'use_stream_mode': True
    }

    success1 = await monitor1.start_monitoring_with_video_sync('session_1', config)
    success2 = await monitor2.start_monitoring_with_video_sync('session_2', config)

    assert success1, "Session 1 should start successfully"
    assert success2, "Session 2 should start successfully"

    # Both should have detections
    await asyncio.sleep(5)  # Wait for some detections

    detections1 = monitor1.get_detection_events('session_1')
    detections2 = monitor2.get_detection_events('session_2')

    assert len(detections1) > 0, "Session 1 should have detections"
    assert len(detections2) > 0, "Session 2 should have detections"

    # Cleanup
    await monitor1.stop_session_monitoring('session_1')
    await monitor2.stop_session_monitoring('session_2')
```

### Test 3: Frame Seeking

```python
from utils.video_frame_utils import get_frame_utils

def test_frame_seeking():
    """Test frame seeking utility"""
    frame_utils = get_frame_utils()

    # Get video info
    info = frame_utils.get_video_info('/path/to/test/video.mp4')
    assert 'fps' in info
    assert info['total_frames'] > 0

    # Seek to specific frame
    frame = frame_utils.seek_to_frame('/path/to/test/video.mp4', frame_number=100)
    assert frame is not None
    assert frame.shape[2] == 3  # RGB image

    # Seek by timestamp
    frame_at_2s = frame_utils.frame_at_timestamp('/path/to/test/video.mp4', 2.0, info['fps'])
    assert frame_at_2s is not None
```

### Test 4: Timing Accuracy

```bash
# Run dedicated monitor with logging
python -c "
import asyncio
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor

async def test():
    monitor = DedicatedLabJackMonitor()
    await monitor.start_monitoring_with_video_sync(
        'test_session',
        {
            'video_id': 'test',
            'fps': 24,
            'sample_rate': 1000,
            'use_stream_mode': True
        }
    )

    # Wait for detections
    await asyncio.sleep(30)

    # Check timing accuracy
    detections = monitor.get_detection_events('test_session')
    for det in detections:
        print(f'Detection: voltage={det.voltage}, latency={det.actual_latency_ms}ms, quality={det.timing_sync_quality}')

    await monitor.stop_session_monitoring('test_session')

asyncio.run(test())
"
```

**Expected Results**:
- Latency should be 1-2ms (not 10-100ms)
- Timing quality should be "synchronized"
- No "device in use" errors
- Multiple sessions work simultaneously

---

## Step 9: Deployment (10 minutes)

### Update Requirements

```bash
# Ensure opencv-python is installed
pip install opencv-python

# Verify all dependencies
pip install -r requirements.txt
```

### Restart Services

```bash
# Stop any running backends
pkill -f "uvicorn main:app"
pkill -f "hil_video_frame_monitor"

# Start with new configuration
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Verify Startup

```bash
# Check logs for connection manager
tail -f backend.log | grep "connection manager"

# Expected:
# ✅ Using shared LabJack connection manager
# ✅ LabJack Connection Manager initialized
```

---

## Step 10: Validation (15 minutes)

### Integration Test

```bash
# Start HIL test via API
curl -X POST http://localhost:8000/api/hil/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "validation_test",
    "video_id": "test_video_1",
    "fps": 24,
    "duration": 30
  }'

# Wait 5 seconds, then check detections
curl http://localhost:8000/api/hil/validation_test/detections

# Expected: detections > 0 (not 0!)
```

### Check Metrics

```bash
# Get session status
curl http://localhost:8000/api/hil/validation_test/status

# Check for:
# - detections_count > 0
# - average_latency_ms < 5 (should be 1-2ms)
# - timing_sync_quality: "synchronized"
```

### Test Frame Seeking

```bash
# Get frame at detection
curl http://localhost:8000/api/hil/validation_test/frame/100

# Expected: base64-encoded frame image
```

---

## Rollback Plan

If issues occur:

### Quick Rollback

```bash
# Restore old code
git stash
# or
git checkout HEAD~1

# Restart services
uvicorn main:app --reload
```

### Partial Rollback

Keep connection manager, revert API changes:

```python
# Just ensure connection manager is used
# Don't need new endpoints immediately
```

---

## Monitoring After Deployment

### Key Metrics to Watch

```bash
# Detection count (should be > 0)
watch -n 5 'curl -s http://localhost:8000/api/hil/active-sessions | jq ".[] | {session_id, detections_count}"'

# Connection manager status
curl http://localhost:8000/api/system/connection-manager

# Expected:
# {
#   "is_connected": true,
#   "active_sessions": 2,
#   "device_info": {...}
# }
```

### Log Monitoring

```bash
# Watch for errors
tail -f backend.log | grep -E "(ERROR|device in use|conflict)"

# Should see:
# - No "device in use" errors
# - No "conflict" errors
# - "✅ Using shared LabJack connection manager"
```

---

## Success Criteria

After implementation, you should have:

1. ✅ **0 Detection Issue Fixed**: Multiple services work simultaneously
2. ✅ **Timing Accuracy**: ±1-2ms (not ±10-100ms)
3. ✅ **Frame Seeking**: Can retrieve frames at detection times
4. ✅ **Multi-Session**: Multiple tests run concurrently
5. ✅ **No Conflicts**: Connection manager prevents device conflicts
6. ✅ **Clean Architecture**: Dedicated monitor orchestrates everything

---

## Troubleshooting

### Issue: Still Getting 0 Detections

**Check**:
```bash
# Is connection manager being used?
grep "Using shared LabJack connection manager" backend.log

# Are both services running?
ps aux | grep -E "(dedicated|labjack_detection)"

# Is LabJack hardware connected?
python -c "from services.labjack_service import get_labjack_service; print(get_labjack_service().status())"
```

### Issue: "Device in Use" Error

**Fix**:
```python
# Ensure connection manager is imported and used
from services.labjack_connection_manager import get_connection_manager
manager = get_connection_manager()
handle = manager.acquire_connection(session_id)
```

### Issue: High Latency (> 5ms)

**Check**:
```python
# Is stream mode enabled?
config = {'use_stream_mode': True, 'sample_rate': 1000}

# Is polling mode accidentally active?
grep "use_stream_mode.*False" services/
```

---

## Next Steps

After successful implementation:

1. Add T3 YOLO integration (optional ML detection comparison)
2. Add frame processing statistics dashboard
3. Optimize batch commit thresholds for high-frequency tests
4. Add unit tests for all new utilities
5. Update user documentation

---

**Document**: Implementation Guide
**Status**: Ready for Implementation
**Estimated Time**: 2-3 hours total
**Risk**: Low (following proven patterns)
**Expected Outcome**: 100% detection rate with ±1-2ms accuracy
