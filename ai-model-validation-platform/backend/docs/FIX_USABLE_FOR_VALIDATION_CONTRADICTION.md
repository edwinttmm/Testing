# Fix: usable_for_validation Contradiction

## Problem Statement

**Critical Bug:** Detections are marked as `usable_for_validation=True` (100% rate) in storage, but quality assessment shows them as "unreliable", "unsuitable for validation", "imprecise". This is contradictory and misleading.

## Root Cause Analysis

### Current Broken Logic

**File:** `services/dedicated_labjack_monitor.py`

**Line 961:**
```python
# Sets based only on session-level flag
usable_for_validation = timing_available and not timing_degraded
```

**Problem:** This only checks session-level timing health, not per-detection quality metrics.

### Quality Assessment Disconnect

**File:** `services/frame_aware_quality_assessment.py`

**Lines 659-668:**
```python
def _assess_validation_suitability(self, quality: TimingQualityDimensions) -> str:
    """Assess suitability for validation purposes"""
    reliability = quality.validation_reliability

    if reliability >= 0.8:
        return "suitable"
    elif reliability >= 0.6:
        return "conditional"
    else:
        return "unsuitable"
```

**Problem:** Quality assessment results (category, validation_suitability) are NOT persisted to DetectionEvent model.

## Solution Design

### Fix 1: Enhance usable_for_validation Logic

**Location:** `services/dedicated_labjack_monitor.py` (line 961, 1352)

**Before:**
```python
usable_for_validation = timing_available and not timing_degraded
```

**After:**
```python
# Consider both session-level AND per-detection quality
usable_for_validation = timing_available and not timing_degraded

# Note: This will be further refined after quality assessment
# If quality_assessment results in "unreliable" category or "unsuitable" validation_suitability,
# usable_for_validation will be updated to False before database commit
```

### Fix 2: Add Quality Fields to DetectionEvent Model

**Location:** `models.py` (DetectionEvent class)

**Add fields:**
```python
# TIMING QUALITY TRACKING (NEW)
quality_category = Column(String, nullable=True, index=True)  # "excellent", "good", "acceptable", "unreliable"
quality_validation_suitability = Column(String, nullable=True, index=True)  # "suitable", "conditional", "unsuitable"
quality_notes = Column(Text, nullable=True)  # Human-readable quality assessment notes
```

### Fix 3: Apply Quality Assessment to usable_for_validation

**Location:** `services/dedicated_labjack_monitor.py`

**New logic after quality assessment:**
```python
# Perform quality assessment (after calculating latency/timing)
quality_assessment = assess_detection_quality(detection)

# CRITICAL FIX: Update usable_for_validation based on quality assessment
if quality_assessment:
    detection.quality_category = quality_assessment.category
    detection.quality_validation_suitability = quality_assessment.validation_suitability
    detection.quality_notes = quality_assessment.notes

    # Update usable_for_validation based on quality results
    # Only mark as usable if BOTH session timing is good AND quality is acceptable
    if quality_assessment.category == "unreliable" or quality_assessment.validation_suitability == "unsuitable":
        detection.usable_for_validation = False
        logger.warning(f"⚠️ Detection {detection.id} marked as NON-USABLE due to {quality_assessment.category} quality")
```

### Fix 4: Add Clamping Detection to video_timing_service.py

**Location:** `services/video_timing_service.py` (or detection_window_clamp_service.py)

**Purpose:** Flag clamped detections instead of silently hiding errors.

**Before:**
```python
if video_relative > duration:
    video_relative = duration  # Silently clamp
```

**After:**
```python
if video_relative > duration:
    detection.timing_clamped = True
    detection.original_video_relative = video_relative
    detection.quality_notes = f"Clamped from {video_relative:.3f}s to {duration:.3f}s"
    video_relative = duration
    logger.warning(f"⚠️ Detection {detection.id} exceeded video duration, clamped")
```

## Implementation Steps

1. **Add new fields to DetectionEvent model** (`models.py`)
2. **Create database migration** for new quality tracking fields
3. **Update dedicated_labjack_monitor.py** to perform quality assessment and update flags
4. **Update detection_window_clamp_service.py** to flag clamping instead of hiding
5. **Add integration tests** to verify quality tracking works correctly

## Expected Outcome

After fixes:

- Detections with "unreliable" quality → `usable_for_validation=False`
- Detections with "unsuitable" validation_suitability → `usable_for_validation=False`
- Quality assessment results (category, suitability, notes) → Persisted in database
- Clamped detections → Flagged with timing_clamped=True
- Quality metrics → Visible in API responses and reports

## Validation Rate Impact

**Before:** 100% validation rate (incorrect)
**After:** Expected 60-80% validation rate (accurate reflection of quality)

Detections will be correctly classified:
- Excellent quality → usable_for_validation=True
- Good quality → usable_for_validation=True
- Acceptable quality → usable_for_validation=True (with notes)
- Unreliable quality → usable_for_validation=False
- Unsuitable for validation → usable_for_validation=False

## Files Modified

1. `/backend/models.py` - Add quality tracking fields
2. `/backend/services/dedicated_labjack_monitor.py` - Enhance validation logic
3. `/backend/services/detection_window_clamp_service.py` - Add clamping flags
4. `/backend/migrations/versions/add_detection_quality_tracking.py` - Database migration

## Testing Requirements

1. Test that unreliable detections are marked as non-usable
2. Test that quality assessment results are persisted
3. Test that clamping is detected and flagged
4. Test that validation rate reflects actual quality (not 100%)
5. Integration test for full quality tracking workflow
