import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControlLabel,
  Switch,
  Slider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
  ButtonGroup,
  Button
} from '@mui/material';
import {
  ZoomIn,
  ZoomOut,
  CenterFocusStrong,
  Visibility,
  VisibilityOff,
  Palette,
  Save
} from '@mui/icons-material';
import {
  FrameDetection,
  DetectionMatch,
  ComparisonViewMode
} from '../../types/enhanced-results';

interface DetectionOverlayProps {
  videoUrl: string;
  frameNumber: number;
  groundTruthDetections: FrameDetection[];
  testDetections: FrameDetection[];
  matches: DetectionMatch[];
  viewMode: ComparisonViewMode;
  onDetectionSelect?: (detection: FrameDetection) => void;
  width?: number;
  height?: number;
}

interface DetectionBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  className: string;
  isGroundTruth: boolean;
  matchType?: 'true_positive' | 'false_positive' | 'false_negative' | 'unmatched';
  iouScore?: number;
}

export const DetectionOverlay: React.FC<DetectionOverlayProps> = ({
  videoUrl,
  frameNumber,
  groundTruthDetections,
  testDetections,
  matches,
  viewMode,
  onDetectionSelect,
  width = 800,
  height = 600
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [zoom, setZoom] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredDetection, setHoveredDetection] = useState<DetectionBox | null>(null);
  
  // Visualization settings
  const [showConfidence, setShowConfidence] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showIou, setShowIou] = useState(true);
  const [overlayOpacity, setOverlayOpacity] = useState(viewMode.overlayOpacity);
  const [colorScheme, setColorScheme] = useState<'default' | 'colorblind' | 'high_contrast'>('default');

  // Color schemes
  const colorSchemes = {
    default: {
      groundTruth: '#00ff00', // Green
      truePositive: '#00ff00',
      falsePositive: '#ff0000', // Red  
      falseNegative: '#ff8800', // Orange
      prediction: '#0088ff' // Blue
    },
    colorblind: {
      groundTruth: '#2166ac',
      truePositive: '#2166ac', 
      falsePositive: '#d73027',
      falseNegative: '#f4a582',
      prediction: '#5aae61'
    },
    high_contrast: {
      groundTruth: '#ffffff',
      truePositive: '#ffffff',
      falsePositive: '#000000',
      falseNegative: '#666666',
      prediction: '#cccccc'
    }
  };

  const colors = colorSchemes[colorScheme];

  // Convert detections to drawable boxes
  const getDetectionBoxes = useCallback((): DetectionBox[] => {
    const boxes: DetectionBox[] = [];
    
    // Add ground truth detections
    groundTruthDetections.forEach(detection => {
      const match = matches.find(m => m.groundTruthDetection.id === detection.id);
      boxes.push({
        x: detection.boundingBox.x,
        y: detection.boundingBox.y,
        width: detection.boundingBox.width,
        height: detection.boundingBox.height,
        confidence: detection.confidence || 1.0,
        className: detection.className,
        isGroundTruth: true,
        matchType: match ? 'true_positive' : 'false_negative',
        iouScore: match?.iouScore
      });
    });

    // Add test detections
    testDetections.forEach(detection => {
      const match = matches.find(m => m.testDetection.id === detection.id);
      boxes.push({
        x: detection.boundingBox.x,
        y: detection.boundingBox.y,
        width: detection.boundingBox.width,
        height: detection.boundingBox.height,
        confidence: detection.confidence,
        className: detection.className,
        isGroundTruth: false,
        matchType: match ? 'true_positive' : 'false_positive',
        iouScore: match?.iouScore
      });
    });

    return boxes;
  }, [groundTruthDetections, testDetections, matches]);

  // Draw detection boxes on canvas
  const drawDetections = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Set up transforms
    ctx.save();
    ctx.scale(zoom, zoom);
    ctx.translate(panOffset.x / zoom, panOffset.y / zoom);

    const boxes = getDetectionBoxes();

    boxes.forEach(box => {
      // Determine colors and styles
      let strokeColor = colors.prediction;
      let fillColor = colors.prediction;
      let lineWidth = 2;
      let lineDash: number[] = [];

      if (box.isGroundTruth) {
        strokeColor = colors.groundTruth;
        fillColor = colors.groundTruth;
        lineDash = [5, 5]; // Dashed line for ground truth
      }

      if (box.matchType === 'true_positive') {
        strokeColor = colors.truePositive;
        fillColor = colors.truePositive;
        lineWidth = 3;
      } else if (box.matchType === 'false_positive') {
        strokeColor = colors.falsePositive;
        fillColor = colors.falsePositive;
      } else if (box.matchType === 'false_negative') {
        strokeColor = colors.falseNegative;
        fillColor = colors.falseNegative;
      }

      // Adjust opacity
      const alpha = box.isGroundTruth ? 1.0 : overlayOpacity;
      
      // Draw bounding box
      ctx.strokeStyle = strokeColor;
      ctx.fillStyle = fillColor + Math.round(alpha * 0.2 * 255).toString(16).padStart(2, '0');
      ctx.lineWidth = lineWidth;
      ctx.setLineDash(lineDash);

      ctx.fillRect(box.x, box.y, box.width, box.height);
      ctx.strokeRect(box.x, box.y, box.width, box.height);

      // Draw labels
      if (showLabels) {
        const labelY = box.y > 25 ? box.y - 5 : box.y + box.height + 20;
        
        // Label background
        ctx.fillStyle = strokeColor;
        const labelText = box.className;
        const labelWidth = ctx.measureText(labelText).width + 8;
        ctx.fillRect(box.x, labelY - 15, labelWidth, 18);
        
        // Label text
        ctx.fillStyle = 'white';
        ctx.font = '12px Arial';
        ctx.fillText(labelText, box.x + 4, labelY - 2);
      }

      // Draw confidence
      if (showConfidence && !box.isGroundTruth) {
        const confText = `${(box.confidence * 100).toFixed(0)}%`;
        const confY = showLabels ? 
          (box.y > 45 ? box.y - 25 : box.y + box.height + 40) :
          (box.y > 25 ? box.y - 5 : box.y + box.height + 20);
        
        // Confidence background
        ctx.fillStyle = strokeColor;
        const confWidth = ctx.measureText(confText).width + 6;
        ctx.fillRect(box.x + box.width - confWidth, confY - 15, confWidth, 18);
        
        // Confidence text
        ctx.fillStyle = 'white';
        ctx.font = '11px Arial';
        ctx.fillText(confText, box.x + box.width - confWidth + 3, confY - 2);
      }

      // Draw IoU score for matches
      if (showIou && box.iouScore !== undefined) {
        const iouText = `IoU: ${(box.iouScore * 100).toFixed(0)}%`;
        const iouY = box.y + box.height - 5;
        
        // IoU background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        const iouWidth = ctx.measureText(iouText).width + 6;
        ctx.fillRect(box.x, iouY - 15, iouWidth, 18);
        
        // IoU text
        ctx.fillStyle = 'white';
        ctx.font = '10px Arial';
        ctx.fillText(iouText, box.x + 3, iouY - 2);
      }
    });

    // Draw hover effect
    if (hoveredDetection) {
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 4;
      ctx.setLineDash([]);
      ctx.strokeRect(
        hoveredDetection.x,
        hoveredDetection.y,
        hoveredDetection.width,
        hoveredDetection.height
      );
    }

    ctx.restore();
  }, [
    zoom, panOffset, getDetectionBoxes, colors, overlayOpacity, 
    showLabels, showConfidence, showIou, hoveredDetection
  ]);

  // Handle canvas mouse events
  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left - panOffset.x) / zoom;
    const y = (event.clientY - rect.top - panOffset.y) / zoom;

    // Check if clicked on a detection
    const boxes = getDetectionBoxes();
    const clickedBox = boxes.find(box =>
      x >= box.x && x <= box.x + box.width &&
      y >= box.y && y <= box.y + box.height
    );

    if (clickedBox) {
      // Find original detection
      const detection = clickedBox.isGroundTruth
        ? groundTruthDetections.find(d => 
            d.boundingBox.x === clickedBox.x && d.boundingBox.y === clickedBox.y)
        : testDetections.find(d => 
            d.boundingBox.x === clickedBox.x && d.boundingBox.y === clickedBox.y);
      
      if (detection) {
        onDetectionSelect?.(detection);
      }
    } else {
      // Start panning
      setIsDragging(true);
      setDragStart({ x: event.clientX - panOffset.x, y: event.clientY - panOffset.y });
    }
  }, [zoom, panOffset, getDetectionBoxes, groundTruthDetections, testDetections, onDetectionSelect]);

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (isDragging) {
      setPanOffset({
        x: event.clientX - dragStart.x,
        y: event.clientY - dragStart.y
      });
    } else {
      // Check hover state
      const rect = canvas.getBoundingClientRect();
      const x = (event.clientX - rect.left - panOffset.x) / zoom;
      const y = (event.clientY - rect.top - panOffset.y) / zoom;

      const boxes = getDetectionBoxes();
      const hovered = boxes.find(box =>
        x >= box.x && x <= box.x + box.width &&
        y >= box.y && y <= box.y + box.height
      );

      setHoveredDetection(hovered || null);
      canvas.style.cursor = hovered ? 'pointer' : 'grab';
    }
  }, [isDragging, dragStart, zoom, panOffset, getDetectionBoxes]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Zoom controls
  const handleZoomIn = () => setZoom(prev => Math.min(prev * 1.2, 5));
  const handleZoomOut = () => setZoom(prev => Math.max(prev / 1.2, 0.1));
  const handleZoomReset = () => {
    setZoom(1);
    setPanOffset({ x: 0, y: 0 });
  };

  // Load video frame
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedData = () => {
      if (video.duration && frameNumber < video.duration * 30) { // Assuming 30fps
        video.currentTime = frameNumber / 30;
      }
    };

    const handleSeeked = () => {
      drawDetections();
    };

    video.addEventListener('loadeddata', handleLoadedData);
    video.addEventListener('seeked', handleSeeked);

    if (video.readyState >= 2) {
      handleLoadedData();
    }

    return () => {
      video.removeEventListener('loadeddata', handleLoadedData);
      video.removeEventListener('seeked', handleSeeked);
    };
  }, [videoUrl, frameNumber, drawDetections]);

  // Redraw when detections change
  useEffect(() => {
    drawDetections();
  }, [drawDetections]);

  // Save canvas as image
  const handleSaveImage = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const link = document.createElement('a');
    link.download = `frame_${frameNumber}_comparison.png`;
    link.href = canvas.toDataURL();
    link.click();
  };

  return (
    <Box>
      {/* Controls */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Zoom Controls */}
        <ButtonGroup size="small">
          <Button onClick={handleZoomOut} startIcon={<ZoomOut />}>
            Zoom Out
          </Button>
          <Button onClick={handleZoomReset} startIcon={<CenterFocusStrong />}>
            Reset
          </Button>
          <Button onClick={handleZoomIn} startIcon={<ZoomIn />}>
            Zoom In
          </Button>
        </ButtonGroup>

        {/* Visibility Toggles */}
        <FormControlLabel
          control={
            <Switch
              checked={viewMode.showGroundTruth}
              size="small"
            />
          }
          label="Ground Truth"
        />
        <FormControlLabel
          control={
            <Switch
              checked={viewMode.showPredictions}
              size="small"
            />
          }
          label="Predictions"
        />

        {/* Overlay Opacity */}
        <Box sx={{ minWidth: 150 }}>
          <Typography variant="caption" gutterBottom>
            Overlay Opacity
          </Typography>
          <Slider
            value={overlayOpacity}
            onChange={(_, value) => setOverlayOpacity(value as number)}
            min={0}
            max={1}
            step={0.1}
            size="small"
          />
        </Box>

        {/* Color Scheme */}
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Colors</InputLabel>
          <Select
            value={colorScheme}
            label="Colors"
            onChange={(e) => setColorScheme(e.target.value as any)}
          >
            <MenuItem value="default">Default</MenuItem>
            <MenuItem value="colorblind">Colorblind Friendly</MenuItem>
            <MenuItem value="high_contrast">High Contrast</MenuItem>
          </Select>
        </FormControl>

        {/* Additional Options */}
        <FormControlLabel
          control={
            <Switch
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
              size="small"
            />
          }
          label="Labels"
        />
        <FormControlLabel
          control={
            <Switch
              checked={showConfidence}
              onChange={(e) => setShowConfidence(e.target.checked)}
              size="small"
            />
          }
          label="Confidence"
        />
        <FormControlLabel
          control={
            <Switch
              checked={showIou}
              onChange={(e) => setShowIou(e.target.checked)}
              size="small"
            />
          }
          label="IoU"
        />

        {/* Save Button */}
        <Tooltip title="Save as Image">
          <IconButton onClick={handleSaveImage} size="small">
            <Save />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Canvas Container */}
      <Box
        sx={{
          position: 'relative',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          overflow: 'hidden'
        }}
      >
        {/* Hidden video element */}
        <video
          ref={videoRef}
          src={videoUrl}
          style={{ display: 'none' }}
          preload="metadata"
        />
        
        {/* Canvas for drawing detections */}
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{
            display: 'block',
            cursor: isDragging ? 'grabbing' : 'grab',
            backgroundColor: '#f5f5f5'
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />

        {/* Legend */}
        <Box
          sx={{
            position: 'absolute',
            top: 10,
            right: 10,
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            p: 1,
            borderRadius: 1,
            minWidth: 150
          }}
        >
          <Typography variant="caption" fontWeight="bold" gutterBottom>
            Legend
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box sx={{ 
                width: 16, height: 16, 
                border: `2px dashed ${colors.groundTruth}`,
                backgroundColor: colors.groundTruth + '33'
              }} />
              <Typography variant="caption">Ground Truth</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box sx={{ 
                width: 16, height: 16, 
                border: `3px solid ${colors.truePositive}`,
                backgroundColor: colors.truePositive + '33'
              }} />
              <Typography variant="caption">True Positive</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box sx={{ 
                width: 16, height: 16, 
                border: `2px solid ${colors.falsePositive}`,
                backgroundColor: colors.falsePositive + '33'
              }} />
              <Typography variant="caption">False Positive</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box sx={{ 
                width: 16, height: 16, 
                border: `2px solid ${colors.falseNegative}`,
                backgroundColor: colors.falseNegative + '33'
              }} />
              <Typography variant="caption">False Negative</Typography>
            </Box>
          </Box>
        </Box>

        {/* Zoom Level Indicator */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 10,
            left: 10,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            px: 1,
            py: 0.5,
            borderRadius: 1,
            fontSize: '12px'
          }}
        >
          {Math.round(zoom * 100)}%
        </Box>
      </Box>
    </Box>
  );
};