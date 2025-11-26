/**
 * Example usage of TimingService and DriftMonitor
 */

import { TimingService } from '../services/timingService';
import type { TimingServiceConfig } from '../types/timing.types';

// Configuration
const config: TimingServiceConfig = {
  syncInterval: 30000, // Sync every 30 seconds
  maxRTT: 200, // Reject syncs with RTT > 200ms
  syncSamples: 5, // Average last 5 samples
  wsEndpoint: 'ws://localhost:3000/timing',
};

// Initialize timing service
const timingService = new TimingService(config);

async function initializeVideoTiming() {
  try {
    // Initialize the service
    await timingService.initialize();
    console.log('Timing service initialized');

    // Register video elements
    const videos = document.querySelectorAll('video');
    videos.forEach((video, index) => {
      const videoId = `video-${index}`;
      video.id = videoId;
      timingService.registerVideo(videoId, video);
      console.log(`Registered video: ${videoId}`);
    });

    // Monitor clock sync status
    setInterval(() => {
      const syncStatus = timingService.getClockSyncStatus();
      console.log('Clock Sync Status:', {
        offset: `${syncStatus.offset.toFixed(3)}ms`,
        healthy: syncStatus.isHealthy,
        latency: `${timingService.getWebSocketLatency().toFixed(3)}ms`,
      });
    }, 5000);

  } catch (error) {
    console.error('Failed to initialize timing service:', error);
  }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  timingService.shutdown();
});

// Example React component usage
/*
import React, { useEffect, useState } from 'react';
import { DriftMonitor } from './components/DriftMonitor';
import { TimingService } from './services/timingService';

function VideoTestPage() {
  const [timingService] = useState(() => new TimingService(config));
  const [videoIds, setVideoIds] = useState<string[]>([]);

  useEffect(() => {
    async function setup() {
      await timingService.initialize();

      // Register videos
      const videos = document.querySelectorAll('video');
      const ids: string[] = [];

      videos.forEach((video, index) => {
        const id = `video-${index}`;
        video.id = id;
        ids.push(id);
        timingService.registerVideo(id, video);
      });

      setVideoIds(ids);
    }

    setup();

    return () => {
      timingService.shutdown();
    };
  }, []);

  return (
    <div>
      <h1>Video Synchronization Test</h1>

      <div className="videos">
        <video src="/test-video-1.mp4" controls />
        <video src="/test-video-2.mp4" controls />
        <video src="/test-video-3.mp4" controls />
      </div>

      <DriftMonitor
        timingService={timingService}
        videoIds={videoIds}
      />
    </div>
  );
}
*/

// Export for use in application
export { timingService, initializeVideoTiming };
