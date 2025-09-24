/**
 * Enhanced HIL Test Service
 * 
 * Integrates VRU Track Management and Temporal Matching to solve the
 * 0.0% pass rate problem with industry-standard HIL detection matching.
 * 
 * Key Features:
 * - Track-based ground truth preprocessing
 * - Real-time temporal matching with LabJack signals
 * - Multi-scale temporal windows (±50ms, ±200ms, ±500ms)
 * - Quality metrics and performance monitoring
 * - Sub-100ms processing latency
 */

import { VRUTrackManager, VRUTrack, VRUTrackConfig } from '../vru/VRUTrackManager';
import { TemporalMatcher, TemporalMatcherFactory, HILSignalEvent, TemporalMatch } from '../temporal/TemporalMatcher';
import { hilTestService, HILTestSession, HILDetectionEvent } from '../hilTestService';
import { 
  GroundTruthAnnotation, 
  DetectionOutcome, 
  SignalType, 
  Project,
  VideoFile 
} from '../types';

export interface EnhancedHILTestConfig {
  // VRU tracking configuration
  vruTracking: VRUTrackConfig;
  
  // Temporal matching mode
  matchingMode: 'automotive' | 'general' | 'research';
  
  // Performance settings
  maxLatencyMs: number;
  enableRealTimeMonitoring: boolean;
  qualityThreshold: number;
  
  // Signal processing
  signalBufferSize: number;
  duplicateDetectionWindowMs: number;
}

export interface EnhancedHILTestSession extends HILTestSession {
  // Enhanced session properties
  trackBasedMatching: boolean;
  vruTrackCount: number;
  temporalMatchingConfig: string;
  qualityMetrics: HILQualityMetrics;
  
  // Real-time statistics
  realtimeStats: {
    currentMatches: TemporalMatch[];
    averageMatchConfidence: number;
    processingLatencyMs: number;
    lastUpdateTimestamp: number;
  };
}

export interface HILQualityMetrics {
  // Temporal accuracy
  temporalAccuracy: {
    averageLatencyMs: number;
    latencyStandardDeviation: number;
    sub100msPercentage: number;
    sub50msPercentage: number;
    sub25msPercentage: number;
  };
  
  // Match reliability
  matchReliability: {
    totalMatches: number;
    successfulMatches: number;
    missedDetections: number;
    falsePositives: number;
    matchSuccessRate: number;
  };
  
  // Track quality
  trackQuality: {
    totalTracks: number;
    tracksWithMatches: number;
    averageTrackConfidence: number;
    trackConsistencyScore: number;
  };
  
  // Performance metrics
  performance: {
    averageProcessingTimeMs: number;
    maxProcessingTimeMs: number;
    throughputMatchesPerSecond: number;
    cacheHitRate: number;
  };
}

export interface EnhancedHILResult {
  match: TemporalMatch | null;
  outcome: DetectionOutcome;
  qualityScore: number;
  processingTimeMs: number;
  trackInfo?: {
    trackId: string;
    trackConfidence: number;
    frameCount: number;
  };
}

/**
 * Enhanced HIL Test Service with track-based matching
 */
export class EnhancedHILTestService {
  private vruTrackManager: VRUTrackManager;
  private temporalMatcher: TemporalMatcher;
  private currentTracks: Map<string, VRUTrack> = new Map();
  private activeSession: EnhancedHILTestSession | null = null;
  private realtimeMatches: TemporalMatch[] = [];
  private qualityMetrics: HILQualityMetrics | null = null;
  
  constructor(private config: EnhancedHILTestConfig) {
    // Initialize VRU track manager
    this.vruTrackManager = new VRUTrackManager(config.vruTracking);
    
    // Initialize temporal matcher based on mode
    this.temporalMatcher = this.createTemporalMatcher(config.matchingMode);
  }
  
  /**
   * Create temporal matcher based on configuration mode
   */
  private createTemporalMatcher(mode: 'automotive' | 'general' | 'research'): TemporalMatcher {
    switch (mode) {
      case 'automotive':
        return TemporalMatcherFactory.createAutomotiveMatcher();
      case 'general':
        return TemporalMatcherFactory.createGeneralMatcher();
      case 'research':
        return TemporalMatcherFactory.createResearchMatcher();
      default:
        return TemporalMatcherFactory.createGeneralMatcher();
    }
  }
  
  /**
   * Initialize enhanced HIL test session with track-based ground truth
   * This is the key method that preprocesses annotations into tracks
   */
  async initializeEnhancedSession(
    projectId: number,
    maxLatencyMs: number,
    labjackConnected: boolean
  ): Promise<EnhancedHILTestSession> {
    
    console.log(`Initializing enhanced HIL session for project ${projectId}`);
    const startTime = performance.now();
    
    try {
      // Step 1: Load ground truth annotations
      const annotations = await this.loadGroundTruthAnnotations(projectId);
      console.log(`Loaded ${annotations.length} ground truth annotations`);
      
      // Step 2: Build VRU tracks from frame annotations
      const tracks = await this.vruTrackManager.buildTracksFromAnnotations(
        String(projectId), 
        annotations
      );
      
      this.currentTracks = tracks;
      console.log(`Created ${tracks.size} VRU tracks from annotations`);
      
      // Step 3: Create base HIL test session
      const baseSession = await hilTestService.createTestSession({
        projectId,
        maxLatencyMs,
        labjackConnected
      });
      
      // Step 4: Create enhanced session with track information
      const enhancedSession: EnhancedHILTestSession = {
        ...baseSession,
        trackBasedMatching: true,
        vruTrackCount: tracks.size,
        temporalMatchingConfig: this.config.matchingMode,
        qualityMetrics: this.initializeQualityMetrics(),
        realtimeStats: {
          currentMatches: [],
          averageMatchConfidence: 0,
          processingLatencyMs: 0,
          lastUpdateTimestamp: Date.now()
        }
      };
      
      this.activeSession = enhancedSession;
      
      const initTime = performance.now() - startTime;
      console.log(`Enhanced HIL session initialized in ${initTime.toFixed(2)}ms`);
      
      return enhancedSession;
      
    } catch (error) {
      console.error('Failed to initialize enhanced HIL session:', error);
      throw new Error(`Enhanced HIL session initialization failed: ${error}`);
    }
  }
  
  /**
   * Process incoming LabJack signal with track-based matching
   * Core method that implements the enhanced matching logic
   */
  async processHardwareSignal(
    rawSignal: any,
    sessionId: number
  ): Promise<EnhancedHILResult> {
    
    const startTime = performance.now();
    
    try {
      // Step 1: Convert raw LabJack signal to HIL signal event
      const signalEvent = this.convertToHILSignalEvent(rawSignal);
      if (!signalEvent) {
        return {
          match: null,
          outcome: DetectionOutcome.FAIL_SIGNAL_INVALID,
          qualityScore: 0,
          processingTimeMs: performance.now() - startTime
        };
      }
      
      // Step 2: Get candidate tracks within temporal window
      const candidateTracks = this.vruTrackManager.getTracksAtTimestamp(
        signalEvent.timestampMs,
        500 // 500ms window for candidate selection
      );
      
      console.log(`Found ${candidateTracks.length} candidate tracks for timestamp ${signalEvent.timestampMs}`);
      
      // Step 3: Perform temporal matching
      const match = await this.temporalMatcher.findBestMatch(
        signalEvent,
        candidateTracks
      );
      
      // Step 4: Calculate detection outcome
      const outcome = this.temporalMatcher.calculateDetectionOutcome(
        match, 
        this.config.maxLatencyMs
      );
      
      // Step 5: Calculate quality score
      const qualityScore = match ? match.confidence : 0;
      
      const processingTime = performance.now() - startTime;
      
      // Step 6: Update track with match result if successful
      if (match && outcome === DetectionOutcome.PASS) {
        const hilSignalMatch = {
          matchId: `match_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`,
          trackId: match.trackId,
          expectedTimestampMs: match.matchedFrame.timestampMs,
          actualSignalTimestampMs: signalEvent.timestampMs,
          latencyMs: match.temporalDistance,
          matchConfidence: match.confidence,
          outcome
        };
        
        this.vruTrackManager.updateTrackWithSignalMatch(match.trackId, hilSignalMatch);
      }
      
      // Step 7: Update real-time statistics
      if (match) {
        this.realtimeMatches.push(match);
        // Keep only recent 100 matches for performance
        if (this.realtimeMatches.length > 100) {
          this.realtimeMatches.shift();
        }
      }
      
      // Step 8: Update session statistics
      await this.updateSessionStatistics(match, outcome, processingTime);
      
      const result: EnhancedHILResult = {
        match,
        outcome,
        qualityScore,
        processingTimeMs: processingTime,
        trackInfo: match ? {
          trackId: match.trackId,
          trackConfidence: candidateTracks.find(t => t.trackId === match.trackId)?.confidence || 0,
          frameCount: candidateTracks.find(t => t.trackId === match.trackId)?.frameAnnotations.size || 0
        } : undefined
      };
      
      console.log(`Processed HIL signal in ${processingTime.toFixed(2)}ms - Outcome: ${outcome}`);
      
      return result;
      
    } catch (error) {
      console.error('Error processing hardware signal:', error);
      return {
        match: null,
        outcome: DetectionOutcome.FAIL_PROCESSING_ERROR,
        qualityScore: 0,
        processingTimeMs: performance.now() - startTime
      };
    }
  }
  
  /**
   * Convert raw LabJack signal to standardized HIL signal event
   */
  private convertToHILSignalEvent(rawSignal: any): HILSignalEvent | null {
    try {
      // Extract timestamp with high precision
      const timestampMs = rawSignal.timestamp_ms || rawSignal.timestampMicros / 1000 || Date.now();
      
      // Validate signal strength
      const signalValue = rawSignal.value || 0;
      const signalStrength = this.calculateSignalStrength(rawSignal);
      
      if (signalStrength < 0.3) { // Too weak signal
        return null;
      }
      
      return {
        id: `signal_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`,
        timestampMs,
        signalType: rawSignal.signal_type || SignalType.TTL,
        signalValue,
        signalStrength,
        channelId: rawSignal.channel_id || 'default',
        rawData: rawSignal
      };
      
    } catch (error) {
      console.error('Error converting raw signal:', error);
      return null;
    }
  }
  
  /**
   * Calculate signal strength/quality metric
   */
  private calculateSignalStrength(rawSignal: any): number {
    const signalValue = Math.abs(rawSignal.value || 0);
    const noiseLevel = rawSignal.noise_level || 0.1;
    const baseline = rawSignal.baseline || 0;
    
    const signalMagnitude = Math.abs(signalValue - baseline);
    const signalToNoise = signalMagnitude / Math.max(noiseLevel, 0.01);
    
    // Normalize to [0-1] range
    return Math.min(1.0, signalToNoise / 10.0);
  }
  
  /**
   * Load ground truth annotations for project
   */
  private async loadGroundTruthAnnotations(projectId: number): Promise<GroundTruthAnnotation[]> {
    try {
      // This would typically call the existing annotation API
      // For now, we'll simulate loading annotations
      const response = await fetch(`/api/v1/projects/${projectId}/annotations`);
      if (!response.ok) {
        throw new Error(`Failed to load annotations: ${response.statusText}`);
      }
      
      const annotations = await response.json();
      
      // Filter for VRU annotations only
      return annotations.filter((ann: any) => 
        ann.vruType && 
        ann.bbox && 
        typeof ann.frameNumber === 'number'
      );
      
    } catch (error) {
      console.error('Error loading ground truth annotations:', error);
      return [];
    }
  }
  
  /**
   * Update session statistics with new match result
   */
  private async updateSessionStatistics(
    match: TemporalMatch | null,
    outcome: DetectionOutcome,
    processingTimeMs: number
  ): Promise<void> {
    
    if (!this.activeSession) return;
    
    // Update session counters
    this.activeSession.totalEvents++;
    
    if (outcome === DetectionOutcome.PASS) {
      this.activeSession.passedEvents++;
    } else {
      this.activeSession.failedEvents++;
      if (outcome === DetectionOutcome.FAIL_MISSED_DETECTION) {
        this.activeSession.missedDetections++;
      }
    }
    
    // Update average latency
    if (match) {
      const totalLatency = this.activeSession.averageLatencyMs * (this.activeSession.totalEvents - 1);
      this.activeSession.averageLatencyMs = (totalLatency + match.temporalDistance) / this.activeSession.totalEvents;
    }
    
    // Update real-time statistics
    this.activeSession.realtimeStats.lastUpdateTimestamp = Date.now();
    this.activeSession.realtimeStats.processingLatencyMs = processingTimeMs;
    
    if (this.realtimeMatches.length > 0) {
      this.activeSession.realtimeStats.averageMatchConfidence = 
        this.realtimeMatches.reduce((sum, m) => sum + m.confidence, 0) / this.realtimeMatches.length;
      this.activeSession.realtimeStats.currentMatches = [...this.realtimeMatches];
    }
  }
  
  /**
   * Generate comprehensive quality metrics for session
   */
  async generateQualityMetrics(sessionId: number): Promise<HILQualityMetrics> {
    
    const tracks = Array.from(this.currentTracks.values());
    const matchedTracks = tracks.filter(track => track.matchSuccess);
    const allMatches = tracks.flatMap(track => track.signalMatches);
    
    // Temporal accuracy metrics
    const latencies = allMatches.map(match => match.latencyMs);
    const averageLatency = latencies.length > 0 
      ? latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length 
      : 0;
    
    const latencyStdDev = latencies.length > 0
      ? Math.sqrt(latencies.reduce((sum, lat) => sum + Math.pow(lat - averageLatency, 2), 0) / latencies.length)
      : 0;
    
    // Match reliability metrics
    const missedDetections = this.activeSession?.missedDetections || 0;
    const successfulMatches = allMatches.filter(match => match.outcome === DetectionOutcome.PASS).length;
    
    // Performance metrics from temporal matcher
    const performanceMetrics = this.temporalMatcher.getPerformanceMetrics();
    
    const qualityMetrics: HILQualityMetrics = {
      temporalAccuracy: {
        averageLatencyMs: averageLatency,
        latencyStandardDeviation: latencyStdDev,
        sub100msPercentage: this.calculatePercentage(latencies, lat => lat <= 100),
        sub50msPercentage: this.calculatePercentage(latencies, lat => lat <= 50),
        sub25msPercentage: this.calculatePercentage(latencies, lat => lat <= 25)
      },
      
      matchReliability: {
        totalMatches: allMatches.length,
        successfulMatches,
        missedDetections,
        falsePositives: allMatches.length - successfulMatches,
        matchSuccessRate: allMatches.length > 0 ? (successfulMatches / allMatches.length) * 100 : 0
      },
      
      trackQuality: {
        totalTracks: tracks.length,
        tracksWithMatches: matchedTracks.length,
        averageTrackConfidence: tracks.length > 0 
          ? tracks.reduce((sum, track) => sum + track.confidence, 0) / tracks.length 
          : 0,
        trackConsistencyScore: this.calculateTrackConsistencyScore(tracks)
      },
      
      performance: {
        averageProcessingTimeMs: performanceMetrics.averageMatchTimeMs,
        maxProcessingTimeMs: performanceMetrics.maxMatchTimeMs,
        throughputMatchesPerSecond: performanceMetrics.throughputMatchesPerSecond,
        cacheHitRate: performanceMetrics.cacheHitRate
      }
    };
    
    this.qualityMetrics = qualityMetrics;
    return qualityMetrics;
  }
  
  /**
   * Calculate percentage of values meeting condition
   */
  private calculatePercentage<T>(values: T[], condition: (value: T) => boolean): number {
    if (values.length === 0) return 0;
    const matchingCount = values.filter(condition).length;
    return (matchingCount / values.length) * 100;
  }
  
  /**
   * Calculate track consistency score
   */
  private calculateTrackConsistencyScore(tracks: VRUTrack[]): number {
    if (tracks.length === 0) return 0;
    
    const consistencyScores = tracks.map(track => track.directionConsistency);
    return consistencyScores.reduce((sum, score) => sum + score, 0) / tracks.length;
  }
  
  /**
   * Initialize quality metrics structure
   */
  private initializeQualityMetrics(): HILQualityMetrics {
    return {
      temporalAccuracy: {
        averageLatencyMs: 0,
        latencyStandardDeviation: 0,
        sub100msPercentage: 0,
        sub50msPercentage: 0,
        sub25msPercentage: 0
      },
      matchReliability: {
        totalMatches: 0,
        successfulMatches: 0,
        missedDetections: 0,
        falsePositives: 0,
        matchSuccessRate: 0
      },
      trackQuality: {
        totalTracks: 0,
        tracksWithMatches: 0,
        averageTrackConfidence: 0,
        trackConsistencyScore: 0
      },
      performance: {
        averageProcessingTimeMs: 0,
        maxProcessingTimeMs: 0,
        throughputMatchesPerSecond: 0,
        cacheHitRate: 0
      }
    };
  }
  
  /**
   * Get current VRU tracks
   */
  getCurrentTracks(): Map<string, VRUTrack> {
    return new Map(this.currentTracks);
  }
  
  /**
   * Get track statistics
   */
  getTrackStatistics() {
    return this.vruTrackManager.getTrackStatistics();
  }
  
  /**
   * Get real-time matches
   */
  getRealtimeMatches(): TemporalMatch[] {
    return [...this.realtimeMatches];
  }
  
  /**
   * Get current quality metrics
   */
  getCurrentQualityMetrics(): HILQualityMetrics | null {
    return this.qualityMetrics;
  }
  
  /**
   * Reset session state
   */
  resetSession(): void {
    this.currentTracks.clear();
    this.realtimeMatches = [];
    this.activeSession = null;
    this.qualityMetrics = null;
    this.temporalMatcher.reset();
  }
}

/**
 * Factory for creating enhanced HIL test service with different configurations
 */
export class EnhancedHILTestServiceFactory {
  
  /**
   * Create service optimized for automotive safety testing
   */
  static createAutomotiveService(): EnhancedHILTestService {
    return new EnhancedHILTestService({
      vruTracking: {
        maxFrameGap: 5,           // Tight frame gap for high precision
        minSpatialOverlap: 0.5,   // 50% minimum IoU
        minTrackLength: 3,        // Minimum 3 frames per track
        kalmanFilterQ: 0.01,      // Low process noise
        kalmanFilterR: 0.1        // Measurement noise
      },
      matchingMode: 'automotive',
      maxLatencyMs: 50,           // 50ms max latency for safety
      enableRealTimeMonitoring: true,
      qualityThreshold: 0.8,
      signalBufferSize: 100,
      duplicateDetectionWindowMs: 10
    });
  }
  
  /**
   * Create service for general HIL testing
   */
  static createGeneralService(): EnhancedHILTestService {
    return new EnhancedHILTestService({
      vruTracking: {
        maxFrameGap: 10,          // Moderate frame gap
        minSpatialOverlap: 0.3,   // 30% minimum IoU
        minTrackLength: 2,        // Minimum 2 frames per track
        kalmanFilterQ: 0.05,      // Moderate process noise
        kalmanFilterR: 0.2        // Moderate measurement noise
      },
      matchingMode: 'general',
      maxLatencyMs: 100,          // 100ms max latency
      enableRealTimeMonitoring: true,
      qualityThreshold: 0.6,
      signalBufferSize: 200,
      duplicateDetectionWindowMs: 20
    });
  }
  
  /**
   * Create service for research and development
   */
  static createResearchService(): EnhancedHILTestService {
    return new EnhancedHILTestService({
      vruTracking: {
        maxFrameGap: 20,          // Large frame gap for flexibility
        minSpatialOverlap: 0.2,   // 20% minimum IoU
        minTrackLength: 1,        // Single frame tracks allowed
        kalmanFilterQ: 0.1,       // Higher process noise
        kalmanFilterR: 0.3        // Higher measurement noise
      },
      matchingMode: 'research',
      maxLatencyMs: 500,          // 500ms max latency
      enableRealTimeMonitoring: false,
      qualityThreshold: 0.4,
      signalBufferSize: 500,
      duplicateDetectionWindowMs: 50
    });
  }
}

// Export singleton instance for general use
export const enhancedHILTestService = EnhancedHILTestServiceFactory.createGeneralService();