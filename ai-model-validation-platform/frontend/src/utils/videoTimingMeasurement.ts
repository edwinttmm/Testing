/**
 * Video Timing Measurement Utility
 * 
 * Measures actual video start time vs command time to calculate
 * precise video presentation delays for HIL testing accuracy.
 * 
 * Usage:
 * const measurement = new VideoTimingMeasurement(sessionId);
 * measurement.attachToVideo(videoElement);
 * 
 * This will automatically measure and report video presentation timing.
 */

export interface VideoTimingData {
  client_timestamp: number;
  video_element_ready: boolean;
  video_duration: number;
  video_metadata: {
    readyState: number;
    networkState: number;
    currentSrc: string;
    videoWidth: number;
    videoHeight: number;
  };
}

export class VideoTimingMeasurement {
  private sessionId: string;
  private commandTimestamp: number;
  private measurementSent: boolean = false;
  
  constructor(sessionId: string) {
    this.sessionId = sessionId;
    this.commandTimestamp = Date.now() / 1000; // Record command timestamp
  }
  
  /**
   * Attach timing measurement to a video element
   */
  attachToVideo(videoElement: HTMLVideoElement): void {
    console.log('🎬 VideoTimingMeasurement: Attaching to video element');
    
    // Measure multiple video readiness events to get the most accurate timing
    const events = ['loadeddata', 'canplay', 'canplaythrough', 'playing'] as const;
    
    events.forEach(eventName => {
      videoElement.addEventListener(eventName, () => {
        this.measureVideoStart(videoElement, eventName);
      }, { once: true });
    });
    
    // Fallback timeout measurement
    setTimeout(() => {
      if (!this.measurementSent && videoElement.readyState >= 2) {
        console.log('⏰ VideoTimingMeasurement: Fallback timeout measurement');
        this.measureVideoStart(videoElement, 'timeout_fallback');
      }
    }, 1000);
  }
  
  /**
   * Measure and record the actual video start timing
   */
  private measureVideoStart(videoElement: HTMLVideoElement, triggerEvent: string): void {
    if (this.measurementSent) {
      return; // Only measure once per session
    }
    
    const actualStartTimestamp = Date.now() / 1000; // High precision timestamp
    const presentationDelay = actualStartTimestamp - this.commandTimestamp;
    
    console.log(`🎯 VideoTimingMeasurement: Video started (${triggerEvent})`);
    console.log(`   Command time: ${this.commandTimestamp.toFixed(3)}s`);
    console.log(`   Actual start: ${actualStartTimestamp.toFixed(3)}s`);
    console.log(`   Presentation delay: ${(presentationDelay * 1000).toFixed(1)}ms`);
    
    const timingData: VideoTimingData = {
      client_timestamp: actualStartTimestamp,
      video_element_ready: videoElement.readyState >= 2,
      video_duration: videoElement.duration || 0,
      video_metadata: {
        readyState: videoElement.readyState,
        networkState: videoElement.networkState,
        currentSrc: videoElement.currentSrc,
        videoWidth: videoElement.videoWidth,
        videoHeight: videoElement.videoHeight
      }
    };
    
    // Send to backend
    this.sendTimingToBackend(timingData, triggerEvent);
    this.measurementSent = true;
  }
  
  /**
   * Send timing measurement to backend API
   */
  private async sendTimingToBackend(timingData: VideoTimingData, triggerEvent: string): Promise<void> {
    try {
      const response = await fetch(`/api/video-timing/session/${this.sessionId}/video-started`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...timingData,
          trigger_event: triggerEvent,
          measurement_source: 'frontend_video_timing_utility'
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('✅ VideoTimingMeasurement: Sent to backend', result);
        
        // Dispatch custom event for other components to listen to
        window.dispatchEvent(new CustomEvent('video-timing-measured', {
          detail: {
            sessionId: this.sessionId,
            presentationDelay: result.presentation_delay_ms,
            timingData: result
          }
        }));
      } else {
        console.error('❌ VideoTimingMeasurement: Failed to send timing', response.status);
      }
    } catch (error) {
      console.error('❌ VideoTimingMeasurement: Network error', error);
    }
  }
  
  /**
   * Create and attach measurement to video element (convenience method)
   */
  static measureVideoTiming(sessionId: string, videoElement: HTMLVideoElement): VideoTimingMeasurement {
    const measurement = new VideoTimingMeasurement(sessionId);
    measurement.attachToVideo(videoElement);
    return measurement;
  }
}

/**
 * React Hook for video timing measurement
 */
export const useVideoTimingMeasurement = (sessionId: string | null) => {
  const measureVideo = (videoElement: HTMLVideoElement) => {
    if (!sessionId) {
      console.warn('VideoTimingMeasurement: No session ID provided');
      return null;
    }
    
    return VideoTimingMeasurement.measureVideoTiming(sessionId, videoElement);
  };
  
  return { measureVideo };
};