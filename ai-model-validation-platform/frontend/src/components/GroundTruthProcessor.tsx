import React, { useState } from 'react';
import {
  Box,
  Button,
  Alert,
  CircularProgress,
  Typography,
  Chip,
} from '@mui/material';
import {
  PlayArrow,
  CheckCircle,
  Error,
  HourglassEmpty,
} from '@mui/icons-material';
import { VideoFile } from '../services/types';

interface GroundTruthProcessorProps {
  video: VideoFile;
  onProcessingStart?: (videoId: string) => void;
  onProcessingComplete?: (videoId: string) => void;
}

const GroundTruthProcessor: React.FC<GroundTruthProcessorProps> = ({
  video,
  onProcessingStart,
  onProcessingComplete,
}) => {
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartProcessing = async () => {
    try {
      setProcessing(true);
      setError(null);
      
      const response = await fetch(`/api/videos/${video.id}/process-ground-truth`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        const errorInstance = Error as any;
        throw new errorInstance(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      
      if (result.status === 'started') {
        onProcessingStart?.(video.id);
      } else if (result.status === 'already_completed') {
        onProcessingComplete?.(video.id);
      } else if (result.status === 'failed') {
        setError(result.message);
      }
      
    } catch (err: any) {
      console.error('Failed to start ground truth processing:', err);
      setError(err?.message || err || 'Failed to start processing');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusIcon = () => {
    if (video.ground_truth_generated || video.groundTruthGenerated) {
      return <CheckCircle color="success" />;
    }
    if (video.processing_status === 'processing') {
      return <HourglassEmpty color="warning" />;
    }
    if (video.status === 'failed') {
      return <Error color="error" />;
    }
    return <HourglassEmpty color="info" />;
  };

  const getStatusText = () => {
    if (video.ground_truth_generated || video.groundTruthGenerated) {
      return 'Ground Truth Ready';
    }
    if (video.processing_status === 'processing') {
      return 'Processing...';
    }
    if (video.status === 'failed') {
      return 'Processing Failed';
    }
    return 'Pending Processing';
  };

  const getStatusColor = (): "success" | "warning" | "error" | "info" => {
    if (video.ground_truth_generated || video.groundTruthGenerated) {
      return 'success';
    }
    if (video.processing_status === 'processing') {
      return 'warning';
    }
    if (video.status === 'failed') {
      return 'error';
    }
    return 'info';
  };

  const canStartProcessing = () => {
    return (
      video.status === 'completed' &&
      !video.ground_truth_generated &&
      !video.groundTruthGenerated &&
      video.processing_status !== 'processing' &&
      !processing
    );
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        {getStatusIcon()}
        <Chip
          label={getStatusText()}
          color={getStatusColor()}
          size="small"
        />
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}
      
      {canStartProcessing() && (
        <Box sx={{ mt: 1 }}>
          <Button
            size="small"
            variant="outlined"
            startIcon={processing ? <CircularProgress size={16} /> : <PlayArrow />}
            onClick={handleStartProcessing}
            disabled={processing}
          >
            {processing ? 'Starting...' : 'Process Ground Truth'}
          </Button>
          <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'text.secondary' }}>
            Generate AI detections for this video
          </Typography>
        </Box>
      )}
      
      {video.processing_status === 'processing' && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
          <CircularProgress size={16} />
          <Typography variant="caption" color="text.secondary">
            AI processing in progress...
          </Typography>
        </Box>
      )}
      
      {(video.ground_truth_generated || video.groundTruthGenerated) && (
        <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'success.main' }}>
          ✅ Ground truth data available for testing
        </Typography>
      )}
    </Box>
  );
};

export default GroundTruthProcessor;