/**
 * VRU Track Manager
 * 
 * Core service for managing VRU (Vulnerable Road User) tracks in HIL testing.
 * Handles spatial-temporal clustering, track lifecycle, and trajectory management.
 */

import {
  VRUType,
  VRUTrack,
  VRUPosition,
  VRUTrajectory,
  VRUTrackState,
  VRUTrackCluster,
  VRUTrackingConfig,
  VRUTrackingMetrics,
  VRUTrackingResult,
  DEFAULT_VRU_TRACKING_CONFIG
} from '../types/vru-tracking';

import {
  generateTrackId,
  parseVRUType,
  annotationToPosition,
  arePositionsSpatiallyClose,
  areTimestampsTemporallyClose,
  calculateSpatialDistance,
  calculateTemporalDistance,
  calculateVelocity,
  calculateTrackConfidence,
  calculateSpatialConsistency,
  calculateTemporalConsistency,
  validateTrackingConfig,
  logTrackInfo
} from '../utils/vruTrackingUtils';

import { GroundTruthAnnotation } from '../services/types';

/**
 * VRU Track Manager - Core tracking system
 */
export class VRUTrackManager {
  private config: VRUTrackingConfig;
  private tracks: Map<string, VRUTrack> = new Map();
  private clusters: Map<string, VRUTrackCluster> = new Map();
  private metrics: VRUTrackingMetrics;
  private processingStartTime: number = 0;

  constructor(config: VRUTrackingConfig = DEFAULT_VRU_TRACKING_CONFIG) {
    if (!validateTrackingConfig(config)) {
      console.warn('[VRUTrackManager] Invalid config provided, using defaults');
      this.config = DEFAULT_VRU_TRACKING_CONFIG;
    } else {
      this.config = config;
    }

    this.initializeMetrics();
  }

  /**
   * Initialize tracking metrics
   */
  private initializeMetrics(): void {
    this.metrics = {
      totalTracks: 0,
      activeTracks: 0,
      completedTracks: 0,
      averageTrackDuration: 0,
      totalMatches: 0,
      successfulMatches: 0,
      failedMatches: 0,
      matchSuccessRate: 0,
      averageMatchQuality: 0,
      averageTrackConfidence: 0,
      averageLatencyMs: 0,
      processingTimeMs: 0,
      tracksPerSecond: 0,
      matchesPerSecond: 0,
      memoryUsageMB: 0,
      falsePositives: 0,
      falseNegatives: 0,
      missedDetections: 0,
      duplicateMatches: 0
    };
  }

  /**
   * Process ground truth annotations into VRU tracks
   */
  async processAnnotations(
    annotations: GroundTruthAnnotation[],
    videoId: string,
    projectId: string
  ): Promise<VRUTrack[]> {
    this.processingStartTime = Date.now();
    
    console.log(`🚀 [VRUTrackManager] Processing ${annotations.length} annotations`);
    
    // Reset state
    this.tracks.clear();
    this.clusters.clear();
    this.initializeMetrics();

    if (annotations.length === 0) {
      console.warn('[VRUTrackManager] No annotations to process');
      return [];
    }

    try {
      // Step 1: Group annotations by VRU type
      const annotationsByType = this.groupAnnotationsByType(annotations);
      
      // Step 2: Create clusters for each VRU type
      const allClusters: VRUTrackCluster[] = [];
      
      for (const [vruType, typeAnnotations] of annotationsByType) {
        console.log(`📊 [VRUTrackManager] Processing ${typeAnnotations.length} ${vruType} annotations`);
        const typeClusters = await this.createClustersForType(vruType, typeAnnotations);
        allClusters.push(...typeClusters);
      }

      // Step 3: Convert clusters to tracks
      const tracks = await this.clustersToTracks(allClusters, videoId, projectId);
      
      // Step 4: Optimize and validate tracks
      const optimizedTracks = await this.optimizeTracks(tracks);
      
      // Step 5: Update metrics
      this.updateMetrics(optimizedTracks);
      
      console.log(`✅ [VRUTrackManager] Created ${optimizedTracks.length} VRU tracks from ${annotations.length} annotations`);
      
      // Log track summaries
      optimizedTracks.forEach(track => logTrackInfo(track));
      
      return optimizedTracks;

    } catch (error) {
      console.error('[VRUTrackManager] Error processing annotations:', error);
      throw error;
    }
  }

  /**
   * Group annotations by VRU type
   */
  private groupAnnotationsByType(annotations: GroundTruthAnnotation[]): Map<VRUType, GroundTruthAnnotation[]> {
    const groups = new Map<VRUType, GroundTruthAnnotation[]>();
    
    for (const annotation of annotations) {
      // Try to extract VRU type from annotation
      let vruType = VRUType.UNKNOWN;
      
      if (annotation.vru_type) {
        vruType = parseVRUType(annotation.vru_type);
      } else if (annotation.class_name) {
        vruType = parseVRUType(annotation.class_name);
      } else if ((annotation as any).className) {
        vruType = parseVRUType((annotation as any).className);
      }
      
      if (!groups.has(vruType)) {
        groups.set(vruType, []);
      }
      
      groups.get(vruType)!.push(annotation);
    }
    
    return groups;
  }

  /**
   * Create spatial-temporal clusters for a specific VRU type
   */
  private async createClustersForType(
    vruType: VRUType,
    annotations: GroundTruthAnnotation[]
  ): Promise<VRUTrackCluster[]> {
    
    const positions = annotations.map(ann => annotationToPosition(ann));
    const clusters: VRUTrackCluster[] = [];
    const processed = new Set<number>();

    // Sort positions by timestamp for temporal processing
    const sortedIndices = positions
      .map((_, index) => index)
      .sort((a, b) => positions[a].timestamp - positions[b].timestamp);

    for (const startIdx of sortedIndices) {
      if (processed.has(startIdx)) continue;

      const cluster = await this.createClusterFromSeed(
        startIdx,
        positions,
        annotations,
        processed,
        vruType
      );

      if (cluster && cluster.tracks.length >= this.config.minClusterSize) {
        clusters.push(cluster);
      }
    }

    console.log(`🎯 [VRUTrackManager] Created ${clusters.length} clusters for ${vruType}`);
    return clusters;
  }

  /**
   * Create a cluster starting from a seed position
   */
  private async createClusterFromSeed(
    seedIdx: number,
    positions: VRUPosition[],
    annotations: GroundTruthAnnotation[],
    processed: Set<number>,
    vruType: VRUType
  ): Promise<VRUTrackCluster | null> {

    if (processed.has(seedIdx)) return null;

    const seedPosition = positions[seedIdx];
    const clusterPositions: number[] = [seedIdx];
    processed.add(seedIdx);

    // Find all positions that cluster with the seed
    for (let i = 0; i < positions.length; i++) {
      if (processed.has(i)) continue;

      const position = positions[i];
      
      // Check spatial-temporal proximity to any position in current cluster
      const belongsToCluster = clusterPositions.some(clusterIdx => {
        const clusterPos = positions[clusterIdx];
        
        const spatiallyClose = arePositionsSpatiallyClose(
          position,
          clusterPos,
          this.config.spatialClusterRadius
        );
        
        const temporallyClose = areTimestampsTemporallyClose(
          position.timestamp,
          clusterPos.timestamp,
          this.config.temporalClusterWindow
        );
        
        return spatiallyClose && temporallyClose;
      });

      if (belongsToCluster) {
        clusterPositions.push(i);
        processed.add(i);
      }
    }

    // Create cluster if we have enough positions
    if (clusterPositions.length < this.config.minClusterSize) {
      return null;
    }

    // Calculate cluster center and metrics
    const clusterAnnotations = clusterPositions.map(idx => annotations[idx]);
    const centerPosition = this.calculateClusterCenter(clusterPositions.map(idx => positions[idx]));
    const radius = this.calculateClusterRadius(clusterPositions.map(idx => positions[idx]), centerPosition);
    const timeWindow = this.calculateClusterTimeWindow(clusterAnnotations);

    const clusterId = `${vruType}_cluster_${Date.now()}_${Math.floor(Math.random() * 1000)}`;

    // Create temporary track for this cluster
    const trackId = generateTrackId(vruType, seedPosition.timestamp);
    const track: VRUTrack = await this.createTrackFromAnnotations(
      trackId,
      vruType,
      clusterAnnotations,
      '',
      ''
    );

    return {
      clusterId,
      tracks: [track],
      centerPoint: centerPosition,
      radius,
      timeWindow,
      clusterConfidence: this.calculateClusterConfidence(clusterPositions.map(idx => positions[idx]))
    };
  }

  /**
   * Calculate cluster center position
   */
  private calculateClusterCenter(positions: VRUPosition[]): VRUPosition {
    const centerX = positions.reduce((sum, pos) => sum + pos.x, 0) / positions.length;
    const centerY = positions.reduce((sum, pos) => sum + pos.y, 0) / positions.length;
    const centerTime = positions.reduce((sum, pos) => sum + pos.timestamp, 0) / positions.length;
    const avgConfidence = positions.reduce((sum, pos) => sum + pos.confidence, 0) / positions.length;

    // Create average bounding box
    const avgBBox = {
      x: centerX - 25, // Default width/2
      y: centerY - 25, // Default height/2
      width: 50,
      height: 50,
      confidence: avgConfidence
    };

    return {
      x: centerX,
      y: centerY,
      timestamp: centerTime,
      confidence: avgConfidence,
      boundingBox: avgBBox
    };
  }

  /**
   * Calculate cluster spatial radius
   */
  private calculateClusterRadius(positions: VRUPosition[], center: VRUPosition): number {
    if (positions.length === 0) return 0;
    
    const distances = positions.map(pos => calculateSpatialDistance(pos, center));
    return Math.max(...distances);
  }

  /**
   * Calculate cluster temporal window
   */
  private calculateClusterTimeWindow(annotations: GroundTruthAnnotation[]): number {
    if (annotations.length < 2) return 0;
    
    const timestamps = annotations.map(ann => ann.timestamp).sort((a, b) => a - b);
    return timestamps[timestamps.length - 1] - timestamps[0];
  }

  /**
   * Calculate cluster confidence
   */
  private calculateClusterConfidence(positions: VRUPosition[]): number {
    const avgConfidence = positions.reduce((sum, pos) => sum + pos.confidence, 0) / positions.length;
    const spatialConsistency = calculateSpatialConsistency(positions);
    
    // Bonus for more positions (more data = higher confidence)
    const sizeBonus = Math.min(0.2, positions.length * 0.05);
    
    return Math.min(1, avgConfidence * 0.6 + spatialConsistency * 0.3 + sizeBonus);
  }

  /**
   * Convert clusters to VRU tracks
   */
  private async clustersToTracks(
    clusters: VRUTrackCluster[],
    videoId: string,
    projectId: string
  ): Promise<VRUTrack[]> {
    
    const tracks: VRUTrack[] = [];

    for (const cluster of clusters) {
      for (const track of cluster.tracks) {
        // Update track with video/project context
        track.videoId = videoId;
        track.projectId = projectId;
        
        // Store in manager
        this.tracks.set(track.trackId, track);
        tracks.push(track);
      }
    }

    return tracks;
  }

  /**
   * Create VRU track from annotations
   */
  private async createTrackFromAnnotations(
    trackId: string,
    vruType: VRUType,
    annotations: GroundTruthAnnotation[],
    videoId: string,
    projectId: string
  ): Promise<VRUTrack> {

    // Sort annotations by timestamp
    const sortedAnnotations = [...annotations].sort((a, b) => a.timestamp - b.timestamp);
    
    // Convert to positions
    const positions = sortedAnnotations.map(ann => annotationToPosition(ann));
    
    // Calculate velocities
    const velocities = [];
    for (let i = 1; i < positions.length; i++) {
      velocities.push(calculateVelocity(positions[i-1], positions[i]));
    }

    // Create trajectory
    const trajectory: VRUTrajectory = {
      positions,
      velocities,
      pathConfidence: calculateSpatialConsistency(positions)
    };

    // Calculate time bounds
    const startTime = sortedAnnotations[0].timestamp;
    const endTime = sortedAnnotations[sortedAnnotations.length - 1].timestamp;
    const duration = endTime - startTime;

    // Calculate quality metrics
    const trackConfidence = calculateTrackConfidence(sortedAnnotations);
    const spatialConsistency = calculateSpatialConsistency(positions);
    const temporalConsistency = calculateTemporalConsistency(sortedAnnotations);

    // Calculate confidence metrics
    const confidences = sortedAnnotations.map(ann => ann.confidence || 0.5);
    const averageConfidence = confidences.reduce((sum, conf) => sum + conf, 0) / confidences.length;
    const maxConfidence = Math.max(...confidences);
    const minConfidence = Math.min(...confidences);

    const track: VRUTrack = {
      // Identity
      trackId,
      vruType,
      state: VRUTrackState.ACTIVE,
      
      // Temporal bounds
      startTime,
      endTime,
      duration,
      
      // Spatial information
      trajectory,
      currentPosition: positions[positions.length - 1],
      
      // Source data
      annotations: sortedAnnotations,
      frameCount: sortedAnnotations.length,
      
      // Quality metrics
      trackConfidence,
      spatialConsistency,
      temporalConsistency,
      
      // Detection context
      averageConfidence,
      maxConfidence,
      minConfidence,
      
      // Metadata
      createdAt: new Date(),
      updatedAt: new Date(),
      videoId,
      projectId
    };

    return track;
  }

  /**
   * Optimize tracks for better matching performance
   */
  private async optimizeTracks(tracks: VRUTrack[]): Promise<VRUTrack[]> {
    const optimized: VRUTrack[] = [];

    for (const track of tracks) {
      // Filter low-quality tracks
      if (track.trackConfidence < this.config.minTrackConfidence) {
        console.warn(`[VRUTrackManager] Filtering low-confidence track: ${track.trackId} (${(track.trackConfidence * 100).toFixed(1)}%)`);
        continue;
      }

      // Update track state based on quality
      if (track.spatialConsistency < 0.3 || track.temporalConsistency < 0.3) {
        track.state = VRUTrackState.LOST;
      }

      optimized.push(track);
    }

    // Sort by confidence for better matching performance
    return optimized.sort((a, b) => b.trackConfidence - a.trackConfidence);
  }

  /**
   * Update tracking metrics
   */
  private updateMetrics(tracks: VRUTrack[]): void {
    const processingTime = Date.now() - this.processingStartTime;
    
    this.metrics = {
      ...this.metrics,
      totalTracks: tracks.length,
      activeTracks: tracks.filter(t => t.state === VRUTrackState.ACTIVE).length,
      completedTracks: tracks.filter(t => t.state === VRUTrackState.DEATH).length,
      averageTrackDuration: tracks.length > 0 ? 
        tracks.reduce((sum, t) => sum + t.duration, 0) / tracks.length : 0,
      averageTrackConfidence: tracks.length > 0 ?
        tracks.reduce((sum, t) => sum + t.trackConfidence, 0) / tracks.length : 0,
      processingTimeMs: processingTime,
      tracksPerSecond: processingTime > 0 ? (tracks.length / processingTime) * 1000 : 0
    };
  }

  /**
   * Get all active tracks
   */
  getTracks(): VRUTrack[] {
    return Array.from(this.tracks.values());
  }

  /**
   * Get track by ID
   */
  getTrack(trackId: string): VRUTrack | undefined {
    return this.tracks.get(trackId);
  }

  /**
   * Get tracks by VRU type
   */
  getTracksByType(vruType: VRUType): VRUTrack[] {
    return Array.from(this.tracks.values()).filter(track => track.vruType === vruType);
  }

  /**
   * Get tracks active at a specific timestamp
   */
  getActiveTracksAt(timestamp: number): VRUTrack[] {
    return Array.from(this.tracks.values()).filter(track => 
      timestamp >= track.startTime && 
      timestamp <= track.endTime &&
      track.state === VRUTrackState.ACTIVE
    );
  }

  /**
   * Get tracking metrics
   */
  getMetrics(): VRUTrackingMetrics {
    return { ...this.metrics };
  }

  /**
   * Get tracking configuration
   */
  getConfig(): VRUTrackingConfig {
    return { ...this.config };
  }

  /**
   * Update tracking configuration
   */
  updateConfig(newConfig: Partial<VRUTrackingConfig>): boolean {
    const updatedConfig = { ...this.config, ...newConfig };
    
    if (validateTrackingConfig(updatedConfig)) {
      this.config = updatedConfig;
      console.log('[VRUTrackManager] Configuration updated successfully');
      return true;
    } else {
      console.error('[VRUTrackManager] Invalid configuration provided');
      return false;
    }
  }

  /**
   * Create tracking result summary
   */
  createTrackingResult(
    sessionId: string,
    videoId: string,
    projectId: string
  ): VRUTrackingResult {
    return {
      sessionId,
      videoId,
      projectId,
      tracks: this.getTracks(),
      matches: [], // Will be populated by TemporalMatcher
      events: [], // Will be populated by HIL test execution
      metrics: this.getMetrics(),
      config: this.getConfig(),
      processedAt: new Date(),
      processingDuration: this.metrics.processingTimeMs,
      algorithmsUsed: [
        this.config.clusteringAlgorithm,
        this.config.matchingAlgorithm,
        this.config.trajectoryInterpolation
      ]
    };
  }

  /**
   * Clear all tracks and reset state
   */
  reset(): void {
    this.tracks.clear();
    this.clusters.clear();
    this.initializeMetrics();
    console.log('[VRUTrackManager] State reset completed');
  }

  /**
   * Debug: Print track statistics
   */
  printTrackStatistics(): void {
    const tracks = this.getTracks();
    const typeGroups = new Map<VRUType, number>();
    
    tracks.forEach(track => {
      typeGroups.set(track.vruType, (typeGroups.get(track.vruType) || 0) + 1);
    });

    console.log('🎯 [VRUTrackManager] Track Statistics:');
    console.log(`  Total Tracks: ${tracks.length}`);
    console.log(`  Processing Time: ${this.metrics.processingTimeMs}ms`);
    console.log(`  Average Track Duration: ${this.metrics.averageTrackDuration.toFixed(2)}s`);
    console.log(`  Average Track Confidence: ${(this.metrics.averageTrackConfidence * 100).toFixed(1)}%`);
    
    console.log('  VRU Type Distribution:');
    typeGroups.forEach((count, type) => {
      console.log(`    ${type}: ${count} tracks`);
    });
  }
}

/**
 * Create VRU Track Manager instance with configuration
 */
export const createVRUTrackManager = (config?: VRUTrackingConfig): VRUTrackManager => {
  return new VRUTrackManager(config);
};