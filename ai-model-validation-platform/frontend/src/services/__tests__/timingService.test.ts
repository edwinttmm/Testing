/**
 * Unit tests for TimingService
 */

import { TimingService } from '../timingService';
import type { TimingServiceConfig } from '../../types/timing.types';

// Mock ClockSyncService
jest.mock('../clockSyncService', () => ({
  ClockSyncService: jest.fn().mockImplementation(() => ({
    connect: jest.fn().mockResolvedValue(undefined),
    disconnect: jest.fn(),
    getOffset: jest.fn(() => 50),
    getLatestSync: jest.fn(() => ({
      offset: 50,
      rtt: 10,
      accuracy: 5,
      calculatedAt: Date.now(),
      isValid: true,
    })),
    isHealthy: jest.fn(() => true),
    getSyncHistory: jest.fn(() => []),
  })),
}));

// Mock WebSocket
class MockWebSocket {
  public readyState = WebSocket.CONNECTING;
  public onopen: (() => void) | null = null;
  public onclose: (() => void) | null = null;
  public onerror: ((error: any) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  private messages: string[] = [];

  constructor(public url: string) {
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) this.onopen();
    }, 0);
  }

  send(data: string): void {
    this.messages.push(data);
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose();
  }

  getMessages(): string[] {
    return [...this.messages];
  }
}

describe('TimingService', () => {
  let service: TimingService;
  let mockWebSocket: MockWebSocket;
  const config: TimingServiceConfig = {
    syncInterval: 30000,
    maxRTT: 200,
    syncSamples: 5,
    wsEndpoint: 'ws://localhost:3000',
  };

  beforeEach(() => {
    global.WebSocket = MockWebSocket as any;

    global.performance = {
      now: jest.fn(() => 1000),
      timeOrigin: 1600000000000,
      getEntriesByType: jest.fn(() => []),
    } as any;

    Object.defineProperty(document, 'visibilityState', {
      writable: true,
      value: 'visible',
    });

    service = new TimingService(config);
  });

  afterEach(() => {
    service.shutdown();
    jest.clearAllTimers();
  });

  describe('Initialization', () => {
    it('should initialize successfully', async () => {
      await service.initialize();
      expect(service.getClockSyncStatus().isHealthy).toBe(true);
    });

    it('should handle initialization errors', async () => {
      global.WebSocket = class {
        constructor() {
          setTimeout(() => {
            if (this.onerror) this.onerror(new Error('Connection failed'));
          }, 0);
        }
        onerror: any;
      } as any;

      const newService = new TimingService(config);
      await expect(newService.initialize()).rejects.toThrow();
    });
  });

  describe('Video Registration', () => {
    let mockVideo: HTMLVideoElement;

    beforeEach(async () => {
      await service.initialize();
      mockVideo = document.createElement('video');
      mockVideo.addEventListener = jest.fn();
      mockVideo.removeEventListener = jest.fn();
    });

    it('should register video element', () => {
      service.registerVideo('video-1', mockVideo);
      expect(mockVideo.addEventListener).toHaveBeenCalledTimes(9); // 9 events
    });

    it('should unregister video element', () => {
      service.registerVideo('video-1', mockVideo);
      service.unregisterVideo('video-1');
      expect(mockVideo.removeEventListener).toHaveBeenCalledTimes(9);
    });

    it('should handle multiple videos', () => {
      const mockVideo2 = document.createElement('video');
      mockVideo2.addEventListener = jest.fn();

      service.registerVideo('video-1', mockVideo);
      service.registerVideo('video-2', mockVideo2);

      expect(mockVideo.addEventListener).toHaveBeenCalledTimes(9);
      expect(mockVideo2.addEventListener).toHaveBeenCalledTimes(9);
    });
  });

  describe('Video Event Capture', () => {
    let mockVideo: HTMLVideoElement;

    beforeEach(async () => {
      await service.initialize();
      mockWebSocket = (service as any).ws as MockWebSocket;
      mockVideo = document.createElement('video');

      // Setup video properties
      Object.defineProperties(mockVideo, {
        readyState: { value: 4, writable: true },
        currentTime: { value: 0, writable: true },
        duration: { value: 60, writable: true },
        networkState: { value: 2, writable: true },
      });
    });

    it('should capture playing event', () => {
      service.registerVideo('video-1', mockVideo);

      // Trigger playing event
      const playingEvent = new Event('playing');
      mockVideo.dispatchEvent(playingEvent);

      // Check that timing event was sent
      const messages = mockWebSocket.getMessages();
      const lastMessage = JSON.parse(messages[messages.length - 1]);

      expect(lastMessage.type).toBe('video_timing_event');
      expect(lastMessage.payload.event.event).toBe('playing');
      expect(lastMessage.payload.event.videoId).toBe('video-1');
    });

    it('should capture high-precision timestamp', () => {
      service.registerVideo('video-1', mockVideo);

      const playingEvent = new Event('playing');
      mockVideo.dispatchEvent(playingEvent);

      const messages = mockWebSocket.getMessages();
      const lastMessage = JSON.parse(messages[messages.length - 1]);
      const timing = lastMessage.payload.event.timing;

      expect(timing).toHaveProperty('timestamp');
      expect(timing).toHaveProperty('timeOrigin');
      expect(timing).toHaveProperty('absolute');
      expect(timing).toHaveProperty('clockOffset');
      expect(timing).toHaveProperty('adjusted');
      expect(timing.adjusted).toBeGreaterThan(timing.absolute);
    });

    it('should include video state in event', () => {
      service.registerVideo('video-1', mockVideo);

      const playingEvent = new Event('playing');
      mockVideo.dispatchEvent(playingEvent);

      const messages = mockWebSocket.getMessages();
      const lastMessage = JSON.parse(messages[messages.length - 1]);
      const event = lastMessage.payload.event;

      expect(event.readyState).toBe(4);
      expect(event.currentTime).toBe(0);
      expect(event.duration).toBe(60);
      expect(event.networkState).toBe(2);
    });

    it('should include metadata', () => {
      service.registerVideo('video-1', mockVideo);

      const playingEvent = new Event('playing');
      mockVideo.dispatchEvent(playingEvent);

      const messages = mockWebSocket.getMessages();
      const lastMessage = JSON.parse(messages[messages.length - 1]);
      const metadata = lastMessage.payload;

      expect(metadata).toHaveProperty('userAgent');
      expect(metadata).toHaveProperty('tabVisible');
      expect(metadata).toHaveProperty('wasThrottled');
      expect(metadata).toHaveProperty('wsLatency');
    });
  });

  describe('Clock Sync Status', () => {
    beforeEach(async () => {
      await service.initialize();
    });

    it('should return clock sync status', () => {
      const status = service.getClockSyncStatus();

      expect(status).toHaveProperty('offset');
      expect(status).toHaveProperty('isHealthy');
      expect(status).toHaveProperty('latestSync');
      expect(status).toHaveProperty('history');
    });
  });

  describe('WebSocket Latency', () => {
    beforeEach(async () => {
      await service.initialize();
      mockWebSocket = (service as any).ws as MockWebSocket;
    });

    it('should track WebSocket latency', () => {
      // Initially 0
      expect(service.getWebSocketLatency()).toBe(0);

      // Simulate pong response
      (performance.now as jest.Mock).mockReturnValue(1050);
      mockWebSocket.simulateMessage = (data: any) => {
        if (mockWebSocket.onmessage) {
          const event = new MessageEvent('message', {
            data: JSON.stringify(data),
          });
          mockWebSocket.onmessage(event);
        }
      };

      mockWebSocket.simulateMessage({ type: 'pong' });

      expect(service.getWebSocketLatency()).toBeGreaterThan(0);
    });
  });

  describe('Shutdown', () => {
    it('should cleanup all resources', async () => {
      await service.initialize();
      const mockVideo = document.createElement('video');
      mockVideo.removeEventListener = jest.fn();

      service.registerVideo('video-1', mockVideo);
      service.shutdown();

      expect(mockVideo.removeEventListener).toHaveBeenCalled();
    });
  });

  describe('Visibility Monitoring', () => {
    beforeEach(async () => {
      await service.initialize();
    });

    it('should detect tab visibility changes', () => {
      const consoleSpy = jest.spyOn(console, 'log');

      Object.defineProperty(document, 'visibilityState', {
        writable: true,
        value: 'hidden',
      });

      document.dispatchEvent(new Event('visibilitychange'));

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Tab visibility: hidden')
      );
    });
  });
});
