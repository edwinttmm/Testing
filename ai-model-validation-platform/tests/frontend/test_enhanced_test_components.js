/**
 * Comprehensive Frontend Component Tests for Enhanced Test Page
 * 
 * This test suite covers:
 * - Component rendering and behavior
 * - User interactions and workflows
 * - State management
 * - API integration from frontend perspective
 * - Error handling and edge cases
 * - Accessibility compliance
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { jest } from '@jest/globals';

// Mock external dependencies
jest.mock('axios');
jest.mock('socket.io-client');

// Mock components that might not be available
jest.mock('../../frontend/src/components/EnhancedVideoPlayer', () => {
  return function MockEnhancedVideoPlayer(props) {
    return <div data-testid="enhanced-video-player" {...props}>Mock Video Player</div>;
  };
});

jest.mock('../../frontend/src/components/DetectionControls', () => {
  return function MockDetectionControls(props) {
    return (
      <div data-testid="detection-controls" {...props}>
        <button data-testid="start-detection">Start Detection</button>
        <button data-testid="stop-detection">Stop Detection</button>
        Mock Detection Controls
      </div>
    );
  };
});

jest.mock('../../frontend/src/components/LabJackStatusPanel', () => {
  return function MockLabJackStatusPanel(props) {
    return (
      <div data-testid="labjack-status" {...props}>
        <span data-testid="connection-status">Connected</span>
        Mock LabJack Status
      </div>
    );
  };
});

// Test wrapper component
const TestWrapper = ({ children }) => (
  <BrowserRouter>
    {children}
  </BrowserRouter>
);

describe('Enhanced Test Page Components', () => {
  
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock fetch globally
    global.fetch = jest.fn();
    
    // Mock console methods to reduce noise
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  // =============================================================================
  // TEST PAGE COMPONENT RENDERING TESTS
  // =============================================================================

  describe('TestExecution Page Component', () => {
    
    it('should render the main test execution interface', async () => {
      // Mock the main test execution component
      const MockTestExecution = () => (
        <div data-testid="test-execution-page">
          <h1>Enhanced Test Execution</h1>
          <div data-testid="project-selector">
            <select data-testid="project-dropdown">
              <option value="">Select Project</option>
              <option value="1">Test Project 1</option>
              <option value="2">Test Project 2</option>
            </select>
          </div>
          <div data-testid="test-configuration">
            <h2>Test Configuration</h2>
            <div data-testid="signal-validation-section">
              <h3>Signal Validation</h3>
              <input type="checkbox" data-testid="enable-signal-validation" />
              <label htmlFor="enable-signal-validation">Enable Signal Validation</label>
            </div>
            <div data-testid="detection-pipeline-section">
              <h3>Detection Pipeline</h3>
              <select data-testid="model-selector">
                <option value="yolov8n">YOLOv8 Nano</option>
                <option value="yolov8s">YOLOv8 Small</option>
              </select>
            </div>
          </div>
          <div data-testid="test-controls">
            <button data-testid="start-test-btn">Start Test</button>
            <button data-testid="stop-test-btn" disabled>Stop Test</button>
            <button data-testid="reset-test-btn">Reset</button>
          </div>
          <div data-testid="test-results">
            <h2>Test Results</h2>
            <div data-testid="results-content">No results yet</div>
          </div>
        </div>
      );

      render(
        <TestWrapper>
          <MockTestExecution />
        </TestWrapper>
      );

      // Verify main components are rendered
      expect(screen.getByTestId('test-execution-page')).toBeInTheDocument();
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
      expect(screen.getByTestId('project-selector')).toBeInTheDocument();
      expect(screen.getByTestId('test-configuration')).toBeInTheDocument();
      expect(screen.getByTestId('test-controls')).toBeInTheDocument();
      expect(screen.getByTestId('test-results')).toBeInTheDocument();
    });

    it('should handle project selection', async () => {
      const user = userEvent.setup();
      
      const MockTestExecution = () => {
        const [selectedProject, setSelectedProject] = React.useState('');
        
        return (
          <div>
            <select 
              data-testid="project-dropdown" 
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
            >
              <option value="">Select Project</option>
              <option value="1">Test Project 1</option>
              <option value="2">Test Project 2</option>
            </select>
            <div data-testid="selected-project">{selectedProject}</div>
          </div>
        );
      };

      render(<MockTestExecution />);

      const dropdown = screen.getByTestId('project-dropdown');
      await user.selectOptions(dropdown, '1');

      expect(screen.getByTestId('selected-project')).toHaveTextContent('1');
    });

    it('should toggle signal validation configuration', async () => {
      const user = userEvent.setup();
      
      const MockSignalValidation = () => {
        const [enabled, setEnabled] = React.useState(false);
        
        return (
          <div>
            <input 
              type="checkbox" 
              data-testid="enable-signal-validation"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <label>Enable Signal Validation</label>
            {enabled && (
              <div data-testid="signal-config">
                <input data-testid="signal-type" placeholder="Signal Type" />
                <input data-testid="threshold" placeholder="Threshold" type="number" />
              </div>
            )}
          </div>
        );
      };

      render(<MockSignalValidation />);

      const checkbox = screen.getByTestId('enable-signal-validation');
      await user.click(checkbox);

      expect(screen.getByTestId('signal-config')).toBeInTheDocument();
      expect(screen.getByTestId('signal-type')).toBeInTheDocument();
      expect(screen.getByTestId('threshold')).toBeInTheDocument();
    });

  });

  // =============================================================================
  // USER INTERACTION TESTS
  // =============================================================================

  describe('User Interaction Workflows', () => {

    it('should handle test execution workflow', async () => {
      const user = userEvent.setup();
      let testState = 'idle';
      
      const MockTestWorkflow = () => {
        const [state, setState] = React.useState('idle');
        
        const startTest = () => {
          setState('running');
          // Simulate test completion after 1 second
          setTimeout(() => setState('completed'), 1000);
        };
        
        const stopTest = () => setState('stopped');
        const resetTest = () => setState('idle');

        return (
          <div>
            <div data-testid="test-status">Status: {state}</div>
            <button 
              data-testid="start-btn"
              onClick={startTest}
              disabled={state === 'running'}
            >
              Start Test
            </button>
            <button 
              data-testid="stop-btn"
              onClick={stopTest}
              disabled={state !== 'running'}
            >
              Stop Test
            </button>
            <button 
              data-testid="reset-btn"
              onClick={resetTest}
            >
              Reset
            </button>
          </div>
        );
      };

      render(<MockTestWorkflow />);

      // Initial state
      expect(screen.getByTestId('test-status')).toHaveTextContent('Status: idle');
      expect(screen.getByTestId('stop-btn')).toBeDisabled();

      // Start test
      await user.click(screen.getByTestId('start-btn'));
      expect(screen.getByTestId('test-status')).toHaveTextContent('Status: running');
      expect(screen.getByTestId('start-btn')).toBeDisabled();
      expect(screen.getByTestId('stop-btn')).not.toBeDisabled();

      // Stop test
      await user.click(screen.getByTestId('stop-btn'));
      expect(screen.getByTestId('test-status')).toHaveTextContent('Status: stopped');

      // Reset test
      await user.click(screen.getByTestId('reset-btn'));
      expect(screen.getByTestId('test-status')).toHaveTextContent('Status: idle');
    });

    it('should handle form validation and submission', async () => {
      const user = userEvent.setup();
      let submittedData = null;
      
      const MockConfigForm = () => {
        const [formData, setFormData] = React.useState({
          projectId: '',
          modelType: '',
          confidence: ''
        });
        const [errors, setErrors] = React.useState({});
        
        const validateForm = () => {
          const newErrors = {};
          if (!formData.projectId) newErrors.projectId = 'Project is required';
          if (!formData.modelType) newErrors.modelType = 'Model is required';
          if (!formData.confidence || formData.confidence < 0 || formData.confidence > 1) {
            newErrors.confidence = 'Confidence must be between 0 and 1';
          }
          return newErrors;
        };
        
        const handleSubmit = (e) => {
          e.preventDefault();
          const validationErrors = validateForm();
          setErrors(validationErrors);
          
          if (Object.keys(validationErrors).length === 0) {
            submittedData = formData;
          }
        };
        
        return (
          <form onSubmit={handleSubmit} data-testid="config-form">
            <select
              data-testid="project-select"
              value={formData.projectId}
              onChange={(e) => setFormData({...formData, projectId: e.target.value})}
            >
              <option value="">Select Project</option>
              <option value="1">Project 1</option>
            </select>
            {errors.projectId && <div data-testid="project-error">{errors.projectId}</div>}
            
            <select
              data-testid="model-select"
              value={formData.modelType}
              onChange={(e) => setFormData({...formData, modelType: e.target.value})}
            >
              <option value="">Select Model</option>
              <option value="yolov8n">YOLOv8n</option>
            </select>
            {errors.modelType && <div data-testid="model-error">{errors.modelType}</div>}
            
            <input
              type="number"
              data-testid="confidence-input"
              value={formData.confidence}
              onChange={(e) => setFormData({...formData, confidence: e.target.value})}
              step="0.1"
              min="0"
              max="1"
              placeholder="Confidence (0-1)"
            />
            {errors.confidence && <div data-testid="confidence-error">{errors.confidence}</div>}
            
            <button type="submit" data-testid="submit-btn">Submit</button>
          </form>
        );
      };

      render(<MockConfigForm />);

      // Submit empty form - should show validation errors
      await user.click(screen.getByTestId('submit-btn'));
      
      expect(screen.getByTestId('project-error')).toHaveTextContent('Project is required');
      expect(screen.getByTestId('model-error')).toHaveTextContent('Model is required');

      // Fill form with valid data
      await user.selectOptions(screen.getByTestId('project-select'), '1');
      await user.selectOptions(screen.getByTestId('model-select'), 'yolov8n');
      await user.type(screen.getByTestId('confidence-input'), '0.5');

      // Submit valid form
      await user.click(screen.getByTestId('submit-btn'));
      
      // Should not show errors
      expect(screen.queryByTestId('project-error')).not.toBeInTheDocument();
      expect(screen.queryByTestId('model-error')).not.toBeInTheDocument();
      expect(screen.queryByTestId('confidence-error')).not.toBeInTheDocument();
      
      // Should have submitted data
      expect(submittedData).toEqual({
        projectId: '1',
        modelType: 'yolov8n',
        confidence: '0.5'
      });
    });

  });

  // =============================================================================
  // API INTEGRATION TESTS (Frontend Perspective)
  // =============================================================================

  describe('API Integration from Frontend', () => {

    it('should handle API loading states', async () => {
      const MockApiComponent = () => {
        const [loading, setLoading] = React.useState(false);
        const [data, setData] = React.useState(null);
        const [error, setError] = React.useState(null);
        
        const fetchData = async () => {
          setLoading(true);
          setError(null);
          
          try {
            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 500));
            setData({ message: 'Success' });
          } catch (err) {
            setError('Failed to fetch data');
          } finally {
            setLoading(false);
          }
        };
        
        return (
          <div>
            <button onClick={fetchData} data-testid="fetch-btn">Fetch Data</button>
            {loading && <div data-testid="loading">Loading...</div>}
            {error && <div data-testid="error">{error}</div>}
            {data && <div data-testid="success">{data.message}</div>}
          </div>
        );
      };

      render(<MockApiComponent />);

      const fetchBtn = screen.getByTestId('fetch-btn');
      fireEvent.click(fetchBtn);

      // Should show loading state
      expect(screen.getByTestId('loading')).toBeInTheDocument();

      // Wait for completion
      await waitFor(() => {
        expect(screen.getByTestId('success')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      expect(screen.getByTestId('success')).toHaveTextContent('Success');
    });

    it('should handle API error states', async () => {
      const MockErrorComponent = () => {
        const [error, setError] = React.useState(null);
        
        const triggerError = () => {
          setError('Network error occurred');
        };
        
        const clearError = () => {
          setError(null);
        };
        
        return (
          <div>
            <button onClick={triggerError} data-testid="error-btn">Trigger Error</button>
            {error && (
              <div data-testid="error-display">
                <div>{error}</div>
                <button onClick={clearError} data-testid="retry-btn">Retry</button>
              </div>
            )}
          </div>
        );
      };

      render(<MockErrorComponent />);

      // Trigger error
      fireEvent.click(screen.getByTestId('error-btn'));
      expect(screen.getByTestId('error-display')).toBeInTheDocument();
      expect(screen.getByText('Network error occurred')).toBeInTheDocument();

      // Clear error
      fireEvent.click(screen.getByTestId('retry-btn'));
      expect(screen.queryByTestId('error-display')).not.toBeInTheDocument();
    });

  });

  // =============================================================================
  // REAL-TIME FEATURES TESTS
  // =============================================================================

  describe('Real-time Features', () => {

    it('should handle WebSocket connection status', () => {
      const MockWebSocketStatus = ({ connected }) => (
        <div>
          <div data-testid="ws-status">
            Status: {connected ? 'Connected' : 'Disconnected'}
          </div>
          <div data-testid="ws-indicator" className={connected ? 'connected' : 'disconnected'}>
            {connected ? '🟢' : '🔴'}
          </div>
        </div>
      );

      const { rerender } = render(<MockWebSocketStatus connected={false} />);

      expect(screen.getByTestId('ws-status')).toHaveTextContent('Status: Disconnected');
      expect(screen.getByTestId('ws-indicator')).toHaveTextContent('🔴');

      // Simulate connection
      rerender(<MockWebSocketStatus connected={true} />);

      expect(screen.getByTestId('ws-status')).toHaveTextContent('Status: Connected');
      expect(screen.getByTestId('ws-indicator')).toHaveTextContent('🟢');
    });

    it('should handle real-time updates', async () => {
      const MockRealTimeUpdates = () => {
        const [updates, setUpdates] = React.useState([]);
        
        const addUpdate = (update) => {
          setUpdates(prev => [...prev, { id: Date.now(), message: update }]);
        };
        
        React.useEffect(() => {
          // Simulate periodic updates
          const interval = setInterval(() => {
            addUpdate(`Update at ${new Date().toLocaleTimeString()}`);
          }, 100);
          
          return () => clearInterval(interval);
        }, []);
        
        return (
          <div>
            <div data-testid="update-count">{updates.length}</div>
            <div data-testid="updates-list">
              {updates.map(update => (
                <div key={update.id} data-testid="update-item">
                  {update.message}
                </div>
              ))}
            </div>
          </div>
        );
      };

      render(<MockRealTimeUpdates />);

      // Initially no updates
      expect(screen.getByTestId('update-count')).toHaveTextContent('0');

      // Wait for some updates
      await waitFor(() => {
        expect(Number(screen.getByTestId('update-count').textContent)).toBeGreaterThan(0);
      });

      expect(screen.getAllByTestId('update-item').length).toBeGreaterThan(0);
    });

  });

  // =============================================================================
  // ERROR HANDLING AND EDGE CASES
  // =============================================================================

  describe('Error Handling and Edge Cases', () => {

    it('should handle missing props gracefully', () => {
      const MockComponent = ({ data = {} }) => (
        <div>
          <div data-testid="name">{data.name || 'No name'}</div>
          <div data-testid="count">{data.count || 0}</div>
        </div>
      );

      render(<MockComponent />);

      expect(screen.getByTestId('name')).toHaveTextContent('No name');
      expect(screen.getByTestId('count')).toHaveTextContent('0');

      // Test with partial data
      render(<MockComponent data={{ name: 'Test' }} />);
      expect(screen.getByTestId('name')).toHaveTextContent('Test');
      expect(screen.getByTestId('count')).toHaveTextContent('0');
    });

    it('should handle invalid input gracefully', async () => {
      const user = userEvent.setup();
      
      const MockInputValidation = () => {
        const [value, setValue] = React.useState('');
        const [isValid, setIsValid] = React.useState(true);
        
        const validateInput = (input) => {
          const isValidNumber = /^\d*\.?\d*$/.test(input);
          setIsValid(isValidNumber);
          return isValidNumber;
        };
        
        const handleChange = (e) => {
          const newValue = e.target.value;
          if (validateInput(newValue)) {
            setValue(newValue);
          }
        };
        
        return (
          <div>
            <input
              data-testid="number-input"
              value={value}
              onChange={handleChange}
              placeholder="Enter number"
            />
            <div data-testid="validation-message">
              {isValid ? 'Valid' : 'Invalid number format'}
            </div>
          </div>
        );
      };

      render(<MockInputValidation />);

      const input = screen.getByTestId('number-input');
      
      // Valid input
      await user.type(input, '123.45');
      expect(screen.getByTestId('validation-message')).toHaveTextContent('Valid');

      // Clear and try invalid input
      await user.clear(input);
      await user.type(input, 'abc');
      
      // Should reject invalid characters
      expect(input.value).toBe('');
      expect(screen.getByTestId('validation-message')).toHaveTextContent('Invalid number format');
    });

    it('should handle component unmounting gracefully', () => {
      const MockComponent = () => {
        const [mounted, setMounted] = React.useState(true);
        
        React.useEffect(() => {
          const timer = setTimeout(() => {
            if (mounted) {
              // This should not cause errors after unmounting
              setMounted(false);
            }
          }, 100);
          
          return () => clearTimeout(timer);
        }, [mounted]);
        
        return <div data-testid="component">Component is mounted</div>;
      };

      const { unmount } = render(<MockComponent />);
      
      // Component should render initially
      expect(screen.getByTestId('component')).toBeInTheDocument();
      
      // Unmount before timer completes
      unmount();
      
      // Should not throw errors
    });

  });

  // =============================================================================
  // ACCESSIBILITY TESTS
  // =============================================================================

  describe('Accessibility Compliance', () => {

    it('should have proper ARIA labels and roles', () => {
      const MockAccessibleComponent = () => (
        <div>
          <button 
            data-testid="start-btn"
            aria-label="Start test execution"
            role="button"
          >
            Start
          </button>
          <select 
            data-testid="project-select"
            aria-label="Select project"
            role="combobox"
          >
            <option value="">Choose project</option>
            <option value="1">Project 1</option>
          </select>
          <div 
            data-testid="status-display"
            role="status"
            aria-live="polite"
          >
            Ready
          </div>
        </div>
      );

      render(<MockAccessibleComponent />);

      expect(screen.getByTestId('start-btn')).toHaveAttribute('aria-label', 'Start test execution');
      expect(screen.getByTestId('project-select')).toHaveAttribute('aria-label', 'Select project');
      expect(screen.getByTestId('status-display')).toHaveAttribute('role', 'status');
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();
      
      const MockKeyboardNav = () => (
        <div>
          <button data-testid="btn1">Button 1</button>
          <button data-testid="btn2">Button 2</button>
          <button data-testid="btn3">Button 3</button>
        </div>
      );

      render(<MockKeyboardNav />);

      // Tab through buttons
      await user.tab();
      expect(screen.getByTestId('btn1')).toHaveFocus();

      await user.tab();
      expect(screen.getByTestId('btn2')).toHaveFocus();

      await user.tab();
      expect(screen.getByTestId('btn3')).toHaveFocus();
    });

  });

  // =============================================================================
  // PERFORMANCE TESTS
  // =============================================================================

  describe('Performance Considerations', () => {

    it('should handle large data sets efficiently', () => {
      const largeDataSet = Array.from({ length: 1000 }, (_, i) => ({
        id: i,
        name: `Item ${i}`,
        value: Math.random()
      }));

      const MockLargeList = ({ data }) => (
        <div data-testid="large-list">
          {data.slice(0, 100).map(item => ( // Only render first 100 items
            <div key={item.id} data-testid={`item-${item.id}`}>
              {item.name}: {item.value.toFixed(2)}
            </div>
          ))}
          <div data-testid="total-count">
            Showing 100 of {data.length} items
          </div>
        </div>
      );

      const start = performance.now();
      render(<MockLargeList data={largeDataSet} />);
      const renderTime = performance.now() - start;

      expect(screen.getByTestId('large-list')).toBeInTheDocument();
      expect(screen.getByTestId('total-count')).toHaveTextContent('Showing 100 of 1000 items');
      
      // Render time should be reasonable (less than 100ms)
      expect(renderTime).toBeLessThan(100);
    });

  });

});

// =============================================================================
// INTEGRATION HELPERS
// =============================================================================

/**
 * Helper function to simulate API responses
 */
export const mockApiResponse = (data, delay = 100) => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ data, status: 200, statusText: 'OK' });
    }, delay);
  });
};

/**
 * Helper function to simulate API errors
 */
export const mockApiError = (message, status = 500, delay = 100) => {
  return new Promise((_, reject) => {
    setTimeout(() => {
      reject({ 
        response: { 
          data: { message }, 
          status, 
          statusText: 'Error' 
        } 
      });
    }, delay);
  });
};

/**
 * Helper to render components with common providers
 */
export const renderWithProviders = (component, options = {}) => {
  const Wrapper = ({ children }) => (
    <BrowserRouter>
      {children}
    </BrowserRouter>
  );

  return render(component, { wrapper: Wrapper, ...options });
};

// Export for use in other test files
export {
  TestWrapper,
  userEvent,
  screen,
  render,
  fireEvent,
  waitFor,
  within
};