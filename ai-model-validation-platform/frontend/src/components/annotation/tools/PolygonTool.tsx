import React, { useState, useCallback, useRef } from 'react';
import { Point, AnnotationShape } from '../types';
import { useAnnotation } from '../AnnotationManager';

interface PolygonToolProps {
  onComplete?: (shape: AnnotationShape) => void;
  onCancel?: () => void;
  enabled?: boolean;
}

const PolygonTool: React.FC<PolygonToolProps> = ({
  onComplete,
  onCancel,
  enabled = false,
}) => {
  const { state, actions } = useAnnotation();
  const [currentPoints, setCurrentPoints] = useState<Point[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [previewPoint, setPreviewPoint] = useState<Point | null>(null);

  const startPointRef = useRef<Point | null>(null);
  const MIN_POINTS = 3;
  const CLOSE_THRESHOLD = 10; // pixels

  // Start polygon drawing
  const startPolygon = useCallback((point: Point) => {
    if (!enabled) return;
    
    setCurrentPoints([point]);
    setIsDrawing(true);
    startPointRef.current = point;
    actions.setDrawing(true);
  }, [enabled, actions]);

  // Add point to polygon
  const addPoint = useCallback((point: Point) => {
    if (!isDrawing) return;

    // Check if we're close to the starting point to close the polygon
    if (currentPoints.length >= MIN_POINTS && startPointRef.current) {
      const distanceToStart = Math.sqrt(
        Math.pow(point.x - startPointRef.current.x, 2) + 
        Math.pow(point.y - startPointRef.current.y, 2)
      );
      
      if (distanceToStart <= CLOSE_THRESHOLD) {
        completePolygon();
        return;
      }
    }

    setCurrentPoints(prev => [...prev, point]);
  }, [isDrawing, currentPoints.length]);

  // Complete polygon
  const completePolygon = useCallback(() => {
    if (currentPoints.length < MIN_POINTS) return;

    // Calculate bounding box
    const xs = currentPoints.map(p => p.x);
    const ys = currentPoints.map(p => p.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);

    const shapeId = actions.createPolygon(currentPoints, {
      strokeColor: state.settings.defaultStyle.strokeColor,
      fillColor: state.settings.defaultStyle.fillColor,
    });

    const shape = actions.getShapeById(shapeId);
    if (shape) {
      onComplete?.(shape);
    }

    // Reset state
    setCurrentPoints([]);
    setIsDrawing(false);
    setPreviewPoint(null);
    startPointRef.current = null;
    actions.setDrawing(false);
  }, [currentPoints, actions, state.settings.defaultStyle, onComplete]);

  // Cancel polygon
  const cancelPolygon = useCallback(() => {
    setCurrentPoints([]);
    setIsDrawing(false);
    setPreviewPoint(null);
    startPointRef.current = null;
    actions.setDrawing(false);
    onCancel?.();
  }, [actions, onCancel]);

  // Update preview point for live drawing feedback
  const updatePreview = useCallback((point: Point) => {
    if (!isDrawing) return;
    setPreviewPoint(point);
  }, [isDrawing]);

  // Handle mouse events
  const handleMouseClick = useCallback((point: Point, event: MouseEvent) => {
    if (!enabled) return;
    
    event.preventDefault();
    event.stopPropagation();

    if (!isDrawing) {
      startPolygon(point);
    } else {
      addPoint(point);
    }
  }, [enabled, isDrawing, startPolygon, addPoint]);

  const handleMouseMove = useCallback((point: Point) => {
    if (enabled && isDrawing) {
      updatePreview(point);
    }
  }, [enabled, isDrawing, updatePreview]);

  const handleDoubleClick = useCallback((point: Point, event: MouseEvent) => {
    if (!enabled || !isDrawing) return;
    
    event.preventDefault();
    event.stopPropagation();
    
    completePolygon();
  }, [enabled, isDrawing, completePolygon]);

  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    if (!enabled || !isDrawing) return;

    switch (event.key) {
      case 'Escape':
        cancelPolygon();
        break;
      case 'Enter':
        if (currentPoints.length >= MIN_POINTS) {
          completePolygon();
        }
        break;
      case 'Backspace':
        if (currentPoints.length > 1) {
          setCurrentPoints(prev => prev.slice(0, -1));
        } else {
          cancelPolygon();
        }
        break;
    }
  }, [enabled, isDrawing, currentPoints.length, cancelPolygon, completePolygon]);

  // Render current polygon being drawn
  const renderCurrentPolygon = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!isDrawing || currentPoints.length === 0) return;

    ctx.save();
    
    // Set style
    ctx.strokeStyle = state.settings.defaultStyle.strokeColor;
    ctx.fillStyle = state.settings.defaultStyle.fillColor;
    ctx.lineWidth = state.settings.defaultStyle.strokeWidth;
    ctx.globalAlpha = 0.7;
    ctx.setLineDash([5, 5]);

    // Draw completed segments
    if (currentPoints.length > 1) {
      ctx.beginPath();
      ctx.moveTo(currentPoints[0].x, currentPoints[0].y);
      for (let i = 1; i < currentPoints.length; i++) {
        ctx.lineTo(currentPoints[i].x, currentPoints[i].y);
      }
      ctx.stroke();
    }

    // Draw preview line to cursor
    if (previewPoint && currentPoints.length > 0) {
      ctx.beginPath();
      ctx.moveTo(currentPoints[currentPoints.length - 1].x, currentPoints[currentPoints.length - 1].y);
      ctx.lineTo(previewPoint.x, previewPoint.y);
      ctx.stroke();
    }

    // Draw closing line preview if near start point
    if (currentPoints.length >= MIN_POINTS && previewPoint && startPointRef.current) {
      const distanceToStart = Math.sqrt(
        Math.pow(previewPoint.x - startPointRef.current.x, 2) + 
        Math.pow(previewPoint.y - startPointRef.current.y, 2)
      );
      
      if (distanceToStart <= CLOSE_THRESHOLD) {
        ctx.strokeStyle = '#00ff00'; // Green to indicate closing
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(previewPoint.x, previewPoint.y);
        ctx.lineTo(startPointRef.current.x, startPointRef.current.y);
        ctx.stroke();
      }
    }

    // Draw vertices
    ctx.setLineDash([]);
    ctx.fillStyle = state.settings.defaultStyle.strokeColor;
    currentPoints.forEach((point, index) => {
      ctx.beginPath();
      ctx.arc(point.x, point.y, index === 0 ? 6 : 4, 0, 2 * Math.PI);
      ctx.fill();
      
      if (index === 0) {
        // Draw special indicator for start point
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });

    ctx.restore();
  }, [isDrawing, currentPoints, previewPoint, state.settings.defaultStyle]);

  // Get tool cursor based on state
  const getCursor = useCallback(() => {
    if (!enabled) return 'default';
    if (isDrawing) return 'crosshair';
    return 'crosshair';
  }, [enabled, isDrawing]);

  // Get tool status text
  const getStatusText = useCallback(() => {
    if (!enabled) return '';
    if (!isDrawing) return 'Click to start polygon';
    if (currentPoints.length < MIN_POINTS) {
      return `Click to add point (${currentPoints.length}/${MIN_POINTS} minimum)`;
    }
    return `Click to add point, double-click or Enter to finish, Esc to cancel (${currentPoints.length} points)`;
  }, [enabled, isDrawing, currentPoints.length]);

  // Return tool interface
  return {
    enabled,
    isActive: isDrawing,
    cursor: getCursor(),
    statusText: getStatusText(),
    currentPoints,
    previewPoint,
    
    // Event handlers
    handleMouseClick,
    handleMouseMove,
    handleDoubleClick,
    handleKeyPress,
    
    // Actions
    complete: completePolygon,
    cancel: cancelPolygon,
    
    // Rendering
    render: renderCurrentPolygon,
    
    // State queries
    canComplete: currentPoints.length >= MIN_POINTS,
    pointCount: currentPoints.length,
  } as const;
};

export default PolygonTool;