import React from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Divider,
} from '@mui/material';
import { VideoFile } from '../services/types';
import GroundTruthProcessor from './GroundTruthProcessor';
import VideoValidationControls from './VideoValidationControls';
import { getStatusDisplayInfo } from '../utils/videoStatusUtils';

interface EnhancedVideoCardProps {
  video: VideoFile;
  onStatusChange?: (videoId: string, newStatus: string) => void;
  onProcessingStart?: (videoId: string) => void;
  onProcessingComplete?: (videoId: string) => void;
}

const EnhancedVideoCard: React.FC<EnhancedVideoCardProps> = ({
  video,
  onStatusChange,
  onProcessingStart,
  onProcessingComplete,
}) => {
  const statusInfo = getStatusDisplayInfo(video.status as any);

  const handleValidationComplete = (videoId: string, newStatus: string) => {
    onStatusChange?.(videoId, newStatus);
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box sx={{ mr: 1 }}>{statusInfo.icon}</Box>
          <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
            {video.filename || video.originalName}
          </Typography>
        </Box>
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {statusInfo.description}
        </Typography>
        
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" display="block">
            Size: {(video.fileSize || video.file_size || 0 / (1024 * 1024)).toFixed(1)} MB
          </Typography>
          {video.duration && (
            <Typography variant="caption" display="block">
              Duration: {Math.round(video.duration)} seconds
            </Typography>
          )}
          {video.detectionCount !== undefined && (
            <Typography variant="caption" display="block">
              Detections: {video.detectionCount}
            </Typography>
          )}
        </Box>
        
        <Divider sx={{ my: 2 }} />
        
        {/* Ground Truth Processing */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Ground Truth Processing
          </Typography>
          <GroundTruthProcessor
            video={video}
            onProcessingStart={onProcessingStart}
            onProcessingComplete={onProcessingComplete}
          />
        </Box>
        
        <Divider sx={{ my: 2 }} />
        
        {/* Video Validation Controls */}
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Validation Status
          </Typography>
          <VideoValidationControls
            video={video}
            onValidationComplete={handleValidationComplete}
          />
        </Box>
      </CardContent>
    </Card>
  );
};

export default EnhancedVideoCard;