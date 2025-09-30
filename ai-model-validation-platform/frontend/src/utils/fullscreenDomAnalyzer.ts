/**
 * Comprehensive DOM Fullscreen Analysis Utility
 * Analyzes DOM structure, element states, and browser compatibility issues
 * for fullscreen functionality in HIL test execution
 */

export interface FullscreenDiagnostics {
  browserSupport: {
    fullscreenEnabled: boolean;
    requestFullscreenSupported: boolean;
    exitFullscreenSupported: boolean;
    fullscreenElementSupported: boolean;
    fullscreenChangeEventSupported: boolean;
    fullscreenErrorEventSupported: boolean;
    browserVendorPrefixes: string[];
  };
  domStructure: {
    videoElementExists: boolean;
    videoElementAccessible: boolean;
    containerElementExists: boolean;
    containerElementAccessible: boolean;
    elementHierarchy: string[];
    refTargetingValid: boolean;
  };
  cssAnalysis: {
    conflictingProperties: Array<{
      element: string;
      property: string;
      value: string;
      impact: 'blocking' | 'warning' | 'info';
    }>;
    zIndexIssues: Array<{
      element: string;
      zIndex: string;
      recommendation: string;
    }>;
    positioningIssues: Array<{
      element: string;
      position: string;
      issue: string;
    }>;
    overflowIssues: Array<{
      element: string;
      overflow: string;
      issue: string;
    }>;
  };
  eventListeners: {
    fullscreenChangeRegistered: boolean;
    fullscreenErrorRegistered: boolean;
    videoEventListeners: string[];
    possibleConflicts: string[];
  };
  runtimeState: {
    currentFullscreenElement: Element | null;
    isFullscreenActive: boolean;
    videoReadyState: number;
    videoNetworkState: number;
    videoError: MediaError | null;
    documentVisibilityState: string;
  };
  recommendations: Array<{
    category: 'critical' | 'warning' | 'optimization';
    issue: string;
    solution: string;
    codeExample?: string;
  }>;
}

export class FullscreenDOMAnalyzer {
  private diagnostics: FullscreenDiagnostics;

  constructor() {
    this.diagnostics = this.initializeDiagnostics();
  }

  private initializeDiagnostics(): FullscreenDiagnostics {
    return {
      browserSupport: {
        fullscreenEnabled: false,
        requestFullscreenSupported: false,
        exitFullscreenSupported: false,
        fullscreenElementSupported: false,
        fullscreenChangeEventSupported: false,
        fullscreenErrorEventSupported: false,
        browserVendorPrefixes: [],
      },
      domStructure: {
        videoElementExists: false,
        videoElementAccessible: false,
        containerElementExists: false,
        containerElementAccessible: false,
        elementHierarchy: [],
        refTargetingValid: false,
      },
      cssAnalysis: {
        conflictingProperties: [],
        zIndexIssues: [],
        positioningIssues: [],
        overflowIssues: [],
      },
      eventListeners: {
        fullscreenChangeRegistered: false,
        fullscreenErrorRegistered: false,
        videoEventListeners: [],
        possibleConflicts: [],
      },
      runtimeState: {
        currentFullscreenElement: null,
        isFullscreenActive: false,
        videoReadyState: 0,
        videoNetworkState: 0,
        videoError: null,
        documentVisibilityState: 'visible',
      },
      recommendations: [],
    };
  }

  /**
   * Analyze browser support for fullscreen APIs
   */
  public analyzeBrowserSupport(): void {
    console.log('🔍 Analyzing browser fullscreen API support...');

    // Check document.fullscreenEnabled
    this.diagnostics.browserSupport.fullscreenEnabled = 
      document.fullscreenEnabled || false;

    // Check vendor prefixes and API support
    const testElement = document.createElement('div');
    const prefixes = ['', 'webkit', 'moz', 'ms'];
    
    for (const prefix of prefixes) {
      const requestMethod = prefix ? `${prefix}RequestFullscreen` : 'requestFullscreen';
      const exitMethod = prefix ? `${prefix}ExitFullscreen` : 'exitFullscreen';
      const elementProp = prefix ? `${prefix}FullscreenElement` : 'fullscreenElement';
      
      if (typeof (testElement as any)[requestMethod] === 'function') {
        this.diagnostics.browserSupport.requestFullscreenSupported = true;
        if (prefix) this.diagnostics.browserSupport.browserVendorPrefixes.push(prefix);
      }
      
      if (typeof (document as any)[exitMethod] === 'function') {
        this.diagnostics.browserSupport.exitFullscreenSupported = true;
      }
      
      if ((document as any)[elementProp] !== undefined) {
        this.diagnostics.browserSupport.fullscreenElementSupported = true;
      }
    }

    // Check event support
    try {
      document.addEventListener('fullscreenchange', () => {});
      this.diagnostics.browserSupport.fullscreenChangeEventSupported = true;
    } catch (e) {
      console.warn('fullscreenchange event not supported');
    }

    try {
      document.addEventListener('fullscreenerror', () => {});
      this.diagnostics.browserSupport.fullscreenErrorEventSupported = true;
    } catch (e) {
      console.warn('fullscreenerror event not supported');
    }

    console.log('✅ Browser support analysis complete:', this.diagnostics.browserSupport);
  }

  /**
   * Analyze DOM structure and element accessibility
   */
  public analyzeDOMStructure(videoRef?: React.RefObject<HTMLVideoElement>, containerRef?: React.RefObject<HTMLDivElement>): void {
    console.log('🔍 Analyzing DOM structure for fullscreen elements...');

    // Check video element
    if (videoRef?.current) {
      this.diagnostics.domStructure.videoElementExists = true;
      this.diagnostics.domStructure.videoElementAccessible = 
        videoRef.current instanceof HTMLVideoElement &&
        videoRef.current.isConnected &&
        videoRef.current.parentElement !== null;
    } else {
      // Fallback: search for video elements in document
      const videoElements = document.querySelectorAll('video');
      this.diagnostics.domStructure.videoElementExists = videoElements.length > 0;
      if (videoElements.length > 0) {
        this.diagnostics.domStructure.videoElementAccessible = 
          videoElements[0].isConnected && videoElements[0].parentElement !== null;
      }
    }

    // Check container element
    if (containerRef?.current) {
      this.diagnostics.domStructure.containerElementExists = true;
      this.diagnostics.domStructure.containerElementAccessible = 
        containerRef.current instanceof HTMLElement &&
        containerRef.current.isConnected &&
        containerRef.current.parentElement !== null;
    } else {
      // Fallback: search for fullscreen container
      const containers = document.querySelectorAll('[data-testid="fullscreen-container"], .fullscreen-container, #fullscreen-container');
      this.diagnostics.domStructure.containerElementExists = containers.length > 0;
      if (containers.length > 0) {
        this.diagnostics.domStructure.containerElementAccessible = 
          containers[0].isConnected && containers[0].parentElement !== null;
      }
    }

    // Build element hierarchy
    const targetElement = videoRef?.current || containerRef?.current || document.querySelector('video');
    if (targetElement) {
      let current = targetElement;
      const hierarchy: string[] = [];
      
      while (current && current !== document.body) {
        const tagName = current.tagName.toLowerCase();
        const id = current.id ? `#${current.id}` : '';
        const classes = current.className ? `.${Array.from(current.classList).join('.')}` : '';
        hierarchy.unshift(`${tagName}${id}${classes}`);
        current = current.parentElement;
      }
      
      this.diagnostics.domStructure.elementHierarchy = hierarchy;
    }

    // Validate ref targeting
    this.diagnostics.domStructure.refTargetingValid = 
      (videoRef?.current instanceof HTMLVideoElement) ||
      (containerRef?.current instanceof HTMLElement);

    console.log('✅ DOM structure analysis complete:', this.diagnostics.domStructure);
  }

  /**
   * Analyze CSS properties that might interfere with fullscreen
   */
  public analyzeCSSConflicts(targetElement?: Element): void {
    console.log('🔍 Analyzing CSS conflicts for fullscreen...');

    const element = targetElement || document.querySelector('video') || document.body;
    if (!element) return;

    // Check for conflicting CSS properties
    const computedStyle = window.getComputedStyle(element);
    const conflictingProperties = [
      { property: 'position', problematicValues: ['fixed'], impact: 'warning' as const },
      { property: 'transform', problematicValues: ['none'], impact: 'info' as const, invert: true },
      { property: 'will-change', problematicValues: ['transform'], impact: 'info' as const },
      { property: 'contain', problematicValues: ['layout', 'style'], impact: 'warning' as const },
      { property: 'isolation', problematicValues: ['isolate'], impact: 'warning' as const },
    ];

    conflictingProperties.forEach(({ property, problematicValues, impact, invert }) => {
      const value = computedStyle.getPropertyValue(property);
      const isProblematic = invert ? 
        !problematicValues.includes(value) : 
        problematicValues.some(pv => value.includes(pv));
      
      if (isProblematic) {
        this.diagnostics.cssAnalysis.conflictingProperties.push({
          element: this.getElementSelector(element),
          property,
          value,
          impact,
        });
      }
    });

    // Analyze z-index issues
    let current: Element | null = element;
    while (current && current !== document.body) {
      const style = window.getComputedStyle(current);
      const zIndex = style.zIndex;
      
      if (zIndex !== 'auto' && parseInt(zIndex) > 9000) {
        this.diagnostics.cssAnalysis.zIndexIssues.push({
          element: this.getElementSelector(current),
          zIndex,
          recommendation: 'Consider reducing z-index or ensuring fullscreen element has higher z-index',
        });
      }
      
      current = current.parentElement;
    }

    // Analyze positioning issues
    const ancestors = this.getAncestors(element);
    ancestors.forEach(ancestor => {
      const style = window.getComputedStyle(ancestor);
      const position = style.position;
      
      if (['fixed', 'sticky'].includes(position)) {
        this.diagnostics.cssAnalysis.positioningIssues.push({
          element: this.getElementSelector(ancestor),
          position,
          issue: `${position} positioning may interfere with fullscreen`,
        });
      }

      const overflow = style.overflow;
      if (['hidden', 'scroll', 'auto'].includes(overflow) && ancestor !== element) {
        this.diagnostics.cssAnalysis.overflowIssues.push({
          element: this.getElementSelector(ancestor),
          overflow,
          issue: `${overflow} overflow on ancestor may clip fullscreen content`,
        });
      }
    });

    console.log('✅ CSS conflict analysis complete:', this.diagnostics.cssAnalysis);
  }

  /**
   * Analyze event listeners and potential conflicts
   */
  public analyzeEventListeners(): void {
    console.log('🔍 Analyzing event listeners...');

    // Check for fullscreen event listeners
    // Note: This is limited since we can't directly inspect event listeners
    // but we can check for common patterns
    
    const fullscreenEvents = ['fullscreenchange', 'fullscreenerror'];
    const vendorEvents = ['webkitfullscreenchange', 'mozfullscreenchange', 'MSFullscreenChange'];
    
    // We'll use a heuristic approach - check if events fire
    const testChangeListener = () => {
      this.diagnostics.eventListeners.fullscreenChangeRegistered = true;
    };
    
    const testErrorListener = () => {
      this.diagnostics.eventListeners.fullscreenErrorRegistered = true;
    };

    // Temporarily add listeners to test
    document.addEventListener('fullscreenchange', testChangeListener);
    document.addEventListener('fullscreenerror', testErrorListener);
    
    // Clean up test listeners
    setTimeout(() => {
      document.removeEventListener('fullscreenchange', testChangeListener);
      document.removeEventListener('fullscreenerror', testErrorListener);
    }, 100);

    // Check video element for event listeners
    const videoElement = document.querySelector('video');
    if (videoElement) {
      const videoEvents = [
        'loadstart', 'loadeddata', 'loadedmetadata', 'canplay', 'canplaythrough',
        'playing', 'pause', 'ended', 'error', 'timeupdate', 'volumechange'
      ];
      
      this.diagnostics.eventListeners.videoEventListeners = videoEvents.filter(event => {
        // This is a heuristic - we can't directly detect listeners
        return true; // Assume they exist for comprehensive analysis
      });
    }

    console.log('✅ Event listener analysis complete:', this.diagnostics.eventListeners);
  }

  /**
   * Analyze current runtime state
   */
  public analyzeRuntimeState(): void {
    console.log('🔍 Analyzing runtime state...');

    // Current fullscreen state
    this.diagnostics.runtimeState.currentFullscreenElement = 
      document.fullscreenElement || 
      (document as any).webkitFullscreenElement ||
      (document as any).mozFullScreenElement ||
      (document as any).msFullscreenElement ||
      null;

    this.diagnostics.runtimeState.isFullscreenActive = 
      this.diagnostics.runtimeState.currentFullscreenElement !== null;

    // Video element state
    const videoElement = document.querySelector('video') as HTMLVideoElement;
    if (videoElement) {
      this.diagnostics.runtimeState.videoReadyState = videoElement.readyState;
      this.diagnostics.runtimeState.videoNetworkState = videoElement.networkState;
      this.diagnostics.runtimeState.videoError = videoElement.error;
    }

    // Document visibility
    this.diagnostics.runtimeState.documentVisibilityState = document.visibilityState;

    console.log('✅ Runtime state analysis complete:', this.diagnostics.runtimeState);
  }

  /**
   * Generate recommendations based on analysis
   */
  public generateRecommendations(): void {
    console.log('🔍 Generating fullscreen recommendations...');

    // Browser support recommendations
    if (!this.diagnostics.browserSupport.fullscreenEnabled) {
      this.diagnostics.recommendations.push({
        category: 'critical',
        issue: 'Document.fullscreenEnabled is false',
        solution: 'Check if fullscreen is disabled by browser policy or user preferences',
        codeExample: 'if (!document.fullscreenEnabled) { /* Handle fallback */ }',
      });
    }

    if (!this.diagnostics.browserSupport.requestFullscreenSupported) {
      this.diagnostics.recommendations.push({
        category: 'critical',
        issue: 'requestFullscreen API not supported',
        solution: 'Implement vendor prefix fallbacks or alternative fullscreen solution',
        codeExample: `
const requestFullscreen = element.requestFullscreen || 
  element.webkitRequestFullscreen || 
  element.mozRequestFullScreen || 
  element.msRequestFullscreen;`,
      });
    }

    // DOM structure recommendations
    if (!this.diagnostics.domStructure.videoElementExists) {
      this.diagnostics.recommendations.push({
        category: 'critical',
        issue: 'Video element not found in DOM',
        solution: 'Ensure video element is rendered before attempting fullscreen',
      });
    }

    if (!this.diagnostics.domStructure.refTargetingValid) {
      this.diagnostics.recommendations.push({
        category: 'warning',
        issue: 'React ref targeting may be invalid',
        solution: 'Verify refs are properly attached and elements are mounted',
        codeExample: `
useEffect(() => {
  if (videoRef.current && containerRef.current) {
    // Refs are ready
  }
}, []);`,
      });
    }

    // CSS conflict recommendations
    this.diagnostics.cssAnalysis.conflictingProperties.forEach(conflict => {
      this.diagnostics.recommendations.push({
        category: conflict.impact === 'blocking' ? 'critical' : 'warning',
        issue: `CSS property ${conflict.property}: ${conflict.value} may interfere with fullscreen`,
        solution: `Consider adjusting ${conflict.property} for fullscreen compatibility`,
      });
    });

    this.diagnostics.cssAnalysis.zIndexIssues.forEach(issue => {
      this.diagnostics.recommendations.push({
        category: 'warning',
        issue: `High z-index (${issue.zIndex}) detected`,
        solution: issue.recommendation,
      });
    });

    // Event listener recommendations
    if (!this.diagnostics.eventListeners.fullscreenChangeRegistered) {
      this.diagnostics.recommendations.push({
        category: 'warning',
        issue: 'Fullscreen change event listener not detected',
        solution: 'Add event listeners for fullscreen state changes',
        codeExample: `
document.addEventListener('fullscreenchange', () => {
  setIsFullScreen(!!document.fullscreenElement);
});`,
      });
    }

    // Runtime state recommendations
    if (this.diagnostics.runtimeState.videoError) {
      this.diagnostics.recommendations.push({
        category: 'critical',
        issue: `Video error: ${this.diagnostics.runtimeState.videoError.message}`,
        solution: 'Resolve video loading issues before attempting fullscreen',
      });
    }

    if (this.diagnostics.runtimeState.videoReadyState < 3) {
      this.diagnostics.recommendations.push({
        category: 'warning',
        issue: 'Video not ready for playback',
        solution: 'Wait for video readyState >= HAVE_FUTURE_DATA before fullscreen',
        codeExample: `
const waitForVideoReady = () => {
  return new Promise((resolve) => {
    if (videoRef.current.readyState >= 3) {
      resolve();
    } else {
      videoRef.current.addEventListener('canplay', resolve, { once: true });
    }
  });
};`,
      });
    }

    console.log('✅ Recommendations generated:', this.diagnostics.recommendations);
  }

  /**
   * Run comprehensive analysis
   */
  public runComprehensiveAnalysis(
    videoRef?: React.RefObject<HTMLVideoElement>,
    containerRef?: React.RefObject<HTMLDivElement>
  ): FullscreenDiagnostics {
    console.log('🚀 Starting comprehensive DOM fullscreen analysis...');

    this.analyzeBrowserSupport();
    this.analyzeDOMStructure(videoRef, containerRef);
    this.analyzeCSSConflicts(videoRef?.current || containerRef?.current);
    this.analyzeEventListeners();
    this.analyzeRuntimeState();
    this.generateRecommendations();

    console.log('✅ Comprehensive analysis complete');
    return this.diagnostics;
  }

  /**
   * Get diagnostics results
   */
  public getDiagnostics(): FullscreenDiagnostics {
    return this.diagnostics;
  }

  /**
   * Generate formatted report
   */
  public generateReport(): string {
    const report = [];
    
    report.push('# DOM Fullscreen Analysis Report');
    report.push('Generated on: ' + new Date().toISOString());
    report.push('');

    // Browser Support
    report.push('## Browser Support');
    report.push(`- Fullscreen Enabled: ${this.diagnostics.browserSupport.fullscreenEnabled ? '✅' : '❌'}`);
    report.push(`- Request Fullscreen: ${this.diagnostics.browserSupport.requestFullscreenSupported ? '✅' : '❌'}`);
    report.push(`- Exit Fullscreen: ${this.diagnostics.browserSupport.exitFullscreenSupported ? '✅' : '❌'}`);
    report.push(`- Vendor Prefixes: ${this.diagnostics.browserSupport.browserVendorPrefixes.join(', ') || 'None'}`);
    report.push('');

    // DOM Structure
    report.push('## DOM Structure');
    report.push(`- Video Element: ${this.diagnostics.domStructure.videoElementExists ? '✅' : '❌'}`);
    report.push(`- Container Element: ${this.diagnostics.domStructure.containerElementExists ? '✅' : '❌'}`);
    report.push(`- Element Hierarchy: ${this.diagnostics.domStructure.elementHierarchy.join(' > ')}`);
    report.push('');

    // CSS Analysis
    report.push('## CSS Conflicts');
    if (this.diagnostics.cssAnalysis.conflictingProperties.length > 0) {
      this.diagnostics.cssAnalysis.conflictingProperties.forEach(conflict => {
        report.push(`- ${conflict.element}: ${conflict.property} = ${conflict.value} (${conflict.impact})`);
      });
    } else {
      report.push('- No significant CSS conflicts detected');
    }
    report.push('');

    // Recommendations
    report.push('## Recommendations');
    if (this.diagnostics.recommendations.length > 0) {
      this.diagnostics.recommendations.forEach((rec, index) => {
        report.push(`${index + 1}. **${rec.category.toUpperCase()}**: ${rec.issue}`);
        report.push(`   Solution: ${rec.solution}`);
        if (rec.codeExample) {
          report.push(`   \`\`\`typescript\n   ${rec.codeExample}\n   \`\`\``);
        }
        report.push('');
      });
    } else {
      report.push('- No critical issues detected');
    }

    return report.join('\n');
  }

  // Helper methods
  private getElementSelector(element: Element): string {
    const tagName = element.tagName.toLowerCase();
    const id = element.id ? `#${element.id}` : '';
    const classes = element.className ? `.${Array.from(element.classList).slice(0, 3).join('.')}` : '';
    return `${tagName}${id}${classes}`;
  }

  private getAncestors(element: Element): Element[] {
    const ancestors: Element[] = [];
    let current = element.parentElement;
    
    while (current && current !== document.body) {
      ancestors.push(current);
      current = current.parentElement;
    }
    
    return ancestors;
  }
}

// Export singleton instance for easy use
export const fullscreenAnalyzer = new FullscreenDOMAnalyzer();

// Utility function for quick analysis
export const analyzeFullscreenDOM = (
  videoRef?: React.RefObject<HTMLVideoElement>,
  containerRef?: React.RefObject<HTMLDivElement>
): FullscreenDiagnostics => {
  return fullscreenAnalyzer.runComprehensiveAnalysis(videoRef, containerRef);
};