# Enhanced Annotation System - Label Studio Inspired

A comprehensive, Label Studio-inspired annotation system for the AI Model Validation Platform. This system provides advanced annotation capabilities with multi-tool support, keyboard shortcuts, undo/redo functionality, and professional-grade user interface.

## 🚀 Features

### Core Capabilities
- **Multiple Drawing Tools**: Rectangle, Polygon, Brush/Freehand, Point
- **Interactive Editing**: Resize handles, drag to move, multi-select
- **Keyboard Shortcuts**: Comprehensive hotkey system for fast annotation
- **Undo/Redo System**: Full history tracking with action-based undo/redo
- **Copy/Paste**: Cross-frame annotation copying
- **Zoom & Pan**: Canvas navigation with mouse wheel and pan controls
- **Context Menus**: Right-click operations for quick actions
- **Grid & Snap**: Optional grid overlay with snap-to-grid functionality

### Professional Features
- **Label Studio Compatibility**: Import/export Label Studio format
- **Brush Tool**: Variable size painting with eraser mode
- **Polygon Tool**: Click to create vertices, double-click to complete
- **Selection Tool**: Bounding box selection with multi-select support
- **History Panel**: Visual history with action descriptions
- **Settings Panel**: Customizable tool settings and preferences

### Integration Features
- **Backward Compatibility**: Works with existing VideoAnnotationPlayer
- **Video Frame Sync**: Annotations tied to video frames
- **VRU Type Support**: Full support for pedestrian, cyclist, etc.
- **Export Formats**: JSON, COCO, YOLO, Pascal VOC support
- **Real-time Updates**: Live annotation updates during video playback

## 📦 Components

### Core Components

#### `EnhancedAnnotationCanvas`
- Main annotation canvas with drawing capabilities
- Multi-tool support with tool-specific cursors
- Real-time rendering with optimized drawing loops
- Hit testing and selection management

#### `AnnotationToolbar` 
- Label Studio-inspired toolbar
- Tool selection with visual feedback
- Style controls (color, stroke width, opacity)
- Shape management panel

#### `AnnotationManager`
- Centralized state management with React Context
- Action-based state updates
- History tracking and undo/redo
- Shape manipulation utilities

#### `KeyboardShortcuts`
- Comprehensive keyboard shortcut system
- Tool switching (V, R, P, B, T)
- Edit operations (Ctrl+Z, Ctrl+Y, Ctrl+C, Ctrl+V)
- Frame navigation (Arrow keys, Space)
- Help dialog with shortcut reference

#### `ContextMenu`
- Right-click context menu
- Shape-specific actions
- Label assignment shortcuts
- Conversion between shape types

#### `ZoomPanControls`
- Canvas zoom and pan controls
- Mouse wheel zoom with Ctrl modifier
- Pan with Alt+drag or middle mouse
- Zoom to fit and actual size

#### `AnnotationHistory`
- Visual history panel
- Action descriptions with timestamps
- Click to jump to any point in history
- Memory management with configurable limits

### Drawing Tools

#### `PolygonTool`
- Click to add vertices
- Double-click or Enter to complete
- Backspace to remove last vertex
- Visual feedback with preview lines

#### `BrushTool`
- Variable brush size and opacity
- Eraser mode support
- Pressure sensitivity (when available)
- Path smoothing algorithms

#### `SelectionTool`
- Rectangle selection box
- Multi-select with Shift+click
- Resize handles for selected shapes
- Drag to move multiple shapes

## 🔧 Usage

### Basic Integration

```tsx
import { 
  EnhancedVideoAnnotationPlayer,
  AnnotationProvider 
} from './components/annotation';

// Basic usage with enhanced features
<EnhancedVideoAnnotationPlayer
  video={videoFile}
  annotations={annotations}
  annotationMode={true}
  onAnnotationCreate={handleCreate}
  onAnnotationUpdate={handleUpdate}
  onAnnotationDelete={handleDelete}
/>
```

### Advanced Integration

```tsx
import { 
  AnnotationProvider,
  EnhancedAnnotationCanvas,
  AnnotationToolbar,
  KeyboardShortcuts,
  useAnnotation
} from './components/annotation';

function CustomAnnotationInterface() {
  const { state, actions } = useAnnotation();
  
  return (
    <div className="annotation-interface">
      <AnnotationToolbar />
      <EnhancedAnnotationCanvas 
        width={800}
        height={600}
        videoElement={videoRef.current}
      />
      <KeyboardShortcuts 
        onFrameNavigate={handleFrameNav}
        onPlayPause={handlePlayPause}
      />
    </div>
  );
}

// Wrap with provider
<AnnotationProvider>
  <CustomAnnotationInterface />
</AnnotationProvider>
```

### Manual Tool Usage

```tsx
import { PolygonTool, BrushTool, SelectionTool } from './components/annotation';

// Use individual tools
const polygonTool = PolygonTool({
  enabled: true,
  onComplete: (shape) => console.log('Polygon created:', shape)
});

const brushTool = BrushTool({
  enabled: true,
  onStrokeComplete: (shape) => console.log('Brush stroke:', shape)
});
```

## ⌨️ Keyboard Shortcuts

### Tool Selection
- `V` - Select Tool
- `R` - Rectangle Tool  
- `P` - Polygon Tool
- `B` - Brush Tool
- `T` - Point Tool

### Edit Operations
- `Ctrl+Z` - Undo
- `Ctrl+Y` - Redo
- `Ctrl+C` - Copy
- `Ctrl+V` - Paste
- `Ctrl+X` - Cut
- `Ctrl+A` - Select All
- `Ctrl+D` - Duplicate
- `Delete` - Delete Selected
- `Escape` - Clear Selection

### Navigation
- `←/→` - Previous/Next Frame
- `Space` - Play/Pause
- `0` - Zoom to Fit
- `1` - Zoom 100%
- `+/-` - Zoom In/Out

### View Controls
- `G` - Toggle Grid
- `S` - Toggle Snap to Grid
- `H` - Hide/Show Selected
- `L` - Lock/Unlock Selected

### Label Assignment
- `Shift+1` - Pedestrian
- `Shift+2` - Cyclist
- `Shift+3` - Motorcyclist
- `Shift+4` - Wheelchair User
- `Shift+5` - Scooter Rider

## 🎨 Customization

### Tool Settings

```tsx
const customSettings = {
  showGrid: true,
  gridSize: 20,
  defaultStyle: {
    strokeColor: '#ff0000',
    fillColor: 'rgba(255, 0, 0, 0.1)',
    strokeWidth: 3,
  },
  brushSettings: {
    size: 15,
    opacity: 0.8,
    isEraser: false,
  }
};

<AnnotationProvider 
  initialShapes={shapes}
  onChange={handleShapeChange}
>
  <EnhancedAnnotationCanvas settings={customSettings} />
</AnnotationProvider>
```

### Custom Drawing Tools

```tsx
// Create custom tool following the tool interface
const CustomTool = ({ enabled, onComplete }) => {
  const { state, actions } = useAnnotation();
  
  // Tool implementation...
  
  return {
    enabled,
    cursor: 'crosshair',
    handleMouseDown: (point, event) => {
      // Handle mouse down
    },
    // ... other handlers
  };
};
```

## 🔄 Data Format

### Annotation Shape Format

```typescript
interface AnnotationShape {
  id: string;
  type: 'rectangle' | 'polygon' | 'brush' | 'point';
  points: Point[];
  boundingBox: Rectangle;
  style: AnnotationStyle;
  label?: string;
  confidence?: number;
  visible?: boolean;
  selected?: boolean;
  locked?: boolean;
}
```

### Label Studio Compatibility

```tsx
import { convertToLabelStudio, convertFromLabelStudio } from './components/annotation';

// Export to Label Studio format
const labelStudioData = convertToLabelStudio(shapes);

// Import from Label Studio format
const shapes = convertFromLabelStudio(labelStudioAnnotation);
```

## 🚀 Performance

### Optimizations
- **Canvas Rendering**: Optimized drawing loops with requestAnimationFrame
- **Hit Testing**: Spatial indexing for fast shape lookup
- **Memory Management**: Configurable history limits
- **Event Handling**: Debounced updates for smooth interaction
- **Shape Culling**: Only render visible shapes

### Best Practices
- Use `React.memo` for tool components
- Debounce rapid state updates
- Limit history size for large datasets
- Use shape visibility to improve performance
- Batch multiple operations when possible

## 🔧 Troubleshooting

### Common Issues

**Tools not responding**
- Check if annotation mode is enabled
- Verify tool is properly selected
- Ensure canvas has focus

**Performance issues**
- Reduce history size limit
- Hide unnecessary shapes
- Use canvas culling
- Optimize render loop frequency

**Keyboard shortcuts not working**
- Ensure no input fields are focused
- Check for conflicting browser shortcuts
- Verify KeyboardShortcuts component is rendered

### Debug Mode

```tsx
// Enable debug logging
<AnnotationProvider debug={true}>
  <EnhancedAnnotationCanvas />
</AnnotationProvider>
```

## 📚 API Reference

### Hook: `useAnnotation`

```typescript
const {
  state,      // Current annotation state
  actions: {
    addShape,           // Add new shape
    updateShape,        // Update existing shape
    deleteShapes,       // Delete shapes by IDs
    selectShapes,       // Select shapes
    clearSelection,     // Clear selection
    setActiveTool,      // Change active tool
    undo,              // Undo last action
    redo,              // Redo last undone action
    copyShapes,        // Copy shapes to clipboard
    pasteShapes,       // Paste from clipboard
    // ... more actions
  }
} = useAnnotation();
```

### Events

```typescript
interface AnnotationEvents {
  onShapeCreate: (shape: AnnotationShape) => void;
  onShapeUpdate: (shape: AnnotationShape) => void;
  onShapeDelete: (shapeId: string) => void;
  onSelectionChange: (shapes: AnnotationShape[]) => void;
  onToolChange: (toolId: string) => void;
}
```

## 🤝 Contributing

1. Follow TypeScript best practices
2. Add comprehensive tests for new features  
3. Update documentation for API changes
4. Follow existing code style and patterns
5. Test backward compatibility thoroughly

## 📄 License

Part of the AI Model Validation Platform - see main project license.