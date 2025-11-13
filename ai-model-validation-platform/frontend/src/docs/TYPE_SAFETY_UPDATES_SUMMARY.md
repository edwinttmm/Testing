# Type Safety & Schema Consistency Updates

## Overview
Standardized frontend TypeScript types to match backend API schema, eliminating field naming inconsistencies and adding missing fields.

## Changes Made

### 1. Enhanced `DetectionLatencyEvent` Interface
**File**: `/frontend/src/types/enhanced-results.ts`

**Added Fields**:
- `detection_id?: string` - Backend standardized unique detection identifier
- `validation_type?: 'automatic' | 'manual' | 'hybrid'` - Validation methodology
- `validation_quality?: string` - Quality indicator for validation
- `timing_correction_summary?: string` - Summary of timing corrections applied
- `actual_latency_ms?: string | number` - Flexible type for latency (backend sends both)

**Purpose**: Match backend `DetectionEventResponse` schema with all camelCase aliases.

### 2. Enhanced `EnhancedDetectionEvent` Interface

**New Backend Standardized Fields**:
```typescript
// Detection Identity
detection_id?: string;  // Unique detection identifier

// Multi-Video Sequence Fields (from backend schema)
sequence_timestamp?: number;
sequence_timestamp_ns?: string;
video_relative_timestamp?: number;
video_relative_timestamp_ns?: string;
video_play_offset_ms?: number;
sequence_video_result_id?: string;

// Validation Fields
validation_type?: 'automatic' | 'manual' | 'hybrid';
validation_status?: string;
validation_result?: string | boolean;
validation_quality?: string;
timing_correction_summary?: string;

// Detection Metadata
class_label?: string;
class_name?: string;
vru_type?: string;
bounding_box?: Record<string, any>;
tracking_id?: string;
inference_session_id?: string;
detection_score?: number;
nms_score?: number;
iou_with_ground_truth?: number;
```

**Dual Field Support**:
- `confidence_score?: number` and `confidence?: number` - Backend uses both
- `video_frame?: number` - Video-specific frame reference

### 3. Enhanced `SequenceDetectionEvent` Interface

**Added Multi-Video Sequence Support**:
```typescript
// Backend multi-video sequence fields (both snake_case and camelCase)
video_relative_timestamp?: number | null;
videoRelativeTimestamp?: number | null;
sequence_timestamp?: number | null;
sequenceTimestamp?: number | null;
video_play_offset_ms?: number | null;
videoPlayOffsetMs?: number | null;

// Signal fields
channel?: number | string | null;  // Flexible type (backend sends both)
voltage?: number | null;

// Detection fields
detection_id?: string;
frame_number?: number;
validation_result?: string | boolean;
validation_status?: string;
```

## Backend Schema Alignment

### Backend Source Files Referenced:
1. `/backend/schemas.py` - `DetectionEventResponse`, `SequenceDetectionEventResponse`
2. `/backend/routers/video_sequence_testing.py` - Multi-video sequence handling
3. `/backend/migrations/add_video_sequence_schema.py` - Database schema

### Key Backend Fields Matched:
- `detection_id` (VARCHAR(36)) - Unique identifier
- `validation_type` (Enum: automatic, manual, hybrid)
- `sequence_timestamp` (FLOAT) - Sequence-relative timestamp
- `video_play_offset_ms` (FLOAT) - Offset from video start
- `video_relative_timestamp` (FLOAT) - Video-relative time
- `validation_status` (VARCHAR) - Current validation state

## Field Confusion Fixed

### ✅ ALREADY FIXED (Lines 351-370 in EnhancedResults.tsx):
```typescript
// OLD (WRONG): Used voltage for latency
detection_time_ms: evt.voltage || 0,  // ❌ WRONG

// NEW (CORRECT): Use actual latency fields
detection_time_ms: evt.latency_ms || evt.actual_latency_ms || 0,  // ✅ CORRECT
voltage: evt.voltage || 0,  // Keep voltage in voltage field
```

## Normalization Strategy

### Current Approach (Retained):
The frontend still handles multiple field variations for backward compatibility:
- `latency_ms` OR `actual_latency_ms` OR `real_latency_ms`
- `voltage` OR `labjack_voltage` OR `voltage_level`
- `frame_number` OR `video_frame`

### Future Simplification:
Once backend fully standardizes to single field names, frontend can simplify to:
```typescript
// Simplified mapping (post-backend-standardization)
const normalizedEvent = {
  detection_id: evt.detection_id,
  latency_ms: evt.actual_latency_ms,
  voltage: evt.voltage,
  frame_number: evt.frame_number,
  // ... single canonical field per property
};
```

## Component Updates Needed

### Components Using EnhancedDetectionEvent:
1. ✅ `FrameCorrelationTimeline.tsx` - Already handles optional fields
2. ✅ `SequentialVideoPlayer.tsx` - Uses timing utils with flexible types
3. ⚠️ `DetectionTableRow.tsx` - May need `detection_id` field display
4. ⚠️ `VideoSequenceResults.tsx` - May need sequence field display

### Recommended Next Steps:
1. Update `DetectionTableRow.tsx` to display `detection_id` if available
2. Add sequence timing fields to `VideoSequenceResults.tsx` display
3. Consider Zod schema validation for runtime type checking
4. Create field mapping utility for consistent normalization

## Type Safety Improvements

### Before:
```typescript
// Missing fields caused TypeScript errors
const event: EnhancedDetectionEvent = apiResponse;  // ❌ Type error
```

### After:
```typescript
// All backend fields are typed
const event: EnhancedDetectionEvent = apiResponse;  // ✅ Type safe
```

## Testing Recommendations

1. **Backend API Response Validation**:
   - Verify all fields in `DetectionEventResponse` are received
   - Check camelCase aliases work correctly
   - Test multi-video sequence field population

2. **Frontend Display**:
   - Ensure latency values display correctly (not voltage)
   - Verify sequence timestamps show relative to video start
   - Check detection_id appears in debug/detail views

3. **Field Normalization**:
   - Test with different backend response variations
   - Verify backward compatibility with older API responses
   - Confirm flexible types (string | number) work correctly

## Breaking Changes
**None** - All changes are additive (optional fields) maintaining backward compatibility.

## Dependencies
- Backend schema changes from detection-fix swarm
- Multi-video sequence implementation
- LabJack timing validation system

## Documentation References
- Backend Schema: `/backend/docs/types/backend-schemas.md`
- Multi-Video: `/backend/migrations/MULTI_VIDEO_SEQUENCE_IMPLEMENTATION_SUMMARY.md`
- Field Mapping: See backend `CamelCaseModel` with `alias_generator`

---

**Status**: ✅ Type definitions updated, ready for component integration
**Next Agent**: Component update agent to use new fields in UI
