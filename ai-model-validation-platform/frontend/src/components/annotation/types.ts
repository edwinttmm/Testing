// Enhanced Annotation System Types
import { VRUType } from '../../services/types';

export interface Point {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface Rectangle extends Point, Size {}

export interface AnnotationShape {
  id: string;
  type: 'rectangle' | 'polygon' | 'brush' | 'point';
  points: Point[];
  boundingBox: Rectangle;
  style: AnnotationStyle;
  label?: string;
  confidence?: number;
  selected?: boolean;
  visible?: boolean;
  locked?: boolean;
}

export interface AnnotationStyle {
  strokeColor: string;
  fillColor: string;
  strokeWidth: number;
  fillOpacity: number;
  dashArray?: number[];
}

export interface DrawingTool {
  id: string;
  name: string;
  type: 'rectangle' | 'polygon' | 'brush' | 'point' | 'select';
  icon?: React.ReactNode;
  cursor: string;
  hotkey?: string;
  isActive?: boolean;
}

export interface AnnotationState {
  shapes: AnnotationShape[];
  selectedShapeIds: string[];
  activeToolId: string;
  isDrawing: boolean;
  clipboard: AnnotationShape[];
  canvasTransform: CanvasTransform;
  settings: AnnotationSettings;
}

export interface CanvasTransform {
  scale: number;
  translateX: number;
  translateY: number;
}

export interface AnnotationSettings {
  showGrid: boolean;
  snapToGrid: boolean;
  gridSize: number;
  enableCrosshair: boolean;
  defaultStyle: AnnotationStyle;
  brushSettings: BrushSettings;
}

export interface BrushSettings {
  size: number;
  hardness: number;
  opacity: number;
  isEraser: boolean;
}

export interface AnnotationAction {
  id: string;
  type: 'create' | 'update' | 'delete' | 'move' | 'resize' | 'select';
  timestamp: number;
  description: string;
  before?: AnnotationShape | AnnotationShape[];
  after?: AnnotationShape | AnnotationShape[];
  shapeIds: string[];
}

export interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  description: string;
  action: () => void;
}

export interface ContextMenuItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  disabled?: boolean;
  separator?: boolean;
  action: () => void;
}

export interface SelectionBox extends Rectangle {
  visible: boolean;
}

export interface ResizeHandle {
  id: string;
  x: number;
  y: number;
  cursor: string;
  type: 'corner' | 'edge' | 'rotate';
}

export interface AnnotationEvent {
  type: string;
  target?: AnnotationShape;
  point?: Point;
  originalEvent?: MouseEvent | KeyboardEvent;
  preventDefault?: () => void;
}

export interface ZoomPanState {
  scale: number;
  minScale: number;
  maxScale: number;
  translateX: number;
  translateY: number;
  canvasSize: Size;
  contentSize: Size;
}

export interface BrushStroke {
  id: string;
  points: Point[];
  style: AnnotationStyle & BrushSettings;
  timestamp: number;
}

// Label Studio compatibility types
export interface LabelStudioRegion {
  id: string;
  type: string;
  value: Record<string, unknown>;
  results: Record<string, unknown>[];
  meta?: Record<string, unknown>;
}

export interface LabelStudioTask {
  id: string;
  data: Record<string, unknown>;
  annotations: LabelStudioAnnotation[];
}

export interface LabelStudioAnnotation {
  id: string;
  created_username?: string;
  created_ago?: string;
  result: LabelStudioRegion[];
  task?: number;
  completed_by?: number;
  was_cancelled?: boolean;
  ground_truth?: boolean;
}

// Integration with existing Ground Truth types
export interface EnhancedGroundTruthAnnotation {
  id: string;
  videoId: string;
  frameNumber: number;
  timestamp: number;
  shapes: AnnotationShape[];
  vruType: VRUType;
  confidence: number;
  validated: boolean;
  notes?: string;
  createdAt: string;
  updatedAt?: string;
}