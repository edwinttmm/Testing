import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Alert,
  Grid,
  Divider,
  CircularProgress,
  Paper,
  Stack,
  IconButton,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Timeline as TimelineIcon,
  Speed as SpeedIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Visibility as VisibilityIcon,
  PhotoCamera as PhotoCameraIcon,
  ZoomIn as ZoomInIcon,
} from '@mui/icons-material';
import { getVideoDetections } from '../services/api';
import { VideoFile } from '../services/types';

interface Detection {
  id: string;
  detection_id: string;
  timestamp: number;
  frame_number: number;
  confidence: number;
  class_label: string;
  vru_type: string;
  validation_result: string;
  bounding_box: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  has_visual_evidence: boolean;
  screenshot_path?: string;
  screenshot_zoom_path?: string;
  model_version: string;
  test_session_id: string;
}

interface DetectionApiResponse {
  video_id: string;
  total_detections: number;
  detections: Detection[];
}

interface RealDetectionPanelProps {
  videos: VideoFile[];
  projectId?: string;
  toleranceMs?: number;
  onDetectionComplete?: (result: any) => void;
}

export const RealDetectionPanel: React.FC<RealDetectionPanelProps> = ({
  videos,
  projectId = 'default',
  toleranceMs = 100,
  onDetectionComplete,
}) => {
  const [detectionData, setDetectionData] = useState<DetectionApiResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalDetections, setTotalDetections] = useState(0);

  // Load real detection data from backend
  const loadDetections = useCallback(async () => {
    if (videos.length === 0) {
      setDetectionData([]);
      setTotalDetections(0);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      console.log('🔍 Loading real detection data for videos:', videos.map(v => v.id));
      
      const results: DetectionApiResponse[] = [];
      let total = 0;

      for (const video of videos) {
        try {
          const response = await getVideoDetections(video.id);
          
          // The API returns the data directly, so we need to construct the response
          const detectionResponse: DetectionApiResponse = {
            video_id: video.id,
            total_detections: response.length,
            detections: response as Detection[]
          };
          
          results.push(detectionResponse);
          total += response.length;
          
          console.log(`✅ Loaded ${response.length} detections for video ${video.id}`);
        } catch (videoError) {
          console.warn(`⚠️ Failed to load detections for video ${video.id}:`, videoError);
          // Still add empty result for this video
          results.push({
            video_id: video.id,
            total_detections: 0,
            detections: []
          });
        }
      }

      setDetectionData(results);
      setTotalDetections(total);

      if (onDetectionComplete && total > 0) {
        // Call completion callback with detection summary
        onDetectionComplete({
          success: true,
          total_detections: total,
          videos_processed: videos.length,
          source: 'backend',
          data: results
        });
      }

      console.log(`🎯 Total detections loaded: ${total} from ${videos.length} videos`);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load detections';
      console.error('❌ Failed to load detection data:', error);
      setError(errorMessage);
      setDetectionData([]);
      setTotalDetections(0);
    } finally {
      setLoading(false);
    }
  }, [videos, onDetectionComplete]);

  // Load detections when videos change
  useEffect(() => {
    loadDetections();
  }, [loadDetections]);

  const getStatusColor = (): 'success' | 'error' | 'warning' | 'info' => {
    if (error) return 'error';
    if (loading) return 'info';
    if (totalDetections > 0) return 'success';
    return 'warning';
  };

  const getStatusIcon = () => {
    if (error) return <ErrorIcon color="error" />;
    if (loading) return <CircularProgress size={20} />;
    if (totalDetections > 0) return <CheckCircleIcon color="success" />;
    return <VisibilityIcon color="warning" />;
  };

  const getStatusMessage = (): string => {
    if (error) return `Error: ${error}`;
    if (loading) return 'Loading detection data...';
    if (totalDetections === 0) return 'No detections found';
    return `Found ${totalDetections} objects`;
  };

  const getSourceLabel = (): string => {
    if (totalDetections > 0) return 'AI Backend';
    return 'No Data';
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          AI Detection Results
        </Typography>

        {/* Status Display */}
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Stack direction="row" spacing={2} alignItems="center">
            {getStatusIcon()}
            
            <Box sx={{ flex: 1 }}>
              <Typography variant="body1" color={getStatusColor() === 'error' ? 'error' : 'inherit'}>
                {getStatusMessage()}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Source: {getSourceLabel()}
              </Typography>
            </Box>

            {totalDetections > 0 && (
              <Chip
                label={`${totalDetections} objects`}
                color="success"
                size="small"
              />
            )}
          </Stack>
        </Paper>

        {/* Detection Summary */}
        {detectionData.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Detection Summary by Video:
            </Typography>
            
            <Grid container spacing={1}>
              {detectionData.map((videoData, index) => {
                const video = videos.find(v => v.id === videoData.video_id);
                const filename = video?.filename || video?.name || `Video ${index + 1}`;
                
                return (
                  <Grid item xs={12} sm={6} md={4} key={videoData.video_id}>
                    <Paper variant="outlined" sx={{ p: 1 }}>
                      <Typography variant="caption" noWrap title={filename}>
                        {filename}
                      </Typography>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body2" color="text.secondary">
                          Objects:
                        </Typography>
                        <Chip 
                          label={videoData.total_detections}
                          color={videoData.total_detections > 0 ? 'success' : 'default'}
                          size="small"
                        />
                      </Box>
                    </Paper>
                  </Grid>
                );
              })}
            </Grid>
          </Box>
        )}

        {/* Visual Evidence Section - CRITICAL FIX for AI Detection Images */}
        {detectionData.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <PhotoCameraIcon fontSize="small" />
              AI Detection Visual Evidence ({detectionData.reduce((total, videoData) => 
                total + videoData.detections.filter((d: Detection) => d.has_visual_evidence).length, 0
              )} with screenshots)
            </Typography>
            
            <Grid container spacing={2} sx={{ maxHeight: 400, overflow: 'auto' }}>
              {detectionData.map((videoData) =>
                videoData.detections
                  .filter((detection: Detection) => detection.has_visual_evidence && detection.screenshot_path)
                  .slice(0, 6) // Show first 6 detections with screenshots
                  .map((detection: Detection) => (
                    <Grid item xs={12} sm={6} md={4} key={detection.id}>
                      <Paper variant="outlined" sx={{ p: 1 }}>
                        <Typography variant="caption" noWrap title={`Detection ${detection.detection_id}`}>
                          {detection.vru_type} ({(detection.confidence * 100).toFixed(1)}%)
                        </Typography>
                        <Box sx={{ position: 'relative', mt: 1 }}>
                          <img
                            src={detection.screenshot_path || '/placeholder-image.png'}
                            alt={`${detection.vru_type} detection`}
                            style={{
                              width: '100%',
                              height: '120px',
                              objectFit: 'cover',
                              borderRadius: '4px'
                            }}
                            onError={(e) => {
                              console.warn('Image failed to load:', detection.screenshot_path);
                              (e.target as HTMLImageElement).style.display = 'none';
                            }}
                          />
                          {detection.screenshot_zoom_path && (
                            <IconButton
                              size="small"
                              sx={{
                                position: 'absolute',
                                top: 4,
                                right: 4,
                                bgcolor: 'rgba(0,0,0,0.7)',
                                color: 'white',
                                '&:hover': { bgcolor: 'rgba(0,0,0,0.9)' }
                              }}
                              onClick={() => window.open(detection.screenshot_zoom_path || detection.screenshot_path, '_blank')}
                            >
                              <ZoomInIcon fontSize="small" />
                            </IconButton>
                          )}
                        </Box>
                        <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="caption" color="text.secondary">
                            Frame {detection.frame_number}
                          </Typography>
                          <Chip 
                            label={detection.validation_result || 'AI'}
                            color={detection.validation_result === 'Pass' ? 'success' : 'default'}
                            size="small"
                            sx={{ fontSize: '0.6rem', height: '18px' }}
                          />
                        </Box>
                      </Paper>
                    </Grid>
                  ))
              )}
            </Grid>
            
            {detectionData.some(videoData => 
              videoData.detections.filter((d: Detection) => d.has_visual_evidence).length > 6
            ) && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Showing first 6 detections with visual evidence. Total available: {detectionData.reduce((total, videoData) => 
                  total + videoData.detections.filter((d: Detection) => d.has_visual_evidence).length, 0
                )}
              </Typography>
            )}
          </Box>
        )}

        {/* Action Buttons */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<TimelineIcon />}
            onClick={loadDetections}
            disabled={loading || videos.length === 0}
          >
            Refresh
          </Button>
          
          {totalDetections > 0 && (
            <>
              <Divider orientation="vertical" flexItem />
              <Typography variant="caption" color="text.secondary">
                Ready for HIL testing with {totalDetections} pre-validated objects
              </Typography>
            </>
          )}
        </Box>

        {/* Error Display */}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        {/* No Videos Warning */}
        {videos.length === 0 && !loading && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Select validated videos to load detection data for HIL testing.
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};