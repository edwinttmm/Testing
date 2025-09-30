/**
 * Temporal Matcher
 * 
 * Advanced temporal matching engine for HIL testing. Handles multi-scale
 * temporal windows, confidence-weighted scoring, and performance optimization
 * for matching HIL signals to VRU tracks.
 */

import {
  VRUTrack,
  VRUTrackMatch,
  VRUMatchCandidate,
  VRUDetectionEvent,
  MatchType,
  VRUTrackingConfig,
  VRUTrackingMetrics,
  DEFAULT_VRU_TRACKING_CONFIG
} from '../types/vru-tracking';

import {
  createMatchCandidate,
  filterPotentialTracks,
  sortMatchCandidates,
  isMatchValid,
  calculateLatency,
  determineEventOutcome,
  createDetectionEvent,
  logMatchInfo
} from '../utils/vruTrackingUtils';

/**
 * Temporal matching result with quality assessment
 */
export interface TemporalMatchResult {
  match: VRUTrackMatch | null;
  candidates: VRUMatchCandidate[];
  processingTimeMs: number;
  matchFound: boolean;
  matchQuality: number;
  algorithmUsed: string;
}

/**
 * Multi-scale temporal window configuration
 */
export interface TemporalWindowConfig {
  immediate: number;    // ±50ms - exact timing
  normal: number;       // ±200ms - typical latency
  extended: number;     // ±500ms - high latency scenarios
  adaptive: boolean;    // Enable adaptive window sizing
  scalingFactor: number; // Window scaling based on VRU speed
}

/**
 * Performance optimization settings
 */
export interface PerformanceConfig {
  enableCaching: boolean;
  maxCacheSize: number;
  enableParallel: boolean;
  batchSize: number;
  enablePrediction: boolean;
  predictionWindow: number; // seconds
}

/**
 * Temporal Matcher - Core matching engine
 */
export class TemporalMatcher {
  private config: VRUTrackingConfig;
  private windowConfig: TemporalWindowConfig;
  private perfConfig: PerformanceConfig;
  private matchCache = new Map<string, VRUTrackMatch>();
  private candidateCache = new Map<string, VRUMatchCandidate[]>();
  private metrics: Partial<VRUTrackingMetrics> = {};

  constructor(
    config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG,
    windowConfig?: Partial<TemporalWindowConfig>,
    perfConfig?: Partial<PerformanceConfig>
  ) {
    this.config = config;
    
    this.windowConfig = {
      immediate: 0.05,      // 50ms
      normal: 0.2,          // 200ms  
      extended: 0.5,        // 500ms
      adaptive: true,
      scalingFactor: 1.5,
      ...windowConfig
    };

    this.perfConfig = {
      enableCaching: true,
      maxCacheSize: 1000,
      enableParallel: true,
      batchSize: 10,
      enablePrediction: true,
      predictionWindow: 2.0, // 2 seconds
      ...perfConfig
    };

    this.initializeMetrics();
  }

  /**
   * Initialize matching metrics
   */
  private initializeMetrics(): void {
    this.metrics = {
      totalMatches: 0,
      successfulMatches: 0,
      failedMatches: 0,
      matchSuccessRate: 0,
      averageMatchQuality: 0,
      averageLatencyMs: 0,
      processingTimeMs: 0,
      matchesPerSecond: 0
    };
  }

  /**
   * Find best match for HIL signal using multi-scale temporal windows
   */
  async findBestMatch(
    signalTimestamp: number,
    tracks: VRUTrack[],
    signalData?: any
  ): Promise<TemporalMatchResult> {
    
    const startTime = Date.now();
    let bestMatch: VRUTrackMatch | null = null;
    let allCandidates: VRUMatchCandidate[] = [];
    const algorithmUsed = 'multi_scale_temporal';

    try {
      // Step 1: Check cache for existing match
      if (this.perfConfig.enableCaching) {
        const cacheKey = this.generateCacheKey(signalTimestamp, tracks);
        const cachedMatch = this.matchCache.get(cacheKey);
        if (cachedMatch) {
          console.log(`⚡ [TemporalMatcher] Cache hit for timestamp ${signalTimestamp.toFixed(3)}s`);
          return {
            match: cachedMatch,
            candidates: this.candidateCache.get(cacheKey) || [],
            processingTimeMs: Date.now() - startTime,
            matchFound: true,
            matchQuality: cachedMatch.matchQuality,
            algorithmUsed: 'cached'
          };
        }
      }

      // Step 2: Filter potential tracks
      const potentialTracks = filterPotentialTracks(signalTimestamp, tracks, this.config);
      
      if (potentialTracks.length === 0) {
        console.warn(`⚠️ [TemporalMatcher] No potential tracks found for timestamp ${signalTimestamp.toFixed(3)}s`);
        return this.createEmptyResult(startTime);
      }

      console.log(`🔍 [TemporalMatcher] Matching signal at ${signalTimestamp.toFixed(3)}s against ${potentialTracks.length} potential tracks`);

      // Step 3: Multi-scale temporal matching
      bestMatch = await this.performMultiScaleMatching(
        signalTimestamp,
        potentialTracks,
        signalData
      );

      // Step 4: Generate all candidates for analysis
      allCandidates = potentialTracks.map(track => 
        createMatchCandidate(signalTimestamp, track, this.config)
      );
      allCandidates = sortMatchCandidates(allCandidates);

      // Step 5: Cache results
      if (this.perfConfig.enableCaching && bestMatch) {
        this.cacheResults(signalTimestamp, tracks, bestMatch, allCandidates);
      }

      // Step 6: Update metrics
      this.updateMatchingMetrics(bestMatch, allCandidates, startTime);

      const processingTime = Date.now() - startTime;
      const matchFound = bestMatch !== null;
      const matchQuality = bestMatch?.matchQuality || 0;

      if (bestMatch) {
        logMatchInfo(bestMatch);
      }

      return {
        match: bestMatch,
        candidates: allCandidates,
        processingTimeMs: processingTime,
        matchFound,
        matchQuality,
        algorithmUsed
      };

    } catch (error) {
      console.error('[TemporalMatcher] Error in findBestMatch:', error);
      return this.createEmptyResult(startTime);
    }
  }

  /**
   * Perform multi-scale temporal matching with different window sizes
   */
  private async performMultiScaleMatching(
    signalTimestamp: number,
    tracks: VRUTrack[],
    signalData?: any
  ): Promise<VRUTrackMatch | null> {

    const windows = [
      { size: this.windowConfig.immediate, name: 'immediate' },
      { size: this.windowConfig.normal, name: 'normal' },
      { size: this.windowConfig.extended, name: 'extended' }
    ];

    // Try each window scale, starting with smallest (most precise)
    for (const window of windows) {
      console.log(`🎯 [TemporalMatcher] Trying ${window.name} window (±${(window.size * 1000).toFixed(0)}ms)`);

      const match = await this.matchWithinWindow(
        signalTimestamp,
        tracks,
        window.size,
        signalData
      );

      if (match && match.matchQuality >= this.config.minMatchScore) {
        console.log(`✅ [TemporalMatcher] Found match in ${window.name} window (quality: ${(match.matchQuality * 100).toFixed(1)}%)`);
        return match;
      }
    }

    // Try adaptive window if enabled
    if (this.windowConfig.adaptive) {
      console.log(`🔄 [TemporalMatcher] Trying adaptive window scaling`);
      return await this.matchWithAdaptiveWindow(signalTimestamp, tracks, signalData);
    }

    return null;
  }

  /**
   * Match within a specific temporal window
   */
  private async matchWithinWindow(
    signalTimestamp: number,
    tracks: VRUTrack[],
    windowSize: number,
    signalData?: any
  ): Promise<VRUTrackMatch | null> {

    const candidates: VRUMatchCandidate[] = [];

    // Generate candidates for tracks within window
    for (const track of tracks) {
      const candidate = createMatchCandidate(signalTimestamp, track, this.config);
      
      // Check if candidate is within temporal window
      if (candidate.timeDifference <= (windowSize * 1000)) { // Convert to ms
        candidates.push(candidate);
      }
    }

    if (candidates.length === 0) {
      return null;
    }

    // Sort by match quality and select best
    const sortedCandidates = sortMatchCandidates(candidates);
    const bestCandidate = sortedCandidates[0];

    // Validate match quality
    if (!isMatchValid(bestCandidate, this.config)) {
      return null;
    }

    // Create full match result
    return await this.createTrackMatch(
      bestCandidate,
      signalTimestamp,
      signalData
    );
  }

  /**
   * Match with adaptive window sizing based on VRU characteristics
   */
  private async matchWithAdaptiveWindow(
    signalTimestamp: number,
    tracks: VRUTrack[],
    signalData?: any
  ): Promise<VRUTrackMatch | null> {

    const adaptiveCandidates: Array<{
      candidate: VRUMatchCandidate;
      adaptiveWindow: number;
    }> = [];

    // Calculate adaptive windows for each track
    for (const track of tracks) {
      let adaptiveWindow = this.windowConfig.normal; // Base window

      // Scale window based on VRU speed
      if (track.trajectory.velocities.length > 0) {
        const avgSpeed = track.trajectory.velocities.reduce((sum, v) => sum + v.speed, 0) / track.trajectory.velocities.length;
        // Faster VRUs get larger windows (more prediction uncertainty)
        adaptiveWindow *= (1 + (avgSpeed / 100) * this.windowConfig.scalingFactor);
      }

      // Scale window based on track confidence
      adaptiveWindow *= (2 - track.trackConfidence); // Lower confidence = larger window

      // Clamp to reasonable bounds
      adaptiveWindow = Math.min(adaptiveWindow, this.windowConfig.extended);
      adaptiveWindow = Math.max(adaptiveWindow, this.windowConfig.immediate);

      const candidate = createMatchCandidate(signalTimestamp, track, this.config);
      
      if (candidate.timeDifference <= (adaptiveWindow * 1000)) {
        adaptiveCandidates.push({ candidate, adaptiveWindow });
      }
    }

    if (adaptiveCandidates.length === 0) {
      return null;
    }

    // Select best adaptive candidate
    const sortedAdaptive = adaptiveCandidates
      .sort((a, b) => b.candidate.matchScore - a.candidate.matchScore);
    
    const bestAdaptive = sortedAdaptive[0];
    
    if (!isMatchValid(bestAdaptive.candidate, this.config)) {
      return null;
    }

    console.log(`🎯 [TemporalMatcher] Adaptive match found with window ±${(bestAdaptive.adaptiveWindow * 1000).toFixed(0)}ms`);

    return await this.createTrackMatch(
      bestAdaptive.candidate,
      signalTimestamp,
      signalData
    );
  }

  /**
   * Create full VRU track match from candidate
   */
  private async createTrackMatch(
    candidate: VRUMatchCandidate,
    actualTime: number,
    signalData?: any
  ): Promise<VRUTrackMatch> {

    // Find closest annotation for expected time
    const closestAnnotation = candidate.track.annotations.reduce((closest, ann) => {
      const closestDiff = Math.abs(closest.timestamp - actualTime);
      const currentDiff = Math.abs(ann.timestamp - actualTime);
      return currentDiff < closestDiff ? ann : closest;
    });

    const expectedTime = closestAnnotation.timestamp;
    const latencyMs = Math.abs(actualTime - expectedTime) * 1000;

    // Create position data if available
    const expectedPosition = candidate.track.trajectory.positions.find(pos => 
      Math.abs(pos.timestamp - expectedTime) < 0.1
    ) || candidate.track.currentPosition;

    const match: VRUTrackMatch = {
      // Match result
      track: candidate.track,
      candidate,
      matchQuality: candidate.matchScore,
      matchType: candidate.matchType,
      
      // Timing analysis
      expectedTime,
      actualTime,
      latencyMs,
      temporalDistance: candidate.timeDifference / 1000, // Convert to seconds
      
      // Spatial analysis (if available)
      expectedPosition,
      spatialDistance: undefined, // No spatial data from HIL signals
      
      // Quality metrics
      signalStrength: signalData ? Math.min(1, (signalData.voltage || 0) / 5.0) : 0.8,
      noiseLevel: signalData ? Math.max(0, 1 - (signalData.signalQuality || 0.8)) : 0.1,
      confidence: candidate.matchScore,
      
      // Match metadata
      matchedAt: new Date(),
      matchAlgorithm: this.getActiveAlgorithm(),
      processingTimeMs: 0 // Will be updated by caller
    };

    return match;
  }

  /**
   * Process multiple signals in batch for improved performance
   */
  async batchMatch(
    signalTimestamps: number[],
    tracks: VRUTrack[],
    signalDataArray?: any[]
  ): Promise<TemporalMatchResult[]> {
    
    console.log(`🚀 [TemporalMatcher] Batch matching ${signalTimestamps.length} signals against ${tracks.length} tracks`);
    
    const results: TemporalMatchResult[] = [];
    
    if (this.perfConfig.enableParallel && signalTimestamps.length > this.perfConfig.batchSize) {
      // Process in parallel batches
      const batches = this.chunkArray(signalTimestamps, this.perfConfig.batchSize);
      
      for (const batch of batches) {
        const batchPromises = batch.map((timestamp, index) => {
          const signalData = signalDataArray?.[signalTimestamps.indexOf(timestamp)];
          return this.findBestMatch(timestamp, tracks, signalData);
        });
        
        const batchResults = await Promise.all(batchPromises);
        results.push(...batchResults);
      }
    } else {
      // Process sequentially
      for (let i = 0; i < signalTimestamps.length; i++) {
        const timestamp = signalTimestamps[i];
        const signalData = signalDataArray?.[i];
        const result = await this.findBestMatch(timestamp, tracks, signalData);
        results.push(result);
      }
    }
    
    console.log(`✅ [TemporalMatcher] Batch processing complete: ${results.filter(r => r.matchFound).length}/${results.length} successful matches`);
    
    return results;
  }

  /**
   * Create detection events from match results
   */
  createDetectionEvents(
    matchResults: TemporalMatchResult[],
    signalDataArray: any[],
    sessionId: string,
    videoId: string,
    projectId: string,
    thresholdMs: number
  ): VRUDetectionEvent[] {
    
    const events: VRUDetectionEvent[] = [];
    
    for (let i = 0; i < matchResults.length; i++) {
      const result = matchResults[i];
      const signalData = signalDataArray[i];
      
      const event = createDetectionEvent(
        result.match,
        signalData,
        sessionId,
        videoId,
        projectId,
        thresholdMs,
        Date.now()
      );
      
      events.push(event);
    }
    
    return events;
  }

  /**
   * Generate cache key for match results
   */
  private generateCacheKey(signalTimestamp: number, tracks: VRUTrack[]): string {
    const trackIds = tracks.map(t => t.trackId).sort().join('|');
    const timestampKey = Math.floor(signalTimestamp * 100) / 100; // Round to 10ms precision
    return `${timestampKey}_${trackIds.substring(0, 50)}`; // Limit length
  }

  /**
   * Cache match results for performance
   */
  private cacheResults(
    signalTimestamp: number,
    tracks: VRUTrack[],
    match: VRUTrackMatch,
    candidates: VRUMatchCandidate[]
  ): void {
    
    const cacheKey = this.generateCacheKey(signalTimestamp, tracks);
    
    // Manage cache size
    if (this.matchCache.size >= this.perfConfig.maxCacheSize) {
      // Remove oldest entries (simple LRU)
      const keysToRemove = Array.from(this.matchCache.keys()).slice(0, 100);
      keysToRemove.forEach(key => {
        this.matchCache.delete(key);
        this.candidateCache.delete(key);
      });
    }
    
    this.matchCache.set(cacheKey, match);
    this.candidateCache.set(cacheKey, candidates);
  }

  /**
   * Update matching metrics
   */
  private updateMatchingMetrics(
    match: VRUTrackMatch | null,
    candidates: VRUMatchCandidate[],
    startTime: number
  ): void {
    
    const processingTime = Date.now() - startTime;
    
    this.metrics.totalMatches = (this.metrics.totalMatches || 0) + 1;
    
    if (match) {
      this.metrics.successfulMatches = (this.metrics.successfulMatches || 0) + 1;
      
      // Update quality metrics
      const currentQuality = this.metrics.averageMatchQuality || 0;
      this.metrics.averageMatchQuality = (currentQuality * (this.metrics.successfulMatches - 1) + match.matchQuality) / this.metrics.successfulMatches;
      
      // Update latency metrics
      const currentLatency = this.metrics.averageLatencyMs || 0;
      this.metrics.averageLatencyMs = (currentLatency * (this.metrics.successfulMatches - 1) + match.latencyMs) / this.metrics.successfulMatches;
    } else {
      this.metrics.failedMatches = (this.metrics.failedMatches || 0) + 1;
    }
    
    // Update performance metrics
    const totalMatches = this.metrics.totalMatches;
    const successfulMatches = this.metrics.successfulMatches || 0;
    this.metrics.matchSuccessRate = totalMatches > 0 ? successfulMatches / totalMatches : 0;
    
    // Update processing time
    const currentProcTime = this.metrics.processingTimeMs || 0;
    this.metrics.processingTimeMs = (currentProcTime * (totalMatches - 1) + processingTime) / totalMatches;
    
    this.metrics.matchesPerSecond = this.metrics.processingTimeMs > 0 ? 1000 / this.metrics.processingTimeMs : 0;
  }

  /**
   * Create empty result for failed matches
   */
  private createEmptyResult(startTime: number): TemporalMatchResult {
    return {
      match: null,
      candidates: [],
      processingTimeMs: Date.now() - startTime,
      matchFound: false,
      matchQuality: 0,
      algorithmUsed: 'none'
    };
  }

  /**
   * Get active algorithm identifier
   */
  private getActiveAlgorithm(): string {
    const parts = [
      'temporal_matcher',
      this.config.matchingAlgorithm,
      this.windowConfig.adaptive ? 'adaptive' : 'fixed',
      this.perfConfig.enableParallel ? 'parallel' : 'sequential'
    ];
    return parts.join('_');
  }

  /**
   * Utility: Chunk array into smaller batches
   */
  private chunkArray<T>(array: T[], chunkSize: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < array.length; i += chunkSize) {
      chunks.push(array.slice(i, i + chunkSize));
    }
    return chunks;
  }

  /**
   * Get matching metrics
   */
  getMetrics(): Partial<VRUTrackingMetrics> {
    return { ...this.metrics };
  }

  /**
   * Clear caches and reset metrics
   */
  reset(): void {
    this.matchCache.clear();
    this.candidateCache.clear();
    this.initializeMetrics();
    console.log('[TemporalMatcher] State reset completed');
  }

  /**
   * Print performance statistics
   */
  printPerformanceStats(): void {
    console.log('🎯 [TemporalMatcher] Performance Statistics:');
    console.log(`  Total Matches: ${this.metrics.totalMatches || 0}`);
    console.log(`  Success Rate: ${((this.metrics.matchSuccessRate || 0) * 100).toFixed(1)}%`);
    console.log(`  Average Quality: ${((this.metrics.averageMatchQuality || 0) * 100).toFixed(1)}%`);
    console.log(`  Average Latency: ${(this.metrics.averageLatencyMs || 0).toFixed(1)}ms`);
    console.log(`  Processing Speed: ${(this.metrics.matchesPerSecond || 0).toFixed(1)} matches/sec`);
    console.log(`  Cache Size: ${this.matchCache.size}/${this.perfConfig.maxCacheSize}`);
  }
}

/**
 * Create Temporal Matcher instance
 */
export const createTemporalMatcher = (
  config?: VRUTrackingConfig,
  windowConfig?: Partial<TemporalWindowConfig>,
  perfConfig?: Partial<PerformanceConfig>
): TemporalMatcher => {
  return new TemporalMatcher(config, windowConfig, perfConfig);
};