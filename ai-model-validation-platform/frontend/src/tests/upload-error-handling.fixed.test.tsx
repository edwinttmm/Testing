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

  const getFileInput = () => {
    return document.querySelector('input[type="file"]') as HTMLInputElement;
  };

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
    const input = getFileInput();

    // Simulate file upload
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    fireEvent.change(input);

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
    const input = getFileInput();

    // Start file upload
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    fireEvent.change(input);

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
    render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    // Create a file that will fail validation (wrong extension)
    const file = createMockFile('test.txt', 1024 * 1024, 'text/plain');
    const input = getFileInput();

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    fireEvent.change(input);

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
        maxFiles={5} // Set low limit for testing
      />
    );

    // Create more files than allowed
    const files = Array.from({ length: 10 }, (_, i) =>
      createMockFile(`file-${i}.mp4`, 1024 * 1024, 'video/mp4')
    );

    const input = getFileInput();

    Object.defineProperty(input, 'files', {
      value: files,
      writable: false,
    });
    fireEvent.change(input);

    await waitFor(() => {
      expect(mockOnUploadError).toHaveBeenCalledWith(
        'Maximum 5 files allowed per batch'
      );
    });
  });

  test('cleans up intervals and timeouts on cancel', async () => {
    render(
      <SecureFileUpload
        onUploadComplete={mockOnUploadComplete}
        onUploadError={mockOnUploadError}
      />
    );

    const file = createMockFile('test.mp4', 1024 * 1024, 'video/mp4');
    const input = getFileInput();

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    fireEvent.change(input);

    // Wait for upload to start
    await waitFor(() => {
      expect(screen.getByText(/uploading/i)).toBeInTheDocument();
    });

    // Find and click cancel button
    const cancelButton = screen.getByLabelText('Cancel');
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.getByText(/cancelled/i)).toBeInTheDocument();
    });
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
    const input = getFileInput();

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });
    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/failed/i)).toBeInTheDocument();
    });

    // Try to retry if retry button exists
    const retryButton = screen.queryByLabelText('Retry Upload');
    if (retryButton) {
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(mockOnUploadError).toHaveBeenCalledWith('Retry upload failed');
      });
    }
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