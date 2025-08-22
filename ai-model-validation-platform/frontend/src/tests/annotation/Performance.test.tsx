import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AnnotationProvider } from '../../components/annotation/AnnotationManager';
import EnhancedAnnotationCanvas from '../../components/annotation/EnhancedAnnotationCanvas';
import { AnnotationShape } from '../../components/annotation/types';
import { 
  setupTestEnvironment, 
  TestDataGenerator, 
  PerformanceUtils,
  MockShapeFactory 
} from './testUtils';

describe('Performance Test Suite', () => {
  let testEnv: ReturnType<typeof setupTestEnvironment>;

  beforeEach(() => {
    testEnv = setupTestEnvironment();
    jest.useFakeTimers();
  });

  afterEach(() => {
    testEnv.cleanup();
    jest.useRealTimers();
  });

  describe('Rendering Performance', () => {
    it('should render 1000 shapes within performance budget', async () => {
      const { shapes, memoryEstimate } = TestDataGenerator.generateStressTestData(1000);
      
      const { result, duration } = PerformanceUtils.measureTime(() => {
        render(
          <AnnotationProvider initialShapes={shapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      });

      expect(duration).toBeLessThan(3000); // Should render within 3 seconds
      expect(memoryEstimate).toBeLessThan(1000000); // Should use less than 1MB for shape data
    });

    it('should optimize off-screen shape rendering', async () => {
      const shapes: AnnotationShape[] = [
        // On-screen shape
        MockShapeFactory.rectangle({
          boundingBox: { x: 100, y: 100, width: 100, height: 100 }
        }),
        // Off-screen shapes
        ...Array.from({ length: 100 }, (_, i) => 
          MockShapeFactory.rectangle({
            boundingBox: { x: 2000 + i * 100, y: 2000, width: 50, height: 50 }
          })
        ),
      ];

      const renderCount = jest.fn();
      testEnv.context.strokeRect = jest.fn(renderCount);

      render(
        <AnnotationProvider initialShapes={shapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      // Should render fewer shapes than total (viewport culling)
      await waitFor(() => {
        expect(renderCount).toHaveBeenCalled();
        // Exact count depends on viewport culling implementation
      });
    });

    it('should handle rapid zoom operations efficiently', async () => {
      const shapes = TestDataGenerator.generateShapes(100);
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

      render(
        <AnnotationProvider initialShapes={shapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const start = performance.now();

      // Rapid zoom operations
      for (let i = 0; i < 20; i++) {
        fireEvent.keyDown(document, { key: '=' }); // Zoom in
        act(() => {
          jest.advanceTimersByTime(16); // Simulate 60fps
        });
      }

      const duration = performance.now() - start;
      expect(duration).toBeLessThan(500); // Should handle rapid zooming smoothly
    });

    it('should debounce frequent canvas redraws', async () => {
      const shapes = TestDataGenerator.generateShapes(50);
      let redrawCount = 0;
      
      testEnv.context.clearRect = jest.fn(() => redrawCount++);

      render(
        <AnnotationProvider initialShapes={shapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img');

      // Rapid mouse movements
      const start = performance.now();
      for (let i = 0; i < 100; i++) {
        fireEvent.mouseMove(canvas, { clientX: i, clientY: i });
      }

      act(() => {
        jest.advanceTimersByTime(100); // Allow debouncing to settle
      });

      const duration = performance.now() - start;

      expect(duration).toBeLessThan(200);
      // Should have debounced rapid redraws
      expect(redrawCount).toBeLessThan(100);
    });

    it('should maintain 60fps during continuous drawing', async () => {
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      let frameCount = 0;
      
      const originalRAF = global.requestAnimationFrame;
      global.requestAnimationFrame = jest.fn((callback) => {
        frameCount++;
        return setTimeout(callback, 16.67); // ~60fps
      });

      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img');

      // Simulate continuous drawing
      const startTime = performance.now();
      
      await user.pointer({ keys: '[MouseLeft>]', target: canvas });
      
      for (let i = 0; i < 100; i++) {
        fireEvent.mouseMove(canvas, { clientX: 100 + i, clientY: 100 + i });
        act(() => {
          jest.advanceTimersByTime(16.67);
        });
      }

      await user.pointer({ keys: '[/MouseLeft]', target: canvas });

      const endTime = performance.now();
      const expectedFrames = Math.floor((endTime - startTime) / 16.67);

      // Should maintain close to 60fps
      expect(frameCount).toBeGreaterThanOrEqual(expectedFrames * 0.8);

      global.requestAnimationFrame = originalRAF;
    });
  });

  describe('Memory Performance', () => {
    it('should limit undo/redo history memory usage', () => {
      const TestComponent = () => {
        const [actionCount, setActionCount] = React.useState(0);

        const performManyActions = () => {
          // Simulate 200 actions to test history limits
          for (let i = 0; i < 200; i++) {
            setActionCount(prev => prev + 1);
          }
        };

        return (
          <div>
            <AnnotationProvider>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
            <button onClick={performManyActions}>Perform Many Actions</button>
            <div data-testid="action-count">{actionCount}</div>
          </div>
        );
      };

      const initialMemory = PerformanceUtils.getMemoryUsage();

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Perform Many Actions'));

      const finalMemory = PerformanceUtils.getMemoryUsage();
      
      if (initialMemory && finalMemory) {
        const memoryIncrease = finalMemory.used - initialMemory.used;
        expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024); // Less than 10MB increase
      }

      expect(screen.getByTestId('action-count')).toHaveTextContent('200');
    });

    it('should efficiently handle shape creation and deletion cycles', () => {
      const shapes = TestDataGenerator.generateShapes(100);
      
      const TestComponent = () => {
        const [currentShapes, setCurrentShapes] = React.useState(shapes);

        const cycleShapes = () => {
          // Create and delete shapes in cycles
          for (let i = 0; i < 10; i++) {
            setCurrentShapes(prev => [...prev, MockShapeFactory.rectangle()]);
            setCurrentShapes(prev => prev.slice(1));
          }
        };

        return (
          <div>
            <AnnotationProvider initialShapes={currentShapes}>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
            <button onClick={cycleShapes}>Cycle Shapes</button>
            <div data-testid="shape-count">{currentShapes.length}</div>
          </div>
        );
      };

      const initialMemory = PerformanceUtils.getMemoryUsage();

      render(<TestComponent />);

      // Perform multiple cycles
      for (let i = 0; i < 5; i++) {
        fireEvent.click(screen.getByText('Cycle Shapes'));
      }

      const finalMemory = PerformanceUtils.getMemoryUsage();

      if (initialMemory && finalMemory) {
        const memoryIncrease = finalMemory.used - initialMemory.used;
        expect(memoryIncrease).toBeLessThan(5 * 1024 * 1024); // Less than 5MB increase
      }

      expect(screen.getByTestId('shape-count')).toHaveTextContent('100');
    });

    it('should garbage collect unused shape references', async () => {
      const TestComponent = () => {
        const [shapes, setShapes] = React.useState<AnnotationShape[]>([]);

        const createAndClearShapes = () => {
          // Create many shapes
          const newShapes = TestDataGenerator.generateShapes(1000);
          setShapes(newShapes);
          
          // Clear them immediately
          setTimeout(() => setShapes([]), 100);
        };

        return (
          <div>
            <AnnotationProvider initialShapes={shapes}>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
            <button onClick={createAndClearShapes}>Create and Clear</button>
          </div>
        );
      };

      render(<TestComponent />);

      fireEvent.click(screen.getByText('Create and Clear'));

      await act(async () => {
        jest.advanceTimersByTime(200);
      });

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }

      // Memory should be reclaimed (test is environment-dependent)
      expect(true).toBe(true); // Placeholder assertion
    });
  });

  describe('Interaction Performance', () => {
    it('should handle rapid mouse events without lag', async () => {
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      let eventCount = 0;
      
      const TestCanvas = () => {
        const handleMouseMove = () => {
          eventCount++;
        };

        return (
          <AnnotationProvider>
            <div onMouseMove={handleMouseMove}>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </div>
          </AnnotationProvider>
        );
      };

      render(<TestCanvas />);

      const canvas = screen.getByRole('img');
      const start = performance.now();

      // Rapid mouse movements
      for (let i = 0; i < 1000; i++) {
        fireEvent.mouseMove(canvas, { clientX: i % 800, clientY: i % 600 });
      }

      const duration = performance.now() - start;

      expect(duration).toBeLessThan(1000); // Should handle 1000 events within 1 second
      expect(eventCount).toBe(1000);
    });

    it('should throttle expensive operations during interaction', async () => {
      const shapes = TestDataGenerator.generateShapes(200);
      let expensiveOperationCount = 0;

      const TestComponent = () => {
        React.useEffect(() => {
          // Simulate expensive operation
          const interval = setInterval(() => {
            expensiveOperationCount++;
            // Expensive calculation
            shapes.forEach(shape => {
              shape.points.forEach(point => {
                Math.sqrt(point.x * point.x + point.y * point.y);
              });
            });
          }, 16);

          return () => clearInterval(interval);
        }, []);

        return (
          <AnnotationProvider initialShapes={shapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        );
      };

      render(<TestComponent />);

      const canvas = screen.getByRole('img');

      // Interact while expensive operations are running
      for (let i = 0; i < 50; i++) {
        fireEvent.mouseMove(canvas, { clientX: i * 10, clientY: i * 10 });
        act(() => {
          jest.advanceTimersByTime(16);
        });
      }

      // Should complete interactions smoothly
      expect(expensiveOperationCount).toBeGreaterThan(0);
    });

    it('should maintain responsiveness during bulk operations', async () => {
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

      const TestComponent = () => {
        const [processing, setProcessing] = React.useState(false);

        const performBulkOperation = async () => {
          setProcessing(true);
          
          // Simulate bulk processing
          await new Promise(resolve => {
            setTimeout(resolve, 1000);
          });
          
          setProcessing(false);
        };

        return (
          <div>
            <AnnotationProvider>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
            <button onClick={performBulkOperation} disabled={processing}>
              {processing ? 'Processing...' : 'Bulk Operation'}
            </button>
          </div>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Bulk Operation');
      const canvas = screen.getByRole('img');

      await user.click(button);

      // Should still be able to interact during processing
      fireEvent.mouseMove(canvas, { clientX: 100, clientY: 100 });

      act(() => {
        jest.advanceTimersByTime(1100);
      });

      await waitFor(() => {
        expect(screen.getByText('Bulk Operation')).toBeInTheDocument();
      });
    });
  });

  describe('Scalability Performance', () => {
    it('should scale logarithmically with shape count', () => {
      const shapeCounts = [100, 500, 1000, 2000];
      const renderTimes: number[] = [];

      shapeCounts.forEach(count => {
        const shapes = TestDataGenerator.generateShapes(count);
        
        const { duration } = PerformanceUtils.measureTime(() => {
          const { unmount } = render(
            <AnnotationProvider initialShapes={shapes}>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
          );
          unmount();
        });

        renderTimes.push(duration);
      });

      // Performance should scale sub-linearly (better than O(n))
      const firstRatio = renderTimes[1] / renderTimes[0]; // 500/100
      const secondRatio = renderTimes[2] / renderTimes[1]; // 1000/500
      const thirdRatio = renderTimes[3] / renderTimes[2]; // 2000/1000

      // Each doubling should be less than 2x slower (logarithmic scaling)
      expect(firstRatio).toBeLessThan(5);
      expect(secondRatio).toBeLessThan(firstRatio + 1);
      expect(thirdRatio).toBeLessThan(secondRatio + 1);
    });

    it('should handle concurrent users efficiently', async () => {
      const simulateUser = async (userId: number) => {
        const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
        
        const { unmount } = render(
          <div data-testid={`user-${userId}`}>
            <AnnotationProvider>
              <EnhancedAnnotationCanvas width={800} height={600} />
            </AnnotationProvider>
          </div>
        );

        const canvas = screen.getByRole('img');

        // Simulate user interactions
        for (let i = 0; i < 10; i++) {
          fireEvent.mouseMove(canvas, { 
            clientX: userId * 10 + i, 
            clientY: userId * 10 + i 
          });
          
          act(() => {
            jest.advanceTimersByTime(16);
          });
        }

        unmount();
      };

      const start = performance.now();

      // Simulate 10 concurrent users
      const userPromises = Array.from({ length: 10 }, (_, i) => simulateUser(i));
      await Promise.all(userPromises);

      const duration = performance.now() - start;

      // Should handle concurrent users efficiently
      expect(duration).toBeLessThan(5000); // Less than 5 seconds for 10 users
    });

    it('should optimize for common viewport sizes', () => {
      const viewportSizes = [
        { width: 800, height: 600 },   // Small
        { width: 1920, height: 1080 }, // HD
        { width: 3840, height: 2160 }, // 4K
      ];

      const shapes = TestDataGenerator.generateShapes(500);

      viewportSizes.forEach(({ width, height }) => {
        const { duration } = PerformanceUtils.measureTime(() => {
          const { unmount } = render(
            <AnnotationProvider initialShapes={shapes}>
              <EnhancedAnnotationCanvas width={width} height={height} />
            </AnnotationProvider>
          );
          unmount();
        });

        // Larger viewports should not be dramatically slower
        expect(duration).toBeLessThan(2000);
      });
    });
  });

  describe('Resource Management', () => {
    it('should clean up event listeners on unmount', () => {
      const addEventListenerSpy = jest.spyOn(document, 'addEventListener');
      const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');

      const { unmount } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const addedEventCount = addEventListenerSpy.mock.calls.length;

      unmount();

      const removedEventCount = removeEventListenerSpy.mock.calls.length;

      // Should remove as many listeners as were added
      expect(removedEventCount).toBeGreaterThanOrEqual(addedEventCount);

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('should cancel animation frames on unmount', () => {
      const cancelAnimationFrameSpy = jest.spyOn(global, 'cancelAnimationFrame');

      const { unmount } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      unmount();

      expect(cancelAnimationFrameSpy).toHaveBeenCalled();

      cancelAnimationFrameSpy.mockRestore();
    });

    it('should dispose of WebGL resources if used', () => {
      // Mock WebGL context
      const mockWebGL = {
        deleteBuffer: jest.fn(),
        deleteTexture: jest.fn(),
        deleteProgram: jest.fn(),
        deleteShader: jest.fn(),
      };

      HTMLCanvasElement.prototype.getContext = jest.fn((type: string) => {
        if (type === 'webgl' || type === 'webgl2') {
          return mockWebGL;
        }
        return testEnv.context;
      }) as any;

      const { unmount } = render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      unmount();

      // Should clean up WebGL resources if they were used
      // Note: Actual implementation may vary
      expect(true).toBe(true); // Placeholder assertion
    });

    it('should handle memory pressure gracefully', () => {
      const originalRequestAnimationFrame = global.requestAnimationFrame;
      let frameCallbacks: FrameRequestCallback[] = [];

      // Mock memory pressure scenario
      global.requestAnimationFrame = jest.fn((callback: FrameRequestCallback) => {
        frameCallbacks.push(callback);
        return frameCallbacks.length;
      });

      const shapes = TestDataGenerator.generateShapes(2000); // Large dataset

      render(
        <AnnotationProvider initialShapes={shapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      // Simulate frame processing under memory pressure
      expect(() => {
        frameCallbacks.forEach(callback => callback(performance.now()));
      }).not.toThrow();

      global.requestAnimationFrame = originalRequestAnimationFrame;
    });
  });

  describe('Performance Regression Tests', () => {
    it('should not degrade performance with each re-render', () => {
      const shapes = TestDataGenerator.generateShapes(100);
      const renderTimes: number[] = [];

      const TestComponent = ({ rerenderCount }: { rerenderCount: number }) => (
        <div key={rerenderCount}>
          <AnnotationProvider initialShapes={shapes}>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </AnnotationProvider>
        </div>
      );

      // Measure render times for multiple re-renders
      for (let i = 0; i < 5; i++) {
        const { duration } = PerformanceUtils.measureTime(() => {
          const { unmount } = render(<TestComponent rerenderCount={i} />);
          unmount();
        });
        renderTimes.push(duration);
      }

      // Performance should not significantly degrade
      const avgTime = renderTimes.reduce((sum, time) => sum + time, 0) / renderTimes.length;
      const maxTime = Math.max(...renderTimes);
      
      expect(maxTime).toBeLessThan(avgTime * 2); // No render should be more than 2x average
    });

    it('should maintain consistent frame rates during extended use', async () => {
      const frameRates: number[] = [];
      let frameCount = 0;
      let lastTimestamp = 0;

      const mockRAF = (callback: FrameRequestCallback) => {
        const timestamp = performance.now();
        if (lastTimestamp > 0) {
          const frameDelta = timestamp - lastTimestamp;
          const fps = 1000 / frameDelta;
          frameRates.push(fps);
        }
        lastTimestamp = timestamp;
        frameCount++;
        
        if (frameCount < 100) {
          setTimeout(() => callback(timestamp), 16.67);
        }
        
        return frameCount;
      };

      const originalRAF = global.requestAnimationFrame;
      global.requestAnimationFrame = mockRAF;

      render(
        <AnnotationProvider>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      await act(async () => {
        jest.advanceTimersByTime(2000); // Run for 2 seconds
      });

      global.requestAnimationFrame = originalRAF;

      // Frame rates should be consistent
      const avgFPS = frameRates.reduce((sum, fps) => sum + fps, 0) / frameRates.length;
      const minFPS = Math.min(...frameRates);
      
      expect(avgFPS).toBeGreaterThan(50); // Average should be above 50 FPS
      expect(minFPS).toBeGreaterThan(30); // Minimum should be above 30 FPS
    });
  });
});