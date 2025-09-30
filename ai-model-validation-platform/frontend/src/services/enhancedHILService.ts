/**
 * Enhanced HIL Service
 * 
 * Comprehensive HIL testing service that integrates VRU tracking,
 * temporal matching, and enhanced detection processing for production-ready
 * Hardware-in-the-Loop testing.
 */

import {
  VRUTrack,
  VRUTrackMatch,
  VRUDetectionEvent,
  VRUTrackingResult,
  VRUTrackingConfig,
  VRUTrackingMetrics,
  DEFAULT_VRU_TRACKING_CONFIG
} from '../types/vru-tracking';

import { VRUTrackManager, createVRUTrackManager } from './vruTrackManager';
import { TemporalMatcher, createTemporalMatcher, TemporalMatchResult } from './temporalMatcher';
import { GroundTruthAnnotation, VideoFile, Project } from './types';
import { apiService } from './api';

/**
 * Enhanced HIL Test Session with VRU context
 */
export interface EnhancedHILTestSession {
  id: string;
  projectId: string;
  videoId: string;
  testStartTime: Date | null;
  maxLatencyMs: number;
  labjackConnected: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed';
  
  // VRU Tracking Context
  vruTracks: VRUTrack[];
  trackingResult: VRUTrackingResult | null;
  vruTrackingEnabled: boolean;
  trackingConfig: VRUTrackingConfig;
}

/**
 * HIL Signal Data from LabJack
 */
export interface HILSignalData {
  timestamp: number;
  channel: string;
  voltage: number;
  lastVoltage?: number;
  videoElapsedSeconds: number;
  frameNumber: number;
  triggeredBySimulation?: boolean;
  signalQuality?: number;
}

/**
 * Enhanced HIL Test Results
 */
export interface EnhancedHILTestResults {
  sessionId: string;
  
  // Legacy compatibility
  detectionEvents: Array<{
    expectedEventTime: Date;
    signalReceivedTime?: Date;
    latencyMs?: number;
    outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection';
    videoId: string;
    frameNumber?: number;
    vruTrackId?: string;
    vruDetectionEvent?: VRUDetectionEvent;
    vruTrackMatch?: VRUTrackMatch;
  }>;
  
  // Enhanced VRU results
  vruDetectionEvents: VRUDetectionEvent[];
  vruTrackMatches: VRUTrackMatch[];
  trackingResult: VRUTrackingResult;
  
  // Performance metrics
  totalTests: number;
  passedTests: number;
  failedTests: number;
  passRate: number;
  averageLatencyMs: number;
  maxLatencyMs: number;
  minLatencyMs: number;
  
  // Quality assessment
  trackingQuality: number;
  matchingAccuracy: number;
  processingPerformance: VRUTrackingMetrics;
  
  // Metadata
  completedAt: Date;
  processingDuration: number;
}

/**
 * Enhanced HIL Service - Main service class
 */
export class EnhancedHILService {
  private trackManager: VRUTrackManager;
  private temporalMatcher: TemporalMatcher;
  private config: VRUTrackingConfig;
  private currentSession: EnhancedHILTestSession | null = null;
  private results: EnhancedHILTestResults | null = null;

  constructor(config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG) {
    this.config = config;
    this.trackManager = createVRUTrackManager(config);
    this.temporalMatcher = createTemporalMatcher(config);
    
    console.log('🚀 [EnhancedHILService] Service initialized with VRU tracking enabled');
  }

  /**
   * Initialize HIL test session with VRU tracking
   */
  async initializeSession(
    sessionId: string,
    project: Project,
    video: VideoFile,
    maxLatencyMs: number = 100
  ): Promise<EnhancedHILTestSession> {
    
    console.log(`🚀 [EnhancedHILService] Initializing session ${sessionId} for video ${video.filename}`);
    
    try {
      // Step 1: Load ground truth annotations
      console.log('📊 [EnhancedHILService] Loading ground truth annotations...');
      const annotations = await this.loadGroundTruthAnnotations(video.id);
      
      if (annotations.length === 0) {
        throw new Error('No ground truth annotations found for this video. Please process the video through the detection pipeline first.');
      }
      
      // Step 2: Process annotations into VRU tracks
      console.log(`🎯 [EnhancedHILService] Processing ${annotations.length} annotations into VRU tracks...`);
      const vruTracks = await this.trackManager.processAnnotations(
        annotations,
        video.id,
        project.id
      );
      
      console.log(`✅ [EnhancedHILService] Created ${vruTracks.length} VRU tracks`);
      
      // Step 3: Create tracking result
      const trackingResult = this.trackManager.createTrackingResult(
        sessionId,
        video.id,
        project.id
      );
      
      // Step 4: Initialize session
      this.currentSession = {
        id: sessionId,
        projectId: project.id,
        videoId: video.id,
        testStartTime: null,
        maxLatencyMs,
        labjackConnected: false,
        status: 'pending',
        vruTracks,
        trackingResult,
        vruTrackingEnabled: true,
        trackingConfig: this.config
      };
      
      // Step 5: Initialize results structure
      this.initializeResults();
      
      // Step 6: Print session summary
      this.printSessionSummary();
      
      return this.currentSession;

    } catch (error) {
      console.error('❌ [EnhancedHILService] Session initialization failed:', error);
      throw error;
    }
  }

  /**
   * Start HIL test execution
   */
  async startTest(): Promise<boolean> {
    if (!this.currentSession) {
      throw new Error('No active session - call initializeSession first');
    }
    
    console.log(`🚀 [EnhancedHILService] Starting HIL test for session ${this.currentSession.id}`);
    
    this.currentSession.testStartTime = new Date();
    this.currentSession.status = 'running';
    
    if (this.results) {
      this.results.totalTests = this.currentSession.vruTracks.reduce(
        (sum, track) => sum + track.annotations.length, 0
      );
    }
    
    console.log(`✅ [EnhancedHILService] Test started with ${this.currentSession.vruTracks.length} VRU tracks`);
    return true;
  }

  /**
   * Process HIL signal with VRU track matching
   */
  async processHILSignal(signalData: HILSignalData): Promise<VRUDetectionEvent | null> {
    if (!this.currentSession || !this.currentSession.testStartTime) {
      console.warn('⚠️ [EnhancedHILService] No active session or test not started');
      return null;
    }

    const processingStartTime = Date.now();
    
    try {
      // Step 1: Calculate signal timestamp relative to test start
      const signalTimestamp = signalData.videoElapsedSeconds;
      
      console.log(`📡 [EnhancedHILService] Processing HIL signal at ${signalTimestamp.toFixed(3)}s`);
      
      // Step 2: Find best VRU track match
      const matchResult = await this.temporalMatcher.findBestMatch(
        signalTimestamp,
        this.currentSession.vruTracks,
        signalData
      );
      
      if (!matchResult.matchFound || !matchResult.match) {
        console.warn(`⚠️ [EnhancedHILService] No VRU track match found for signal at ${signalTimestamp.toFixed(3)}s`);
        
        // Create failed detection event
        const failedEvent = this.createFailedDetectionEvent(
          signalData,
          'No matching VRU track found'
        );
        
        this.updateResults(failedEvent, null);
        return failedEvent;
      }
      
      // Step 3: Create detection event from match
      const detectionEvent = this.createDetectionEventFromMatch(
        matchResult.match,
        signalData,
        processingStartTime
      );
      
      // Step 4: Update results
      this.updateResults(detectionEvent, matchResult.match);
      
      // Step 5: Log success
      console.log(`✅ [EnhancedHILService] Detection event created:`, {
        trackId: detectionEvent.trackId,
        outcome: detectionEvent.outcome,
        latencyMs: detectionEvent.latencyMs?.toFixed(1),
        matchQuality: (matchResult.matchQuality * 100).toFixed(1) + '%'
      });
      
      return detectionEvent;

    } catch (error) {
      console.error('❌ [EnhancedHILService] Signal processing failed:', error);
      
      const errorEvent = this.createFailedDetectionEvent(
        signalData,
        `Processing error: ${error.message}`
      );
      
      this.updateResults(errorEvent, null);
      return errorEvent;
    }
  }

  /**
   * Process multiple signals in batch
   */
  async processBatchSignals(signalDataArray: HILSignalData[]): Promise<VRUDetectionEvent[]> {
    if (!this.currentSession) {
      throw new Error('No active session');
    }

    console.log(`🚀 [EnhancedHILService] Processing ${signalDataArray.length} signals in batch`);
    
    const timestamps = signalDataArray.map(signal => signal.videoElapsedSeconds);
    const matchResults = await this.temporalMatcher.batchMatch(
      timestamps,
      this.currentSession.vruTracks,
      signalDataArray
    );
    
    const events: VRUDetectionEvent[] = [];
    
    for (let i = 0; i < matchResults.length; i++) {
      const matchResult = matchResults[i];
      const signalData = signalDataArray[i];
      
      if (matchResult.matchFound && matchResult.match) {
        const event = this.createDetectionEventFromMatch(
          matchResult.match,
          signalData,
          Date.now()
        );
        events.push(event);
        this.updateResults(event, matchResult.match);
      } else {
        const failedEvent = this.createFailedDetectionEvent(
          signalData,
          'Batch processing - no match found'
        );
        events.push(failedEvent);
        this.updateResults(failedEvent, null);
      }
    }
    
    console.log(`✅ [EnhancedHILService] Batch processing complete: ${events.filter(e => e.outcome === 'pass').length}/${events.length} successful`);
    
    return events;
  }

  /**
   * Complete HIL test and generate results
   */
  async completeTest(): Promise<EnhancedHILTestResults> {
    if (!this.currentSession || !this.results) {
      throw new Error('No active session or results');
    }

    console.log(`🏁 [EnhancedHILService] Completing test for session ${this.currentSession.id}`);
    
    this.currentSession.status = 'completed';
    this.results.completedAt = new Date();
    
    if (this.currentSession.testStartTime) {
      this.results.processingDuration = Date.now() - this.currentSession.testStartTime.getTime();
    }
    
    // Calculate final metrics
    this.calculateFinalMetrics();
    
    // Print results summary
    this.printResultsSummary();
    
    return { ...this.results };
  }

  /**
   * Get current test results
   */
  getCurrentResults(): EnhancedHILTestResults | null {
    return this.results ? { ...this.results } : null;
  }

  /**
   * Get current session
   */
  getCurrentSession(): EnhancedHILTestSession | null {
    return this.currentSession ? { ...this.currentSession } : null;
  }

  /**
   * Reset service state
   */
  reset(): void {
    this.currentSession = null;
    this.results = null;
    this.trackManager.reset();
    this.temporalMatcher.reset();
    console.log('🔄 [EnhancedHILService] Service state reset');
  }

  // Private helper methods

  private async loadGroundTruthAnnotations(videoId: string): Promise<GroundTruthAnnotation[]> {
    try {
      const annotations = await apiService.getAnnotations(videoId);
      console.log(`📊 [EnhancedHILService] Loaded ${annotations.length} annotations from API`);
      return annotations;
    } catch (error) {
      console.warn(`⚠️ [EnhancedHILService] Failed to load annotations: ${error.message}`);
      return [];
    }
  }


  private initializeResults(): void {
    if (!this.currentSession) return;

    this.results = {
      sessionId: this.currentSession.id,
      detectionEvents: [],
      vruDetectionEvents: [],
      vruTrackMatches: [],
      trackingResult: this.currentSession.trackingResult!,
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      passRate: 0,
      averageLatencyMs: 0,
      maxLatencyMs: 0,
      minLatencyMs: Infinity,
      trackingQuality: 0,
      matchingAccuracy: 0,
      processingPerformance: this.trackManager.getMetrics(),
      completedAt: new Date(),
      processingDuration: 0
    };
  }

  private createDetectionEventFromMatch(
    match: VRUTrackMatch,
    signalData: HILSignalData,
    processingStartTime: number
  ): VRUDetectionEvent {
    
    const latencyMs = match.latencyMs;
    const outcome = latencyMs <= this.currentSession!.maxLatencyMs ? 'pass' : 'fail_high_latency';
    
    const event: VRUDetectionEvent = {
      id: `${match.track.trackId}_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
      eventType: 'vru_matched',
      timestamp: signalData.videoElapsedSeconds,
      detectedAt: new Date(),
      frameNumber: signalData.frameNumber,
      trackId: match.track.trackId,
      vruType: match.track.vruType,
      trackMatch: match,
      confidence: match.confidence,
      signalQuality: signalData.signalQuality || 0.8,
      labJackChannel: signalData.channel,
      voltageLevel: signalData.voltage,
      outcome,
      latencyMs,
      thresholdMs: this.currentSession!.maxLatencyMs,
      position: match.expectedPosition,
      boundingBox: match.expectedPosition?.boundingBox,
      videoId: this.currentSession!.videoId,
      projectId: this.currentSession!.projectId,
      sessionId: this.currentSession!.id,
      processingTimeMs: Date.now() - processingStartTime
    };

    return event;
  }

  private createFailedDetectionEvent(
    signalData: HILSignalData,
    reason: string
  ): VRUDetectionEvent {
    
    const event: VRUDetectionEvent = {
      id: `failed_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
      eventType: 'vru_lost',
      timestamp: signalData.videoElapsedSeconds,
      detectedAt: new Date(),
      frameNumber: signalData.frameNumber,
      trackId: 'unmatched',
      vruType: 'unknown',
      confidence: 0,
      signalQuality: signalData.signalQuality || 0.5,
      labJackChannel: signalData.channel,
      voltageLevel: signalData.voltage,
      outcome: 'fail_missed_detection',
      latencyMs: 0,
      thresholdMs: this.currentSession!.maxLatencyMs,
      videoId: this.currentSession!.videoId,
      projectId: this.currentSession!.projectId,
      sessionId: this.currentSession!.id,
      processingTimeMs: 0
    };

    return event;
  }

  private updateResults(event: VRUDetectionEvent, match: VRUTrackMatch | null): void {
    if (!this.results) return;

    // Add to VRU events
    this.results.vruDetectionEvents.push(event);
    
    if (match) {
      this.results.vruTrackMatches.push(match);
    }

    // Create legacy detection event for backward compatibility
    const legacyEvent = {
      expectedEventTime: match ? new Date(this.currentSession!.testStartTime!.getTime() + match.expectedTime * 1000) : new Date(),
      signalReceivedTime: event.detectedAt,
      latencyMs: event.latencyMs,
      outcome: event.outcome as 'pass' | 'fail_high_latency' | 'fail_missed_detection',
      videoId: event.videoId,
      frameNumber: event.frameNumber,
      vruTrackId: event.trackId,
      vruDetectionEvent: event,
      vruTrackMatch: match || undefined
    };
    
    this.results.detectionEvents.push(legacyEvent);

    // Update statistics
    if (event.outcome === 'pass') {
      this.results.passedTests++;
    } else {
      this.results.failedTests++;
    }

    const totalEvents = this.results.vruDetectionEvents.length;
    this.results.passRate = totalEvents > 0 ? this.results.passedTests / totalEvents : 0;

    // Update latency statistics
    if (event.latencyMs && event.latencyMs > 0) {
      this.results.maxLatencyMs = Math.max(this.results.maxLatencyMs, event.latencyMs);
      this.results.minLatencyMs = Math.min(this.results.minLatencyMs, event.latencyMs);
      
      const validLatencies = this.results.vruDetectionEvents
        .filter(e => e.latencyMs && e.latencyMs > 0)
        .map(e => e.latencyMs!);
      
      if (validLatencies.length > 0) {
        this.results.averageLatencyMs = validLatencies.reduce((sum, lat) => sum + lat, 0) / validLatencies.length;
      }
    }
  }

  private calculateFinalMetrics(): void {
    if (!this.results) return;

    // Calculate tracking quality
    const matchedEvents = this.results.vruDetectionEvents.filter(e => e.trackMatch);
    if (matchedEvents.length > 0) {
      this.results.trackingQuality = matchedEvents.reduce((sum, e) => 
        sum + (e.trackMatch?.matchQuality || 0), 0) / matchedEvents.length;
    }

    // Calculate matching accuracy
    this.results.matchingAccuracy = this.results.passRate;

    // Update performance metrics
    this.results.processingPerformance = {
      ...this.trackManager.getMetrics(),
      ...this.temporalMatcher.getMetrics()
    };

    // Fix infinity values
    if (!isFinite(this.results.minLatencyMs)) {
      this.results.minLatencyMs = 0;
    }
  }

  private printSessionSummary(): void {
    if (!this.currentSession) return;

    console.log('🎯 [EnhancedHILService] Session Summary:');
    console.log(`  Session ID: ${this.currentSession.id}`);
    console.log(`  Video ID: ${this.currentSession.videoId}`);
    console.log(`  VRU Tracks: ${this.currentSession.vruTracks.length}`);
    console.log(`  Max Latency: ${this.currentSession.maxLatencyMs}ms`);
    console.log(`  VRU Tracking: ${this.currentSession.vruTrackingEnabled ? 'Enabled' : 'Disabled'}`);
  }

  private printResultsSummary(): void {
    if (!this.results) return;

    console.log('📊 [EnhancedHILService] Final Results:');
    console.log(`  Total Events: ${this.results.vruDetectionEvents.length}`);
    console.log(`  Pass Rate: ${(this.results.passRate * 100).toFixed(1)}%`);
    console.log(`  Average Latency: ${this.results.averageLatencyMs.toFixed(1)}ms`);
    console.log(`  Tracking Quality: ${(this.results.trackingQuality * 100).toFixed(1)}%`);
    console.log(`  Processing Duration: ${this.results.processingDuration}ms`);
  }
}

/**
 * Create Enhanced HIL Service instance
 */
export const createEnhancedHILService = (config?: VRUTrackingConfig): EnhancedHILService => {
  return new EnhancedHILService(config);
};