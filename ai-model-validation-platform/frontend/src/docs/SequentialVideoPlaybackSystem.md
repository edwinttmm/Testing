# Sequential Video Playback System

## Overview

The Sequential Video Playback System provides a comprehensive solution for automated video playback with fullscreen functionality, designed specifically for research and testing environments where precise video playback control and timing synchronization are essential.

## Key Features

### 🎬 **Automatic Sequential Playback**
- Automatic video transitions with configurable delays
- Smooth loading between videos with preloading optimization
- Support for various playback modes (sequential, random, loop)

### 🖥️ **Fullscreen API Integration**
- Cross-browser fullscreen support (Chrome, Firefox, Safari, Edge)
- Automatic fullscreen entry on playback start
- Video-optimized fullscreen layout with proper aspect ratio handling
- Seamless fullscreen transitions between videos

### 📊 **Comprehensive Progress Tracking**
- Real-time progress updates for individual videos and overall sequence
- Video completion tracking with persistent state
- Performance metrics and statistics

### 🔧 **Robust Error Handling**
- Automatic retry mechanisms for failed video loads
- Graceful error recovery with user notifications
- Comprehensive error logging and reporting

### 🔄 **Video Queue Management**
- Dynamic video queue with add/remove capabilities
- Video preloading for smooth transitions
- Queue reordering and shuffling support

### 🎛️ **Advanced Controls**
- Play, pause, stop, skip forward/backward
- Jump to any video in the queue
- Manual fullscreen toggle
- Configuration management

### 🔗 **External System Integration**
- LabJack data acquisition synchronization
- WebSocket communication for real-time updates
- Custom event handlers and callbacks

## Architecture

### Core Components

```
SequentialVideoPlaybackSystem (Core Engine)
├── VideoPlaybackManager (Video Operations)
├── FullscreenManager (Fullscreen API)
├── VideoQueueItem (Queue Management)
└── PlaybackConfiguration (Settings)

SequentialVideoPlayer (React Component)
├── useSequentialVideoPlayback (React Hook)
├── Video Container (DOM Element)
└── UI Controls (MUI Components)
```

### File Structure

```
src/
├── utils/
│   ├── sequentialVideoPlaybackSystem.ts    # Core playback engine
│   ├── fullscreenUtils.ts                  # Fullscreen API utilities
│   └── videoPlaybackManager.ts             # Video management (existing)
├── components/
│   └── SequentialVideoPlayer.tsx           # React component
├── hooks/
│   └── useSequentialVideoPlayback.ts       # React hook
├── examples/
│   └── SequentialVideoPlaybackExample.tsx  # Usage examples
└── docs/
    └── SequentialVideoPlaybackSystem.md    # This documentation
```

## Usage Guide

### Basic Implementation

```typescript
import React, { useRef } from 'react';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile } from '../services/types';

const MyComponent = () => {
  const videos: VideoFile[] = [
    {
      id: '1',
      filename: 'video1.mp4',
      url: '/path/to/video1.mp4',
      duration: 30,
      // ... other properties
    },
    // ... more videos
  ];

  return (
    <SequentialVideoPlayer
      videos={videos}
      config={{
        autoAdvance: true,
        fullscreenMode: true,
        autoFullscreen: true,
        preloadNext: true,
      }}
      onVideoStart={(video, index) => {
        console.log(`Started video ${index + 1}: ${video.filename}`);
      }}
      onPlaybackComplete={() => {
        console.log('All videos completed!');
      }}
    />
  );
};
```

### Advanced Configuration

```typescript
const advancedConfig = {
  autoAdvance: true,              // Auto-advance to next video
  loopPlayback: false,            // Loop back to first video when done
  randomOrder: false,             // Randomize video order
  preloadNext: true,              // Preload next video for smooth transitions
  fullscreenMode: true,           // Enable fullscreen capability
  autoFullscreen: true,           // Auto-enter fullscreen on start
  transitionDelay: 500,           // Delay between video transitions (ms)
  maxRetries: 3,                  // Max retry attempts for failed videos
  enableHardwareAcceleration: true, // Use hardware acceleration
  syncWithExternalSignals: false, // Sync with LabJack/external systems
};
```

### Using the React Hook

```typescript
import { useRef } from 'react';
import useSequentialVideoPlayback from '../hooks/useSequentialVideoPlayback';

const MyCustomPlayer = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [state, controls] = useSequentialVideoPlayback(containerRef, {
    config: {
      autoAdvance: true,
      fullscreenMode: true,
    },
    onVideoStart: (video, index) => {
      console.log('Video started:', video.filename);
    },
  });

  const handleStart = async () => {
    await controls.loadVideoQueue(videos);
    await controls.startPlayback();
  };

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: '400px' }} />
      <button onClick={handleStart}>Start Playback</button>
      <button onClick={controls.pausePlayback}>Pause</button>
      <button onClick={controls.toggleFullscreen}>Toggle Fullscreen</button>
    </div>
  );
};
```

## Configuration Options

### PlaybackConfiguration Interface

```typescript
interface PlaybackConfiguration {
  autoAdvance: boolean;              // Automatically advance to next video
  loopPlayback: boolean;             // Loop back to beginning when complete
  randomOrder: boolean;              // Randomize video playback order
  preloadNext: boolean;              // Preload next video for smooth transitions
  fullscreenMode: boolean;           // Enable fullscreen functionality
  autoFullscreen: boolean;           // Auto-enter fullscreen on playback start
  transitionDelay: number;           // Delay between videos (milliseconds)
  maxRetries: number;                // Maximum retry attempts for failed videos
  enableHardwareAcceleration: boolean; // Use GPU acceleration when available
  syncWithExternalSignals: boolean;  // Sync with external data collection
}
```

### Callback Functions

```typescript
interface PlaybackCallbacks {
  onVideoStart?: (video: VideoQueueItem, index: number) => void;
  onVideoEnd?: (video: VideoQueueItem, index: number) => void;
  onPlaybackComplete?: () => void;
  onFullscreenChange?: (isFullscreen: boolean) => void;
  onProgressUpdate?: (progress: number, videoIndex: number) => void;
  onError?: (error: PlaybackError) => void;
  onStateChange?: (state: PlaybackState) => void;
}
```

## API Reference

### SequentialVideoPlaybackSystem Class

#### Methods

```typescript
// Core playback control
loadVideoQueue(videos: VideoFile[]): Promise<void>
startPlayback(): Promise<void>
pausePlayback(): void
resumePlayback(): Promise<void>
stopPlayback(): Promise<void>

// Navigation
advanceToNext(): Promise<void>
goToPrevious(): Promise<void>
jumpToVideo(index: number): Promise<void>

// Fullscreen control
enterFullscreen(): Promise<void>
exitFullscreen(): Promise<void>

// State and information
getCurrentVideo(): VideoQueueItem | null
getState(): PlaybackState
getStatistics(): PlaybackStatistics
updateConfig(config: Partial<PlaybackConfiguration>): void

// Cleanup
destroy(): void
```

#### Events

The system emits various events through callback functions:

- `onVideoStart` - When a video begins playing
- `onVideoEnd` - When a video finishes playing
- `onPlaybackComplete` - When all videos have been played
- `onError` - When an error occurs
- `onProgressUpdate` - Progress updates (throttled)
- `onStateChange` - When playback state changes
- `onFullscreenChange` - When fullscreen state changes

### Fullscreen API Support

The system includes comprehensive fullscreen API support:

#### Supported Browsers

- **Chrome/Chromium**: `requestFullscreen()` / `exitFullscreen()`
- **Firefox**: `mozRequestFullScreen()` / `mozCancelFullScreen()`
- **Safari**: `webkitRequestFullscreen()` / `webkitExitFullscreen()`
- **Edge/IE**: `msRequestFullscreen()` / `msExitFullscreen()`

#### Video-Optimized Fullscreen

```typescript
// Automatically optimizes video display in fullscreen
await requestVideoFullscreen(videoElement, containerElement);

// Features:
// - Proper aspect ratio handling
// - Black letterboxing for non-matching ratios
// - Hardware acceleration optimization
// - Smooth enter/exit transitions
```

## Error Handling

### Error Types

```typescript
interface PlaybackError {
  videoId: string;           // ID of the problematic video
  videoIndex: number;        // Index in the queue
  errorType: 'load' | 'play' | 'fullscreen' | 'transition';
  message: string;           // Human-readable error message
  timestamp: number;         // When the error occurred
  recoverable: boolean;      // Whether automatic recovery is possible
}
```

### Automatic Recovery

The system includes sophisticated error recovery:

1. **Network Errors**: Automatic retry with exponential backoff
2. **Video Format Errors**: Skip to next video with notification
3. **Fullscreen Errors**: Graceful fallback to windowed mode
4. **Playback Errors**: Retry with different codecs/formats

### Error Logging

Errors are logged both to the console and through callback functions:

```typescript
const handleError = (error: PlaybackError) => {
  console.error('Playback error:', error);
  
  if (error.recoverable) {
    // System will automatically retry
    showNotification(`Retrying video ${error.videoIndex + 1}...`, 'warning');
  } else {
    // Manual intervention required
    showNotification(`Video ${error.videoIndex + 1} failed: ${error.message}`, 'error');
  }
};
```

## Performance Optimization

### Video Preloading

The system implements intelligent video preloading:

```typescript
// Preloading strategies:
1. **Metadata First**: Load video metadata immediately
2. **Progressive Loading**: Load next video while current is playing
3. **Bandwidth Awareness**: Adjust preloading based on connection speed
4. **Memory Management**: Limit concurrent preloaded videos
```

### Hardware Acceleration

When enabled, the system uses:

- **GPU-accelerated video decoding**
- **Hardware-accelerated CSS transforms**
- **WebGL-based video processing** (when available)
- **Optimized memory allocation**

### Browser-Specific Optimizations

```typescript
// Chrome/Chromium
video.setAttribute('webkit-playsinline', 'true');
video.style.willChange = 'transform';

// Safari
video.setAttribute('playsInline', 'true');
video.setAttribute('x-webkit-airplay', 'allow');

// Firefox
video.setAttribute('preload', 'metadata');
```

## Integration with External Systems

### LabJack Data Acquisition

The system can synchronize with LabJack devices for research applications:

```typescript
const config = {
  syncWithExternalSignals: true,
  // System will emit events at precise video timestamps
  // for synchronization with data collection
};

// Event synchronization
onVideoStart: (video, index) => {
  // Signal LabJack to start data collection
  labJackController.startCollection(video.id);
},

onVideoEnd: (video, index) => {
  // Signal LabJack to stop data collection
  labJackController.stopCollection(video.id);
}
```

### WebSocket Communication

Real-time updates via WebSocket:

```typescript
// Connect to backend for real-time updates
const ws = new WebSocket('ws://localhost:8000/video-sync');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'video_command') {
    // Execute video control commands from backend
    controls.jumpToVideo(data.videoIndex);
  }
};
```

## Testing and Debugging

### Debug Mode

Enable debug mode for detailed logging:

```typescript
// Enable in development
localStorage.setItem('sequentialVideoDebug', 'true');

// Provides detailed logs for:
// - Video loading progress
// - Fullscreen API calls
// - Event timing
// - Error stack traces
// - Performance metrics
```

### Testing Utilities

The system includes testing utilities:

```typescript
// Mock video URLs for testing
const testVideos = [
  {
    id: 'test1',
    url: 'data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDE=',
    // ... minimal valid video data
  }
];

// Simulate network conditions
const slowNetworkConfig = {
  retryDelay: 5000,
  loadTimeout: 60000,
  maxRetries: 5,
};
```

## Browser Compatibility

### Supported Browsers

| Browser | Version | Fullscreen API | Hardware Acceleration | Video Formats |
|---------|---------|----------------|----------------------|---------------|
| Chrome  | 71+     | ✅ Full        | ✅ WebGL/GPU         | H.264, WebM   |
| Firefox | 64+     | ✅ Full        | ✅ WebGL             | H.264, WebM   |
| Safari  | 12+     | ✅ Full        | ✅ Metal             | H.264, HEVC   |
| Edge    | 79+     | ✅ Full        | ✅ DirectX           | H.264, WebM   |

### Fallback Strategies

```typescript
// Graceful degradation for unsupported browsers
if (!isFullscreenSupported()) {
  // Disable fullscreen mode
  config.fullscreenMode = false;
  showNotification('Fullscreen not supported', 'info');
}

// Video format fallbacks
const videoSources = [
  { src: 'video.webm', type: 'video/webm' },
  { src: 'video.mp4', type: 'video/mp4' },
  { src: 'video.ogv', type: 'video/ogg' },
];
```

## Best Practices

### Performance

1. **Limit Queue Size**: Don't load too many videos at once
2. **Use Appropriate Codecs**: H.264 for compatibility, WebM for efficiency
3. **Monitor Memory Usage**: Implement cleanup for long sequences
4. **Progressive Enhancement**: Start with basic features, add advanced ones

### User Experience

1. **Provide Clear Feedback**: Show loading states and progress
2. **Handle Interruptions**: Allow users to pause/resume/skip
3. **Respect Preferences**: Remember user settings
4. **Accessibility**: Support keyboard navigation and screen readers

### Error Handling

1. **Fail Gracefully**: Never crash the entire application
2. **Provide Context**: Explain what went wrong and how to fix it
3. **Log Comprehensively**: Include sufficient detail for debugging
4. **User Recovery**: Offer manual retry options

## Troubleshooting

### Common Issues

#### Videos Won't Load
```typescript
// Check network connectivity
// Verify video URLs are accessible
// Ensure proper CORS headers
// Check video format compatibility
```

#### Fullscreen Not Working
```typescript
// Must be triggered by user interaction
// Check browser fullscreen support
// Verify element is properly attached to DOM
// Check for conflicting CSS
```

#### Poor Performance
```typescript
// Reduce preloading count
// Use lower quality videos for testing
// Disable hardware acceleration if causing issues
// Check for memory leaks
```

#### Synchronization Issues
```typescript
// Verify WebSocket connection
// Check timestamp accuracy
// Ensure external systems are responsive
// Monitor network latency
```

## Examples

See the `SequentialVideoPlaybackExample.tsx` file for a complete working example demonstrating all features of the system.

## Support

For issues and questions:

1. Check the browser console for error messages
2. Enable debug mode for detailed logging
3. Verify video file accessibility and formats
4. Test with minimal configuration first
5. Check network connectivity and CORS settings

---

*This system was designed specifically for research environments requiring precise video playback control and external system synchronization. It provides enterprise-level robustness while maintaining ease of use for development teams.*