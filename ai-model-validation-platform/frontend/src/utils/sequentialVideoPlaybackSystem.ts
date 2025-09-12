/**
 * Sequential Video Playback System - SIMPLE & RELIABLE APPROACH
 * 
 * This system provides bulletproof video playlist management with:
 * - Simple queue-based sequential playback
 * - Independent video lifecycle for each video
 * - Foolproof end detection with backup timers
 * - Clear state management without complex timing
 */

import { VideoFile } from '../services/types';
import { debugSequentialVideoPlayer, debugVideoLoading } from './enhancedModeDebugger';

// Type-safe video playback system with full compatibility

// Legacy compatibility types
export interface VideoQueueItem extends VideoFile {
  // Additional properties that might be expected
  queueIndex?: number;
  preloaded?: boolean;
}

export interface PlaybackConfiguration {
  autoAdvance?: boolean;
  loopPlayback?: boolean;
  randomOrder?: boolean;
  preloadNext?: boolean;
  fullscreenMode?: boolean;
  autoFullscreen?: boolean;
  transitionDelay?: number;
  maxRetries?: number;
  enableHardwareAcceleration?: boolean;
  syncWithExternalSignals?: boolean;
  volume?: number;
  muted?: boolean;
}

export interface PlaybackError {
  videoId: string;
  videoIndex: number;
  errorType: 'load' | 'play' | 'network' | 'decode' | 'transition' | 'fullscreen' | 'unknown';
  message: string;
  timestamp: number;
  recoverable: boolean;
  originalError?: Error;
}

export interface PlaybackState {
  currentIndex: number;
  isPlaying: boolean;
  isTransitioning: boolean;
  isPaused: boolean;
  isFullscreen: boolean;
  isMuted: boolean;
  videos: VideoQueueItem[];
  totalProgress: number;
  videoProgress: number;
  errors: PlaybackError[];
  currentVideo: VideoQueueItem | null;
  statistics: {
    totalPlayTime: number;
    videosCompleted: number;
    errorCount: number;
    sessionStartTime: number;
  };
}

// Simple interface for backward compatibility
export interface VideoState {
  currentIndex: number;
  isPlaying: boolean;
  isTransitioning: boolean;
  videos: VideoFile[];
  totalProgress: number;
  errors: string[];
}

export interface VideoCallbacks {
  onVideoStart?: (video: VideoFile | VideoQueueItem, index: number) => void;
  onVideoEnd?: (video: VideoFile | VideoQueueItem, index: number) => void;
  onVideoError?: (error: string | PlaybackError, video: VideoFile | VideoQueueItem) => void;
  onPlaybackComplete?: () => void;
  onProgressUpdate?: (progress: number, videoIndex: number) => void;
  onStateChange?: (state: VideoState | PlaybackState) => void;
  onFullscreenChange?: (isFullscreen: boolean) => void;
}

export class SequentialVideoPlaybackSystem {
  private container: HTMLElement;
  private videoElement: HTMLVideoElement | null = null;
  private callbacks: VideoCallbacks = {};
  private config: PlaybackConfiguration = {};
  
  private state: VideoState = {
    currentIndex: 0,
    isPlaying: false,
    isTransitioning: false,
    videos: [],
    totalProgress: 0,
    errors: []
  };

  // Simple flags for tracking video end
  private hasVideoEnded = false;
  private endCheckTimer?: NodeJS.Timeout;
  private transitionDelayTimer?: NodeJS.Timeout;

  constructor(
    container: HTMLElement, 
    configOrCallbacks?: PlaybackConfiguration | VideoCallbacks,
    callbacks?: VideoCallbacks
  ) {
    this.container = container;
    
    // Handle different constructor signatures for backward compatibility
    if (configOrCallbacks && typeof configOrCallbacks === 'object') {
      // Check if it's a config object (has config properties) or callbacks (has callback functions)
      const hasConfigProps = 'autoAdvance' in configOrCallbacks || 'loopPlayback' in configOrCallbacks || 'transitionDelay' in configOrCallbacks;
      const hasCallbackProps = 'onVideoStart' in configOrCallbacks || 'onVideoEnd' in configOrCallbacks || 'onPlaybackComplete' in configOrCallbacks;
      
      if (hasConfigProps && !hasCallbackProps) {
        // New signature: (container, config, callbacks)
        this.config = configOrCallbacks as PlaybackConfiguration;
        this.callbacks = callbacks || {};
      } else if (hasCallbackProps) {
        // Old signature: (container, callbacks)
        this.callbacks = configOrCallbacks as VideoCallbacks;
        this.config = {};
      } else {
        // Mixed or unknown - assume callbacks for safety
        this.callbacks = configOrCallbacks as VideoCallbacks;
        this.config = {};
      }
    } else {
      // Fallback to old signature
      this.callbacks = {};
      this.config = {};
    }
    
    console.log('🎬 SequentialVideoPlaybackSystem initialized with SIMPLE approach');
  }

  /**
   * Load video queue - simple array assignment
   */
  public async loadVideoQueue(videos: VideoFile[]): Promise<void> {
    if (videos.length === 0) {
      throw new Error('Video queue cannot be empty');
    }

    console.log(`📥 Loading ${videos.length} videos into queue`);
    this.state.videos = [...videos];
    this.state.currentIndex = 0;
    this.state.totalProgress = 0;
    this.state.errors = [];
    
    this.notifyStateChange();
    console.log('✅ Video queue loaded successfully');
  }

  /**
   * Start playback - load and play first video
   */
  public async startPlayback(userInitiated: boolean = true): Promise<void> {
    console.log('🔍 DEBUG: startPlayback() called with userInitiated:', userInitiated);
    console.log('🔍 DEBUG: Current state.videos.length:', this.state.videos.length);
    
    if (this.state.videos.length === 0) {
      console.log('🔍 DEBUG: No videos in queue, throwing error');
      throw new Error('No videos in queue');
    }

    console.log('🚀 Starting sequential video playback', userInitiated ? '(user initiated)' : '');
    console.log('🔍 DEBUG: About to call playVideoAtIndex(0)');
    
    // Mark user interaction for autoplay policy compliance
    if (userInitiated) {
      const { markUserInteraction } = await import('./videoUtils');
      markUserInteraction();
    }
    
    await this.playVideoAtIndex(0, userInitiated);
  }

  /**
   * Play video at specific index - SIMPLE APPROACH
   */
  private async playVideoAtIndex(index: number, userInitiated: boolean = false): Promise<void> {
    console.log(`🔍 DEBUG: playVideoAtIndex() called with index: ${index}, userInitiated: ${userInitiated}`);
    
    if (index < 0 || index >= this.state.videos.length) {
      console.error(`❌ Invalid video index: ${index}`);
      return;
    }

    const video = this.state.videos[index];
    console.log(`🎥 Playing video ${index + 1}/${this.state.videos.length}: ${video.filename}`);
    console.log(`🔍 DEBUG: Video object:`, video);

    try {
      // Update state
      this.state.currentIndex = index;
      this.state.isTransitioning = false;
      this.hasVideoEnded = false;
      this.clearTimers();

      // Create fresh video element for each video
      console.log('🔍 DEBUG: About to create video element');
      this.createVideoElement();
      
      if (!this.videoElement) {
        console.log('🔍 DEBUG: Failed to create video element');
        throw new Error('Failed to create video element');
      }
      console.log('🔍 DEBUG: Video element created successfully:', this.videoElement);

      // Load video with proper URL handling
      console.log(`📂 Loading video: ${video.filename || video.id}`);
      let videoUrl = video.url;
      
      // If no URL provided, try to generate one using dynamic URL
      if (!videoUrl) {
        if (video.id) {
          const { getDynamicVideoUrl } = await import('./videoUtils');
          videoUrl = getDynamicVideoUrl(video.id);
          console.log(`📂 Generated dynamic video URL: ${videoUrl}`);
        } else if (video.filename) {
          const { generateVideoUrl } = await import('./videoUtils');
          videoUrl = generateVideoUrl(video as any);
          console.log(`📂 Generated video URL: ${videoUrl}`);
        }
      }
      
      if (!videoUrl) {
        throw new Error('No video URL available');
      }
      
      console.log(`📂 Setting video source: ${videoUrl}`);
      console.log('🔍 DEBUG: Video element before setting src:', {
        readyState: this.videoElement.readyState,
        src: this.videoElement.src,
        currentSrc: this.videoElement.currentSrc
      });
      
      // Debug video loading
      debugVideoLoading(video.id || video.filename || 'unknown', videoUrl, true);
      debugSequentialVideoPlayer({
        currentIndex: this.state.currentIndex,
        isPlaying: this.state.isPlaying,
        isTransitioning: this.state.isTransitioning,
        videos: this.state.videos,
        videoElement: this.videoElement
      }, `LoadingVideo_${video.filename || video.id}`);
      
      this.videoElement.src = videoUrl;
      
      // Wait for video to be ready
      console.log('🔍 DEBUG: About to wait for video to be ready');
      await this.waitForVideoReady();
      console.log('🔍 DEBUG: Video is ready, proceeding to safeVideoPlay');
      
      // Start playback using safe video play
      console.log('▶️ Starting video playback');
      console.log('🔍 DEBUG: About to call safeVideoPlay with options:', { userInitiated, retryWithMuted: true });
      const { safeVideoPlay } = await import('./videoUtils');
      const playResult = await safeVideoPlay(this.videoElement, {
        userInitiated,
        retryWithMuted: true
      });
      
      console.log('🔍 DEBUG: safeVideoPlay result:', playResult);
      
      if (!playResult.success) {
        console.log('🔍 DEBUG: Video playback failed, throwing error');
        throw new Error(playResult.error?.message || 'Failed to start video playback');
      }
      console.log('🔍 DEBUG: Video playback succeeded');
      
      this.state.isPlaying = true;
      this.notifyStateChange();
      this.callbacks.onVideoStart?.(video, index);
      
      console.log(`✅ Video ${index + 1} started successfully`);
      
    } catch (error) {
      const errorMessage = `Failed to play video ${index + 1}: ${error instanceof Error ? error.message : 'Unknown error'}`;
      console.error(`❌ ${errorMessage}`);
      this.state.errors.push(errorMessage);
      this.callbacks.onVideoError?.(errorMessage, video);
      
      // Try next video after error
      setTimeout(() => {
        this.playNextVideo();
      }, 2000);
    }
  }

  /**
   * Create fresh video element for each video
   */
  private createVideoElement(): void {
    // Remove existing video element
    if (this.videoElement && this.videoElement.parentNode) {
      this.videoElement.parentNode.removeChild(this.videoElement);
      this.videoElement = null;
    }

    // Create new video element
    this.videoElement = document.createElement('video');
    this.videoElement.setAttribute('controls', 'false');
    this.videoElement.setAttribute('playsInline', 'true');
    this.videoElement.setAttribute('preload', 'metadata');
    this.videoElement.setAttribute('crossorigin', 'anonymous');
    this.videoElement.muted = true;
    this.videoElement.style.width = '100%';
    this.videoElement.style.height = '100%';
    this.videoElement.style.objectFit = 'contain';
    this.videoElement.style.backgroundColor = '#000';
    
    // Add to container
    this.container.appendChild(this.videoElement);
    
    // Setup event listeners
    this.setupVideoEvents();
    
    console.log('🎬 Created fresh video element with proper attributes');
  }

  /**
   * Setup simple event listeners
   */
  private setupVideoEvents(): void {
    if (!this.videoElement) return;

    // Main ended event listener
    this.videoElement.addEventListener('ended', () => {
      console.log(`🏁 Video ended: ${this.getCurrentVideo()?.filename}`);
      this.onVideoEnded();
    });

    // Backup end detection using timeupdate
    this.videoElement.addEventListener('timeupdate', () => {
      if (!this.videoElement) return;
      
      const { currentTime, duration } = this.videoElement;
      
      // Update progress
      const videoProgress = duration > 0 ? (currentTime / duration) * 100 : 0;
      const totalProgress = ((this.state.currentIndex / this.state.videos.length) * 100) + 
                           (videoProgress / this.state.videos.length);
      this.state.totalProgress = Math.min(100, totalProgress);
      this.callbacks.onProgressUpdate?.(this.state.totalProgress, this.state.currentIndex);
      
      // Backup end detection - if within 0.5 seconds of end
      if (duration > 0 && currentTime >= duration - 0.5 && !this.hasVideoEnded) {
        console.log(`🏁 Video end detected via timeupdate: ${currentTime}/${duration}`);
        this.onVideoEnded();
      }
    });

    // Error handling
    this.videoElement.addEventListener('error', (event) => {
      const video = this.getCurrentVideo();
      const errorMessage = `Video playback error: ${this.videoElement?.error?.message || 'Unknown error'}`;
      console.error(`❌ ${errorMessage}`);
      this.callbacks.onVideoError?.(errorMessage, video!);
    });

    console.log('🔗 Video event listeners setup complete');
  }

  /**
   * Handle video end - SIMPLE AND RELIABLE
   */
  private onVideoEnded(): void {
    if (this.hasVideoEnded) {
      console.log('⚠️ Video end already handled, ignoring duplicate');
      return;
    }

    this.hasVideoEnded = true;
    this.state.isPlaying = false;
    
    const currentVideo = this.getCurrentVideo();
    if (currentVideo) {
      console.log(`✅ Video completed: ${currentVideo.filename}`);
      this.callbacks.onVideoEnd?.(currentVideo, this.state.currentIndex);
    }

    // Wait 2 seconds then advance to next video
    console.log('⏱️ Waiting 2 seconds before next video...');
    this.transitionDelayTimer = setTimeout(() => {
      this.playNextVideo();
    }, 2000);
  }

  /**
   * Play next video in sequence
   */
  private playNextVideo(): void {
    const nextIndex = this.state.currentIndex + 1;
    
    console.log(`🔄 playNextVideo() - current: ${this.state.currentIndex}, next: ${nextIndex}, total: ${this.state.videos.length}`);
    
    if (nextIndex >= this.state.videos.length) {
      // All videos completed
      console.log('🎉 All videos completed!');
      this.state.isPlaying = false;
      this.state.totalProgress = 100;
      this.notifyStateChange();
      this.callbacks.onPlaybackComplete?.();
      return;
    }

    // Play next video
    this.state.isTransitioning = true;
    this.notifyStateChange();
    
    console.log(`➡️ Advancing to video ${nextIndex + 1}/${this.state.videos.length}`);
    this.playVideoAtIndex(nextIndex, false); // Auto-advance, not user-initiated
  }

  /**
   * Wait for video to be ready for playback
   */
  private waitForVideoReady(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.videoElement) {
        reject(new Error('No video element'));
        return;
      }

      const timeout = setTimeout(() => {
        cleanup();
        reject(new Error('Video load timeout after 15 seconds'));
      }, 15000); // 15 second timeout

      let resolved = false;
      
      const cleanup = () => {
        if (this.videoElement) {
          this.videoElement.removeEventListener('canplay', handleCanPlay);
          this.videoElement.removeEventListener('canplaythrough', handleCanPlayThrough);
          this.videoElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
          this.videoElement.removeEventListener('error', handleError);
        }
        clearTimeout(timeout);
      };

      const handleSuccess = (event: string) => {
        if (resolved) return;
        resolved = true;
        cleanup();
        console.log(`✅ Video ready for playback via ${event} (readyState: ${this.videoElement?.readyState})`);
        resolve();
      };

      const handleCanPlay = () => handleSuccess('canplay');
      const handleCanPlayThrough = () => handleSuccess('canplaythrough');
      const handleLoadedMetadata = () => handleSuccess('loadedmetadata');
      
      const handleError = (event: Event) => {
        if (resolved) return;
        resolved = true;
        cleanup();
        const errorMsg = this.videoElement?.error?.message || 'Unknown video error';
        console.error(`❌ Video load error: ${errorMsg}`);
        reject(new Error(`Video load error: ${errorMsg}`));
      };

      // Check if already ready
      if (this.videoElement.readyState >= HTMLMediaElement.HAVE_METADATA) {
        handleSuccess('already-loaded');
        return;
      }

      // Add event listeners
      this.videoElement.addEventListener('canplay', handleCanPlay, { once: true });
      this.videoElement.addEventListener('canplaythrough', handleCanPlayThrough, { once: true });
      this.videoElement.addEventListener('loadedmetadata', handleLoadedMetadata, { once: true });
      this.videoElement.addEventListener('error', handleError, { once: true });
      
      // Start loading
      this.videoElement.load();
      console.log('⏳ Waiting for video to load...');
    });
  }

  /**
   * Get current video
   */
  public getCurrentVideo(): VideoFile | null {
    return this.state.videos[this.state.currentIndex] || null;
  }

  /**
   * Get current video as VideoQueueItem for compatibility
   */
  public getCurrentVideoQueueItem(): VideoQueueItem | null {
    const video = this.getCurrentVideo();
    return video ? {
      ...video,
      queueIndex: this.state.currentIndex,
      preloaded: false,
    } : null;
  }

  /**
   * Compatibility properties for external access
   */
  public get playbackManager() {
    return {
      getCurrentVideo: () => this.getCurrentVideo(),
      getState: () => this.getState(),
      pause: () => this.pause(),
      resume: () => this.resume(),
      stop: () => this.stop(),
      next: () => this.next(),
      previous: () => this.previous(),
    };
  }

  public get isMutedForAutoplay(): boolean {
    return this.videoElement?.muted || false;
  }


  /**
   * Enable unmuted playback after user interaction
   */
  public async enableUnmutedPlayback(): Promise<boolean> {
    try {
      if (this.videoElement && this.videoElement.muted) {
        this.videoElement.muted = false;
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to enable unmuted playback:', error);
      return false;
    }
  }

  /**
   * Get current state
   */
  public getState(): VideoState {
    return { ...this.state };
  }

  /**
   * Get current state as PlaybackState for compatibility
   */
  public getPlaybackState(): PlaybackState {
    const currentVideo = this.getCurrentVideo();
    return {
      currentIndex: this.state.currentIndex,
      isPlaying: this.state.isPlaying,
      isTransitioning: this.state.isTransitioning,
      isPaused: !this.state.isPlaying,
      isFullscreen: document.fullscreenElement === this.container,
      isMuted: this.videoElement?.muted || false,
      videos: this.state.videos.map((video, index) => ({
        ...video,
        queueIndex: index,
        preloaded: false,
      })),
      totalProgress: this.state.totalProgress,
      videoProgress: this.videoElement?.currentTime || 0,
      errors: this.state.errors.map((error, index) => ({
        videoId: currentVideo?.id || '',
        videoIndex: this.state.currentIndex,
        errorType: 'unknown' as const,
        message: error,
        timestamp: Date.now(),
        recoverable: true,
      })),
      currentVideo: currentVideo ? { ...currentVideo, queueIndex: this.state.currentIndex } : null,
      statistics: {
        totalPlayTime: 0,
        videosCompleted: this.state.currentIndex,
        errorCount: this.state.errors.length,
        sessionStartTime: Date.now(),
      },
    };
  }

  /**
   * Get statistics for compatibility
   */
  public getStatistics() {
    return {
      totalVideos: this.state.videos.length,
      currentIndex: this.state.currentIndex,
      totalProgress: this.state.totalProgress,
      errors: this.state.errors.length,
      isPlaying: this.state.isPlaying,
      isTransitioning: this.state.isTransitioning,
      videosCompleted: this.state.currentIndex,
      sessionStartTime: Date.now(),
    };
  }

  /**
   * Update configuration
   */
  public updateConfig(newConfig: Partial<PlaybackConfiguration>): void {
    this.config = { ...this.config, ...newConfig };
    console.log('📝 Configuration updated:', newConfig);
  }

  /**
   * Pause playback
   */
  public pause(): void {
    if (this.videoElement) {
      this.videoElement.pause();
      this.state.isPlaying = false;
      this.notifyStateChange();
    }
  }

  /**
   * Pause playback (alias for compatibility)
   */
  public pausePlayback(): void {
    this.pause();
  }

  /**
   * Resume playback
   */
  public async resume(): Promise<void> {
    if (this.videoElement) {
      try {
        await this.videoElement.play();
        this.state.isPlaying = true;
        this.notifyStateChange();
      } catch (error) {
        console.error('Failed to resume playback:', error);
        throw error;
      }
    }
  }

  /**
   * Resume playback (alias for compatibility)
   */
  public async resumePlayback(): Promise<void> {
    return this.resume();
  }

  /**
   * Jump to next video
   */
  public next(): void {
    const nextIndex = this.state.currentIndex + 1;
    if (nextIndex < this.state.videos.length) {
      this.playVideoAtIndex(nextIndex);
    }
  }

  /**
   * Advance to next video (alias for compatibility)
   */
  public async advanceToNext(): Promise<void> {
    this.next();
  }

  /**
   * Jump to previous video
   */
  public previous(): void {
    const prevIndex = this.state.currentIndex - 1;
    if (prevIndex >= 0) {
      this.playVideoAtIndex(prevIndex);
    }
  }

  /**
   * Go to previous video (alias for compatibility)
   */
  public async goToPrevious(): Promise<void> {
    this.previous();
  }

  /**
   * Jump to specific video by index
   */
  public jumpTo(index: number): void {
    if (index >= 0 && index < this.state.videos.length) {
      this.playVideoAtIndex(index, true); // User-initiated jump
    }
  }

  /**
   * Jump to video (alias for compatibility)
   */
  public async jumpToVideo(index: number): Promise<void> {
    this.jumpTo(index);
  }

  /**
   * Stop playback
   */
  public stop(): void {
    this.clearTimers();
    
    if (this.videoElement) {
      this.videoElement.pause();
      this.videoElement.currentTime = 0;
    }
    
    this.state.isPlaying = false;
    this.state.isTransitioning = false;
    this.notifyStateChange();
  }

  /**
   * Stop playback (alias for compatibility)
   */
  public async stopPlayback(): Promise<void> {
    this.stop();
  }


  /**
   * Enter fullscreen
   */
  public async enterFullscreen(): Promise<void> {
    if (!this.container) {
      throw new Error('No container element for fullscreen');
    }

    try {
      if (this.container.requestFullscreen) {
        await this.container.requestFullscreen();
      } else if ('webkitRequestFullscreen' in this.container) {
        await (this.container as any).webkitRequestFullscreen();
      } else {
        throw new Error('Fullscreen API not supported');
      }
    } catch (error) {
      console.error('Failed to enter fullscreen:', error);
      throw error;
    }
  }

  /**
   * Exit fullscreen
   */
  public async exitFullscreen(): Promise<void> {
    try {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if ('webkitExitFullscreen' in document) {
        await (document as any).webkitExitFullscreen();
      }
    } catch (error) {
      console.error('Failed to exit fullscreen:', error);
    }
  }

  /**
   * Notify state change
   */
  private notifyStateChange(): void {
    this.callbacks.onStateChange?.(this.state);
  }

  /**
   * Clear all timers
   */
  private clearTimers(): void {
    if (this.endCheckTimer) {
      clearTimeout(this.endCheckTimer);
      this.endCheckTimer = undefined;
    }
    
    if (this.transitionDelayTimer) {
      clearTimeout(this.transitionDelayTimer);
      this.transitionDelayTimer = undefined;
    }
  }

  /**
   * Destroy and cleanup
   */
  public destroy(): void {
    console.log('🧹 Destroying SequentialVideoPlaybackSystem');
    
    this.clearTimers();
    
    if (this.videoElement && this.container) {
      this.container.removeChild(this.videoElement);
      this.videoElement = null;
    }
    
    this.state = {
      currentIndex: 0,
      isPlaying: false,
      isTransitioning: false,
      videos: [],
      totalProgress: 0,
      errors: []
    };
  }
}

export default SequentialVideoPlaybackSystem;