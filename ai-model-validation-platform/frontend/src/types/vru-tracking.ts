/**
 * VRU Tracking System Types
 * 
 * Comprehensive type definitions for VRU (Vulnerable Road User) tracking
 * in Hardware-in-the-Loop (HIL) testing systems. Supports persistent
 * VRU identity across video timelines with spatial-temporal clustering.
 */

import { GroundTruthAnnotation } from '../services/types';

export enum VRUType {
  PEDESTRIAN = 'pedestrian',
  CYCLIST = 'cyclist', 
  MOTORCYCLIST = 'motorcyclist',
  WHEELCHAIR_USER = 'wheelchair_user',
  SCOOTER_RIDER = 'scooter_rider',
  UNKNOWN = 'unknown'
}

export enum VRUTrackState {
  BIRTH = 'birth',        // First detection
  ACTIVE = 'active',      // Continuously tracked
  OCCLUDED = 'occluded',  // Temporarily hidden
  LOST = 'lost',          // Tracking failed
  DEATH = 'death'         // Left scene
}

export enum MatchType {
  EXACT = 'exact',               // Direct timestamp match
  INTERPOLATED = 'interpolated', // Between known positions
  PREDICTED = 'predicted',       // Extrapolated from trajectory
  MISSED = 'missed'              // No ground truth available
}

export interface VRUBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
}

export interface VRUPosition {
  x: number;        // Center X coordinate
  y: number;        // Center Y coordinate
  timestamp: number; // Time in seconds
  confidence: number; // Position confidence 0-1
  boundingBox: VRUBoundingBox;
}

export interface VRUVelocity {
  vx: number;       // Velocity X (pixels/second)
  vy: number;       // Velocity Y (pixels/second)  
  speed: number;    // Overall speed (pixels/second)
  direction: number; // Direction in radians
}

export interface VRUTrajectory {
  positions: VRUPosition[];
  velocities: VRUVelocity[];
  predictedPath?: VRUPosition[]; // Future predicted positions
  pathConfidence: number; // Trajectory reliability 0-1
}

export interface VRUTrack {
  // Identity
  trackId: string;              // Persistent unique identifier
  vruType: VRUType;            // Classification
  state: VRUTrackState;        // Current tracking state
  
  // Temporal bounds
  startTime: number;           // First detection timestamp
  endTime: number;             // Last detection timestamp  
  duration: number;            // Total track duration (seconds)
  
  // Spatial information
  trajectory: VRUTrajectory;   // Complete movement history
  currentPosition?: VRUPosition; // Most recent position
  
  // Source data
  annotations: GroundTruthAnnotation[]; // Original frame annotations
  frameCount: number;          // Number of frames with detections
  
  // Quality metrics
  trackConfidence: number;     // Overall track quality 0-1
  spatialConsistency: number;  // Position consistency score 0-1
  temporalConsistency: number; // Timing consistency score 0-1
  
  // Detection context
  averageConfidence: number;   // Mean detection confidence
  maxConfidence: number;       // Peak detection confidence
  minConfidence: number;       // Lowest detection confidence
  
  // Metadata
  createdAt: Date;
  updatedAt: Date;
  videoId: string;
  projectId: string;
}

export interface VRUTrackCluster {
  clusterId: string;
  tracks: VRUTrack[];
  centerPoint: VRUPosition;
  radius: number;              // Spatial clustering radius (pixels)
  timeWindow: number;          // Temporal clustering window (seconds)
  clusterConfidence: number;   // Clustering quality 0-1
}

export interface VRUMatchCandidate {
  track: VRUTrack;
  matchScore: number;          // Overall match quality 0-1
  temporalScore: number;       // Time alignment score 0-1
  spatialScore?: number;       // Spatial alignment score 0-1
  confidenceScore: number;     // Detection confidence factor 0-1
  distanceScore: number;       // Distance penalty 0-1
  timeDifference: number;      // Absolute time difference (ms)
  matchType: MatchType;
}

export interface VRUTrackMatch {
  // Match result
  track: VRUTrack;
  candidate: VRUMatchCandidate;
  matchQuality: number;        // Final match score 0-1
  matchType: MatchType;
  
  // Timing analysis
  expectedTime: number;        // Ground truth timestamp
  actualTime: number;          // HIL signal timestamp  
  latencyMs: number;          // Timing difference (ms)
  temporalDistance: number;    // Normalized time distance
  
  // Spatial analysis (if available)
  expectedPosition?: VRUPosition;
  actualPosition?: VRUPosition;
  spatialDistance?: number;    // Euclidean distance (pixels)
  
  // Quality metrics
  signalStrength: number;      // HIL signal quality 0-1
  noiseLevel: number;         // Signal noise factor 0-1
  confidence: number;         // Overall match confidence 0-1
  
  // Match metadata
  matchedAt: Date;
  matchAlgorithm: string;     // Algorithm used for matching
  processingTimeMs: number;   // Time to compute match
}

export interface VRUDetectionEvent {
  // Event identity
  id: string;
  eventType: 'vru_detected' | 'vru_matched' | 'vru_lost' | 'vru_false_positive';
  
  // Timing
  timestamp: number;          // Event time (video seconds)
  detectedAt: Date;          // System detection time
  frameNumber: number;       // Video frame number
  
  // VRU context
  trackId: string;           // Associated VRU track
  vruType: VRUType;         // VRU classification
  trackMatch?: VRUTrackMatch; // Match details (if applicable)
  
  // Detection quality
  confidence: number;        // Detection confidence 0-1
  signalQuality: number;     // HIL signal quality 0-1
  
  // HIL-specific data
  labJackChannel?: string;   // Hardware channel
  voltageLevel?: number;     // Signal voltage
  signalRiseTime?: number;   // Edge detection time (ms)
  
  // Outcome assessment
  outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection' | 'fail_false_positive';
  latencyMs?: number;        // Measured latency (ms)
  thresholdMs: number;       // Acceptable latency threshold
  
  // Spatial context (if available)
  position?: VRUPosition;
  boundingBox?: VRUBoundingBox;
  
  // Event metadata
  videoId: string;
  projectId: string;
  sessionId: string;
  processingTimeMs: number;
}

export interface VRUTrackingConfig {
  // Clustering parameters
  spatialClusterRadius: number;    // Max distance for spatial clustering (pixels)
  temporalClusterWindow: number;   // Max time gap for temporal clustering (seconds)
  minClusterSize: number;          // Minimum annotations per track
  
  // Matching parameters
  maxTemporalWindow: number;       // Maximum matching time window (seconds)
  temporalWindowScaling: number;   // Window size multiplier based on VRU speed
  confidenceWeight: number;        // Confidence factor in matching (0-1)
  spatialWeight: number;          // Spatial factor in matching (0-1)
  temporalWeight: number;         // Temporal factor in matching (0-1)
  
  // Quality thresholds
  minTrackConfidence: number;      // Minimum track quality to use
  minMatchScore: number;          // Minimum match score to accept
  maxLatencyMs: number;           // Maximum acceptable latency
  
  // Performance settings
  enableParallelProcessing: boolean;
  maxConcurrentTracks: number;
  cacheTrajectories: boolean;
  
  // Algorithm selection
  clusteringAlgorithm: 'spatial_temporal' | 'dbscan' | 'hierarchical';
  matchingAlgorithm: 'weighted_score' | 'hungarian' | 'greedy';
  trajectoryInterpolation: 'linear' | 'cubic_spline' | 'kalman';
}

export interface VRUTrackingMetrics {
  // Track statistics
  totalTracks: number;
  activeTracks: number;
  completedTracks: number;
  averageTrackDuration: number;
  
  // Match statistics  
  totalMatches: number;
  successfulMatches: number;
  failedMatches: number;
  matchSuccessRate: number;
  
  // Quality metrics
  averageMatchQuality: number;
  averageTrackConfidence: number;
  averageLatencyMs: number;
  
  // Performance metrics
  processingTimeMs: number;
  tracksPerSecond: number;
  matchesPerSecond: number;
  memoryUsageMB: number;
  
  // Error analysis
  falsePositives: number;
  falseNegatives: number;
  missedDetections: number;
  duplicateMatches: number;
}

export interface VRUTrackingResult {
  // Session context
  sessionId: string;
  videoId: string;
  projectId: string;
  
  // Results
  tracks: VRUTrack[];
  matches: VRUTrackMatch[];
  events: VRUDetectionEvent[];
  
  // Summary statistics
  metrics: VRUTrackingMetrics;
  
  // Configuration used
  config: VRUTrackingConfig;
  
  // Processing metadata
  processedAt: Date;
  processingDuration: number;
  algorithmsUsed: string[];
}

// Export utility types
export type VRUTrackId = string;
export type VRUMatchScore = number; // 0-1
export type VRULatency = number;    // milliseconds
export type VRUTimestamp = number;  // seconds

// Export default configuration
export const DEFAULT_VRU_TRACKING_CONFIG: VRUTrackingConfig = {
  // Clustering parameters
  spatialClusterRadius: 100,        // 100 pixels
  temporalClusterWindow: 2.0,       // 2 seconds
  minClusterSize: 3,               // At least 3 annotations
  
  // Matching parameters  
  maxTemporalWindow: 0.5,          // 500ms window
  temporalWindowScaling: 1.2,      // 20% scaling factor
  confidenceWeight: 0.3,           // 30% confidence factor
  spatialWeight: 0.2,              // 20% spatial factor (if available)
  temporalWeight: 0.5,             // 50% temporal factor
  
  // Quality thresholds
  minTrackConfidence: 0.6,         // 60% minimum track quality
  minMatchScore: 0.4,              // 40% minimum match score
  maxLatencyMs: 500,               // 500ms max acceptable latency
  
  // Performance settings
  enableParallelProcessing: true,
  maxConcurrentTracks: 10,
  cacheTrajectories: true,
  
  // Algorithm selection
  clusteringAlgorithm: 'spatial_temporal',
  matchingAlgorithm: 'weighted_score',
  trajectoryInterpolation: 'linear'
};