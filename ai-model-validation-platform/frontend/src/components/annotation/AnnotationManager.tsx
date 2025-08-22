import React, { createContext, useContext, useReducer, useCallback, useRef, useEffect } from 'react';
import {
  AnnotationState,
  AnnotationShape,
  AnnotationAction,
  DrawingTool,
  Point,
  Rectangle,
  CanvasTransform,
  AnnotationSettings,
  BrushSettings,
  AnnotationStyle,
} from './types';
// Generate unique IDs without external dependencies
const generateId = () => `${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;

// Default settings
const defaultSettings: AnnotationSettings = {
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

const defaultTransform: CanvasTransform = {
  scale: 1,
  translateX: 0,
  translateY: 0,
};

// Initial state
const initialState: AnnotationState = {
  shapes: [],
  selectedShapeIds: [],
  activeToolId: 'select',
  isDrawing: false,
  clipboard: [],
  canvasTransform: defaultTransform,
  settings: defaultSettings,
};

// Action types
type AnnotationActionType = 
  | { type: 'SET_SHAPES'; shapes: AnnotationShape[] }
  | { type: 'ADD_SHAPE'; shape: AnnotationShape }
  | { type: 'UPDATE_SHAPE'; id: string; updates: Partial<AnnotationShape> }
  | { type: 'DELETE_SHAPES'; ids: string[] }
  | { type: 'SELECT_SHAPES'; ids: string[]; append?: boolean }
  | { type: 'CLEAR_SELECTION' }
  | { type: 'SET_ACTIVE_TOOL'; toolId: string }
  | { type: 'SET_DRAWING'; isDrawing: boolean }
  | { type: 'COPY_SHAPES'; shapes: AnnotationShape[] }
  | { type: 'PASTE_SHAPES'; offset?: Point }
  | { type: 'MOVE_SHAPES'; ids: string[]; delta: Point }
  | { type: 'SET_TRANSFORM'; transform: Partial<CanvasTransform> }
  | { type: 'UPDATE_SETTINGS'; settings: Partial<AnnotationSettings> }
  | { type: 'UNDO' }
  | { type: 'REDO' }
  | { type: 'CLEAR_ALL' };

// Reducer
function annotationReducer(state: AnnotationState, action: AnnotationActionType): AnnotationState {
  switch (action.type) {
    case 'SET_SHAPES':
      return { ...state, shapes: action.shapes };

    case 'ADD_SHAPE':
      return { 
        ...state, 
        shapes: [...state.shapes, action.shape],
        selectedShapeIds: [action.shape.id]
      };

    case 'UPDATE_SHAPE':
      return {
        ...state,
        shapes: state.shapes.map(shape =>
          shape.id === action.id ? { ...shape, ...action.updates } : shape
        ),
      };

    case 'DELETE_SHAPES':
      return {
        ...state,
        shapes: state.shapes.filter(shape => !action.ids.includes(shape.id)),
        selectedShapeIds: state.selectedShapeIds.filter(id => !action.ids.includes(id)),
      };

    case 'SELECT_SHAPES':
      return {
        ...state,
        selectedShapeIds: action.append
          ? [...new Set([...state.selectedShapeIds, ...action.ids])]
          : action.ids,
      };

    case 'CLEAR_SELECTION':
      return { ...state, selectedShapeIds: [] };

    case 'SET_ACTIVE_TOOL':
      return { ...state, activeToolId: action.toolId };

    case 'SET_DRAWING':
      return { ...state, isDrawing: action.isDrawing };

    case 'COPY_SHAPES':
      return { ...state, clipboard: action.shapes };

    case 'PASTE_SHAPES':
      const offset = action.offset ?? { x: 10, y: 10 };
      const pastedShapes = state.clipboard.map(shape => ({
        ...shape,
        id: generateId(),
        points: shape.points.map(point => ({ x: point.x + offset.x, y: point.y + offset.y })),
        boundingBox: {
          ...shape.boundingBox,
          x: shape.boundingBox.x + offset.x,
          y: shape.boundingBox.y + offset.y,
        },
      }));
      return {
        ...state,
        shapes: [...state.shapes, ...pastedShapes],
        selectedShapeIds: pastedShapes.map(s => s.id),
      };

    case 'MOVE_SHAPES':
      return {
        ...state,
        shapes: state.shapes.map(shape =>
          action.ids.includes(shape.id)
            ? {
                ...shape,
                points: shape.points.map(point => ({ x: point.x + action.delta.x, y: point.y + action.delta.y })),
                boundingBox: {
                  ...shape.boundingBox,
                  x: shape.boundingBox.x + action.delta.x,
                  y: shape.boundingBox.y + action.delta.y,
                },
              }
            : shape
        ),
      };

    case 'SET_TRANSFORM':
      return {
        ...state,
        canvasTransform: { ...state.canvasTransform, ...action.transform },
      };

    case 'UPDATE_SETTINGS':
      return {
        ...state,
        settings: { ...state.settings, ...action.settings },
      };

    case 'CLEAR_ALL':
      return {
        ...state,
        shapes: [],
        selectedShapeIds: [],
        isDrawing: false,
      };

    default:
      return state;
  }
}

// Context
interface AnnotationContextType {
  state: AnnotationState;
  actions: {
    setShapes: (shapes: AnnotationShape[]) => void;
    addShape: (shape: AnnotationShape) => void;
    updateShape: (id: string, updates: Partial<AnnotationShape>) => void;
    deleteShapes: (ids: string[]) => void;
    selectShapes: (ids: string[], append?: boolean) => void;
    clearSelection: () => void;
    setActiveTool: (toolId: string) => void;
    setDrawing: (isDrawing: boolean) => void;
    copyShapes: (shapes: AnnotationShape[]) => void;
    pasteShapes: (offset?: Point) => void;
    moveShapes: (ids: string[], delta: Point) => void;
    setTransform: (transform: Partial<CanvasTransform>) => void;
    updateSettings: (settings: Partial<AnnotationSettings>) => void;
    undo: () => void;
    redo: () => void;
    clearAll: () => void;
    createRectangle: (start: Point, end: Point, style?: Partial<AnnotationStyle>) => string;
    createPolygon: (points: Point[], style?: Partial<AnnotationStyle>) => string;
    createPoint: (point: Point, style?: Partial<AnnotationStyle>) => string;
    getSelectedShapes: () => AnnotationShape[];
    getShapeById: (id: string) => AnnotationShape | undefined;
    getBoundingBoxForShapes: (ids: string[]) => Rectangle | null;
    transformPoint: (point: Point) => Point;
    inverseTransformPoint: (point: Point) => Point;
  };
}

const AnnotationContext = createContext<AnnotationContextType | null>(null);

export const useAnnotation = () => {
  const context = useContext(AnnotationContext);
  if (!context) {
    throw new Error('useAnnotation must be used within AnnotationProvider');
  }
  return context;
};

// Provider component
interface AnnotationProviderProps {
  children: React.ReactNode;
  initialShapes?: AnnotationShape[];
  onChange?: (shapes: AnnotationShape[]) => void;
}

export const AnnotationProvider: React.FC<AnnotationProviderProps> = ({
  children,
  initialShapes = [],
  onChange,
}) => {
  const [state, dispatch] = useReducer(annotationReducer, {
    ...initialState,
    shapes: initialShapes,
  });

  const historyRef = useRef<AnnotationAction[]>([]);
  const historyIndexRef = useRef(-1);
  const maxHistorySize = 100;

  // Add action to history
  const addToHistory = useCallback((action: AnnotationAction) => {
    const history = historyRef.current;
    const currentIndex = historyIndexRef.current;

    // Remove future history if we're not at the end
    if (currentIndex < history.length - 1) {
      historyRef.current = history.slice(0, currentIndex + 1);
    }

    // Add new action
    historyRef.current.push(action);

    // Limit history size
    if (historyRef.current.length > maxHistorySize) {
      historyRef.current = historyRef.current.slice(-maxHistorySize);
    }

    historyIndexRef.current = historyRef.current.length - 1;
  }, []);

  // Notify parent component of changes
  useEffect(() => {
    onChange?.(state.shapes);
  }, [state.shapes, onChange]);

  // Create action functions
  const actions = {
    setShapes: useCallback((shapes: AnnotationShape[]) => {
      dispatch({ type: 'SET_SHAPES', shapes });
    }, []),

    addShape: useCallback((shape: AnnotationShape) => {
      dispatch({ type: 'ADD_SHAPE', shape });
      addToHistory({
        id: generateId(),
        type: 'create',
        timestamp: Date.now(),
        description: `Created ${shape.type}`,
        after: shape,
        shapeIds: [shape.id],
      });
    }, [addToHistory]),

    updateShape: useCallback((id: string, updates: Partial<AnnotationShape>) => {
      const shape = state.shapes.find(s => s.id === id);
      if (shape) {
        dispatch({ type: 'UPDATE_SHAPE', id, updates });
        addToHistory({
          id: generateId(),
          type: 'update',
          timestamp: Date.now(),
          description: `Updated ${shape.type}`,
          before: shape,
          after: { ...shape, ...updates },
          shapeIds: [id],
        });
      }
    }, [state.shapes, addToHistory]),

    deleteShapes: useCallback((ids: string[]) => {
      const shapes = state.shapes.filter(s => ids.includes(s.id));
      dispatch({ type: 'DELETE_SHAPES', ids });
      addToHistory({
        id: generateId(),
        type: 'delete',
        timestamp: Date.now(),
        description: `Deleted ${ids.length} shape(s)`,
        before: shapes,
        shapeIds: ids,
      });
    }, [state.shapes, addToHistory]),

    selectShapes: useCallback((ids: string[], append = false) => {
      dispatch({ type: 'SELECT_SHAPES', ids, append });
    }, []),

    clearSelection: useCallback(() => {
      dispatch({ type: 'CLEAR_SELECTION' });
    }, []),

    setActiveTool: useCallback((toolId: string) => {
      dispatch({ type: 'SET_ACTIVE_TOOL', toolId });
    }, []),

    setDrawing: useCallback((isDrawing: boolean) => {
      dispatch({ type: 'SET_DRAWING', isDrawing });
    }, []),

    copyShapes: useCallback((shapes: AnnotationShape[]) => {
      dispatch({ type: 'COPY_SHAPES', shapes });
    }, []),

    pasteShapes: useCallback((offset?: Point) => {
      dispatch({ type: 'PASTE_SHAPES', offset: offset || { x: 10, y: 10 } });
      addToHistory({
        id: generateId(),
        type: 'create',
        timestamp: Date.now(),
        description: `Pasted ${state.clipboard.length} shape(s)`,
        after: state.clipboard,
        shapeIds: state.clipboard.map(s => s.id),
      });
    }, [state.clipboard, addToHistory]),

    moveShapes: useCallback((ids: string[], delta: Point) => {
      dispatch({ type: 'MOVE_SHAPES', ids, delta });
      addToHistory({
        id: generateId(),
        type: 'move',
        timestamp: Date.now(),
        description: `Moved ${ids.length} shape(s)`,
        shapeIds: ids,
      });
    }, [addToHistory]),

    setTransform: useCallback((transform: Partial<CanvasTransform>) => {
      dispatch({ type: 'SET_TRANSFORM', transform });
    }, []),

    updateSettings: useCallback((settings: Partial<AnnotationSettings>) => {
      dispatch({ type: 'UPDATE_SETTINGS', settings });
    }, []),

    undo: useCallback(() => {
      if (historyIndexRef.current >= 0) {
        historyIndexRef.current--;
        // TODO: Implement undo logic based on action history
        dispatch({ type: 'UNDO' });
      }
    }, []),

    redo: useCallback(() => {
      if (historyIndexRef.current < historyRef.current.length - 1) {
        historyIndexRef.current++;
        // TODO: Implement redo logic based on action history
        dispatch({ type: 'REDO' });
      }
    }, []),

    clearAll: useCallback(() => {
      dispatch({ type: 'CLEAR_ALL' });
      addToHistory({
        id: generateId(),
        type: 'delete',
        timestamp: Date.now(),
        description: 'Cleared all shapes',
        before: state.shapes,
        shapeIds: state.shapes.map(s => s.id),
      });
    }, [state.shapes, addToHistory]),

    // Utility functions
    createRectangle: useCallback((start: Point, end: Point, style?: Partial<AnnotationStyle>): string => {
      const id = generateId();
      const x = Math.min(start.x, end.x);
      const y = Math.min(start.y, end.y);
      const width = Math.abs(end.x - start.x);
      const height = Math.abs(end.y - start.y);

      const shape: AnnotationShape = {
        id,
        type: 'rectangle',
        points: [
          { x, y },
          { x: x + width, y },
          { x: x + width, y: y + height },
          { x, y: y + height },
        ],
        boundingBox: { x, y, width, height },
        style: { ...state.settings.defaultStyle, ...style },
      };

      dispatch({ type: 'ADD_SHAPE', shape });
      return id;
    }, [state.settings.defaultStyle]),

    createPolygon: useCallback((points: Point[], style?: Partial<AnnotationStyle>): string => {
      const id = generateId();
      const xs = points.map(p => p.x);
      const ys = points.map(p => p.y);
      const x = Math.min(...xs);
      const y = Math.min(...ys);
      const width = Math.max(...xs) - x;
      const height = Math.max(...ys) - y;

      const shape: AnnotationShape = {
        id,
        type: 'polygon',
        points,
        boundingBox: { x, y, width, height },
        style: { ...state.settings.defaultStyle, ...style },
      };

      dispatch({ type: 'ADD_SHAPE', shape });
      return id;
    }, [state.settings.defaultStyle]),

    createPoint: useCallback((point: Point, style?: Partial<AnnotationStyle>): string => {
      const id = generateId();
      const size = 10; // Point size

      const shape: AnnotationShape = {
        id,
        type: 'point',
        points: [point],
        boundingBox: { 
          x: point.x - size / 2, 
          y: point.y - size / 2, 
          width: size, 
          height: size 
        },
        style: { ...state.settings.defaultStyle, ...style },
      };

      dispatch({ type: 'ADD_SHAPE', shape });
      return id;
    }, [state.settings.defaultStyle]),

    getSelectedShapes: useCallback(() => {
      return state.shapes.filter(shape => state.selectedShapeIds.includes(shape.id));
    }, [state.shapes, state.selectedShapeIds]),

    getShapeById: useCallback((id: string) => {
      return state.shapes.find(shape => shape.id === id);
    }, [state.shapes]),

    getBoundingBoxForShapes: useCallback((ids: string[]): Rectangle | null => {
      const shapes = state.shapes.filter(s => ids.includes(s.id));
      if (shapes.length === 0) return null;

      const allPoints = shapes.flatMap(s => s.points);
      const xs = allPoints.map(p => p.x);
      const ys = allPoints.map(p => p.y);

      const x = Math.min(...xs);
      const y = Math.min(...ys);
      const maxX = Math.max(...xs);
      const maxY = Math.max(...ys);

      return {
        x,
        y,
        width: maxX - x,
        height: maxY - y,
      };
    }, [state.shapes]),

    transformPoint: useCallback((point: Point): Point => {
      const { scale, translateX, translateY } = state.canvasTransform;
      return {
        x: point.x * scale + translateX,
        y: point.y * scale + translateY,
      };
    }, [state.canvasTransform]),

    inverseTransformPoint: useCallback((point: Point): Point => {
      const { scale, translateX, translateY } = state.canvasTransform;
      return {
        x: (point.x - translateX) / scale,
        y: (point.y - translateY) / scale,
      };
    }, [state.canvasTransform]),
  };

  return (
    <AnnotationContext.Provider value={{ state, actions }}>
      {children}
    </AnnotationContext.Provider>
  );
};