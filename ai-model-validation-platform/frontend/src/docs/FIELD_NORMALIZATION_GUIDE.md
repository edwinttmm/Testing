# Detection Event Field Normalization Guide

## Overview
This guide explains how to use the detection event schema utilities for consistent field handling across the application.

## The Problem

Backend API endpoints return detection events with varying field names:
```typescript
// Endpoint 1
{ detection_id: "123", latency_ms: 45.2, voltage: 2.5 }

// Endpoint 2
{ id: "123", actual_latency_ms: 45.2, labjack_voltage: 2.5 }

// Endpoint 3
{ event_id: "123", real_latency_ms: 45.2, voltage_level: 2.5 }
```

## The Solution

Use `normalizeDetectionEvent()` for consistent field access:

```typescript
import { normalizeDetectionEvent } from '../utils/detectionEventSchema';

// Raw API response
const rawEvent = apiResponse.detection_events[0];

// Normalized event with canonical field names
const event = normalizeDetectionEvent(rawEvent);

// Now access with confidence:
console.log(event.detection_id);  // ✅ Always available
console.log(event.detection_time_ms);  // ✅ Latency, never voltage
console.log(event.voltage);  // ✅ Voltage in voltage field
```

## Usage Examples

### 1. Normalizing API Response Arrays

```typescript
import { normalizeDetectionEventArray } from '../utils/detectionEventSchema';

const response = await apiService.getDetectionEvents(sessionId);
const normalizedEvents = normalizeDetectionEventArray(response.events);

// Now safe to map over
normalizedEvents.forEach(event => {
  console.log(`Detection ${event.detection_id}: ${event.detection_time_ms}ms`);
});
```

### 2. Type Guards

```typescript
import { validateDetectionEvent, isSequenceDetectionEvent } from '../utils/detectionEventSchema';

// Check if object is valid detection event
if (validateDetectionEvent(unknownObject)) {
  // TypeScript knows it's EnhancedDetectionEvent
  const latency = unknownObject.detection_time_ms;
}

// Check if event is from multi-video sequence
if (isSequenceDetectionEvent(event)) {
  console.log(`Sequence time: ${event.sequence_timestamp}s`);
  console.log(`Video offset: ${event.video_play_offset_ms}ms`);
}
```

### 3. Extracting Specific Fields

```typescript
import { getDetectionId, getLatencyMs, getVoltage } from '../utils/detectionEventSchema';

// Safe extraction with fallbacks
const detectionId = getDetectionId(rawEvent);  // Never undefined
const latency = getLatencyMs(rawEvent);  // Always number, never voltage
const voltage = getVoltage(rawEvent);  // Always number
```

### 4. Component Integration

```typescript
import { normalizeDetectionEvent } from '../utils/detectionEventSchema';
import { EnhancedDetectionEvent } from '../types/enhanced-results';

interface DetectionTableProps {
  events: EnhancedDetectionEvent[];
}

export const DetectionTable: React.FC<DetectionTableProps> = ({ events }) => {
  // Events are already normalized, safe to use directly
  return (
    <table>
      {events.map(event => (
        <tr key={event.detection_id || event.id}>
          <td>{event.detection_id}</td>
          <td>{event.detection_time_ms}ms</td>
          <td>{event.voltage}V</td>
          <td>{event.frame_number}</td>
        </tr>
      ))}
    </table>
  );
};

// When receiving raw API data:
function loadDetections() {
  const rawEvents = await apiService.getDetections();
  const normalized = rawEvents.map(normalizeDetectionEvent);
  setEvents(normalized);
}
```

## Field Mapping Reference

### Canonical Field → Backend Variations

| Canonical Field | Backend Variations |
|----------------|-------------------|
| `detection_id` | detection_id, detectionId, id, event_id |
| `detection_time_ms` | latency_ms, actual_latency_ms, real_latency_ms, detection_time_ms |
| `voltage` | voltage, labjack_voltage, voltage_level, signalValue |
| `frame_number` | frame_number, video_frame, frameNumber |
| `validation_result` | validation_result, validationResult, passed |
| `sequence_timestamp` | sequence_timestamp, sequenceTimestamp |
| `video_relative_timestamp` | video_relative_timestamp, videoRelativeTimestamp |
| `confidence` | confidence, confidence_score, detection_score |

## Migration Path

### Before (Direct API Access):
```typescript
// ❌ Fragile: breaks if API changes field names
const latency = event.latency_ms || event.actual_latency_ms || event.real_latency_ms || 0;
const voltage = event.voltage || event.labjack_voltage || 0;
const id = event.detection_id || event.id || 'unknown';
```

### After (Normalized):
```typescript
// ✅ Robust: handles all variations automatically
const normalized = normalizeDetectionEvent(event);
const latency = normalized.detection_time_ms;
const voltage = normalized.voltage;
const id = normalized.detection_id;
```

## Best Practices

### DO:
- ✅ Always normalize events at API boundary (in service layer)
- ✅ Pass normalized `EnhancedDetectionEvent` to components
- ✅ Use type guards before accessing optional fields
- ✅ Use extraction helpers for single field access

### DON'T:
- ❌ Access raw API response fields directly in components
- ❌ Repeat field variation checks throughout codebase
- ❌ Mix voltage and latency fields
- ❌ Assume field names are consistent across endpoints

## Future: Zod Schema Validation

Once backend fully standardizes (single field names), consider adding Zod:

```typescript
import { z } from 'zod';

const DetectionEventSchema = z.object({
  detection_id: z.string(),
  detection_time_ms: z.number(),
  voltage: z.number(),
  frame_number: z.number(),
  timestamp: z.number(),
  // ... all required fields
}).strict();

// Runtime validation
const validated = DetectionEventSchema.parse(apiResponse);
```

## Troubleshooting

### Problem: Field is undefined after normalization
**Cause**: Backend not sending any of the expected field variations
**Solution**: Check `CANONICAL_FIELD_MAP` and add the backend field name

### Problem: Getting voltage value for latency
**Cause**: Using raw API response instead of normalized event
**Solution**: Always call `normalizeDetectionEvent()` first

### Problem: TypeScript errors about missing fields
**Cause**: Using old type definitions
**Solution**: Import `EnhancedDetectionEvent` from `types/enhanced-results`

## Related Files

- **Type Definitions**: `/frontend/src/types/enhanced-results.ts`
- **Schema Utils**: `/frontend/src/utils/detectionEventSchema.ts`
- **Backend Schema**: `/backend/schemas.py` (DetectionEventResponse)
- **Type Safety Doc**: `/frontend/src/docs/TYPE_SAFETY_UPDATES_SUMMARY.md`

---

**Remember**: Normalize once at the API boundary, use typed data everywhere else.
