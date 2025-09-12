import React, { useMemo } from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { CheckCircle, Error, AccessTime } from '@mui/icons-material';

interface Detection {
  id: string | number;
  videoId: number;
  expectedEventTime?: string;
  signalReceivedTime?: string;
  latencyMs?: number;
  outcome: 'PASS' | 'FAIL' | 'PENDING';
  createdAt: string;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence?: number;
  classLabel?: string;
}

interface DetectionOverlayProps {
  detections: Detection[];
  videoWidth: number;
  videoHeight: number;
  currentTime: number;
  isVisible: boolean;
  toleranceMs?: number;
}

const DetectionOverlay: React.FC<DetectionOverlayProps> = ({
  detections,
  videoWidth,
  videoHeight,
  currentTime,
  isVisible,
  toleranceMs = 500
}) => {
  // Filter detections that should be visible at current time
  const visibleDetections = useMemo(() => {
    if (!isVisible) return [];
    
    return detections.filter(detection => {
      // Show recent detections (within last 5 seconds)
      const detectionTime = new Date(detection.createdAt).getTime();
      const now = Date.now();
      return now - detectionTime < 5000;
    });
  }, [detections, currentTime, isVisible]);

  const getOutcomeColor = (outcome: string, latencyMs?: number) => {
    switch (outcome) {
      case 'PASS':
        return '#4caf50';
      case 'FAIL':
        return '#f44336';
      case 'PENDING':
        return '#ff9800';
      default:
        return latencyMs && latencyMs > toleranceMs ? '#f44336' : '#4caf50';
    }
  };

  const getOutcomeIcon = (outcome: string, latencyMs?: number) => {
    switch (outcome) {
      case 'PASS':
        return <CheckCircle sx={{ fontSize: 16, color: '#4caf50' }} />;
      case 'FAIL':
        return <Error sx={{ fontSize: 16, color: '#f44336' }} />;
      case 'PENDING':
        return <AccessTime sx={{ fontSize: 16, color: '#ff9800' }} />;
      default:
        return latencyMs && latencyMs > toleranceMs 
          ? <Error sx={{ fontSize: 16, color: '#f44336' }} />
          : <CheckCircle sx={{ fontSize: 16, color: '#4caf50' }} />;
    }
  };

  if (!isVisible || visibleDetections.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 1000
      }}
    >
      {visibleDetections.map((detection, index) => {
        const boundingBox = detection.boundingBox;
        
        // If we have bounding box coordinates, use them
        if (boundingBox) {
          const left = (boundingBox.x / videoWidth) * 100;
          const top = (boundingBox.y / videoHeight) * 100;
          const width = (boundingBox.width / videoWidth) * 100;
          const height = (boundingBox.height / videoHeight) * 100;

          return (
            <Box
              key={detection.id}
              sx={{
                position: 'absolute',
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
                border: `3px solid ${getOutcomeColor(detection.outcome, detection.latencyMs)}`,
                borderRadius: 1,
                backgroundColor: `${getOutcomeColor(detection.outcome, detection.latencyMs)}20`,
                animation: 'pulse 2s infinite'
              }}
            >
              {/* Detection Label */}
              <Chip
                icon={getOutcomeIcon(detection.outcome, detection.latencyMs)}
                label={`${detection.classLabel || 'Object'} ${detection.latencyMs ? `${detection.latencyMs.toFixed(1)}ms` : ''}`}
                size="small"
                sx={{
                  position: 'absolute',
                  top: -24,
                  left: 0,
                  backgroundColor: getOutcomeColor(detection.outcome, detection.latencyMs),
                  color: 'white',
                  fontSize: '0.7rem',
                  height: '20px',
                  '& .MuiChip-icon': {
                    color: 'white !important'
                  }
                }}
              />
            </Box>
          );
        } else {
          // If no bounding box, show as overlay in corner
          return (
            <Box
              key={detection.id}
              sx={{
                position: 'absolute',
                top: 16 + (index * 40),
                right: 16,
                backgroundColor: 'rgba(0,0,0,0.8)',
                borderRadius: 2,
                p: 1,
                animation: 'fadeInOut 3s ease-in-out'
              }}
            >
              <Chip
                icon={getOutcomeIcon(detection.outcome, detection.latencyMs)}
                label={`Detection ${detection.latencyMs ? `${detection.latencyMs.toFixed(1)}ms` : ''}`}
                size="small"
                sx={{
                  backgroundColor: getOutcomeColor(detection.outcome, detection.latencyMs),
                  color: 'white',
                  '& .MuiChip-icon': {
                    color: 'white !important'
                  }
                }}
              />
            </Box>
          );
        }
      })}

      {/* CSS Animations */}
      <style>
        {`
          @keyframes pulse {
            0% {
              opacity: 1;
              transform: scale(1);
            }
            50% {
              opacity: 0.7;
              transform: scale(1.05);
            }
            100% {
              opacity: 1;
              transform: scale(1);
            }
          }
          
          @keyframes fadeInOut {
            0% {
              opacity: 0;
              transform: translateX(100%);
            }
            20% {
              opacity: 1;
              transform: translateX(0);
            }
            80% {
              opacity: 1;
              transform: translateX(0);
            }
            100% {
              opacity: 0;
              transform: translateX(100%);
            }
          }
        `}
      </style>
    </Box>
  );
};

export default DetectionOverlay;