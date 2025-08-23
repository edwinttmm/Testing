// Enhanced Annotation System - Label Studio Inspired
// Main exports for the annotation system

import type {
  Point,
  Size,
  Rectangle,
  AnnotationShape,
  AnnotationStyle,
  DrawingTool,
  AnnotationState,
  CanvasTransform,
  AnnotationSettings,
  BrushSettings,
  AnnotationAction,
  KeyboardShortcut,
  ContextMenuItem,
  SelectionBox,
  ResizeHandle,
  AnnotationEvent,
  ZoomPanState,
  BrushStroke,
  LabelStudioRegion,
  LabelStudioTask,
  LabelStudioAnnotation,
  EnhancedGroundTruthAnnotation,
} from './types';

// Core components
export { default as EnhancedAnnotationCanvas } from './EnhancedAnnotationCanvas';
export { default as AnnotationToolbar } from './AnnotationToolbar';
export { default as KeyboardShortcuts } from './KeyboardShortcuts';
export { default as AnnotationHistory } from './AnnotationHistory';
export { default as ContextMenu } from './ContextMenu';
export { default as ZoomPanControls } from './ZoomPanControls';
export { default as EnhancedVideoAnnotationPlayer } from './EnhancedVideoAnnotationPlayer';

// State management
export { AnnotationProvider, useAnnotation } from './AnnotationManager';

// Drawing tools
export { default as PolygonTool, usePolygonTool } from './tools/PolygonTool';
export { default as BrushTool, useBrushTool } from './tools/BrushTool';
export { default as SelectionTool, useSelectionTool } from './tools/SelectionTool';

// Types
export type {
  Point,
  Size,
  Rectangle,
  AnnotationShape,
  AnnotationStyle,
  DrawingTool,
  AnnotationState,
  CanvasTransform,
  AnnotationSettings,
  BrushSettings,
  AnnotationAction,
  KeyboardShortcut,
  ContextMenuItem,
  SelectionBox,
  ResizeHandle,
  AnnotationEvent,
  ZoomPanState,
  BrushStroke,
  LabelStudioRegion,
  LabelStudioTask,
  LabelStudioAnnotation,
  EnhancedGroundTruthAnnotation,
} from './types';

// Utility functions
export const createAnnotationShape = (
  type: 'rectangle' | 'polygon' | 'brush' | 'point',
  points: Point[],
  style?: Partial<AnnotationStyle>
): AnnotationShape => {
  const xs = points.map(p => p.x);
  const ys = points.map(p => p.y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...ys);

  return {
    id: `${type}_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
    type,
    points,
    boundingBox: {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY,
    },
    style: {
      strokeColor: '#3498db',
      fillColor: 'rgba(52, 152, 219, 0.2)',
      strokeWidth: 2,
      fillOpacity: 0.2,
      ...style,
    },
    visible: true,
    selected: false,
  };
};

export const convertToLabelStudio = (shapes: AnnotationShape[]): LabelStudioAnnotation => {
  return {
    id: `annotation_${Date.now()}`,
    result: shapes.map(shape => ({
      id: shape.id,
      type: shape.type,
      value: {
        points: shape.points,
        width: (shape.boundingBox.width / 800) * 100, // Convert to percentage
        height: (shape.boundingBox.height / 600) * 100,
        x: (shape.boundingBox.x / 800) * 100,
        y: (shape.boundingBox.y / 600) * 100,
        rotation: 0,
        rectanglelabels: shape.label ? [shape.label] : [],
      },
      results: [],
    })),
  };
};

export const convertFromLabelStudio = (annotation: LabelStudioAnnotation): AnnotationShape[] => {
  return annotation.result.map(region => {
    // Type-safe value extraction
    const value = region.value as any; // temporary for migration
    const x = typeof value.x === 'number' ? value.x : 0;
    const y = typeof value.y === 'number' ? value.y : 0;
    const width = typeof value.width === 'number' ? value.width : 100;
    const height = typeof value.height === 'number' ? value.height : 100;
    
    return {
      id: region.id,
      type: region.type as 'rectangle' | 'polygon' | 'brush' | 'point',
      points: (value.points as Point[]) || [
        { x: x * 8, y: y * 6 },
        { x: (x + width) * 8, y: y * 6 },
        { x: (x + width) * 8, y: (y + height) * 6 },
        { x: x * 8, y: (y + height) * 6 },
      ],
      boundingBox: {
        x: x * 8,
        y: y * 6,
        width: width * 8,
        height: height * 6,
      },
      style: {
        strokeColor: '#3498db',
        fillColor: 'rgba(52, 152, 219, 0.2)',
        strokeWidth: 2,
        fillOpacity: 0.2,
      },
      label: value.rectanglelabels?.[0] || undefined,
      visible: true,
      selected: false,
    };
  });
};

// Default configurations
export const DEFAULT_ANNOTATION_SETTINGS = {
  showGrid: false,
  snapToGrid: false,
  gridSize: 10,
  enableCrosshair: true,
  defaultStyle: {
    strokeColor: '#3498db',
    fillColor: 'rgba(52, 152, 219, 0.2)',
    strokeWidth: 2,
    fillOpacity: 0.2,
  },
  brushSettings: {
    size: 10,
    hardness: 0.8,
    opacity: 0.7,
    isEraser: false,
  },
};

export const DEFAULT_DRAWING_TOOLS = [
  { id: 'select', name: 'Select', type: 'select' as const, hotkey: 'V' },
  { id: 'rectangle', name: 'Rectangle', type: 'rectangle' as const, hotkey: 'R' },
  { id: 'polygon', name: 'Polygon', type: 'polygon' as const, hotkey: 'P' },
  { id: 'brush', name: 'Brush', type: 'brush' as const, hotkey: 'B' },
  { id: 'point', name: 'Point', type: 'point' as const, hotkey: 'T' },
];

export const VRU_TYPE_COLORS = {
  pedestrian: '#2196f3',
  cyclist: '#4caf50',
  motorcyclist: '#ff9800',
  wheelchair_user: '#9c27b0',
  scooter_rider: '#ff5722',
} as const;