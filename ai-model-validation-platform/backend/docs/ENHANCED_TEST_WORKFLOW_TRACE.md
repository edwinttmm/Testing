# ENHANCED TEST WORKFLOW TRACE
## Complete Flow from UI "Start Test" Button to LabJack Detection

**Investigation Date:** 2025-11-24
**Purpose:** Trace where `constant_voltage_mode` can be injected into Enhanced Test workflow

---

## EXECUTIVE SUMMARY

**CRITICAL FINDING:** `constant_voltage_mode` is **MISSING** from the Enhanced Test workflow.

The parameter exists in `DetectionConfig` (line 155 of `services/labjack_detection_service.py`) with default `False`, but is **NEVER** passed through the Enhanced Test API endpoints. This means users cannot enable constant voltage mode through the UI.

**IMMEDIATE FIX LOCATION:**
- File: `/home/rigade/Testing/ai-model-validation-platform/backend/api_enhanced_test_workflow_integrated.py`
- Function: `start_detection_validation_test()` (line 71)
- Add: `constant_voltage_mode` parameter to `DetectionTestConfig` model

---

## COMPLETE WORKFLOW TRACE

### 1. FRONTEND → BACKEND ROUTE

```
UI: "Enhanced Test" page → "Start Test" button
  ↓
Frontend: POST request to /api/enhanced-test-workflow/start
  ↓
Backend Router: api_enhanced_test_workflow_integrated.py
  ↓
Handler: start_detection_validation_test() at line 71
```

**Files Involved:**
- **Router:** `/backend/api_enhanced_test_workflow_integrated.py`
- **Prefix:** `/api/enhanced-test-workflow`
- **Endpoint:** `POST /start`

---

### 2. REQUEST FLOW DETAIL

#### Step 1: Frontend API Call
```python
# Frontend calls (likely from React/TypeScript):
POST /api/enhanced-test-workflow/start
Content-Type: application/json

{
  "project_id": "abc-123",
  "detection_window_ms": 500.0,
  "voltage_threshold": 2.5,
  "sample_rate": 1000,
  "channels": ["AIN0", "AIN1"]
}
```

#### Step 2: Backend Receives Request
**File:** `api_enhanced_test_workflow_integrated.py`
**Function:** `start_detection_validation_test()` (line 71)

```python
@router.post("/start")
async def start_detection_validation_test(
    config: DetectionTestConfig,
    db: Session = Depends(get_db)
):
    """Start the Enhanced Test Workflow with LabJack detection validation"""

    # Check LabJack connection
    labjack_service = get_labjack_service()
    status = labjack_service.get_status()

    if not status.connected:
        raise HTTPException(
            status_code=400,
            detail="LabJack not connected. Please connect LabJack first."
        )
```

**Request Model:**
```python
class DetectionTestConfig(BaseModel):
    project_id: str
    detection_window_ms: float = 500.0
    voltage_threshold: float = 2.5
    sample_rate: int = 1000
    channels: List[str] = ["AIN0", "AIN1"]
    # ❌ MISSING: constant_voltage_mode parameter
```

---

### 3. LABJACK DETECTION START

#### Step 3: Configure LabJack
**File:** `api_enhanced_test_workflow_integrated.py`
**Lines:** 104-105

```python
# Configure LabJack for testing
await labjack_service.start_stream(
    config.channels,  # ["AIN0", "AIN1"]
    config.sample_rate  # 1000
)
```

#### Step 4: Workflow Monitoring Loop
**File:** `api_enhanced_test_workflow_integrated.py`
**Function:** `run_detection_validation_workflow()` (line 198)

```python
async def run_detection_validation_workflow(websocket: WebSocket):
    """Run the complete detection validation workflow"""
    labjack_service = get_labjack_service()

    for i, video in enumerate(current_test_state["videos"]):
        # Start timing for this video
        video_start_time = time.time()

        # Monitor for LabJack signal during video playback
        while (time.time() - start_monitor_time) < timeout:
            # Read voltage from LabJack
            voltage = await labjack_service.read_single_voltage("AIN0")

            if voltage > current_test_state["config"].voltage_threshold:
                # Detection found!
                # Store result...
```

**❌ PROBLEM:** This workflow uses `labjack_service.read_single_voltage()` for direct polling, which **BYPASSES** the `DetectionConfig` system entirely!

---

### 4. ALTERNATIVE DETECTION PATH (NOT USED)

The proper detection path that **WOULD** use `DetectionConfig` is:

**File:** `services/labjack_detection_service.py`
**Function:** `start_monitoring()` (line 300)

```python
def start_monitoring(
    self,
    session_id: str,
    channels: List[str] = None,
    voltage_threshold: float = 2.5,
    debounce_ms: int = None,
    sample_rate: int = 1000,
    **kwargs
) -> bool:
    """Start monitoring LabJack channels for detection events"""

    # Create DetectionConfig object
    config = DetectionConfig(
        session_id=session_id,
        channels=channels,
        voltage_threshold=voltage_threshold,
        debounce_ms=debounce_ms,
        sample_rate=sample_rate,
        enable_websocket=kwargs.get('enable_websocket', True),
        store_in_db=kwargs.get('store_in_db', True),
        metadata=metadata,
        continuous_mode=kwargs.get('continuous_mode', False),
        continuous_lower_bound=kwargs.get('continuous_lower_bound'),
        continuous_upper_bound=kwargs.get('continuous_upper_bound'),
        continuous_interval_ms=kwargs.get('continuous_interval_ms', 5),
        steady_high_logging=kwargs.get('steady_high_logging', True),
        steady_high_interval_ms=kwargs.get('steady_high_interval_ms', 5),
        use_stream_mode=kwargs.get('use_stream_mode', default_stream_mode),
        # ❌ MISSING: constant_voltage_mode parameter from kwargs
    )
```

**Lines:** 411-426 in `services/labjack_detection_service.py`

---

## CURRENT STATUS ANALYSIS

### Where `constant_voltage_mode` Exists

1. **Defined in:** `services/labjack_detection_service.py`
   - Line 155: Field definition in `DetectionConfig` dataclass
   - Default value: `False`
   - Purpose: "Bypass debounce for constant voltage testing"

2. **Used in:** Detection logic
   - Line: (search needed) - Checked in `_should_record_detection()`
   - Effect: When `True`, bypasses debounce filter for 100% detection rate

3. **Tested in:** Test files
   - `tests/test_constant_voltage_mode_fix.py`
   - `tests/test_constant_voltage_integration.py`
   - Tests verify bypass works correctly

### Where `constant_voltage_mode` is MISSING

1. **❌ Enhanced Test Request Model**
   - File: `api_enhanced_test_workflow_integrated.py`
   - Line: 23-28
   - Missing from `DetectionTestConfig` Pydantic model

2. **❌ Enhanced Test Workflow Configuration**
   - File: `api_enhanced_test_workflow_integrated.py`
   - Line: 92-102
   - Not passed to LabJack service

3. **❌ Detection Service `start_monitoring()`**
   - File: `services/labjack_detection_service.py`
   - Line: 411-426
   - Not extracted from `kwargs` when creating `DetectionConfig`

---

## RECOMMENDED FIXES

### Fix Option A: Add to Enhanced Test Workflow (RECOMMENDED)

**Why:** Provides UI-level control, user-friendly

**Implementation:**

1. **Update Request Model** (Line 23-28)
   ```python
   class DetectionTestConfig(BaseModel):
       project_id: str
       detection_window_ms: float = 500.0
       voltage_threshold: float = 2.5
       sample_rate: int = 1000
       channels: List[str] = ["AIN0", "AIN1"]
       constant_voltage_mode: bool = False  # ✅ ADD THIS
   ```

2. **Update Workflow State** (Line 92-102)
   ```python
   current_test_state.update({
       "active": True,
       "session_id": session_id,
       "config": config,  # Now includes constant_voltage_mode
       "videos": [...],
       # ...
   })
   ```

3. **Pass to Detection Service**
   - Problem: Enhanced Test workflow uses `read_single_voltage()` polling
   - Solution: Need to refactor to use proper `start_monitoring()` path

### Fix Option B: Add to Detection Service kwargs

**Why:** Backend-level control, requires API parameter passing

**Implementation:**

**File:** `services/labjack_detection_service.py`
**Line:** 426 (after existing kwargs)

```python
config = DetectionConfig(
    # ... existing parameters ...
    use_stream_mode=kwargs.get('use_stream_mode', default_stream_mode),
    constant_voltage_mode=kwargs.get('constant_voltage_mode', False),  # ✅ ADD THIS
)
```

### Fix Option C: Default to True for Testing

**Why:** Quick fix for testing, not production-ready

**File:** `services/labjack_detection_service.py`
**Line:** 155

```python
@dataclass
class DetectionConfig:
    # ... other fields ...
    constant_voltage_mode: bool = True  # Change from False to True
```

**⚠️ WARNING:** This breaks backward compatibility, affects all detection sessions

---

## ARCHITECTURAL ISSUE: TWO DETECTION PATHS

The Enhanced Test workflow has **TWO SEPARATE** detection implementations:

### Path 1: Direct Polling (Currently Used)
```python
# api_enhanced_test_workflow_integrated.py line 233
voltage = await labjack_service.read_single_voltage("AIN0")
if voltage > threshold:
    # Handle detection
```

**Issues:**
- Bypasses `DetectionConfig` entirely
- No debounce control
- No `constant_voltage_mode` support
- Manual detection logic

### Path 2: Detection Service (Proper Way)
```python
# services/labjack_detection_service.py line 300
monitor.start_monitoring(
    session_id=session_id,
    channels=channels,
    voltage_threshold=threshold,
    constant_voltage_mode=True  # ✅ Supports this
)
```

**Benefits:**
- Uses `DetectionConfig` properly
- Full feature support
- Centralized detection logic
- Tested and reliable

---

## RECOMMENDED SOLUTION: REFACTOR TO USE DETECTION SERVICE

**Instead of adding `constant_voltage_mode` to broken polling code, refactor Enhanced Test to use proper detection service.**

### Implementation Plan:

1. **Remove Direct Polling**
   - Delete lines 230-282 in `api_enhanced_test_workflow_integrated.py`

2. **Use Detection Service**
   ```python
   from services.labjack_detection_service import get_detection_service

   @router.post("/start")
   async def start_detection_validation_test(...):
       detection_service = get_detection_service()

       # Start proper monitoring
       success = detection_service.start_monitoring(
           session_id=session_id,
           channels=config.channels,
           voltage_threshold=config.voltage_threshold,
           sample_rate=config.sample_rate,
           constant_voltage_mode=config.constant_voltage_mode,  # ✅ Pass through
           enable_websocket=True,
           store_in_db=True
       )
   ```

3. **Subscribe to Detection Events**
   ```python
   # Listen for detection events via callback
   def on_detection(event: DetectionEvent):
       # Update workflow state
       # Emit WebSocket to frontend

   detection_service.register_detection_callback(on_detection)
   ```

---

## QUICK FIX FOR IMMEDIATE TESTING

If refactoring is too large, here's the minimal change:

**File:** `api_enhanced_test_workflow_integrated.py`
**Line:** 23-28

```python
class DetectionTestConfig(BaseModel):
    project_id: str
    detection_window_ms: float = 500.0
    voltage_threshold: float = 2.5
    sample_rate: int = 1000
    channels: List[str] = ["AIN0", "AIN1"]
    constant_voltage_mode: bool = False  # ✅ ADD THIS
```

**Line:** 92-102 (update state)
```python
current_test_state.update({
    "config": config,  # Now includes constant_voltage_mode
    # ...
})
```

**Line:** 236 (modify detection check)
```python
# Read voltage from LabJack
voltage = await labjack_service.read_single_voltage("AIN0")

# Apply debounce logic unless in constant voltage mode
bypass_debounce = current_test_state["config"].constant_voltage_mode

if bypass_debounce or self._check_debounce(session_id, "AIN0", current_time):
    if voltage > current_test_state["config"].voltage_threshold:
        # Detection found!
```

---

## FILES TO MODIFY

### Primary Changes:
1. `/backend/api_enhanced_test_workflow_integrated.py` (Line 23-28, 92-102, 236)
2. `/backend/services/labjack_detection_service.py` (Line 426)

### Supporting Changes:
3. Frontend Enhanced Test form (add checkbox for constant voltage mode)
4. API documentation
5. Test cases

---

## TESTING CHECKLIST

After implementing fix:

- [ ] Enhanced Test API accepts `constant_voltage_mode` parameter
- [ ] Parameter is passed through to detection logic
- [ ] With `constant_voltage_mode=False`: Debounce active (existing behavior)
- [ ] With `constant_voltage_mode=True`: Debounce bypassed (100% detection)
- [ ] Frontend UI shows constant voltage mode option
- [ ] Database stores detection results correctly
- [ ] WebSocket events fire properly
- [ ] No regression in normal detection mode

---

## CONCLUSION

**The workflow is traced. The fix location is identified. The parameter exists but is not wired through the API.**

**Easiest Fix:** Add `constant_voltage_mode: bool = False` to `DetectionTestConfig` Pydantic model in `api_enhanced_test_workflow_integrated.py` line 28, then implement debounce bypass in detection loop at line 236.

**Best Fix:** Refactor Enhanced Test workflow to use `LabJackDetectionMonitor.start_monitoring()` instead of direct polling, which provides full `DetectionConfig` support including `constant_voltage_mode`.
