import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SecureFileUpload from '../components/SecureFileUpload';
import UploadErrorBoundary from '../components/ui/UploadErrorBoundary';

// Mock file for testing
const createMockFile = (name: string, size: number, type: string): File => {
  const file = new File([''], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

describe('Upload Error Handling', () => {
  let mockOnUploadComplete: jest.Mock;
  let mockOnUploadError: jest.Mock;

  beforeEach(() => {
    mockOnUploadComplete = jest.fn();
    mockOnUploadError = jest.fn();
    
    // Clear console errors for clean testing
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('handles upload completion callback errors gracefully', async () => {
    // Mock callback that throws an error
    const errorCallback = jest.fn().mockImplementation(() => {
      throw new Error('Callback error');
    });

    render(
      <UploadErrorBoundary>
        <SecureFileUpload
          onUploadComplete={errorCallback}
          onUploadError={mockOnUploadError}
        />
      </UploadErrorBoundary>
    );

    const file = createMockFile('test.mp4', 1024 * 1024, 'video/mp4');
    const input = screen.getByRole('button', { hidden: true });

    // Simulate file upload
    fireEvent.change(input, { target: { files: [file] } });

    // Wait for upload to complete and error to be handled
    await waitFor(() => {
      expect(mockOnUploadError).toHaveBeenCalledWith('Failed to process upload completion');
    }, { timeout: 8000 });
  });

  test('prevents memory leaks on component unmount', async () => {
    const { unmount } = render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    const file = createMockFile('test.mp4', 1024 * 1024, 'video/mp4');
    const input = screen.getByRole('button', { hidden: true });

    // Start file upload
    fireEvent.change(input, { target: { files: [file] } });

    // Wait a moment for upload to start
    await waitFor(() => {
      expect(screen.getByText(/validating/i)).toBeInTheDocument();
    });

    // Unmount component while upload is in progress
    unmount();

    // Wait to ensure no memory leaks or errors after unmount
    await new Promise(resolve => setTimeout(resolve, 1000));

    // No callbacks should be called after unmount
    expect(mockOnUploadComplete).not.toHaveBeenCalled();
  });

  test('handles promise rejections in validation', async () => {
    // Mock validateFileSecurely to reject
    jest.spyOn(global, 'FileReader').mockImplementation(() => {
      const fr = new FileReader();
      setTimeout(() => {
        const progressEvent = Object.assign(new Event('error'), {
          lengthComputable: true,
          loaded: 0,
          total: 0
        }) as ProgressEvent<FileReader>;
        fr.onerror?.(progressEvent);
      }, 0);
      return fr;
    });

    render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    const file = createMockFile('test.mp4', 1024 * 1024, 'video/mp4');
    const input = screen.getByRole('button', { hidden: true });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/failed/i)).toBeInTheDocument();
    });
  });

  test('error boundary catches upload component errors', () => {
    const ErrorComponent = () => {
      throw new Error('Component error');
    };

    render(
      <UploadErrorBoundary>
        <ErrorComponent />
      </UploadErrorBoundary>
    );

    expect(screen.getByText(/Upload Component Error/i)).toBeInTheDocument();
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
  });

  test('handles rate limiting gracefully', async () => {
    render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    // Create multiple large files to trigger rate limiting
    const largeFiles = Array.from({ length: 25 }, (_, i) =>
      createMockFile(`large-file-${i}.mp4`, 50 * 1024 * 1024, 'video/mp4')
    );

    const input = screen.getByRole('button', { hidden: true });

    fireEvent.change(input, { target: { files: largeFiles } });

    await waitFor(() => {
      expect(mockOnUploadError).toHaveBeenCalledWith(
        expect.stringContaining('Rate limit exceeded')
      );
    });
  });

  test('cleans up intervals and timeouts on cancel', async () => {
    const { unmount } = render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    const file = createMockFile('test.mp4', 1024 * 1024, 'video/mp4');
    const input = screen.getByRole('button', { hidden: true });

    fireEvent.change(input, { target: { files: [file] } });

    // Wait for upload to start
    await waitFor(() => {
      expect(screen.getByText(/uploading/i)).toBeInTheDocument();
    });

    // Find and click cancel button
    const cancelButton = screen.getByTitle('Cancel');
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.getByText(/cancelled/i)).toBeInTheDocument();
    });

    // Unmount to ensure cleanup
    unmount();

    // No errors should occur after cleanup
    await new Promise(resolve => setTimeout(resolve, 500));
  });

  test('handles retry upload failures', async () => {
    render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    // Create a file that will fail validation
    const file = createMockFile('test.exe', 1024, 'application/x-executable');
    const input = screen.getByRole('button', { hidden: true });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/failed/i)).toBeInTheDocument();
    });

    // Try to retry
    const retryButton = screen.getByTitle('Retry Upload');
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(mockOnUploadError).toHaveBeenCalledWith('Retry upload failed');
    });
  });
});

describe('Upload Promise Handling', () => {
  test('setupGlobalUploadErrorHandler prevents unhandled rejections', () => {
    const { setupGlobalUploadErrorHandler } = require('../utils/uploadPromiseHandler');
    
    // Mock window.addEventListener
    const originalAddEventListener = window.addEventListener;
    const mockAddEventListener = jest.fn();
    window.addEventListener = mockAddEventListener;
    
    // Call the setup function
    setupGlobalUploadErrorHandler();
    
    // Verify the handler was registered
    expect(mockAddEventListener).toHaveBeenCalledWith(
      'unhandledrejection',
      expect.any(Function)
    );
    
    // Restore original
    window.addEventListener = originalAddEventListener;
  });
});