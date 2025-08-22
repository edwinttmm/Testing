import React from 'react';
import {
  Paper, Typography, List, ListItem, ListItemText, 
  ListItemAvatar, Avatar, Chip, Box, Button, CircularProgress,
  Alert
} from '@mui/material';
import { Visibility, CameraAlt, Person } from '@mui/icons-material';

interface DetectionResult {
  id: string;
  timestamp: number;
  frameNumber: number;
  confidence: number;
  classLabel: string;
  vruType: string;
  boundingBox: {
    x: number;
    y: number; 
    width: number;
    height: number;
  };
  screenshotPath?: string;
  screenshotZoomPath?: string;
}

interface DetectionResultsPanelProps {
  detections: DetectionResult[];
  onDetectionSelect?: (detection: DetectionResult) => void;
  loading?: boolean;
  error?: string | null;
  isRunning?: boolean;
}

const DetectionResultsPanel: React.FC<DetectionResultsPanelProps> = ({
  detections,
  onDetectionSelect,
  loading = false,
  error = null,
  isRunning = false
}) => {
  if (isRunning) {
    return (
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CircularProgress size={24} />
          <Typography variant="h6">
            Running Detection Pipeline...
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Analyzing video for VRU objects. This may take a few minutes.
        </Typography>
      </Paper>
    );
  }

  if (loading) {
    return (
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CircularProgress size={24} />
          <Typography variant="h6">Loading detections...</Typography>
        </Box>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ p: 2 }}>
        <Alert severity="error">
          <Typography variant="h6">Detection Error</Typography>
          <Typography variant="body2">{error}</Typography>
        </Alert>
      </Paper>
    );
  }

  if (!detections || detections.length === 0) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          No Detections Found
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Click "Start Detection" to analyze this video for VRU objects.
        </Typography>
      </Paper>
    );
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';  
    return 'error';
  };

  const getVRUIcon = (vruType: string) => {
    switch (vruType?.toLowerCase()) {
      case 'pedestrian':
        return <Person />;
      case 'cyclist':
        return <CameraAlt />; // Could use a bike icon if available
      default:
        return <CameraAlt />;
    }
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Detection Results ({detections.length})
      </Typography>
      
      <List sx={{ maxHeight: 400, overflow: 'auto' }}>
        {detections.map((detection, index) => (
          <ListItem 
            key={detection.id || index}
            sx={{ 
              border: '1px solid #e0e0e0', 
              mb: 1, 
              borderRadius: 1,
              cursor: 'pointer',
              '&:hover': { backgroundColor: 'action.hover' }
            }}
            onClick={() => onDetectionSelect?.(detection)}
          >
            <ListItemAvatar>
              <Avatar sx={{ bgcolor: 'primary.main' }}>
                {getVRUIcon(detection.vruType || detection.classLabel)}
              </Avatar>
            </ListItemAvatar>
            
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle2">
                    {detection.classLabel || detection.vruType || 'Unknown'}
                  </Typography>
                  <Chip 
                    label={`${(detection.confidence * 100).toFixed(1)}%`}
                    color={getConfidenceColor(detection.confidence)}
                    size="small"
                  />
                </Box>
              }
              secondary={
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Frame {detection.frameNumber} • {detection.timestamp?.toFixed(2)}s
                  </Typography>
                  {detection.boundingBox && (
                    <Typography variant="caption" color="text.secondary">
                      Box: {Math.round(detection.boundingBox.x)},{Math.round(detection.boundingBox.y)} 
                      {Math.round(detection.boundingBox.width)}×{Math.round(detection.boundingBox.height)}
                    </Typography>
                  )}
                </Box>
              }
            />
            
            {detection.screenshotPath && (
              <Button
                size="small"
                startIcon={<Visibility />}
                onClick={(e) => {
                  e.stopPropagation();
                  // Open screenshot in new tab
                  const baseUrl = window.location.origin;
                  window.open(`${baseUrl}${detection.screenshotPath}`, '_blank');
                }}
              >
                View
              </Button>
            )}
          </ListItem>
        ))}
      </List>
    </Paper>
  );
};

export default DetectionResultsPanel;