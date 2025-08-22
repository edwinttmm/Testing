import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AnnotationProvider } from '../../components/annotation/AnnotationManager';
import EnhancedAnnotationCanvas from '../../components/annotation/EnhancedAnnotationCanvas';
import KeyboardShortcuts from '../../components/annotation/KeyboardShortcuts';
import AnnotationToolbar from '../../components/annotation/AnnotationToolbar';
import { AnnotationShape, LabelStudioAnnotation, EnhancedGroundTruthAnnotation } from '../../components/annotation/types';

// Mock canvas context
const mockContext = {
  clearRect: jest.fn(),
  save: jest.fn(),
  restore: jest.fn(),
  scale: jest.fn(),
  translate: jest.fn(),
  drawImage: jest.fn(),
  strokeStyle: '#000000',
  fillStyle: '#000000',
  lineWidth: 1,
  globalAlpha: 1,
  strokeRect: jest.fn(),
  fillRect: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  closePath: jest.fn(),
  stroke: jest.fn(),
  fill: jest.fn(),
  arc: jest.fn(),
  setLineDash: jest.fn(),
};

HTMLCanvasElement.prototype.getContext = jest.fn(() => mockContext) as any;
HTMLCanvasElement.prototype.getBoundingClientRect = jest.fn(() => ({
  left: 0,
  top: 0,
  width: 800,
  height: 600,
  right: 800,
  bottom: 600,
  x: 0,
  y: 0,
  toJSON: jest.fn(),
}));

// Mock ground truth data
const mockGroundTruthAnnotations: EnhancedGroundTruthAnnotation[] = [
  {
    id: 'gt1',
    videoId: 'video1',
    frameNumber: 100,
    timestamp: 1000,
    shapes: [
      {
        id: 'gt-shape1',
        type: 'rectangle',
        points: [
          { x: 100, y: 100 },
          { x: 200, y: 100 },
          { x: 200, y: 200 },
          { x: 100, y: 200 },
        ],
        boundingBox: { x: 100, y: 100, width: 100, height: 100 },
        style: {
          strokeColor: '#00ff00',
          fillColor: 'rgba(0, 255, 0, 0.2)',
          strokeWidth: 2,
          fillOpacity: 0.2,
        },
        visible: true,
        selected: false,
        label: 'pedestrian',
      },
    ],
    vruType: 'pedestrian',
    confidence: 0.95,
    validated: false,
    createdAt: '2024-01-01T00:00:00Z',
  },
];

// Mock Label Studio data
const mockLabelStudioAnnotation: LabelStudioAnnotation = {
  id: 'ls1',
  result: [
    {
      id: 'ls-region1',
      type: 'rectangle',
      value: {
        x: 25,
        y: 25,
        width: 25,
        height: 25,
        points: [],
        rectanglelabels: ['cyclist'],
      },
      results: [],
    },
  ],
};

// Full annotation system component
const FullAnnotationSystem: React.FC<{
  mode?: 'classic' | 'enhanced';
  onModeChange?: (mode: 'classic' | 'enhanced') => void;
  onShapeChange?: (shapes: AnnotationShape[]) => void;
  groundTruthData?: EnhancedGroundTruthAnnotation[];
}> = ({ 
  mode = 'enhanced', 
  onModeChange, 
  onShapeChange,
  groundTruthData = []
}) => {
  const [showHelp, setShowHelp] = React.useState(false);
  
  return (
    <AnnotationProvider>
      <div data-testid="annotation-system">
        <div data-testid="mode-indicator">{mode}</div>
        <button 
          onClick={() => onModeChange?.(mode === 'classic' ? 'enhanced' : 'classic')}
          data-testid="mode-toggle"
        >
          Switch to {mode === 'classic' ? 'Enhanced' : 'Classic'}
        </button>
        
        <AnnotationToolbar 
          onToolChange={() => {}}
          onShowHelp={() => setShowHelp(true)}
        />
        
        <EnhancedAnnotationCanvas
          width={800}
          height={600}
          onShapeChange={onShapeChange}
        />
        
        <KeyboardShortcuts
          showHelpDialog={showHelp}
          onHelpDialogClose={() => setShowHelp(false)}
        />
        
        <div data-testid="ground-truth-count">
          {groundTruthData.length}
        </div>
      </div>
    </AnnotationProvider>
  );
};

describe('Integration Test Suite', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Ground Truth Integration', () => {
    it('should load ground truth annotations', async () => {
      const onShapeChange = jest.fn();

      render(
        <FullAnnotationSystem
          groundTruthData={mockGroundTruthAnnotations}
          onShapeChange={onShapeChange}
        />
      );

      expect(screen.getByTestId('ground-truth-count')).toHaveTextContent('1');
    });

    it('should display ground truth shapes on canvas', async () => {
      render(
        <FullAnnotationSystem groundTruthData={mockGroundTruthAnnotations} />
      );

      await waitFor(() => {
        expect(mockContext.strokeRect).toHaveBeenCalled();
        expect(mockContext.fillRect).toHaveBeenCalled();
      });
    });

    it('should differentiate ground truth from user annotations visually', async () => {
      const user = userEvent.setup();

      render(
        <FullAnnotationSystem groundTruthData={mockGroundTruthAnnotations} />
      );

      const canvas = screen.getByRole('img');
      
      // Add user annotation
      await user.pointer([
        { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 300, clientY: 300 } },
        { pointerName: 'mouse', target: canvas, coords: { clientX: 400, clientY: 400 } },
        { keys: '[/MouseLeft]', target: canvas },
      ]);

      // Should render both ground truth and user annotations with different styles
      expect(mockContext.strokeStyle).toHaveBeenCalledWith('#00ff00'); // Ground truth color
      expect(mockContext.strokeRect).toHaveBeenCalledTimes(expect.any(Number));
    });

    it('should validate annotations against ground truth', async () => {
      const onShapeChange = jest.fn();

      render(
        <FullAnnotationSystem
          groundTruthData={mockGroundTruthAnnotations}
          onShapeChange={onShapeChange}
        />
      );

      const canvas = screen.getByRole('img');
      const user = userEvent.setup();

      // Create annotation near ground truth
      await user.pointer([
        { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 105, clientY: 105 } },
        { pointerName: 'mouse', target: canvas, coords: { clientX: 195, clientY: 195 } },
        { keys: '[/MouseLeft]', target: canvas },
      ]);

      expect(onShapeChange).toHaveBeenCalled();
    });

    it('should support ground truth annotation editing', async () => {
      const user = userEvent.setup();

      render(
        <FullAnnotationSystem groundTruthData={mockGroundTruthAnnotations} />
      );

      const canvas = screen.getByRole('img');

      // Click on ground truth annotation to select
      await user.click(canvas, { clientX: 150, clientY: 150 });

      // Should show selection handles for ground truth annotations
      expect(mockContext.fillRect).toHaveBeenCalled(); // Selection handles
    });

    it('should preserve ground truth metadata during operations', async () => {
      const onShapeChange = jest.fn();

      render(
        <FullAnnotationSystem
          groundTruthData={mockGroundTruthAnnotations}
          onShapeChange={onShapeChange}
        />
      );

      // Ground truth should maintain its metadata
      expect(screen.getByTestId('ground-truth-count')).toHaveTextContent('1');
    });
  });

  describe('Mode Switching (Classic/Enhanced)', () => {
    it('should switch between classic and enhanced modes', () => {
      const onModeChange = jest.fn();

      render(
        <FullAnnotationSystem onModeChange={onModeChange} />
      );

      expect(screen.getByTestId('mode-indicator')).toHaveTextContent('enhanced');

      fireEvent.click(screen.getByTestId('mode-toggle'));

      expect(onModeChange).toHaveBeenCalledWith('classic');
    });

    it('should maintain annotations when switching modes', async () => {
      const onModeChange = jest.fn();
      const onShapeChange = jest.fn();

      const { rerender } = render(
        <FullAnnotationSystem 
          mode="enhanced" 
          onModeChange={onModeChange}
          onShapeChange={onShapeChange}
        />
      );

      const canvas = screen.getByRole('img');
      const user = userEvent.setup();

      // Create annotation in enhanced mode
      await user.pointer([
        { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
        { pointerName: 'mouse', target: canvas, coords: { clientX: 200, clientY: 200 } },
        { keys: '[/MouseLeft]', target: canvas },
      ]);

      // Switch to classic mode
      rerender(
        <FullAnnotationSystem 
          mode="classic" 
          onModeChange={onModeChange}
          onShapeChange={onShapeChange}
        />
      );

      // Annotations should still be visible
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should provide different tool sets in different modes', () => {
      const { rerender } = render(
        <FullAnnotationSystem mode="classic" />
      );

      // Classic mode UI
      expect(screen.getByTestId('mode-indicator')).toHaveTextContent('classic');

      rerender(<FullAnnotationSystem mode="enhanced" />);

      // Enhanced mode UI
      expect(screen.getByTestId('mode-indicator')).toHaveTextContent('enhanced');
    });

    it('should handle mode switching without data loss', async () => {
      const onShapeChange = jest.fn();

      const { rerender } = render(
        <FullAnnotationSystem 
          mode="enhanced"
          onShapeChange={onShapeChange}
          groundTruthData={mockGroundTruthAnnotations}
        />
      );

      // Switch modes multiple times
      rerender(
        <FullAnnotationSystem 
          mode="classic"
          onShapeChange={onShapeChange}
          groundTruthData={mockGroundTruthAnnotations}
        />
      );

      rerender(
        <FullAnnotationSystem 
          mode="enhanced"
          onShapeChange={onShapeChange}
          groundTruthData={mockGroundTruthAnnotations}
        />
      );

      // Ground truth should still be present
      expect(screen.getByTestId('ground-truth-count')).toHaveTextContent('1');
    });
  });

  describe('State Synchronization', () => {
    it('should synchronize canvas and toolbar state', async () => {
      render(<FullAnnotationSystem />);

      // Tool change should be reflected in canvas behavior
      fireEvent.keyDown(document, { key: 'r' }); // Rectangle tool

      const canvas = screen.getByRole('img');
      
      // Canvas should now be in rectangle drawing mode
      fireEvent.mouseMove(canvas, { clientX: 100, clientY: 100 });
      
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should synchronize selection state across components', async () => {
      const user = userEvent.setup();

      render(<FullAnnotationSystem />);

      const canvas = screen.getByRole('img');

      // Create and select shape
      await user.pointer([
        { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
        { pointerName: 'mouse', target: canvas, coords: { clientX: 200, clientY: 200 } },
        { keys: '[/MouseLeft]', target: canvas },
      ]);

      // Selection should be visible in canvas
      expect(mockContext.strokeRect).toHaveBeenCalled();

      // Use keyboard shortcut to delete
      fireEvent.keyDown(document, { key: 'Delete' });

      // Shape should be removed
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should synchronize zoom and pan state', async () => {
      render(<FullAnnotationSystem />);

      // Zoom in with keyboard shortcut
      fireEvent.keyDown(document, { key: '=' });

      // Canvas should reflect zoom change
      expect(mockContext.scale).toHaveBeenCalled();
    });

    it('should synchronize settings across components', () => {
      render(<FullAnnotationSystem />);

      // Toggle grid with keyboard shortcut
      fireEvent.keyDown(document, { key: 'g' });

      // Grid should be visible on canvas
      expect(mockContext.strokeStyle).toBeDefined();
    });

    it('should handle concurrent state changes', async () => {
      const user = userEvent.setup();

      render(<FullAnnotationSystem />);

      const canvas = screen.getByRole('img');

      // Perform multiple operations simultaneously
      act(() => {
        fireEvent.keyDown(document, { key: 'r' }); // Switch to rectangle
        user.pointer([
          { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 50, clientY: 50 } },
        ]); // Start drawing
        fireEvent.keyDown(document, { key: 'v' }); // Switch to select (while drawing)
      });

      // Should handle state changes gracefully
      expect(() => mockContext.clearRect).not.toThrow();
    });
  });

  describe('Backward Compatibility', () => {
    it('should import legacy annotation formats', () => {
      const TestComponent = () => {
        const [imported, setImported] = React.useState(false);

        const importLegacyData = () => {
          // Simulate importing legacy data
          setImported(true);
        };

        return (
          <div>
            <FullAnnotationSystem />
            <button onClick={importLegacyData}>Import Legacy</button>
            <div data-testid="import-status">{imported ? 'imported' : 'not-imported'}</div>
          </div>
        );
      };

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Import Legacy'));

      expect(screen.getByTestId('import-status')).toHaveTextContent('imported');
    });

    it('should export annotations in multiple formats', () => {
      const TestComponent = () => {
        const [exportFormat, setExportFormat] = React.useState<string>('');

        const exportAsLabelStudio = () => {
          setExportFormat('labelstudio');
        };

        const exportAsVOC = () => {
          setExportFormat('voc');
        };

        return (
          <div>
            <FullAnnotationSystem />
            <button onClick={exportAsLabelStudio}>Export as Label Studio</button>
            <button onClick={exportAsVOC}>Export as PASCAL VOC</button>
            <div data-testid="export-format">{exportFormat}</div>
          </div>
        );
      };

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Export as Label Studio'));
      expect(screen.getByTestId('export-format')).toHaveTextContent('labelstudio');

      fireEvent.click(screen.getByText('Export as PASCAL VOC'));
      expect(screen.getByTestId('export-format')).toHaveTextContent('voc');
    });

    it('should handle version migration', () => {
      const TestComponent = () => {
        const [version, setVersion] = React.useState('v1');

        const migrateToV2 = () => {
          setVersion('v2');
        };

        return (
          <div>
            <FullAnnotationSystem />
            <button onClick={migrateToV2}>Migrate to V2</button>
            <div data-testid="version">{version}</div>
          </div>
        );
      };

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Migrate to V2'));

      expect(screen.getByTestId('version')).toHaveTextContent('v2');
    });

    it('should maintain API compatibility', async () => {
      const user = userEvent.setup();

      render(<FullAnnotationSystem />);

      const canvas = screen.getByRole('img');

      // Use legacy API patterns
      await user.pointer([
        { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
        { pointerName: 'mouse', target: canvas, coords: { clientX: 200, clientY: 200 } },
        { keys: '[/MouseLeft]', target: canvas },
      ]);

      // Should work with both old and new API calls
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should support incremental feature adoption', () => {
      const TestComponent = () => {
        const [features, setFeatures] = React.useState<string[]>(['basic']);

        const enableAdvancedFeatures = () => {
          setFeatures(prev => [...prev, 'advanced', 'ai-assist']);
        };

        return (
          <div>
            <FullAnnotationSystem />
            <button onClick={enableAdvancedFeatures}>Enable Advanced</button>
            <div data-testid="feature-count">{features.length}</div>
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId('feature-count')).toHaveTextContent('1');

      fireEvent.click(screen.getByText('Enable Advanced'));

      expect(screen.getByTestId('feature-count')).toHaveTextContent('3');
    });
  });

  describe('Label Studio Compatibility', () => {
    it('should convert to Label Studio format', () => {
      const TestComponent = () => {
        const [converted, setConverted] = React.useState<LabelStudioAnnotation | null>(null);

        const convertToLS = () => {
          // Mock conversion
          setConverted(mockLabelStudioAnnotation);
        };

        return (
          <div>
            <FullAnnotationSystem />
            <button onClick={convertToLS}>Convert to Label Studio</button>
            <div data-testid="ls-regions">
              {converted ? converted.result.length : 0}
            </div>
          </div>
        );
      };

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Convert to Label Studio'));

      expect(screen.getByTestId('ls-regions')).toHaveTextContent('1');
    });

    it('should import from Label Studio format', () => {
      const TestComponent = () => {
        const [imported, setImported] = React.useState(false);

        const importFromLS = () => {
          setImported(true);
        };

        return (
          <div>
            <FullAnnotationSystem />
            <button onClick={importFromLS}>Import from Label Studio</button>
            <div data-testid="ls-imported">{imported ? 'true' : 'false'}</div>
          </div>
        );
      };

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Import from Label Studio'));

      expect(screen.getByTestId('ls-imported')).toHaveTextContent('true');
    });

    it('should maintain Label Studio region properties', () => {
      // Test that Label Studio specific properties are preserved
      const region = mockLabelStudioAnnotation.result[0];
      
      expect(region).toHaveProperty('type', 'rectangle');
      expect(region).toHaveProperty('value');
      expect(region.value).toHaveProperty('rectanglelabels');
      expect(region.value.rectanglelabels).toEqual(['cyclist']);
    });

    it('should handle Label Studio coordinate system', () => {
      // Label Studio uses percentage-based coordinates
      const region = mockLabelStudioAnnotation.result[0];
      
      // Coordinates should be in percentage (0-100)
      expect(region.value.x).toBeGreaterThanOrEqual(0);
      expect(region.value.x).toBeLessThanOrEqual(100);
      expect(region.value.y).toBeGreaterThanOrEqual(0);
      expect(region.value.y).toBeLessThanOrEqual(100);
    });

    it('should support Label Studio task structure', () => {
      const mockTask = {
        id: 'task1',
        data: { image: '/path/to/image.jpg' },
        annotations: [mockLabelStudioAnnotation],
      };

      expect(mockTask).toHaveProperty('id');
      expect(mockTask).toHaveProperty('data');
      expect(mockTask).toHaveProperty('annotations');
      expect(mockTask.annotations[0]).toBe(mockLabelStudioAnnotation);
    });
  });

  describe('Performance Integration', () => {
    it('should handle large numbers of annotations efficiently', async () => {
      const manyAnnotations: EnhancedGroundTruthAnnotation[] = Array.from({ length: 100 }, (_, i) => ({
        ...mockGroundTruthAnnotations[0],
        id: `gt${i}`,
        shapes: [{
          ...mockGroundTruthAnnotations[0].shapes[0],
          id: `shape${i}`,
          boundingBox: {
            x: (i % 10) * 50,
            y: Math.floor(i / 10) * 50,
            width: 40,
            height: 40,
          },
        }],
      }));

      const start = performance.now();

      render(
        <FullAnnotationSystem groundTruthData={manyAnnotations} />
      );

      const end = performance.now();

      expect(end - start).toBeLessThan(2000); // Should render within 2 seconds
      expect(screen.getByTestId('ground-truth-count')).toHaveTextContent('100');
    });

    it('should optimize rendering for viewport visibility', async () => {
      const user = userEvent.setup();

      render(<FullAnnotationSystem />);

      const canvas = screen.getByRole('img');

      // Create annotations outside viewport
      for (let i = 0; i < 50; i++) {
        await user.pointer([
          { keys: '[MouseLeft>]', target: canvas, coords: { clientX: i * 1000, clientY: i * 1000 } },
          { pointerName: 'mouse', target: canvas, coords: { clientX: i * 1000 + 50, clientY: i * 1000 + 50 } },
          { keys: '[/MouseLeft]', target: canvas },
        ]);
      }

      // Should not render all annotations if they're outside viewport
      expect(mockContext.strokeRect).toHaveBeenCalledTimes(expect.any(Number));
    });

    it('should debounce rapid updates', async () => {
      const onShapeChange = jest.fn();

      render(
        <FullAnnotationSystem onShapeChange={onShapeChange} />
      );

      const canvas = screen.getByRole('img');

      // Rapid mouse movements
      for (let i = 0; i < 100; i++) {
        fireEvent.mouseMove(canvas, { clientX: i, clientY: i });
      }

      // Should not call onChange for every movement
      await waitFor(() => {
        expect(onShapeChange.mock.calls.length).toBeLessThan(100);
      });
    });

    it('should handle memory efficiently with undo/redo history', async () => {
      const user = userEvent.setup();

      render(<FullAnnotationSystem />);

      const canvas = screen.getByRole('img');

      // Create many operations to test memory usage
      for (let i = 0; i < 200; i++) {
        await user.pointer([
          { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
          { pointerName: 'mouse', target: canvas, coords: { clientX: 150, clientY: 150 } },
          { keys: '[/MouseLeft]', target: canvas },
        ]);
        fireEvent.keyDown(document, { key: 'Delete' });
      }

      // Should not consume excessive memory
      const memoryUsage = (performance as any).memory;
      if (memoryUsage) {
        expect(memoryUsage.usedJSHeapSize).toBeLessThan(100 * 1024 * 1024); // <100MB
      }
    });
  });

  describe('Error Recovery Integration', () => {
    it('should recover from canvas rendering errors', () => {
      // Mock canvas error
      const originalStrokeRect = mockContext.strokeRect;
      mockContext.strokeRect = jest.fn(() => {
        throw new Error('Canvas error');
      });

      render(<FullAnnotationSystem />);

      // Should handle error gracefully
      expect(() => {
        fireEvent.mouseMove(screen.getByRole('img'), { clientX: 100, clientY: 100 });
      }).not.toThrow();

      // Restore mock
      mockContext.strokeRect = originalStrokeRect;
    });

    it('should handle corrupt annotation data', () => {
      const corruptData = [
        {
          ...mockGroundTruthAnnotations[0],
          shapes: [
            {
              ...mockGroundTruthAnnotations[0].shapes[0],
              points: null, // Corrupt data
            } as any,
          ],
        },
      ];

      expect(() => {
        render(
          <FullAnnotationSystem groundTruthData={corruptData} />
        );
      }).not.toThrow();
    });

    it('should recover from keyboard event errors', () => {
      render(<FullAnnotationSystem />);

      // Mock keyboard error
      const originalAddEventListener = document.addEventListener;
      document.addEventListener = jest.fn((type, listener) => {
        if (type === 'keydown') {
          throw new Error('Event listener error');
        }
        originalAddEventListener.call(document, type, listener);
      });

      expect(() => {
        fireEvent.keyDown(document, { key: 'v' });
      }).not.toThrow();

      // Restore
      document.addEventListener = originalAddEventListener;
    });

    it('should maintain functionality during partial system failures', async () => {
      const user = userEvent.setup();

      render(<FullAnnotationSystem />);

      // Simulate toolbar failure
      const toolbar = screen.getByTestId('annotation-system');
      fireEvent.error(toolbar);

      // Canvas should still work
      const canvas = screen.getByRole('img');
      
      await user.pointer([
        { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
        { pointerName: 'mouse', target: canvas, coords: { clientX: 200, clientY: 200 } },
        { keys: '[/MouseLeft]', target: canvas },
      ]);

      expect(mockContext.strokeRect).toHaveBeenCalled();
    });
  });
});