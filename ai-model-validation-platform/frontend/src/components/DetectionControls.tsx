import React, { useState, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Alert,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Tooltip,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Settings,
  ExpandMore,
  ExpandLess,
  CheckCircle,
  Error as ErrorIcon,
  HourglassEmpty,
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation, VRUType } from '../services/types';
import { detectionService, DetectionConfig } from '../services/detectionService';
import { apiService } from '../services/api';
import { getErrorMessage } from '../utils/errorUtils';
import { generateDetectionId, createDetectionTracker } from '../utils/detectionIdManager';

export interface DetectionStatus {
  isRunning: boolean;
  progress: number;
  stage: 'idle' | 'initializing' | 'processing' | 'analyzing' | 'saving' | 'completed' | 'error';
  message: string;
  detectionCount: number;
  source: 'backend' | 'fallback' | null;
}

interface DetectionControlsProps {
  video: VideoFile;
  onDetectionStart: () => void;
  onDetectionComplete: (annotations: GroundTruthAnnotation[]) => void;
  onDetectionError: (error: string) => void;
  disabled?: boolean;
  initialConfig?: Partial<DetectionConfig>;
}

const DetectionControls: React.FC<DetectionControlsProps> = ({
  video,
  onDetectionStart,
  onDetectionComplete,
  onDetectionError,
  disabled = false,
  initialConfig = {},
}) => {
  const [status, setStatus] = useState<DetectionStatus>({
    isRunning: false,
    progress: 0,
    stage: 'idle',
    message: 'Ready to start detection',
    detectionCount: 0,
    source: null,
  });

  const [config, setConfig] = useState<DetectionConfig>({
    confidenceThreshold: initialConfig.confidenceThreshold ?? 0.5,
    nmsThreshold: initialConfig.nmsThreshold ?? 0.5,
    modelName: initialConfig.modelName ?? 'yolov8s',
    targetClasses: initialConfig.targetClasses ?? ['person', 'bicycle', 'motorcycle'],
    maxRetries: initialConfig.maxRetries ?? 2,
    retryDelay: initialConfig.retryDelay ?? 1000,
    useFallback: initialConfig.useFallback ?? true,
  });

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const updateStatus = useCallback((updates: Partial<DetectionStatus>) => {
    setStatus(prev => ({ ...prev, ...updates }));
  }, []);

  const simulateProgress = useCallback((startProgress: number, endProgress: number, duration: number) => {
    const steps = 20;
    const increment = (endProgress - startProgress) / steps;
    const stepDuration = duration / steps;

    let currentProgress = startProgress;
    const interval = setInterval(() => {
      currentProgress += increment;
      if (currentProgress >= endProgress) {
        clearInterval(interval);
        updateStatus({ progress: endProgress });
      } else {
        updateStatus({ progress: currentProgress });
      }
    }, stepDuration);

    return () => clearInterval(interval);
  }, [updateStatus]);

  const startDetection = useCallback(async () => {
    if (status.isRunning || disabled) return;

    try {
      // Reset state
      setRetryCount(0);
      updateStatus({
        isRunning: true,
        progress: 0,
        stage: 'initializing',
        message: 'Initializing detection pipeline...',
        detectionCount: 0,
        source: null,
      });

      onDetectionStart();

      // Stage 1: Initialization (0-20%)
      const cleanup1 = simulateProgress(0, 20, 1000);
      await new Promise(resolve => setTimeout(resolve, 1000));
      cleanup1();

      updateStatus({
        stage: 'processing',
        message: 'Processing video frames...',
        progress: 20,
      });

      // Stage 2: Processing (20-70%)
      const cleanup2 = simulateProgress(20, 70, 3000);

      // Run actual detection
      const detectionResult = await detectionService.runDetection(video.id, config);
      cleanup2();

      if (detectionResult.success) {
        updateStatus({
          stage: 'analyzing',
          message: 'Analyzing detection results...',
          progress: 70,
        });

        // Stage 3: Analysis (70-85%)
        const cleanup3 = simulateProgress(70, 85, 1000);
        await new Promise(resolve => setTimeout(resolve, 1000));
        cleanup3();

        updateStatus({
          stage: 'saving',
          message: 'Saving annotations...',
          progress: 85,
        });

        // Stage 4: Save annotations (85-100%)
        const savedAnnotations: GroundTruthAnnotation[] = [];

        for (const detection of detectionResult.detections) {
          try {
            const annotationPayload: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'> = {
              videoId: video.id,
              detectionId: detection.detectionId || generateDetectionId(detection.vruType as VRUType, detection.frameNumber),
              frameNumber: detection.frameNumber,
              timestamp: detection.timestamp,
              vruType: detection.vruType as VRUType,
              boundingBox: detection.boundingBox,
              occluded: detection.occluded || false,
              truncated: detection.truncated || false,
              difficult: detection.difficult || false,
              validated: false,
            };

            const savedAnnotation = await apiService.createAnnotation(video.id, annotationPayload);
            savedAnnotations.push(savedAnnotation);

            // Update detection tracker
            createDetectionTracker(
              savedAnnotation.detectionId,
              savedAnnotation.vruType,
              savedAnnotation.frameNumber,
              savedAnnotation.timestamp,
              savedAnnotation.boundingBox,
              savedAnnotation.boundingBox.confidence || 1.0
            );
          } catch (err) {
            console.warn('Failed to save detection as annotation:', err);
          }
        }

        updateStatus({
          stage: 'completed',
          message: `Detection completed successfully! Found ${savedAnnotations.length} objects.`,
          progress: 100,
          detectionCount: savedAnnotations.length,
          source: detectionResult.source,
          isRunning: false,
        });

        onDetectionComplete(savedAnnotations);

      } else {
        throw new Error(detectionResult.error || 'Detection failed');
      }

    } catch (error: any) {
      const errorMessage = getErrorMessage(error, 'Detection failed');
      
      updateStatus({
        stage: 'error',
        message: errorMessage,
        progress: 0,
        isRunning: false,
      });

      onDetectionError(errorMessage);
    }
  }, [video.id, config, status.isRunning, disabled, onDetectionStart, onDetectionComplete, onDetectionError, updateStatus, simulateProgress]);

  const stopDetection = useCallback(() => {
    updateStatus({
      isRunning: false,
      stage: 'idle',
      message: 'Detection stopped by user',
      progress: 0,
    });
  }, [updateStatus]);

  const retryDetection = useCallback(async () => {
    if (retryCount >= 3) {
      onDetectionError('Maximum retry attempts reached. Please try with different settings.');
      return;
    }

    setRetryCount(prev => prev + 1);

    // Adjust config for retry
    const retryConfig = {
      ...config,
      confidenceThreshold: Math.max(0.3, config.confidenceThreshold - 0.1),
      modelName: retryCount === 0 ? 'yolov8n' : 'yolov8s', // Try different models
    };

    setConfig(retryConfig);
    await startDetection();
  }, [retryCount, config, startDetection, onDetectionError]);

  const getStatusIcon = () => {
    switch (status.stage) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'error':
        return <ErrorIcon color="error" />;
      case 'idle':
        return null;
      default:
        return <HourglassEmpty color="primary" />;
    }
  };

  const getStatusColor = () => {
    switch (status.stage) {
      case 'completed':
        return 'success.main';
      case 'error':
        return 'error.main';
      case 'idle':
        return 'text.secondary';
      default:
        return 'primary.main';
    }
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Stack spacing={2}>
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">
              Detection Controls
            </Typography>
            <Tooltip title="Advanced Settings">
              <IconButton
                onClick={() => setShowAdvanced(!showAdvanced)}
                size="small"
              >
                <Settings />
              </IconButton>
            </Tooltip>
          </Box>

          {/* Status Display */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {getStatusIcon()}
            <Box sx={{ flex: 1 }}>
              <Typography variant="body1" sx={{ color: getStatusColor() }}>
                {status.message}
              </Typography>
              {status.source && (
                <Typography variant="caption" color="text.secondary">
                  Source: {status.source === 'backend' ? 'AI Backend' : 'Demo Mode'}
                </Typography>
              )}
            </Box>
            {status.detectionCount > 0 && (
              <Chip
                label={`${status.detectionCount} objects`}
                color="success"
                size="small"
              />
            )}
          </Box>

          {/* Progress Bar */}
          {status.isRunning && (
            <Box>
              <LinearProgress variant="determinate" value={status.progress} />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                {status.progress.toFixed(0)}% complete
              </Typography>
            </Box>
          )}

          {/* Error Display with Retry */}
          {status.stage === 'error' && (
            <Alert
              severity="error"
              action={
                retryCount < 3 ? (
                  <Button
                    color="inherit"
                    size="small"
                    onClick={retryDetection}
                  >
                    Retry ({retryCount + 1}/3)
                  </Button>
                ) : null
              }
            >
              {status.message}
            </Alert>
          )}

          {/* Control Buttons */}
          <Stack direction="row" spacing={2}>
            {!status.isRunning ? (
              <Button
                variant="contained"
                startIcon={<PlayArrow />}
                onClick={startDetection}
                disabled={disabled}
                color="primary"
              >
                Start Detection
              </Button>
            ) : (
              <Button
                variant="outlined"
                startIcon={<Stop />}
                onClick={stopDetection}
                color="error"
              >
                Stop Detection
              </Button>
            )}

            <Tooltip title="Toggle Advanced Settings">
              <Button
                variant="outlined"
                startIcon={showAdvanced ? <ExpandLess /> : <ExpandMore />}
                onClick={() => setShowAdvanced(!showAdvanced)}
                size="small"
              >
                Advanced
              </Button>
            </Tooltip>
          </Stack>

          {/* Advanced Settings */}
          <Collapse in={showAdvanced}>
            <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom>
                Detection Configuration
              </Typography>
              
              <Stack spacing={2}>
                <FormControl fullWidth size="small">
                  <InputLabel id="model-select-label">Model</InputLabel>
                  <Select
                    labelId="model-select-label"
                    value={config.modelName}
                    label="Model"
                    onChange={(e) => setConfig(prev => ({ ...prev, modelName: e.target.value }))}
                    disabled={status.isRunning}
                  >
                    <MenuItem value="yolov8n">YOLOv8 Nano (Fast)</MenuItem>
                    <MenuItem value="yolov8s">YOLOv8 Small (Balanced)</MenuItem>
                    <MenuItem value="yolov8m">YOLOv8 Medium (Accurate)</MenuItem>
                  </Select>
                </FormControl>

                <Box>
                  <Typography variant="caption" gutterBottom>
                    Confidence Threshold: {config.confidenceThreshold}
                  </Typography>
                  <input
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.1"
                    value={config.confidenceThreshold}
                    onChange={(e) => setConfig(prev => ({ 
                      ...prev, 
                      confidenceThreshold: parseFloat(e.target.value) 
                    }))}
                    disabled={status.isRunning}
                    style={{ width: '100%' }}
                  />
                </Box>

                <Box>
                  <Typography variant="caption" gutterBottom>
                    NMS Threshold: {config.nmsThreshold}
                  </Typography>
                  <input
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.1"
                    value={config.nmsThreshold}
                    onChange={(e) => setConfig(prev => ({ 
                      ...prev, 
                      nmsThreshold: parseFloat(e.target.value) 
                    }))}
                    disabled={status.isRunning}
                    style={{ width: '100%' }}
                  />
                </Box>

                <FormControl fullWidth size="small">
                  <InputLabel id="target-classes-select-label">Target Classes</InputLabel>
                  <Select
                    labelId="target-classes-select-label"
                    multiple
                    value={config.targetClasses}
                    label="Target Classes"
                    onChange={(e) => setConfig(prev => ({ 
                      ...prev, 
                      targetClasses: typeof e.target.value === 'string' 
                        ? e.target.value.split(',') 
                        : e.target.value 
                    }))}
                    disabled={status.isRunning}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {(selected as string[]).map((value) => (
                          <Chip key={value} label={value} size="small" />
                        ))}
                      </Box>
                    )}
                  >
                    <MenuItem value="person">Person</MenuItem>
                    <MenuItem value="bicycle">Bicycle</MenuItem>
                    <MenuItem value="motorcycle">Motorcycle</MenuItem>
                    <MenuItem value="car">Car</MenuItem>
                  </Select>
                </FormControl>
              </Stack>
            </Box>
          </Collapse>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default DetectionControls;