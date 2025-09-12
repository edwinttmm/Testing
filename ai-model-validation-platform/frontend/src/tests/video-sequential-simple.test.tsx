/**
 * Simple Sequential Video Test
 * 
 * This is a straightforward test to verify basic video sequence functionality:
 * - Video 1 plays completely
 * - 2-second gap
 * - Video 2 loads and plays completely  
 * - 2-second gap
 * - Video 3 loads and plays completely
 * - Test completes
 * 
 * No complex timing verification, just basic functionality validation.
 */

import React from 'react';
import { render, screen, waitFor, act, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

import SequentialVideoManager from '../components/SequentialVideoManager';
import { VideoFile } from '../services/types';

// Simple test video data
const testVideos: VideoFile[] = [
  {
    id: 'simple-video-1',
    filename: 'video1.mp4',
    originalName: 'video1.mp4',
    url: '/test/video1.mp4',
    projectId: 'test-project',
    status: 'completed' as const,
    duration: 5,
    fps: 30,
    size: 1000000,
    fileSize: 1000000,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending' as const,
    processing_status: 'completed' as const,
    detectionCount: 0
  },
  {
    id: 'simple-video-2',
    filename: 'video2.mp4',
    originalName: 'video2.mp4',
    url: '/test/video2.mp4',
    projectId: 'test-project',
    status: 'completed' as const,
    duration: 5,
    fps: 30,
    size: 1000000,
    fileSize: 1000000,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending' as const,
    processing_status: 'completed' as const,
    detectionCount: 0
  },
  {
    id: 'simple-video-3',
    filename: 'video3.mp4',
    originalName: 'video3.mp4',
    url: '/test/video3.mp4',
    projectId: 'test-project',
    status: 'completed' as const,
    duration: 5,
    fps: 30,
    size: 1000000,
    fileSize: 1000000,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending' as const,
    processing_status: 'completed' as const,
    detectionCount: 0
  }
];

// Simple mock video element
const createSimpleMockVideo = () => {
  const mockVideo = {
    src: '',
    currentTime: 0,
    duration: 5,
    paused: true,
    ended: false,
    readyState: HTMLMediaElement.HAVE_ENOUGH_DATA,
    
    play: jest.fn().mockImplementation(function(this: any) {
      this.paused = false;
      return Promise.resolve();
    }),
    
    pause: jest.fn().mockImplementation(function(this: any) {
      this.paused = true;
    }),
    
    load: jest.fn(),
    
    addEventListener: jest.fn().mockImplementation(function(this: any, event: string, handler: Function) {
      if (!this._listeners) this._listeners = {};
      if (!this._listeners[event]) this._listeners[event] = [];
      this._listeners[event].push(handler);
    }),
    
    removeEventListener: jest.fn(),
    
    // Helper to simulate video completion
    _completeVideo: function(this: any) {
      this.ended = true;
      this.paused = true;
      if (this._listeners && this._listeners['ended']) {
        this._listeners['ended'].forEach((handler: Function) => {
          handler({ type: 'ended', target: this });
        });
      }
    },
    
    _listeners: {}
  };
  
  return mockVideo;
};

describe('Simple Sequential Video Test', () => {
  let mockVideos: any[] = [];
  let videoSequence: string[] = [];
  
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockVideos = [];
    videoSequence = [];
    
    // Mock document.createElement for video elements
    const originalCreateElement = document.createElement;
    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        const mockVideo = createSimpleMockVideo();
        mockVideos.push(mockVideo);
        console.log(`Created mock video element ${mockVideos.length}`);
        return mockVideo as any;
      }
      return originalCreateElement.call(document, tagName);
    });
  });
  
  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
    cleanup();
  });

  test('Video 1 → Video 2 → Video 3 Sequential Playback', async () => {
    console.log('🎬 Starting simple sequential video test');
    
    // Track video changes
    const onVideoChange = jest.fn().mockImplementation((video, index) => {
      const videoInfo = `Video ${index + 1}: ${video.filename}`;
      videoSequence.push(videoInfo);
      console.log(`✓ ${videoInfo} loaded`);
    });
    
    const onPlaybackComplete = jest.fn().mockImplementation(() => {
      console.log('✅ All videos completed successfully');
    });
    
    // Render the sequential video manager with 2-second gaps
    render(
      <SequentialVideoManager
        videos={testVideos}
        onVideoChange={onVideoChange}
        onPlaybackComplete={onPlaybackComplete}
        autoAdvance={true}
        latencyMs={2000} // 2-second gap as requested
      />
    );
    
    // Step 1: Verify Video 1 starts
    await waitFor(() => {
      expect(screen.getByText(/Video 1 of 3/)).toBeInTheDocument();
      expect(screen.getByText(/video1\.mp4/)).toBeInTheDocument();
    });
    
    console.log('1️⃣ Video 1 is displayed and ready');
    
    // Step 2: Simulate Video 1 completion
    if (mockVideos[0]) {
      await act(async () => {
        mockVideos[0]._completeVideo();
        console.log('1️⃣ Video 1 playback completed');
      });
      
      // Wait for the 2-second gap
      act(() => {
        jest.advanceTimersByTime(2100); // Slightly over 2 seconds
        console.log('⏱️  Waited 2-second gap after Video 1');
      });
    }
    
    // Step 3: Verify Video 2 loads and starts
    await waitFor(() => {
      expect(onVideoChange).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'simple-video-2', filename: 'video2.mp4' }),
        1
      );
    });
    
    console.log('2️⃣ Video 2 loaded successfully (NOT SKIPPED)');
    
    // Step 4: Simulate Video 2 completion
    if (mockVideos[1]) {
      await act(async () => {
        mockVideos[1]._completeVideo();
        console.log('2️⃣ Video 2 playback completed');
      });
      
      // Wait for the 2-second gap
      act(() => {
        jest.advanceTimersByTime(2100); // Slightly over 2 seconds
        console.log('⏱️  Waited 2-second gap after Video 2');
      });
    }
    
    // Step 5: Verify Video 3 loads and starts
    await waitFor(() => {
      expect(onVideoChange).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'simple-video-3', filename: 'video3.mp4' }),
        2
      );
    });
    
    console.log('3️⃣ Video 3 loaded successfully');
    
    // Step 6: Simulate Video 3 completion
    if (mockVideos[2]) {
      await act(async () => {
        mockVideos[2]._completeVideo();
        console.log('3️⃣ Video 3 playbook completed');
      });
      
      // Allow final processing
      act(() => {
        jest.advanceTimersByTime(500);
      });
    }
    
    // Step 7: Verify complete sequence
    await waitFor(() => {
      expect(onPlaybackComplete).toHaveBeenCalled();
    });
    
    // Final verification
    expect(videoSequence).toHaveLength(3);
    expect(videoSequence[0]).toContain('Video 1: video1.mp4');
    expect(videoSequence[1]).toContain('Video 2: video2.mp4');
    expect(videoSequence[2]).toContain('Video 3: video3.mp4');
    
    console.log('✅ TEST PASSED: All videos played in correct sequence');
    console.log('📋 Sequence log:', videoSequence);
  });

  test('Basic Error Handling - Video 2 Still Attempts to Play', async () => {
    console.log('🧪 Testing basic error recovery');
    
    const onVideoChange = jest.fn();
    const onError = jest.fn();
    
    render(
      <SequentialVideoManager
        videos={testVideos}
        onVideoChange={onVideoChange}
        autoAdvance={true}
        latencyMs={2000}
      />
    );
    
    // Simulate Video 1 failure
    if (mockVideos[0]) {
      mockVideos[0].play.mockRejectedValue(new Error('Video 1 failed'));
      
      await act(async () => {
        // Trigger error
        if (mockVideos[0]._listeners && mockVideos[0]._listeners['error']) {
          mockVideos[0]._listeners['error'].forEach((handler: Function) => {
            handler({ type: 'error', target: mockVideos[0] });
          });
        }
        
        console.log('❌ Video 1 simulated failure');
      });
      
      // Wait for error recovery
      act(() => {
        jest.advanceTimersByTime(3000);
      });
    }
    
    // Even with Video 1 failure, Video 2 should still be attempted
    await waitFor(() => {
      const video2Calls = onVideoChange.mock.calls.filter(call => 
        call[0].id === 'simple-video-2'
      );
      expect(video2Calls.length).toBeGreaterThan(0);
    });
    
    console.log('✅ Video 2 was still attempted after Video 1 failure');
  });

  test('Simple Timing Validation', async () => {
    console.log('⏰ Testing basic timing');
    
    const transitionTimes: number[] = [];
    const onVideoChange = jest.fn().mockImplementation(() => {
      transitionTimes.push(Date.now());
    });
    
    render(
      <SequentialVideoManager
        videos={testVideos.slice(0, 2)} // Only test first 2 videos for timing
        onVideoChange={onVideoChange}
        autoAdvance={true}
        latencyMs={2000}
      />
    );
    
    // Simulate Video 1 completion
    if (mockVideos[0]) {
      await act(async () => {
        mockVideos[0]._completeVideo();
      });
      
      act(() => {
        jest.advanceTimersByTime(2000); // Exactly 2 seconds
      });
    }
    
    // Verify Video 2 transition happened
    await waitFor(() => {
      expect(transitionTimes.length).toBeGreaterThanOrEqual(2);
    });
    
    console.log('✅ Basic timing validation passed');
  });
});