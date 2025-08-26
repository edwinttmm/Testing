import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Point, BrushPoint, AnnotationShape } from '../types';
import { useAnnotation } from '../AnnotationManager';

interface BrushToolProps {
  onStrokeComplete?: (shape: AnnotationShape) => void;
  enabled?: boolean;
}

// Hook that provides brush tool functionality
export const useBrushTool = (props: BrushToolProps) => {
  const { state, actions } = useAnnotation();
  const [currentStroke, setCurrentStroke] = useState<BrushPoint[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [brushPreview, setBrushPreview] = useState<Point | null>(null);

  const lastPointRef = useRef<Point | null>(null);
  const strokeStartTimeRef = useRef<number>(0);

  const brushSettings = state.settings.brushSettings;

  // Calculate brush size based on pressure (if available) and settings
  const getBrushSize = useCallback((pressure: number = 1) => {
    return brushSettings.size * pressure;
  }, [brushSettings.size]);

  // Interpolate points between two positions for smoother strokes
  const interpolatePoints = useCallback((start: Point, end: Point, steps: number): Point[] => {
    const points: Point[] = [];
    for (let i = 1; i <= steps; i++) {
      const ratio = i / (steps + 1);
      points.push({
        x: start.x + (end.x - start.x) * ratio,
        y: start.y + (end.y - start.y) * ratio,
      });
    }
    return points;
  }, []);

  // Smooth stroke path using simple averaging
  const smoothStrokePath = useCallback((points: Point[]): Point[] => {
    if (points.length < 3) return points;

    const smoothed: Point[] = [points[0]]; // Keep first point

    for (let i = 1; i < points.length - 1; i++) {
      const prev = points[i - 1];
      const current = points[i];
      const next = points[i + 1];

      // Simple averaging for smoothing
      const smoothedPoint = {
        x: (prev.x + current.x + next.x) / 3,
        y: (prev.y + current.y + next.y) / 3,
      };

      smoothed.push(smoothedPoint);
    }

    smoothed.push(points[points.length - 1]); // Keep last point
    return smoothed;
  }, []);

  // Start brush stroke
  const startStroke = useCallback((point: Point, pressure: number = 1) => {
    if (!props.enabled) return;

    setCurrentStroke([{
      ...point,
      pressure,
      size: getBrushSize(pressure),
      timestamp: Date.now(),
    }]);
    setIsDrawing(true);
    lastPointRef.current = point;
    strokeStartTimeRef.current = Date.now();
    actions.setDrawing(true);
  }, [props.enabled, getBrushSize, actions]);

  // Add point to current stroke with interpolation for smooth lines
  const addPoint = useCallback((point: Point, pressure: number = 1) => {
    if (!isDrawing || !lastPointRef.current) return;

    // Interpolate points for smoother strokes
    const interpolatedPoints = interpolatePoints(lastPointRef.current, point, 2);
    const newPoints = interpolatedPoints.map((p, index) => ({
      ...p,
      pressure: pressure * (1 - index * 0.1), // Gradually decrease pressure
      size: getBrushSize(pressure * (1 - index * 0.1)),
      timestamp: Date.now(),
    }));

    setCurrentStroke(prev => [...prev, ...newPoints]);
    lastPointRef.current = point;
  }, [isDrawing, getBrushSize, interpolatePoints]);

  // Cancel current stroke
  const cancelStroke = useCallback(() => {
    setCurrentStroke([]);
    setIsDrawing(false);
    lastPointRef.current = null;
    actions.setDrawing(false);
  }, [actions]);

  // Complete brush stroke
  const completeStroke = useCallback(() => {
    if (currentStroke.length < 2) {
      // Too short, cancel
      cancelStroke();
      return;
    }

    // Smooth the stroke path
    const smoothedStroke = smoothStrokePath(currentStroke);

    // Calculate bounding box
    const xs = smoothedStroke.map(p => p.x);
    const ys = smoothedStroke.map(p => p.y);
    const minX = Math.min(...xs) - brushSettings.size / 2;
    const minY = Math.min(...ys) - brushSettings.size / 2;
    const maxX = Math.max(...xs) + brushSettings.size / 2;
    const maxY = Math.max(...ys) + brushSettings.size / 2;

    // Create shape from stroke
    const shape: AnnotationShape = {
      id: `brush_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type: 'brush',
      points: smoothedStroke,
      boundingBox: {
        x: minX,
        y: minY,
        width: maxX - minX,
        height: maxY - minY,
      },
      style: {
        strokeColor: brushSettings.isEraser ? 'rgba(255,255,255,0)' : state.settings.defaultStyle.strokeColor,
        fillColor: state.settings.defaultStyle.fillColor,
        strokeWidth: brushSettings.size,
        fillOpacity: brushSettings.opacity,
      },
      visible: true,
      selected: false,
    };

    actions.addShape(shape);
    props.onStrokeComplete?.(shape);

    // Reset state
    setCurrentStroke([]);
    setIsDrawing(false);
    lastPointRef.current = null;
    actions.setDrawing(false);
  }, [currentStroke, brushSettings, state.settings.defaultStyle, actions, props, cancelStroke, smoothStrokePath]);

  // Update brush preview
  const updatePreview = useCallback((point: Point) => {
    setBrushPreview(point);
  }, []);

  // Handle mouse events
  const handleMouseDown = useCallback((point: Point, event: MouseEvent) => {
    if (!props.enabled) return;

    event.preventDefault();
    event.stopPropagation();

    const pressure = (event as any).pressure || 1;
    startStroke(point, pressure);
  }, [props.enabled, startStroke]);

  const handleMouseMove = useCallback((point: Point, event?: MouseEvent) => {
    if (!props.enabled) return;

    updatePreview(point);

    if (isDrawing) {
      const pressure = (event as any)?.pressure || 1;
      addPoint(point, pressure);
    }
  }, [props.enabled, isDrawing, updatePreview, addPoint]);

  const handleMouseUp = useCallback((point: Point, event: MouseEvent) => {
    if (!props.enabled || !isDrawing) return;

    event.preventDefault();
    event.stopPropagation();

    // Add final point
    const pressure = (event as any).pressure || 1;
    addPoint(point, pressure);
    
    // Complete stroke after a short delay to allow final point processing
    setTimeout(completeStroke, 10);
  }, [props.enabled, isDrawing, addPoint, completeStroke]);

  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    if (!props.enabled) return;

    if (event.key === 'Escape' && isDrawing) {
      cancelStroke();
    }
  }, [props.enabled, isDrawing, cancelStroke]);

  // Render current brush stroke
  const renderCurrentStroke = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!isDrawing || currentStroke.length === 0) return;

    ctx.save();

    // Set style
    ctx.strokeStyle = brushSettings.isEraser 
      ? 'rgba(255, 0, 0, 0.5)' // Red overlay for eraser preview
      : state.settings.defaultStyle.strokeColor;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.globalAlpha = brushSettings.opacity;

    // Draw variable-width stroke
    if (currentStroke.length > 1) {
      for (let i = 1; i < currentStroke.length; i++) {
        const prevPoint = currentStroke[i - 1] as any;
        const currentPoint = currentStroke[i] as any;
        
        const size = currentPoint.size || brushSettings.size;
        
        ctx.lineWidth = size;
        ctx.beginPath();
        ctx.moveTo(prevPoint.x, prevPoint.y);
        ctx.lineTo(currentPoint.x, currentPoint.y);
        ctx.stroke();
      }
    }

    ctx.restore();
  }, [isDrawing, currentStroke, brushSettings, state.settings.defaultStyle]);

  // Render brush preview cursor
  const renderBrushPreview = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!props.enabled || !brushPreview) return;

    ctx.save();
    
    // Draw brush preview circle
    ctx.strokeStyle = brushSettings.isEraser ? '#ff0000' : state.settings.defaultStyle.strokeColor;
    ctx.fillStyle = brushSettings.isEraser 
      ? 'rgba(255, 0, 0, 0.1)' 
      : `${state.settings.defaultStyle.strokeColor}20`;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);

    ctx.beginPath();
    ctx.arc(brushPreview.x, brushPreview.y, brushSettings.size / 2, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.fill();

    // Draw crosshair
    const crossSize = 6;
    ctx.setLineDash([]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(brushPreview.x - crossSize, brushPreview.y);
    ctx.lineTo(brushPreview.x + crossSize, brushPreview.y);
    ctx.moveTo(brushPreview.x, brushPreview.y - crossSize);
    ctx.lineTo(brushPreview.x, brushPreview.y + crossSize);
    ctx.stroke();

    ctx.restore();
  }, [props.enabled, brushPreview, brushSettings, state.settings.defaultStyle]);

  // Get tool cursor
  const getCursor = useCallback(() => {
    if (!props.enabled) return 'default';
    return 'none'; // Hide cursor, we'll draw our own
  }, [props.enabled]);

  // Get tool status text
  const getStatusText = useCallback(() => {
    if (!props.enabled) return '';
    if (brushSettings.isEraser) {
      return isDrawing ? 'Erasing...' : 'Eraser mode - Click and drag to erase';
    }
    return isDrawing ? 'Drawing...' : 'Click and drag to paint';
  }, [props.enabled, isDrawing, brushSettings.isEraser]);

  // Handle brush setting changes
  const updateBrushSettings = useCallback((updates: Partial<typeof brushSettings>) => {
    actions.updateSettings({
      brushSettings: { ...brushSettings, ...updates }
    });
  }, [actions, brushSettings]);

  // Cleanup on unmount or disable
  useEffect(() => {
    if (!props.enabled && isDrawing) {
      cancelStroke();
    }
  }, [props.enabled, isDrawing, cancelStroke]);

  return {
    // Event handlers
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleKeyPress,
    
    // Tool state
    isDrawing,
    enabled: props.enabled || false,
    currentStroke,
    brushPreview,
    
    // Actions
    startStroke,
    addPoint,
    completeStroke,
    cancelStroke,
    updatePreview,
    updateBrushSettings,
    
    // Rendering
    renderCurrentStroke,
    renderBrushPreview,
    
    // Tool properties
    getCursor,
    getStatusText,
    
    // Settings
    brushSettings,
  } as const;
};

// React component for BrushTool with UI controls
const BrushTool: React.FC<BrushToolProps> = (props) => {
  const brushTool = useBrushTool(props);
  
  return (
    <div className="brush-tool-controls" style={{
      padding: '12px',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      backgroundColor: '#fafafa',
      marginBottom: '8px'
    }}>
      {/* Brush tool controls UI */}
      <div className="brush-settings" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div className="setting-group" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '12px', fontWeight: '500', color: '#555' }}>
            Size: {brushTool.brushSettings.size}px
          </label>
          <input
            type="range"
            min="1"
            max="50"
            value={brushTool.brushSettings.size}
            onChange={(e) => brushTool.updateBrushSettings({ size: parseInt(e.target.value) })}
            style={{ width: '100%' }}
          />
        </div>
        
        <div className="setting-group" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '12px', fontWeight: '500', color: '#555' }}>
            Opacity: {Math.round(brushTool.brushSettings.opacity * 100)}%
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={brushTool.brushSettings.opacity}
            onChange={(e) => brushTool.updateBrushSettings({ opacity: parseFloat(e.target.value) })}
            style={{ width: '100%' }}
          />
        </div>
        
        <div className="setting-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '6px', 
            fontSize: '12px', 
            cursor: 'pointer' 
          }}>
            <input
              type="checkbox"
              checked={brushTool.brushSettings.isEraser}
              onChange={(e) => brushTool.updateBrushSettings({ isEraser: e.target.checked })}
            />
            Eraser Mode
          </label>
        </div>
      </div>
      
      {brushTool.enabled && (
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
          {brushTool.getStatusText()}
        </div>
      )}
    </div>
  );
};

export default BrushTool;