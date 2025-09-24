/**
 * VRU Track Management System
 * 
 * Solves the core problem of persistent VRU identification across video frames.
 * Converts frame-by-frame annotations into coherent tracks with stable IDs.
 * 
 * Key Features:
 * - Spatial-temporal clustering of frame annotations
 * - Persistent track ID assignment across video timeline  
 * - Trajectory calculation and motion prediction
 * - Track quality assessment and validation
 */

import { GroundTruthAnnotation, VRUType, DetectionOutcome } from '../types';

export enum TrackState {
  BIRTH = "BIRTH",         // First 3 frames, establishing identity
  ACTIVE = "ACTIVE",       // Normal tracking state  
  OCCLUDED = "OCCLUDED",   // Temporarily hidden
  DEATH = "DEATH"          // Track terminated
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point2D {
  x: number;
  y: number;
}

export interface Vector2D {
  dx: number;
  dy: number;
}

export interface FrameAnnotation {
  frameNumber: number;
  timestampMs: number;               // Video timestamp
  bbox: BoundingBox;
  detectionConfidence: number;
  annotationId: string;              // Original frame annotation ID
  quality: AnnotationQuality;
}

export interface AnnotationQuality {
  spatialStability: number;          // Bbox consistency [0-1]
  temporalConsistency: number;       // Motion smoothness [0-1]  
  overallScore: number;              // Composite quality [0-1]
}

export interface HILSignalMatch {
  matchId: string;
  trackId: string;
  expectedTimestampMs: number;       // From ground truth
  actualSignalTimestampMs: number;   // From LabJack
  latencyMs: number;                 // actualSignal - expected
  matchConfidence: number;           // Match quality score [0-1]
  spatialAccuracy?: number;          // If spatial data available
  outcome: DetectionOutcome;         // PASS, FAIL_HIGH_LATENCY, etc.
}

export interface VRUTrack {
  // Persistent Identity
  trackId: string;                    // Unique across entire video
  vruType: VRUType;                   // Pedestrian, Cyclist, etc.
  
  // Track Lifecycle
  birthFrame: number;                 // First appearance
  deathFrame: number | null;          // Last appearance (null if active)
  currentState: TrackState;           // BIRTH, ACTIVE, OCCLUDED, DEATH
  confidence: number;                 // Overall track confidence [0-1]
  
  // Frame-by-Frame Annotations
  frameAnnotations: Map<number, FrameAnnotation>;
  
  // Trajectory Data
  trajectory: {
    positions: Point2D[];              // Bbox centers over time
    velocities: Vector2D[];            // Movement vectors
    smoothedPath: Point2D[];           // Kalman-filtered positions
    predictedPath: Point2D[];          // Future position prediction
  };
  
  // Temporal Properties
  averageSpeed: number;                // pixels/second
  directionConsistency: number;        // Direction stability [0-1]
  occlusionDuration: number;           // Frames occluded
  
  // Match History
  signalMatches: HILSignalMatch[];     // Successful HIL matches
  lastMatchTimestamp: number;          // Most recent signal match
  matchSuccess: boolean;               // Has successful HIL match
}

export interface VRUTrackConfig {
  maxFrameGap: number;                 // Max frames between annotations in track
  minSpatialOverlap: number;           // Min IoU for spatial matching
  minTrackLength: number;              // Min frames for valid track
  kalmanFilterQ: number;               // Process noise for smoothing
  kalmanFilterR: number;               // Measurement noise
}

export interface TemporalIndex {
  getTracksInWindow(timestampMs: number, windowMs: number): VRUTrack[];
  indexTrack(track: VRUTrack): void;
  removeTrack(trackId: string): void;
}

/**
 * Temporal indexing for fast track lookup by timestamp
 */
class SimpleTemporalIndex implements TemporalIndex {
  private timeIndex: Map<number, Set<string>> = new Map();
  private trackMap: Map<string, VRUTrack> = new Map();
  
  getTracksInWindow(timestampMs: number, windowMs: number): VRUTrack[] {
    const startTime = timestampMs - windowMs;
    const endTime = timestampMs + windowMs;
    const trackIds = new Set<string>();
    
    // Sample time points within window (every 100ms)
    for (let time = startTime; time <= endTime; time += 100) {
      const roundedTime = Math.floor(time / 100) * 100;
      const tracksAtTime = this.timeIndex.get(roundedTime);
      if (tracksAtTime) {
        tracksAtTime.forEach(id => trackIds.add(id));
      }
    }
    
    return Array.from(trackIds)
      .map(id => this.trackMap.get(id))
      .filter((track): track is VRUTrack => track !== undefined);
  }
  
  indexTrack(track: VRUTrack): void {
    this.trackMap.set(track.trackId, track);
    
    // Index each frame timestamp
    track.frameAnnotations.forEach((annotation, frameNum) => {
      const roundedTime = Math.floor(annotation.timestampMs / 100) * 100;
      if (!this.timeIndex.has(roundedTime)) {
        this.timeIndex.set(roundedTime, new Set());
      }
      this.timeIndex.get(roundedTime)!.add(track.trackId);
    });
  }
  
  removeTrack(trackId: string): void {
    const track = this.trackMap.get(trackId);
    if (track) {
      // Remove from time index
      track.frameAnnotations.forEach((annotation) => {
        const roundedTime = Math.floor(annotation.timestampMs / 100) * 100;
        const tracksAtTime = this.timeIndex.get(roundedTime);
        if (tracksAtTime) {
          tracksAtTime.delete(trackId);
          if (tracksAtTime.size === 0) {
            this.timeIndex.delete(roundedTime);
          }
        }
      });
      
      this.trackMap.delete(trackId);
    }
  }
}

/**
 * Main VRU Track Management System
 */
export class VRUTrackManager {
  private tracks: Map<string, VRUTrack> = new Map();
  private frameToTracks: Map<number, string[]> = new Map();
  private temporalIndex: TemporalIndex;
  
  constructor(private config: VRUTrackConfig) {
    this.temporalIndex = new SimpleTemporalIndex();
  }
  
  /**
   * Convert frame-based annotations to persistent tracks
   * This is the core method that solves the VRU ID consistency problem
   */
  async buildTracksFromAnnotations(
    videoId: string, 
    annotations: GroundTruthAnnotation[]
  ): Promise<Map<string, VRUTrack>> {
    
    console.log(`Building tracks from ${annotations.length} annotations for video ${videoId}`);
    
    // Group annotations by spatial-temporal proximity
    const annotationClusters = this.clusterAnnotationsByProximity(annotations);
    console.log(`Created ${annotationClusters.length} annotation clusters`);
    
    // Convert clusters to tracks
    const tracks = new Map<string, VRUTrack>();
    
    for (const cluster of annotationClusters) {
      if (cluster.length >= this.config.minTrackLength) {
        const track = await this.createTrackFromCluster(videoId, cluster);
        tracks.set(track.trackId, track);
        
        // Index for fast temporal lookups
        this.temporalIndex.indexTrack(track);
        
        console.log(`Created track ${track.trackId} with ${cluster.length} annotations`);
      }
    }
    
    this.tracks = tracks;
    return tracks;
  }
  
  /**
   * Spatial-temporal clustering of frame annotations into tracks
   * Solves the problem where same VRU gets different IDs each frame
   */
  private clusterAnnotationsByProximity(
    annotations: GroundTruthAnnotation[]
  ): GroundTruthAnnotation[][] {
    
    // Sort by frame number and VRU type
    const sortedAnnotations = annotations
      .filter(ann => ann.vruType) // Only VRU annotations
      .sort((a, b) => a.frameNumber - b.frameNumber);
    
    const clusters: GroundTruthAnnotation[][] = [];
    const processed = new Set<string>();
    
    for (const annotation of sortedAnnotations) {
      if (processed.has(annotation.id)) continue;
      
      const cluster = this.findTemporalCluster(annotation, sortedAnnotations, processed);
      if (cluster.length > 0) {
        clusters.push(cluster);
      }
    }
    
    return clusters;
  }
  
  /**
   * Find all annotations belonging to same VRU across frames
   * Uses spatial overlap and motion consistency
   */
  private findTemporalCluster(
    seedAnnotation: GroundTruthAnnotation,
    allAnnotations: GroundTruthAnnotation[],
    processed: Set<string>
  ): GroundTruthAnnotation[] {
    
    const cluster: GroundTruthAnnotation[] = [seedAnnotation];
    processed.add(seedAnnotation.id);
    
    let currentFrame = seedAnnotation.frameNumber;
    let currentBbox = seedAnnotation.bbox;
    
    // Forward tracking - find subsequent frames with same VRU
    for (let frameOffset = 1; frameOffset <= this.config.maxFrameGap; frameOffset++) {
      const nextFrame = currentFrame + frameOffset;
      const candidates = allAnnotations.filter(ann => 
        ann.frameNumber === nextFrame && 
        ann.vruType === seedAnnotation.vruType &&
        !processed.has(ann.id)
      );
      
      // Find best spatial match
      const bestMatch = this.findBestSpatialMatch(currentBbox, candidates);
      if (bestMatch && this.isValidTemporalMatch(currentBbox, bestMatch.bbox, frameOffset)) {
        cluster.push(bestMatch);
        processed.add(bestMatch.id);
        currentBbox = bestMatch.bbox;
        currentFrame = nextFrame;
      } else {
        break; // No valid continuation found
      }
    }
    
    return cluster;
  }
  
  /**
   * Spatial matching based on IoU and motion consistency
   */
  private findBestSpatialMatch(
    referenceBbox: BoundingBox,
    candidates: GroundTruthAnnotation[]
  ): GroundTruthAnnotation | null {
    
    let bestMatch: GroundTruthAnnotation | null = null;
    let bestScore = this.config.minSpatialOverlap;
    
    for (const candidate of candidates) {
      const iou = this.calculateIoU(referenceBbox, candidate.bbox);
      const motionScore = this.calculateMotionConsistency(referenceBbox, candidate.bbox);
      const compositeScore = (iou * 0.7) + (motionScore * 0.3); // Weighted combination
      
      if (compositeScore > bestScore) {
        bestMatch = candidate;
        bestScore = compositeScore;
      }
    }
    
    return bestMatch;
  }
  
  /**
   * Calculate Intersection over Union for spatial overlap
   */
  private calculateIoU(bbox1: BoundingBox, bbox2: BoundingBox): number {
    const x1 = Math.max(bbox1.x, bbox2.x);
    const y1 = Math.max(bbox1.y, bbox2.y);
    const x2 = Math.min(bbox1.x + bbox1.width, bbox2.x + bbox2.width);
    const y2 = Math.min(bbox1.y + bbox1.height, bbox2.y + bbox2.height);
    
    if (x2 <= x1 || y2 <= y1) return 0;
    
    const intersection = (x2 - x1) * (y2 - y1);
    const area1 = bbox1.width * bbox1.height;
    const area2 = bbox2.width * bbox2.height;
    const union = area1 + area2 - intersection;
    
    return intersection / union;
  }
  
  /**
   * Calculate motion consistency score
   */
  private calculateMotionConsistency(bbox1: BoundingBox, bbox2: BoundingBox): number {
    const center1 = { x: bbox1.x + bbox1.width / 2, y: bbox1.y + bbox1.height / 2 };
    const center2 = { x: bbox2.x + bbox2.width / 2, y: bbox2.y + bbox2.height / 2 };
    
    const distance = Math.sqrt(
      Math.pow(center2.x - center1.x, 2) + Math.pow(center2.y - center1.y, 2)
    );
    
    // Normalize by bbox size
    const avgSize = (bbox1.width + bbox1.height + bbox2.width + bbox2.height) / 4;
    const normalizedDistance = distance / avgSize;
    
    // Return inverse distance (closer = higher score)
    return Math.max(0, 1.0 - normalizedDistance);
  }
  
  /**
   * Validate temporal match based on reasonable motion constraints
   */
  private isValidTemporalMatch(
    bbox1: BoundingBox, 
    bbox2: BoundingBox, 
    frameGap: number
  ): boolean {
    const maxPixelsPerFrame = 50; // Maximum reasonable movement per frame
    const maxMovement = maxPixelsPerFrame * frameGap;
    
    const center1 = { x: bbox1.x + bbox1.width / 2, y: bbox1.y + bbox1.height / 2 };
    const center2 = { x: bbox2.x + bbox2.width / 2, y: bbox2.y + bbox2.height / 2 };
    
    const distance = Math.sqrt(
      Math.pow(center2.x - center1.x, 2) + Math.pow(center2.y - center1.y, 2)
    );
    
    return distance <= maxMovement;
  }
  
  /**
   * Create VRU track from annotation cluster
   */
  private async createTrackFromCluster(
    videoId: string,
    cluster: GroundTruthAnnotation[]
  ): Promise<VRUTrack> {
    
    const trackId = `${videoId}_vru_${this.generateTrackId()}`;
    const sortedCluster = cluster.sort((a, b) => a.frameNumber - b.frameNumber);
    
    // Build frame annotations map
    const frameAnnotations = new Map<number, FrameAnnotation>();
    for (const annotation of sortedCluster) {
      frameAnnotations.set(annotation.frameNumber, {
        frameNumber: annotation.frameNumber,
        timestampMs: this.frameToTimestamp(annotation.frameNumber),
        bbox: annotation.bbox,
        detectionConfidence: annotation.confidence || 0.8,
        annotationId: annotation.id,
        quality: this.assessAnnotationQuality(annotation)
      });
    }
    
    // Calculate trajectory
    const trajectory = this.calculateTrajectory(frameAnnotations);
    
    return {
      trackId,
      vruType: sortedCluster[0].vruType!,
      birthFrame: sortedCluster[0].frameNumber,
      deathFrame: sortedCluster[sortedCluster.length - 1].frameNumber,
      currentState: TrackState.ACTIVE,
      confidence: this.calculateTrackConfidence(sortedCluster),
      frameAnnotations,
      trajectory,
      averageSpeed: this.calculateAverageSpeed(trajectory.positions),
      directionConsistency: this.calculateDirectionConsistency(trajectory.velocities),
      occlusionDuration: this.calculateOcclusionDuration(sortedCluster),
      signalMatches: [],
      lastMatchTimestamp: 0,
      matchSuccess: false
    };
  }
  
  /**
   * Calculate smooth trajectory from frame annotations
   */
  private calculateTrajectory(frameAnnotations: Map<number, FrameAnnotation>) {
    const positions: Point2D[] = [];
    const velocities: Vector2D[] = [];
    
    const sortedFrames = Array.from(frameAnnotations.keys()).sort((a, b) => a - b);
    
    for (const frameNum of sortedFrames) {
      const annotation = frameAnnotations.get(frameNum)!;
      const center = {
        x: annotation.bbox.x + annotation.bbox.width / 2,
        y: annotation.bbox.y + annotation.bbox.height / 2
      };
      positions.push(center);
      
      // Calculate velocity if we have previous position
      if (positions.length > 1) {
        const prev = positions[positions.length - 2];
        const velocity = {
          dx: center.x - prev.x,
          dy: center.y - prev.y
        };
        velocities.push(velocity);
      }
    }
    
    // Simple smoothing (could use Kalman filter for better results)
    const smoothedPath = this.applySmoothingFilter(positions);
    const predictedPath = this.predictFuturePath(positions, velocities);
    
    return {
      positions,
      velocities,
      smoothedPath,
      predictedPath
    };
  }
  
  private applySmoothingFilter(positions: Point2D[]): Point2D[] {
    if (positions.length <= 2) return [...positions];
    
    const smoothed: Point2D[] = [positions[0]]; // Keep first position
    
    // Simple moving average smoothing
    for (let i = 1; i < positions.length - 1; i++) {
      const avg = {
        x: (positions[i - 1].x + positions[i].x + positions[i + 1].x) / 3,
        y: (positions[i - 1].y + positions[i].y + positions[i + 1].y) / 3
      };
      smoothed.push(avg);
    }
    
    smoothed.push(positions[positions.length - 1]); // Keep last position
    return smoothed;
  }
  
  private predictFuturePath(positions: Point2D[], velocities: Vector2D[]): Point2D[] {
    if (positions.length === 0 || velocities.length === 0) return [];
    
    const lastPosition = positions[positions.length - 1];
    const averageVelocity = {
      dx: velocities.reduce((sum, v) => sum + v.dx, 0) / velocities.length,
      dy: velocities.reduce((sum, v) => sum + v.dy, 0) / velocities.length
    };
    
    // Predict next 5 positions
    const predicted: Point2D[] = [];
    for (let i = 1; i <= 5; i++) {
      predicted.push({
        x: lastPosition.x + (averageVelocity.dx * i),
        y: lastPosition.y + (averageVelocity.dy * i)
      });
    }
    
    return predicted;
  }
  
  /**
   * Get tracks active at specific timestamp for HIL matching
   */
  getTracksAtTimestamp(timestampMs: number, windowMs: number = 100): VRUTrack[] {
    return this.temporalIndex.getTracksInWindow(timestampMs, windowMs);
  }
  
  /**
   * Update track with HIL signal match result
   */
  updateTrackWithSignalMatch(trackId: string, match: HILSignalMatch): void {
    const track = this.tracks.get(trackId);
    if (track) {
      track.signalMatches.push(match);
      track.lastMatchTimestamp = match.actualSignalTimestampMs;
      track.matchSuccess = match.outcome === DetectionOutcome.PASS;
      this.tracks.set(trackId, track);
    }
  }
  
  // Helper methods
  private frameToTimestamp(frameNumber: number, fps: number = 30): number {
    return (frameNumber / fps) * 1000; // Convert to milliseconds
  }
  
  private generateTrackId(): string {
    return Math.random().toString(36).substring(2, 15);
  }
  
  private calculateTrackConfidence(annotations: GroundTruthAnnotation[]): number {
    const avgConfidence = annotations.reduce((sum, ann) => sum + (ann.confidence || 0.8), 0) / annotations.length;
    const lengthBonus = Math.min(0.2, annotations.length / 10 * 0.2); // Bonus for longer tracks
    return Math.min(1.0, avgConfidence + lengthBonus);
  }
  
  private assessAnnotationQuality(annotation: GroundTruthAnnotation): AnnotationQuality {
    return {
      spatialStability: 0.8, // Would calculate based on bbox consistency
      temporalConsistency: 0.8, // Would calculate based on motion smoothness
      overallScore: 0.8
    };
  }
  
  private calculateAverageSpeed(positions: Point2D[]): number {
    if (positions.length < 2) return 0;
    
    let totalDistance = 0;
    for (let i = 1; i < positions.length; i++) {
      const distance = Math.sqrt(
        Math.pow(positions[i].x - positions[i-1].x, 2) +
        Math.pow(positions[i].y - positions[i-1].y, 2)
      );
      totalDistance += distance;
    }
    
    // Assuming 30 FPS, return pixels per second
    return (totalDistance / (positions.length - 1)) * 30;
  }
  
  private calculateDirectionConsistency(velocities: Vector2D[]): number {
    if (velocities.length < 2) return 1.0;
    
    let consistencySum = 0;
    for (let i = 1; i < velocities.length; i++) {
      const v1 = velocities[i - 1];
      const v2 = velocities[i];
      
      // Calculate angle between velocity vectors
      const dot = v1.dx * v2.dx + v1.dy * v2.dy;
      const mag1 = Math.sqrt(v1.dx * v1.dx + v1.dy * v1.dy);
      const mag2 = Math.sqrt(v2.dx * v2.dx + v2.dy * v2.dy);
      
      if (mag1 > 0 && mag2 > 0) {
        const cosAngle = dot / (mag1 * mag2);
        consistencySum += Math.max(0, cosAngle); // 1 = same direction, 0 = perpendicular, -1 = opposite
      }
    }
    
    return consistencySum / (velocities.length - 1);
  }
  
  private calculateOcclusionDuration(annotations: GroundTruthAnnotation[]): number {
    // Count frame gaps in the annotation sequence
    const sortedFrames = annotations.map(ann => ann.frameNumber).sort((a, b) => a - b);
    
    let occlusionFrames = 0;
    for (let i = 1; i < sortedFrames.length; i++) {
      const gap = sortedFrames[i] - sortedFrames[i - 1] - 1; // -1 because consecutive frames have gap 0
      occlusionFrames += Math.max(0, gap);
    }
    
    return occlusionFrames;
  }
  
  /**
   * Get all tracks
   */
  getAllTracks(): Map<string, VRUTrack> {
    return new Map(this.tracks);
  }
  
  /**
   * Get track by ID
   */
  getTrack(trackId: string): VRUTrack | undefined {
    return this.tracks.get(trackId);
  }
  
  /**
   * Get track statistics
   */
  getTrackStatistics() {
    const tracks = Array.from(this.tracks.values());
    
    return {
      totalTracks: tracks.length,
      activeTracksCount: tracks.filter(t => t.currentState === TrackState.ACTIVE).length,
      averageTrackLength: tracks.reduce((sum, t) => sum + t.frameAnnotations.size, 0) / tracks.length,
      vruTypeCounts: tracks.reduce((counts, track) => {
        counts[track.vruType] = (counts[track.vruType] || 0) + 1;
        return counts;
      }, {} as Record<VRUType, number>),
      tracksWithHILMatches: tracks.filter(t => t.matchSuccess).length,
      averageTrackConfidence: tracks.reduce((sum, t) => sum + t.confidence, 0) / tracks.length
    };
  }
}