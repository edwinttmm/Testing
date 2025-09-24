/**
 * VRU Tracking Utilities
 * 
 * Helper functions and utilities for VRU (Vulnerable Road User) tracking
 * in Hardware-in-the-Loop (HIL) testing systems.
 */

import { 
  VRUType, 
  VRUPosition, 
  VRUVelocity, 
  VRUBoundingBox,
  VRUTrack,
  VRUTrackMatch,
  VRUMatchCandidate,
  VRUDetectionEvent,
  MatchType,
  VRUTrackingConfig,
  DEFAULT_VRU_TRACKING_CONFIG
} from '../types/vru-tracking';
import { GroundTruthAnnotation } from '../services/types';

/**
 * Generate unique track ID
 */
export const generateTrackId = (vruType: VRUType, startTime: number): string => {
  const timestamp = Math.floor(startTime * 1000);
  const random = Math.floor(Math.random() * 1000);
  return `${vruType}_${timestamp}_${random}`;
};

/**
 * Generate unique detection event ID
 */
export const generateEventId = (trackId: string, timestamp: number): string => {
  const eventTimestamp = Math.floor(timestamp * 1000);
  const random = Math.floor(Math.random() * 100);
  return `${trackId}_event_${eventTimestamp}_${random}`;
};

/**
 * Convert string to VRUType enum
 */
export const parseVRUType = (typeString: string): VRUType => {
  const normalized = typeString.toLowerCase().trim();
  
  switch (normalized) {
    case 'pedestrian':
    case 'person':
    case 'walker':
      return VRUType.PEDESTRIAN;
      
    case 'cyclist':
    case 'bicycle':
    case 'bike':
    case 'cycling':
      return VRUType.CYCLIST;
      
    case 'motorcyclist':
    case 'motorcycle':
    case 'motorbike':
    case 'scooter':
      return VRUType.MOTORCYCLIST;
      
    case 'wheelchair_user':
    case 'wheelchair':
      return VRUType.WHEELCHAIR_USER;
      
    case 'scooter_rider':
    case 'e_scooter':
    case 'escooter':
      return VRUType.SCOOTER_RIDER;
      
    default:
      console.warn(`Unknown VRU type: ${typeString}, defaulting to UNKNOWN`);
      return VRUType.UNKNOWN;
  }
};

/**
 * Extract bounding box center position
 */
export const getBoundingBoxCenter = (bbox: VRUBoundingBox): { x: number, y: number } => {
  return {
    x: bbox.x + (bbox.width / 2),
    y: bbox.y + (bbox.height / 2)
  };
};

/**
 * Calculate Euclidean distance between two positions
 */
export const calculateSpatialDistance = (pos1: VRUPosition, pos2: VRUPosition): number => {
  const dx = pos1.x - pos2.x;
  const dy = pos1.y - pos2.y;
  return Math.sqrt(dx * dx + dy * dy);
};

/**
 * Calculate temporal distance between timestamps
 */
export const calculateTemporalDistance = (time1: number, time2: number): number => {
  return Math.abs(time1 - time2);
};

/**
 * Calculate velocity between two positions
 */
export const calculateVelocity = (pos1: VRUPosition, pos2: VRUPosition): VRUVelocity => {
  const timeDelta = pos2.timestamp - pos1.timestamp;
  
  if (timeDelta === 0) {
    return {
      vx: 0,
      vy: 0,
      speed: 0,
      direction: 0
    };
  }
  
  const vx = (pos2.x - pos1.x) / timeDelta;
  const vy = (pos2.y - pos1.y) / timeDelta;
  const speed = Math.sqrt(vx * vx + vy * vy);
  const direction = Math.atan2(vy, vx);
  
  return { vx, vy, speed, direction };
};

/**
 * Convert ground truth annotation to VRU position
 */
export const annotationToPosition = (annotation: GroundTruthAnnotation): VRUPosition => {
  const boundingBox: VRUBoundingBox = {
    x: annotation.bounding_box?.x || 0,
    y: annotation.bounding_box?.y || 0,
    width: annotation.bounding_box?.width || 0,
    height: annotation.bounding_box?.height || 0,
    confidence: annotation.confidence
  };
  
  const center = getBoundingBoxCenter(boundingBox);
  
  return {
    x: center.x,
    y: center.y,
    timestamp: annotation.timestamp,
    confidence: annotation.confidence || 0.5,
    boundingBox
  };
};

/**
 * Check if two positions are within spatial clustering radius
 */
export const arePositionsSpatiallyClose = (
  pos1: VRUPosition, 
  pos2: VRUPosition, 
  radius: number
): boolean => {
  const distance = calculateSpatialDistance(pos1, pos2);
  return distance <= radius;
};

/**
 * Check if two timestamps are within temporal clustering window
 */
export const areTimestampsTemporallyClose = (
  time1: number, 
  time2: number, 
  windowSeconds: number
): boolean => {
  const distance = calculateTemporalDistance(time1, time2);
  return distance <= windowSeconds;
};

/**
 * Calculate match score between HIL signal and VRU track
 */
export const calculateMatchScore = (
  signalTimestamp: number,
  track: VRUTrack,
  config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG
): number => {
  // Temporal score - closer timestamps get higher scores
  const closestAnnotation = track.annotations.reduce((closest, ann) => {
    const closestDiff = Math.abs(closest.timestamp - signalTimestamp);
    const currentDiff = Math.abs(ann.timestamp - signalTimestamp);
    return currentDiff < closestDiff ? ann : closest;
  });
  
  const temporalDiff = Math.abs(closestAnnotation.timestamp - signalTimestamp);
  const temporalScore = Math.max(0, 1 - (temporalDiff / config.maxTemporalWindow));
  
  // Confidence score - higher confidence annotations contribute more
  const confidenceScore = track.averageConfidence;
  
  // Track quality score - more consistent tracks get higher scores
  const qualityScore = (track.trackConfidence + track.temporalConsistency) / 2;
  
  // Weighted combination
  const matchScore = (
    temporalScore * config.temporalWeight +
    confidenceScore * config.confidenceWeight +
    qualityScore * (1 - config.temporalWeight - config.confidenceWeight)
  );
  
  return Math.max(0, Math.min(1, matchScore));
};

/**
 * Determine match type based on timing and track state
 */
export const determineMatchType = (
  signalTimestamp: number,
  track: VRUTrack,
  temporalDistance: number
): MatchType => {
  // Check if signal timestamp matches exactly with any annotation
  const exactMatch = track.annotations.some(ann => 
    Math.abs(ann.timestamp - signalTimestamp) < 0.05 // 50ms tolerance for "exact"
  );
  
  if (exactMatch) {
    return MatchType.EXACT;
  }
  
  // Check if signal timestamp is within track time bounds
  if (signalTimestamp >= track.startTime && signalTimestamp <= track.endTime) {
    return MatchType.INTERPOLATED;
  }
  
  // Check if signal is close to track bounds (prediction case)
  const startDistance = Math.abs(signalTimestamp - track.startTime);
  const endDistance = Math.abs(signalTimestamp - track.endTime);
  const minDistance = Math.min(startDistance, endDistance);
  
  if (minDistance <= 1.0) { // Within 1 second of track bounds
    return MatchType.PREDICTED;
  }
  
  return MatchType.MISSED;
};

/**
 * Create match candidate from track and signal
 */
export const createMatchCandidate = (
  signalTimestamp: number,
  track: VRUTrack,
  config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG
): VRUMatchCandidate => {
  const matchScore = calculateMatchScore(signalTimestamp, track, config);
  
  // Find closest annotation for temporal scoring
  const closestAnnotation = track.annotations.reduce((closest, ann) => {
    const closestDiff = Math.abs(closest.timestamp - signalTimestamp);
    const currentDiff = Math.abs(ann.timestamp - signalTimestamp);
    return currentDiff < closestDiff ? ann : closest;
  });
  
  const timeDifference = Math.abs(closestAnnotation.timestamp - signalTimestamp) * 1000; // Convert to ms
  const temporalScore = Math.max(0, 1 - (timeDifference / (config.maxTemporalWindow * 1000)));
  
  const matchType = determineMatchType(signalTimestamp, track, timeDifference / 1000);
  
  return {
    track,
    matchScore,
    temporalScore,
    confidenceScore: track.averageConfidence,
    distanceScore: 1 - Math.min(1, timeDifference / (config.maxTemporalWindow * 1000)),
    timeDifference,
    matchType
  };
};

/**
 * Filter tracks that could potentially match a signal
 */
export const filterPotentialTracks = (
  signalTimestamp: number,
  tracks: VRUTrack[],
  config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG
): VRUTrack[] => {
  return tracks.filter(track => {
    // Check if signal is within expanded temporal window of track
    const expandedWindow = config.maxTemporalWindow * 2; // Give extra buffer
    const trackStart = track.startTime - expandedWindow;
    const trackEnd = track.endTime + expandedWindow;
    
    return signalTimestamp >= trackStart && signalTimestamp <= trackEnd;
  });
};

/**
 * Sort match candidates by quality score
 */
export const sortMatchCandidates = (candidates: VRUMatchCandidate[]): VRUMatchCandidate[] => {
  return [...candidates].sort((a, b) => b.matchScore - a.matchScore);
};

/**
 * Check if a match meets minimum quality thresholds
 */
export const isMatchValid = (
  candidate: VRUMatchCandidate,
  config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG
): boolean => {
  return (
    candidate.matchScore >= config.minMatchScore &&
    candidate.track.trackConfidence >= config.minTrackConfidence &&
    candidate.timeDifference <= (config.maxLatencyMs)
  );
};

/**
 * Calculate latency from match
 */
export const calculateLatency = (match: VRUTrackMatch): number => {
  return Math.abs(match.actualTime - match.expectedTime) * 1000; // Convert to ms
};

/**
 * Determine detection event outcome based on latency
 */
export const determineEventOutcome = (
  latencyMs: number,
  thresholdMs: number,
  matchFound: boolean
): 'pass' | 'fail_high_latency' | 'fail_missed_detection' | 'fail_false_positive' => {
  if (!matchFound) {
    return 'fail_missed_detection';
  }
  
  if (latencyMs <= thresholdMs) {
    return 'pass';
  }
  
  return 'fail_high_latency';
};

/**
 * Create detection event from match result
 */
export const createDetectionEvent = (
  match: VRUTrackMatch | null,
  signalData: any,
  sessionId: string,
  videoId: string,
  projectId: string,
  thresholdMs: number,
  processingStartTime: number
): VRUDetectionEvent => {
  const eventId = match ? 
    generateEventId(match.track.trackId, signalData.timestamp / 1000) : 
    generateEventId('unmatched', signalData.timestamp / 1000);
  
  const timestamp = (signalData.timestamp || Date.now()) / 1000; // Convert to seconds
  const frameNumber = Math.floor(timestamp * 30); // Assume 30 FPS
  
  const latencyMs = match ? calculateLatency(match) : 0;
  const outcome = determineEventOutcome(latencyMs, thresholdMs, !!match);
  
  const processingTimeMs = Date.now() - processingStartTime;
  
  return {
    // Event identity
    id: eventId,
    eventType: match ? 'vru_matched' : 'vru_lost',
    
    // Timing
    timestamp,
    detectedAt: new Date(),
    frameNumber,
    
    // VRU context
    trackId: match?.track.trackId || 'unmatched',
    vruType: match?.track.vruType || VRUType.UNKNOWN,
    trackMatch: match || undefined,
    
    // Detection quality
    confidence: match?.confidence || 0,
    signalQuality: Math.min(1, (signalData.voltage || 0) / 5.0), // Normalize voltage to 0-1
    
    // HIL-specific data
    labJackChannel: signalData.channel,
    voltageLevel: signalData.voltage,
    signalRiseTime: signalData.riseTime,
    
    // Outcome assessment
    outcome,
    latencyMs: latencyMs,
    thresholdMs,
    
    // Spatial context
    position: match?.expectedPosition,
    boundingBox: match?.expectedPosition?.boundingBox,
    
    // Event metadata
    videoId,
    projectId,
    sessionId,
    processingTimeMs
  };
};

/**
 * Calculate track confidence based on annotation quality
 */
export const calculateTrackConfidence = (annotations: GroundTruthAnnotation[]): number => {
  if (annotations.length === 0) return 0;
  
  // Average confidence of all annotations
  const avgConfidence = annotations.reduce((sum, ann) => sum + (ann.confidence || 0.5), 0) / annotations.length;
  
  // Bonus for more annotations (more data = higher confidence)
  const dataBonus = Math.min(0.2, annotations.length * 0.02); // Up to 20% bonus
  
  // Penalty for sparse annotations (large time gaps)
  let sparsityPenalty = 0;
  if (annotations.length > 1) {
    annotations.sort((a, b) => a.timestamp - b.timestamp);
    let maxGap = 0;
    for (let i = 1; i < annotations.length; i++) {
      const gap = annotations[i].timestamp - annotations[i-1].timestamp;
      maxGap = Math.max(maxGap, gap);
    }
    sparsityPenalty = Math.min(0.3, maxGap * 0.1); // Up to 30% penalty for gaps > 3s
  }
  
  const confidence = avgConfidence + dataBonus - sparsityPenalty;
  return Math.max(0, Math.min(1, confidence));
};

/**
 * Calculate spatial consistency of track positions
 */
export const calculateSpatialConsistency = (positions: VRUPosition[]): number => {
  if (positions.length < 2) return 1.0; // Single point is perfectly consistent
  
  // Calculate average distance between consecutive positions
  let totalDistance = 0;
  let maxDistance = 0;
  
  for (let i = 1; i < positions.length; i++) {
    const distance = calculateSpatialDistance(positions[i-1], positions[i]);
    totalDistance += distance;
    maxDistance = Math.max(maxDistance, distance);
  }
  
  const avgDistance = totalDistance / (positions.length - 1);
  
  // Consistency is higher when movements are more uniform
  const consistency = avgDistance > 0 ? Math.min(1, avgDistance / maxDistance) : 1.0;
  return consistency;
};

/**
 * Calculate temporal consistency of track timestamps
 */
export const calculateTemporalConsistency = (annotations: GroundTruthAnnotation[]): number => {
  if (annotations.length < 2) return 1.0;
  
  // Sort by timestamp
  const sorted = [...annotations].sort((a, b) => a.timestamp - b.timestamp);
  
  // Calculate time intervals
  const intervals = [];
  for (let i = 1; i < sorted.length; i++) {
    intervals.push(sorted[i].timestamp - sorted[i-1].timestamp);
  }
  
  // Calculate coefficient of variation (std dev / mean)
  const mean = intervals.reduce((sum, interval) => sum + interval, 0) / intervals.length;
  const variance = intervals.reduce((sum, interval) => sum + Math.pow(interval - mean, 2), 0) / intervals.length;
  const stdDev = Math.sqrt(variance);
  
  const coefficientOfVariation = mean > 0 ? stdDev / mean : 0;
  
  // Lower coefficient of variation = higher consistency
  const consistency = Math.max(0, 1 - coefficientOfVariation);
  return consistency;
};

/**
 * Validate VRU tracking configuration
 */
export const validateTrackingConfig = (config: VRUTrackingConfig): boolean => {
  try {
    // Check required numeric ranges
    if (config.spatialClusterRadius <= 0) return false;
    if (config.temporalClusterWindow <= 0) return false;
    if (config.minClusterSize < 1) return false;
    if (config.maxTemporalWindow <= 0) return false;
    
    // Check weight values sum to reasonable range
    const totalWeight = config.confidenceWeight + config.spatialWeight + config.temporalWeight;
    if (totalWeight < 0.8 || totalWeight > 1.2) return false;
    
    // Check threshold ranges
    if (config.minTrackConfidence < 0 || config.minTrackConfidence > 1) return false;
    if (config.minMatchScore < 0 || config.minMatchScore > 1) return false;
    if (config.maxLatencyMs <= 0) return false;
    
    return true;
  } catch (error) {
    console.error('Invalid VRU tracking configuration:', error);
    return false;
  }
};

/**
 * Create default VRU tracking configuration with overrides
 */
export const createTrackingConfig = (overrides: Partial<VRUTrackingConfig> = {}): VRUTrackingConfig => {
  const config = { ...DEFAULT_VRU_TRACKING_CONFIG, ...overrides };
  
  if (!validateTrackingConfig(config)) {
    console.warn('Invalid tracking configuration, using defaults');
    return DEFAULT_VRU_TRACKING_CONFIG;
  }
  
  return config;
};

/**
 * Debug utility - log track information
 */
export const logTrackInfo = (track: VRUTrack): void => {
  console.log(`🎯 [VRU Track] ${track.trackId}`, {
    type: track.vruType,
    duration: `${track.duration.toFixed(2)}s`,
    frames: track.frameCount,
    confidence: `${(track.trackConfidence * 100).toFixed(1)}%`,
    timeRange: `${track.startTime.toFixed(2)}s - ${track.endTime.toFixed(2)}s`,
    annotations: track.annotations.length
  });
};

/**
 * Debug utility - log match information
 */
export const logMatchInfo = (match: VRUTrackMatch): void => {
  console.log(`🎯 [VRU Match] ${match.track.trackId}`, {
    quality: `${(match.matchQuality * 100).toFixed(1)}%`,
    latency: `${match.latencyMs.toFixed(1)}ms`,
    type: match.matchType,
    expected: `${match.expectedTime.toFixed(2)}s`,
    actual: `${match.actualTime.toFixed(2)}s`
  });
};