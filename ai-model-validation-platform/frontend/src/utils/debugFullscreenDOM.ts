/**
 * Debug Utility for DOM Fullscreen Issues
 * Comprehensive testing and analysis for HIL test execution fullscreen problems
 */

import React from 'react';

interface FullscreenDebugResult {
  timestamp: string;
  testName: string;
  success: boolean;
  details: any;
  error?: string;
  recommendations: string[];
}

export class FullscreenDebugger {
  private results: FullscreenDebugResult[] = [];

  constructor(private debugMode: boolean = true) {}

  /**
   * Run comprehensive fullscreen debugging
   */
  public async runFullDiagnostics(
    videoRef?: React.RefObject<HTMLVideoElement>,
    containerRef?: React.RefObject<HTMLDivElement>
  ): Promise<FullscreenDebugResult[]> {
    this.results = [];

    if (this.debugMode) {
      console.log('🔍 Starting comprehensive fullscreen DOM diagnostics...');
    }

    // Test 1: Browser API Support
    await this.testBrowserAPISupport();

    // Test 2: Document Fullscreen Enabled
    await this.testDocumentFullscreenEnabled();

    // Test 3: Element Accessibility
    await this.testElementAccessibility(videoRef, containerRef);

    // Test 4: CSS Conflicts
    await this.testCSSConflicts(videoRef?.current || containerRef?.current);

    // Test 5: Event Listeners
    await this.testEventListeners();

    // Test 6: Security Policies
    await this.testSecurityPolicies();

    // Test 7: User Interaction Requirements
    await this.testUserInteractionRequirements();

    // Test 8: Video Element Readiness
    if (videoRef?.current) {
      await this.testVideoElementReadiness(videoRef.current);
    }

    // Test 9: Material-UI Conflicts
    await this.testMaterialUIConflicts();

    // Test 10: Fullscreen Attempt Simulation
    await this.testFullscreenAttemptSimulation(containerRef?.current);

    if (this.debugMode) {
      console.log('✅ Fullscreen diagnostics complete. Results:', this.results);
    }

    return this.results;
  }

  /**
   * Test browser API support
   */
  private async testBrowserAPISupport(): Promise<void> {
    const testName = 'Browser API Support';
    const details: any = {};

    try {
      // Check for standard API
      details.standardAPI = {
        requestFullscreen: typeof Element.prototype.requestFullscreen === 'function',
        exitFullscreen: typeof document.exitFullscreen === 'function',
        fullscreenElement: 'fullscreenElement' in document,
        fullscreenEnabled: 'fullscreenEnabled' in document,
      };

      // Check vendor prefixes
      details.vendorPrefixes = {
        webkit: {
          requestFullscreen: typeof (Element.prototype as any).webkitRequestFullscreen === 'function',
          exitFullscreen: typeof (document as any).webkitExitFullscreen === 'function',
          fullscreenElement: 'webkitFullscreenElement' in document,
          fullscreenEnabled: 'webkitFullscreenEnabled' in document,
        },
        moz: {
          requestFullscreen: typeof (Element.prototype as any).mozRequestFullScreen === 'function',
          exitFullscreen: typeof (document as any).mozCancelFullScreen === 'function',
          fullscreenElement: 'mozFullScreenElement' in document,
          fullscreenEnabled: 'mozFullScreenEnabled' in document,
        },
        ms: {
          requestFullscreen: typeof (Element.prototype as any).msRequestFullscreen === 'function',
          exitFullscreen: typeof (document as any).msExitFullscreen === 'function',
          fullscreenElement: 'msFullscreenElement' in document,
          fullscreenEnabled: 'msFullscreenEnabled' in document,
        },
      };

      details.userAgent = navigator.userAgent;
      
      const hasAnySupport = 
        details.standardAPI.requestFullscreen || 
        details.vendorPrefixes.webkit.requestFullscreen || 
        details.vendorPrefixes.moz.requestFullscreen || 
        details.vendorPrefixes.ms.requestFullscreen;

      this.addResult({
        testName,
        success: hasAnySupport,
        details,
        recommendations: hasAnySupport ? [] : [
          'Browser does not support fullscreen API',
          'Consider implementing CSS-based fullscreen fallback',
          'Test on different browsers for compatibility',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error testing browser API support'],
      });
    }
  }

  /**
   * Test document fullscreen enabled
   */
  private async testDocumentFullscreenEnabled(): Promise<void> {
    const testName = 'Document Fullscreen Enabled';
    const details: any = {};

    try {
      details.fullscreenEnabled = document.fullscreenEnabled;
      details.webkitFullscreenEnabled = (document as any).webkitFullscreenEnabled;
      details.mozFullScreenEnabled = (document as any).mozFullScreenEnabled;
      details.msFullscreenEnabled = (document as any).msFullscreenEnabled;

      const isEnabled = 
        document.fullscreenEnabled || 
        (document as any).webkitFullscreenEnabled || 
        (document as any).mozFullScreenEnabled || 
        (document as any).msFullscreenEnabled;

      const recommendations = [];
      if (!isEnabled) {
        recommendations.push('Fullscreen is disabled in browser settings or by policy');
        recommendations.push('Check browser permissions and user preferences');
        recommendations.push('Test in incognito/private mode to rule out extensions');
      }

      this.addResult({
        testName,
        success: isEnabled,
        details,
        recommendations,
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error checking fullscreen enabled status'],
      });
    }
  }

  /**
   * Test element accessibility
   */
  private async testElementAccessibility(
    videoRef?: React.RefObject<HTMLVideoElement>,
    containerRef?: React.RefObject<HTMLDivElement>
  ): Promise<void> {
    const testName = 'Element Accessibility';
    const details: any = {};

    try {
      // Test video element
      if (videoRef) {
        details.videoElement = {
          exists: !!videoRef.current,
          isHTMLVideoElement: videoRef.current instanceof HTMLVideoElement,
          isConnected: videoRef.current?.isConnected,
          hasParent: !!videoRef.current?.parentElement,
          inDOM: document.contains(videoRef.current),
          boundingRect: videoRef.current?.getBoundingClientRect(),
        };
      }

      // Test container element
      if (containerRef) {
        details.containerElement = {
          exists: !!containerRef.current,
          isHTMLElement: containerRef.current instanceof HTMLElement,
          isConnected: containerRef.current?.isConnected,
          hasParent: !!containerRef.current?.parentElement,
          inDOM: document.contains(containerRef.current),
          boundingRect: containerRef.current?.getBoundingClientRect(),
        };
      }

      // Check if any video elements exist in DOM
      const videoElements = document.querySelectorAll('video');
      details.videoElementsInDOM = Array.from(videoElements).map(video => ({
        tagName: video.tagName,
        id: video.id,
        className: video.className,
        src: video.src,
        isConnected: video.isConnected,
        readyState: video.readyState,
        boundingRect: video.getBoundingClientRect(),
      }));

      const success = 
        (videoRef ? details.videoElement.exists && details.videoElement.isConnected : true) &&
        (containerRef ? details.containerElement.exists && details.containerElement.isConnected : true);

      const recommendations = [];
      if (!success) {
        recommendations.push('Elements are not properly mounted or accessible');
        recommendations.push('Check React ref assignment and component lifecycle');
        recommendations.push('Ensure elements are rendered before fullscreen attempt');
      }

      this.addResult({
        testName,
        success,
        details,
        recommendations,
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error testing element accessibility'],
      });
    }
  }

  /**
   * Test CSS conflicts
   */
  private async testCSSConflicts(targetElement?: Element): Promise<void> {
    const testName = 'CSS Conflicts';
    const details: any = {};

    try {
      const element = targetElement || document.querySelector('video') || document.body;
      const computedStyle = window.getComputedStyle(element);

      details.targetElement = this.getElementSelector(element);
      details.computedStyles = {
        position: computedStyle.position,
        zIndex: computedStyle.zIndex,
        transform: computedStyle.transform,
        opacity: computedStyle.opacity,
        visibility: computedStyle.visibility,
        display: computedStyle.display,
        overflow: computedStyle.overflow,
        pointerEvents: computedStyle.pointerEvents,
      };

      // Check ancestors for problematic styles
      details.ancestorIssues = [];
      let current = element.parentElement;
      while (current && current !== document.body) {
        const style = window.getComputedStyle(current);
        
        if (style.position === 'fixed' || style.position === 'sticky') {
          details.ancestorIssues.push({
            element: this.getElementSelector(current),
            issue: `position: ${style.position}`,
          });
        }

        if (style.overflow === 'hidden' || style.overflow === 'scroll') {
          details.ancestorIssues.push({
            element: this.getElementSelector(current),
            issue: `overflow: ${style.overflow}`,
          });
        }

        if (style.zIndex !== 'auto' && parseInt(style.zIndex) > 9000) {
          details.ancestorIssues.push({
            element: this.getElementSelector(current),
            issue: `high z-index: ${style.zIndex}`,
          });
        }

        current = current.parentElement;
      }

      const success = details.ancestorIssues.length === 0;
      const recommendations = success ? [] : [
        'CSS properties on element or ancestors may interfere with fullscreen',
        'Consider adjusting position, overflow, or z-index values',
        'Test with minimal CSS to isolate conflicts',
      ];

      this.addResult({
        testName,
        success,
        details,
        recommendations,
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error analyzing CSS conflicts'],
      });
    }
  }

  /**
   * Test event listeners
   */
  private async testEventListeners(): Promise<void> {
    const testName = 'Event Listeners';
    const details: any = {};

    try {
      // Test if fullscreen events can be registered
      let changeEventWorks = false;
      let errorEventWorks = false;

      const testChangeListener = () => { changeEventWorks = true; };
      const testErrorListener = () => { errorEventWorks = true; };

      try {
        document.addEventListener('fullscreenchange', testChangeListener);
        document.addEventListener('fullscreenerror', testErrorListener);
        
        // Clean up immediately
        document.removeEventListener('fullscreenchange', testChangeListener);
        document.removeEventListener('fullscreenerror', testErrorListener);
        
        changeEventWorks = true;
        errorEventWorks = true;
      } catch (e) {
        // Events not supported
      }

      details.eventSupport = {
        fullscreenchange: changeEventWorks,
        fullscreenerror: errorEventWorks,
      };

      // Check for vendor-prefixed events
      const vendorEvents = [
        'webkitfullscreenchange',
        'mozfullscreenchange', 
        'MSFullscreenChange',
      ];

      details.vendorEventSupport = {};
      vendorEvents.forEach(event => {
        try {
          document.addEventListener(event, () => {});
          document.removeEventListener(event, () => {});
          details.vendorEventSupport[event] = true;
        } catch (e) {
          details.vendorEventSupport[event] = false;
        }
      });

      const success = changeEventWorks || errorEventWorks;

      this.addResult({
        testName,
        success,
        details,
        recommendations: success ? [] : [
          'Fullscreen events may not be supported',
          'Consider using polling or alternative state management',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error testing event listeners'],
      });
    }
  }

  /**
   * Test security policies
   */
  private async testSecurityPolicies(): Promise<void> {
    const testName = 'Security Policies';
    const details: any = {};

    try {
      // Check for feature policy
      details.featurePolicy = {
        fullscreen: (document as any).featurePolicy?.allowsFeature?.('fullscreen') ?? 'unknown',
      };

      // Check for permissions API
      if ('permissions' in navigator) {
        try {
          // Note: 'fullscreen' permission is not widely supported in permissions API
          details.permissionsAPI = 'supported';
        } catch (e) {
          details.permissionsAPI = 'error';
        }
      } else {
        details.permissionsAPI = 'not_supported';
      }

      // Check for secure context
      details.isSecureContext = window.isSecureContext;
      details.protocol = window.location.protocol;

      // Check iframe context
      details.inIframe = window !== window.top;
      if (details.inIframe) {
        details.iframeSandbox = (document.querySelector('iframe') as HTMLIFrameElement)?.sandbox?.toString();
      }

      const success = details.isSecureContext || details.protocol === 'file:';

      this.addResult({
        testName,
        success,
        details,
        recommendations: success ? [] : [
          'Fullscreen may require secure context (HTTPS)',
          'Check iframe sandbox attributes if running in iframe',
          'Test outside of iframe context',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error checking security policies'],
      });
    }
  }

  /**
   * Test user interaction requirements
   */
  private async testUserInteractionRequirements(): Promise<void> {
    const testName = 'User Interaction Requirements';
    const details: any = {};

    try {
      // Check if we're in a user activation context
      details.hasUserActivation = (navigator as any).userActivation?.isActive ?? 'unknown';
      details.userAgent = navigator.userAgent;
      
      // Many browsers require user activation for fullscreen
      const requiresUserActivation = /Chrome|Safari|Firefox/.test(navigator.userAgent);
      details.requiresUserActivation = requiresUserActivation;

      const success = !requiresUserActivation || details.hasUserActivation === true;

      this.addResult({
        testName,
        success,
        details,
        recommendations: success ? [] : [
          'Fullscreen requests may require user interaction (click, touch)',
          'Ensure fullscreen is triggered from user event handler',
          'Consider showing user instruction to interact first',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error checking user interaction requirements'],
      });
    }
  }

  /**
   * Test video element readiness
   */
  private async testVideoElementReadiness(videoElement: HTMLVideoElement): Promise<void> {
    const testName = 'Video Element Readiness';
    const details: any = {};

    try {
      details.readyState = videoElement.readyState;
      details.networkState = videoElement.networkState;
      details.error = videoElement.error ? {
        code: videoElement.error.code,
        message: videoElement.error.message,
      } : null;
      
      details.src = videoElement.src;
      details.currentSrc = videoElement.currentSrc;
      details.duration = videoElement.duration;
      details.paused = videoElement.paused;
      details.ended = videoElement.ended;
      
      details.videoWidth = videoElement.videoWidth;
      details.videoHeight = videoElement.videoHeight;
      details.clientWidth = videoElement.clientWidth;
      details.clientHeight = videoElement.clientHeight;

      const success = 
        videoElement.readyState >= 3 && // HAVE_FUTURE_DATA
        !videoElement.error &&
        videoElement.videoWidth > 0 &&
        videoElement.videoHeight > 0;

      this.addResult({
        testName,
        success,
        details,
        recommendations: success ? [] : [
          'Video element is not ready for fullscreen',
          'Wait for readyState >= HAVE_FUTURE_DATA before fullscreen',
          'Check for video loading errors',
          'Ensure video has valid dimensions',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error checking video element readiness'],
      });
    }
  }

  /**
   * Test Material-UI conflicts
   */
  private async testMaterialUIConflicts(): Promise<void> {
    const testName = 'Material-UI Conflicts';
    const details: any = {};

    try {
      // Check for Material-UI root elements
      const muiRoot = document.querySelector('#root, [data-mui-root]');
      details.muiRootFound = !!muiRoot;

      // Check for portal containers
      const portals = document.querySelectorAll('[data-mui-portal]');
      details.portalsFound = portals.length;

      // Check for high z-index Material-UI components
      const highZIndexElements = Array.from(document.querySelectorAll('*')).filter(el => {
        const zIndex = window.getComputedStyle(el).zIndex;
        return zIndex !== 'auto' && parseInt(zIndex) > 1000;
      });

      details.highZIndexElements = highZIndexElements.map(el => ({
        element: this.getElementSelector(el),
        zIndex: window.getComputedStyle(el).zIndex,
      }));

      // Check for backdrop elements
      const backdrops = document.querySelectorAll('.MuiBackdrop-root, [class*="backdrop"]');
      details.backdropsFound = backdrops.length;

      const success = details.highZIndexElements.length < 5; // Arbitrary threshold

      this.addResult({
        testName,
        success,
        details,
        recommendations: success ? [] : [
          'High z-index Material-UI components may interfere with fullscreen',
          'Consider adjusting Material-UI theme z-index values',
          'Test with minimal Material-UI components',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error checking Material-UI conflicts'],
      });
    }
  }

  /**
   * Simulate fullscreen attempt
   */
  private async testFullscreenAttemptSimulation(targetElement?: Element): Promise<void> {
    const testName = 'Fullscreen Attempt Simulation';
    const details: any = {};

    try {
      const element = targetElement || document.documentElement;
      
      details.targetElement = this.getElementSelector(element);
      details.isConnected = element.isConnected;
      details.hasRequestFullscreen = typeof (element as any).requestFullscreen === 'function';

      // Check all vendor prefixes
      const methods = [
        'requestFullscreen',
        'webkitRequestFullscreen',
        'mozRequestFullScreen',
        'msRequestFullscreen',
      ];

      details.availableMethods = methods.filter(method => 
        typeof (element as any)[method] === 'function'
      );

      // Simulate the call (but don't actually execute)
      details.simulationNotes = [
        'This is a simulation - actual fullscreen not attempted',
        'Real attempt would require user interaction',
      ];

      const success = details.availableMethods.length > 0 && details.isConnected;

      this.addResult({
        testName,
        success,
        details,
        recommendations: success ? [
          'Element appears ready for fullscreen attempt',
          'Ensure real attempt is triggered by user interaction',
        ] : [
          'Element may not be ready for fullscreen',
          'Check element connection and available methods',
        ],
      });

    } catch (error) {
      this.addResult({
        testName,
        success: false,
        details,
        error: String(error),
        recommendations: ['Error simulating fullscreen attempt'],
      });
    }
  }

  /**
   * Generate comprehensive report
   */
  public generateReport(): string {
    const report = [];
    
    report.push('# DOM Fullscreen Debug Report');
    report.push(`Generated: ${new Date().toISOString()}`);
    report.push(`Total Tests: ${this.results.length}`);
    report.push(`Passed: ${this.results.filter(r => r.success).length}`);
    report.push(`Failed: ${this.results.filter(r => !r.success).length}`);
    report.push('');

    this.results.forEach((result, index) => {
      report.push(`## Test ${index + 1}: ${result.testName}`);
      report.push(`Status: ${result.success ? '✅ PASS' : '❌ FAIL'}`);
      
      if (result.error) {
        report.push(`Error: ${result.error}`);
      }

      if (result.recommendations.length > 0) {
        report.push('Recommendations:');
        result.recommendations.forEach(rec => {
          report.push(`- ${rec}`);
        });
      }

      report.push('');
    });

    // Summary
    const failedTests = this.results.filter(r => !r.success);
    if (failedTests.length > 0) {
      report.push('## Critical Issues');
      failedTests.forEach(test => {
        report.push(`- ${test.testName}: ${test.error || 'Test failed'}`);
      });
    }

    return report.join('\n');
  }

  /**
   * Get test results
   */
  public getResults(): FullscreenDebugResult[] {
    return this.results;
  }

  // Helper methods
  private addResult(result: Omit<FullscreenDebugResult, 'timestamp'>): void {
    this.results.push({
      ...result,
      timestamp: new Date().toISOString(),
    });

    if (this.debugMode) {
      const status = result.success ? '✅' : '❌';
      console.log(`${status} ${result.testName}`, result);
    }
  }

  private getElementSelector(element: Element): string {
    const tagName = element.tagName.toLowerCase();
    const id = element.id ? `#${element.id}` : '';
    const classes = element.className ? `.${Array.from(element.classList).slice(0, 2).join('.')}` : '';
    return `${tagName}${id}${classes}`;
  }
}

// Export utility function
export const debugFullscreenDOM = async (
  videoRef?: React.RefObject<HTMLVideoElement>,
  containerRef?: React.RefObject<HTMLDivElement>
): Promise<FullscreenDebugResult[]> => {
  const debugger = new FullscreenDebugger(true);
  return debugger.runFullDiagnostics(videoRef, containerRef);
};

export const generateFullscreenDebugReport = async (
  videoRef?: React.RefObject<HTMLVideoElement>,
  containerRef?: React.RefObject<HTMLDivElement>
): Promise<string> => {
  const debugger = new FullscreenDebugger(true);
  await debugger.runFullDiagnostics(videoRef, containerRef);
  return debugger.generateReport();
};