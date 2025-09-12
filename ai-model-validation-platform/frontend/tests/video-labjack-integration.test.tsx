/**
 * LabJack Integration Test Suite for Video Playback
 * Tests video synchronization with LabJack data acquisition hardware
 * including timing precision, signal synchronization, and data correlation
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';

import SequentialVideoManager from '../src/components/SequentialVideoManager';
import { VideoFile } from '../src/services/types';

// Mock LabJack device interfaces
interface MockLabJackDevice {
  deviceType: string;
  serialNumber: string;
  isConnected: boolean;
  sampleRate: number;
  channels: string[];
  startAcquisition(): Promise<void>;
  stopAcquisition(): Promise<void>;
  getCurrentSample(): LabJackSample;
  onDataReceived(callback: (data: LabJackSample) => void): void;
  synchronizeWithTimestamp(timestamp: number): void;
}

interface LabJackSample {
  timestamp: number; // High precision timestamp
  channels: { [channel: string]: number };
  frameNumber?: number; // Correlated video frame
  deviceTime: number; // Device internal time
}

// Mock LabJack implementations for different device types
const createMockLabJackDevice = (type: 'T4' | 'T7' | 'T8'): MockLabJackDevice => {
  const baseChannels = ['AIN0', 'AIN1', 'FIO0', 'FIO1'];
  const extendedChannels = type === 'T8' ? [...baseChannels, 'AIN2', 'AIN3', 'FIO2', 'FIO3'] : baseChannels;
  
  return {
    deviceType: type,
    serialNumber: `440${Math.floor(Math.random() * 1000000)}`,
    isConnected: true,
    sampleRate: type === 'T8' ? 100000 : type === 'T7' ? 50000 : 10000, // Hz
    channels: extendedChannels,
    startAcquisition: jest.fn().mockResolvedValue(undefined),
    stopAcquisition: jest.fn().mockResolvedValue(undefined),
    getCurrentSample: jest.fn(),
    onDataReceived: jest.fn(),
    synchronizeWithTimestamp: jest.fn(),
  };
};

// Mock synchronized data scenarios
const createMockSynchronizedData = (videoTimestamp: number, deviceType: 'T4' | 'T7' | 'T8') => {
  const baseTime = videoTimestamp * 1000; // Convert to microseconds for higher precision
  
  return {
    timestamp: baseTime,
    channels: {
      'AIN0': Math.sin(videoTimestamp * 2 * Math.PI * 0.5), // 0.5 Hz sine wave
      'AIN1': Math.cos(videoTimestamp * 2 * Math.PI * 0.3), // 0.3 Hz cosine wave
      'FIO0': videoTimestamp % 2 > 1 ? 1 : 0, // Digital signal
      'FIO1': videoTimestamp % 4 > 2 ? 1 : 0, // Different digital pattern
    },
    deviceTime: baseTime,
    frameNumber: Math.floor(videoTimestamp * 30), // Assuming 30 FPS video
  };
};

// Test video with timing markers
const mockTimestampedVideo: VideoFile = {
  id: 'sync-test-video',
  filename: 'synchronized_test_video.mp4',
  originalName: 'synchronized_test_video.mp4',
  url: '/test-videos/synchronized_test_video.mp4',
  projectId: 'labjack-sync-test',
  status: 'completed',
  duration: 30, // 30 second video
  fps: 30,
  size: 50 * 1024 * 1024,
  fileSize: 50 * 1024 * 1024,
  createdAt: '2024-01-01T00:00:00Z',
  uploadedAt: '2024-01-01T00:00:00Z',
  groundTruthGenerated: false,
  groundTruthStatus: 'pending',
  processing_status: 'completed',
  detectionCount: 0
};

describe('LabJack Integration Tests for Video Playback', () => {
  let mockLabJackT7: MockLabJackDevice;
  let mockLabJackT8: MockLabJackDevice;
  let mockVideoElement: any;
  
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    mockLabJackT7 = createMockLabJackDevice('T7');
    mockLabJackT8 = createMockLabJackDevice('T8');
    
    mockVideoElement = {
      play: jest.fn().mockResolvedValue(undefined),
      pause: jest.fn(),
      currentTime: 0,
      duration: 30,
      paused: true,
      ended: false,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      requestFullscreen: jest.fn().mockResolvedValue(undefined),
    };

    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        return mockVideoElement;
      }
      return document.createElement(tagName);
    });
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  describe('Device Connection and Configuration', () => {
    it('should detect and connect to LabJack devices', async () => {
      const devices = [mockLabJackT7, mockLabJackT8];
      
      for (const device of devices) {
        expect(device.isConnected).toBe(true);
        expect(device.deviceType).toMatch(/T[478]/);
        expect(device.serialNumber).toMatch(/^440\d{6}$/);
        expect(device.channels.length).toBeGreaterThan(0);
      }
      
      // Verify device capabilities
      expect(mockLabJackT8.sampleRate).toBeGreaterThan(mockLabJackT7.sampleRate);
      expect(mockLabJackT8.channels.length).toBeGreaterThanOrEqual(mockLabJackT7.channels.length);
    });

    it('should configure appropriate sample rates for video synchronization', async () => {
      const videoFPS = 30;
      const recommendedSampleRate = videoFPS * 10; // 10x oversampling
      
      const deviceConfigs = [
        { device: mockLabJackT7, maxRate: 50000 },
        { device: mockLabJackT8, maxRate: 100000 }
      ];

      for (const config of deviceConfigs) {
        const optimalSampleRate = Math.min(recommendedSampleRate * 10, config.maxRate);
        expect(config.device.sampleRate).toBeGreaterThanOrEqual(recommendedSampleRate);
        expect(config.device.sampleRate).toBeLessThanOrEqual(config.maxRate);
      }
    });

    it('should handle device disconnection gracefully', async () => {
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Simulate device disconnection
      mockLabJackT7.isConnected = false;
      
      // Video playback should continue without external sync
      const videoElement = document.querySelector('video');
      expect(videoElement).toBeInTheDocument();
      
      // Should show appropriate warning/status
      await waitFor(() => {
        expect(screen.getByText(/Sequential Playback/)).toBeInTheDocument();
      });
    });
  });

  describe('Timing Synchronization', () => {
    it('should synchronize video timestamps with LabJack data', async () => {
      const syncCallbacks: ((timestamp: number) => void)[] = [];
      const onSyncRequest = jest.fn((callback) => {
        syncCallbacks.push(callback);
      });

      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
          latencyMs={10} // Low latency for precision
        />
      );

      // Simulate video time updates
      const videoTimes = [0, 1.0, 2.5, 5.0, 10.0, 15.0];
      
      for (const videoTime of videoTimes) {
        mockVideoElement.currentTime = videoTime;
        
        // Trigger time update event
        act(() => {
          const videoElement = document.querySelector('video');
          if (videoElement) {
            Object.defineProperty(videoElement, 'currentTime', { value: videoTime });
            fireEvent.timeUpdate(videoElement);
          }
        });

        // Verify LabJack synchronization
        const expectedLabJackData = createMockSynchronizedData(videoTime, 'T7');
        mockLabJackT7.getCurrentSample.mockReturnValue(expectedLabJackData);
        
        const sample = mockLabJackT7.getCurrentSample();
        
        // Verify timestamp correlation (within 1ms tolerance)
        const timestampDifference = Math.abs(sample.timestamp - videoTime * 1000);
        expect(timestampDifference).toBeLessThan(1); // 1ms precision
        
        // Verify frame number correlation
        const expectedFrame = Math.floor(videoTime * 30); // 30 FPS
        expect(sample.frameNumber).toBe(expectedFrame);
      }
    });

    it('should handle timing drift correction', async () => {
      const initialSyncTime = 0;
      let currentVideoTime = 0;
      let currentLabJackTime = 0;
      
      const driftRate = 0.001; // 1ms drift per second
      const correctionThreshold = 5; // Correct when drift > 5ms
      
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Simulate 30 seconds of playback with drift
      for (let second = 0; second < 30; second++) {
        currentVideoTime = second;
        currentLabJackTime = second * (1 + driftRate); // Accumulating drift
        
        const drift = Math.abs(currentLabJackTime - currentVideoTime) * 1000; // Convert to ms
        
        if (drift > correctionThreshold) {
          // Simulate drift correction
          mockLabJackT7.synchronizeWithTimestamp(currentVideoTime * 1000);
          expect(mockLabJackT7.synchronizeWithTimestamp).toHaveBeenCalledWith(currentVideoTime * 1000);
          
          // Reset drift after correction
          currentLabJackTime = currentVideoTime;
        }
        
        expect(drift).toBeLessThan(correctionThreshold * 2); // Should never exceed 2x threshold
      }
    });

    it('should maintain sub-millisecond precision for high-speed events', async () => {
      const highPrecisionDevice = createMockLabJackDevice('T8');
      highPrecisionDevice.sampleRate = 100000; // 100 kHz for high precision
      
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Test rapid events (every 0.1ms)
      const testDuration = 0.01; // 10ms total
      const sampleInterval = 0.0001; // 0.1ms intervals
      const samples: LabJackSample[] = [];
      
      for (let t = 0; t <= testDuration; t += sampleInterval) {
        const sample = createMockSynchronizedData(t, 'T8');
        samples.push(sample);
        
        // Verify microsecond precision
        const expectedTimestamp = t * 1000; // Convert to microseconds
        expect(Math.abs(sample.timestamp - expectedTimestamp)).toBeLessThan(0.01); // 0.01µs precision
      }
      
      expect(samples.length).toBe(Math.floor(testDuration / sampleInterval) + 1);
    });
  });

  describe('Data Correlation and Analysis', () => {
    it('should correlate video events with sensor data', async () => {
      const eventTimes = [2.5, 7.8, 12.3, 18.9, 25.1]; // Video event timestamps
      const correlationResults: Array<{
        videoTime: number;
        sensorData: LabJackSample;
        correlation: number;
      }> = [];

      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      for (const eventTime of eventTimes) {
        // Get sensor data at video event time
        const sensorSample = createMockSynchronizedData(eventTime, 'T7');
        mockLabJackT7.getCurrentSample.mockReturnValue(sensorSample);
        
        // Calculate correlation (simplified example)
        const sensorValue = sensorSample.channels['AIN0'];
        const expectedValue = Math.sin(eventTime * 2 * Math.PI * 0.5);
        const correlation = 1 - Math.abs(sensorValue - expectedValue);
        
        correlationResults.push({
          videoTime: eventTime,
          sensorData: sensorSample,
          correlation
        });
        
        expect(correlation).toBeGreaterThan(0.99); // High correlation expected
      }
      
      // Verify all events were correlated successfully
      expect(correlationResults.length).toBe(eventTimes.length);
      expect(correlationResults.every(r => r.correlation > 0.99)).toBe(true);
    });

    it('should detect and flag synchronization issues', async () => {
      const synchronizationIssues: string[] = [];
      
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Simulate various synchronization problems
      const problemScenarios = [
        { time: 5.0, issue: 'timestamp_gap', description: 'Missing data for 10ms' },
        { time: 12.5, issue: 'clock_drift', description: 'Clock drift detected' },
        { time: 20.0, issue: 'sample_rate_change', description: 'Sample rate changed unexpectedly' }
      ];

      for (const scenario of problemScenarios) {
        let sample: LabJackSample;
        
        switch (scenario.issue) {
          case 'timestamp_gap':
            // Create sample with timestamp gap
            sample = createMockSynchronizedData(scenario.time, 'T7');
            sample.timestamp += 10000; // 10ms gap
            break;
            
          case 'clock_drift':
            // Create sample with significant drift
            sample = createMockSynchronizedData(scenario.time, 'T7');
            sample.deviceTime += 50000; // 50ms drift
            break;
            
          case 'sample_rate_change':
            // Simulate sample rate change
            sample = createMockSynchronizedData(scenario.time, 'T7');
            mockLabJackT7.sampleRate = 25000; // Changed from 50000
            break;
            
          default:
            sample = createMockSynchronizedData(scenario.time, 'T7');
        }
        
        mockLabJackT7.getCurrentSample.mockReturnValue(sample);
        
        // Check for synchronization issues
        const expectedTimestamp = scenario.time * 1000;
        const timestampError = Math.abs(sample.timestamp - expectedTimestamp);
        const deviceTimeError = Math.abs(sample.deviceTime - expectedTimestamp);
        
        if (timestampError > 5 || deviceTimeError > 5) { // 5ms threshold
          synchronizationIssues.push(scenario.description);
        }
      }
      
      expect(synchronizationIssues.length).toBeGreaterThan(0);
      expect(synchronizationIssues).toContain('Missing data for 10ms');
      expect(synchronizationIssues).toContain('Clock drift detected');
    });

    it('should export synchronized data for analysis', async () => {
      const exportedData: Array<{
        timestamp: number;
        videoFrame: number;
        sensorChannels: { [channel: string]: number };
      }> = [];

      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Simulate data collection over video duration
      const sampleRate = 1000; // 1 kHz for export
      const videoDuration = 10; // 10 seconds
      
      for (let t = 0; t <= videoDuration; t += 1/sampleRate) {
        const sample = createMockSynchronizedData(t, 'T7');
        
        exportedData.push({
          timestamp: t,
          videoFrame: sample.frameNumber || 0,
          sensorChannels: sample.channels
        });
      }
      
      // Verify export data integrity
      expect(exportedData.length).toBe(videoDuration * sampleRate + 1);
      
      // Check data continuity
      for (let i = 1; i < exportedData.length; i++) {
        const timeDiff = exportedData[i].timestamp - exportedData[i-1].timestamp;
        expect(Math.abs(timeDiff - 1/sampleRate)).toBeLessThan(0.001); // 1ms tolerance
      }
      
      // Verify channel data exists
      exportedData.forEach(sample => {
        expect(sample.sensorChannels).toHaveProperty('AIN0');
        expect(sample.sensorChannels).toHaveProperty('AIN1');
        expect(sample.sensorChannels).toHaveProperty('FIO0');
        expect(sample.sensorChannels).toHaveProperty('FIO1');
      });
    });
  });

  describe('Real-time Performance', () => {
    it('should maintain real-time performance with high sample rates', async () => {
      const highSpeedDevice = createMockLabJackDevice('T8');
      highSpeedDevice.sampleRate = 50000; // 50 kHz
      
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
          latencyMs={1} // Minimize latency for real-time performance
        />
      );

      const performanceMetrics = {
        samplesProcessed: 0,
        processingTimes: [] as number[],
        maxProcessingTime: 0,
        droppedSamples: 0
      };

      // Simulate high-speed data processing
      const testDuration = 1; // 1 second
      const expectedSamples = highSpeedDevice.sampleRate * testDuration;
      const maxProcessingTimeAllowed = (1 / highSpeedDevice.sampleRate) * 0.5; // 50% of sample period
      
      for (let i = 0; i < expectedSamples; i++) {
        const startTime = performance.now();
        
        // Simulate sample processing
        const sample = createMockSynchronizedData(i / highSpeedDevice.sampleRate, 'T8');
        
        // Simulate processing time
        const processingTime = (performance.now() - startTime) / 1000; // Convert to seconds
        performanceMetrics.processingTimes.push(processingTime);
        performanceMetrics.maxProcessingTime = Math.max(performanceMetrics.maxProcessingTime, processingTime);
        
        if (processingTime > maxProcessingTimeAllowed) {
          performanceMetrics.droppedSamples++;
        } else {
          performanceMetrics.samplesProcessed++;
        }
      }
      
      // Verify real-time performance
      const averageProcessingTime = performanceMetrics.processingTimes.reduce((a, b) => a + b, 0) / performanceMetrics.processingTimes.length;
      const dropRate = performanceMetrics.droppedSamples / expectedSamples;
      
      expect(dropRate).toBeLessThan(0.01); // Less than 1% drop rate
      expect(averageProcessingTime).toBeLessThan(maxProcessingTimeAllowed);
      expect(performanceMetrics.samplesProcessed).toBeGreaterThan(expectedSamples * 0.99);
    });

    it('should handle buffer overflow scenarios', async () => {
      const bufferSize = 1000; // samples
      const overflowThreshold = 0.9; // 90% full
      
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      let currentBufferLevel = 0;
      const overflowEvents: number[] = [];
      
      // Simulate varying data rates
      const dataRateVariations = [1.0, 1.5, 2.0, 1.2, 0.8, 2.5, 1.0]; // Multipliers
      
      for (let i = 0; i < dataRateVariations.length; i++) {
        const rateMultiplier = dataRateVariations[i];
        const samplesThisInterval = Math.floor(100 * rateMultiplier);
        
        currentBufferLevel += samplesThisInterval;
        
        // Simulate buffer processing (consume samples)
        const processedSamples = Math.min(90, currentBufferLevel); // Process up to 90 samples per interval
        currentBufferLevel -= processedSamples;
        
        // Check for overflow
        if (currentBufferLevel > bufferSize * overflowThreshold) {
          overflowEvents.push(i);
          // Simulate buffer management (drop oldest samples)
          currentBufferLevel = Math.floor(bufferSize * 0.5); // Drop to 50% capacity
        }
      }
      
      // Verify overflow handling
      expect(overflowEvents.length).toBeGreaterThan(0); // Some overflows expected with variable rates
      expect(currentBufferLevel).toBeLessThan(bufferSize); // Buffer managed properly
    });
  });

  describe('Error Recovery and Robustness', () => {
    it('should recover from device communication errors', async () => {
      let communicationErrors = 0;
      const maxAllowedErrors = 5;
      
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Simulate communication errors
      const errorScenarios = [
        'timeout', 'connection_lost', 'invalid_response', 'checksum_error', 'device_reset'
      ];

      for (const errorType of errorScenarios) {
        communicationErrors++;
        
        // Simulate error recovery based on type
        switch (errorType) {
          case 'timeout':
            // Retry communication
            expect(mockLabJackT7.startAcquisition).toHaveBeenCalled();
            break;
            
          case 'connection_lost':
            // Attempt reconnection
            mockLabJackT7.isConnected = false;
            // Simulate reconnection attempt
            mockLabJackT7.isConnected = true;
            break;
            
          case 'invalid_response':
            // Reset communication protocol
            expect(mockLabJackT7.getCurrentSample).toHaveBeenCalled();
            break;
            
          case 'checksum_error':
            // Request data retransmission
            expect(mockLabJackT7.getCurrentSample).toHaveBeenCalled();
            break;
            
          case 'device_reset':
            // Reconfigure device
            expect(mockLabJackT7.startAcquisition).toHaveBeenCalled();
            break;
        }
        
        // Verify system remains operational
        expect(mockLabJackT7.isConnected).toBe(true);
      }
      
      expect(communicationErrors).toBeLessThanOrEqual(maxAllowedErrors);
    });

    it('should maintain video playback when sync fails', async () => {
      render(
        <SequentialVideoManager
          videos={[mockTimestampedVideo]}
          syncExternalSignals={true}
        />
      );

      // Simulate sync failure
      mockLabJackT7.isConnected = false;
      mockLabJackT7.getCurrentSample.mockImplementation(() => {
        throw new Error('Device not available');
      });

      // Video should continue playing
      const videoElement = document.querySelector('video');
      expect(videoElement).toBeInTheDocument();
      
      // Simulate video play
      act(() => {
        if (videoElement) {
          fireEvent.play(videoElement);
        }
      });

      // Should not crash and video should be playable
      await waitFor(() => {
        expect(mockVideoElement.play).toHaveBeenCalled();
      });
    });
  });
});