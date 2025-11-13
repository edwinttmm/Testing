/**
 * Error Boundary for SequentialVideoPlayer
 *
 * Catches React errors in the video player component tree and displays
 * user-friendly error messages instead of crashing the entire app.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import logger from '../utils/safeErrorLogger';

interface Props {
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class VideoPlayerErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
      errorInfo: null
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log the error to our logging service
    console.error('🚨 [VideoPlayerErrorBoundary] Caught error:', error);
    console.error('🚨 [VideoPlayerErrorBoundary] Error info:', errorInfo);
    console.error('🚨 [VideoPlayerErrorBoundary] Component stack:', errorInfo.componentStack);

    logger.error('Video player component crashed', error, {
      context: 'VideoPlayerErrorBoundary',
      componentStack: errorInfo.componentStack
    });

    this.setState({
      error,
      errorInfo
    });

    // Notify parent component if callback provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = () => {
    console.log('🔄 [VideoPlayerErrorBoundary] Resetting error boundary');
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem',
          backgroundColor: '#ffebee',
          borderRadius: '8px',
          border: '2px solid #f44336',
          margin: '1rem 0'
        }}>
          <h2 style={{ color: '#c62828', margin: '0 0 1rem 0' }}>
            🚨 Video Player Error
          </h2>
          <p style={{ color: '#666', marginBottom: '1rem' }}>
            The video player component encountered an error and could not continue.
          </p>

          {this.state.error && (
            <div style={{
              padding: '1rem',
              backgroundColor: 'white',
              borderRadius: '4px',
              marginBottom: '1rem',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              color: '#d32f2f',
              overflowX: 'auto'
            }}>
              <strong>Error:</strong> {this.state.error.toString()}
            </div>
          )}

          {this.state.errorInfo && (
            <details style={{ marginBottom: '1rem' }}>
              <summary style={{
                cursor: 'pointer',
                color: '#666',
                fontSize: '0.875rem',
                padding: '0.5rem',
                backgroundColor: 'white',
                borderRadius: '4px'
              }}>
                Show component stack trace
              </summary>
              <pre style={{
                marginTop: '0.5rem',
                padding: '1rem',
                backgroundColor: 'white',
                borderRadius: '4px',
                fontSize: '0.75rem',
                overflowX: 'auto',
                color: '#666'
              }}>
                {this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              onClick={this.handleReset}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#2196f3',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              Try Again
            </button>

            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#666',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              Reload Page
            </button>
          </div>

          <div style={{
            marginTop: '1rem',
            padding: '0.75rem',
            backgroundColor: '#fff3e0',
            borderRadius: '4px',
            fontSize: '0.875rem',
            color: '#e65100'
          }}>
            <strong>💡 Tip:</strong> Check the browser console (F12) for detailed error information.
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default VideoPlayerErrorBoundary;
