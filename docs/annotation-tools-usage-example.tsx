// Example showing how the refactored BrushTool and PolygonTool can be used
// Both as React components and as hooks

import React, { useState } from 'react';
import { 
  BrushTool, 
  PolygonTool, 
  useBrushTool, 
  usePolygonTool,
  AnnotationProvider,
  type AnnotationShape 
} from '../ai-model-validation-platform/frontend/src/components/annotation';

// Example 1: Using tools as React components with UI controls
const AnnotationToolsPanel: React.FC = () => {
  const [activeType, setActiveType] = useState<'brush' | 'polygon'>('brush');
  const [shapes, setShapes] = useState<AnnotationShape[]>([]);

  const handleShapeComplete = (shape: AnnotationShape) => {
    setShapes(prev => [...prev, shape]);
    console.log('Shape created:', shape);
  };

  return (
    <div style={{ display: 'flex', gap: '16px' }}>
      <div style={{ width: '200px' }}>
        <h3>Tool Controls</h3>
        
        {activeType === 'brush' && (
          <BrushTool
            enabled={true}
            onStrokeComplete={handleShapeComplete}
          />
        )}
        
        {activeType === 'polygon' && (
          <PolygonTool
            enabled={true}
            onComplete={handleShapeComplete}
            onCancel={() => console.log('Polygon cancelled')}
          />
        )}
        
        <div style={{ marginTop: '16px' }}>
          <button 
            onClick={() => setActiveType('brush')}
            disabled={activeType === 'brush'}
          >
            Brush Tool
          </button>
          <button 
            onClick={() => setActiveType('polygon')}
            disabled={activeType === 'polygon'}
          >
            Polygon Tool
          </button>
        </div>
      </div>
      
      <div style={{ flex: 1 }}>
        <h3>Canvas Area</h3>
        <div style={{ 
          border: '1px solid #ccc', 
          minHeight: '400px', 
          backgroundColor: '#f9f9f9',
          position: 'relative'
        }}>
          {/* Canvas would be here */}
          <p>Shapes created: {shapes.length}</p>
        </div>
      </div>
    </div>
  );
};

// Example 2: Using tools as hooks for custom implementations
const CustomCanvas: React.FC = () => {
  const [brushEnabled, setBrushEnabled] = useState(false);
  const [polygonEnabled, setPolygonEnabled] = useState(false);
  
  // Use hooks to get tool functionality without UI
  const brushTool = useBrushTool({
    enabled: brushEnabled,
    onStrokeComplete: (shape) => {
      console.log('Brush stroke completed:', shape);
    }
  });

  const polygonTool = usePolygonTool({
    enabled: polygonEnabled,
    onComplete: (shape) => {
      console.log('Polygon completed:', shape);
    },
    onCancel: () => {
      console.log('Polygon cancelled');
    }
  });

  const handleCanvasMouseDown = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const point = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    };

    if (brushEnabled) {
      brushTool.handleMouseDown(point, event.nativeEvent as MouseEvent);
    } else if (polygonEnabled) {
      polygonTool.handleMouseClick(point, event.nativeEvent as MouseEvent);
    }
  };

  const handleCanvasMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const point = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    };

    if (brushEnabled) {
      brushTool.handleMouseMove(point, event.nativeEvent as MouseEvent);
    } else if (polygonEnabled) {
      polygonTool.handleMouseMove(point);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '16px' }}>
        <h3>Custom Canvas Implementation</h3>
        <button 
          onClick={() => {
            setBrushEnabled(true);
            setPolygonEnabled(false);
          }}
          style={{ 
            backgroundColor: brushEnabled ? '#4caf50' : '#e0e0e0',
            marginRight: '8px'
          }}
        >
          Brush Tool {brushTool.isDrawing ? '(Drawing...)' : ''}
        </button>
        <button 
          onClick={() => {
            setPolygonEnabled(true);
            setBrushEnabled(false);
          }}
          style={{ 
            backgroundColor: polygonEnabled ? '#4caf50' : '#e0e0e0'
          }}
        >
          Polygon Tool {polygonTool.isDrawing ? `(${polygonTool.currentPoints.length} points)` : ''}
        </button>
      </div>
      
      <div style={{ marginBottom: '8px', fontSize: '12px', color: '#666' }}>
        Status: {brushEnabled ? brushTool.getStatusText() : polygonTool.getStatusText()}
      </div>
      
      <canvas
        width={600}
        height={400}
        style={{ 
          border: '1px solid #ccc',
          cursor: brushEnabled ? brushTool.getCursor() : polygonTool.getCursor()
        }}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleCanvasMouseMove}
        onMouseUp={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const point = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
          };
          
          if (brushEnabled) {
            brushTool.handleMouseUp(point, event.nativeEvent as MouseEvent);
          }
        }}
        onDoubleClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const point = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
          };
          
          if (polygonEnabled) {
            polygonTool.handleDoubleClick(point, event.nativeEvent as MouseEvent);
          }
        }}
      />
    </div>
  );
};

// Main app component
const App: React.FC = () => {
  return (
    <AnnotationProvider>
      <div style={{ padding: '20px' }}>
        <h1>Refactored Annotation Tools Demo</h1>
        
        <div style={{ marginBottom: '32px' }}>
          <h2>1. Tools as React Components</h2>
          <AnnotationToolsPanel />
        </div>
        
        <div>
          <h2>2. Tools as Hooks (Custom Implementation)</h2>
          <CustomCanvas />
        </div>
      </div>
    </AnnotationProvider>
  );
};

export default App;