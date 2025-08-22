import React from 'react';
import { Box, Typography, Alert } from '@mui/material';
import { VideoFile, GroundTruthAnnotation } from '../services/types';

interface VideoAnnotationPlayerProps {
  video: VideoFile;
  annotations: GroundTruthAnnotation[];
  onAnnotationSelect?: (annotation: GroundTruthAnnotation) => void;
  onTimeUpdate?: (currentTime: number, frameNumber: number) => void;
  onCanvasClick?: (x: number, y: number, frameNumber: number, timestamp: number) => void;
  annotationMode: boolean;
  selectedAnnotation?: GroundTruthAnnotation | null;
  frameRate?: number;
  showDetectionControls?: boolean;
  detectionControlsComponent?: React.ReactNode;
  // Additional props for SequentialVideoManager compatibility
  onVideoEnd?: () => void;
  enableFullscreen?: boolean;
  syncIndicator?: boolean;
  onSyncRequest?: () => void;
  recordingMode?: boolean;
  onRecordingToggle?: (isRecording: boolean) => void;
  externalTimeSync?: number | undefined;
}

// Fallback/legacy video annotation player component
const VideoAnnotationPlayer: React.FC<VideoAnnotationPlayerProps> = ({
  video,
  annotations,
  onAnnotationSelect,
  onTimeUpdate,
  onCanvasClick,
  annotationMode,
  selectedAnnotation,
  frameRate = 30,
  showDetectionControls = false,
  detectionControlsComponent,
  // Additional props for SequentialVideoManager compatibility
  onVideoEnd,
  enableFullscreen = false,
  syncIndicator = false,
  onSyncRequest,
  recordingMode = false,
  onRecordingToggle,
  externalTimeSync,
}) => {
  return (
    <Box sx={{ p: 2 }}>
      <Alert severity="info" sx={{ mb: 2 }}>
        Classic annotation mode is not fully implemented. Please use Enhanced mode.
      </Alert>
      
      <Typography variant="h6" gutterBottom>
        Video: {video.filename}
      </Typography>
      
      <Box sx={{ 
        width: '100%', 
        height: 400, 
        bgcolor: 'grey.100', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        borderRadius: 1
      }}>
        <video
          src={video.url}
          controls
          style={{ maxWidth: '100%', maxHeight: '100%' }}
          onTimeUpdate={(e) => {
            const currentTime = e.currentTarget.currentTime;
            onTimeUpdate?.(currentTime, Math.floor(currentTime * frameRate));
          }}
          onEnded={() => {
            onVideoEnd?.();
          }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const currentTime = e.currentTarget.currentTime;
            onCanvasClick?.(x, y, Math.floor(currentTime * frameRate), currentTime);
          }}
        />
      </Box>
      
      {showDetectionControls && detectionControlsComponent && (
        <Box sx={{ mt: 2 }}>
          {detectionControlsComponent}
        </Box>
      )}
      
      {annotations.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2">
            Annotations: {annotations.length}
          </Typography>
          {selectedAnnotation && (
            <Typography variant="body2" color="primary">
              Selected: {selectedAnnotation.vruType} at frame {selectedAnnotation.frameNumber}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
};

export default VideoAnnotationPlayer;