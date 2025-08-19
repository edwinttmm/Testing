import { VRUType } from '../services/types';

interface DetectionIdConfig {
  prefix: string;
  includeTimestamp: boolean;
  includeVRUType: boolean;
  sequenceLength: number;
  sessionId?: string;
}

interface DetectionTracker {
  id: string;
  vruType: VRUType;
  firstSeen: number; // frame number
  lastSeen: number; // frame number
  track: Array<{
    frame: number;
    timestamp: number;
    confidence: number;
    boundingBox: { x: number; y: number; width: number; height: number };
  }>;
  validated: boolean;
  notes?: string;
}

class DetectionIdManager {
  private sequences: Map<string, number> = new Map();
  private trackers: Map<string, DetectionTracker> = new Map();
  private config: DetectionIdConfig;
  
  constructor(config?: Partial<DetectionIdConfig>) {
    this.config = {
      prefix: 'DET',
      includeTimestamp: false,
      includeVRUType: true,
      sequenceLength: 4,
      ...config,
    };
  }

  /**
   * Generate a new detection ID
   */
  generateDetectionId(vruType: VRUType, frameNumber?: number): string {
    const vruPrefix = this.config.includeVRUType ? this.getVRUPrefix(vruType) : '';
    const key = `${this.config.prefix}_${vruPrefix}`;
    
    // Get or initialize sequence number
    const currentSequence = this.sequences.get(key) || 0;
    const nextSequence = currentSequence + 1;
    this.sequences.set(key, nextSequence);
    
    // Build detection ID
    let detectionId = `${this.config.prefix}`;
    
    if (this.config.includeVRUType) {
      detectionId += `_${vruPrefix}`;
    }
    
    // Add sequence number with padding
    const paddedSequence = nextSequence.toString().padStart(this.config.sequenceLength, '0');
    detectionId += `_${paddedSequence}`;
    
    // Add timestamp if requested
    if (this.config.includeTimestamp) {
      const timestamp = Date.now().toString(36).toUpperCase();
      detectionId += `_${timestamp}`;
    }
    
    // Add session ID if provided
    if (this.config.sessionId) {
      const sessionSuffix = this.config.sessionId.slice(-4).toUpperCase();
      detectionId += `_${sessionSuffix}`;
    }
    
    return detectionId;
  }

  /**
   * Get VRU type prefix for ID generation
   */
  private getVRUPrefix(vruType: VRUType): string {
    const prefixes = {
      pedestrian: 'PED',
      cyclist: 'CYC',
      motorcyclist: 'MOT',
      wheelchair_user: 'WHE',
      scooter_rider: 'SCO',
    };
    return prefixes[vruType] || 'UNK';
  }

  /**
   * Parse detection ID to extract information
   */
  parseDetectionId(detectionId: string): {
    prefix: string;
    vruType?: VRUType;
    sequence: number;
    timestamp?: string;
    sessionId?: string;
    isValid: boolean;
  } {
    try {
      const parts = detectionId.split('_');
      if (parts.length < 2) {
        return { prefix: detectionId, sequence: 0, isValid: false };
      }

      const prefix = parts[0];
      let partIndex = 1;
      let vruType: VRUType | undefined;
      let sequence = 0;
      let timestamp: string | undefined;
      let sessionId: string | undefined;

      // Check for VRU type
      if (this.config.includeVRUType && parts.length > partIndex) {
        const vruPrefix = parts[partIndex];
        vruType = this.getVRUTypeFromPrefix(vruPrefix);
        if (vruType) {
          partIndex++;
        }
      }

      // Get sequence number
      if (parts.length > partIndex) {
        sequence = parseInt(parts[partIndex], 10) || 0;
        partIndex++;
      }

      // Check for timestamp
      if (this.config.includeTimestamp && parts.length > partIndex) {
        timestamp = parts[partIndex];
        partIndex++;
      }

      // Check for session ID
      if (this.config.sessionId && parts.length > partIndex) {
        sessionId = parts[partIndex];
      }

      return {
        prefix,
        vruType,
        sequence,
        timestamp,
        sessionId,
        isValid: true,
      } as { prefix: string; vruType?: VRUType; sequence: number; timestamp?: string; sessionId?: string; isValid: boolean; };
    } catch (error) {
      return { prefix: detectionId, sequence: 0, isValid: false };
    }
  }

  /**
   * Get VRU type from prefix
   */
  private getVRUTypeFromPrefix(prefix: string): VRUType | undefined {
    const typeMap: Record<string, VRUType> = {
      PED: 'pedestrian',
      CYC: 'cyclist',
      MOT: 'motorcyclist',
      WHE: 'wheelchair_user',
      SCO: 'scooter_rider',
    };
    return typeMap[prefix];
  }

  /**
   * Create a new detection tracker
   */
  createTracker(
    detectionId: string,
    vruType: VRUType,
    frameNumber: number,
    timestamp: number,
    boundingBox: { x: number; y: number; width: number; height: number },
    confidence: number = 1.0
  ): DetectionTracker {
    const tracker: DetectionTracker = {
      id: detectionId,
      vruType,
      firstSeen: frameNumber,
      lastSeen: frameNumber,
      track: [{
        frame: frameNumber,
        timestamp,
        confidence,
        boundingBox: { ...boundingBox },
      }],
      validated: false,
    };

    this.trackers.set(detectionId, tracker);
    return tracker;
  }

  /**
   * Update an existing tracker with new detection data
   */
  updateTracker(
    detectionId: string,
    frameNumber: number,
    timestamp: number,
    boundingBox: { x: number; y: number; width: number; height: number },
    confidence: number = 1.0
  ): DetectionTracker | null {
    const tracker = this.trackers.get(detectionId);
    if (!tracker) {
      return null;
    }

    // Update last seen frame
    tracker.lastSeen = Math.max(tracker.lastSeen, frameNumber);

    // Add new track point
    tracker.track.push({
      frame: frameNumber,
      timestamp,
      confidence,
      boundingBox: { ...boundingBox },
    });

    // Sort track points by frame number
    tracker.track.sort((a, b) => a.frame - b.frame);

    return tracker;
  }

  /**
   * Get tracker by detection ID
   */
  getTracker(detectionId: string): DetectionTracker | undefined {
    return this.trackers.get(detectionId);
  }

  /**
   * Get all trackers
   */
  getAllTrackers(): DetectionTracker[] {
    return Array.from(this.trackers.values());
  }

  /**
   * Get trackers active in a frame range
   */
  getTrackersInRange(startFrame: number, endFrame: number): DetectionTracker[] {
    return Array.from(this.trackers.values()).filter(tracker =>
      tracker.firstSeen <= endFrame && tracker.lastSeen >= startFrame
    );
  }

  /**
   * Remove a tracker
   */
  removeTracker(detectionId: string): boolean {
    return this.trackers.delete(detectionId);
  }

  /**
   * Validate a detection
   */
  validateDetection(detectionId: string, validated: boolean = true): boolean {
    const tracker = this.trackers.get(detectionId);
    if (tracker) {
      tracker.validated = validated;
      return true;
    }
    return false;
  }

  /**
   * Add notes to a detection
   */
  addNotes(detectionId: string, notes: string): boolean {
    const tracker = this.trackers.get(detectionId);
    if (tracker) {
      tracker.notes = notes;
      return true;
    }
    return false;
  }

  /**
   * Get detection statistics
   */
  getStatistics(): {
    totalDetections: number;
    validatedDetections: number;
    detectionsByType: Record<VRUType, number>;
    averageTrackLength: number;
    longestTrack: number;
  } {
    const trackers = Array.from(this.trackers.values());
    const stats = {
      totalDetections: trackers.length,
      validatedDetections: trackers.filter(t => t.validated).length,
      detectionsByType: {} as Record<VRUType, number>,
      averageTrackLength: 0,
      longestTrack: 0,
    };

    // Count by type
    const vruTypes: VRUType[] = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair_user', 'scooter_rider'];
    vruTypes.forEach(type => {
      stats.detectionsByType[type] = trackers.filter(t => t.vruType === type).length;
    });

    // Calculate track statistics
    if (trackers.length > 0) {
      const trackLengths = trackers.map(t => t.track.length);
      stats.averageTrackLength = trackLengths.reduce((a, b) => a + b, 0) / trackLengths.length;
      stats.longestTrack = Math.max(...trackLengths);
    }

    return stats;
  }

  /**
   * Export trackers data
   */
  exportData(): {
    config: DetectionIdConfig;
    sequences: Record<string, number>;
    trackers: DetectionTracker[];
  } {
    return {
      config: { ...this.config },
      sequences: Object.fromEntries(this.sequences),
      trackers: Array.from(this.trackers.values()),
    };
  }

  /**
   * Import trackers data
   */
  importData(data: {
    config?: Partial<DetectionIdConfig>;
    sequences?: Record<string, number>;
    trackers?: DetectionTracker[];
  }): void {
    if (data.config) {
      this.config = { ...this.config, ...data.config };
    }

    if (data.sequences) {
      this.sequences = new Map(Object.entries(data.sequences));
    }

    if (data.trackers) {
      this.trackers.clear();
      data.trackers.forEach(tracker => {
        this.trackers.set(tracker.id, tracker);
      });
    }
  }

  /**
   * Clear all data
   */
  clear(): void {
    this.sequences.clear();
    this.trackers.clear();
  }

  /**
   * Reset sequences
   */
  resetSequences(): void {
    this.sequences.clear();
  }
}

// Create and export singleton instance
export const detectionIdManager = new DetectionIdManager();

// Export class for creating custom instances
export { DetectionIdManager };

// Export utility functions
export const generateDetectionId = (vruType: VRUType, frameNumber?: number) =>
  detectionIdManager.generateDetectionId(vruType, frameNumber);

export const createDetectionTracker = (
  detectionId: string,
  vruType: VRUType,
  frameNumber: number,
  timestamp: number,
  boundingBox: { x: number; y: number; width: number; height: number },
  confidence?: number
) => detectionIdManager.createTracker(detectionId, vruType, frameNumber, timestamp, boundingBox, confidence);

export const getDetectionTracker = (detectionId: string) =>
  detectionIdManager.getTracker(detectionId);

export const getAllDetectionTrackers = () =>
  detectionIdManager.getAllTrackers();

export const getDetectionStatistics = () =>
  detectionIdManager.getStatistics();

export default detectionIdManager;