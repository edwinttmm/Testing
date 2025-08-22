import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AnnotationProvider } from '../../components/annotation/AnnotationManager';
import EnhancedAnnotationCanvas from '../../components/annotation/EnhancedAnnotationCanvas';
import KeyboardShortcuts from '../../components/annotation/KeyboardShortcuts';
import { AnnotationShape, Point } from '../../components/annotation/types';
import { setupTestEnvironment, MockShapeFactory, GeometryUtils } from './testUtils';

describe('Edge Cases and Error Handling Test Suite', () => {
  let testEnv: ReturnType<typeof setupTestEnvironment>;

  beforeEach(() => {
    testEnv = setupTestEnvironment();
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    testEnv.cleanup();
    jest.restoreAllMocks();
  });

  describe('Invalid Data Handling', () => {
    it('should handle corrupt shape data gracefully', () => {
      const corruptShapes = [
        {
          id: 'corrupt1',
          type: 'rectangle',
          points: null, // Invalid points
          boundingBox: { x: 50, y: 50, width: 100, height: 100 },
          style: {
            strokeColor: '#000',
            fillColor: '#fff',
            strokeWidth: 2,
            fillOpacity: 0.5,
          },
          visible: true,
          selected: false,
        },
        {
          id: 'corrupt2',
          type: 'polygon',
          points: [{ x: 100, y: 100 }], // Too few points for polygon
          boundingBox: { x: 100, y: 100, width: 0, height: 0 },
          style: {
            strokeColor: '#000',
            fillColor: '#fff',
            strokeWidth: 2,
            fillOpacity: 0.5,
          },
          visible: true,
          selected: false,
        },
      ] as AnnotationShape[];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={corruptShapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();

      // Should render without crashing
      expect(screen.getByRole('img')).toBeInTheDocument();
    });

    it('should handle NaN and Infinity coordinates', () => {
      const invalidShapes = [
        MockShapeFactory.rectangle({
          boundingBox: { x: NaN, y: 50, width: 100, height: 100 },
        }),
        MockShapeFactory.point({ x: Infinity, y: -Infinity }),
        MockShapeFactory.polygon([
          { x: 0, y: 0 },
          { x: NaN, y: 100 },
          { x: 100, y: Infinity },
        ]),
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={invalidShapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle negative dimensions', () => {
      const negativeShapes = [
        MockShapeFactory.rectangle({
          boundingBox: { x: 100, y: 100, width: -50, height: -50 },
        }),
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={negativeShapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle empty or undefined style properties', () => {
      const shapesWithBadStyles = [
        {
          ...MockShapeFactory.rectangle(),
          style: undefined as any,
        },
        {
          ...MockShapeFactory.rectangle(),
          style: {
            strokeColor: null,
            fillColor: '',
            strokeWidth: undefined,
            fillOpacity: NaN,
          } as any,
        },
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={shapesWithBadStyles}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Canvas Error Handling', () => {
    it('should handle canvas context unavailable', () => {
      HTMLCanvasElement.prototype.getContext = jest.fn(() => null);

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();

      // Restore
      HTMLCanvasElement.prototype.getContext = jest.fn(() => testEnv.context) as any;
    });

    it('should handle canvas drawing errors', () => {
      testEnv.context.strokeRect = jest.fn(() => {
        throw new Error('Canvas drawing error');
      });

      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      expect(() => {
        fireEvent.mouseMove(screen.getByRole('img'), { clientX: 100, clientY: 100 });
      }).not.toThrow();
    });

    it('should handle canvas size changes to zero', () => {
      const { rerender } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      expect(() => {
        rerender(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={0} height={0} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle canvas size changes to negative values', () => {
      const { rerender } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      expect(() => {
        rerender(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={-100} height={-100} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Event Handling Edge Cases', () => {
    it('should handle events with missing properties', async () => {
      const user = userEvent.setup();

      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img');

      // Mock event with missing properties
      const invalidEvent = {
        clientX: undefined,
        clientY: undefined,
        target: canvas,
        preventDefault: jest.fn(),
        stopPropagation: jest.fn(),
      };

      expect(() => {
        fireEvent.mouseDown(canvas, invalidEvent);
        fireEvent.mouseMove(canvas, invalidEvent);
        fireEvent.mouseUp(canvas, invalidEvent);
      }).not.toThrow();
    });

    it('should handle rapid event firing', async () => {
      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img');

      expect(() => {
        // Fire 1000 events rapidly
        for (let i = 0; i < 1000; i++) {
          fireEvent.mouseMove(canvas, { clientX: i % 800, clientY: i % 600 });
        }
      }).not.toThrow();
    });

    it('should handle keyboard events on non-existent elements', () => {
      render(
        <AnnotationProvider>
          <KeyboardShortcuts />
        </AnnotationProvider>
      );

      expect(() => {
        // Fire keyboard events when no canvas is present
        fireEvent.keyDown(document, { key: 'v' });
        fireEvent.keyDown(document, { key: 'r' });
        fireEvent.keyDown(document, { key: 'Delete' });
      }).not.toThrow();
    });

    it('should handle touch events on non-touch devices', () => {
      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img');

      expect(() => {
        fireEvent.touchStart(canvas, {
          touches: [{ clientX: 100, clientY: 100 }],
        });
        fireEvent.touchMove(canvas, {
          touches: [{ clientX: 150, clientY: 150 }],
        });
        fireEvent.touchEnd(canvas, {
          changedTouches: [{ clientX: 150, clientY: 150 }],
        });
      }).not.toThrow();
    });

    it('should handle concurrent mouse and touch events', () => {
      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img');

      expect(() => {
        // Simultaneous mouse and touch events
        fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 });
        fireEvent.touchStart(canvas, {
          touches: [{ clientX: 200, clientY: 200 }],
        });
        fireEvent.mouseMove(canvas, { clientX: 110, clientY: 110 });
        fireEvent.touchMove(canvas, {
          touches: [{ clientX: 210, clientY: 210 }],
        });
        fireEvent.mouseUp(canvas, { clientX: 120, clientY: 120 });
        fireEvent.touchEnd(canvas, {
          changedTouches: [{ clientX: 220, clientY: 220 }],
        });
      }).not.toThrow();
    });
  });

  describe('State Consistency Edge Cases', () => {
    it('should handle concurrent state updates', async () => {
      const TestComponent = () => {
        const [shapes, setShapes] = React.useState<AnnotationShape[]>([]);
        
        const addMultipleShapes = () => {
          // Add multiple shapes concurrently
          Promise.all([
            new Promise(resolve => {
              setTimeout(() => {
                setShapes(prev => [...prev, MockShapeFactory.rectangle()]);
                resolve(undefined);
              }, 10);
            }),
            new Promise(resolve => {
              setTimeout(() => {
                setShapes(prev => [...prev, MockShapeFactory.polygon()]);
                resolve(undefined);
              }, 15);
            }),
            new Promise(resolve => {
              setTimeout(() => {
                setShapes(prev => [...prev, MockShapeFactory.point()]);
                resolve(undefined);
              }, 20);
            }),
          ]);
        };

        return (
          <div>
            <AnnotationProvider initialShapes={shapes}>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
            <button onClick={addMultipleShapes}>Add Multiple</button>
          </div>
        );
      };

      render(<TestComponent />);

      expect(() => {
        fireEvent.click(screen.getByText('Add Multiple'));
      }).not.toThrow();
    });

    it('should handle state updates during unmount', () => {
      const TestComponent = ({ shouldRender }: { shouldRender: boolean }) => {
        const [, setCounter] = React.useState(0);

        React.useEffect(() => {
          if (!shouldRender) {
            // Try to update state during unmount
            setCounter(1);
          }
        }, [shouldRender]);

        if (!shouldRender) {
          return null;
        }

        return (
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      };

      const { rerender } = render(<TestComponent shouldRender={true} />);

      expect(() => {
        rerender(<TestComponent shouldRender={false} />);
      }).not.toThrow();
    });

    it('should handle circular references in shape data', () => {
      const circularShape = MockShapeFactory.rectangle();
      (circularShape as any).parent = circularShape; // Create circular reference

      expect(() => {
        render(
          <AnnotationProvider initialShapes={[circularShape]}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle state mutations from external sources', () => {
      const shapes = [MockShapeFactory.rectangle()];
      
      render(
        <AnnotationProvider initialShapes={shapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      // Mutate the original shape array
      shapes.push(MockShapeFactory.polygon());
      shapes[0].visible = false;

      expect(() => {
        fireEvent.mouseMove(screen.getByRole('img'), { clientX: 100, clientY: 100 });
      }).not.toThrow();
    });
  });

  describe('Geometry Edge Cases', () => {
    it('should handle degenerate shapes', () => {
      const degenerateShapes = [
        MockShapeFactory.rectangle({
          boundingBox: { x: 100, y: 100, width: 0, height: 0 }, // Zero-size rectangle
        }),
        MockShapeFactory.polygon([
          { x: 100, y: 100 },
          { x: 100, y: 100 }, // Duplicate points
        ]),
        MockShapeFactory.brush([{ x: 100, y: 100 }]), // Single-point brush
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={degenerateShapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle shapes outside canvas bounds', () => {
      const outsideShapes = [
        MockShapeFactory.rectangle({
          boundingBox: { x: -100, y: -100, width: 50, height: 50 },
        }),
        MockShapeFactory.rectangle({
          boundingBox: { x: 1000, y: 1000, width: 100, height: 100 },
        }),
        MockShapeFactory.point({ x: -50, y: -50 }),
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={outsideShapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle extremely large coordinates', () => {
      const largeCoordinateShapes = [
        MockShapeFactory.rectangle({
          boundingBox: { 
            x: Number.MAX_SAFE_INTEGER - 1000, 
            y: Number.MAX_SAFE_INTEGER - 1000, 
            width: 100, 
            height: 100 
          },
        }),
        MockShapeFactory.point({ 
          x: Number.MAX_SAFE_INTEGER, 
          y: Number.MIN_SAFE_INTEGER 
        }),
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={largeCoordinateShapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle precision errors in floating point calculations', () => {
      const precisionPoints: Point[] = [
        { x: 0.1 + 0.2, y: 0.1 + 0.2 }, // 0.30000000000000004
        { x: 1.1 + 1.2, y: 1.1 + 1.2 },
        { x: 0.1 * 3, y: 0.1 * 3 },
      ];

      expect(() => {
        const shape = MockShapeFactory.polygon(precisionPoints);
        render(
          <AnnotationProvider initialShapes={[shape]}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle self-intersecting polygons', () => {
      const selfIntersectingPolygon = MockShapeFactory.polygon([
        { x: 100, y: 100 },
        { x: 200, y: 200 },
        { x: 100, y: 200 },
        { x: 200, y: 100 }, // Creates intersection
      ]);

      expect(() => {
        render(
          <AnnotationProvider initialShapes={[selfIntersectingPolygon]}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Memory and Resource Edge Cases', () => {
    it('should handle memory exhaustion gracefully', () => {
      // Simulate memory pressure by creating many objects
      const createManyShapes = () => {
        const shapes: AnnotationShape[] = [];
        try {
          for (let i = 0; i < 100000; i++) {
            shapes.push(MockShapeFactory.rectangle());
          }
        } catch (e) {
          // Expected if memory runs out
        }
        return shapes.slice(0, 1000); // Return manageable subset
      };

      const shapes = createManyShapes();

      expect(() => {
        render(
          <AnnotationProvider initialShapes={shapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle resource cleanup failures', () => {
      const originalRemoveEventListener = document.removeEventListener;
      document.removeEventListener = jest.fn(() => {
        throw new Error('Cleanup failed');
      });

      const { unmount } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
          <KeyboardShortcuts />
        </AnnotationProvider>
      );

      expect(() => {
        unmount();
      }).not.toThrow();

      document.removeEventListener = originalRemoveEventListener;
    });

    it('should handle animation frame cleanup failures', () => {
      const originalCancelAnimationFrame = global.cancelAnimationFrame;
      global.cancelAnimationFrame = jest.fn(() => {
        throw new Error('Cancel animation frame failed');
      });

      const { unmount } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      expect(() => {
        unmount();
      }).not.toThrow();

      global.cancelAnimationFrame = originalCancelAnimationFrame;
    });
  });

  describe('Browser Compatibility Edge Cases', () => {
    it('should handle missing requestAnimationFrame', () => {
      const originalRAF = global.requestAnimationFrame;
      delete (global as any).requestAnimationFrame;

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();

      global.requestAnimationFrame = originalRAF;
    });

    it('should handle missing performance API', () => {
      const originalPerformance = global.performance;
      delete (global as any).performance;

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();

      global.performance = originalPerformance;
    });

    it('should handle unsupported canvas features', () => {
      // Mock canvas context without certain features
      delete testEnv.context.setLineDash;
      delete testEnv.context.globalAlpha;

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle DOM exceptions', () => {
      HTMLCanvasElement.prototype.getBoundingClientRect = jest.fn(() => {
        throw new DOMException('DOM operation failed');
      });

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();

      // Restore
      HTMLCanvasElement.prototype.getBoundingClientRect = jest.fn(() => ({
        left: 0, top: 0, width: 800, height: 600,
        right: 800, bottom: 600, x: 0, y: 0, toJSON: jest.fn(),
      }));
    });
  });

  describe('Accessibility Edge Cases', () => {
    it('should handle keyboard navigation with no focusable elements', () => {
      render(
        <AnnotationProvider>
          <div tabIndex={-1}>
            <EnhancedAnnotationCanvas width={800} height={600} />
            <KeyboardShortcuts />
          </div>
        </AnnotationProvider>
      );

      expect(() => {
        fireEvent.keyDown(document, { key: 'Tab' });
        fireEvent.keyDown(document, { key: 'Escape' });
        fireEvent.keyDown(document, { key: 'Enter' });
      }).not.toThrow();
    });

    it('should handle high contrast mode', () => {
      // Mock high contrast mode
      Object.defineProperty(window, 'matchMedia', {
        value: jest.fn(() => ({
          matches: true,
          media: '(prefers-contrast: high)',
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
        })),
      });

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle reduced motion preferences', () => {
      Object.defineProperty(window, 'matchMedia', {
        value: jest.fn(() => ({
          matches: true,
          media: '(prefers-reduced-motion: reduce)',
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
        })),
      });

      expect(() => {
        render(
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Network and Data Loading Edge Cases', () => {
    it('should handle failed data loading', async () => {
      const TestComponent = () => {
        const [error, setError] = React.useState<Error | null>(null);

        React.useEffect(() => {
          // Simulate failed data loading
          setTimeout(() => {
            setError(new Error('Failed to load annotation data'));
          }, 100);
        }, []);

        if (error) {
          return <div>Error: {error.message}</div>;
        }

        return (
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      };

      render(<TestComponent />);

      await waitFor(() => {
        expect(screen.getByText(/Error: Failed to load/)).toBeInTheDocument();
      });
    });

    it('should handle partial data corruption', () => {
      const partiallyCorruptData = [
        MockShapeFactory.rectangle(), // Good shape
        {
          id: 'corrupt',
          type: 'unknown' as any,
          points: 'invalid' as any,
          boundingBox: null as any,
          style: 'invalid' as any,
          visible: 'true' as any,
          selected: 'false' as any,
        },
        MockShapeFactory.polygon(), // Another good shape
      ];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={partiallyCorruptData}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle timeout during data processing', async () => {
      const TestComponent = () => {
        const [processing, setProcessing] = React.useState(true);

        React.useEffect(() => {
          // Simulate timeout
          const timeout = setTimeout(() => {
            setProcessing(false);
          }, 5000);

          return () => clearTimeout(timeout);
        }, []);

        if (processing) {
          return <div>Processing...</div>;
        }

        return (
          <AnnotationProvider>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      };

      render(<TestComponent />);
      
      expect(screen.getByText('Processing...')).toBeInTheDocument();

      // Fast-forward time
      act(() => {
        jest.advanceTimersByTime(6000);
      });

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });
    });
  });
});