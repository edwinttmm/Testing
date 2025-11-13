/**
 * Detection Event Schema Validation & Normalization
 *
 * Provides runtime validation and field normalization for detection events
 * from various backend API endpoints.
 */

import { EnhancedDetectionEvent, SequenceDetectionEvent } from '../types/enhanced-results';

/**
 * Canonical field mapping for detection events
 * Maps all backend field variations to single normalized names
 */
export const CANONICAL_FIELD_MAP = {
  // Detection Identity
  id: ['id', 'detection_id', 'event_id'],
  detection_id: ['detection_id', 'detectionId', 'id'],

  // Timing Fields - UPDATED (Issue #2 - Agent 1)
  latency_ms: ['actual_latency_ms', 'actualLatencyMs', 'latency_ms', 'real_latency_ms', 'detection_time_ms'], // NEW: actual_latency_ms is PRIMARY
  actual_latency_ms: ['actual_latency_ms', 'actualLatencyMs'], // NEW: Explicit unified latency field
  timestamp: ['timestamp', 'detection_time', 'event_time'],
  sequence_timestamp: ['sequence_timestamp', 'sequenceTimestamp'],
  video_relative_timestamp: ['video_relative_timestamp', 'videoRelativeTimestamp'],
  video_play_offset_ms: ['video_play_offset_ms', 'videoPlayOffsetMs'],
  // NEW BACKEND FIELDS (Issue #2 - Agent 1)
  video_start_time: ['video_start_time', 'videoStartTime'], // NEW: Video start epoch timestamp
  video_end_time: ['video_end_time', 'videoEndTime'],       // NEW: Video end epoch timestamp

  // Hardware Fields
  voltage: ['voltage', 'labjack_voltage', 'voltage_level', 'signalValue'],
  channel: ['channel', 'detection_channel'],

  // Frame References
  frame_number: ['frame_number', 'video_frame', 'frameNumber'],

  // NEW BACKEND FIELDS (Issue #2 - Agent 1)
  sequence_id: ['sequence_id', 'sequenceId'],                           // NEW: Video sequence identifier
  sequence_video_result_id: ['sequence_video_result_id', 'sequenceVideoResultId'], // NEW: Links to specific video

  // Validation Fields
  validation_result: ['validation_result', 'validationResult', 'passed'],
  validation_status: ['validation_status', 'validationStatus'],
  validation_type: ['validation_type', 'validationType'],

  // Detection Metadata
  confidence: ['confidence', 'confidence_score', 'detection_score'],
  class_label: ['class_label', 'class_name', 'className', 'vru_type'],

  // Ground Truth
  ground_truth_match_id: ['ground_truth_match_id', 'groundTruthMatchId'],
  iou_score: ['iou_with_ground_truth', 'match_iou_score', 'iou_score']
} as const;

/**
 * Extract first available value from field variations
 */
function getFirstAvailableField<T>(
  obj: Record<string, any>,
  fieldNames: readonly string[]
): T | undefined {
  for (const field of fieldNames) {
    if (obj[field] !== undefined && obj[field] !== null) {
      return obj[field];
    }
  }
  return undefined;
}

/**
 * Normalize detection event to canonical field names
 * Handles all backend API response variations
 */
export function normalizeDetectionEvent(
  rawEvent: Record<string, any>
): EnhancedDetectionEvent {
  return {
    // Required fields
    id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.id) || `evt_${Date.now()}_${Math.random()}`,
    timestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.timestamp) || 0,
    frame_number: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.frame_number) || 0,
    detection_time_ms: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.latency_ms) || 0,
    labJack_trigger_time_ms: rawEvent.labjack_trigger_time || rawEvent.timestamp || 0,
    passed: Boolean(rawEvent.passed ?? true),

    // Optional backend standardized fields
    detection_id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.detection_id),
    validation_type: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.validation_type),
    validation_status: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.validation_status),
    validation_result: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.validation_result),
    validation_quality: rawEvent.validation_quality,
    timing_correction_summary: rawEvent.timing_correction_summary,

    // NEW BACKEND FIELDS (Issue #2 - Agent 1) - Unified latency
    actual_latency_ms: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.actual_latency_ms),

    // Multi-video sequence fields
    sequence_timestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.sequence_timestamp),
    video_relative_timestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.video_relative_timestamp),
    video_play_offset_ms: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.video_play_offset_ms),
    // NEW BACKEND FIELDS (Issue #2 - Agent 1)
    sequence_id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.sequence_id),
    sequence_video_result_id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.sequence_video_result_id),

    // Hardware fields
    voltage: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.voltage),
    channel: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.channel),

    // Detection metadata
    confidence: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.confidence),
    class_label: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.class_label),
    vru_type: rawEvent.vru_type || rawEvent.vruType,
    bounding_box: rawEvent.bounding_box || rawEvent.boundingBox,

    // Ground truth
    ground_truth_match_id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.ground_truth_match_id),
    iou_with_ground_truth: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.iou_score),
    ground_truth_available: rawEvent.ground_truth_available,

    // Timing quality
    timing_quality: rawEvent.timing_quality,
    real_latency_ms: rawEvent.real_latency_ms,
    apparent_latency_ms: rawEvent.apparent_latency_ms,
    processing_time_ms: rawEvent.processing_time_ms || rawEvent.processing_latency_ms,

    // Failure information
    error_message: rawEvent.error_message || rawEvent.errorMessage,
    failure_reason: rawEvent.failure_reason || rawEvent.failureReason,
    failure_type: rawEvent.failure_type || rawEvent.failureType,
    screenshot_path: rawEvent.screenshot_path || rawEvent.screenshotPath,
    screenshot_zoom_path: rawEvent.screenshot_zoom_path || rawEvent.screenshotZoomPath,

    // Additional tracking
    tracking_id: rawEvent.tracking_id || rawEvent.trackingId,
    inference_session_id: rawEvent.inference_session_id || rawEvent.inferenceSessionId,

    // Measured breakdown (if available)
    measured_breakdown: rawEvent.measured_breakdown || rawEvent.measuredBreakdown
  };
}

/**
 * Normalize sequence detection event
 */
export function normalizeSequenceEvent(
  rawEvent: Record<string, any>
): SequenceDetectionEvent {
  return {
    id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.id) || `seq_${Date.now()}`,
    timestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.timestamp) || 0,

    // Sequence timing
    video_relative_timestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.video_relative_timestamp),
    videoRelativeTimestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.video_relative_timestamp),
    sequence_timestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.sequence_timestamp),
    sequenceTimestamp: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.sequence_timestamp),
    video_play_offset_ms: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.video_play_offset_ms),
    videoPlayOffsetMs: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.video_play_offset_ms),

    // Signal fields
    signalType: rawEvent.signalType || rawEvent.signal_type,
    channel: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.channel),
    signalValue: rawEvent.signalValue || rawEvent.signal_value,
    voltage: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.voltage),

    // Detection fields
    detection_id: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.detection_id),
    frame_number: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.frame_number),
    validation_result: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.validation_result),
    validation_status: getFirstAvailableField(rawEvent, CANONICAL_FIELD_MAP.validation_status)
  };
}

/**
 * Validate detection event has required fields
 */
export function validateDetectionEvent(event: any): event is EnhancedDetectionEvent {
  return (
    event &&
    typeof event === 'object' &&
    ('id' in event || 'detection_id' in event) &&
    ('timestamp' in event || 'detection_time' in event) &&
    ('frame_number' in event || 'video_frame' in event)
  );
}

/**
 * Normalize array of detection events
 */
export function normalizeDetectionEventArray(
  rawEvents: Record<string, any>[]
): EnhancedDetectionEvent[] {
  return rawEvents
    .filter(validateDetectionEvent)
    .map(normalizeDetectionEvent);
}

/**
 * Type guard for sequence detection event
 */
export function isSequenceDetectionEvent(event: any): event is SequenceDetectionEvent {
  return (
    event &&
    typeof event === 'object' &&
    ('sequence_timestamp' in event || 'sequenceTimestamp' in event ||
     'video_play_offset_ms' in event || 'videoPlayOffsetMs' in event)
  );
}

/**
 * Extract detection ID with fallback
 */
export function getDetectionId(event: Record<string, any>): string {
  return getFirstAvailableField(event, CANONICAL_FIELD_MAP.detection_id) ||
         `unknown_${Date.now()}`;
}

/**
 * Extract latency value with proper typing
 */
export function getLatencyMs(event: Record<string, any>): number {
  const latency = getFirstAvailableField<number | string>(event, CANONICAL_FIELD_MAP.latency_ms);
  if (typeof latency === 'string') {
    const parsed = parseFloat(latency);
    return isNaN(parsed) ? 0 : parsed;
  }
  return latency || 0;
}

/**
 * Extract voltage with fallback
 */
export function getVoltage(event: Record<string, any>): number {
  return getFirstAvailableField<number>(event, CANONICAL_FIELD_MAP.voltage) || 0;
}
