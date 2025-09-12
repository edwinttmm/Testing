/**
 * Enhanced Fullscreen Manager for Video Test Execution
 * 
 * Provides improved fullscreen API integration specifically designed for
 * video compatibility testing with better error handling and browser compatibility
 */

import { fullscreenManager, FullscreenState } from './fullscreenUtils';

export interface VideoFullscreenOptions {
  element: HTMLElement;
  videoElement?: HTMLVideoElement;
  onEnter?: () => void;
  onExit?: () => void;
  onError?: (error: Error) => void;
  autoHideCursor?: boolean;
  escapeKeyEnabled?: boolean;
  fallbackMode?: boolean;
}

export interface FullscreenTestResult {
  success: boolean;
  error?: Error;
  browserSupported: boolean;
  fallbackUsed: boolean;
  timeToFullscreen?: number;
}

export class EnhancedFullscreenManager {
  private static instance: EnhancedFullscreenManager | null = null;
  private activeOptions: VideoFullscreenOptions | null = null;
  private cursorTimer: NodeJS.Timeout | null = null;
  private keydownHandler: ((e: KeyboardEvent) => void) | null = null;
  private startTime: number = 0;

  constructor() {
    this.setupGlobalEventHandlers();
  }

  public static getInstance(): EnhancedFullscreenManager {
    if (!EnhancedFullscreenManager.instance) {
      EnhancedFullscreenManager.instance = new EnhancedFullscreenManager();
    }
    return EnhancedFullscreenManager.instance;
  }

  /**
   * Test fullscreen functionality with comprehensive browser support detection
   */
  public async testFullscreenSupport(): Promise<FullscreenTestResult> {
    const startTime = performance.now();
    
    try {
      // Check if fullscreen API is supported
      if (!fullscreenManager.isSupported()) {
        return {
          success: false,
          browserSupported: false,
          fallbackUsed: false,
          error: new Error('Fullscreen API not supported by browser'),
        };
      }

      // Create a temporary test element
      const testElement = document.createElement('div');
      testElement.style.cssText = `
        position: fixed;
        top: -1000px;
        left: -1000px;
        width: 1px;
        height: 1px;
        opacity: 0;
        pointer-events: none;
        z-index: -1;
      `;
      document.body.appendChild(testElement);

      try {
        // Attempt to enter fullscreen briefly
        await fullscreenManager.requestFullscreen(testElement);
        
        // Quick exit
        await fullscreenManager.exitFullscreen();
        
        const endTime = performance.now();
        
        return {
          success: true,
          browserSupported: true,
          fallbackUsed: false,
          timeToFullscreen: endTime - startTime,
        };
        
      } catch (testError) {
        return {
          success: false,
          browserSupported: true, // API exists but failed
          fallbackUsed: false,
          error: testError as Error,
        };
      } finally {
        document.body.removeChild(testElement);
      }
      
    } catch (error) {
      return {
        success: false,
        browserSupported: false,
        fallbackUsed: false,
        error: error as Error,
      };
    }
  }

  /**
   * Enhanced fullscreen request with video optimization
   */
  public async requestVideoFullscreen(options: VideoFullscreenOptions): Promise<FullscreenTestResult> {
    this.startTime = performance.now();
    this.activeOptions = options;

    try {
      // Pre-fullscreen optimizations
      this.optimizeForFullscreen(options);

      // Setup event handlers
      this.setupFullscreenEventHandlers(options);

      // Request fullscreen
      await fullscreenManager.requestFullscreen(options.element);

      const endTime = performance.now();
      
      // Post-fullscreen setup
      this.setupFullscreenEnvironment(options);

      options.onEnter?.();

      return {
        success: true,
        browserSupported: true,
        fallbackUsed: false,
        timeToFullscreen: endTime - this.startTime,
      };

    } catch (error) {
      this.cleanup();
      options.onError?.(error as Error);
      
      return {
        success: false,
        browserSupported: fullscreenManager.isSupported(),
        fallbackUsed: false,
        error: error as Error,
      };
    }
  }

  /**
   * Enhanced fullscreen exit
   */
  public async exitVideoFullscreen(): Promise<FullscreenTestResult> {
    const startTime = performance.now();
    
    try {
      await fullscreenManager.exitFullscreen();
      
      this.cleanup();
      this.activeOptions?.onExit?.();
      
      const endTime = performance.now();
      
      return {
        success: true,
        browserSupported: true,
        fallbackUsed: false,
        timeToFullscreen: endTime - startTime,
      };
      
    } catch (error) {
      this.cleanup();
      this.activeOptions?.onError?.(error as Error);
      
      return {
        success: false,
        browserSupported: fullscreenManager.isSupported(),
        fallbackUsed: false,
        error: error as Error,
      };
    }
  }

  /**
   * Check current fullscreen state
   */
  public getCurrentState(): FullscreenState {
    return fullscreenManager.getCurrentState();
  }

  /**
   * Toggle fullscreen with video optimization
   */
  public async toggleVideoFullscreen(options: VideoFullscreenOptions): Promise<FullscreenTestResult> {
    const currentState = this.getCurrentState();
    
    if (currentState.isFullscreen) {
      return this.exitVideoFullscreen();
    } else {
      return this.requestVideoFullscreen(options);
    }
  }

  /**
   * Setup global event handlers
   */
  private setupGlobalEventHandlers(): void {
    // Listen for fullscreen changes globally
    fullscreenManager.onFullscreenChange((state) => {
      if (!state.isFullscreen && this.activeOptions) {
        // Fullscreen exited (possibly by user pressing Escape)
        this.cleanup();
        this.activeOptions.onExit?.();
      }
    });

    // Listen for fullscreen errors
    fullscreenManager.onFullscreenError((error) => {
      if (this.activeOptions) {
        this.cleanup();
        this.activeOptions.onError?.(new Error(error));
      }
    });
  }

  /**
   * Optimize elements for fullscreen display
   */
  private optimizeForFullscreen(options: VideoFullscreenOptions): void {
    const { element, videoElement } = options;

    // Store original styles for restoration
    element.dataset.originalStyles = JSON.stringify({
      position: element.style.position,
      top: element.style.top,
      left: element.style.left,
      width: element.style.width,
      height: element.style.height,
      zIndex: element.style.zIndex,
      backgroundColor: element.style.backgroundColor,
    });

    // Optimize container
    element.style.position = 'relative';
    element.style.width = '100%';
    element.style.height = '100%';
    element.style.backgroundColor = '#000';
    element.style.display = 'flex';
    element.style.alignItems = 'center';
    element.style.justifyContent = 'center';

    // Optimize video element if provided
    if (videoElement) {
      videoElement.dataset.originalVideoStyles = JSON.stringify({
        width: videoElement.style.width,
        height: videoElement.style.height,
        maxWidth: videoElement.style.maxWidth,
        maxHeight: videoElement.style.maxHeight,
        objectFit: videoElement.style.objectFit,
      });

      videoElement.style.width = '100%';
      videoElement.style.height = '100%';
      videoElement.style.maxWidth = '100vw';
      videoElement.style.maxHeight = '100vh';
      videoElement.style.objectFit = 'contain';
    }
  }

  /**
   * Setup fullscreen-specific event handlers
   */
  private setupFullscreenEventHandlers(options: VideoFullscreenOptions): void {
    // Escape key handler
    if (options.escapeKeyEnabled !== false) {
      this.keydownHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          this.exitVideoFullscreen();
        }
      };
      document.addEventListener('keydown', this.keydownHandler);
    }
  }

  /**
   * Setup fullscreen environment (cursor hiding, etc.)
   */
  private setupFullscreenEnvironment(options: VideoFullscreenOptions): void {
    const { element, autoHideCursor = true } = options;

    // Auto-hide cursor
    if (autoHideCursor) {
      this.setupCursorAutoHide(element);
    }
  }

  /**
   * Setup automatic cursor hiding
   */
  private setupCursorAutoHide(element: HTMLElement): void {
    const showCursor = () => {
      element.style.cursor = 'default';
      if (this.cursorTimer) {
        clearTimeout(this.cursorTimer);
      }
      this.cursorTimer = setTimeout(() => {
        if (this.getCurrentState().isFullscreen) {
          element.style.cursor = 'none';
        }
      }, 3000);
    };

    const hideCursor = () => {
      element.style.cursor = 'none';
    };

    // Show cursor on mouse movement
    element.addEventListener('mousemove', showCursor);
    element.addEventListener('mouseenter', showCursor);
    
    // Hide cursor initially after a delay
    setTimeout(hideCursor, 3000);

    // Store handlers for cleanup
    element.dataset.cursorHandlers = 'true';
  }

  /**
   * Restore original styles and cleanup
   */
  private cleanup(): void {
    if (this.activeOptions) {
      const { element, videoElement } = this.activeOptions;

      // Restore container styles
      if (element.dataset.originalStyles) {
        try {
          const originalStyles = JSON.parse(element.dataset.originalStyles);
          Object.keys(originalStyles).forEach(property => {
            if (originalStyles[property]) {
              (element.style as any)[property] = originalStyles[property];
            } else {
              (element.style as any)[property] = '';
            }
          });
          delete element.dataset.originalStyles;
        } catch (error) {
          console.warn('Failed to restore element styles:', error);
        }
      }

      // Restore video styles
      if (videoElement && videoElement.dataset.originalVideoStyles) {
        try {
          const originalStyles = JSON.parse(videoElement.dataset.originalVideoStyles);
          Object.keys(originalStyles).forEach(property => {
            if (originalStyles[property]) {
              (videoElement.style as any)[property] = originalStyles[property];
            } else {
              (videoElement.style as any)[property] = '';
            }
          });
          delete videoElement.dataset.originalVideoStyles;
        } catch (error) {
          console.warn('Failed to restore video styles:', error);
        }
      }

      // Restore cursor
      element.style.cursor = '';

      // Remove cursor handlers
      if (element.dataset.cursorHandlers) {
        // Handlers are anonymous, so we can't remove them specifically
        // but they'll be garbage collected
        delete element.dataset.cursorHandlers;
      }
    }

    // Clear timers
    if (this.cursorTimer) {
      clearTimeout(this.cursorTimer);
      this.cursorTimer = null;
    }

    // Remove keydown handler
    if (this.keydownHandler) {
      document.removeEventListener('keydown', this.keydownHandler);
      this.keydownHandler = null;
    }

    // Clear active options
    this.activeOptions = null;
  }

  /**
   * Force cleanup (for error scenarios)
   */
  public forceCleanup(): void {
    this.cleanup();
    
    // Try to exit fullscreen if still active
    const state = this.getCurrentState();
    if (state.isFullscreen) {
      fullscreenManager.exitFullscreen().catch(console.warn);
    }
  }

  /**
   * Get performance metrics
   */
  public getPerformanceMetrics() {
    return {
      isSupported: fullscreenManager.isSupported(),
      currentState: this.getCurrentState(),
      hasActiveOptions: !!this.activeOptions,
      capabilities: fullscreenManager.getCapabilities(),
    };
  }
}

// Export singleton instance
export const enhancedFullscreenManager = EnhancedFullscreenManager.getInstance();

// Convenience functions
export const testFullscreenSupport = (): Promise<FullscreenTestResult> => {
  return enhancedFullscreenManager.testFullscreenSupport();
};

export const requestVideoFullscreen = (options: VideoFullscreenOptions): Promise<FullscreenTestResult> => {
  return enhancedFullscreenManager.requestVideoFullscreen(options);
};

export const exitVideoFullscreen = (): Promise<FullscreenTestResult> => {
  return enhancedFullscreenManager.exitVideoFullscreen();
};

export const toggleVideoFullscreen = (options: VideoFullscreenOptions): Promise<FullscreenTestResult> => {
  return enhancedFullscreenManager.toggleVideoFullscreen(options);
};

export default enhancedFullscreenManager;