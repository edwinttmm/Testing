/**
 * Unit tests for ClockSyncService
 */

import { ClockSyncService } from '../clockSyncService';
import type { TimingServiceConfig } from '../../types/timing.types';

// Mock WebSocket
class MockWebSocket {
  public readyState = WebSocket.CONNECTING;
  public onopen: (() => void) | null = null;
  public onclose: (() => void) | null = null;
  public onerror: ((error: any) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  private messages: string[] = [];

  constructor(public url: string) {
    // Simulate connection after a tick
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

  simulateMessage(data: any): void {
    if (this.onmessage) {
      const event = new MessageEvent('message', {
        data: JSON.stringify(data),
      });
      this.onmessage(event);
    }
  }
}

describe('ClockSyncService', () => {
  let service: ClockSyncService;
  let mockWebSocket: MockWebSocket;
  const config: TimingServiceConfig = {
    syncInterval: 30000,
    maxRTT: 200,
    syncSamples: 5,
    wsEndpoint: 'ws://localhost:3000',
  };

  beforeEach(() => {
    // Mock WebSocket globally
    global.WebSocket = MockWebSocket as any;

    // Mock performance API
    global.performance = {
      now: jest.fn(() => 1000),
      timeOrigin: 1600000000000,
    } as any;

    service = new ClockSyncService(config);
  });

  afterEach(() => {
    service.disconnect();
    jest.clearAllTimers();
  });

  describe('Connection', () => {
    it('should connect to WebSocket successfully', async () => {
      await service.connect(config.wsEndpoint);
      expect(service.isHealthy()).toBe(false); // No sync yet
    });

    it('should handle connection errors', async () => {
      global.WebSocket = class {
        constructor() {
          setTimeout(() => {
            if (this.onerror) this.onerror(new Error('Connection failed'));
          }, 0);
        }
        onerror: any;
      } as any;

      await expect(service.connect(config.wsEndpoint)).rejects.toThrow();
    });
  });

  describe('Clock Synchronization', () => {
    beforeEach(async () => {
      await service.connect(config.wsEndpoint);
      mockWebSocket = (service as any).ws as MockWebSocket;
    });

    it('should send clock sync request on connect', () => {
      const messages = mockWebSocket.getMessages();
      expect(messages.length).toBeGreaterThan(0);

      const request = JSON.parse(messages[0]);
      expect(request.type).toBe('clock_sync_request');
      expect(request.payload).toHaveProperty('clientTimestamp');
      expect(request.payload).toHaveProperty('sequence');
    });

    it('should calculate offset from sync response', () => {
      const now = performance.now() + performance.timeOrigin;
      const serverTime = now + 100; // Server is 100ms ahead

      mockWebSocket.simulateMessage({
        type: 'clock_sync_response',
        payload: {
          clientTimestamp: now,
          serverTimestamp: serverTime,
          serverSendTimestamp: serverTime + 1,
          sequence: 0,
        },
      });

      // Should calculate offset close to 100ms
      const offset = service.getOffset();
      expect(offset).toBeCloseTo(100, 0);
    });

    it('should reject sync responses with high RTT', () => {
      const now = performance.now() + performance.timeOrigin;

      // Simulate high RTT by advancing time
      (performance.now as jest.Mock).mockReturnValue(2000); // +1000ms RTT

      mockWebSocket.simulateMessage({
        type: 'clock_sync_response',
        payload: {
          clientTimestamp: now,
          serverTimestamp: now + 50,
          serverSendTimestamp: now + 51,
          sequence: 0,
        },
      });

      // Should not update offset due to high RTT
      expect(service.getLatestSync()).toBeNull();
    });

    it('should use weighted average for offset calculation', () => {
      const now = performance.now() + performance.timeOrigin;

      // Send multiple sync responses
      for (let i = 0; i < 3; i++) {
        mockWebSocket.simulateMessage({
          type: 'clock_sync_response',
          payload: {
            clientTimestamp: now,
            serverTimestamp: now + 100 + i * 10, // Varying offsets
            serverSendTimestamp: now + 101 + i * 10,
            sequence: i,
          },
        });
      }

      const offset = service.getOffset();
      expect(offset).toBeGreaterThan(100);
      expect(offset).toBeLessThan(120);
    });
  });

  describe('Health Monitoring', () => {
    beforeEach(async () => {
      await service.connect(config.wsEndpoint);
      mockWebSocket = (service as any).ws as MockWebSocket;
    });

    it('should report unhealthy when no sync performed', () => {
      expect(service.isHealthy()).toBe(false);
    });

    it('should report healthy after successful sync', () => {
      const now = performance.now() + performance.timeOrigin;

      mockWebSocket.simulateMessage({
        type: 'clock_sync_response',
        payload: {
          clientTimestamp: now,
          serverTimestamp: now + 50,
          serverSendTimestamp: now + 51,
          sequence: 0,
        },
      });

      expect(service.isHealthy()).toBe(true);
    });

    it('should report unhealthy when sync is stale', () => {
      const now = performance.now() + performance.timeOrigin;

      mockWebSocket.simulateMessage({
        type: 'clock_sync_response',
        payload: {
          clientTimestamp: now,
          serverTimestamp: now + 50,
          serverSendTimestamp: now + 51,
          sequence: 0,
        },
      });

      // Advance time beyond 2x sync interval
      (performance.now as jest.Mock).mockReturnValue(70000);

      expect(service.isHealthy()).toBe(false);
    });
  });

  describe('Timestamp Adjustment', () => {
    beforeEach(async () => {
      await service.connect(config.wsEndpoint);
      mockWebSocket = (service as any).ws as MockWebSocket;

      // Perform sync to set offset
      const now = performance.now() + performance.timeOrigin;
      mockWebSocket.simulateMessage({
        type: 'clock_sync_response',
        payload: {
          clientTimestamp: now,
          serverTimestamp: now + 100,
          serverSendTimestamp: now + 101,
          sequence: 0,
        },
      });
    });

    it('should adjust timestamps with clock offset', () => {
      const localTime = 5000;
      const adjusted = service.getAdjustedTimestamp(localTime);

      expect(adjusted).toBeGreaterThan(localTime);
      expect(adjusted - localTime).toBeCloseTo(100, 0);
    });

    it('should provide current adjusted timestamp', () => {
      const { local, adjusted, offset } = service.now();

      expect(adjusted).toBeGreaterThan(local);
      expect(adjusted - local).toBeCloseTo(offset, 0);
      expect(offset).toBeCloseTo(100, 0);
    });
  });

  describe('Callbacks', () => {
    beforeEach(async () => {
      await service.connect(config.wsEndpoint);
      mockWebSocket = (service as any).ws as MockWebSocket;
    });

    it('should trigger callback on sync', () => {
      const callback = jest.fn();
      service.onSync(callback);

      const now = performance.now() + performance.timeOrigin;
      mockWebSocket.simulateMessage({
        type: 'clock_sync_response',
        payload: {
          clientTimestamp: now,
          serverTimestamp: now + 50,
          serverSendTimestamp: now + 51,
          sequence: 0,
        },
      });

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          offset: expect.any(Number),
          rtt: expect.any(Number),
          accuracy: expect.any(Number),
          isValid: true,
        })
      );
    });
  });

  describe('Disconnect', () => {
    it('should cleanup on disconnect', async () => {
      await service.connect(config.wsEndpoint);
      mockWebSocket = (service as any).ws as MockWebSocket;

      service.disconnect();

      expect(mockWebSocket.readyState).toBe(WebSocket.CLOSED);
      expect((service as any).syncTimer).toBeNull();
    });
  });
});
