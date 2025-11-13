/**
 * Frontend Integration Test: Detection WebSocket Reception
 * =======================================================
 *
 * Tests that frontend properly receives and processes detection events
 * from WebSocket, updates state, and triggers UI re-renders.
 *
 * CRITICAL FIX: Verifies video_id filtering prevents showing wrong detections.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { io, Socket } from 'socket.io-client';
import { useWebSocket } from '../hooks/useWebSocket';
import { DetectionEvent } from '../types/detection';

// Mock socket.io-client
jest.mock('socket.io-client');

describe('Detection WebSocket Reception', () => {
  let mockSocket: jest.Mocked<Socket>;

  beforeEach(() => {
    // Create mock socket
    mockSocket = {
      on: jest.fn(),
      emit: jest.fn(),
      off: jest.fn(),
      connect: jest.fn(),
      disconnect: jest.fn(),
      connected: true,
    } as any;

    (io as jest.Mock).mockReturnValue(mockSocket);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('receives detection event and updates state', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Mock detection event
    const mockDetection: DetectionEvent = {
      id: 'det-001',
      test_session_id: 'test-session-001',
      video_id: 'video-001',
      timestamp: 1234567890.123,
      labjack_timestamp: 1234567890.123,
      labjack_voltage: 3.3,
      channel: 0,
      actual_latency_ms: 123.4,
      validation_result: 'Pass',
      video_relative_timestamp: 5.9,
      video_frame_number: 177,
    };

    // Simulate WebSocket emission
    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        detectionHandler(mockDetection);
      }
    });

    // Wait for state update
    await waitFor(() => {
      expect(result.current.detections).toHaveLength(1);
    });

    // Verify detection stored correctly
    expect(result.current.detections[0]).toEqual(mockDetection);
  });

  test('filters detections by video_id', async () => {
    const { result } = renderHook(() =>
      useWebSocket('test-session-001', { video_id: 'video-001' })
    );

    // Mock detection for correct video
    const correctDetection: DetectionEvent = {
      id: 'det-001',
      test_session_id: 'test-session-001',
      video_id: 'video-001',
      timestamp: 1234567890.0,
      validation_result: 'Pass',
    } as DetectionEvent;

    // Mock detection for different video (should be filtered)
    const wrongDetection: DetectionEvent = {
      id: 'det-002',
      test_session_id: 'test-session-001',
      video_id: 'video-002',
      timestamp: 1234567891.0,
      validation_result: 'Pass',
    } as DetectionEvent;

    // Simulate WebSocket emissions
    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        detectionHandler(correctDetection);
        detectionHandler(wrongDetection);
      }
    });

    // Wait for state update
    await waitFor(() => {
      expect(result.current.detections).toHaveLength(1);
    });

    // Verify only correct video's detection stored
    expect(result.current.detections[0].video_id).toBe('video-001');
  });

  test('updates detection count in real-time', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Initial count should be 0
    expect(result.current.detectionCount).toBe(0);

    // Simulate multiple detections
    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        for (let i = 0; i < 5; i++) {
          detectionHandler({
            id: `det-${i}`,
            test_session_id: 'test-session-001',
            video_id: 'video-001',
            timestamp: 1234567890.0 + i,
            validation_result: 'Pass',
          });
        }
      }
    });

    // Wait for state update
    await waitFor(() => {
      expect(result.current.detectionCount).toBe(5);
    });
  });

  test('maintains detection order by timestamp', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Simulate out-of-order detections
    const detections = [
      { id: 'det-2', timestamp: 1234567892.0 },
      { id: 'det-1', timestamp: 1234567891.0 },
      { id: 'det-3', timestamp: 1234567893.0 },
    ];

    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        detections.forEach(det => {
          detectionHandler({
            ...det,
            test_session_id: 'test-session-001',
            video_id: 'video-001',
            validation_result: 'Pass',
          });
        });
      }
    });

    // Wait for state update
    await waitFor(() => {
      expect(result.current.detections).toHaveLength(3);
    });

    // Verify sorted by timestamp
    const timestamps = result.current.detections.map(d => d.timestamp);
    expect(timestamps).toEqual([1234567891.0, 1234567892.0, 1234567893.0]);
  });

  test('handles multi-video sequence detections', async () => {
    const { result } = renderHook(() =>
      useWebSocket('test-session-001', { sequence_id: 'seq-001' })
    );

    // Mock sequence detection
    const sequenceDetection: DetectionEvent = {
      id: 'det-seq-001',
      test_session_id: 'test-session-001',
      video_id: 'video-002',
      sequence_id: 'seq-001',
      sequence_timestamp: 35.5,
      video_play_offset_ms: 30000.0,
      timestamp: 1234567890.0,
      validation_result: 'Pass',
    } as DetectionEvent;

    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        detectionHandler(sequenceDetection);
      }
    });

    await waitFor(() => {
      expect(result.current.detections).toHaveLength(1);
    });

    // Verify sequence metadata
    const detection = result.current.detections[0];
    expect(detection.sequence_id).toBe('seq-001');
    expect(detection.sequence_timestamp).toBe(35.5);
    expect(detection.video_play_offset_ms).toBe(30000.0);
  });

  test('subscribes to correct room on mount', () => {
    renderHook(() => useWebSocket('test-session-001'));

    // Verify subscription to session room
    expect(mockSocket.emit).toHaveBeenCalledWith(
      'subscribe_to_updates',
      expect.objectContaining({
        type: 'session',
        target_id: 'test-session-001',
      })
    );
  });

  test('unsubscribes on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket('test-session-001'));

    unmount();

    // Verify cleanup
    expect(mockSocket.off).toHaveBeenCalledWith('detection_event');
  });

  test('handles connection errors gracefully', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Simulate connection error
    act(() => {
      const errorHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'connect_error'
      )?.[1];

      if (errorHandler) {
        errorHandler(new Error('Connection failed'));
      }
    });

    // Should set error state
    await waitFor(() => {
      expect(result.current.connectionError).toBeTruthy();
    });
  });

  test('reconnects automatically after disconnect', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Simulate disconnect
    act(() => {
      mockSocket.connected = false;
      const disconnectHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'disconnect'
      )?.[1];

      if (disconnectHandler) {
        disconnectHandler();
      }
    });

    // Wait for reconnection attempt
    await waitFor(() => {
      expect(mockSocket.connect).toHaveBeenCalled();
    });
  });

  test('updates pass/fail statistics', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Simulate detections with mixed results
    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        // 3 Pass, 2 Fail
        ['Pass', 'Pass', 'Fail', 'Pass', 'Fail'].forEach((result, i) => {
          detectionHandler({
            id: `det-${i}`,
            test_session_id: 'test-session-001',
            video_id: 'video-001',
            timestamp: 1234567890.0 + i,
            validation_result: result,
          });
        });
      }
    });

    await waitFor(() => {
      expect(result.current.passCount).toBe(3);
      expect(result.current.failCount).toBe(2);
      expect(result.current.passRate).toBeCloseTo(0.6);
    });
  });

  test('calculates average latency', async () => {
    const { result } = renderHook(() => useWebSocket('test-session-001'));

    // Simulate detections with varying latency
    const latencies = [100.0, 150.0, 120.0, 110.0, 130.0];

    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        latencies.forEach((latency, i) => {
          detectionHandler({
            id: `det-${i}`,
            test_session_id: 'test-session-001',
            video_id: 'video-001',
            timestamp: 1234567890.0 + i,
            actual_latency_ms: latency,
            validation_result: 'Pass',
          });
        });
      }
    });

    await waitFor(() => {
      const avgLatency = result.current.averageLatency;
      const expectedAvg = latencies.reduce((a, b) => a + b) / latencies.length;
      expect(avgLatency).toBeCloseTo(expectedAvg);
    });
  });

  test('triggers UI callbacks on detection', async () => {
    const onDetection = jest.fn();

    renderHook(() =>
      useWebSocket('test-session-001', { onDetection })
    );

    // Simulate detection
    act(() => {
      const detectionHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'detection_event'
      )?.[1];

      if (detectionHandler) {
        detectionHandler({
          id: 'det-001',
          test_session_id: 'test-session-001',
          video_id: 'video-001',
          timestamp: 1234567890.0,
          validation_result: 'Pass',
        });
      }
    });

    // Verify callback triggered
    await waitFor(() => {
      expect(onDetection).toHaveBeenCalledTimes(1);
    });
  });
});
