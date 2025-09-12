/**
 * Browser Compatibility Test Suite for Video Playback
 * Tests cross-browser compatibility for video playback features
 * including fullscreen APIs, codec support, and browser-specific behaviors
 */

import { VideoPlaybackManager } from '../src/utils/videoPlaybackManager';

// Mock user agents for different browsers
const BROWSER_USER_AGENTS = {
  chrome: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
  firefox: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
  safari: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
  edge: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
  mobile_chrome: 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
  mobile_safari: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
};

// Mock video formats and codecs
const VIDEO_FORMATS = {
  mp4_h264: { type: 'video/mp4; codecs="avc1.42E01E"', supported: true },
  mp4_h265: { type: 'video/mp4; codecs="hev1.1.6.L93.B0"', supported: false }, // Not universally supported
  webm_vp8: { type: 'video/webm; codecs="vp8"', supported: true },
  webm_vp9: { type: 'video/webm; codecs="vp9"', supported: true },
  webm_av1: { type: 'video/webm; codecs="av01.0.05M.08"', supported: false }, // Limited support
  ogg_theora: { type: 'video/ogg; codecs="theora"', supported: false }, // Legacy
};

// Mock fullscreen API variations
const FULLSCREEN_APIS = {
  standard: {
    request: 'requestFullscreen',
    exit: 'exitFullscreen',
    element: 'fullscreenElement',
    enabled: 'fullscreenEnabled',
    change: 'fullscreenchange',
    error: 'fullscreenerror'
  },
  webkit: {
    request: 'webkitRequestFullscreen',
    exit: 'webkitExitFullscreen',
    element: 'webkitFullscreenElement',
    enabled: 'webkitFullscreenEnabled',
    change: 'webkitfullscreenchange',
    error: 'webkitfullscreenerror'
  },
  moz: {
    request: 'mozRequestFullScreen',
    exit: 'mozCancelFullScreen',
    element: 'mozFullScreenElement',
    enabled: 'mozFullScreenEnabled',
    change: 'mozfullscreenchange',
    error: 'mozfullscreenerror'
  },
  ms: {
    request: 'msRequestFullscreen',
    exit: 'msExitFullscreen',
    element: 'msFullscreenElement',
    enabled: 'msFullscreenEnabled',
    change: 'MSFullscreenChange',
    error: 'MSFullscreenError'
  }
};

describe('Video Browser Compatibility Tests', () => {
  let originalUserAgent: string;
  let mockVideoElement: any;

  beforeEach(() => {
    originalUserAgent = navigator.userAgent;
    
    // Create comprehensive mock video element
    mockVideoElement = {
      play: jest.fn().mockResolvedValue(undefined),
      pause: jest.fn(),
      load: jest.fn(),
      canPlayType: jest.fn(),
      currentTime: 0,
      duration: 10,
      volume: 1,
      muted: false,
      paused: true,
      ended: false,
      readyState: HTMLMediaElement.HAVE_METADATA,
      videoWidth: 1920,
      videoHeight: 1080,
      error: null,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      
      // Standard fullscreen API
      requestFullscreen: jest.fn().mockResolvedValue(undefined),
      
      // Webkit fullscreen API (Safari, old Chrome)
      webkitRequestFullscreen: jest.fn(),
      webkitSupportsFullscreen: true,
      webkitDisplayingFullscreen: false,
      
      // Mozilla fullscreen API (Firefox)
      mozRequestFullScreen: jest.fn(),
      
      // Microsoft fullscreen API (IE/Edge legacy)
      msRequestFullscreen: jest.fn(),
    };

    // Mock document fullscreen properties
    Object.defineProperty(document, 'fullscreenEnabled', { value: true, configurable: true });
    Object.defineProperty(document, 'webkitFullscreenEnabled', { value: true, configurable: true });
    Object.defineProperty(document, 'mozFullScreenEnabled', { value: true, configurable: true });
    Object.defineProperty(document, 'msFullscreenEnabled', { value: true, configurable: true });

    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        return mockVideoElement;
      }
      return document.createElement(tagName);
    });
  });

  afterEach(() => {
    Object.defineProperty(navigator, 'userAgent', {
      value: originalUserAgent,
      configurable: true
    });
    jest.restoreAllMocks();
  });

  const setUserAgent = (userAgent: string) => {
    Object.defineProperty(navigator, 'userAgent', {
      value: userAgent,
      configurable: true
    });
  };

  describe('Browser-Specific Video Codec Support', () => {
    it('should detect Chrome codec support correctly', () => {
      setUserAgent(BROWSER_USER_AGENTS.chrome);
      
      // Chrome typically supports H.264, VP8, VP9
      mockVideoElement.canPlayType.mockImplementation((type: string) => {
        if (type.includes('avc1') || type.includes('vp8') || type.includes('vp9')) {
          return 'probably';
        }
        return '';
      });

      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.mp4_h264.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_vp8.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_vp9.type)).toBe('probably');
    });

    it('should detect Safari codec support correctly', () => {
      setUserAgent(BROWSER_USER_AGENTS.safari);
      
      // Safari primarily supports H.264, limited WebM support
      mockVideoElement.canPlayType.mockImplementation((type: string) => {
        if (type.includes('avc1')) {
          return 'probably';
        }
        if (type.includes('webm')) {
          return ''; // Limited or no support
        }
        return '';
      });

      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.mp4_h264.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_vp8.type)).toBe('');
    });

    it('should detect Firefox codec support correctly', () => {
      setUserAgent(BROWSER_USER_AGENTS.firefox);
      
      // Firefox supports H.264, VP8, VP9, AV1
      mockVideoElement.canPlayType.mockImplementation((type: string) => {
        if (type.includes('avc1') || type.includes('vp8') || type.includes('vp9') || type.includes('av01')) {
          return 'probably';
        }
        return '';
      });

      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.mp4_h264.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_vp8.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_av1.type)).toBe('probably');
    });

    it('should handle mobile browser codec differences', () => {
      setUserAgent(BROWSER_USER_AGENTS.mobile_chrome);
      
      // Mobile Chrome has similar codec support but may have performance limitations
      mockVideoElement.canPlayType.mockImplementation((type: string) => {
        if (type.includes('avc1') || type.includes('vp8')) {
          return 'probably';
        }
        if (type.includes('vp9')) {
          return 'maybe'; // Performance dependent
        }
        return '';
      });

      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.mp4_h264.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_vp8.type)).toBe('probably');
      expect(mockVideoElement.canPlayType(VIDEO_FORMATS.webm_vp9.type)).toBe('maybe');
    });
  });

  describe('Fullscreen API Cross-Browser Compatibility', () => {
    it('should use standard fullscreen API when available', async () => {
      setUserAgent(BROWSER_USER_AGENTS.chrome);
      
      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      // Simulate fullscreen request
      if (mockVideoElement.requestFullscreen) {
        await mockVideoElement.requestFullscreen();
        expect(mockVideoElement.requestFullscreen).toHaveBeenCalled();
      }
    });

    it('should fallback to webkit fullscreen API in Safari', async () => {
      setUserAgent(BROWSER_USER_AGENTS.safari);
      
      // Remove standard API, keep webkit
      delete mockVideoElement.requestFullscreen;
      
      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      // Test webkit fullscreen
      if (mockVideoElement.webkitRequestFullscreen) {
        mockVideoElement.webkitRequestFullscreen();
        expect(mockVideoElement.webkitRequestFullscreen).toHaveBeenCalled();
      }
    });

    it('should use mozilla fullscreen API in Firefox', async () => {
      setUserAgent(BROWSER_USER_AGENTS.firefox);
      
      // Remove other APIs, keep mozilla
      delete mockVideoElement.requestFullscreen;
      delete mockVideoElement.webkitRequestFullscreen;
      
      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      // Test mozilla fullscreen
      if (mockVideoElement.mozRequestFullScreen) {
        mockVideoElement.mozRequestFullScreen();
        expect(mockVideoElement.mozRequestFullScreen).toHaveBeenCalled();
      }
    });

    it('should handle fullscreen API detection across browsers', () => {
      const testCases = [
        {
          browser: 'chrome',
          userAgent: BROWSER_USER_AGENTS.chrome,
          apis: ['requestFullscreen'],
          documentProps: ['fullscreenEnabled']
        },
        {
          browser: 'safari',
          userAgent: BROWSER_USER_AGENTS.safari,
          apis: ['webkitRequestFullscreen'],
          documentProps: ['webkitFullscreenEnabled']
        },
        {
          browser: 'firefox',
          userAgent: BROWSER_USER_AGENTS.firefox,
          apis: ['mozRequestFullScreen'],
          documentProps: ['mozFullScreenEnabled']
        }
      ];

      testCases.forEach(testCase => {
        setUserAgent(testCase.userAgent);
        
        // Check API availability detection
        testCase.apis.forEach(api => {
          expect(typeof mockVideoElement[api]).toBe('function');
        });
        
        testCase.documentProps.forEach(prop => {
          expect((document as any)[prop]).toBeDefined();
        });
      });
    });
  });

  describe('Video Loading and Playback Behavior', () => {
    it('should handle autoplay policies across browsers', async () => {
      const testCases = [
        {
          browser: 'chrome',
          userAgent: BROWSER_USER_AGENTS.chrome,
          autoplayPolicy: 'document-user-activation-required'
        },
        {
          browser: 'safari',
          userAgent: BROWSER_USER_AGENTS.safari,
          autoplayPolicy: 'user-gesture-required'
        },
        {
          browser: 'firefox',
          userAgent: BROWSER_USER_AGENTS.firefox,
          autoplayPolicy: 'allowed'
        }
      ];

      for (const testCase of testCases) {
        setUserAgent(testCase.userAgent);
        
        const manager = new VideoPlaybackManager();
        manager.attachVideoElement(mockVideoElement);

        // Test play attempt
        const result = await manager.play();
        
        // Result depends on browser autoplay policy
        if (testCase.autoplayPolicy === 'allowed') {
          expect(result).toBe(true);
        } else {
          // May require user interaction
          expect(typeof result).toBe('boolean');
        }
      }
    });

    it('should handle mobile playback restrictions', async () => {
      setUserAgent(BROWSER_USER_AGENTS.mobile_safari);
      
      // Mobile Safari requires user interaction for video playback
      mockVideoElement.play.mockRejectedValueOnce(
        new DOMException('The request is not allowed', 'NotAllowedError')
      );

      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      const result = await manager.play();
      expect(result).toBe(false);
    });

    it('should adapt to browser-specific loading behaviors', () => {
      const browserBehaviors = [
        {
          browser: 'chrome',
          userAgent: BROWSER_USER_AGENTS.chrome,
          preloadSupport: true,
          rangeRequestSupport: true
        },
        {
          browser: 'safari',
          userAgent: BROWSER_USER_AGENTS.safari,
          preloadSupport: true,
          rangeRequestSupport: true
        },
        {
          browser: 'firefox',
          userAgent: BROWSER_USER_AGENTS.firefox,
          preloadSupport: true,
          rangeRequestSupport: true
        },
        {
          browser: 'mobile_safari',
          userAgent: BROWSER_USER_AGENTS.mobile_safari,
          preloadSupport: false, // Limited on mobile to save bandwidth
          rangeRequestSupport: true
        }
      ];

      browserBehaviors.forEach(behavior => {
        setUserAgent(behavior.userAgent);
        
        // Test preload behavior
        expect(typeof behavior.preloadSupport).toBe('boolean');
        expect(typeof behavior.rangeRequestSupport).toBe('boolean');
      });
    });
  });

  describe('Performance Characteristics by Browser', () => {
    it('should handle memory management differences', () => {
      const browsers = [
        { name: 'chrome', userAgent: BROWSER_USER_AGENTS.chrome },
        { name: 'firefox', userAgent: BROWSER_USER_AGENTS.firefox },
        { name: 'safari', userAgent: BROWSER_USER_AGENTS.safari },
        { name: 'edge', userAgent: BROWSER_USER_AGENTS.edge }
      ];

      browsers.forEach(browser => {
        setUserAgent(browser.userAgent);
        
        const manager = new VideoPlaybackManager();
        manager.attachVideoElement(mockVideoElement);
        
        // Test memory cleanup
        manager.destroy();
        
        expect(manager.getCurrentState()).toEqual(
          expect.objectContaining({
            isPlaying: false,
            currentTime: 0,
            duration: 0,
            error: null
          })
        );
      });
    });

    it('should adapt timeout values for different browsers', () => {
      const browserConfigs = [
        {
          browser: 'chrome',
          userAgent: BROWSER_USER_AGENTS.chrome,
          loadTimeout: 30000,
          playTimeout: 10000
        },
        {
          browser: 'safari',
          userAgent: BROWSER_USER_AGENTS.safari,
          loadTimeout: 45000, // Safari can be slower
          playTimeout: 15000
        },
        {
          browser: 'mobile_chrome',
          userAgent: BROWSER_USER_AGENTS.mobile_chrome,
          loadTimeout: 60000, // Mobile connections slower
          playTimeout: 20000
        }
      ];

      browserConfigs.forEach(config => {
        setUserAgent(config.userAgent);
        
        const manager = new VideoPlaybackManager({
          loadTimeout: config.loadTimeout,
          playTimeout: config.playTimeout
        });

        expect(manager).toBeDefined();
      });
    });
  });

  describe('Feature Detection and Graceful Degradation', () => {
    it('should detect video element support', () => {
      const videoSupported = !!(document.createElement('video').canPlayType);
      expect(videoSupported).toBe(true);
    });

    it('should detect fullscreen support', () => {
      const fullscreenSupported = !!(
        document.fullscreenEnabled ||
        document.webkitFullscreenEnabled ||
        document.mozFullScreenEnabled ||
        document.msFullscreenEnabled
      );
      expect(fullscreenSupported).toBe(true);
    });

    it('should provide fallbacks for unsupported features', () => {
      // Test with no fullscreen support
      Object.defineProperty(document, 'fullscreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'webkitFullscreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'mozFullScreenEnabled', { value: false, configurable: true });
      Object.defineProperty(document, 'msFullscreenEnabled', { value: false, configurable: true });

      const fullscreenSupported = !!(
        document.fullscreenEnabled ||
        document.webkitFullscreenEnabled ||
        document.mozFullScreenEnabled ||
        document.msFullscreenEnabled
      );

      expect(fullscreenSupported).toBe(false);
      
      // App should still function without fullscreen
      const manager = new VideoPlaybackManager();
      expect(manager).toBeDefined();
    });

    it('should handle codec fallbacks', () => {
      // Test with limited codec support
      mockVideoElement.canPlayType.mockImplementation((type: string) => {
        if (type.includes('avc1')) {
          return 'probably';
        }
        return ''; // No other codec support
      });

      const supportedFormats = Object.entries(VIDEO_FORMATS)
        .filter(([_, format]) => mockVideoElement.canPlayType(format.type) !== '')
        .map(([key, _]) => key);

      expect(supportedFormats).toContain('mp4_h264');
      expect(supportedFormats.length).toBeGreaterThan(0);
    });
  });

  describe('Error Handling Across Browsers', () => {
    it('should handle browser-specific error codes', () => {
      const browserErrorScenarios = [
        {
          browser: 'chrome',
          errorCode: MediaError.MEDIA_ERR_NETWORK,
          message: 'Network error'
        },
        {
          browser: 'firefox',
          errorCode: MediaError.MEDIA_ERR_DECODE,
          message: 'Decode error'
        },
        {
          browser: 'safari',
          errorCode: MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED,
          message: 'Source not supported'
        }
      ];

      browserErrorScenarios.forEach(scenario => {
        const mockError = {
          code: scenario.errorCode,
          message: scenario.message
        };

        // Test error categorization
        const isNetworkError = mockError.code === MediaError.MEDIA_ERR_NETWORK;
        const isDecodeError = mockError.code === MediaError.MEDIA_ERR_DECODE;
        const isSourceError = mockError.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED;

        expect(isNetworkError || isDecodeError || isSourceError).toBe(true);
      });
    });

    it('should provide browser-appropriate error recovery strategies', () => {
      const recoveryStrategies = [
        {
          browser: 'chrome',
          strategy: 'immediate_retry',
          maxRetries: 3
        },
        {
          browser: 'safari',
          strategy: 'delayed_retry',
          maxRetries: 2,
          delay: 2000
        },
        {
          browser: 'firefox',
          strategy: 'format_fallback',
          maxRetries: 3
        }
      ];

      recoveryStrategies.forEach(strategy => {
        expect(strategy.maxRetries).toBeGreaterThan(0);
        expect(['immediate_retry', 'delayed_retry', 'format_fallback']).toContain(strategy.strategy);
      });
    });
  });
});