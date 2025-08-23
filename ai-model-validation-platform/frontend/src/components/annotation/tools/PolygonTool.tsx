import React, { useState, useCallback, useRef } from 'react';
import { Point, AnnotationShape } from '../types';
import { useAnnotation } from '../AnnotationManager';

interface PolygonToolProps {
  onComplete?: (shape: AnnotationShape) => void;
  onCancel?: () => void;
  enabled?: boolean;
}

// Hook that provides polygon tool functionality
export const usePolygonTool = (props: PolygonToolProps) => {
  const { state, actions } = useAnnotation();
  const [currentPoints, setCurrentPoints] = useState<Point[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [previewPoint, setPreviewPoint] = useState<Point | null>(null);

  const startPointRef = useRef<Point | null>(null);
  const MIN_POINTS = 3;
  const CLOSE_THRESHOLD = 10; // pixels

  // Start polygon drawing
  const startPolygon = useCallback((point: Point) => {
    if (!props.enabled) return;
    
    setCurrentPoints([point]);
    setIsDrawing(true);
    startPointRef.current = point;
    actions.setDrawing(true);
  }, [props.enabled, actions]);

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
      props.onComplete?.(shape);
    }

    // Reset state
    setCurrentPoints([]);
    setIsDrawing(false);
    setPreviewPoint(null);
    startPointRef.current = null;
    actions.setDrawing(false);
  }, [currentPoints, actions, state.settings.defaultStyle, props]);

  // Cancel polygon
  const cancelPolygon = useCallback(() => {
    setCurrentPoints([]);
    setIsDrawing(false);
    setPreviewPoint(null);
    startPointRef.current = null;
    actions.setDrawing(false);
    props.onCancel?.();
  }, [actions, props]);

  // Update preview point for live drawing feedback
  const updatePreview = useCallback((point: Point) => {
    if (!isDrawing) return;
    setPreviewPoint(point);
  }, [isDrawing]);

  // Handle mouse events
  const handleMouseClick = useCallback((point: Point, event: MouseEvent) => {
    if (!props.enabled) return;
    
    event.preventDefault();
    event.stopPropagation();

    if (!isDrawing) {
      startPolygon(point);
    } else {
      addPoint(point);
    }
  }, [props.enabled, isDrawing, startPolygon, addPoint]);

  const handleMouseMove = useCallback((point: Point) => {
    if (props.enabled && isDrawing) {
      updatePreview(point);
    }
  }, [props.enabled, isDrawing, updatePreview]);

  const handleDoubleClick = useCallback((point: Point, event: MouseEvent) => {
    if (!props.enabled || !isDrawing) return;
    
    event.preventDefault();
    event.stopPropagation();
    
    completePolygon();
  }, [props.enabled, isDrawing, completePolygon]);

  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    if (!props.enabled || !isDrawing) return;

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
  }, [props.enabled, isDrawing, currentPoints.length, cancelPolygon, completePolygon]);

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
    if (!props.enabled) return 'default';
    if (isDrawing) return 'crosshair';
    return 'crosshair';
  }, [props.enabled, isDrawing]);

  // Get tool status text
  const getStatusText = useCallback(() => {
    if (!props.enabled) return '';
    if (!isDrawing) return 'Click to start polygon';
    if (currentPoints.length < MIN_POINTS) {
      return `Click to add point (${currentPoints.length}/${MIN_POINTS} minimum)`;
    }
    return `Click to add point, double-click or Enter to finish, Esc to cancel (${currentPoints.length} points)`;
  }, [props.enabled, isDrawing, currentPoints.length]);

  return {
    // Event handlers
    handleMouseClick,
    handleMouseMove,
    handleDoubleClick,
    handleKeyPress,
    
    // Tool state
    isDrawing,
    enabled: props.enabled || false,
    currentPoints,
    previewPoint,
    
    // Actions
    startPolygon,
    addPoint,
    completePolygon,
    cancelPolygon,
    updatePreview,
    
    // Rendering
    renderCurrentPolygon,
    
    // Tool properties
    getCursor,
    getStatusText,
    
    // Constants
    MIN_POINTS,
    CLOSE_THRESHOLD,
  } as const;
};

// React component for PolygonTool with UI controls
const PolygonTool: React.FC<PolygonToolProps> = (props) => {
  const polygonTool = usePolygonTool(props);
  
  return (
    <div className="polygon-tool-controls" style={{
      padding: '12px',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      backgroundColor: '#fafafa',
      marginBottom: '8px'
    }}>
      {/* Polygon tool controls UI */}
      <div className="polygon-info" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ 
          fontSize: '14px', 
          fontWeight: '500', 
          color: '#333',
          borderBottom: '1px solid #ddd',
          paddingBottom: '6px'
        }}>
          Polygon Tool
        </div>
        
        {polygonTool.isDrawing && (
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '4px',
            fontSize: '12px',
            color: '#666'
          }}>
            <div>Points: {polygonTool.currentPoints.length}</div>
            <div>Minimum: {polygonTool.MIN_POINTS}</div>
            {polygonTool.currentPoints.length >= polygonTool.MIN_POINTS && (
              <div style={{ color: '#2e7d32', fontWeight: '500' }}>
                Ready to close (double-click or Enter)
              </div>
            )}
          </div>
        )}
        
        <div style={{ 
          fontSize: '11px', 
          color: '#999',
          lineHeight: '1.4'
        }}>
          <div>• Click to add vertices</div>
          <div>• Double-click to finish</div>
          <div>• Backspace to remove last point</div>
          <div>• Escape to cancel</div>
          <div>• Click near start point to close</div>
        </div>
      </div>
      
      {polygonTool.enabled && (
        <div 
          className="tool-status" 
          style={{ 
            marginTop: '8px',
            padding: '6px',
            backgroundColor: '#f0f7ff',
            border: '1px solid #b3d9ff',
            borderRadius: '4px',
            fontSize: '11px',
            color: '#1976d2'
          }}
        >
          {polygonTool.getStatusText()}
        </div>
      )}
    </div>
  );
};

export default PolygonTool;