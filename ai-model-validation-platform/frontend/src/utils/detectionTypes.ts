// Detection and HIL Testing Type Definitions

// Re-export VideoFile from services/types if needed
import type { VideoFile } from '../services/types';

export enum DetectionOutcome {
  PASS = 'PASS',
  FAIL = 'FAIL',
  PENDING = 'PENDING'
}

export interface DetectionEvent {
  id: string | number;
  videoId: number;
  expectedEventTime?: string;
  signalReceivedTime?: string;
  latencyMs?: number;
  outcome: DetectionOutcome;
  createdAt: string;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence?: number;
  classLabel?: string;
  vruType?: string;
}

export interface HardwareSignal {
  timestamp: number;
  voltage: number;
  channel: string;
  latency?: number;
  detected?: boolean;
}

export interface TimingMetrics {
  latency: number;
  responseTime: number;
  accuracy: number;
  jitter?: number;
  throughput?: number;
}

export interface ConnectionStatus {
  connected: boolean;
  latency: number;
  lastCheck?: Date;
  errorMessage?: string;
}

export interface HILTestConfiguration {
  maxLatencyMs: number;
  voltageThreshold: {
    lower: number;
    upper: number;
  };
  sampleRate: number;
  channels: string[];
  detectionWindowMs: number;
  autoAdvance: boolean;
  emergencyStopEnabled: boolean;
}

export interface VideoPlaylistItem extends VideoFile {
  order: number;
  processed: boolean;
  startTime?: Date;
  endTime?: Date;
  detectionCount: number;
}
export type { VideoFile };