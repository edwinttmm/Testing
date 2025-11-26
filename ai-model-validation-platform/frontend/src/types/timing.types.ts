/**
 * High-precision timing types for video synchronization
 */

export interface HighPrecisionTimestamp {
  /** Timestamp in milliseconds with microsecond precision */
  timestamp: number;
  /** Performance API timeOrigin for absolute time */
  timeOrigin: number;
  /** Combined absolute timestamp */
  absolute: number;
  /** Local clock offset from server (ms) */
  clockOffset: number;
  /** Adjusted timestamp compensating for clock drift */
  adjusted: number;
}

export interface VideoTimingEvent {
  /** Video element ID */
  videoId: string;
  /** Event type */
  event: 'loading' | 'canplay' | 'playing' | 'pause' | 'ended' | 'error';
  /** High-precision timestamp */
  timing: HighPrecisionTimestamp;
  /** Video element ready state */
  readyState: number;
  /** Current time in video */
  currentTime: number;
  /** Video duration */
  duration: number;
  /** Network state */
  networkState: number;
}

export interface ClockSyncRequest {
  /** Client timestamp when ping sent */
  clientTimestamp: number;
  /** Sequence number for tracking */
  sequence: number;
}

export interface ClockSyncResponse {
  /** Original client timestamp */
  clientTimestamp: number;
  /** Server timestamp when received */
  serverTimestamp: number;
  /** Server timestamp when sent */
  serverSendTimestamp: number;
  /** Sequence number */
  sequence: number;
}

export interface ClockSyncResult {
  /** Calculated offset (ms) - add to local time to get server time */
  offset: number;
  /** Round-trip time (ms) */
  rtt: number;
  /** Estimated accuracy (ms) */
  accuracy: number;
  /** Timestamp when calculated */
  calculatedAt: number;
  /** Is sync valid */
  isValid: boolean;
}

export interface NetworkTimingMetadata {
  /** DNS lookup time */
  dnsLookupTime?: number;
  /** TCP connection time */
  tcpConnectionTime?: number;
  /** TLS negotiation time */
  tlsTime?: number;
  /** Time to first byte */
  ttfb?: number;
  /** Download time */
  downloadTime?: number;
  /** Total time */
  totalTime?: number;
}

export interface VideoTimingMetadata {
  /** Video timing event */
  event: VideoTimingEvent;
  /** Network timing from Navigation Timing API */
  networkTiming?: NetworkTimingMetadata;
  /** WebSocket latency (ms) */
  wsLatency?: number;
  /** Browser info */
  userAgent: string;
  /** Tab visibility state */
  tabVisible: boolean;
  /** Tab was throttled */
  wasThrottled: boolean;
}

export interface DriftStatus {
  /** Video ID */
  videoId: string;
  /** Current drift in ms */
  drift: number;
  /** Drift severity */
  severity: 'good' | 'warning' | 'critical';
  /** Clock offset */
  clockOffset: number;
  /** Compensation active */
  compensated: boolean;
  /** Last update timestamp */
  lastUpdate: number;
}

export interface TimingServiceConfig {
  /** Clock sync interval (ms) */
  syncInterval: number;
  /** Max acceptable RTT (ms) */
  maxRTT: number;
  /** Number of sync samples to average */
  syncSamples: number;
  /** WebSocket endpoint */
  wsEndpoint: string;
}
