/**
 * Frontend Tests for Ground Truth Validation UI (Issue #3)
 *
 * Tests:
 * - Validation modal rendering
 * - "Start Anyway" flow
 * - API error handling
 * - User interaction flows
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Mock components (adjust imports based on actual structure)
import { ValidationModal } from '../components/ValidationModal';
import { TestExecutionPage } from '../pages/HILTestExecution';

// ===== MOCK SERVER =====

const server = setupServer(
  // Mock validation endpoint
  rest.get('/api/videos/:videoId/validate', (req, res, ctx) => {
    const { videoId } = req.params;

    // Simulate different validation scenarios
    if (videoId === 'valid-video-001') {
      return res(
        ctx.json({
          video_id: videoId,
          validation_status: 'passed',
          ground_truth_count: 10,
          warnings: []
        })
      );
    }

    if (videoId === 'missing-gt-video') {
      return res(
        ctx.json({
          video_id: videoId,
          validation_status: 'warning',
          ground_truth_count: 0,
          warnings: ['No ground truth objects found. Test results may be inaccurate.']
        })
      );
    }

    if (videoId === 'error-video') {
      return res(
        ctx.status(500),
        ctx.json({
          message: 'Internal server error during validation',
          status: 500
        })
      );
    }

    return res(
      ctx.json({
        video_id: videoId,
        validation_status: 'unknown',
        ground_truth_count: 0
      })
    );
  }),

  // Mock test session start endpoint
  rest.post('/api/test-sessions/start', (req, res, ctx) => {
    return res(
      ctx.json({
        session_id: 'test-session-001',
        status: 'running',
        message: 'Test session started successfully'
      })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());


// ===== VALIDATION MODAL TESTS =====

describe('ValidationModal Component', () => {

  test('renders validation modal with video information', () => {
    const mockVideo = {
      id: 'valid-video-001',
      filename: 'test_video.mp4',
      ground_truth_count: 10
    };

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={jest.fn()}
        onStartAnyway={jest.fn()}
      />
    );

    expect(screen.getByText(/test_video.mp4/i)).toBeInTheDocument();
    expect(screen.getByText(/10 ground truth objects/i)).toBeInTheDocument();
  });

  test('displays warning when ground truth is missing', async () => {
    const mockVideo = {
      id: 'missing-gt-video',
      filename: 'no_gt_video.mp4',
      ground_truth_count: 0
    };

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={jest.fn()}
        onStartAnyway={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/no ground truth/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/test results may be inaccurate/i)).toBeInTheDocument();
  });

  test('"Start Anyway" button triggers callback', async () => {
    const mockVideo = {
      id: 'missing-gt-video',
      filename: 'test_video.mp4',
      ground_truth_count: 0
    };

    const mockStartAnyway = jest.fn();

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={jest.fn()}
        onStartAnyway={mockStartAnyway}
      />
    );

    const startButton = screen.getByRole('button', { name: /start anyway/i });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(mockStartAnyway).toHaveBeenCalledTimes(1);
      expect(mockStartAnyway).toHaveBeenCalledWith(mockVideo);
    });
  });

  test('Close button dismisses modal', () => {
    const mockVideo = {
      id: 'valid-video-001',
      filename: 'test_video.mp4',
      ground_truth_count: 10
    };

    const mockClose = jest.fn();

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={mockClose}
        onStartAnyway={jest.fn()}
      />
    );

    const closeButton = screen.getByRole('button', { name: /close|cancel/i });
    fireEvent.click(closeButton);

    expect(mockClose).toHaveBeenCalledTimes(1);
  });

  test('handles API error gracefully', async () => {
    const mockVideo = {
      id: 'error-video',
      filename: 'error_video.mp4',
      ground_truth_count: 0
    };

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={jest.fn()}
        onStartAnyway={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});


// ===== TEST EXECUTION PAGE INTEGRATION =====

describe('Test Execution Page with Validation', () => {

  test('validates video before starting test', async () => {
    const mockVideo = {
      id: 'valid-video-001',
      filename: 'test_video.mp4',
      ground_truth_count: 10
    };

    render(<TestExecutionPage video={mockVideo} />);

    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // Should trigger validation
    await waitFor(() => {
      expect(screen.getByText(/validating/i)).toBeInTheDocument();
    });

    // After validation passes, should proceed
    await waitFor(() => {
      expect(screen.getByText(/test running/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('shows warning modal when ground truth missing', async () => {
    const mockVideo = {
      id: 'missing-gt-video',
      filename: 'no_gt_video.mp4',
      ground_truth_count: 0
    };

    render(<TestExecutionPage video={mockVideo} />);

    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // Should show validation warning modal
    await waitFor(() => {
      expect(screen.getByText(/no ground truth/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /start anyway/i })).toBeInTheDocument();
    });
  });

  test('"Start Anyway" proceeds with test despite warning', async () => {
    const mockVideo = {
      id: 'missing-gt-video',
      filename: 'no_gt_video.mp4',
      ground_truth_count: 0
    };

    render(<TestExecutionPage video={mockVideo} />);

    // Start test
    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // Wait for warning modal
    await waitFor(() => {
      expect(screen.getByText(/no ground truth/i)).toBeInTheDocument();
    });

    // Click "Start Anyway"
    const startAnywayButton = screen.getByRole('button', { name: /start anyway/i });
    fireEvent.click(startAnywayButton);

    // Should proceed with test
    await waitFor(() => {
      expect(screen.getByText(/test running/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('displays validation error when API fails', async () => {
    const mockVideo = {
      id: 'error-video',
      filename: 'error_video.mp4',
      ground_truth_count: 0
    };

    render(<TestExecutionPage video={mockVideo} />);

    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // Should show error message
    await waitFor(() => {
      expect(screen.getByText(/validation failed/i)).toBeInTheDocument();
      expect(screen.getByText(/internal server error/i)).toBeInTheDocument();
    });

    // Test should not start
    expect(screen.queryByText(/test running/i)).not.toBeInTheDocument();
  });
});


// ===== VALIDATION API RESPONSE STRUCTURE TESTS =====

describe('Validation API Response Structure', () => {

  test('API returns all required fields', async () => {
    const response = await fetch('/api/videos/valid-video-001/validate');
    const data = await response.json();

    expect(data).toHaveProperty('video_id');
    expect(data).toHaveProperty('validation_status');
    expect(data).toHaveProperty('ground_truth_count');
    expect(data).toHaveProperty('warnings');
  });

  test('API includes warnings array when ground truth missing', async () => {
    const response = await fetch('/api/videos/missing-gt-video/validate');
    const data = await response.json();

    expect(data.validation_status).toBe('warning');
    expect(data.ground_truth_count).toBe(0);
    expect(Array.isArray(data.warnings)).toBe(true);
    expect(data.warnings.length).toBeGreaterThan(0);
    expect(data.warnings[0]).toContain('No ground truth');
  });

  test('API returns 500 error with proper structure', async () => {
    const response = await fetch('/api/videos/error-video/validate');

    expect(response.status).toBe(500);

    const data = await response.json();
    expect(data).toHaveProperty('message');
    expect(data).toHaveProperty('status');
    expect(data.status).toBe(500);
  });
});


// ===== USER INTERACTION FLOW TESTS =====

describe('Complete User Interaction Flows', () => {

  test('Happy path: Valid video with ground truth', async () => {
    const mockVideo = {
      id: 'valid-video-001',
      filename: 'test_video.mp4',
      ground_truth_count: 10
    };

    const { container } = render(<TestExecutionPage video={mockVideo} />);

    // 1. User clicks Start Test
    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // 2. Validation passes (no modal shown)
    await waitFor(() => {
      expect(screen.queryByText(/warning/i)).not.toBeInTheDocument();
    });

    // 3. Test starts immediately
    await waitFor(() => {
      expect(screen.getByText(/test running/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('Warning path: Missing ground truth with override', async () => {
    const mockVideo = {
      id: 'missing-gt-video',
      filename: 'no_gt_video.mp4',
      ground_truth_count: 0
    };

    render(<TestExecutionPage video={mockVideo} />);

    // 1. User clicks Start Test
    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // 2. Warning modal appears
    await waitFor(() => {
      expect(screen.getByText(/no ground truth/i)).toBeInTheDocument();
      expect(screen.getByText(/test results may be inaccurate/i)).toBeInTheDocument();
    });

    // 3. User clicks "Start Anyway"
    const startAnywayButton = screen.getByRole('button', { name: /start anyway/i });
    fireEvent.click(startAnywayButton);

    // 4. Test starts with warning acknowledged
    await waitFor(() => {
      expect(screen.getByText(/test running/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('Error path: API error blocks test execution', async () => {
    const mockVideo = {
      id: 'error-video',
      filename: 'error_video.mp4',
      ground_truth_count: 0
    };

    render(<TestExecutionPage video={mockVideo} />);

    // 1. User clicks Start Test
    const startButton = screen.getByRole('button', { name: /start test/i });
    fireEvent.click(startButton);

    // 2. Error message displayed
    await waitFor(() => {
      expect(screen.getByText(/validation failed/i)).toBeInTheDocument();
    });

    // 3. Test does not start
    expect(screen.queryByText(/test running/i)).not.toBeInTheDocument();

    // 4. User can retry
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});


// ===== ACCESSIBILITY TESTS =====

describe('Validation Modal Accessibility', () => {

  test('modal has proper ARIA attributes', () => {
    const mockVideo = {
      id: 'valid-video-001',
      filename: 'test_video.mp4',
      ground_truth_count: 10
    };

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={jest.fn()}
        onStartAnyway={jest.fn()}
      />
    );

    const modal = screen.getByRole('dialog');
    expect(modal).toHaveAttribute('aria-modal', 'true');
    expect(modal).toHaveAttribute('aria-labelledby');
  });

  test('warning icon has accessible label', async () => {
    const mockVideo = {
      id: 'missing-gt-video',
      filename: 'no_gt_video.mp4',
      ground_truth_count: 0
    };

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={jest.fn()}
        onStartAnyway={jest.fn()}
      />
    );

    await waitFor(() => {
      const warningIcon = screen.getByRole('img', { name: /warning/i });
      expect(warningIcon).toBeInTheDocument();
    });
  });

  test('keyboard navigation works correctly', () => {
    const mockVideo = {
      id: 'valid-video-001',
      filename: 'test_video.mp4',
      ground_truth_count: 10
    };

    const mockClose = jest.fn();

    render(
      <ValidationModal
        video={mockVideo}
        isOpen={true}
        onClose={mockClose}
        onStartAnyway={jest.fn()}
      />
    );

    // Escape key should close modal
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape', code: 'Escape' });
    expect(mockClose).toHaveBeenCalled();
  });
});
