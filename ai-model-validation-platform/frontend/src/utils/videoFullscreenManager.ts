/**
 * Video Fullscreen Manager
 * 
 * Provides robust fullscreen API integration for video elements
 * with proper browser compatibility and error handling
 */

interface FullscreenAPI {
  requestFullscreen: string;
  exitFullscreen: string;
  fullscreenElement: string;
  fullscreenEnabled: string;
  fullscreenchange: string;
  fullscreenerror: string;
}

class VideoFullscreenManager {
  private static instance: VideoFullscreenManager;
  private fullscreenAPI: FullscreenAPI;
  private activeVideo: HTMLVideoElement | null = null;
  private eventListeners: Array<{ element: Element; event: string; handler: EventListener }> = [];

  private constructor() {
    this.fullscreenAPI = this.detectFullscreenAPI();
  }

  static getInstance(): VideoFullscreenManager {
    if (!VideoFullscreenManager.instance) {
      VideoFullscreenManager.instance = new VideoFullscreenManager();
    }
    return VideoFullscreenManager.instance;
  }

  /**
   * Detect browser-specific fullscreen API
   */
  private detectFullscreenAPI(): FullscreenAPI {
    const apis = [
      {
        requestFullscreen: 'requestFullscreen',
        exitFullscreen: 'exitFullscreen',
        fullscreenElement: 'fullscreenElement',
        fullscreenEnabled: 'fullscreenEnabled',
        fullscreenchange: 'fullscreenchange',
        fullscreenerror: 'fullscreenerror'
      },
      {
        requestFullscreen: 'webkitRequestFullscreen',
        exitFullscreen: 'webkitExitFullscreen',
        fullscreenElement: 'webkitFullscreenElement',
        fullscreenEnabled: 'webkitFullscreenEnabled',
        fullscreenchange: 'webkitfullscreenchange',
        fullscreenerror: 'webkitfullscreenerror'
      },
      {
        requestFullscreen: 'mozRequestFullScreen',
        exitFullscreen: 'mozCancelFullScreen',
        fullscreenElement: 'mozFullScreenElement',
        fullscreenEnabled: 'mozFullScreenEnabled',
        fullscreenchange: 'mozfullscreenchange',
        fullscreenerror: 'mozfullscreenerror'
      },
      {
        requestFullscreen: 'msRequestFullscreen',
        exitFullscreen: 'msExitFullscreen',
        fullscreenElement: 'msFullscreenElement',
        fullscreenEnabled: 'msFullscreenEnabled',
        fullscreenchange: 'MSFullscreenChange',
        fullscreenerror: 'MSFullscreenError'
      }
    ];

    // Find the first supported API
    for (const api of apis) {
      if (api.requestFullscreen in document.documentElement) {
        return api;
      }
    }

    // Fallback (should not happen in modern browsers)
    return apis[0];
  }

  /**
   * Check if fullscreen is supported
   */
  isSupported(): boolean {
    return !!(document as any)[this.fullscreenAPI.fullscreenEnabled];
  }

  /**
   * Check if currently in fullscreen mode
   */
  isFullscreen(): boolean {
    return !!(document as any)[this.fullscreenAPI.fullscreenElement];
  }

  /**
   * Request fullscreen for video element
   */
  async requestFullscreen(video: HTMLVideoElement): Promise<void> {
    if (!this.isSupported()) {
      throw new Error('Fullscreen API not supported');
    }

    if (this.isFullscreen()) {
      throw new Error('Already in fullscreen mode');
    }

    try {
      // Create container for video if needed
      const container = this.createFullscreenContainer(video);
      
      const requestMethod = (container as any)[this.fullscreenAPI.requestFullscreen];
      if (!requestMethod) {
        throw new Error('Fullscreen request method not available');
      }

      await requestMethod.call(container);
      this.activeVideo = video;
      
      // Set up event listeners
      this.setupFullscreenEventListeners(video, container);
      
    } catch (error) {
      throw new Error(`Failed to enter fullscreen: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Exit fullscreen mode
   */
  async exitFullscreen(): Promise<void> {
    if (!this.isFullscreen()) {
      return; // Already not in fullscreen
    }

    try {
      const exitMethod = (document as any)[this.fullscreenAPI.exitFullscreen];
      if (!exitMethod) {
        throw new Error('Fullscreen exit method not available');
      }

      await exitMethod.call(document);
      
    } catch (error) {
      throw new Error(`Failed to exit fullscreen: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Toggle fullscreen mode
   */
  async toggleFullscreen(video: HTMLVideoElement): Promise<boolean> {
    if (this.isFullscreen()) {
      await this.exitFullscreen();
      return false;
    } else {
      await this.requestFullscreen(video);
      return true;
    }
  }

  /**
   * Create fullscreen container for video
   */
  private createFullscreenContainer(video: HTMLVideoElement): HTMLElement {
    // Check if video already has a fullscreen container
    const existingContainer = video.parentElement?.closest('[data-video-fullscreen-container]');
    if (existingContainer) {
      return existingContainer as HTMLElement;
    }

    // Create new container
    const container = document.createElement('div');
    container.setAttribute('data-video-fullscreen-container', 'true');
    container.style.cssText = `
      position: relative;
      width: 100%;
      height: 100%;
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
    `;

    // Wrap video in container
    const parent = video.parentElement;
    if (parent) {
      parent.insertBefore(container, video);
      container.appendChild(video);
    }

    return container;
  }

  /**
   * Set up fullscreen event listeners
   */
  private setupFullscreenEventListeners(video: HTMLVideoElement, container: HTMLElement): void {
    const onFullscreenChange = () => {
      if (!this.isFullscreen()) {
        this.handleFullscreenExit(video, container);
      } else {
        this.handleFullscreenEnter(video, container);
      }
    };

    const onFullscreenError = (event: Event) => {
      console.error('Fullscreen error:', event);
      this.handleFullscreenExit(video, container);
    };

    const onKeyDown = (event: Event) => {
      const keyboardEvent = event as KeyboardEvent;
      if (keyboardEvent.key === 'Escape' && this.isFullscreen()) {
        this.exitFullscreen().catch(console.error);
      }
    };

    // Add event listeners
    this.addEventListener(document, this.fullscreenAPI.fullscreenchange, onFullscreenChange);
    this.addEventListener(document, this.fullscreenAPI.fullscreenerror, onFullscreenError);
    this.addEventListener(document, 'keydown', onKeyDown);
  }

  /**
   * Handle fullscreen enter
   */
  private handleFullscreenEnter(video: HTMLVideoElement, container: HTMLElement): void {
    // Style video for fullscreen
    video.style.cssText = `
      width: 100%;
      height: 100%;
      object-fit: contain;
    `;

    container.style.cssText += `
      cursor: none;
    `;

    // Hide cursor after 3 seconds
    let hideTimer: NodeJS.Timeout;
    const showCursor = () => {
      container.style.cursor = 'auto';
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => {
        if (this.isFullscreen()) {
          container.style.cursor = 'none';
        }
      }, 3000);
    };

    this.addEventListener(container, 'mousemove', showCursor);
    showCursor();
  }

  /**
   * Handle fullscreen exit
   */
  private handleFullscreenExit(video: HTMLVideoElement, container: HTMLElement): void {
    // Reset video styles
    video.style.cssText = '';
    container.style.cursor = 'auto';

    // Clean up event listeners
    this.removeAllEventListeners();
    
    this.activeVideo = null;
  }

  /**
   * Add event listener with tracking
   */
  private addEventListener(element: Element | Document, event: string, handler: EventListener): void {
    element.addEventListener(event, handler);
    this.eventListeners.push({ element: element as Element, event, handler });
  }

  /**
   * Remove all tracked event listeners
   */
  private removeAllEventListeners(): void {
    this.eventListeners.forEach(({ element, event, handler }) => {
      try {
        element.removeEventListener(event, handler);
      } catch (error) {
        console.warn('Error removing event listener:', error);
      }
    });
    this.eventListeners = [];
  }

  /**
   * Get fullscreen capabilities
   */
  getCapabilities() {
    return {
      supported: this.isSupported(),
      isFullscreen: this.isFullscreen(),
      activeVideo: this.activeVideo,
      api: this.fullscreenAPI.requestFullscreen
    };
  }

  /**
   * Cleanup all resources
   */
  cleanup(): void {
    if (this.isFullscreen()) {
      this.exitFullscreen().catch(console.error);
    }
    this.removeAllEventListeners();
    this.activeVideo = null;
  }
}

// Export singleton instance
export const videoFullscreenManager = VideoFullscreenManager.getInstance();

// Export convenience functions
export const requestVideoFullscreen = (video: HTMLVideoElement) =>
  videoFullscreenManager.requestFullscreen(video);

export const exitVideoFullscreen = () =>
  videoFullscreenManager.exitFullscreen();

export const toggleVideoFullscreen = (video: HTMLVideoElement) =>
  videoFullscreenManager.toggleFullscreen(video);

export const isFullscreenSupported = () =>
  videoFullscreenManager.isSupported();

export const isVideoFullscreen = () =>
  videoFullscreenManager.isFullscreen();

export default videoFullscreenManager;