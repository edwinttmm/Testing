/**
 * Temporal Matching Engine for HIL Detection
 * 
 * Implements multi-scale temporal windows and adaptive matching strategies
 * to correlate LabJack voltage signals with VRU ground truth tracks.
 * 
 * Key Features:
 * - Multi-scale temporal windows (±50ms, ±200ms, ±500ms)
 * - Adaptive window sizing based on VRU speed and confidence
 * - Confidence-weighted matching scores
 * - Real-time performance optimization
 */

import { VRUTrack, FrameAnnotation } from '../vru/VRUTrackManager';
import { DetectionOutcome, SignalType } from '../types';

export interface HILSignalEvent {
  id: string;
  timestampMs: number;            // High-precision signal timestamp
  signalType: SignalType;         // TTL, GPIO, ANALOG
  signalValue: number;            // Voltage or digital value  
  signalStrength: number;         // Signal quality [0-1]
  channelId: string;              // LabJack channel identifier
  rawData: any;                   // Original LabJack data
}

export interface TemporalMatchingConfig {
  // Primary matching windows
  immediateWindowMs: number;      // ±50ms - High precision
  normalWindowMs: number;         // ±200ms - Standard matching  
  extendedWindowMs: number;       // ±500ms - Edge cases
  
  // Adaptive parameters
  speedAdaptationFactor: number;  // Expand windows for high-speed VRUs
  confidenceThreshold: number;    // Confidence-based window tightening
  
  // Quality thresholds
  minMatchConfidence: number;     // Minimum confidence for valid match
  maxLatencyMs: number;           // Maximum acceptable latency
  
  // Performance settings
  maxConcurrentMatches: number;   // Parallel processing limit
  cacheSize: number;              // LRU cache size
}

export interface TemporalMatch {
  trackId: string;
  signalEvent: HILSignalEvent;
  matchedFrame: FrameAnnotation;
  temporalDistance: number;       // ms between signal and annotation
  confidence: number;             // Match confidence [0-1]
  windowMs: number;               // Window size used for match
  matchQuality: MatchQuality;     // Detailed quality assessment
}

export interface MatchQuality {
  temporalQuality: number;        // How close in time [0-1]
  trackQuality: number;          // Quality of matched track [0-1] 
  movementConsistency: number;    // Motion pattern consistency [0-1]
  signalQuality: number;         // Signal strength/clarity [0-1]
  compositeScore: number;        // Overall match quality [0-1]
}

/**
 * Main Temporal Matching Engine
 */
export class TemporalMatcher {
  private matchCache: Map<string, TemporalMatch> = new Map();
  private performanceMetrics: PerformanceMetrics;
  
  constructor(private config: TemporalMatchingConfig) {
    this.performanceMetrics = new PerformanceMetrics();
  }
  
  /**
   * Find best VRU track match for HIL signal
   * Core method that implements the temporal matching strategy
   */
  async findBestMatch(
    signalEvent: HILSignalEvent,
    candidateTracks: VRUTrack[]
  ): Promise<TemporalMatch | null> {
    
    const startTime = performance.now();
    
    try {
      // Check cache first for performance
      const cacheKey = this.generateCacheKey(signalEvent);
      const cachedMatch = this.matchCache.get(cacheKey);
      if (cachedMatch && this.isCacheValid(cachedMatch, signalEvent)) {
        this.performanceMetrics.recordCacheHit(performance.now() - startTime);
        return cachedMatch;
      }
      
      const matches: TemporalMatch[] = [];
      
      // Try different temporal windows in order of precision
      for (const windowMs of [
        this.config.immediateWindowMs,
        this.config.normalWindowMs, 
        this.config.extendedWindowMs
      ]) {
        
        const windowMatches = await this.matchWithinWindow(
          signalEvent, 
          candidateTracks, 
          windowMs
        );
        
        matches.push(...windowMatches);
        
        // Stop if we found high-confidence matches in tight window
        if (windowMatches.length > 0 && windowMs <= this.config.normalWindowMs) {
          const highConfidenceMatch = windowMatches.find(m => 
            m.confidence >= this.config.minMatchConfidence
          );
          if (highConfidenceMatch) break;
        }
      }
      
      // Return best match based on composite scoring
      const bestMatch = this.selectBestMatch(matches);
      
      // Cache successful matches
      if (bestMatch) {
        this.matchCache.set(cacheKey, bestMatch);
        
        // Limit cache size
        if (this.matchCache.size > this.config.cacheSize) {
          const oldestKey = this.matchCache.keys().next().value;
          this.matchCache.delete(oldestKey);
        }
      }
      
      this.performanceMetrics.recordMatch(performance.now() - startTime, bestMatch !== null);
      return bestMatch;
      
    } catch (error) {
      this.performanceMetrics.recordError(performance.now() - startTime, error);
      console.error('Temporal matching error:', error);
      return null;
    }
  }
  
  /**
   * Match signal within specific temporal window
   */
  private async matchWithinWindow(
    signalEvent: HILSignalEvent,
    tracks: VRUTrack[],
    windowMs: number
  ): Promise<TemporalMatch[]> {
    
    const matches: TemporalMatch[] = [];
    const signalTimestamp = signalEvent.timestampMs;
    
    for (const track of tracks) {
      // Find frame annotations within temporal window
      const candidateFrames = this.getFramesInWindow(
        track, 
        signalTimestamp, 
        windowMs
      );
      
      for (const frameData of candidateFrames) {
        const temporalDistance = Math.abs(signalTimestamp - frameData.timestampMs);
        const confidence = this.calculateMatchConfidence(
          signalEvent,
          track,
          frameData,
          temporalDistance,
          windowMs
        );
        
        if (confidence >= this.config.minMatchConfidence) {
          const matchQuality = this.assessMatchQuality(
            signalEvent,
            track,
            frameData,
            temporalDistance,
            windowMs
          );
          
          matches.push({
            trackId: track.trackId,
            signalEvent,
            matchedFrame: frameData,
            temporalDistance,
            confidence,
            windowMs,
            matchQuality
          });
        }
      }
    }
    
    return matches;
  }
  
  /**
   * Get frame annotations within temporal window
   */
  private getFramesInWindow(
    track: VRUTrack,
    timestampMs: number,
    windowMs: number
  ): FrameAnnotation[] {
    
    const startTime = timestampMs - windowMs;
    const endTime = timestampMs + windowMs;
    const candidates: FrameAnnotation[] = [];
    
    track.frameAnnotations.forEach((annotation, frameNum) => {
      if (annotation.timestampMs >= startTime && annotation.timestampMs <= endTime) {
        candidates.push(annotation);
      }
    });
    
    return candidates;
  }
  
  /**
   * Calculate match confidence based on multiple factors
   */
  private calculateMatchConfidence(
    signalEvent: HILSignalEvent,
    track: VRUTrack,
    frameData: FrameAnnotation,
    temporalDistance: number,
    windowMs: number
  ): number {
    
    // Temporal proximity score (closer = higher confidence)
    const temporalScore = 1.0 - (temporalDistance / windowMs);
    
    // Track quality score
    const trackQualityScore = track.confidence;
    
    // Frame annotation quality
    const frameQualityScore = frameData.detectionConfidence;
    
    // Movement consistency (if track has trajectory data)
    const movementConsistency = this.calculateMovementConsistency(track, frameData);
    
    // Signal strength/quality
    const signalQuality = signalEvent.signalStrength || 1.0;
    
    // Adaptive weighting based on VRU speed
    const adaptiveWeights = this.calculateAdaptiveWeights(track, temporalDistance);
    
    // Composite confidence score
    return (
      temporalScore * adaptiveWeights.temporal +
      trackQualityScore * adaptiveWeights.trackQuality +
      frameQualityScore * adaptiveWeights.frameQuality +
      movementConsistency * adaptiveWeights.movement +
      signalQuality * adaptiveWeights.signal
    );
  }
  
  /**
   * Calculate adaptive weights based on track characteristics
   */
  private calculateAdaptiveWeights(track: VRUTrack, temporalDistance: number) {
    // Base weights
    const baseWeights = {
      temporal: 0.35,
      trackQuality: 0.25,
      frameQuality: 0.20,
      movement: 0.15,
      signal: 0.05
    };
    
    // Adjust weights based on track speed
    if (track.averageSpeed > 100) { // High-speed VRU
      baseWeights.temporal = 0.25;  // Less emphasis on exact timing
      baseWeights.movement = 0.25;  // More emphasis on movement consistency
    }
    
    // Adjust weights based on temporal distance
    if (temporalDistance < 50) { // Very close in time
      baseWeights.temporal = 0.45; // Higher emphasis on temporal precision
    }
    
    return baseWeights;
  }
  
  /**
   * Calculate movement consistency score
   */
  private calculateMovementConsistency(track: VRUTrack, frameData: FrameAnnotation): number {
    if (track.trajectory.velocities.length === 0) return 0.5; // Neutral for static objects
    
    // Use direction consistency as movement score
    return track.directionConsistency;
  }
  
  /**
   * Assess comprehensive match quality
   */
  private assessMatchQuality(
    signalEvent: HILSignalEvent,
    track: VRUTrack,
    frameData: FrameAnnotation,
    temporalDistance: number,
    windowMs: number
  ): MatchQuality {
    
    const temporalQuality = 1.0 - (temporalDistance / windowMs);
    const trackQuality = track.confidence;
    const movementConsistency = this.calculateMovementConsistency(track, frameData);
    const signalQuality = signalEvent.signalStrength;
    
    const compositeScore = (
      temporalQuality * 0.4 +
      trackQuality * 0.3 +
      movementConsistency * 0.2 +
      signalQuality * 0.1
    );
    
    return {
      temporalQuality,
      trackQuality,
      movementConsistency,
      signalQuality,
      compositeScore
    };
  }
  
  /**
   * Select best match from candidates using composite scoring
   */
  private selectBestMatch(matches: TemporalMatch[]): TemporalMatch | null {
    if (matches.length === 0) return null;
    
    // Sort by confidence (descending) and temporal distance (ascending)
    matches.sort((a, b) => {
      const confidenceDiff = b.confidence - a.confidence;
      if (Math.abs(confidenceDiff) > 0.1) return confidenceDiff;
      return a.temporalDistance - b.temporalDistance;
    });
    
    const bestMatch = matches[0];
    
    // Validate best match meets minimum requirements
    if (bestMatch.confidence >= this.config.minMatchConfidence && 
        bestMatch.temporalDistance <= this.config.maxLatencyMs) {
      return bestMatch;
    }
    
    return null;
  }
  
  /**
   * Generate cache key for performance optimization
   */
  private generateCacheKey(signalEvent: HILSignalEvent): string {
    // Round timestamp to 10ms for cache efficiency
    const roundedTimestamp = Math.round(signalEvent.timestampMs / 10) * 10;
    return `${roundedTimestamp}_${signalEvent.channelId}_${signalEvent.signalType}`;
  }
  
  /**
   * Check if cached match is still valid
   */
  private isCacheValid(cachedMatch: TemporalMatch, signalEvent: HILSignalEvent): boolean {
    const timeDiff = Math.abs(cachedMatch.signalEvent.timestampMs - signalEvent.timestampMs);
    return timeDiff <= 100; // Cache valid for 100ms
  }
  
  /**
   * Calculate detection outcome based on match result
   */
  calculateDetectionOutcome(match: TemporalMatch | null, maxLatencyMs: number): DetectionOutcome {
    if (!match) {
      return DetectionOutcome.FAIL_MISSED_DETECTION;
    }
    
    if (match.temporalDistance <= maxLatencyMs) {
      return DetectionOutcome.PASS;
    } else {
      return DetectionOutcome.FAIL_HIGH_LATENCY;
    }
  }
  
  /**
   * Get performance metrics
   */
  getPerformanceMetrics() {
    return this.performanceMetrics.getMetrics();
  }
  
  /**
   * Clear cache and reset metrics
   */
  reset(): void {
    this.matchCache.clear();
    this.performanceMetrics.reset();
  }
}

/**
 * Performance metrics tracking
 */
class PerformanceMetrics {
  private matchTimes: number[] = [];
  private cacheHits = 0;
  private errors = 0;
  private successfulMatches = 0;
  private totalAttempts = 0;
  
  recordMatch(timeMs: number, success: boolean): void {
    this.matchTimes.push(timeMs);
    this.totalAttempts++;
    if (success) this.successfulMatches++;
    
    // Keep only recent 1000 measurements
    if (this.matchTimes.length > 1000) {
      this.matchTimes.shift();
    }
  }
  
  recordCacheHit(timeMs: number): void {
    this.cacheHits++;
    this.matchTimes.push(timeMs);
  }
  
  recordError(timeMs: number, error: any): void {
    this.errors++;
    this.totalAttempts++;
    console.error('Temporal matching error:', error);
  }
  
  getMetrics() {
    const avgTime = this.matchTimes.length > 0 
      ? this.matchTimes.reduce((sum, time) => sum + time, 0) / this.matchTimes.length
      : 0;
    
    const maxTime = this.matchTimes.length > 0 ? Math.max(...this.matchTimes) : 0;
    const minTime = this.matchTimes.length > 0 ? Math.min(...this.matchTimes) : 0;
    
    return {
      averageMatchTimeMs: avgTime,
      maxMatchTimeMs: maxTime,
      minMatchTimeMs: minTime,
      cacheHitRate: this.totalAttempts > 0 ? this.cacheHits / this.totalAttempts : 0,
      errorRate: this.totalAttempts > 0 ? this.errors / this.totalAttempts : 0,
      successRate: this.totalAttempts > 0 ? this.successfulMatches / this.totalAttempts : 0,
      totalAttempts: this.totalAttempts,
      throughputMatchesPerSecond: avgTime > 0 ? 1000 / avgTime : 0
    };
  }
  
  reset(): void {
    this.matchTimes = [];
    this.cacheHits = 0;
    this.errors = 0;
    this.successfulMatches = 0;
    this.totalAttempts = 0;
  }
}

/**
 * Factory for creating temporal matcher with different configurations
 */
export class TemporalMatcherFactory {
  
  /**
   * Create matcher optimized for automotive safety (tight windows, high precision)
   */
  static createAutomotiveMatcher(): TemporalMatcher {
    return new TemporalMatcher({
      immediateWindowMs: 25,        // ±25ms for safety-critical
      normalWindowMs: 100,          // ±100ms standard  
      extendedWindowMs: 250,        // ±250ms edge cases
      speedAdaptationFactor: 1.5,
      confidenceThreshold: 0.8,
      minMatchConfidence: 0.7,
      maxLatencyMs: 100,
      maxConcurrentMatches: 10,
      cacheSize: 100
    });
  }
  
  /**
   * Create matcher optimized for general HIL testing (balanced performance)
   */
  static createGeneralMatcher(): TemporalMatcher {
    return new TemporalMatcher({
      immediateWindowMs: 50,        // ±50ms immediate
      normalWindowMs: 200,          // ±200ms standard
      extendedWindowMs: 500,        // ±500ms extended
      speedAdaptationFactor: 2.0,
      confidenceThreshold: 0.6,
      minMatchConfidence: 0.5,
      maxLatencyMs: 200,
      maxConcurrentMatches: 15,
      cacheSize: 200
    });
  }
  
  /**
   * Create matcher optimized for research/development (loose tolerances)
   */
  static createResearchMatcher(): TemporalMatcher {
    return new TemporalMatcher({
      immediateWindowMs: 100,       // ±100ms immediate
      normalWindowMs: 500,          // ±500ms standard
      extendedWindowMs: 1000,       // ±1000ms extended
      speedAdaptationFactor: 3.0,
      confidenceThreshold: 0.4,
      minMatchConfidence: 0.3,
      maxLatencyMs: 500,
      maxConcurrentMatches: 20,
      cacheSize: 500
    });
  }
}