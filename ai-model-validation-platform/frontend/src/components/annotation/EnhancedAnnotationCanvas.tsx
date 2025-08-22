import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import { Box } from '@mui/material';
import { styled } from '@mui/material/styles';
import { useAnnotation } from './AnnotationManager';
import { AnnotationShape, Point, Rectangle, ResizeHandle, SelectionBox } from './types';

const CanvasContainer = styled(Box)({
  position: 'relative',
  width: '100%',
  height: '100%',
  overflow: 'hidden',
  cursor: 'crosshair',
  userSelect: 'none',
});

const Canvas = styled('canvas')({
  position: 'absolute',
  top: 0,
  left: 0,
  zIndex: 1,
});

const OverlayCanvas = styled('canvas')({
  position: 'absolute',
  top: 0,
  left: 0,
  zIndex: 2,
  pointerEvents: 'none',
});

interface EnhancedAnnotationCanvasProps {
  width: number;
  height: number;
  backgroundImage?: string;
  videoElement?: HTMLVideoElement;
  onShapeClick?: (shape: AnnotationShape, event: MouseEvent) => void;
  onCanvasClick?: (point: Point, event: MouseEvent) => void;
  onShapeChange?: (shapes: AnnotationShape[]) => void;
  disabled?: boolean;
}

const EnhancedAnnotationCanvas: React.FC<EnhancedAnnotationCanvasProps> = ({
  width,
  height,
  backgroundImage,
  videoElement,
  onShapeClick,
  onCanvasClick,
  onShapeChange,
  disabled = false,
}) => {
  const { state, actions } = useAnnotation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  
  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentPath, setCurrentPath] = useState<Point[]>([]);
  const [dragStart, setDragStart] = useState<Point | null>(null);
  const [selectionBox, setSelectionBox] = useState<SelectionBox>({
    x: 0, y: 0, width: 0, height: 0, visible: false
  });
  
  // Resize handles
  const [resizeHandles, setResizeHandles] = useState<ResizeHandle[]>([]);
  const [activeResizeHandle, setActiveResizeHandle] = useState<string | null>(null);
  
  // Pan and zoom
  const [isPanning, setIsPanning] = useState(false);
  const [lastPanPoint, setLastPanPoint] = useState<Point | null>(null);

  // Get mouse position relative to canvas
  const getMousePos = useCallback((event: MouseEvent): Point => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    
    const rect = canvas.getBoundingClientRect();
    const point = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
    
    return actions.inverseTransformPoint(point);
  }, [actions]);

  // Hit testing
  const hitTest = useCallback((point: Point): AnnotationShape | null => {
    for (let i = state.shapes.length - 1; i >= 0; i--) {
      const shape = state.shapes[i];
      if (!shape.visible) continue;
      
      // Simple bounding box hit test
      const bbox = shape.boundingBox;
      if (point.x >= bbox.x && point.x <= bbox.x + bbox.width &&
          point.y >= bbox.y && point.y <= bbox.y + bbox.height) {
        
        // More detailed hit test for polygons
        if (shape.type === 'polygon' && shape.points.length > 2) {
          if (pointInPolygon(point, shape.points)) {
            return shape;
          }
        } else if (shape.type === 'point') {
          const distance = Math.sqrt(
            Math.pow(point.x - shape.points[0].x, 2) + 
            Math.pow(point.y - shape.points[0].y, 2)
          );
          if (distance <= 5) return shape; // 5px tolerance for points
        } else {
          return shape; // Rectangle and brush strokes use bounding box
        }
      }
    }
    return null;
  }, [state.shapes]);

  // Point in polygon test
  const pointInPolygon = useCallback((point: Point, polygon: Point[]): boolean => {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      if (((polygon[i].y > point.y) !== (polygon[j].y > point.y)) &&
          (point.x < (polygon[j].x - polygon[i].x) * (point.y - polygon[i].y) / (polygon[j].y - polygon[i].y) + polygon[i].x)) {
        inside = !inside;
      }
    }
    return inside;
  }, []);

  // Generate resize handles for selected shapes
  const generateResizeHandles = useCallback((shapes: AnnotationShape[]): ResizeHandle[] => {
    if (shapes.length !== 1) return [];
    
    const shape = shapes[0];
    const bbox = shape.boundingBox;
    const handles: ResizeHandle[] = [];
    
    // Corner handles
    handles.push(
      { id: 'nw', x: bbox.x, y: bbox.y, cursor: 'nw-resize', type: 'corner' },
      { id: 'ne', x: bbox.x + bbox.width, y: bbox.y, cursor: 'ne-resize', type: 'corner' },
      { id: 'sw', x: bbox.x, y: bbox.y + bbox.height, cursor: 'sw-resize', type: 'corner' },
      { id: 'se', x: bbox.x + bbox.width, y: bbox.y + bbox.height, cursor: 'se-resize', type: 'corner' }
    );
    
    // Edge handles (only for rectangles)
    if (shape.type === 'rectangle') {
      handles.push(
        { id: 'n', x: bbox.x + bbox.width / 2, y: bbox.y, cursor: 'n-resize', type: 'edge' },
        { id: 's', x: bbox.x + bbox.width / 2, y: bbox.y + bbox.height, cursor: 's-resize', type: 'edge' },
        { id: 'w', x: bbox.x, y: bbox.y + bbox.height / 2, cursor: 'w-resize', type: 'edge' },
        { id: 'e', x: bbox.x + bbox.width, y: bbox.y + bbox.height / 2, cursor: 'e-resize', type: 'edge' }
      );
    }
    
    return handles;
  }, []);

  // Update resize handles when selection changes
  useEffect(() => {
    const selectedShapes = actions.getSelectedShapes();
    setResizeHandles(generateResizeHandles(selectedShapes));
  }, [state.selectedShapeIds, state.shapes, actions, generateResizeHandles]);

  // Mouse event handlers
  const handleMouseDown = useCallback((event: React.MouseEvent) => {
    if (disabled) return;
    
    const mouseEvent = event.nativeEvent;
    const point = getMousePos(mouseEvent);
    
    // Check if clicking on resize handle
    for (const handle of resizeHandles) {
      const handlePoint = actions.transformPoint(handle);
      const distance = Math.sqrt(
        Math.pow(point.x - handlePoint.x, 2) + 
        Math.pow(point.y - handlePoint.y, 2)
      );
      if (distance <= 5) {
        setActiveResizeHandle(handle.id);
        setDragStart(point);
        return;
      }
    }
    
    // Handle different tool types
    switch (state.activeToolId) {
      case 'select': {
        const hitShape = hitTest(point);
        if (hitShape) {
          if (!state.selectedShapeIds.includes(hitShape.id)) {
            actions.selectShapes([hitShape.id], mouseEvent.shiftKey);
          }
          onShapeClick?.(hitShape, mouseEvent);
          setDragStart(point);
        } else {
          if (!mouseEvent.shiftKey) {
            actions.clearSelection();
          }
          setSelectionBox({ x: point.x, y: point.y, width: 0, height: 0, visible: true });
          setDragStart(point);
        }
        break;
      }
      
      case 'rectangle': {
        setIsDrawing(true);
        setDragStart(point);
        setCurrentPath([point]);
        break;
      }
      
      case 'polygon': {
        if (isDrawing) {
          // Add point to current polygon
          setCurrentPath(prev => [...prev, point]);
        } else {
          // Start new polygon
          setIsDrawing(true);
          setCurrentPath([point]);
        }
        break;
      }
      
      case 'point': {
        const id = actions.createPoint(point);
        onCanvasClick?.(point, mouseEvent);
        break;
      }
      
      case 'brush': {
        setIsDrawing(true);
        setCurrentPath([point]);
        break;
      }
    }
  }, [
    disabled, getMousePos, resizeHandles, actions, state.activeToolId, state.selectedShapeIds,
    hitTest, onShapeClick, onCanvasClick, isDrawing
  ]);

  const handleMouseMove = useCallback((event: React.MouseEvent) => {
    if (disabled) return;
    
    const mouseEvent = event.nativeEvent;
    const point = getMousePos(mouseEvent);
    
    // Handle resize
    if (activeResizeHandle && dragStart) {
      const selectedShapes = actions.getSelectedShapes();
      if (selectedShapes.length === 1) {
        const shape = selectedShapes[0];
        const delta = { x: point.x - dragStart.x, y: point.y - dragStart.y };
        
        // Calculate new bounding box based on handle
        let newBbox = { ...shape.boundingBox };
        
        switch (activeResizeHandle) {
          case 'nw':
            newBbox.x += delta.x;
            newBbox.y += delta.y;
            newBbox.width -= delta.x;
            newBbox.height -= delta.y;
            break;
          case 'ne':
            newBbox.y += delta.y;
            newBbox.width += delta.x;
            newBbox.height -= delta.y;
            break;
          case 'sw':
            newBbox.x += delta.x;
            newBbox.width -= delta.x;
            newBbox.height += delta.y;
            break;
          case 'se':
            newBbox.width += delta.x;
            newBbox.height += delta.y;
            break;
          case 'n':
            newBbox.y += delta.y;
            newBbox.height -= delta.y;
            break;
          case 's':
            newBbox.height += delta.y;
            break;
          case 'w':
            newBbox.x += delta.x;
            newBbox.width -= delta.x;
            break;
          case 'e':
            newBbox.width += delta.x;
            break;
        }
        
        // Update shape with new bounding box
        const newPoints = shape.type === 'rectangle' 
          ? [
              { x: newBbox.x, y: newBbox.y },
              { x: newBbox.x + newBbox.width, y: newBbox.y },
              { x: newBbox.x + newBbox.width, y: newBbox.y + newBbox.height },
              { x: newBbox.x, y: newBbox.y + newBbox.height },
            ]
          : shape.points; // For other shapes, keep original points for now
        
        actions.updateShape(shape.id, {
          points: newPoints,
          boundingBox: newBbox,
        });
      }
      return;
    }
    
    // Handle selection box
    if (selectionBox.visible && dragStart) {
      const width = point.x - dragStart.x;
      const height = point.y - dragStart.y;
      setSelectionBox({
        x: width < 0 ? point.x : dragStart.x,
        y: height < 0 ? point.y : dragStart.y,
        width: Math.abs(width),
        height: Math.abs(height),
        visible: true,
      });
      return;
    }
    
    // Handle shape dragging
    if (dragStart && state.selectedShapeIds.length > 0 && state.activeToolId === 'select') {
      const delta = { x: point.x - dragStart.x, y: point.y - dragStart.y };
      actions.moveShapes(state.selectedShapeIds, delta);
      setDragStart(point);
      return;
    }
    
    // Handle drawing
    if (isDrawing && dragStart) {
      switch (state.activeToolId) {
        case 'rectangle':
          setCurrentPath([dragStart, point]);
          break;
        case 'brush':
          setCurrentPath(prev => [...prev, point]);
          break;
      }
    }
  }, [
    disabled, getMousePos, activeResizeHandle, dragStart, actions, selectionBox.visible,
    state.selectedShapeIds, state.activeToolId, isDrawing
  ]);

  const handleMouseUp = useCallback((event: React.MouseEvent) => {
    if (disabled) return;
    
    const mouseEvent = event.nativeEvent;
    const point = getMousePos(mouseEvent);
    
    // Clear resize handle
    if (activeResizeHandle) {
      setActiveResizeHandle(null);
      setDragStart(null);
      return;
    }
    
    // Handle selection box
    if (selectionBox.visible) {
      const selectedIds: string[] = [];
      for (const shape of state.shapes) {
        const bbox = shape.boundingBox;
        if (bbox.x >= selectionBox.x && 
            bbox.y >= selectionBox.y && 
            bbox.x + bbox.width <= selectionBox.x + selectionBox.width &&
            bbox.y + bbox.height <= selectionBox.y + selectionBox.height) {
          selectedIds.push(shape.id);
        }
      }
      actions.selectShapes(selectedIds, mouseEvent.shiftKey);
      setSelectionBox({ x: 0, y: 0, width: 0, height: 0, visible: false });
      setDragStart(null);
      return;
    }
    
    // Complete drawing operations
    if (isDrawing && currentPath.length > 0) {
      switch (state.activeToolId) {
        case 'rectangle':
          if (currentPath.length === 2 && dragStart) {
            actions.createRectangle(dragStart, point);
          }
          setIsDrawing(false);
          setCurrentPath([]);
          setDragStart(null);
          break;
          
        case 'brush':
          // Create brush stroke shape
          const xs = currentPath.map(p => p.x);
          const ys = currentPath.map(p => p.y);
          const x = Math.min(...xs);
          const y = Math.min(...ys);
          const width = Math.max(...xs) - x;
          const height = Math.max(...ys) - y;
          
          // TODO: Implement brush stroke creation
          setIsDrawing(false);
          setCurrentPath([]);
          break;
      }
    }
    
    // Handle polygon double-click to complete
    if (state.activeToolId === 'polygon' && currentPath.length > 2) {
      // Check for double-click (simplified)
      if (dragStart && Math.abs(point.x - dragStart.x) < 5 && Math.abs(point.y - dragStart.y) < 5) {
        actions.createPolygon(currentPath);
        setIsDrawing(false);
        setCurrentPath([]);
      }
    }
    
    setDragStart(null);
  }, [
    disabled, getMousePos, activeResizeHandle, selectionBox, state.shapes, state.activeToolId,
    actions, isDrawing, currentPath, dragStart
  ]);

  // Double-click handler for polygon completion
  const handleDoubleClick = useCallback((event: React.MouseEvent) => {
    if (disabled) return;
    
    if (state.activeToolId === 'polygon' && isDrawing && currentPath.length > 2) {
      actions.createPolygon(currentPath);
      setIsDrawing(false);
      setCurrentPath([]);
    }
  }, [disabled, state.activeToolId, isDrawing, currentPath, actions]);

  // Drawing function
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const overlayCanvas = overlayCanvasRef.current;
    if (!canvas || !overlayCanvas) return;
    
    const ctx = canvas.getContext('2d');
    const overlayCtx = overlayCanvas.getContext('2d');
    if (!ctx || !overlayCtx) return;
    
    // Clear canvases
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    
    // Apply transform
    const { scale, translateX, translateY } = state.canvasTransform;
    ctx.save();
    ctx.scale(scale, scale);
    ctx.translate(translateX / scale, translateY / scale);
    
    overlayCtx.save();
    overlayCtx.scale(scale, scale);
    overlayCtx.translate(translateX / scale, translateY / scale);
    
    // Draw background video frame if available
    if (videoElement && !videoElement.paused) {
      try {
        ctx.drawImage(videoElement, 0, 0, canvas.width / scale, canvas.height / scale);
      } catch (e) {
        // Ignore errors when video is not ready
      }
    }
    
    // Draw grid if enabled
    if (state.settings.showGrid) {
      const gridSize = state.settings.gridSize;
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width / scale; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height / scale);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height / scale; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width / scale, y);
        ctx.stroke();
      }
    }
    
    // Draw shapes
    state.shapes.forEach(shape => {
      if (!shape.visible) return;
      
      const isSelected = state.selectedShapeIds.includes(shape.id);
      const style = shape.style;
      
      ctx.strokeStyle = isSelected ? '#ff0000' : style.strokeColor;
      ctx.fillStyle = style.fillColor;
      ctx.lineWidth = isSelected ? style.strokeWidth + 1 : style.strokeWidth;
      ctx.globalAlpha = style.fillOpacity;
      
      switch (shape.type) {
        case 'rectangle':
          if (shape.points.length >= 4) {
            const bbox = shape.boundingBox;
            ctx.fillRect(bbox.x, bbox.y, bbox.width, bbox.height);
            ctx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);
          }
          break;
          
        case 'polygon':
          if (shape.points.length > 0) {
            ctx.beginPath();
            ctx.moveTo(shape.points[0].x, shape.points[0].y);
            for (let i = 1; i < shape.points.length; i++) {
              ctx.lineTo(shape.points[i].x, shape.points[i].y);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
          }
          break;
          
        case 'point':
          if (shape.points.length > 0) {
            const point = shape.points[0];
            ctx.beginPath();
            ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
          }
          break;
          
        case 'brush':
          if (shape.points.length > 1) {
            ctx.beginPath();
            ctx.moveTo(shape.points[0].x, shape.points[0].y);
            for (let i = 1; i < shape.points.length; i++) {
              ctx.lineTo(shape.points[i].x, shape.points[i].y);
            }
            ctx.stroke();
          }
          break;
      }
      
      ctx.globalAlpha = 1;
    });
    
    // Draw current drawing operation on overlay
    if (isDrawing && currentPath.length > 0) {
      overlayCtx.strokeStyle = state.settings.defaultStyle.strokeColor;
      overlayCtx.lineWidth = state.settings.defaultStyle.strokeWidth;
      overlayCtx.setLineDash([5, 5]);
      
      switch (state.activeToolId) {
        case 'rectangle':
          if (currentPath.length === 2) {
            const start = currentPath[0];
            const end = currentPath[1];
            const width = end.x - start.x;
            const height = end.y - start.y;
            overlayCtx.strokeRect(start.x, start.y, width, height);
          }
          break;
          
        case 'polygon':
          if (currentPath.length > 1) {
            overlayCtx.beginPath();
            overlayCtx.moveTo(currentPath[0].x, currentPath[0].y);
            for (let i = 1; i < currentPath.length; i++) {
              overlayCtx.lineTo(currentPath[i].x, currentPath[i].y);
            }
            overlayCtx.stroke();
            
            // Draw line to cursor if available
            // This would require tracking mouse position
          }
          break;
          
        case 'brush':
          if (currentPath.length > 1) {
            overlayCtx.beginPath();
            overlayCtx.moveTo(currentPath[0].x, currentPath[0].y);
            for (let i = 1; i < currentPath.length; i++) {
              overlayCtx.lineTo(currentPath[i].x, currentPath[i].y);
            }
            overlayCtx.stroke();
          }
          break;
      }
      
      overlayCtx.setLineDash([]);
    }
    
    // Draw selection box
    if (selectionBox.visible) {
      overlayCtx.strokeStyle = '#0066cc';
      overlayCtx.fillStyle = 'rgba(0, 102, 204, 0.1)';
      overlayCtx.lineWidth = 1;
      overlayCtx.setLineDash([3, 3]);
      overlayCtx.fillRect(selectionBox.x, selectionBox.y, selectionBox.width, selectionBox.height);
      overlayCtx.strokeRect(selectionBox.x, selectionBox.y, selectionBox.width, selectionBox.height);
      overlayCtx.setLineDash([]);
    }
    
    // Draw resize handles
    resizeHandles.forEach(handle => {
      overlayCtx.fillStyle = '#ffffff';
      overlayCtx.strokeStyle = '#0066cc';
      overlayCtx.lineWidth = 1;
      const size = 6;
      overlayCtx.fillRect(handle.x - size / 2, handle.y - size / 2, size, size);
      overlayCtx.strokeRect(handle.x - size / 2, handle.y - size / 2, size, size);
    });
    
    ctx.restore();
    overlayCtx.restore();
  }, [
    state.shapes, state.selectedShapeIds, state.canvasTransform, state.settings,
    state.activeToolId, videoElement, isDrawing, currentPath, selectionBox, resizeHandles
  ]);

  // Animation loop
  useEffect(() => {
    let animationFrame: number;
    
    const animate = () => {
      draw();
      animationFrame = requestAnimationFrame(animate);
    };
    
    animationFrame = requestAnimationFrame(animate);
    
    return () => {
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [draw]);

  // Update canvas size
  useEffect(() => {
    const canvas = canvasRef.current;
    const overlayCanvas = overlayCanvasRef.current;
    if (!canvas || !overlayCanvas) return;
    
    canvas.width = width;
    canvas.height = height;
    overlayCanvas.width = width;
    overlayCanvas.height = height;
  }, [width, height]);

  // Set cursor based on active tool and hover state
  const canvasCursor = useMemo(() => {
    if (activeResizeHandle) {
      const handle = resizeHandles.find(h => h.id === activeResizeHandle);
      return handle ? handle.cursor : 'default';
    }
    
    switch (state.activeToolId) {
      case 'select':
        return 'default';
      case 'rectangle':
      case 'polygon':
        return 'crosshair';
      case 'brush':
        return 'url("data:image/svg+xml;charset=utf8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'20\' height=\'20\' viewBox=\'0 0 20 20\'%3E%3Ccircle cx=\'10\' cy=\'10\' r=\'8\' stroke=\'black\' stroke-width=\'2\' fill=\'none\'/%3E%3C/svg%3E") 10 10, crosshair';
      case 'point':
        return 'pointer';
      default:
        return 'default';
    }
  }, [state.activeToolId, activeResizeHandle, resizeHandles]);

  return (
    <CanvasContainer
      style={{ cursor: canvasCursor }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      <Canvas ref={canvasRef} />
      <OverlayCanvas ref={overlayCanvasRef} />
    </CanvasContainer>
  );
};

export default EnhancedAnnotationCanvas;