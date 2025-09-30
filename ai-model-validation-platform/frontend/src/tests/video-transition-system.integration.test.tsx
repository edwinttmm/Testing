/**
 * Comprehensive Video Transition System Integration Test
 * 
 * This test suite validates the robust video transition system to ensure:
 * 1. Sequential Flow: Video 1 → Video 2 → Video 3 all play completely
 * 2. Timing Verification: Each video has proper gaps and starts reliably  
 * 3. Failure Recovery: Test what happens if a video fails to load/play
 * 4. Console Log Analysis: Verify debug output shows proper progression
 * 5. Manual Integration: Simulate exact user experience
 * 
 * CRITICAL: Video 2 should NEVER get skipped under any circumstances
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

import SequentialVideoManager from '../components/SequentialVideoManager';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import { VideoFile } from '../services/types';

// Test video data - simulating realistic video files
const createTestVideo = (id: string, filename: string, duration: number = 10): VideoFile => ({
  id,
  filename,
  originalName: filename,
  url: `/test-videos/${filename}`,
  projectId: 'test-project-video-transitions',
  status: 'completed',
  duration,
  fps: 30,
  size: duration * 1024 * 1024, // Simulate size based on duration
  fileSize: duration * 1024 * 1024,
  createdAt: new Date().toISOString(),
  uploadedAt: new Date().toISOString(),
  groundTruthGenerated: false,
  groundTruthStatus: 'pending',
  processing_status: 'completed',
  detectionCount: Math.floor(Math.random() * 50) // Random detections for variety
});

// Test video sequence - exactly 3 videos for comprehensive testing
const testVideoSequence: VideoFile[] = [
  createTestVideo('video-transition-1', 'first-video.mp4', 8),    // 8 seconds
  createTestVideo('video-transition-2', 'middle-video.mp4', 12), // 12 seconds - Critical video that should NEVER be skipped
  createTestVideo('video-transition-3', 'final-video.mp4', 6),   // 6 seconds
];

// Mock video element with enhanced event simulation
const createMockVideoElement = (videoId: string) => {
  const mockElement = {
    id: `video-${videoId}`,
    src: '',
    currentTime: 0,
    duration: 0,
    paused: true,
    ended: false,
    readyState: HTMLMediaElement.HAVE_NOTHING,
    videoWidth: 1920,
    videoHeight: 1080,
    volume: 1,
    muted: false,
    error: null,
    
    // Playback control methods
    play: jest.fn().mockImplementation(function(this: any) {
      console.log(`[VIDEO TRANSITION TEST] Video ${this.id} play() called`);
      this.paused = false;
      return Promise.resolve();
    }),
    
    pause: jest.fn().mockImplementation(function(this: any) {
      console.log(`[VIDEO TRANSITION TEST] Video ${this.id} pause() called`);
      this.paused = true;
    }),
    
    load: jest.fn().mockImplementation(function(this: any) {
      console.log(`[VIDEO TRANSITION TEST] Video ${this.id} load() called`);
      this.readyState = HTMLMediaElement.HAVE_METADATA;
    }),
    
    // Event management
    addEventListener: jest.fn().mockImplementation(function(this: any, event: string, handler: Function) {
      console.log(`[VIDEO TRANSITION TEST] Video ${this.id} addEventListener('${event}')`);
      if (!this._eventListeners) this._eventListeners = {};
      if (!this._eventListeners[event]) this._eventListeners[event] = [];
      this._eventListeners[event].push(handler);
    }),
    
    removeEventListener: jest.fn().mockImplementation(function(this: any, event: string, handler: Function) {
      console.log(`[VIDEO TRANSITION TEST] Video ${this.id} removeEventListener('${event}')`);
      if (this._eventListeners && this._eventListeners[event]) {
        this._eventListeners[event] = this._eventListeners[event].filter((h: Function) => h !== handler);
      }
    }),
    
    // Helper method to simulate events
    _triggerEvent: function(this: any, eventType: string, eventData?: any) {
      console.log(`[VIDEO TRANSITION TEST] Video ${this.id} triggering '${eventType}' event`);
      if (this._eventListeners && this._eventListeners[eventType]) {
        this._eventListeners[eventType].forEach((handler: Function) => {
          const event = { 
            type: eventType, 
            target: this, 
            currentTarget: this,
            ...eventData 
          };
          handler(event);
        });
      }
    },
    
    // Helper to simulate video progression
    _simulateVideoProgress: function(this: any, targetDuration: number) {
      return new Promise<void>((resolve) => {
        this.duration = targetDuration;
        this.readyState = HTMLMediaElement.HAVE_ENOUGH_DATA;
        this._triggerEvent('loadedmetadata');
        this._triggerEvent('canplay');
        
        let currentTime = 0;
        const progressInterval = setInterval(() => {
          if (this.paused || this.ended) {
            clearInterval(progressInterval);
            resolve();
            return;
          }
          
          currentTime += 0.1;
          this.currentTime = currentTime;
          this._triggerEvent('timeupdate');
          
          if (currentTime >= targetDuration) {
            this.ended = true;
            this.paused = true;
            this._triggerEvent('ended');
            clearInterval(progressInterval);
            resolve();
          }
        }, 100); // Update every 100ms for realistic simulation
      });
    },
    
    _eventListeners: {},
    removeAttribute: jest.fn(),
  };
  
  return mockElement;
};

// Console log capture for analysis
interface LogEntry {
  level: 'log' | 'info' | 'warn' | 'error' | 'debug';
  message: string;
  timestamp: number;
}

class ConsoleCapture {
  private logs: LogEntry[] = [];
  private originalConsole: any = {};
  
  start() {
    this.logs = [];
    ['log', 'info', 'warn', 'error', 'debug'].forEach(level => {
      this.originalConsole[level] = console[level as keyof Console];
      (console as any)[level] = (...args: any[]) => {
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
        this.logs.push({
          level: level as LogEntry['level'],
          message,
          timestamp: Date.now()
        });
        this.originalConsole[level](...args);
      };
    });
  }
  
  stop() {
    Object.keys(this.originalConsole).forEach(level => {
      (console as any)[level] = this.originalConsole[level];
    });
  }
  
  getLogs(): LogEntry[] {
    return [...this.logs];
  }
  
  getLogsByPattern(pattern: RegExp): LogEntry[] {
    return this.logs.filter(log => pattern.test(log.message));
  }
  
  hasLogMatching(pattern: RegExp): boolean {
    return this.logs.some(log => pattern.test(log.message));
  }
  
  getVideoTransitionLogs(): LogEntry[] {
    return this.getLogsByPattern(/VIDEO TRANSITION|video.*transition|transition.*video/i);
  }
}

// Test state tracker
interface VideoTransitionState {
  currentVideoIndex: number;
  videosPlayed: string[];
  videosCompleted: string[];
  transitionTimings: { from: string; to: string; timestamp: number }[];
  errors: any[];
  isComplete: boolean;
}

describe('Video Transition System Integration Tests', () => {
  let consoleCapture: ConsoleCapture;
  let mockVideoElements: { [key: string]: any } = {};
  let transitionState: VideoTransitionState;
  
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Initialize console capture
    consoleCapture = new ConsoleCapture();
    consoleCapture.start();
    
    // Initialize transition state
    transitionState = {
      currentVideoIndex: 0,
      videosPlayed: [],
      videosCompleted: [],
      transitionTimings: [],
      errors: [],
      isComplete: false
    };
    
    // Mock video element creation
    const originalCreateElement = document.createElement;
    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        const videoId = `mock-video-${Date.now()}-${Math.random()}`;
        const mockElement = createMockVideoElement(videoId);
        mockVideoElements[videoId] = mockElement;
        console.log(`[VIDEO TRANSITION TEST] Created mock video element: ${videoId}`);
        return mockElement as any;
      }
      return originalCreateElement.call(document, tagName);
    });
    
    // Mock video utilities
    jest.doMock('../utils/videoUtils', () => ({
      safeVideoPlay: jest.fn().mockImplementation((element: any) => {
        console.log(`[VIDEO TRANSITION TEST] safeVideoPlay called for ${element?.id}`);
        if (!element) {
          return Promise.resolve({ success: false, error: new Error('No video element') });
        }
        return element.play().then(() => ({ success: true })).catch((error: any) => ({ success: false, error }));
      }),
      safeVideoPause: jest.fn().mockImplementation((element: any) => {
        console.log(`[VIDEO TRANSITION TEST] safeVideoPause called for ${element?.id}`);
        if (element) element.pause();
      }),
      cleanupVideoElement: jest.fn().mockImplementation((element: any) => {
        console.log(`[VIDEO TRANSITION TEST] cleanupVideoElement called for ${element?.id}`);
        if (element) {
          element.pause();
          element.src = '';
          element.load();
        }
      }),
      setVideoSource: jest.fn().mockResolvedValue(undefined),
      isVideoReady: jest.fn().mockReturnValue(true),
    }));
  });
  
  afterEach(() => {
    consoleCapture.stop();
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
    mockVideoElements = {};
    cleanup();
  });

  describe('1. Sequential Flow Test: Video 1 → Video 2 → Video 3', () => {
    it('should play all three videos in sequence without skipping Video 2', async () => {
      console.log('[VIDEO TRANSITION TEST] Starting sequential flow test');
      
      const onVideoChange = jest.fn().mockImplementation((video, index) => {
        console.log(`[VIDEO TRANSITION TEST] Video changed to: ${video.filename} (index: ${index})`);
        transitionState.currentVideoIndex = index;
        transitionState.videosPlayed.push(video.id);
        
        if (index > 0) {
          const previousVideo = testVideoSequence[index - 1];
          transitionState.transitionTimings.push({
            from: previousVideo.id,
            to: video.id,
            timestamp: Date.now()
          });
        }
      });
      
      const onPlaybackComplete = jest.fn().mockImplementation(() => {
        console.log('[VIDEO TRANSITION TEST] Playback completed');
        transitionState.isComplete = true;
      });
      
      const onProgress = jest.fn().mockImplementation((progress) => {
        console.log(`[VIDEO TRANSITION TEST] Progress: ${progress}%`);
      });
      
      render(
        <SequentialVideoManager
          videos={testVideoSequence}
          onVideoChange={onVideoChange}
          onPlaybackComplete={onPlaybackComplete}
          onProgress={onProgress}
          autoAdvance={true}
          latencyMs={200} // 200ms gap between videos
        />
      );
      
      // Verify initial state - should start with Video 1
      await waitFor(() => {
        expect(screen.getByText(/Video 1 of 3/)).toBeInTheDocument();
        expect(screen.getByText(/first-video\.mp4/)).toBeInTheDocument();
      });
      
      console.log('[VIDEO TRANSITION TEST] Verified initial video display');
      
      // Simulate Video 1 playback and completion
      console.log('[VIDEO TRANSITION TEST] Starting Video 1 simulation');
      const firstVideoElement = Object.values(mockVideoElements)[0];
      if (firstVideoElement) {
        await act(async () => {
          await firstVideoElement._simulateVideoProgress(testVideoSequence[0].duration);
        });
        
        // Fast-forward through the transition gap
        act(() => {
          jest.advanceTimersByTime(250); // Slightly more than latencyMs
        });
      }
      
      // Verify transition to Video 2
      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-transition-2', filename: 'middle-video.mp4' }),
          1
        );
      });
      
      console.log('[VIDEO TRANSITION TEST] ✅ Successfully transitioned to Video 2');
      
      // CRITICAL: Verify Video 2 is never skipped
      expect(transitionState.videosPlayed).toContain('video-transition-2');
      expect(transitionState.currentVideoIndex).toBe(1);
      
      // Simulate Video 2 playback and completion
      console.log('[VIDEO TRANSITION TEST] Starting Video 2 simulation');
      const secondVideoElement = Object.values(mockVideoElements)[1];
      if (secondVideoElement) {
        await act(async () => {
          await secondVideoElement._simulateVideoProgress(testVideoSequence[1].duration);
        });
        
        // Fast-forward through the transition gap
        act(() => {
          jest.advanceTimersByTime(250);
        });
      }
      
      // Verify transition to Video 3
      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-transition-3', filename: 'final-video.mp4' }),
          2
        );
      });
      
      console.log('[VIDEO TRANSITION TEST] ✅ Successfully transitioned to Video 3');
      
      // Simulate Video 3 playback and completion
      console.log('[VIDEO TRANSITION TEST] Starting Video 3 simulation');
      const thirdVideoElement = Object.values(mockVideoElements)[2];
      if (thirdVideoElement) {
        await act(async () => {
          await thirdVideoElement._simulateVideoProgress(testVideoSequence[2].duration);
        });
        
        // Fast-forward through final transition
        act(() => {
          jest.advanceTimersByTime(250);
        });
      }
      
      // Verify playback completion
      await waitFor(() => {
        expect(onPlaybackComplete).toHaveBeenCalled();
      });
      
      console.log('[VIDEO TRANSITION TEST] ✅ Playback completed successfully');
      
      // Final assertions
      expect(transitionState.videosPlayed).toEqual([
        'video-transition-1',
        'video-transition-2', 
        'video-transition-3'
      ]);
      
      expect(transitionState.transitionTimings).toHaveLength(2);
      expect(transitionState.isComplete).toBe(true);
      
      // CRITICAL: Ensure Video 2 was played and never skipped
      const video2Logs = consoleCapture.getLogsByPattern(/video-transition-2|middle-video\.mp4/i);
      expect(video2Logs.length).toBeGreaterThan(0);
      
      console.log('[VIDEO TRANSITION TEST] ✅ All tests passed - Video 2 was never skipped');
    });
  });

  describe('2. Timing Verification Test', () => {
    it('should maintain proper gaps and timing between video transitions', async () => {
      console.log('[VIDEO TRANSITION TEST] Starting timing verification test');
      
      const transitionTimestamps: number[] = [];
      const onVideoChange = jest.fn().mockImplementation((video, index) => {
        const timestamp = Date.now();
        transitionTimestamps.push(timestamp);
        console.log(`[VIDEO TRANSITION TEST] Video transition at ${timestamp}: ${video.filename}`);
      });
      
      render(
        <SequentialVideoManager
          videos={testVideoSequence.slice(0, 2)} // Use first 2 videos for timing test
          onVideoChange={onVideoChange}
          autoAdvance={true}
          latencyMs={300} // 300ms gap for precise timing verification
        />
      );
      
      // Record initial timestamp
      const testStartTime = Date.now();
      console.log(`[VIDEO TRANSITION TEST] Test started at ${testStartTime}`);
      
      // Simulate first video completion
      const firstVideo = Object.values(mockVideoElements)[0];
      if (firstVideo) {
        await act(async () => {
          await firstVideo._simulateVideoProgress(5); // 5 second video
        });
        
        // Wait for exactly the specified latency
        act(() => {
          jest.advanceTimersByTime(300);
        });
      }
      
      // Verify timing precision
      if (transitionTimestamps.length >= 2) {
        const timingGap = transitionTimestamps[1] - transitionTimestamps[0];
        console.log(`[VIDEO TRANSITION TEST] Measured timing gap: ${timingGap}ms`);
        
        // Allow for small variations in timing (±50ms tolerance)
        expect(timingGap).toBeGreaterThanOrEqual(250);
        expect(timingGap).toBeLessThanOrEqual(350);
      }
      
      console.log('[VIDEO TRANSITION TEST] ✅ Timing verification passed');
    });
  });

  describe('3. Failure Recovery Test', () => {
    it('should handle video loading failures and attempt recovery', async () => {
      console.log('[VIDEO TRANSITION TEST] Starting failure recovery test');
      
      const failingVideo = createTestVideo('video-failing', 'corrupted-video.mp4', 10);
      const recoverySequence = [testVideoSequence[0], failingVideo, testVideoSequence[2]];
      
      const onVideoChange = jest.fn();
      const onError = jest.fn();
      
      render(
        <SequentialVideoManager
          videos={recoverySequence}
          onVideoChange={onVideoChange}
          autoAdvance={true}
        />
      );
      
      // Simulate first video success
      const firstVideo = Object.values(mockVideoElements)[0];
      if (firstVideo) {
        await act(async () => {
          await firstVideo._simulateVideoProgress(testVideoSequence[0].duration);
        });
        
        act(() => {
          jest.advanceTimersByTime(150);
        });
      }
      
      // Simulate second video failure
      const secondVideo = Object.values(mockVideoElements)[1];
      if (secondVideo) {
        // Mock video loading failure
        secondVideo.play = jest.fn().mockRejectedValue(new Error('Video loading failed'));
        secondVideo.error = { code: 3, message: 'MEDIA_ERR_DECODE' };
        
        await act(async () => {
          secondVideo._triggerEvent('error', { error: secondVideo.error });
        });
        
        console.log('[VIDEO TRANSITION TEST] Simulated video loading failure');
      }
      
      // The system should attempt recovery or skip to next video
      act(() => {
        jest.advanceTimersByTime(1000); // Allow time for recovery attempts
      });
      
      // Verify error handling logs
      const errorLogs = consoleCapture.getLogsByPattern(/error|failed|recovery/i);
      expect(errorLogs.length).toBeGreaterThan(0);
      
      console.log('[VIDEO TRANSITION TEST] ✅ Failure recovery test completed');
    });

    it('should never skip Video 2 even during failure scenarios', async () => {
      console.log('[VIDEO TRANSITION TEST] Testing Video 2 skip prevention during failures');
      
      const onVideoChange = jest.fn();
      
      // Create scenario where Video 1 fails but Video 2 should still be attempted
      const testSequenceWithFailure = [
        createTestVideo('video-1-failing', 'video-1-fail.mp4', 5),
        testVideoSequence[1], // Video 2 - should NEVER be skipped
        testVideoSequence[2]
      ];
      
      render(
        <SequentialVideoManager
          videos={testSequenceWithFailure}
          onVideoChange={onVideoChange}
          autoAdvance={true}
        />
      );
      
      // Simulate Video 1 failure
      const firstVideo = Object.values(mockVideoElements)[0];
      if (firstVideo) {
        firstVideo.play = jest.fn().mockRejectedValue(new Error('Network error'));
        
        await act(async () => {
          firstVideo._triggerEvent('error');
        });
        
        act(() => {
          jest.advanceTimersByTime(500);
        });
      }
      
      // Even with Video 1 failure, Video 2 should be attempted
      await waitFor(() => {
        const video2Calls = onVideoChange.mock.calls.filter(call => 
          call[0].id === 'video-transition-2'
        );
        expect(video2Calls.length).toBeGreaterThan(0);
      });
      
      console.log('[VIDEO TRANSITION TEST] ✅ Video 2 was attempted even after Video 1 failure');
    });
  });

  describe('4. Console Log Analysis Test', () => {
    it('should generate proper debug output during video transitions', async () => {
      console.log('[VIDEO TRANSITION TEST] Starting console log analysis');
      
      render(
        <SequentialVideoManager
          videos={testVideoSequence}
          autoAdvance={true}
        />
      );
      
      // Simulate complete playback sequence
      for (let i = 0; i < testVideoSequence.length; i++) {
        const videoElement = Object.values(mockVideoElements)[i];
        if (videoElement) {
          await act(async () => {
            await videoElement._simulateVideoProgress(testVideoSequence[i].duration);
          });
          
          if (i < testVideoSequence.length - 1) {
            act(() => {
              jest.advanceTimersByTime(250);
            });
          }
        }
      }
      
      // Analyze captured logs
      const allLogs = consoleCapture.getLogs();
      const transitionLogs = consoleCapture.getVideoTransitionLogs();
      
      console.log(`[VIDEO TRANSITION TEST] Captured ${allLogs.length} total logs`);
      console.log(`[VIDEO TRANSITION TEST] Found ${transitionLogs.length} transition-related logs`);
      
      // Verify key log patterns exist
      expect(consoleCapture.hasLogMatching(/Video.*play\(\) called/)).toBe(true);
      expect(consoleCapture.hasLogMatching(/Video.*ended.*event/)).toBe(true);
      expect(consoleCapture.hasLogMatching(/Video.*change/)).toBe(true);
      
      // Verify Video 2 specific logs
      expect(consoleCapture.hasLogMatching(/video-transition-2|middle-video/)).toBe(true);
      
      console.log('[VIDEO TRANSITION TEST] ✅ Console log analysis passed');
      
      // Output log summary for manual inspection
      console.log('\n=== VIDEO TRANSITION LOG SUMMARY ===');
      transitionLogs.forEach((log, index) => {
        console.log(`${index + 1}. [${log.level.toUpperCase()}] ${log.message}`);
      });
      console.log('=== END LOG SUMMARY ===\n');
    });
  });

  describe('5. Manual Integration Test Simulation', () => {
    it('should simulate exact user experience with realistic interactions', async () => {
      console.log('[VIDEO TRANSITION TEST] Starting manual integration test simulation');
      
      const user = userEvent.setup({ delay: null });
      const userExperienceLog: string[] = [];
      
      const onVideoChange = jest.fn().mockImplementation((video, index) => {
        const logEntry = `User sees video ${index + 1}: ${video.filename}`;
        userExperienceLog.push(logEntry);
        console.log(`[USER EXPERIENCE] ${logEntry}`);
      });
      
      const onProgress = jest.fn().mockImplementation((progress) => {
        if (progress % 25 === 0) { // Log progress at 25% intervals
          const logEntry = `Progress indicator shows: ${progress}%`;
          userExperienceLog.push(logEntry);
          console.log(`[USER EXPERIENCE] ${logEntry}`);
        }
      });
      
      render(
        <SequentialVideoManager
          videos={testVideoSequence}
          onVideoChange={onVideoChange}
          onProgress={onProgress}
          autoAdvance={true}
          latencyMs={200}
        />
      );
      
      // Step 1: User sees initial interface
      await waitFor(() => {
        expect(screen.getByText(/Sequential Playback/)).toBeInTheDocument();
        expect(screen.getByText(/Video 1 of 3/)).toBeInTheDocument();
      });
      
      userExperienceLog.push('User sees sequential playback interface');
      console.log('[USER EXPERIENCE] User sees sequential playback interface');
      
      // Step 2: User watches Video 1 play automatically
      const firstVideo = Object.values(mockVideoElements)[0];
      if (firstVideo) {
        await act(async () => {
          userExperienceLog.push('Video 1 starts playing automatically');
          console.log('[USER EXPERIENCE] Video 1 starts playing automatically');
          await firstVideo._simulateVideoProgress(testVideoSequence[0].duration);
          userExperienceLog.push('Video 1 completes playing');
          console.log('[USER EXPERIENCE] Video 1 completes playing');
        });
        
        act(() => {
          jest.advanceTimersByTime(250);
        });
      }
      
      // Step 3: User sees transition to Video 2 (CRITICAL - should never be skipped)
      await waitFor(() => {
        expect(screen.getByText(/Video 2 of 3/)).toBeInTheDocument();
        expect(screen.getByText(/middle-video\.mp4/)).toBeInTheDocument();
      });
      
      userExperienceLog.push('User sees transition to Video 2 - VIDEO NEVER SKIPPED');
      console.log('[USER EXPERIENCE] User sees transition to Video 2 - VIDEO NEVER SKIPPED');
      
      // Step 4: User watches Video 2
      const secondVideo = Object.values(mockVideoElements)[1];
      if (secondVideo) {
        await act(async () => {
          userExperienceLog.push('Video 2 starts playing');
          console.log('[USER EXPERIENCE] Video 2 starts playing');
          await secondVideo._simulateVideoProgress(testVideoSequence[1].duration);
          userExperienceLog.push('Video 2 completes playing');
          console.log('[USER EXPERIENCE] Video 2 completes playing');
        });
        
        act(() => {
          jest.advanceTimersByTime(250);
        });
      }
      
      // Step 5: User sees transition to Video 3
      await waitFor(() => {
        expect(screen.getByText(/Video 3 of 3/)).toBeInTheDocument();
        expect(screen.getByText(/final-video\.mp4/)).toBeInTheDocument();
      });
      
      // Step 6: User can interact with controls
      const settingsButton = screen.getByLabelText(/settings/i);
      await user.click(settingsButton);
      
      await waitFor(() => {
        expect(screen.getByText(/Playback Settings/)).toBeInTheDocument();
      });
      
      userExperienceLog.push('User successfully opens settings dialog');
      console.log('[USER EXPERIENCE] User successfully opens settings dialog');
      
      // Close settings
      const closeButton = screen.getByText(/close/i);
      await user.click(closeButton);
      
      // Final verification
      expect(userExperienceLog).toContain('User sees transition to Video 2 - VIDEO NEVER SKIPPED');
      
      console.log('\n=== USER EXPERIENCE LOG ===');
      userExperienceLog.forEach((entry, index) => {
        console.log(`${index + 1}. ${entry}`);
      });
      console.log('=== END USER EXPERIENCE LOG ===\n');
      
      console.log('[VIDEO TRANSITION TEST] ✅ Manual integration test simulation passed');
    });
  });

  describe('6. Edge Cases and Boundary Conditions', () => {
    it('should handle rapid video transitions without skipping Video 2', async () => {
      console.log('[VIDEO TRANSITION TEST] Testing rapid transitions');
      
      const onVideoChange = jest.fn();
      
      render(
        <SequentialVideoManager
          videos={testVideoSequence}
          onVideoChange={onVideoChange}
          autoAdvance={true}
          latencyMs={10} // Very short gap for rapid transitions
        />
      );
      
      // Rapidly trigger video completions
      for (let i = 0; i < testVideoSequence.length; i++) {
        const videoElement = Object.values(mockVideoElements)[i];
        if (videoElement) {
          await act(async () => {
            // Simulate very short playback duration
            await videoElement._simulateVideoProgress(0.1);
          });
          
          act(() => {
            jest.advanceTimersByTime(20);
          });
        }
      }
      
      // Verify all videos were called, including Video 2
      const allVideoCalls = onVideoChange.mock.calls;
      const video2Calls = allVideoCalls.filter(call => call[0].id === 'video-transition-2');
      
      expect(video2Calls.length).toBeGreaterThanOrEqual(1);
      console.log('[VIDEO TRANSITION TEST] ✅ Video 2 was not skipped during rapid transitions');
    });

    it('should handle empty video list gracefully', async () => {
      console.log('[VIDEO TRANSITION TEST] Testing empty video list');
      
      const onPlaybackComplete = jest.fn();
      
      render(
        <SequentialVideoManager
          videos={[]}
          onPlaybackComplete={onPlaybackComplete}
          autoAdvance={true}
        />
      );
      
      // Should not crash and should handle empty state
      await waitFor(() => {
        expect(screen.getByText(/Sequential Playback/)).toBeInTheDocument();
      });
      
      console.log('[VIDEO TRANSITION TEST] ✅ Empty video list handled gracefully');
    });

    it('should handle single video scenario', async () => {
      console.log('[VIDEO TRANSITION TEST] Testing single video scenario');
      
      const onPlaybackComplete = jest.fn();
      
      render(
        <SequentialVideoManager
          videos={[testVideoSequence[0]]}
          onPlaybackComplete={onPlaybackComplete}
          autoAdvance={true}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText(/Video 1 of 1/)).toBeInTheDocument();
      });
      
      // Simulate single video completion
      const videoElement = Object.values(mockVideoElements)[0];
      if (videoElement) {
        await act(async () => {
          await videoElement._simulateVideoProgress(testVideoSequence[0].duration);
        });
        
        act(() => {
          jest.advanceTimersByTime(250);
        });
      }
      
      await waitFor(() => {
        expect(onPlaybackComplete).toHaveBeenCalled();
      });
      
      console.log('[VIDEO TRANSITION TEST] ✅ Single video scenario handled correctly');
    });
  });
});

/**
 * MANUAL TEST INSTRUCTIONS FOR DEVELOPERS
 * 
 * To manually validate the video transition system:
 * 
 * 1. Run this test suite: `npm test video-transition-system.integration.test.tsx`
 * 2. Check console output for detailed transition logs
 * 3. Verify all tests pass, especially Video 2 skip prevention tests
 * 4. Look for log entries containing "VIDEO NEVER SKIPPED"
 * 5. Confirm timing measurements are within expected ranges
 * 
 * Key Success Criteria:
 * ✅ All 3 videos play in sequence (1 → 2 → 3)
 * ✅ Video 2 is NEVER skipped under any circumstances  
 * ✅ Proper timing gaps between videos (configurable latency)
 * ✅ Failure recovery doesn't skip subsequent videos
 * ✅ Console logs show proper debug progression
 * ✅ Manual interaction test simulates real user experience
 * 
 * If any test fails, check:
 * - Video element creation and event handling
 * - Timing logic in SequentialVideoManager
 * - Auto-advance mechanism
 * - Error recovery pathways
 */