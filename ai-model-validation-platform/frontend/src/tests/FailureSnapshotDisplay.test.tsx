import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { act } from 'react-dom/test-utils';
import '@testing-library/jest-dom';

import FailureSnapshotDisplay from '../components/FailureSnapshotDisplay';
import { FailureSnapshotData } from '../types/enhanced-results';

// Mock Material-UI components that might cause issues in tests
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="zoom-modal">{children}</div> : null,
}));

describe('FailureSnapshotDisplay', () => {
  const mockFailures: FailureSnapshotData[] = [
    {
      id: 'failure_1',
      frameNumber: 150,
      timestamp: Date.now() - 3600000, // 1 hour ago
      screenshot_path: '/api/snapshots/failure_1.jpg',
      screenshot_zoom_path: '/api/snapshots/failure_1_zoom.jpg',
      failure_reason: 'Detection latency exceeded threshold (120ms > 100ms)',
      failure_type: 'timing',
      confidence: 0.65,
      expected_value: 100,
      actual_value: 120,
      threshold: 100,
      metadata: {
        sessionId: 'test_session_1',
        sessionName: 'Test Session 1',
        projectName: 'Test Project',
        videoName: 'test_video.mp4'
      }
    },
    {
      id: 'failure_2',
      frameNumber: 275,
      timestamp: Date.now() - 1800000, // 30 minutes ago
      screenshot_path: '/api/snapshots/failure_2.jpg',
      failure_reason: 'False positive detection',
      failure_type: 'accuracy',
      confidence: 0.45,
      metadata: {
        sessionId: 'test_session_2',
        sessionName: 'Test Session 2',
        projectName: 'Test Project',
        videoName: 'test_video_2.mp4'
      }
    },
    {
      id: 'failure_3',
      frameNumber: 425,
      timestamp: Date.now() - 900000, // 15 minutes ago
      screenshot_path: '/api/snapshots/failure_3.jpg',
      failure_reason: 'System timeout during processing',
      failure_type: 'system',
      metadata: {
        sessionId: 'test_session_1',
        sessionName: 'Test Session 1',
        projectName: 'Test Project',
        videoName: 'test_video.mp4'
      }
    }
  ];

  beforeEach(() => {
    // Mock Image constructor to avoid loading actual images in tests
    global.Image = class {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      src: string = '';
      
      constructor() {
        setTimeout(() => {
          if (this.onload) {
            this.onload();
          }
        }, 100);
      }
    } as any;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    test('renders failure snapshots display with data', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      expect(screen.getByText('Failure Snapshots (3 failures)')).toBeInTheDocument();
      
      await waitFor(() => {
        expect(screen.getByText('Frame 150')).toBeInTheDocument();
        expect(screen.getByText('Frame 275')).toBeInTheDocument();
        expect(screen.getByText('Frame 425')).toBeInTheDocument();
      });
    });

    test('renders loading state correctly', () => {
      render(<FailureSnapshotDisplay failures={[]} loading={true} />);

      expect(screen.getByText('Loading Failure Snapshots...')).toBeInTheDocument();
    });

    test('renders error state correctly', () => {
      const errorMessage = 'Failed to load snapshots';
      render(<FailureSnapshotDisplay failures={[]} error={errorMessage} />);

      expect(screen.getByText('Failed to Load Snapshots')).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    test('renders empty state when no failures', () => {
      render(<FailureSnapshotDisplay failures={[]} />);

      expect(screen.getByText('No Failures Found')).toBeInTheDocument();
      expect(screen.getByText('All tests passed successfully - no failure snapshots to display.')).toBeInTheDocument();
    });
  });

  describe('PRD Compliance Features', () => {
    test('displays PRD-compliant failure information', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      await waitFor(() => {
        // Check that failure reasons are displayed
        expect(screen.getByText('Detection latency exceeded threshold (120ms > 100ms)')).toBeInTheDocument();
        expect(screen.getByText('False positive detection')).toBeInTheDocument();
        expect(screen.getByText('System timeout during processing')).toBeInTheDocument();
      });
    });

    test('shows expected vs actual values for timing failures', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      await waitFor(() => {
        expect(screen.getByText('Expected: 100')).toBeInTheDocument();
        expect(screen.getByText('Actual: 120')).toBeInTheDocument();
      });
    });

    test('displays different failure type indicators', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      await waitFor(() => {
        const timingChips = screen.getAllByText('timing');
        const accuracyChips = screen.getAllByText('accuracy');
        const systemChips = screen.getAllByText('system');
        
        expect(timingChips.length).toBeGreaterThan(0);
        expect(accuracyChips.length).toBeGreaterThan(0);
        expect(systemChips.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Image Display and Loading', () => {
    test('handles image loading correctly', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images.length).toBe(mockFailures.length);
      });
    });

    test('handles image loading errors gracefully', async () => {
      // Mock image loading failure
      global.Image = class {
        onload: (() => void) | null = null;
        onerror: (() => void) | null = null;
        src: string = '';
        
        constructor() {
          setTimeout(() => {
            if (this.onerror) {
              this.onerror();
            }
          }, 100);
        }
      } as any;

      render(<FailureSnapshotDisplay failures={mockFailures.slice(0, 1)} />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load image/)).toBeInTheDocument();
      });
    });

    test('supports lazy loading when enabled', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} showSettings={true} />);

      // Enable lazy loading
      const lazyLoadingSwitch = screen.getByLabelText('Lazy Loading');
      fireEvent.click(lazyLoadingSwitch);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        images.forEach(img => {
          expect(img).toHaveAttribute('loading', 'lazy');
        });
      });
    });
  });

  describe('Zoom Functionality', () => {
    test('opens zoom modal when image is clicked', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures.slice(0, 1)} />);

      await waitFor(() => {
        const image = screen.getByRole('img');
        fireEvent.click(image.parentElement!); // Click the container
      });

      await waitFor(() => {
        expect(screen.getByTestId('zoom-modal')).toBeInTheDocument();
      });
    });

    test('disables zoom when setting is turned off', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures.slice(0, 1)} showSettings={true} />);

      // Disable zoom
      const zoomSwitch = screen.getByLabelText('Enable Zoom');
      fireEvent.click(zoomSwitch);

      await waitFor(() => {
        const imageContainer = screen.getByRole('img').parentElement!;
        expect(imageContainer).toHaveStyle('cursor: default');
      });
    });
  });

  describe('Filtering and Sorting', () => {
    test('filters by failure type correctly', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      // Filter to show only timing failures
      const filterSelect = screen.getByLabelText('Filter Type');
      fireEvent.mouseDown(filterSelect);
      
      await waitFor(() => {
        const timingOption = screen.getByText('Timing Only');
        fireEvent.click(timingOption);
      });

      await waitFor(() => {
        expect(screen.getByText('Frame 150')).toBeInTheDocument();
        expect(screen.queryByText('Frame 275')).not.toBeInTheDocument();
        expect(screen.queryByText('Frame 425')).not.toBeInTheDocument();
      });
    });

    test('sorts by different criteria', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      // Sort by frame number
      const sortSelect = screen.getByLabelText('Sort By');
      fireEvent.mouseDown(sortSelect);
      
      await waitFor(() => {
        const frameOption = screen.getByText('Frame Number');
        fireEvent.click(frameOption);
      });

      await waitFor(() => {
        const frames = screen.getAllByText(/Frame \d+/);
        expect(frames[0]).toHaveTextContent('Frame 425'); // Highest frame number first
      });
    });

    test('groups by failure type when enabled', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} showSettings={true} />);

      // Enable grouping
      const groupingSwitch = screen.getByLabelText('Group by Type');
      fireEvent.click(groupingSwitch);

      await waitFor(() => {
        expect(screen.getByText('Timing Failures (1)')).toBeInTheDocument();
        expect(screen.getByText('Accuracy Failures (1)')).toBeInTheDocument();
        expect(screen.getByText('System Failures (1)')).toBeInTheDocument();
      });
    });
  });

  describe('View Modes', () => {
    test('switches between grid and list view', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      // Switch to list view
      const viewModeButton = screen.getByRole('button', { name: /view/i });
      fireEvent.click(viewModeButton);

      await waitFor(() => {
        expect(screen.getByRole('list')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    test('provides proper alt text for images', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        images.forEach((img, index) => {
          expect(img).toHaveAttribute('alt', `Failure snapshot for frame ${mockFailures[index].frameNumber}`);
        });
      });
    });

    test('provides keyboard navigation support', async () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      await waitFor(() => {
        const buttons = screen.getAllByRole('button');
        buttons.forEach(button => {
          expect(button).not.toHaveAttribute('tabindex', '-1');
        });
      });
    });
  });

  describe('Error Recovery', () => {
    test('provides retry functionality on error', async () => {
      const mockRefresh = jest.fn();
      render(
        <FailureSnapshotDisplay 
          failures={[]} 
          error="Network error" 
          onRefresh={mockRefresh} 
        />
      );

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });

    test('handles image retry mechanism', async () => {
      // Start with error, then succeed on retry
      let shouldFail = true;
      global.Image = class {
        onload: (() => void) | null = null;
        onerror: (() => void) | null = null;
        src: string = '';
        
        constructor() {
          setTimeout(() => {
            if (shouldFail && this.onerror) {
              this.onerror();
            } else if (!shouldFail && this.onload) {
              this.onload();
            }
          }, 100);
        }
      } as any;

      render(<FailureSnapshotDisplay failures={mockFailures.slice(0, 1)} />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load image/)).toBeInTheDocument();
      });

      // Click retry
      shouldFail = false;
      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });
    });
  });

  describe('Performance Features', () => {
    test('limits displayed items to maxDisplayCount', () => {
      const manyFailures = Array.from({ length: 20 }, (_, i) => ({
        ...mockFailures[0],
        id: `failure_${i}`,
        frameNumber: i + 100
      }));

      render(<FailureSnapshotDisplay failures={manyFailures} maxDisplayCount={5} />);

      expect(screen.getByText('Showing first 5 of 20 failures.')).toBeInTheDocument();
    });

    test('shows performance stats in header', () => {
      render(<FailureSnapshotDisplay failures={mockFailures} />);

      expect(screen.getByText('Failure Snapshots (3 failures)')).toBeInTheDocument();
    });
  });

  describe('Integration with Backend Types', () => {
    test('handles different screenshot path formats', async () => {
      const failuresWithDifferentPaths: FailureSnapshotData[] = [
        {
          ...mockFailures[0],
          screenshot_path: 'http://example.com/full-url-image.jpg' // Full URL
        },
        {
          ...mockFailures[1],
          screenshot_path: '/api/relative-path-image.jpg' // Relative path
        }
      ];

      render(<FailureSnapshotDisplay failures={failuresWithDifferentPaths} baseUrl="http://localhost:8000" />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images[0]).toHaveAttribute('src', 'http://example.com/full-url-image.jpg');
        expect(images[1]).toHaveAttribute('src', 'http://localhost:8000/api/relative-path-image.jpg');
      });
    });

    test('handles missing screenshot paths gracefully', () => {
      const failureWithoutScreenshot: FailureSnapshotData[] = [
        {
          ...mockFailures[0],
          screenshot_path: '', // Empty path
        }
      ];

      render(<FailureSnapshotDisplay failures={failureWithoutScreenshot} />);

      expect(screen.getByText('No screenshot available for this failure')).toBeInTheDocument();
    });
  });
});