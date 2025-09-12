import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { FrameDetection } from '../../types/enhanced-results';
import { useBoundaryBoxSnapping } from '../../hooks/useBoundaryBoxSnapping';

export interface BoundaryBoxVisualizerProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  videoUrl: string;
  frameNumber: number;
  detections: FrameDetection[];
  groundTruthDetections?: FrameDetection[];
  width: number;
  height: number;
  showSnapGrid?: boolean;
  snapToGrid?: boolean;
  gridSize?: number;
  onBoundingBoxUpdate?: (detection: FrameDetection, newBoundingBox: FrameDetection['boundingBox']) => void;
  onDetectionSelect?: (detection: FrameDetection) => void;
  highlightFrame80?: boolean;
  showConfidence?: boolean;
  showCoordinates?: boolean;
  enableDragAndDrop?: boolean;
  debugMode?: boolean;
}

export const BoundaryBoxVisualizer: React.FC<BoundaryBoxVisualizerProps> = ({
  videoRef,
  videoUrl,
  frameNumber,
  detections,
  groundTruthDetections = [],
  width,
  height,
  showSnapGrid = true,
  snapToGrid = true,
  gridSize = 20,
  onBoundingBoxUpdate,
  onDetectionSelect,
  highlightFrame80 = false,
  showConfidence = true,
  showCoordinates = false,
  enableDragAndDrop = true,
  debugMode = false
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const [selectedDetection, setSelectedDetection] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartPos, setDragStartPos] = useState<{ x: number; y: number } | null>(null);

  // Initialize boundary box snapping
  const snappingOptions = useMemo(() => ({
    enabled: snapToGrid,
    gridSize: gridSize || 20,
    width,
    height,
    snapDistance: 15,
    snapToGrid: true,
    snapToDetections: true,
    snapToEdges: true,
    snapToCenters: true
  }), [snapToGrid, gridSize, width, height]);

  const {
    snapPosition,
    isNearSnapPoint,
    getSnapPoint,
    snapPoints,
    setDetections: setSnappingDetections
  } = useBoundaryBoxSnapping(snappingOptions);

  // Update snapping detections when detections change
  useEffect(() => {
    const snappingData = detections.map(detection => ({
      id: detection.id,
      boundingBox: detection.boundingBox
    }));
    setSnappingDetections(snappingData);
  }, [detections, setSnappingDetections]);

  // Draw boundary boxes and overlays
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = width;
    canvas.height = height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw grid if enabled
    if (showSnapGrid && snapToGrid) {
      drawGrid(ctx, gridSize || 20, width, height);
    }

    // Highlight Frame 80 if enabled
    if (highlightFrame80 && frameNumber === 80) {
      drawFrame80Highlight(ctx, width, height);
    }

    // Draw ground truth detections first (underneath)
    groundTruthDetections.forEach(detection => {
      drawBoundingBox(ctx, detection, 'groundtruth', false, showConfidence, showCoordinates);
    });

    // Draw regular detections
    detections.forEach(detection => {
      const isSelected = selectedDetection === detection.id;
      drawBoundingBox(ctx, detection, 'detection', isSelected, showConfidence, showCoordinates);
    });

    // Draw snap points if in debug mode
    if (debugMode && snapToGrid) {
      drawSnapPoints(ctx, snapPoints);
    }

  }, [frameNumber, detections, groundTruthDetections, selectedDetection, showSnapGrid, snapToGrid, gridSize, highlightFrame80, showConfidence, showCoordinates, debugMode, snapPoints, width, height]);

  const drawGrid = (ctx: CanvasRenderingContext2D, size: number, w: number, h: number) => {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 1;
    
    // Vertical lines
    for (let x = 0; x <= w; x += size) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    // Horizontal lines
    for (let y = 0; y <= h; y += size) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
  };

  const drawFrame80Highlight = (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = 'rgba(255, 215, 0, 0.1)';
    ctx.fillRect(0, 0, w, h);
    
    ctx.strokeStyle = '#ffd700';
    ctx.lineWidth = 3;
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(2, 2, w - 4, h - 4);
    ctx.setLineDash([]);

    // Frame 80 label
    ctx.fillStyle = '#ffd700';
    ctx.font = 'bold 16px Arial';
    ctx.fillText('FRAME 80 - VALIDATION', 10, 25);
  };

  const drawBoundingBox = (
    ctx: CanvasRenderingContext2D,
    detection: FrameDetection,
    type: 'detection' | 'groundtruth',
    isSelected: boolean,
    showConf: boolean,
    showCoords: boolean
  ) => {
    const { boundingBox } = detection;
    const { x, y, width: w, height: h } = boundingBox;

    // Colors based on type and confidence
    let strokeColor = '#ff4444';
    let fillColor = 'rgba(255, 68, 68, 0.1)';
    let lineWidth = 2;

    if (type === 'groundtruth') {
      strokeColor = '#44ff44';
      fillColor = 'rgba(68, 255, 68, 0.1)';
      lineWidth = 3;
    } else {
      // Color by confidence for detections
      if (detection.confidence >= 0.8) {
        strokeColor = '#44ff44'; // Green for high confidence
        fillColor = 'rgba(68, 255, 68, 0.1)';
      } else if (detection.confidence >= 0.6) {
        strokeColor = '#ffaa44'; // Orange for medium confidence
        fillColor = 'rgba(255, 170, 68, 0.1)';
      } else {
        strokeColor = '#ff4444'; // Red for low confidence
        fillColor = 'rgba(255, 68, 68, 0.1)';
      }
    }

    if (isSelected) {
      lineWidth = 4;
      strokeColor = '#ffff00'; // Yellow for selected
    }

    // Draw bounding box
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;
    ctx.lineWidth = lineWidth;
    
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);

    // Draw label background
    const label = type === 'groundtruth' ? 'GT' : detection.className;
    const labelText = showConf && detection.confidence 
      ? `${label} ${Math.round(detection.confidence * 100)}%`
      : label;

    ctx.font = '12px Arial';
    const textMetrics = ctx.measureText(labelText);
    const textWidth = textMetrics.width;
    const textHeight = 16;

    ctx.fillStyle = strokeColor;
    ctx.fillRect(x, y - textHeight - 2, textWidth + 8, textHeight + 4);

    // Draw label text
    ctx.fillStyle = '#ffffff';
    ctx.fillText(labelText, x + 4, y - 4);

    // Draw coordinates if enabled
    if (showCoords) {
      const coordText = `(${Math.round(x)}, ${Math.round(y)})`;
      ctx.font = '10px Arial';
      ctx.fillStyle = strokeColor;
      ctx.fillText(coordText, x, y + h + 12);
    }

    // Draw VRU type indicator
    if (detection.vruType) {
      const vruIndicator = detection.vruType.charAt(0).toUpperCase();
      ctx.fillStyle = strokeColor;
      ctx.fillRect(x + w - 20, y, 20, 20);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 12px Arial';
      ctx.textAlign = 'center';
      ctx.fillText(vruIndicator, x + w - 10, y + 14);
      ctx.textAlign = 'left';
    }
  };

  const drawSnapPoints = (ctx: CanvasRenderingContext2D, points: Array<{ x: number; y: number; type: string }>) => {
    points.forEach(point => {
      ctx.fillStyle = point.type === 'grid' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 255, 255, 0.6)';
      ctx.beginPath();
      ctx.arc(point.x, point.y, 3, 0, 2 * Math.PI);
      ctx.fill();
    });
  };

  const handleCanvasClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Find clicked detection
    const clickedDetection = detections.find(detection => {
      const { boundingBox } = detection;
      return (
        x >= boundingBox.x &&
        x <= boundingBox.x + boundingBox.width &&
        y >= boundingBox.y &&
        y <= boundingBox.y + boundingBox.height
      );
    });

    if (clickedDetection) {
      setSelectedDetection(clickedDetection.id);
      onDetectionSelect?.(clickedDetection);
    } else {
      setSelectedDetection(null);
    }
  }, [detections, onDetectionSelect]);

  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!enableDragAndDrop) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Check if clicking on a detection
    const clickedDetection = detections.find(detection => {
      const { boundingBox } = detection;
      return (
        x >= boundingBox.x &&
        x <= boundingBox.x + boundingBox.width &&
        y >= boundingBox.y &&
        y <= boundingBox.y + boundingBox.height
      );
    });

    if (clickedDetection) {
      setIsDragging(true);
      setDragStartPos({ x, y });
      setSelectedDetection(clickedDetection.id);
    }
  }, [enableDragAndDrop, detections]);

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging || !dragStartPos || !selectedDetection) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const currentX = event.clientX - rect.left;
    const currentY = event.clientY - rect.top;

    const deltaX = currentX - dragStartPos.x;
    const deltaY = currentY - dragStartPos.y;

    const detection = detections.find(d => d.id === selectedDetection);
    if (!detection) return;

    const newBoundingBox = {
      ...detection.boundingBox,
      x: Math.max(0, Math.min(width - detection.boundingBox.width, detection.boundingBox.x + deltaX)),
      y: Math.max(0, Math.min(height - detection.boundingBox.height, detection.boundingBox.y + deltaY))
    };

    // Apply snapping if enabled
    if (snapToGrid) {
      const snapped = snapPosition({ x: newBoundingBox.x, y: newBoundingBox.y });
      if (snapped.snapped) {
        newBoundingBox.x = snapped.x;
        newBoundingBox.y = snapped.y;
      }
    }

    onBoundingBoxUpdate?.(detection, newBoundingBox);
    setDragStartPos({ x: currentX, y: currentY });
  }, [isDragging, dragStartPos, selectedDetection, detections, width, height, snapToGrid, snapPosition, onBoundingBoxUpdate]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setDragStartPos(null);
  }, []);

  return (
    <Box
      ref={overlayRef}
      sx={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'auto',
        zIndex: 10
      }}
    >
      <canvas
        ref={canvasRef}
        onClick={handleCanvasClick}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          width: '100%',
          height: '100%',
          cursor: isDragging ? 'grabbing' : enableDragAndDrop ? 'pointer' : 'default'
        }}
      />
    </Box>
  );
};

export default BoundaryBoxVisualizer;