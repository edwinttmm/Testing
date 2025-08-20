import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  IconButton,
  Slider,
  Typography,
  Card,
  CardContent,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  VolumeUp,
  VolumeOff,
  Fullscreen,
  SkipNext,
  SkipPrevious,
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation } from '../services/types';
import {
  safeVideoPlay,
  safeVideoPause,
  cleanupVideoElement,
  setVideoSource,
  addVideoEventListeners,
} from '../utils/videoUtils';
import { videoUtils, generateVideoUrl, getFallbackVideoUrl, VideoMetadata } from '../utils/videoUtils';
import { isDebugEnabled } from '../utils/envConfig';

interface VideoAnnotationPlayerProps {
  video: VideoFile;
  annotations: GroundTruthAnnotation[];
  onAnnotationSelect?: (annotation: GroundTruthAnnotation) => void;
  onTimeUpdate?: (currentTime: number, frameNumber: number) => void;
  onCanvasClick?: (x: number, y: number, frameNumber: number, timestamp: number) => void;
  annotationMode: boolean;
  selectedAnnotation?: GroundTruthAnnotation | null;
  frameRate?: number;
}


const VideoAnnotationPlayer: React.FC<VideoAnnotationPlayerProps> = ({
  video,
  annotations,
  onAnnotationSelect,
  onTimeUpdate,
  onCanvasClick,
  annotationMode,
  selectedAnnotation,
  frameRate = 30,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [videoSize, setVideoSize] = useState({ width: 0, height: 0 });

  // Calculate current frame number
  const currentFrame = Math.floor(currentTime * frameRate);

  // Get annotations for current frame
  const currentAnnotations = annotations.filter(
    annotation => Math.abs(annotation.frameNumber - currentFrame) <= 1
  );

  // Initialize video with enhanced cleanup and fallback URL handling
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement || (!video.url && !video.filename && !video.id)) return;

    // Track if this effect is still valid
    let effectValid = true;

    const initializeVideo = async () => {
      try {
        // First, ensure any previous video is properly cleaned up
        cleanupVideoElement(videoElement);
        
        // Small delay to ensure DOM is ready
        await new Promise(resolve => setTimeout(resolve, 50));
        
        if (!effectValid) return; // Effect was cleaned up while waiting

        // Generate or get video URL using environment-aware utilities
        let videoUrl = video.url;
        
        if (!videoUrl) {
          // Convert video to metadata format for URL generation
          const videoMetadata: VideoMetadata = {
            id: video.id,
            filename: video.filename,
            originalName: video.originalName,
            url: video.url || '',
            size: video.fileSize || 0,
            status: video.status as any
          };
          
          if (isDebugEnabled()) {
            console.log('🎥 Generating video URL for:', videoMetadata);
          }
          
          // Try to get a working video URL with fallbacks
          const fallbackUrl = await getFallbackVideoUrl(videoMetadata);
          videoUrl = fallbackUrl || undefined;
          
          if (!videoUrl) {
            // Enhanced error handling for missing videos
            console.error(`❌ Video ${video.id} not found. This may be a deleted or missing video.`);
            console.error('Video object:', video);
            
            // Clear any stale cache for this video using utility function
            try {
              videoUtils.clearStaleVideoCache([video.id]); // Clear from videoUtils cache
              
              // Also clear localStorage cache for this specific video
              if (typeof window !== 'undefined') {
                try {
                  const videoCache = localStorage.getItem('video-cache');
                  if (videoCache) {
                    const cache = JSON.parse(videoCache);
                    if (cache[video.id]) {
                      delete cache[video.id];
                      localStorage.setItem('video-cache', JSON.stringify(cache));
                      console.log(`🧹 Cleared localStorage cache for video ${video.id}`);
                    }
                  }
                } catch (storageError) {
                  console.warn('Failed to clear localStorage video cache:', storageError);
                }
              }
            } catch (cacheError) {
              console.warn('Failed to clear video cache:', cacheError);
            }
            
            throw new Error(`Video ${video.id} not found. This video may have been deleted or moved.`);
          }
        }
        
        if (isDebugEnabled()) {
          console.log('🎥 Using video URL:', videoUrl);
        }
        
        await setVideoSource(videoElement, videoUrl);
        
        if (!effectValid) return; // Effect was cleaned up while loading
        
        // Setup event handlers
        const handleLoadedMetadata = () => {
          if (!effectValid) return;
          setDuration(videoElement.duration);
          setVideoSize({ width: videoElement.videoWidth, height: videoElement.videoHeight });
          // Delay drawing annotations to ensure canvas is ready
          requestAnimationFrame(() => {
            if (effectValid) {
              // Draw annotations after video is loaded
              const canvas = canvasRef.current;
              if (canvas && videoElement && videoElement.videoWidth && videoElement.videoHeight) {
                // Initial canvas setup - drawAnnotations will be called by useEffect
                const ctx = canvas.getContext('2d');
                if (ctx) {
                  ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
              }
            }
          });
        };

        const handleTimeUpdate = () => {
          if (!effectValid || videoElement.currentTime === undefined) return;
          const time = videoElement.currentTime;
          setCurrentTime(time);
          const frame = Math.floor(time * frameRate);
          onTimeUpdate?.(time, frame);
        };

        const handlePlay = () => effectValid && setIsPlaying(true);
        const handlePause = () => effectValid && setIsPlaying(false);
        const handleEnded = () => effectValid && setIsPlaying(false);
        
        const handleError = (event: Event) => {
          console.error('Video playback error:', event);
          if (effectValid) setIsPlaying(false);
        };

        // Use utility function for batch event listener management
        const cleanupListeners = addVideoEventListeners(videoElement, [
          { event: 'loadedmetadata', handler: handleLoadedMetadata },
          { event: 'timeupdate', handler: handleTimeUpdate },
          { event: 'play', handler: handlePlay },
          { event: 'pause', handler: handlePause },
          { event: 'ended', handler: handleEnded },
          { event: 'error', handler: handleError },
          { event: 'loadstart', handler: () => console.log('Video loading started') },
          { event: 'canplay', handler: () => console.log('Video can start playing') }
        ]);

        // Store cleanup function for effect cleanup
        return cleanupListeners;
      } catch (error) {
        console.error('Video initialization error:', error);
        if (effectValid) setIsPlaying(false);
        return () => {};
      }
    };

    // Initialize video and store cleanup function
    let cleanupListeners: (() => void) | undefined;
    initializeVideo().then(cleanup => {
      cleanupListeners = cleanup;
    });

    // Cleanup function
    return () => {
      effectValid = false;
      
      // Clean up event listeners
      if (cleanupListeners) {
        cleanupListeners();
      }
      
      // Cleanup video element using utility - use local variable to avoid stale closure
      const currentVideoElement = videoRef.current;
      if (currentVideoElement) {
        cleanupVideoElement(currentVideoElement);
      }
    };
  }, [video.url, frameRate, onTimeUpdate]); // Include video.url in deps to reinitialize on video change

  // Draw annotations on canvas
  const drawAnnotations = useCallback(() => {
    const canvas = canvasRef.current;
    const videoElement = videoRef.current;
    
    if (!canvas || !videoElement) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Set canvas size to match video display size
    const rect = videoElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Calculate scaling factors
    const scaleX = rect.width / videoSize.width;
    const scaleY = rect.height / videoSize.height;

    if (videoSize.width === 0 || videoSize.height === 0) return;

    // Draw current annotations
    currentAnnotations.forEach(annotation => {
      const bbox = annotation.boundingBox;
      
      // Scale bounding box to canvas size
      const x = bbox.x * scaleX;
      const y = bbox.y * scaleY;
      const width = bbox.width * scaleX;
      const height = bbox.height * scaleY;

      // Set style based on annotation type and selection
      const isSelected = selectedAnnotation?.id === annotation.id;
      const color = getVRUColor(annotation.vruType);
      
      ctx.strokeStyle = isSelected ? '#ff0000' : color;
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.fillStyle = isSelected ? 'rgba(255, 0, 0, 0.1)' : `${color}20`;

      // Draw bounding box
      ctx.strokeRect(x, y, width, height);
      ctx.fillRect(x, y, width, height);

      // Draw label
      ctx.fillStyle = isSelected ? '#ff0000' : color;
      ctx.font = '14px Arial';
      const labelText = `${annotation.vruType} (${annotation.detectionId})`;
      const labelWidth = ctx.measureText(labelText).width;
      
      // Label background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(x, y - 20, labelWidth + 8, 18);
      
      // Label text
      ctx.fillStyle = '#ffffff';
      ctx.fillText(labelText, x + 4, y - 6);

      // Draw validation indicator
      if (annotation.validated) {
        ctx.fillStyle = '#4caf50';
        ctx.fillRect(x + width - 20, y, 20, 20);
        ctx.fillStyle = '#ffffff';
        ctx.font = '12px Arial';
        ctx.fillText('✓', x + width - 15, y + 14);
      }
    });
  }, [currentAnnotations, selectedAnnotation, videoSize]);

  // Redraw annotations when annotations change
  useEffect(() => {
    drawAnnotations();
  }, [drawAnnotations]);

  // Handle canvas click
  const handleCanvasClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!annotationMode) return;

    const canvas = canvasRef.current;
    const videoElement = videoRef.current;
    
    if (!canvas || !videoElement) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Convert to video coordinates
    const scaleX = videoSize.width / rect.width;
    const scaleY = videoSize.height / rect.height;
    const videoX = x * scaleX;
    const videoY = y * scaleY;

    // Check if click is on existing annotation
    const clickedAnnotation = currentAnnotations.find(annotation => {
      const bbox = annotation.boundingBox;
      return (
        videoX >= bbox.x &&
        videoX <= bbox.x + bbox.width &&
        videoY >= bbox.y &&
        videoY <= bbox.y + bbox.height
      );
    });

    if (clickedAnnotation) {
      onAnnotationSelect?.(clickedAnnotation);
    } else {
      // Create new annotation at click position
      onCanvasClick?.(videoX, videoY, currentFrame, currentTime);
    }
  }, [annotationMode, currentAnnotations, videoSize, currentFrame, currentTime, onAnnotationSelect, onCanvasClick]);

  // Get color for VRU type
  const getVRUColor = (vruType: string): string => {
    const colors = {
      pedestrian: '#2196f3',
      cyclist: '#4caf50',
      motorcyclist: '#ff9800',
      wheelchair_user: '#9c27b0',
      scooter_rider: '#ff5722',
    };
    return colors[vruType as keyof typeof colors] || '#607d8b';
  };

  // Control functions with proper error handling using utilities
  const togglePlayPause = useCallback(async () => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      if (isPlaying) {
        safeVideoPause(videoElement);
        setIsPlaying(false);
      } else {
        // Check if video is ready before attempting to play
        if (videoElement.readyState < HTMLMediaElement.HAVE_METADATA) {
          console.warn('Video not ready for playback');
          return;
        }
        
        const result = await safeVideoPlay(videoElement);
        if (result.success) {
          setIsPlaying(true);
        } else {
          console.warn('Video play failed:', result.error?.message);
          setIsPlaying(false);
        }
      }
    } catch (error) {
      console.error('Toggle play/pause error:', error);
      setIsPlaying(false);
    }
  }, [isPlaying]);

  const handleSeek = (value: number) => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      videoElement.currentTime = value;
      setCurrentTime(value);
    } catch (error) {
      console.warn('Video seek failed:', error);
    }
  };

  const handleVolumeChange = (value: number) => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    videoElement.volume = value;
    setVolume(value);
    setIsMuted(value === 0);
  };

  const toggleMute = () => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    if (isMuted) {
      videoElement.volume = volume;
      setIsMuted(false);
    } else {
      videoElement.volume = 0;
      setIsMuted(true);
    }
  };

  const stepFrame = (direction: 'forward' | 'backward') => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      const frameTime = 1 / frameRate;
      const newTime = direction === 'forward' 
        ? Math.min(currentTime + frameTime, duration)
        : Math.max(currentTime - frameTime, 0);
      
      videoElement.currentTime = newTime;
      setCurrentTime(newTime);
    } catch (error) {
      console.warn('Frame step failed:', error);
    }
  };

  const formatTime = (time: number): string => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box ref={containerRef} sx={{ position: 'relative', bgcolor: 'black', borderRadius: 1 }}>
          {/* Video Element */}
          <video
            ref={videoRef}
            style={{
              width: '100%',
              height: 'auto',
              display: 'block',
              maxHeight: '500px',
            }}
            src={video.url}
            preload="metadata"
            playsInline
            onResize={() => {
              const videoElement = videoRef.current;
              if (videoElement && videoElement.videoWidth && videoElement.videoHeight) {
                setVideoSize({
                  width: videoElement.videoWidth,
                  height: videoElement.videoHeight,
                });
              }
            }}
            onError={(e) => {
              console.error('Video element error:', e);
            }}
            onAbort={(e) => {
              console.warn('Video loading aborted:', e);
            }}
          />

          {/* Annotation Canvas Overlay */}
          <canvas
            ref={canvasRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: annotationMode ? 'auto' : 'none',
              cursor: annotationMode ? 'crosshair' : 'default',
            }}
            onClick={handleCanvasClick}
          />

          {/* Annotation Mode Indicator */}
          {annotationMode && (
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                bgcolor: 'rgba(255, 152, 0, 0.9)',
                color: 'white',
                px: 2,
                py: 1,
                borderRadius: 1,
                fontSize: '14px',
                fontWeight: 'bold',
              }}
            >
              ANNOTATION MODE
            </Box>
          )}
        </Box>

        {/* Video Controls */}
        <Box sx={{ mt: 2 }}>
          {/* Progress Slider */}
          <Box sx={{ mb: 2 }}>
            <Slider
              value={currentTime}
              min={0}
              max={duration}
              onChange={(_, value) => handleSeek(value as number)}
              sx={{ width: '100%' }}
              size="small"
            />
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1 }}>
              <Typography variant="caption">
                Frame: {currentFrame} | {formatTime(currentTime)} / {formatTime(duration)}
              </Typography>
              <Typography variant="caption">
                Annotations: {currentAnnotations.length}
              </Typography>
            </Stack>
          </Box>

          {/* Control Buttons */}
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
            <Tooltip title="Previous Frame">
              <IconButton onClick={() => stepFrame('backward')} size="small">
                <SkipPrevious />
              </IconButton>
            </Tooltip>
            
            <Tooltip title={isPlaying ? 'Pause' : 'Play'}>
              <IconButton onClick={togglePlayPause}>
                {isPlaying ? <Pause /> : <PlayArrow />}
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Next Frame">
              <IconButton onClick={() => stepFrame('forward')} size="small">
                <SkipNext />
              </IconButton>
            </Tooltip>

            <Box sx={{ mx: 2, display: 'flex', alignItems: 'center', minWidth: 120 }}>
              <Tooltip title={isMuted ? 'Unmute' : 'Mute'}>
                <IconButton onClick={toggleMute} size="small">
                  {isMuted ? <VolumeOff /> : <VolumeUp />}
                </IconButton>
              </Tooltip>
              <Slider
                value={isMuted ? 0 : volume}
                min={0}
                max={1}
                step={0.1}
                onChange={(_, value) => handleVolumeChange(value as number)}
                size="small"
                sx={{ ml: 1, width: 80 }}
              />
            </Box>

            <Tooltip title="Fullscreen">
              <IconButton size="small">
                <Fullscreen />
              </IconButton>
            </Tooltip>
          </Stack>
        </Box>

        {/* Current Annotations Info */}
        {currentAnnotations.length > 0 && (
          <Paper sx={{ mt: 2, p: 2, bgcolor: 'grey.50' }}>
            <Typography variant="subtitle2" gutterBottom>
              Current Frame Annotations ({currentAnnotations.length})
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {currentAnnotations.map(annotation => (
                <Box
                  key={annotation.id}
                  onClick={() => onAnnotationSelect?.(annotation)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 2,
                    py: 1,
                    bgcolor: selectedAnnotation?.id === annotation.id ? 'primary.main' : 'white',
                    color: selectedAnnotation?.id === annotation.id ? 'white' : 'text.primary',
                    border: '1px solid',
                    borderColor: getVRUColor(annotation.vruType),
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': {
                      bgcolor: selectedAnnotation?.id === annotation.id ? 'primary.dark' : 'grey.100',
                    },
                  }}
                >
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      bgcolor: getVRUColor(annotation.vruType),
                      borderRadius: '50%',
                    }}
                  />
                  <Typography variant="caption">
                    {annotation.vruType} ({annotation.detectionId})
                  </Typography>
                  {annotation.validated && (
                    <Typography variant="caption" sx={{ color: 'success.main' }}>
                      ✓
                    </Typography>
                  )}
                </Box>
              ))}
            </Stack>
          </Paper>
        )}
      </CardContent>
    </Card>
  );
};

export default VideoAnnotationPlayer;