/**
 * High-Precision Video Timing Service
 * Captures exact video start times and lifecycle events
 */

import type {
  HighPrecisionTimestamp,
  VideoTimingEvent,
  VideoTimingMetadata,
  NetworkTimingMetadata,
  TimingServiceConfig,
} from '../types/timing.types';
import { ClockSyncService } from './clockSyncService';

export class TimingService {
  private clockSync: ClockSyncService;
  private ws: WebSocket | null = null;
  private videoElements: Map<string, HTMLVideoElement> = new Map();
  private videoListeners: Map<string, Map<string, EventListener>> = new Map();
  private wsLatency: number = 0;
  private lastPingTime: number = 0;
  private config: TimingServiceConfig;
  private throttleDetected: boolean = false;
  private lastThrottleCheck: number = 0;

  constructor(config: TimingServiceConfig) {
    this.config = config;
    this.clockSync = new ClockSyncService(config);
    this.setupVisibilityMonitoring();
  }

  /**
   * Initialize timing service and connect to backend
   */
  public async initialize(): Promise<void> {
    try {
      // Connect clock sync (it manages its own WebSocket)
      await this.clockSync.connect(this.config.wsEndpoint);

      // Connect main WebSocket for timing events
      await this.connectWebSocket();

      // Setup periodic WebSocket latency checks
      this.startLatencyMonitoring();

      console.log('[TimingService] Initialized successfully');
    } catch (error) {
      console.error('[TimingService] Initialization failed:', error);
      throw error;
    }
  }

  /**
   * Connect WebSocket for timing events
   */
  private async connectWebSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.config.wsEndpoint);

        this.ws.onopen = () => {
          console.log('[TimingService] WebSocket connected');
          resolve();
        };

        this.ws.onerror = (error) => {
          console.error('[TimingService] WebSocket error:', error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('[TimingService] WebSocket closed, attempting reconnect...');
          this.handleDisconnect();
        };

        this.ws.onmessage = (event) => {
          this.handleWebSocketMessage(event);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Handle WebSocket disconnect with exponential backoff
   */
  private handleDisconnect(): void {
    let retryDelay = 1000;
    const maxRetryDelay = 30000;

    const attemptReconnect = () => {
      console.log(`[TimingService] Reconnecting in ${retryDelay}ms...`);

      setTimeout(async () => {
        try {
          await this.connectWebSocket();
          retryDelay = 1000; // Reset on success
        } catch (error) {
          retryDelay = Math.min(retryDelay * 2, maxRetryDelay);
          attemptReconnect();
        }
      }, retryDelay);
    };

    attemptReconnect();
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleWebSocketMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data);

      if (data.type === 'pong') {
        const now = performance.now() + performance.timeOrigin;
        this.wsLatency = now - this.lastPingTime;
        console.log(`[TimingService] WebSocket latency: ${this.wsLatency.toFixed(3)}ms`);
      }
    } catch (error) {
      console.error('[TimingService] Error handling WebSocket message:', error);
    }
  }

  /**
   * Start periodic WebSocket latency monitoring
   */
  private startLatencyMonitoring(): void {
    setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.lastPingTime = performance.now() + performance.timeOrigin;
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 5000); // Check every 5 seconds
  }

  /**
   * Register a video element for timing capture
   */
  public registerVideo(videoId: string, videoElement: HTMLVideoElement): void {
    this.videoElements.set(videoId, videoElement);

    const listeners = new Map<string, EventListener>();

    // Define all video events to track
    const events = [
      'loadstart',
      'canplay',
      'canplaythrough',
      'playing',  // Most reliable for actual playback start
      'pause',
      'ended',
      'error',
      'stalled',
      'waiting',
    ];

    events.forEach(eventName => {
      const listener = () => this.handleVideoEvent(videoId, eventName, videoElement);
      videoElement.addEventListener(eventName, listener);
      listeners.set(eventName, listener);
    });

    this.videoListeners.set(videoId, listeners);

    console.log(`[TimingService] Registered video: ${videoId}`);
  }

  /**
   * Unregister a video element
   */
  public unregisterVideo(videoId: string): void {
    const videoElement = this.videoElements.get(videoId);
    const listeners = this.videoListeners.get(videoId);

    if (videoElement && listeners) {
      listeners.forEach((listener, eventName) => {
        videoElement.removeEventListener(eventName, listener);
      });
    }

    this.videoElements.delete(videoId);
    this.videoListeners.delete(videoId);

    console.log(`[TimingService] Unregistered video: ${videoId}`);
  }

  /**
   * Handle video events and capture timing
   */
  private handleVideoEvent(
    videoId: string,
    eventName: string,
    videoElement: HTMLVideoElement
  ): void {
    const timing = this.captureHighPrecisionTimestamp();

    // Map event names to our event types
    let eventType: VideoTimingEvent['event'];
    switch (eventName) {
      case 'loadstart':
        eventType = 'loading';
        break;
      case 'canplay':
      case 'canplaythrough':
        eventType = 'canplay';
        break;
      case 'playing':
        eventType = 'playing';
        break;
      case 'pause':
        eventType = 'pause';
        break;
      case 'ended':
        eventType = 'ended';
        break;
      case 'error':
      case 'stalled':
        eventType = 'error';
        break;
      default:
        return; // Ignore other events
    }

    const event: VideoTimingEvent = {
      videoId,
      event: eventType,
      timing,
      readyState: videoElement.readyState,
      currentTime: videoElement.currentTime,
      duration: videoElement.duration || 0,
      networkState: videoElement.networkState,
    };

    // Check for throttling
    this.detectThrottling();

    // Create metadata
    const metadata: VideoTimingMetadata = {
      event,
      networkTiming: this.captureNetworkTiming(),
      wsLatency: this.wsLatency,
      userAgent: navigator.userAgent,
      tabVisible: document.visibilityState === 'visible',
      wasThrottled: this.throttleDetected,
    };

    // Send to backend immediately
    this.sendTimingEvent(metadata);

    console.log(`[TimingService] ${videoId} - ${eventType} at ${timing.adjusted.toFixed(3)}ms (offset: ${timing.clockOffset.toFixed(3)}ms)`);
  }

  /**
   * Capture high-precision timestamp with clock adjustment
   */
  private captureHighPrecisionTimestamp(): HighPrecisionTimestamp {
    const timestamp = performance.now();
    const timeOrigin = performance.timeOrigin;
    const absolute = timestamp + timeOrigin;
    const clockOffset = this.clockSync.getOffset();
    const adjusted = absolute + clockOffset;

    return {
      timestamp,
      timeOrigin,
      absolute,
      clockOffset,
      adjusted,
    };
  }

  /**
   * Capture network timing using Navigation Timing API
   */
  private captureNetworkTiming(): NetworkTimingMetadata | undefined {
    if (!performance.getEntriesByType) {
      return undefined;
    }

    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (!navigation) {
      return undefined;
    }

    return {
      dnsLookupTime: navigation.domainLookupEnd - navigation.domainLookupStart,
      tcpConnectionTime: navigation.connectEnd - navigation.connectStart,
      tlsTime: navigation.secureConnectionStart > 0
        ? navigation.connectEnd - navigation.secureConnectionStart
        : undefined,
      ttfb: navigation.responseStart - navigation.requestStart,
      downloadTime: navigation.responseEnd - navigation.responseStart,
      totalTime: navigation.responseEnd - navigation.fetchStart,
    };
  }

  /**
   * Detect browser tab throttling
   */
  private detectThrottling(): void {
    const now = performance.now();
    const expectedInterval = 100; // Check every 100ms

    if (this.lastThrottleCheck > 0) {
      const actualInterval = now - this.lastThrottleCheck;
      // If actual interval is much longer than expected, tab might be throttled
      if (actualInterval > expectedInterval * 2) {
        this.throttleDetected = true;
        console.warn(`[TimingService] Tab throttling detected: ${actualInterval.toFixed(2)}ms interval`);
      } else {
        this.throttleDetected = false;
      }
    }

    this.lastThrottleCheck = now;
  }

  /**
   * Setup visibility state monitoring
   */
  private setupVisibilityMonitoring(): void {
    document.addEventListener('visibilitychange', () => {
      const visible = document.visibilityState === 'visible';
      console.log(`[TimingService] Tab visibility: ${visible ? 'visible' : 'hidden'}`);

      if (!visible) {
        console.warn('[TimingService] Tab hidden - timing may be affected by throttling');
      }
    });
  }

  /**
   * Send timing event to backend
   */
  private sendTimingEvent(metadata: VideoTimingMetadata): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[TimingService] WebSocket not ready, queueing event');
      // TODO: Implement event queue for offline resilience
      return;
    }

    try {
      this.ws.send(JSON.stringify({
        type: 'video_timing_event',
        payload: metadata,
      }));
    } catch (error) {
      console.error('[TimingService] Error sending timing event:', error);
    }
  }

  /**
   * Get current clock sync status
   */
  public getClockSyncStatus() {
    return {
      offset: this.clockSync.getOffset(),
      isHealthy: this.clockSync.isHealthy(),
      latestSync: this.clockSync.getLatestSync(),
      history: this.clockSync.getSyncHistory(),
    };
  }

  /**
   * Get WebSocket latency
   */
  public getWebSocketLatency(): number {
    return this.wsLatency;
  }

  /**
   * Shutdown timing service
   */
  public shutdown(): void {
    // Unregister all videos
    this.videoElements.forEach((_, videoId) => {
      this.unregisterVideo(videoId);
    });

    // Disconnect WebSocket
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    // Disconnect clock sync
    this.clockSync.disconnect();

    console.log('[TimingService] Shutdown complete');
  }
}
