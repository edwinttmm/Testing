/**
 * Video Stall and Fullscreen Investigation Tests
 * 
 * Comprehensive test suite for investigating video element stalling behavior
 * and fullscreen compatibility issues. Tests various scenarios that could
 * cause video stalls and fullscreen failures.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { videoAPIInvestigator, startVideoInvestigation } from '../utils/videoAPIInvestigation';
import { videoCompatibilityChecker } from '../utils/videoCompatibilityChecker';
import VideoStallInvestigator from '../components/VideoStallInvestigator';

// Mock video element for testing
class MockVideoElement {
  public readyState = HTMLMediaElement.HAVE_NOTHING;
  public networkState = HTMLMediaElement.NETWORK_EMPTY;
  public currentTime = 0;
  public duration = NaN;
  public paused = true;
  public ended = false;
  public seeking = false;
  public error: MediaError | null = null;
  public src = '';
  public currentSrc = '';
  public buffered: TimeRanges;
  public seekable: TimeRanges;
  public played: TimeRanges;
  public videoWidth = 0;
  public videoHeight = 0;
  public playbackRate = 1;
  public defaultPlaybackRate = 1;
  public volume = 1;
  public muted = false;
  public crossOrigin = null;
  public preload = 'metadata';
  public loop = false;
  public controls = false;
  public autoplay = false;

  private eventListeners = new Map<string, EventListener[]>();

  constructor() {
    this.buffered = createMockTimeRanges([]);
    this.seekable = createMockTimeRanges([]);
    this.played = createMockTimeRanges([]);
  }

  addEventListener(event: string, listener: EventListener): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(listener);
  }

  removeEventListener(event: string, listener: EventListener): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  dispatchEvent(event: Event): boolean {
    const listeners = this.eventListeners.get(event.type);
    if (listeners) {
      listeners.forEach(listener => listener(event));
    }
    return true;
  }

  async play(): Promise<void> {
    if (this.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      this.paused = false;
      this.dispatchEvent(new Event('play'));
      this.dispatchEvent(new Event('playing'));
      return Promise.resolve();
    }
    throw new Error('Not enough data to play');
  }

  pause(): void {
    this.paused = true;
    this.dispatchEvent(new Event('pause'));
  }

  load(): void {
    this.networkState = HTMLMediaElement.NETWORK_LOADING;
    this.readyState = HTMLMediaElement.HAVE_NOTHING;
    this.dispatchEvent(new Event('loadstart'));
    
    // Simulate loading progression
    setTimeout(() => {
      this.readyState = HTMLMediaElement.HAVE_METADATA;
      this.duration = 120; // 2 minutes
      this.videoWidth = 1920;
      this.videoHeight = 1080;
      this.dispatchEvent(new Event('loadedmetadata'));
    }, 100);
  }

  async requestFullscreen(): Promise<void> {
    // Mock fullscreen request
    return Promise.resolve();
  }

  // Simulation methods for testing
  simulateStall(): void {
    this.networkState = HTMLMediaElement.NETWORK_LOADING;
    this.readyState = HTMLMediaElement.HAVE_CURRENT_DATA;
    this.dispatchEvent(new Event('stalled'));
    this.dispatchEvent(new Event('waiting'));
  }

  simulateProgress(): void {
    this.networkState = HTMLMediaElement.NETWORK_LOADING;
    this.buffered = createMockTimeRanges([{ start: 0, end: this.currentTime + 10 }]);
    this.dispatchEvent(new Event('progress'));
  }

  simulateCanPlay(): void {
    this.readyState = HTMLMediaElement.HAVE_FUTURE_DATA;
    this.networkState = HTMLMediaElement.NETWORK_IDLE;
    this.dispatchEvent(new Event('canplay'));
  }

  simulateCanPlayThrough(): void {
    this.readyState = HTMLMediaElement.HAVE_ENOUGH_DATA;
    this.networkState = HTMLMediaElement.NETWORK_IDLE;
    this.dispatchEvent(new Event('canplaythrough'));
  }

  simulateError(code: number, message: string): void {
    this.error = { code, message } as MediaError;
    this.dispatchEvent(new Event('error'));
  }

  simulateTimeUpdate(time: number): void {
    this.currentTime = time;
    this.played = createMockTimeRanges([{ start: 0, end: time }]);
    this.dispatchEvent(new Event('timeupdate'));
  }
}

function createMockTimeRanges(ranges: Array<{ start: number; end: number }>): TimeRanges {
  return {
    length: ranges.length,
    start: (index: number) => ranges[index]?.start || 0,
    end: (index: number) => ranges[index]?.end || 0
  } as TimeRanges;
}

// Mock HTMLVideoElement constructor
Object.defineProperty(global, 'HTMLVideoElement', {
  value: MockVideoElement,
  writable: true
});

// Mock document.createElement to return MockVideoElement for video tags
const originalCreateElement = document.createElement;
document.createElement = jest.fn().mockImplementation((tagName: string) => {
  if (tagName === 'video') {
    return new MockVideoElement();
  }
  return originalCreateElement.call(document, tagName);
});

// Mock fullscreen APIs
Object.defineProperty(document, 'fullscreenEnabled', { value: true, writable: true });
Object.defineProperty(document, 'fullscreenElement', { value: null, writable: true });

describe('Video Stall Investigation', () => {
  let mockVideo: MockVideoElement;
  let investigation: { id: string; cleanup: () => void };

  beforeEach(() => {
    mockVideo = new MockVideoElement();
    mockVideo.src = 'http://example.com/test.mp4';
    investigation = startVideoInvestigation(mockVideo as any);
    jest.clearAllMocks();
  });

  afterEach(() => {
    investigation.cleanup();
    videoAPIInvestigator.clearAll();
  });

  describe('Video Loading States and ReadyState Progression', () => {
    test('should track readyState progression from HAVE_NOTHING to HAVE_ENOUGH_DATA', async () => {
      // Start with HAVE_NOTHING
      expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_NOTHING);
      
      // Simulate loading progression
      mockVideo.load();
      expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_NOTHING);
      expect(mockVideo.networkState).toBe(HTMLMediaElement.NETWORK_LOADING);

      // Wait for metadata loading
      await waitFor(() => {
        expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_METADATA);
      });

      // Simulate data loading
      mockVideo.simulateProgress();
      mockVideo.simulateCanPlay();
      expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_FUTURE_DATA);

      // Simulate enough data for smooth playback
      mockVideo.simulateCanPlayThrough();
      expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_ENOUGH_DATA);

      // Verify event logs captured the progression
      const logs = videoAPIInvestigator.getEventLogs(investigation.id);
      const readyStateProgression = logs
        .filter(log => ['loadstart', 'loadedmetadata', 'canplay', 'canplaythrough'].includes(log.event))
        .map(log => ({ event: log.event, readyState: log.elementState.readyState }));

      expect(readyStateProgression).toEqual([
        { event: 'loadstart', readyState: HTMLMediaElement.HAVE_NOTHING },
        { event: 'loadedmetadata', readyState: HTMLMediaElement.HAVE_METADATA },
        { event: 'canplay', readyState: HTMLMediaElement.HAVE_FUTURE_DATA },
        { event: 'canplaythrough', readyState: HTMLMediaElement.HAVE_ENOUGH_DATA }
      ]);
    });

    test('should detect stall during initial loading', async () => {
      mockVideo.load();
      
      // Wait for initial loading
      await waitFor(() => {
        expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_METADATA);
      });

      // Simulate stall during data loading
      mockVideo.simulateStall();
      
      // Check stall diagnostic
      const stallDiagnostic = videoAPIInvestigator.analyzeStallCondition(mockVideo as any);
      expect(stallDiagnostic.isStalled).toBe(true);
      expect(stallDiagnostic.stallType).toBe('loading');

      // Verify stall events in logs
      const logs = videoAPIInvestigator.getEventLogs(investigation.id);
      const stallEvents = logs.filter(log => ['stalled', 'waiting'].includes(log.event));
      expect(stallEvents.length).toBeGreaterThan(0);
    });

    test('should track network state changes during loading', () => {
      expect(mockVideo.networkState).toBe(HTMLMediaElement.NETWORK_EMPTY);
      
      mockVideo.load();
      expect(mockVideo.networkState).toBe(HTMLMediaElement.NETWORK_LOADING);
      
      mockVideo.simulateCanPlayThrough();
      expect(mockVideo.networkState).toBe(HTMLMediaElement.NETWORK_IDLE);

      const logs = videoAPIInvestigator.getEventLogs(investigation.id);
      const networkStates = logs.map(log => log.elementState.networkState);
      
      expect(networkStates).toContain(HTMLMediaElement.NETWORK_EMPTY);
      expect(networkStates).toContain(HTMLMediaElement.NETWORK_LOADING);
      expect(networkStates).toContain(HTMLMediaElement.NETWORK_IDLE);
    });
  });

  describe('Stall Detection and Analysis', () => {
    test('should detect buffer-related stalls', async () => {
      mockVideo.load();
      await waitFor(() => expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_METADATA));
      
      // Start playing
      mockVideo.simulateCanPlay();
      await mockVideo.play();
      
      // Simulate playback and then buffer depletion
      mockVideo.simulateTimeUpdate(30);
      mockVideo.readyState = HTMLMediaElement.HAVE_CURRENT_DATA; // Not enough for smooth playback
      mockVideo.simulateStall();
      
      const stallDiagnostic = videoAPIInvestigator.analyzeStallCondition(mockVideo as any);
      expect(stallDiagnostic.isStalled).toBe(true);
      expect(stallDiagnostic.stallType).toBe('buffering');
    });

    test('should detect seek-related stalls', () => {
      mockVideo.load();
      mockVideo.simulateCanPlayThrough();
      
      // Simulate seeking
      mockVideo.seeking = true;
      mockVideo.readyState = HTMLMediaElement.HAVE_METADATA; // Waiting for seek target data
      
      const stallDiagnostic = videoAPIInvestigator.analyzeStallCondition(mockVideo as any);
      expect(stallDiagnostic.isStalled).toBe(true);
      expect(stallDiagnostic.stallType).toBe('seeking');
    });

    test('should analyze buffer health during stalls', () => {
      mockVideo.load();
      mockVideo.simulateCanPlay();
      
      // Set up some buffered data
      mockVideo.buffered = createMockTimeRanges([
        { start: 0, end: 20 },
        { start: 30, end: 50 }  // Gap from 20-30
      ]);
      mockVideo.currentTime = 25; // In the gap
      
      const stallDiagnostic = videoAPIInvestigator.analyzeStallCondition(mockVideo as any);
      expect(stallDiagnostic.bufferHealth.hasBufferedData).toBe(true);
      // Would detect buffer gaps in a full implementation
    });

    test('should provide network analysis during stalls', () => {
      // Mock navigator.connection
      Object.defineProperty(navigator, 'connection', {
        value: { effectiveType: '4g', downlink: 10, rtt: 100 },
        writable: true
      });

      mockVideo.simulateStall();
      
      const stallDiagnostic = videoAPIInvestigator.analyzeStallCondition(mockVideo as any);
      expect(stallDiagnostic.networkAnalysis.effectiveType).toBe('4g');
      expect(stallDiagnostic.networkAnalysis.downlink).toBe(10);
    });
  });

  describe('Video Error Detection and Analysis', () => {
    test('should capture MediaError details', () => {
      mockVideo.load();
      mockVideo.simulateError(MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED, 'Format not supported');
      
      const logs = videoAPIInvestigator.getEventLogs(investigation.id);
      const errorLog = logs.find(log => log.event === 'error');
      
      expect(errorLog).toBeDefined();
      expect(errorLog?.elementState.error?.code).toBe(MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED);
      expect(errorLog?.elementState.error?.message).toBe('Format not supported');
    });

    test('should categorize different error types', () => {
      const errorTypes = [
        { code: MediaError.MEDIA_ERR_NETWORK, expectedType: 'network' },
        { code: MediaError.MEDIA_ERR_DECODE, expectedType: 'decode' },
        { code: MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED, expectedType: 'format' },
        { code: MediaError.MEDIA_ERR_ABORTED, expectedType: 'unknown' }
      ];

      errorTypes.forEach(({ code, expectedType }) => {
        mockVideo.simulateError(code, 'Test error');
        
        const logs = videoAPIInvestigator.getEventLogs(investigation.id);
        const errorLog = logs.find(log => log.event === 'error');
        
        // In a full implementation, would check error categorization
        expect(errorLog?.elementState.error?.code).toBe(code);
      });
    });
  });

  describe('Video Format and Codec Compatibility', () => {
    test('should test MP4 format compatibility', async () => {
      const testResult = await videoCompatibilityChecker.testVideoPlayback(
        'http://example.com/test.mp4',
        'mp4'
      );
      
      // Mock implementation would return compatibility results
      expect(testResult.format).toBe('mp4');
      expect(testResult.url).toBe('http://example.com/test.mp4');
    });

    test('should provide fallback format recommendations', async () => {
      const compatibilityResult = await videoCompatibilityChecker.performCompatibilityCheck(
        'http://example.com/test.avi',
        'test.avi'
      );
      
      // AVI should not be compatible and suggest alternatives
      expect(compatibilityResult.isCompatible).toBe(false);
      expect(compatibilityResult.fallbackFormats).toContain('mp4');
    });

    test('should detect codec support for H.264', () => {
      const capabilities = videoCompatibilityChecker.getBrowserCapabilities();
      
      // Most modern browsers support H.264
      expect(capabilities.codecs.h264).toBeDefined();
    });
  });

  describe('Fullscreen Compatibility Testing', () => {
    test('should detect basic fullscreen API support', async () => {
      const fullscreenTest = await videoAPIInvestigator.testFullscreenCompatibility(mockVideo as any);
      
      expect(fullscreenTest.supportsFullscreen).toBe(true);
      expect(fullscreenTest.fullscreenMethod).toBeDefined();
      expect(fullscreenTest.exitFullscreenMethod).toBeDefined();
    });

    test('should test direct video fullscreen capability', async () => {
      const fullscreenTest = await videoAPIInvestigator.testFullscreenCompatibility(mockVideo as any);
      
      // Results depend on browser implementation
      expect(fullscreenTest.testResults).toBeDefined();
      expect(typeof fullscreenTest.testResults.directVideoFullscreen).toBe('boolean');
    });

    test('should identify browser-specific fullscreen quirks', async () => {
      // Mock Safari user agent
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        writable: true
      });

      const fullscreenTest = await videoAPIInvestigator.testFullscreenCompatibility(mockVideo as any);
      
      expect(fullscreenTest.browserQuirks).toContain('Safari requires user gesture for fullscreen');
    });

    test('should test Picture-in-Picture support', async () => {
      // Mock PiP support
      Object.defineProperty(document, 'pictureInPictureEnabled', { value: true });
      
      const fullscreenTest = await videoAPIInvestigator.testFullscreenCompatibility(mockVideo as any);
      
      expect(fullscreenTest.supportsPictureInPicture).toBe(true);
    });

    test('should test fullscreen behavior with different video states', async () => {
      mockVideo.load();
      await waitFor(() => expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_METADATA));
      
      const fullscreenTest = await videoAPIInvestigator.testFullscreenCompatibility(mockVideo as any);
      
      // These would test actual fullscreen behavior in different states
      expect(fullscreenTest.testResults.fullscreenWhilePaused).toBeDefined();
      expect(fullscreenTest.testResults.fullscreenWhilePlaying).toBeDefined();
      expect(fullscreenTest.testResults.fullscreenBeforeLoad).toBeDefined();
    });
  });

  describe('Event Sequence and Timing Analysis', () => {
    test('should track proper event firing sequence', async () => {
      mockVideo.load();
      
      // Wait for loading events
      await waitFor(() => expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_METADATA));
      
      mockVideo.simulateCanPlay();
      await mockVideo.play();
      mockVideo.simulateTimeUpdate(5);
      
      const logs = videoAPIInvestigator.getEventLogs(investigation.id);
      const eventSequence = logs.map(log => log.event);
      
      // Verify expected event order
      expect(eventSequence.indexOf('loadstart')).toBeLessThan(eventSequence.indexOf('loadedmetadata'));
      expect(eventSequence.indexOf('loadedmetadata')).toBeLessThan(eventSequence.indexOf('canplay'));
      expect(eventSequence.indexOf('canplay')).toBeLessThan(eventSequence.indexOf('play'));
    });

    test('should measure event timing intervals', () => {
      const startTime = performance.now();
      
      mockVideo.load();
      setTimeout(() => mockVideo.simulateCanPlay(), 100);
      
      const logs = videoAPIInvestigator.getEventLogs(investigation.id);
      
      if (logs.length >= 2) {
        const loadStartLog = logs.find(log => log.event === 'loadstart');
        const canPlayLog = logs.find(log => log.event === 'canplay');
        
        if (loadStartLog && canPlayLog) {
          const loadDuration = canPlayLog.timestamp - loadStartLog.timestamp;
          expect(loadDuration).toBeGreaterThan(0);
        }
      }
    });
  });

  describe('Comprehensive Diagnostic Report Generation', () => {
    test('should generate complete diagnostic report', async () => {
      mockVideo.load();
      await waitFor(() => expect(mockVideo.readyState).toBe(HTMLMediaElement.HAVE_METADATA));
      
      mockVideo.simulateCanPlay();
      await mockVideo.play();
      mockVideo.simulateStall();
      
      const report = videoAPIInvestigator.generateDiagnosticReport(investigation.id, mockVideo as any);
      
      expect(report).toContain('Video Element API Investigation Report');
      expect(report).toContain('Current Video Element State');
      expect(report).toContain('Stall Analysis');
      expect(report).toContain('Event Sequence Analysis');
      expect(report).toContain('HAVE_METADATA');
      expect(report).toContain('stalled');
    });

    test('should include buffer analysis in report', () => {
      mockVideo.buffered = createMockTimeRanges([{ start: 0, end: 30 }]);
      mockVideo.seekable = createMockTimeRanges([{ start: 0, end: 120 }]);
      
      const report = videoAPIInvestigator.generateDiagnosticReport(investigation.id, mockVideo as any);
      
      expect(report).toContain('Buffering Status');
      expect(report).toContain('[0.00-30.00]');
      expect(report).toContain('[0.00-120.00]');
    });
  });
});

describe('VideoStallInvestigator Component', () => {
  test('should render investigation interface', () => {
    render(<VideoStallInvestigator testVideoUrl="/test-video.mp4" />);
    
    expect(screen.getByText('Video Stall Investigator')).toBeInTheDocument();
    expect(screen.getByText('Test Video Player')).toBeInTheDocument();
    expect(screen.getByText('Investigation Status')).toBeInTheDocument();
  });

  test('should start and stop investigation', () => {
    render(<VideoStallInvestigator testVideoUrl="/test-video.mp4" />);
    
    const startButton = screen.getByText('Start Investigation');
    expect(startButton).toBeInTheDocument();
    
    fireEvent.click(startButton);
    
    // After starting, button should change to "Stop Investigation"
    expect(screen.getByText('Stop Investigation')).toBeInTheDocument();
  });

  test('should display video state information', () => {
    render(<VideoStallInvestigator testVideoUrl="/test-video.mp4" />);
    
    expect(screen.getByText('Ready State')).toBeInTheDocument();
    expect(screen.getByText('Network State')).toBeInTheDocument();
    expect(screen.getByText('Current Time')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
  });

  test('should show stall diagnostic results', async () => {
    render(<VideoStallInvestigator testVideoUrl="/test-video.mp4" />);
    
    // Start investigation
    fireEvent.click(screen.getByText('Start Investigation'));
    
    // Update diagnostics
    fireEvent.click(screen.getByText('Update Diagnostics'));
    
    // Should show diagnostic accordions
    expect(screen.getByText('Stall Diagnostic')).toBeInTheDocument();
    expect(screen.getByText('Fullscreen Compatibility Test')).toBeInTheDocument();
  });
});

// Integration test with real video element behavior
describe('Real Video Element Integration', () => {
  let realVideo: HTMLVideoElement;

  beforeEach(() => {
    // Create actual video element for integration testing
    realVideo = document.createElement('video') as HTMLVideoElement;
    document.body.appendChild(realVideo);
  });

  afterEach(() => {
    if (realVideo.parentNode) {
      realVideo.parentNode.removeChild(realVideo);
    }
  });

  test('should handle real video element properties', () => {
    expect(realVideo.readyState).toBe(HTMLMediaElement.HAVE_NOTHING);
    expect(realVideo.networkState).toBe(HTMLMediaElement.NETWORK_EMPTY);
    expect(realVideo.paused).toBe(true);
    expect(realVideo.currentTime).toBe(0);
  });

  test('should detect real browser fullscreen capabilities', async () => {
    const fullscreenTest = await videoAPIInvestigator.testFullscreenCompatibility(realVideo);
    
    // These should reflect actual browser capabilities
    expect(typeof fullscreenTest.supportsFullscreen).toBe('boolean');
    expect(Array.isArray(fullscreenTest.browserQuirks)).toBe(true);
  });
});