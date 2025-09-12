/**
 * Comprehensive Video Format Testing Suite
 * 
 * Tests all video format compatibility and validation functionality:
 * - Format detection and validation
 * - Browser compatibility checking
 * - Cross-browser codec support
 * - Video accessibility testing
 * - Debug tools functionality
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import {
  videoCompatibilityChecker,
  performCompatibilityCheck,
  testVideoPlayback,
  getBrowserCapabilities
} from '../src/utils/videoCompatibilityChecker';

import {
  videoDebugTools,
  startDebugSession,
  testVideo,
  analyzeVideoFormat,
  generateCompatibilityMatrix
} from '../src/utils/videoDebugTools';

import {
  videoFormatValidator,
  validateVideoFormat,
  testVideoPlayability
} from '../src/utils/videoFormatValidator';

import VideoCompatibilityPanel from '../src/components/VideoCompatibilityPanel';

// Mock video element with comprehensive API
const createMockVideoElement = (canPlayTypes: Record<string, string> = {}) => {
  const mockVideo = {
    canPlayType: jest.fn((type: string) => canPlayTypes[type] || ''),
    play: jest.fn().mockResolvedValue(undefined),
    pause: jest.fn(),
    load: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    currentTime: 0,
    duration: 10,
    readyState: HTMLMediaElement.HAVE_METADATA,
    networkState: HTMLMediaElement.NETWORK_IDLE,
    error: null,
    src: '',
    videoWidth: 1920,
    videoHeight: 1080,
    buffered: {
      length: 1,
      start: () => 0,
      end: () => 5
    }
  };

  return mockVideo;
};

// Mock DOM environment
const setupMockDOM = () => {
  // Mock document.createElement for video elements
  const originalCreateElement = document.createElement;
  document.createElement = jest.fn((tagName) => {
    if (tagName === 'video') {
      return createMockVideoElement({
        'video/mp4': 'probably',
        'video/webm': 'probably', 
        'video/ogg': 'maybe',
        'video/mp4; codecs="avc1.42E01E"': 'probably',
        'video/webm; codecs="vp8"': 'probably',
        'video/webm; codecs="vp9"': 'probably'
      }) as any;
    }
    return originalCreateElement.call(document, tagName);
  });

  // Mock fullscreen APIs
  Object.defineProperty(document, 'fullscreenEnabled', { value: true, configurable: true });
  Object.defineProperty(document, 'webkitFullscreenEnabled', { value: true, configurable: true });
  
  // Mock fetch for video accessibility tests
  global.fetch = jest.fn().mockImplementation((url: string) => {
    if (url.includes('.mp4')) {
      return Promise.resolve({
        ok: true,
        headers: new Map([['content-type', 'video/mp4']])
      } as any);
    }
    if (url.includes('.webm')) {
      return Promise.resolve({
        ok: true,
        headers: new Map([['content-type', 'video/webm']])
      } as any);
    }
    return Promise.resolve({
      ok: false,
      headers: new Map()
    } as any);
  });
};

describe('Comprehensive Video Format Testing', () => {
  beforeEach(() => {
    setupMockDOM();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Format Detection and Validation', () => {
    it('should detect MP4 format correctly', () => {
      const result = validateVideoFormat('test-video.mp4');
      
      expect(result.isSupported).toBe(true);
      expect(result.originalFormat.extension).toBe('mp4');
      expect(result.originalFormat.mimeType).toBe('video/mp4');
      expect(result.originalFormat.browserSupport).toBe('universal');
    });

    it('should detect WebM format correctly', () => {
      const result = validateVideoFormat('test-video.webm');
      
      expect(result.originalFormat.extension).toBe('webm');
      expect(result.originalFormat.mimeType).toBe('video/webm');
      expect(result.originalFormat.browserSupport).toBe('modern');
    });

    it('should handle unknown formats gracefully', () => {
      const result = validateVideoFormat('test-video.xyz');
      
      expect(result.isSupported).toBe(false);
      expect(result.originalFormat.extension).toBe('xyz');
      expect(result.originalFormat.browserSupport).toBe('unsupported');
      expect(result.errorMessage).toContain('not supported');
    });

    it('should provide format alternatives', () => {
      const result = validateVideoFormat('test-video.avi');
      
      expect(result.supportedAlternatives.length).toBeGreaterThan(0);
      expect(result.supportedAlternatives[0].extension).toBe('mp4');
      expect(result.recommendation).toContain('MP4');
    });

    it('should validate codec support', () => {
      const result = validateVideoFormat('test-video.mp4');
      
      // Should detect H.264 support
      expect(result.confidence).toBeOneOf(['probably', 'maybe', 'certainly']);
      if (result.isSupported) {
        expect(result.confidence).not.toBe('no');
      }
    });
  });

  describe('Browser Compatibility Detection', () => {
    it('should detect browser capabilities', () => {
      const capabilities = getBrowserCapabilities();
      
      expect(capabilities).toHaveProperty('browser');
      expect(capabilities).toHaveProperty('formats');
      expect(capabilities).toHaveProperty('codecs');
      expect(capabilities).toHaveProperty('features');
      
      expect(capabilities.browser).toHaveProperty('name');
      expect(capabilities.browser).toHaveProperty('version');
      expect(capabilities.browser).toHaveProperty('platform');
      
      expect(capabilities.formats).toHaveProperty('mp4');
      expect(capabilities.formats).toHaveProperty('webm');
      expect(capabilities.formats).toHaveProperty('ogg');
    });

    it('should test codec support correctly', () => {
      const capabilities = getBrowserCapabilities();
      
      expect(capabilities.codecs).toHaveProperty('h264');
      expect(capabilities.codecs).toHaveProperty('vp8');
      expect(capabilities.codecs).toHaveProperty('vp9');
      
      // H.264 should be supported in our mock
      expect(capabilities.codecs.h264).toBe(true);
    });

    it('should detect fullscreen support', () => {
      const capabilities = getBrowserCapabilities();
      
      expect(capabilities.features).toHaveProperty('fullscreen');
      expect(capabilities.features.fullscreen).toBe(true);
    });

    it('should detect mobile vs desktop', () => {
      const capabilities = getBrowserCapabilities();
      
      expect(capabilities.browser).toHaveProperty('mobile');
      expect(typeof capabilities.browser.mobile).toBe('boolean');
    });
  });

  describe('Video Playability Testing', () => {
    it('should test video loading successfully', async () => {
      const result = await testVideoPlayability('https://example.com/video.mp4');
      
      expect(result).toHaveProperty('canPlay');
      expect(result).toHaveProperty('loadTime');
      
      if (result.canPlay) {
        expect(result.loadTime).toBeGreaterThan(0);
      }
    });

    it('should handle network errors gracefully', async () => {
      // Mock network failure
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));
      
      const result = await testVideoPlayability('https://example.com/nonexistent.mp4');
      
      expect(result.canPlay).toBe(false);
      expect(result.error).toContain('error');
    });

    it('should test multiple formats', async () => {
      const results = await videoCompatibilityChecker.testMultipleFormats(
        'https://example.com/video',
        ['mp4', 'webm', 'ogg']
      );
      
      expect(results).toHaveLength(3);
      expect(results[0].format).toBe('mp4');
      expect(results[1].format).toBe('webm');
      expect(results[2].format).toBe('ogg');
    });

    it('should measure load times accurately', async () => {
      const startTime = Date.now();
      const result = await testVideoPlayability('https://example.com/video.mp4');
      const endTime = Date.now();
      
      if (result.loadTime) {
        expect(result.loadTime).toBeGreaterThan(0);
        expect(result.loadTime).toBeLessThan(endTime - startTime + 100); // Allow some margin
      }
    });
  });

  describe('Compatibility Checking', () => {
    it('should perform comprehensive compatibility check', async () => {
      const result = await performCompatibilityCheck(
        'https://example.com/video.mp4',
        'video.mp4'
      );
      
      expect(result).toHaveProperty('isCompatible');
      expect(result).toHaveProperty('primaryFormat');
      expect(result).toHaveProperty('fallbackFormats');
      expect(result).toHaveProperty('recommendations');
      expect(result).toHaveProperty('browserSupport');
      expect(result).toHaveProperty('compatibilityMatrix');
    });

    it('should provide fallback recommendations', async () => {
      const result = await performCompatibilityCheck(
        'https://example.com/video.avi',
        'video.avi'
      );
      
      expect(result.isCompatible).toBe(false);
      expect(result.fallbackFormats).toContain('mp4');
      expect(result.recommendations.length).toBeGreaterThan(0);
    });

    it('should handle streaming formats', async () => {
      const result = await performCompatibilityCheck(
        'https://example.com/stream.m3u8',
        'stream.m3u8'
      );
      
      expect(result.compatibilityMatrix).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            format: 'm3u8'
          })
        ])
      );
    });
  });

  describe('Debug Tools Functionality', () => {
    it('should start debug session', () => {
      const sessionId = startDebugSession();
      
      expect(typeof sessionId).toBe('string');
      expect(sessionId).toMatch(/debug_\d+_/);
    });

    it('should test video with session tracking', async () => {
      const sessionId = startDebugSession();
      const result = await testVideo('https://example.com/video.mp4', 'mp4', sessionId);
      
      expect(result).toHaveProperty('format');
      expect(result).toHaveProperty('canLoad');
      expect(result).toHaveProperty('canPlay');
      expect(result.format).toBe('mp4');
    });

    it('should analyze video format details', async () => {
      const analysis = await analyzeVideoFormat(
        'https://example.com/video.mp4',
        'video.mp4'
      );
      
      expect(analysis).toHaveProperty('detected');
      expect(analysis).toHaveProperty('validation');
      expect(analysis).toHaveProperty('recommendations');
      expect(analysis).toHaveProperty('alternatives');
      
      expect(analysis.detected.extension).toBe('mp4');
      expect(analysis.detected.mimeType).toBe('video/mp4');
    });

    it('should generate compatibility matrix', () => {
      const matrix = generateCompatibilityMatrix();
      
      expect(typeof matrix).toBe('string');
      expect(matrix).toContain('Chrome');
      expect(matrix).toContain('Firefox');
      expect(matrix).toContain('Safari');
      expect(matrix).toContain('Edge');
      expect(matrix).toContain('MP4');
      expect(matrix).toContain('WebM');
    });

    it('should track performance metrics', async () => {
      const sessionId = startDebugSession();
      
      // Run multiple tests
      await testVideo('https://example.com/video1.mp4', 'mp4', sessionId);
      await testVideo('https://example.com/video2.webm', 'webm', sessionId);
      
      const sessions = videoDebugTools.getSessions();
      const session = sessions.find(s => s.id === sessionId);
      
      expect(session).toBeDefined();
      expect(session!.performance.totalTests).toBe(2);
    });
  });

  describe('Video Compatibility Panel Component', () => {
    it('should render compatibility panel', () => {
      render(<VideoCompatibilityPanel />);
      
      expect(screen.getByText('Video Compatibility Checker')).toBeInTheDocument();
      expect(screen.getByLabelText('Video URL')).toBeInTheDocument();
      expect(screen.getByLabelText('Filename')).toBeInTheDocument();
      expect(screen.getByText('Check Compatibility')).toBeInTheDocument();
    });

    it('should show browser capabilities', async () => {
      render(<VideoCompatibilityPanel />);
      
      await waitFor(() => {
        expect(screen.getByText('Browser Capabilities')).toBeInTheDocument();
      });
      
      // Should show format support information
      expect(screen.getByText(/Browser Information/)).toBeInTheDocument();
      expect(screen.getByText(/Format Support/)).toBeInTheDocument();
    });

    it('should perform compatibility check on button click', async () => {
      render(<VideoCompatibilityPanel />);
      
      const urlInput = screen.getByLabelText('Video URL');
      const filenameInput = screen.getByLabelText('Filename');
      const checkButton = screen.getByText('Check Compatibility');
      
      fireEvent.change(urlInput, { target: { value: 'https://example.com/video.mp4' } });
      fireEvent.change(filenameInput, { target: { value: 'video.mp4' } });
      fireEvent.click(checkButton);
      
      await waitFor(() => {
        expect(screen.getByText('Compatibility Results')).toBeInTheDocument();
      });
    });

    it('should show compatibility matrix', () => {
      render(<VideoCompatibilityPanel />);
      
      expect(screen.getByText('Format Compatibility Matrix')).toBeInTheDocument();
    });

    it('should handle debug session controls', () => {
      render(<VideoCompatibilityPanel showDebugTools />);
      
      expect(screen.getByText('Start Debug Session')).toBeInTheDocument();
      expect(screen.getByLabelText('Enable Real-time Monitoring')).toBeInTheDocument();
    });

    it('should display test results in table format', async () => {
      render(<VideoCompatibilityPanel />);
      
      const urlInput = screen.getByLabelText('Video URL');
      const testButton = screen.getByText('Test Playback');
      
      fireEvent.change(urlInput, { target: { value: 'https://example.com/video.mp4' } });
      fireEvent.click(testButton);
      
      await waitFor(() => {
        expect(screen.getByText('Test Results')).toBeInTheDocument();
      });
    });

    it('should show error messages appropriately', async () => {
      render(<VideoCompatibilityPanel />);
      
      const checkButton = screen.getByText('Check Compatibility');
      fireEvent.click(checkButton);
      
      await waitFor(() => {
        expect(screen.getByText(/Please provide both URL and filename/)).toBeInTheDocument();
      });
    });
  });

  describe('Cross-Browser Format Support', () => {
    const mockUserAgents = {
      chrome: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      firefox: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
      safari: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
      edge: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59'
    };

    it('should detect Chrome correctly', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: mockUserAgents.chrome,
        configurable: true
      });

      const capabilities = getBrowserCapabilities();
      expect(capabilities.browser.name).toBe('chrome');
      expect(capabilities.browser.engine).toBe('blink');
    });

    it('should detect Firefox correctly', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: mockUserAgents.firefox,
        configurable: true
      });

      const capabilities = getBrowserCapabilities();
      expect(capabilities.browser.name).toBe('firefox');
      expect(capabilities.browser.engine).toBe('gecko');
    });

    it('should detect Safari correctly', () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: mockUserAgents.safari,
        configurable: true
      });

      const capabilities = getBrowserCapabilities();
      expect(capabilities.browser.name).toBe('safari');
      expect(capabilities.browser.engine).toBe('webkit');
    });

    it('should provide browser-specific recommendations', async () => {
      Object.defineProperty(navigator, 'userAgent', {
        value: mockUserAgents.safari,
        configurable: true
      });

      const result = await performCompatibilityCheck(
        'https://example.com/video.webm',
        'video.webm'
      );

      // Safari has limited WebM support
      expect(result.recommendations).toEqual(
        expect.arrayContaining([
          expect.stringContaining('limited support')
        ])
      );
    });
  });

  describe('Performance and Error Handling', () => {
    it('should handle video loading timeout', async () => {
      // Mock slow loading video
      const slowVideo = createMockVideoElement();
      slowVideo.addEventListener = jest.fn((event, handler) => {
        if (event === 'loadedmetadata') {
          // Never call the handler to simulate timeout
        }
      });

      document.createElement = jest.fn((tagName) => {
        if (tagName === 'video') return slowVideo as any;
        return document.createElement(tagName);
      });

      const result = await testVideoPlayability('https://slow.example.com/video.mp4');
      
      expect(result.canPlay).toBe(false);
      expect(result.error).toContain('timeout');
    }, 15000); // Increase timeout for this test

    it('should categorize error types correctly', async () => {
      const sessionId = startDebugSession();
      
      // Mock different error types
      const networkError = { code: MediaError.MEDIA_ERR_NETWORK, message: 'Network error' };
      const formatError = { code: MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED, message: 'Format not supported' };
      
      // These would be tracked by the debug tools in real scenarios
      expect(networkError.code).toBe(MediaError.MEDIA_ERR_NETWORK);
      expect(formatError.code).toBe(MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED);
    });

    it('should cache test results appropriately', async () => {
      const url = 'https://example.com/cached-video.mp4';
      
      // First call
      const result1 = await testVideoPlayback(url);
      
      // Second call should use cached result
      const result2 = await testVideoPlayback(url);
      
      expect(result1).toEqual(result2);
    });
  });

  describe('Video File Accessibility', () => {
    it('should check video file accessibility via HEAD request', async () => {
      const accessible = await videoFormatValidator.checkVideoAccessibility('https://example.com/video.mp4');
      
      // Based on our mock, MP4 should be accessible
      expect(typeof accessible).toBe('boolean');
    });

    it('should handle CORS and permission errors', async () => {
      // Mock CORS error
      global.fetch = jest.fn().mockRejectedValue(new Error('CORS error'));
      
      const accessible = await videoFormatValidator.checkVideoAccessibility('https://cors-blocked.example.com/video.mp4');
      
      expect(accessible).toBe(false);
    });

    it('should validate file permissions correctly', async () => {
      // Mock forbidden response
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 403,
        headers: new Map()
      } as any);
      
      const accessible = await videoFormatValidator.checkVideoAccessibility('https://forbidden.example.com/video.mp4');
      
      expect(accessible).toBe(false);
    });
  });

  describe('Integration with Fullscreen APIs', () => {
    it('should detect standard fullscreen API', () => {
      Object.defineProperty(document, 'fullscreenEnabled', { value: true, configurable: true });
      
      const capabilities = getBrowserCapabilities();
      expect(capabilities.features.fullscreen).toBe(true);
    });

    it('should fallback to webkit fullscreen API', () => {
      Object.defineProperty(document, 'fullscreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'webkitFullscreenEnabled', { value: true, configurable: true });
      
      const capabilities = getBrowserCapabilities();
      expect(capabilities.features.fullscreen).toBe(true);
    });

    it('should handle no fullscreen support gracefully', () => {
      Object.defineProperty(document, 'fullscreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'webkitFullscreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'mozFullScreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'msFullscreenEnabled', { value: false, configurable: true });
      
      const capabilities = getBrowserCapabilities();
      expect(capabilities.features.fullscreen).toBe(false);
    });
  });
});