/**
 * Video Utility Functions
 * Provides safe video operations with proper error handling
 * and DOM cleanup to prevent play() interruption errors
 */

export interface VideoPlayPromiseResult {
  success: boolean;
  error?: Error;
}

/**
 * Safely play a video element with proper error handling
 * @param videoElement - The HTML video element
 * @returns Promise with success status and potential error
 */
export async function safeVideoPlay(videoElement: HTMLVideoElement | null): Promise<VideoPlayPromiseResult> {
  if (!videoElement) {
    return { success: false, error: new Error('Video element not available') };
  }

  try {
    // Check if video is already playing
    if (!videoElement.paused) {
      return { success: true };
    }

    const playPromise = videoElement.play();
    
    // Handle browsers that return a promise from play()
    if (playPromise !== undefined) {
      await playPromise;
    }
    
    return { success: true };
  } catch (error) {
    // Common play() errors:
    // - NotAllowedError: User hasn't interacted with page yet
    // - AbortError: Play was interrupted by another play() call
    // - NotSupportedError: Video format not supported
    console.warn('Video play failed:', error);
    return { success: false, error: error as Error };
  }
}

/**
 * Safely pause a video element
 * @param videoElement - The HTML video element
 */
export function safeVideoPause(videoElement: HTMLVideoElement | null): void {
  if (!videoElement || videoElement.paused) {
    return;
  }

  try {
    videoElement.pause();
  } catch (error) {
    console.warn('Video pause failed:', error);
  }
}

/**
 * Safely stop a video element (pause and reset to beginning)
 * @param videoElement - The HTML video element
 */
export function safeVideoStop(videoElement: HTMLVideoElement | null): void {
  if (!videoElement) {
    return;
  }

  try {
    if (!videoElement.paused) {
      videoElement.pause();
    }
    videoElement.currentTime = 0;
  } catch (error) {
    console.warn('Video stop failed:', error);
  }
}

/**
 * Clean up video element before component unmount
 * This prevents "play() interrupted" errors by properly stopping
 * playback and removing event listeners
 * @param videoElement - The HTML video element
 */
export function cleanupVideoElement(videoElement: HTMLVideoElement | null): void {
  if (!videoElement) {
    return;
  }

  try {
    // Stop any ongoing playback
    if (!videoElement.paused) {
      videoElement.pause();
    }

    // Reset video position
    videoElement.currentTime = 0;

    // Clear source to prevent further loading
    videoElement.removeAttribute('src');
    videoElement.src = '';
    
    // Trigger load to clear any buffered data
    videoElement.load();
  } catch (error) {
    console.warn('Video cleanup failed:', error);
  }
}

/**
 * Set video source with proper error handling
 * @param videoElement - The HTML video element
 * @param src - Video source URL
 * @returns Promise that resolves when video metadata is loaded
 */
export function setVideoSource(videoElement: HTMLVideoElement | null, src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!videoElement) {
      reject(new Error('Video element not available'));
      return;
    }

    const handleLoaded = () => {
      cleanup();
      resolve();
    };

    const handleError = (event: Event) => {
      cleanup();
      reject(new Error('Failed to load video'));
    };

    const cleanup = () => {
      videoElement.removeEventListener('loadedmetadata', handleLoaded);
      videoElement.removeEventListener('error', handleError);
    };

    videoElement.addEventListener('loadedmetadata', handleLoaded);
    videoElement.addEventListener('error', handleError);

    // Set source and trigger load
    videoElement.src = src;
    videoElement.load();
  });
}

/**
 * Check if video element is ready for playback
 * @param videoElement - The HTML video element
 * @returns Boolean indicating if video is ready
 */
export function isVideoReady(videoElement: HTMLVideoElement | null): boolean {
  return !!(
    videoElement &&
    videoElement.readyState >= HTMLMediaElement.HAVE_METADATA &&
    videoElement.duration > 0 &&
    videoElement.videoWidth > 0 &&
    videoElement.videoHeight > 0
  );
}

/**
 * Get video element error message
 * @param videoElement - The HTML video element
 * @returns Human-readable error message
 */
export function getVideoErrorMessage(videoElement: HTMLVideoElement | null): string {
  if (!videoElement || !videoElement.error) {
    return 'Unknown video error';
  }

  const error = videoElement.error;
  
  switch (error.code) {
    case MediaError.MEDIA_ERR_ABORTED:
      return 'Video playback was aborted';
    case MediaError.MEDIA_ERR_NETWORK:
      return 'Network error occurred while loading video';
    case MediaError.MEDIA_ERR_DECODE:
      return 'Video format is not supported or corrupted';
    case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
      return 'Video source is not supported';
    default:
      return `Video error: ${error.message || 'Unknown error'}`;
  }
}

/**
 * Create a video element cleanup hook for React components
 * @param videoRef - React ref to video element
 * @returns Cleanup function
 */
export function createVideoCleanupHook(videoRef: React.RefObject<HTMLVideoElement>) {
  return () => {
    cleanupVideoElement(videoRef.current);
  };
}

/**
 * Video event listener helper with automatic cleanup
 * @param videoElement - The HTML video element
 * @param event - Event name
 * @param handler - Event handler function
 * @returns Cleanup function
 */
export function addVideoEventListener(
  videoElement: HTMLVideoElement | null,
  event: string,
  handler: EventListener
): () => void {
  if (!videoElement) {
    return () => {};
  }

  videoElement.addEventListener(event, handler);
  
  return () => {
    videoElement.removeEventListener(event, handler);
  };
}

/**
 * Batch add video event listeners with cleanup
 * @param videoElement - The HTML video element  
 * @param listeners - Array of event listener configurations
 * @returns Cleanup function for all listeners
 */
export function addVideoEventListeners(
  videoElement: HTMLVideoElement | null,
  listeners: Array<{ event: string; handler: EventListener }>
): () => void {
  if (!videoElement) {
    return () => {};
  }

  const cleanupFunctions = listeners.map(({ event, handler }) => 
    addVideoEventListener(videoElement, event, handler)
  );

  return () => {
    cleanupFunctions.forEach(cleanup => cleanup());
  };
}