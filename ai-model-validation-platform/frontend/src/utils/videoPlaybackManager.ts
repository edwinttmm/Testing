/**
 * Enhanced Video Playback Manager
 * Provides robust video playback with retry logic, error recovery, and state management
 */

import { safeVideoPlay, safeVideoPause, safeVideoStop, setVideoSource, cleanupVideoElement } from './videoUtils';

export interface VideoPlaybackState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  buffering: boolean;
  loading: boolean;
  error: VideoPlaybackError | null;
  readyState: number;
}

export interface VideoPlaybackError {
  type: 'network' | 'decode' | 'src_not_supported' | 'aborted' | 'timeout' | 'unknown';
  message: string;
  code?: number;
  recoverable: boolean;
  timestamp: number;
}

export interface VideoPlaybackConfig {
  retryAttempts: number;
  retryDelay: number;
  loadTimeout: number;
  playTimeout: number;
  enableAutoRetry: boolean;
}

export class VideoPlaybackManager {
  private videoElement: HTMLVideoElement | null = null;
  private config: VideoPlaybackConfig;
  private retryCount = 0;
  private loadPromise: Promise<void> | null = null;
  private playPromise: Promise<void> | null = null;
  private timeoutId: NodeJS.Timeout | null = null;
  private stateChangeCallbacks: ((state: VideoPlaybackState) => void)[] = [];

  constructor(config?: Partial<VideoPlaybackConfig>) {
    this.config = {
      retryAttempts: 3,
      retryDelay: 1000,
      loadTimeout: 30000,
      playTimeout: 10000,
      enableAutoRetry: true,
      ...config
    };
  }

  public attachVideoElement(element: HTMLVideoElement): void {
    if (this.videoElement) {
      this.cleanup();
    }
    
    this.videoElement = element;
    this.setupEventListeners();
  }

  public detachVideoElement(): void {
    this.cleanup();
    this.videoElement = null;
  }

  public async loadVideo(url: string): Promise<void> {
    if (!this.videoElement) {
      throw new Error('No video element attached');
    }

    // Cancel any existing load operation
    if (this.loadPromise) {
      this.cancelOperation();
    }

    this.retryCount = 0;
    this.updateState({ loading: true, error: null });

    this.loadPromise = this.attemptLoad(url);
    return this.loadPromise;
  }

  private async attemptLoad(url: string): Promise<void> {
    if (!this.videoElement) {
      throw new Error('Video element not available');
    }

    try {
      // Set timeout for loading
      const timeoutPromise = new Promise<never>((_, reject) => {
        this.timeoutId = setTimeout(() => {
          reject(new Error('Video load timeout'));
        }, this.config.loadTimeout);
      });

      // Attempt to load video
      const loadPromise = setVideoSource(this.videoElement, url);
      
      await Promise.race([loadPromise, timeoutPromise]);
      
      // Clear timeout if successful
      if (this.timeoutId) {
        clearTimeout(this.timeoutId);
        this.timeoutId = null;
      }

      this.updateState({ loading: false, error: null });
      console.log('Video loaded successfully:', url);

    } catch (error) {
      console.error('Video load failed:', error);
      
      const playbackError = this.createPlaybackError(error as Error, 'network');
      
      if (this.config.enableAutoRetry && playbackError.recoverable && this.retryCount < this.config.retryAttempts) {
        this.retryCount++;
        console.log(`Retrying video load (${this.retryCount}/${this.config.retryAttempts})`);
        
        await this.delay(this.config.retryDelay * this.retryCount);
        return this.attemptLoad(url);
      }

      this.updateState({ loading: false, error: playbackError });
      throw error;
    }
  }

  public async play(): Promise<boolean> {
    if (!this.videoElement) {
      console.warn('Cannot play: no video element attached');
      return false;
    }

    if (!this.isVideoReady()) {
      console.warn('Cannot play: video not ready');
      return false;
    }

    try {
      this.updateState({ buffering: true });
      
      const result = await safeVideoPlay(this.videoElement);
      
      if (result.success) {
        this.updateState({ isPlaying: true, buffering: false, error: null });
        return true;
      } else {
        const error = this.createPlaybackError(
          result.error || new Error('Play failed'), 
          'unknown'
        );
        this.updateState({ isPlaying: false, buffering: false, error });
        return false;
      }
    } catch (error) {
      console.error('Video play error:', error);
      const playbackError = this.createPlaybackError(error as Error, 'unknown');
      this.updateState({ isPlaying: false, buffering: false, error: playbackError });
      return false;
    }
  }

  public pause(): void {
    if (!this.videoElement) return;
    
    safeVideoPause(this.videoElement);
    this.updateState({ isPlaying: false });
  }

  public stop(): void {
    if (!this.videoElement) return;
    
    safeVideoStop(this.videoElement);
    this.updateState({ isPlaying: false, currentTime: 0 });
  }

  public seek(time: number): void {
    if (!this.videoElement || !this.isVideoReady()) return;

    try {
      this.updateState({ buffering: true });
      this.videoElement.currentTime = time;
      setTimeout(() => this.updateState({ buffering: false }), 500);
    } catch (error) {
      console.warn('Seek failed:', error);
      this.updateState({ buffering: false });
    }
  }

  public setVolume(volume: number): void {
    if (!this.videoElement) return;

    try {
      this.videoElement.volume = Math.max(0, Math.min(1, volume));
    } catch (error) {
      console.warn('Volume change failed:', error);
    }
  }

  public getCurrentState(): VideoPlaybackState {
    if (!this.videoElement) {
      return {
        isPlaying: false,
        currentTime: 0,
        duration: 0,
        buffering: false,
        loading: false,
        error: null,
        readyState: 0,
      };
    }

    return {
      isPlaying: !this.videoElement.paused,
      currentTime: this.videoElement.currentTime,
      duration: this.videoElement.duration || 0,
      buffering: false, // This would be managed by the state updates
      loading: false,   // This would be managed by the state updates
      error: null,      // This would be managed by the state updates
      readyState: this.videoElement.readyState,
    };
  }

  public isVideoReady(): boolean {
    return !!(
      this.videoElement &&
      this.videoElement.readyState >= HTMLMediaElement.HAVE_METADATA &&
      this.videoElement.duration > 0 &&
      this.videoElement.videoWidth > 0 &&
      this.videoElement.videoHeight > 0
    );
  }

  public onStateChange(callback: (state: VideoPlaybackState) => void): () => void {
    this.stateChangeCallbacks.push(callback);
    
    // Return unsubscribe function
    return () => {
      const index = this.stateChangeCallbacks.indexOf(callback);
      if (index > -1) {
        this.stateChangeCallbacks.splice(index, 1);
      }
    };
  }

  private setupEventListeners(): void {
    if (!this.videoElement) return;

    const events = [
      'loadedmetadata',
      'canplay',
      'canplaythrough', 
      'waiting',
      'playing',
      'pause',
      'ended',
      'error',
      'stalled',
      'suspend',
      'timeupdate',
      'progress'
    ];

    events.forEach(eventName => {
      this.videoElement!.addEventListener(eventName, this.handleVideoEvent);
    });
  }

  private handleVideoEvent = (event: Event): void => {
    if (!this.videoElement) return;

    const eventType = event.type;
    
    switch (eventType) {
      case 'loadedmetadata':
        this.updateState({ loading: false });
        break;
        
      case 'canplay':
      case 'canplaythrough':
        this.updateState({ buffering: false });
        break;
        
      case 'waiting':
      case 'stalled':
        this.updateState({ buffering: true });
        break;
        
      case 'playing':
        this.updateState({ isPlaying: true, buffering: false });
        break;
        
      case 'pause':
      case 'ended':
        this.updateState({ isPlaying: false });
        break;
        
      case 'error':
        const error = this.createPlaybackError(
          new Error(`Video error: ${this.videoElement.error?.message || 'Unknown'}`),
          'decode'
        );
        this.updateState({ error, loading: false, buffering: false, isPlaying: false });
        break;
        
      case 'timeupdate':
        // Throttle time updates to avoid excessive state changes
        if (this.stateChangeCallbacks.length > 0) {
          const state = this.getCurrentState();
          this.stateChangeCallbacks.forEach(callback => callback(state));
        }
        break;
    }
  };

  private updateState(partialState: Partial<VideoPlaybackState>): void {
    if (this.stateChangeCallbacks.length === 0) return;

    const currentState = this.getCurrentState();
    const newState = { ...currentState, ...partialState };
    
    this.stateChangeCallbacks.forEach(callback => callback(newState));
  }

  private createPlaybackError(error: Error, type: VideoPlaybackError['type']): VideoPlaybackError {
    const isRecoverable = type === 'network' || type === 'timeout' || type === 'aborted';
    
    return {
      type,
      message: error.message,
      code: (error as any).code,
      recoverable: isRecoverable,
      timestamp: Date.now(),
    };
  }

  private cancelOperation(): void {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private cleanup(): void {
    this.cancelOperation();
    
    if (this.videoElement) {
      const events = [
        'loadedmetadata', 'canplay', 'canplaythrough', 'waiting',
        'playing', 'pause', 'ended', 'error', 'stalled', 'suspend',
        'timeupdate', 'progress'
      ];

      events.forEach(eventName => {
        this.videoElement!.removeEventListener(eventName, this.handleVideoEvent);
      });

      cleanupVideoElement(this.videoElement);
    }
  }

  public destroy(): void {
    this.cleanup();
    this.stateChangeCallbacks.length = 0;
    this.videoElement = null;
    this.loadPromise = null;
    this.playPromise = null;
  }
}

export default VideoPlaybackManager;