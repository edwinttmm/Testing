import React, { useState, useCallback, useRef } from 'react';
import { Point, AnnotationShape, ResizeHandle, SelectionBox } from '../types';
import { useAnnotation } from '../AnnotationManager';

interface SelectionToolProps {
  onSelectionChange?: (shapes: AnnotationShape[]) => void;
  enabled?: boolean;
}

// Hook that provides selection tool functionality
export const useSelectionTool = ({
  onSelectionChange,
  enabled = false,
}: SelectionToolProps) => {
  const { state, actions } = useAnnotation();
  
  // Selection state
  const [dragState, setDragState] = useState<{
    type: 'none' | 'select' | 'move' | 'resize';
    startPoint: Point;
    activeHandle?: string;
  }>({ type: 'none', startPoint: { x: 0, y: 0 } });
  
  const [selectionBox, setSelectionBox] = useState<SelectionBox>({
    x: 0, y: 0, width: 0, height: 0, visible: false
  });
  
  const [resizeHandles, setResizeHandles] = useState<ResizeHandle[]>([]);

  const dragStartShapesRef = useRef<AnnotationShape[]>([]);

  const selectedShapes = actions.getSelectedShapes();

  // Hit testing
  const hitTest = useCallback((point: Point): AnnotationShape | null => {
    // Test in reverse order (top to bottom)
    for (let i = state.shapes.length - 1; i >= 0; i--) {
      const shape = state.shapes[i];
      if (!shape.visible || shape.locked) continue;
      
      if (isPointInShape(point, shape)) {
        return shape;
      }
    }
    return null;
  }, [state.shapes]);

  // Point in shape testing
  const isPointInShape = useCallback((point: Point, shape: AnnotationShape): boolean => {
    const bbox = shape.boundingBox;
    
    // Quick bounding box test
    if (point.x < bbox.x || point.x > bbox.x + bbox.width ||
        point.y < bbox.y || point.y > bbox.y + bbox.height) {
      return false;
    }
    
    // Detailed tests for different shapes
    switch (shape.type) {
      case 'rectangle':
        return true; // Already passed bounding box test
        
      case 'polygon':
        return isPointInPolygon(point, shape.points);
        
      case 'point':
        const distance = Math.sqrt(
          Math.pow(point.x - shape.points[0].x, 2) + 
          Math.pow(point.y - shape.points[0].y, 2)
        );
        return distance <= 8; // 8px tolerance for points
        
      case 'brush':
        // For brush strokes, check distance to path
        return isPointNearPath(point, shape.points, shape.style.strokeWidth || 5);
        
      default:
        return true;
    }
  }, []);

  // Point in polygon test
  const isPointInPolygon = useCallback((point: Point, polygon: Point[]): boolean => {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      if (((polygon[i].y > point.y) !== (polygon[j].y > point.y)) &&
          (point.x < (polygon[j].x - polygon[i].x) * (point.y - polygon[i].y) / (polygon[j].y - polygon[i].y) + polygon[i].x)) {
        inside = !inside;
      }
    }
    return inside;
  }, []);

  // Point near path test for brush strokes
  const isPointNearPath = useCallback((point: Point, path: Point[], tolerance: number): boolean => {
    for (let i = 1; i < path.length; i++) {
      const distance = distanceToLineSegment(point, path[i - 1], path[i]);
      if (distance <= tolerance) {
        return true;
      }
    }
    return false;
  }, []);

  // Distance from point to line segment
  const distanceToLineSegment = useCallback((point: Point, lineStart: Point, lineEnd: Point): number => {
    const A = point.x - lineStart.x;
    const B = point.y - lineStart.y;
    const C = lineEnd.x - lineStart.x;
    const D = lineEnd.y - lineStart.y;

    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    
    if (lenSq === 0) {
      // Line start and end are the same point
      return Math.sqrt(A * A + B * B);
    }
    
    let param = dot / lenSq;

    let xx, yy;
    if (param < 0) {
      xx = lineStart.x;
      yy = lineStart.y;
    } else if (param > 1) {
      xx = lineEnd.x;
      yy = lineEnd.y;
    } else {
      xx = lineStart.x + param * C;
      yy = lineStart.y + param * D;
    }

    const dx = point.x - xx;
    const dy = point.y - yy;
    return Math.sqrt(dx * dx + dy * dy);
  }, []);

  // Generate resize handles for selected shapes
  const generateResizeHandles = useCallback((): ResizeHandle[] => {
    if (selectedShapes.length !== 1) return [];
    
    const shape = selectedShapes[0];
    if (shape.locked) return [];
    
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
  }, [selectedShapes]);

  // Update resize handles when selection changes
  React.useEffect(() => {
    setResizeHandles(generateResizeHandles());
    onSelectionChange?.(selectedShapes);
  }, [selectedShapes, generateResizeHandles, onSelectionChange]);

  // Hit test resize handles
  const hitTestHandle = useCallback((point: Point): ResizeHandle | null => {
    for (const handle of resizeHandles) {
      const distance = Math.sqrt(
        Math.pow(point.x - handle.x, 2) + 
        Math.pow(point.y - handle.y, 2)
      );
      if (distance <= 6) { // 6px tolerance for handles
        return handle;
      }
    }
    return null;
  }, [resizeHandles]);

  // Start drag operation
  const startDrag = useCallback((point: Point, event: MouseEvent) => {
    if (!enabled) return;

    // Check for resize handle first
    const handle = hitTestHandle(point);
    if (handle) {
      setDragState({
        type: 'resize',
        startPoint: point,
        activeHandle: handle.id,
      });
      dragStartShapesRef.current = [...selectedShapes];
      return;
    }

    // Check for shape hit
    const hitShape = hitTest(point);
    if (hitShape) {
      // If clicking on unselected shape, select it
      if (!state.selectedShapeIds.includes(hitShape.id)) {
        actions.selectShapes([hitShape.id], event.shiftKey);
      }
      
      // Start move operation
      setDragState({
        type: 'move',
        startPoint: point,
      });
      dragStartShapesRef.current = actions.getSelectedShapes();
      return;
    }

    // Start selection box
    if (!event.shiftKey) {
      actions.clearSelection();
    }
    
    setSelectionBox({ x: point.x, y: point.y, width: 0, height: 0, visible: true });
    setDragState({
      type: 'select',
      startPoint: point,
    });
  }, [enabled, hitTestHandle, hitTest, selectedShapes, state.selectedShapeIds, actions]);

  // Update drag operation
  const updateDrag = useCallback((point: Point) => {
    if (!enabled || dragState.type === 'none') return;

    const delta = {
      x: point.x - dragState.startPoint.x,
      y: point.y - dragState.startPoint.y,
    };

    switch (dragState.type) {
      case 'select':
        // Update selection box
        const width = delta.x;
        const height = delta.y;
        setSelectionBox({
          x: width < 0 ? point.x : dragState.startPoint.x,
          y: height < 0 ? point.y : dragState.startPoint.y,
          width: Math.abs(width),
          height: Math.abs(height),
          visible: true,
        });
        break;

      case 'move':
        // Move selected shapes
        if (selectedShapes.length > 0) {
          actions.moveShapes(selectedShapes.map(s => s.id), delta);
        }
        break;

      case 'resize':
        // Resize shape
        if (selectedShapes.length === 1 && dragState.activeHandle) {
          resizeShape(selectedShapes[0], dragState.activeHandle, delta);
        }
        break;
    }
  }, [enabled, dragState, selectedShapes, actions]);

  // Resize shape based on handle
  const resizeShape = useCallback((shape: AnnotationShape, handleId: string, delta: Point) => {
    const originalShape = dragStartShapesRef.current[0];
    if (!originalShape) return;

    let newBbox = { ...originalShape.boundingBox };
    
    switch (handleId) {
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

    // Ensure minimum size
    const minSize = 10;
    if (newBbox.width < minSize || newBbox.height < minSize) {
      return;
    }

    // Update shape points for rectangle
    let newPoints = shape.points;
    if (shape.type === 'rectangle') {
      newPoints = [
        { x: newBbox.x, y: newBbox.y },
        { x: newBbox.x + newBbox.width, y: newBbox.y },
        { x: newBbox.x + newBbox.width, y: newBbox.y + newBbox.height },
        { x: newBbox.x, y: newBbox.y + newBbox.height },
      ];
    }

    actions.updateShape(shape.id, {
      points: newPoints,
      boundingBox: newBbox,
    });
  }, [actions]);

  // End drag operation
  const endDrag = useCallback((_point: Point, event: MouseEvent) => {
    if (!enabled || dragState.type === 'none') return;

    switch (dragState.type) {
      case 'select':
        // Complete selection box
        const shapesInBox = state.shapes.filter(shape => {
          const bbox = shape.boundingBox;
          return bbox.x >= selectionBox.x &&
                 bbox.y >= selectionBox.y &&
                 bbox.x + bbox.width <= selectionBox.x + selectionBox.width &&
                 bbox.y + bbox.height <= selectionBox.y + selectionBox.height;
        });
        
        if (shapesInBox.length > 0) {
          actions.selectShapes(shapesInBox.map(s => s.id), event.shiftKey);
        }
        
        setSelectionBox({ x: 0, y: 0, width: 0, height: 0, visible: false });
        break;

      case 'move':
      case 'resize':
        // Operations already applied during drag
        break;
    }

    setDragState({ type: 'none', startPoint: { x: 0, y: 0 } });
    dragStartShapesRef.current = [];
  }, [enabled, dragState.type, state.shapes, selectionBox, actions]);

  // Handle keyboard events
  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    if (!enabled) return;

    switch (event.key) {
      case 'Delete':
      case 'Backspace':
        if (selectedShapes.length > 0) {
          actions.deleteShapes(selectedShapes.map(s => s.id));
        }
        break;
      case 'Escape':
        actions.clearSelection();
        setSelectionBox({ x: 0, y: 0, width: 0, height: 0, visible: false });
        break;
    }
  }, [enabled, selectedShapes, actions]);

  // Render selection indicators
  const renderSelection = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!enabled) return;

    ctx.save();

    // Render selection box
    if (selectionBox.visible) {
      ctx.strokeStyle = '#0066cc';
      ctx.fillStyle = 'rgba(0, 102, 204, 0.1)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      
      ctx.fillRect(selectionBox.x, selectionBox.y, selectionBox.width, selectionBox.height);
      ctx.strokeRect(selectionBox.x, selectionBox.y, selectionBox.width, selectionBox.height);
    }

    // Render resize handles
    resizeHandles.forEach(handle => {
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#0066cc';
      ctx.lineWidth = 1;
      ctx.setLineDash([]);
      
      const size = 8;
      const half = size / 2;
      
      ctx.fillRect(handle.x - half, handle.y - half, size, size);
      ctx.strokeRect(handle.x - half, handle.y - half, size, size);
    });

    ctx.restore();
  }, [enabled, selectionBox, resizeHandles]);

  // Get cursor for current state
  const getCursor = useCallback((point: Point) => {
    if (!enabled) return 'default';

    // Check for resize handle
    const handle = hitTestHandle(point);
    if (handle) {
      return handle.cursor;
    }

    // Check for shape hit
    const hitShape = hitTest(point);
    if (hitShape) {
      return 'move';
    }

    return 'default';
  }, [enabled, hitTestHandle, hitTest]);

  // Get status text
  const getStatusText = useCallback(() => {
    if (!enabled) return '';
    
    const count = selectedShapes.length;
    if (count === 0) {
      return 'Click to select shapes, drag to select multiple';
    }
    
    switch (dragState.type) {
      case 'move':
        return `Moving ${count} shape${count !== 1 ? 's' : ''}`;
      case 'resize':
        return 'Resizing shape';
      case 'select':
        return 'Selecting shapes...';
      default:
        return `${count} shape${count !== 1 ? 's' : ''} selected`;
    }
  }, [enabled, selectedShapes.length, dragState.type]);

  // Return tool interface
  return {
    enabled,
    isActive: dragState.type !== 'none',
    cursor: getCursor,
    statusText: getStatusText(),
    selectedShapes,
    selectionBox,
    resizeHandles,
    
    // Event handlers
    handleMouseDown: startDrag,
    handleMouseMove: updateDrag,
    handleMouseUp: endDrag,
    handleKeyPress,
    
    // Actions
    clearSelection: actions.clearSelection,
    selectAll: () => actions.selectShapes(state.shapes.map(s => s.id)),
    
    // Rendering
    render: renderSelection,
    
    // State queries
    hasSelection: selectedShapes.length > 0,
    selectionCount: selectedShapes.length,
    isDragging: dragState.type !== 'none',
    dragType: dragState.type,
  } as const;
};

// Component that uses the selection tool hook
const SelectionTool: React.FC<SelectionToolProps> = () => {
  // The component now just provides a hook interface
  // Actual functionality is provided through useSelectionTool hook
  return (
    <div className="selection-tool" style={{ display: 'none' }}>
      {/* This component provides selection functionality through its hook */}
    </div>
  );
};

export default SelectionTool;