import React from 'react';
import {
  Paper, Typography, List, ListItem, ListItemText, 
  ListItemAvatar, Avatar, Chip, Box, Button, CircularProgress,
  Alert
} from '@mui/material';
import { Visibility, CameraAlt, Person, SmartToy, PersonOutline } from '@mui/icons-material';

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
  manualAnnotations?: DetectionResult[];
  aiDetections?: DetectionResult[];
  detections?: DetectionResult[]; // Backward compatibility
  onDetectionSelect?: (detection: DetectionResult) => void;
  loading?: boolean;
  error?: string | null;
  isRunning?: boolean;
}

interface ExtendedDetectionResult extends DetectionResult {
  source: 'manual' | 'ai';
}

const DetectionResultsPanel: React.FC<DetectionResultsPanelProps> = ({
  manualAnnotations = [],
  aiDetections = [],
  detections = [], // Backward compatibility
  onDetectionSelect,
  loading = false,
  error = null,
  isRunning = false
}) => {
  const [showManualAnnotations, setShowManualAnnotations] = React.useState(true);
  const [showAIDetections, setShowAIDetections] = React.useState(true);
  
  // Combine all detections for display (backward compatibility or dual mode)
  const combinedDetections = React.useMemo<ExtendedDetectionResult[]>(() => {
    if (detections.length > 0) {
      // Backward compatibility mode
      return detections.map(det => ({ ...det, source: 'manual' as const }));
    }
    
    const results: ExtendedDetectionResult[] = [];
    
    if (showManualAnnotations) {
      results.push(...manualAnnotations.map(annotation => ({ ...annotation, source: 'manual' as const })));
    }
    
    if (showAIDetections) {
      results.push(...aiDetections.map(detection => ({ ...detection, source: 'ai' as const })));
    }
    
    // Sort by timestamp
    return results.sort((a, b) => a.timestamp - b.timestamp);
  }, [detections, manualAnnotations, aiDetections, showManualAnnotations, showAIDetections]);

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

  if (!combinedDetections || combinedDetections.length === 0) {
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
    
    return (
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          No Detections Found
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {manualAnnotations.length === 0 && aiDetections.length === 0 
            ? 'Use the detection controls above to analyze this video for VRU objects.'
            : 'All detection types are currently hidden. Use the toggle controls below to show detections.'}
        </Typography>
      </Paper>
    );
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';  
    return 'error';
  };

  const getVRUIcon = (vruType: string, source: 'manual' | 'ai') => {
    const baseIcon = (() => {
      switch (vruType?.toLowerCase()) {
        case 'pedestrian':
          return <Person />;
        case 'cyclist':
          return <CameraAlt />; // Could use a bike icon if available
        default:
          return <CameraAlt />;
      }
    })();
    
    // Return appropriate icon based on source
    return source === 'ai' ? <SmartToy /> : baseIcon;
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="h6">
          Detection Results ({combinedDetections.length})
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          {manualAnnotations.length > 0 && (
            <Chip
              icon={<PersonOutline />}
              label={`Manual: ${manualAnnotations.length}`}
              color={showManualAnnotations ? 'primary' : 'default'}
              size="small"
              onClick={() => setShowManualAnnotations(!showManualAnnotations)}
              variant={showManualAnnotations ? 'filled' : 'outlined'}
              sx={{ cursor: 'pointer' }}
            />
          )}
          {aiDetections.length > 0 && (
            <Chip
              icon={<SmartToy />}
              label={`AI: ${aiDetections.length}`}
              color={showAIDetections ? 'secondary' : 'default'}
              size="small"
              onClick={() => setShowAIDetections(!showAIDetections)}
              variant={showAIDetections ? 'filled' : 'outlined'}
              sx={{ cursor: 'pointer' }}
            />
          )}
          {combinedDetections.length > 0 && (
            <Chip 
              label={`${combinedDetections.filter(d => d.confidence >= 0.8).length} high confidence`}
              color="success"
              size="small"
            />
          )}
        </Box>
      </Box>
      
      <List sx={{ maxHeight: 400, overflow: 'auto' }}>
        {combinedDetections.map((detection, index) => (
          <ListItem 
            key={detection.id || index}
            sx={{ 
              border: detection.source === 'manual' 
                ? '2px solid #1976d2' // Solid blue border for manual annotations
                : '2px dashed #9c27b0', // Dashed purple border for AI detections
              mb: 1, 
              borderRadius: 1,
              cursor: 'pointer',
              '&:hover': { backgroundColor: 'action.hover' },
              backgroundColor: detection.source === 'manual' 
                ? 'rgba(25, 118, 210, 0.04)' // Light blue background for manual
                : 'rgba(156, 39, 176, 0.04)' // Light purple background for AI
            }}
            onClick={() => onDetectionSelect?.(detection)}
          >
            <ListItemAvatar>
              <Avatar sx={{ 
                bgcolor: detection.source === 'manual' ? 'primary.main' : 'secondary.main'
              }}>
                {getVRUIcon(detection.vruType || detection.classLabel, detection.source)}
              </Avatar>
            </ListItemAvatar>
            
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="subtitle2">
                    {detection.classLabel || detection.vruType || 'Unknown'}
                  </Typography>
                  <Chip 
                    label={`${(detection.confidence * 100).toFixed(1)}%`}
                    color={getConfidenceColor(detection.confidence)}
                    size="small"
                  />
                  <Chip
                    label={detection.source === 'manual' ? 'Manual' : 'AI'}
                    color={detection.source === 'manual' ? 'primary' : 'secondary'}
                    size="small"
                    variant="outlined"
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
                  try {
                    // Open screenshot from backend server
                    const backendUrl = 'http://localhost:8000';
                    let screenshotUrl;
                    
                    if (detection.screenshotPath!.startsWith('http')) {
                      // Full URL already provided
                      screenshotUrl = detection.screenshotPath;
                    } else if (detection.screenshotPath!.startsWith('/')) {
                      // Relative path starting with /
                      screenshotUrl = `${backendUrl}${detection.screenshotPath}`;
                    } else {
                      // Relative path without leading /
                      screenshotUrl = `${backendUrl}/${detection.screenshotPath}`;
                    }
                    
                    // console.log('Opening screenshot URL:', screenshotUrl);
                    window.open(screenshotUrl, '_blank');
                  } catch (error) {
                    console.error('Error opening screenshot:', error);
                  }
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