/**
 * Fullscreen Utilities
 * 
 * Cross-browser fullscreen API with comprehensive compatibility
 * and enhanced video fullscreen support
 */

export interface FullscreenCapabilities {
  supported: boolean;
  prefixes: string[];
  events: string[];
  exitMethods: string[];
  requestMethods: string[];
}

export interface FullscreenState {
  isFullscreen: boolean;
  element: Element | null;
  error: string | null;
}

export class FullscreenManager {
  private static instance: FullscreenManager | null = null;
  private capabilities: FullscreenCapabilities;
  private changeHandlers: ((state: FullscreenState) => void)[] = [];
  private errorHandlers: ((error: string) => void)[] = [];

  constructor() {
    this.capabilities = this.detectCapabilities();
    this.setupEventListeners();
  }

  public static getInstance(): FullscreenManager {
    if (!FullscreenManager.instance) {
      FullscreenManager.instance = new FullscreenManager();
    }
    return FullscreenManager.instance;
  }

  /**
   * Detect browser fullscreen capabilities
   */
  private detectCapabilities(): FullscreenCapabilities {
    const doc = document as any;
    const element = document.documentElement as any;

    const requestMethods = [
      'requestFullscreen',
      'webkitRequestFullscreen',
      'webkitRequestFullScreen',
      'mozRequestFullScreen',
      'msRequestFullscreen'
    ];

    const exitMethods = [
      'exitFullscreen',
      'webkitExitFullscreen',
      'webkitCancelFullScreen',
      'mozCancelFullScreen',
      'msExitFullscreen'
    ];

    const events = [
      'fullscreenchange',
      'webkitfullscreenchange',
      'mozfullscreenchange',
      'MSFullscreenChange'
    ];

    const errorEvents = [
      'fullscreenerror',
      'webkitfullscreenerror',
      'mozfullscreenerror',
      'MSFullscreenError'
    ];

    const prefixes = ['', 'webkit', 'moz', 'ms'];

    // Check if any fullscreen method is supported
    const supported = requestMethods.some(method => typeof element[method] === 'function') &&
                     exitMethods.some(method => typeof doc[method] === 'function');

    return {
      supported,
      prefixes,
      events: [...events, ...errorEvents],
      exitMethods,
      requestMethods,
    };
  }

  /**
   * Setup cross-browser event listeners
   */
  private setupEventListeners(): void {
    // Fullscreen change events
    const changeEvents = [
      'fullscreenchange',
      'webkitfullscreenchange',
      'mozfullscreenchange',
      'MSFullscreenChange'
    ];

    changeEvents.forEach(event => {
      document.addEventListener(event, this.handleFullscreenChange.bind(this));
    });

    // Fullscreen error events
    const errorEvents = [
      'fullscreenerror',
      'webkitfullscreenerror',
      'mozfullscreenerror',
      'MSFullscreenError'
    ];

    errorEvents.forEach(event => {
      document.addEventListener(event, this.handleFullscreenError.bind(this));
    });
  }

  /**
   * Handle fullscreen change events
   */
  private handleFullscreenChange(): void {
    const state = this.getCurrentState();
    this.changeHandlers.forEach(handler => handler(state));
  }

  /**
   * Handle fullscreen error events
   */
  private handleFullscreenError(event: Event): void {
    const error = `Fullscreen error: ${event.type}`;
    this.errorHandlers.forEach(handler => handler(error));
  }

  /**
   * Get current fullscreen state
   */
  public getCurrentState(): FullscreenState {
    const doc = document as any;
    
    const fullscreenElement = 
      doc.fullscreenElement ||
      doc.webkitFullscreenElement ||
      doc.mozFullScreenElement ||
      doc.msFullscreenElement;

    return {
      isFullscreen: !!fullscreenElement,
      element: fullscreenElement || null,
      error: null,
    };
  }

  /**
   * Check if fullscreen is supported
   */
  public isSupported(): boolean {
    return this.capabilities.supported;
  }

  /**
   * Request fullscreen for an element
   */
  public async requestFullscreen(element: Element): Promise<void> {
    if (!this.capabilities.supported) {
      throw new Error('Fullscreen API not supported');
    }

    const el = element as any;
    
    // Try different fullscreen request methods
    const methods = this.capabilities.requestMethods;
    
    for (const method of methods) {
      if (typeof el[method] === 'function') {
        try {
          const result = el[method]();
          
          // Handle promise-based implementations
          if (result && typeof result.then === 'function') {
            await result;
          }
          
          return;
        } catch (error) {
          console.warn(`Fullscreen method ${method} failed:`, error);
          continue;
        }
      }
    }

    throw new Error('No working fullscreen method found');
  }

  /**
   * Exit fullscreen
   */
  public async exitFullscreen(): Promise<void> {
    if (!this.capabilities.supported) {
      throw new Error('Fullscreen API not supported');
    }

    const doc = document as any;
    const methods = this.capabilities.exitMethods;

    for (const method of methods) {
      if (typeof doc[method] === 'function') {
        try {
          const result = doc[method]();
          
          // Handle promise-based implementations
          if (result && typeof result.then === 'function') {
            await result;
          }
          
          return;
        } catch (error) {
          console.warn(`Exit fullscreen method ${method} failed:`, error);
          continue;
        }
      }
    }

    throw new Error('No working exit fullscreen method found');
  }

  /**
   * Toggle fullscreen for an element
   */
  public async toggleFullscreen(element: Element): Promise<void> {
    const state = this.getCurrentState();
    
    if (state.isFullscreen) {
      await this.exitFullscreen();
    } else {
      await this.requestFullscreen(element);
    }
  }

  /**
   * Request fullscreen with video optimization
   */
  public async requestVideoFullscreen(
    videoElement: HTMLVideoElement,
    containerElement?: Element
  ): Promise<void> {
    // For video elements, we might want to use the container for better layout control
    const targetElement = containerElement || videoElement;
    
    try {
      // Apply video-specific optimizations before going fullscreen
      this.optimizeVideoForFullscreen(videoElement);
      
      await this.requestFullscreen(targetElement);
      
      // Post-fullscreen video optimizations
      this.applyFullscreenVideoStyles(videoElement, targetElement);
      
    } catch (error) {
      throw new Error(`Failed to enter video fullscreen: ${error}`);
    }
  }

  /**
   * Optimize video element for fullscreen playback
   */
  private optimizeVideoForFullscreen(videoElement: HTMLVideoElement): void {
    // Store original styles
    const originalStyles = {
      width: videoElement.style.width,
      height: videoElement.style.height,
      objectFit: videoElement.style.objectFit,
      backgroundColor: videoElement.style.backgroundColor,
    };

    videoElement.dataset.originalStyles = JSON.stringify(originalStyles);

    // Apply fullscreen optimizations
    videoElement.style.width = '100vw';
    videoElement.style.height = '100vh';
    videoElement.style.objectFit = 'contain';
    videoElement.style.backgroundColor = '#000';
  }

  /**
   * Apply styles when video is in fullscreen mode
   */
  private applyFullscreenVideoStyles(
    videoElement: HTMLVideoElement,
    containerElement: Element
  ): void {
    const container = containerElement as HTMLElement;
    
    // Ensure container fills the screen
    container.style.width = '100vw';
    container.style.height = '100vh';
    container.style.position = 'fixed';
    container.style.top = '0';
    container.style.left = '0';
    container.style.zIndex = '9999';
    container.style.backgroundColor = '#000';
    container.style.display = 'flex';
    container.style.alignItems = 'center';
    container.style.justifyContent = 'center';

    // Center the video
    videoElement.style.maxWidth = '100%';
    videoElement.style.maxHeight = '100%';
    videoElement.style.width = 'auto';
    videoElement.style.height = 'auto';
  }

  /**
   * Restore video styles when exiting fullscreen
   */
  public restoreVideoStyles(videoElement: HTMLVideoElement): void {
    const originalStylesData = videoElement.dataset.originalStyles;
    
    if (originalStylesData) {
      try {
        const originalStyles = JSON.parse(originalStylesData);
        
        Object.keys(originalStyles).forEach(property => {
          (videoElement.style as any)[property] = originalStyles[property];
        });
        
        delete videoElement.dataset.originalStyles;
      } catch (error) {
        console.warn('Failed to restore original video styles:', error);
      }
    }
  }

  /**
   * Add fullscreen change listener
   */
  public onFullscreenChange(handler: (state: FullscreenState) => void): () => void {
    this.changeHandlers.push(handler);
    
    // Return unsubscribe function
    return () => {
      const index = this.changeHandlers.indexOf(handler);
      if (index > -1) {
        this.changeHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Add fullscreen error listener
   */
  public onFullscreenError(handler: (error: string) => void): () => void {
    this.errorHandlers.push(handler);
    
    // Return unsubscribe function
    return () => {
      const index = this.errorHandlers.indexOf(handler);
      if (index > -1) {
        this.errorHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Get fullscreen capabilities information
   */
  public getCapabilities(): FullscreenCapabilities {
    return { ...this.capabilities };
  }

  /**
   * Cleanup event listeners
   */
  public destroy(): void {
    const allEvents = [
      'fullscreenchange',
      'webkitfullscreenchange',
      'mozfullscreenchange',
      'MSFullscreenChange',
      'fullscreenerror',
      'webkitfullscreenerror',
      'mozfullscreenerror',
      'MSFullscreenError'
    ];

    allEvents.forEach(event => {
      document.removeEventListener(event, this.handleFullscreenChange.bind(this));
      document.removeEventListener(event, this.handleFullscreenError.bind(this));
    });

    this.changeHandlers.length = 0;
    this.errorHandlers.length = 0;
  }
}

// Singleton instance
export const fullscreenManager = FullscreenManager.getInstance();

// Convenience functions
export const isFullscreenSupported = (): boolean => {
  return fullscreenManager.isSupported();
};

export const getCurrentFullscreenState = (): FullscreenState => {
  return fullscreenManager.getCurrentState();
};

export const requestFullscreen = async (element: Element): Promise<void> => {
  return fullscreenManager.requestFullscreen(element);
};

export const exitFullscreen = async (): Promise<void> => {
  return fullscreenManager.exitFullscreen();
};

export const toggleFullscreen = async (element: Element): Promise<void> => {
  return fullscreenManager.toggleFullscreen(element);
};

export const requestVideoFullscreen = async (
  videoElement: HTMLVideoElement,
  containerElement?: Element
): Promise<void> => {
  return fullscreenManager.requestVideoFullscreen(videoElement, containerElement);
};

export const onFullscreenChange = (handler: (state: FullscreenState) => void): (() => void) => {
  return fullscreenManager.onFullscreenChange(handler);
};

export const onFullscreenError = (handler: (error: string) => void): (() => void) => {
  return fullscreenManager.onFullscreenError(handler);
};

export default fullscreenManager;