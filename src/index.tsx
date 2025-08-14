/**
 * Main application entry point
 * Demonstrates GPU detection and image processing capabilities
 */

import React from 'react';
import { createRoot } from 'react-dom/client';
import { ImageProcessor } from './components/ImageProcessor';
import { useImageProcessor } from './hooks/useImageProcessor';
import './styles/main.css';

// Main application component
const App: React.FC = () => {
  const {
    processor,
    isLoading,
    isInitialized,
    error,
    gpuCapabilities,
    availableLibraries,
    processingHistory
  } = useImageProcessor({
    autoInitialize: true,
    onProcessingEvent: (event) => {
      console.log('Processing event:', event);
    }
  });

  return (
    <div className="app">
      <header className="app-header">
        <h1>GPU Image Processing System</h1>
        <p>
          Automatic GPU detection with seamless CPU fallback for image processing
        </p>
      </header>

      <main className="app-main">
        {/* System Status */}
        <section className="system-status">
          <h2>System Status</h2>
          <div className="status-grid">
            <div className="status-item">
              <label>Initialization:</label>
              <span className={`status ${isInitialized ? 'success' : 'pending'}`}>
                {isLoading ? 'Loading...' : isInitialized ? 'Ready' : 'Not Ready'}
              </span>
            </div>
            
            {processor && (
              <div className="status-item">
                <label>Active Library:</label>
                <span className="library-name">{processor.library}</span>
                <span className={`acceleration ${processor.isGPUAccelerated ? 'gpu' : 'cpu'}`}>
                  ({processor.isGPUAccelerated ? 'GPU' : 'CPU'})
                </span>
              </div>
            )}

            {gpuCapabilities && (
              <>
                <div className="status-item">
                  <label>GPU Available:</label>
                  <span className={`status ${gpuCapabilities.hasGPU ? 'success' : 'warning'}`}>
                    {gpuCapabilities.hasGPU ? 'Yes' : 'No'}
                  </span>
                </div>
                
                <div className="status-item">
                  <label>WebGL Support:</label>
                  <span className="webgl-support">
                    {gpuCapabilities.hasWebGL2 ? 'WebGL2' : 
                     gpuCapabilities.hasWebGL ? 'WebGL' : 'None'}
                  </span>
                </div>
                
                <div className="status-item">
                  <label>Platform:</label>
                  <span className="platform">{gpuCapabilities.platform}</span>
                </div>
                
                <div className="status-item">
                  <label>OS:</label>
                  <span className="os">{gpuCapabilities.os}</span>
                </div>

                {gpuCapabilities.renderer && (
                  <div className="status-item">
                    <label>GPU Renderer:</label>
                    <span className="renderer" title={gpuCapabilities.renderer}>
                      {gpuCapabilities.renderer.length > 30 
                        ? `${gpuCapabilities.renderer.substring(0, 30)}...`
                        : gpuCapabilities.renderer
                      }
                    </span>
                  </div>
                )}
              </>
            )}

            {error && (
              <div className="status-item error">
                <label>Error:</label>
                <span className="error-message">{error}</span>
              </div>
            )}
          </div>
        </section>

        {/* Available Libraries */}
        {availableLibraries.length > 0 && (
          <section className="libraries-section">
            <h2>Available Libraries</h2>
            <div className="libraries-grid">
              {availableLibraries.map((library) => (
                <div 
                  key={library.name} 
                  className={`library-card ${library.loaded ? 'loaded' : 'failed'} ${
                    processor?.library === library.name.toLowerCase().replace('.js', '') ? 'active' : ''
                  }`}
                >
                  <div className="library-header">
                    <h3>{library.name}</h3>
                    <span className={`status-indicator ${library.loaded ? 'success' : 'error'}`}>
                      {library.loaded ? '✓' : '✗'}
                    </span>
                  </div>
                  
                  {library.loaded && (
                    <div className="library-details">
                      {library.version && (
                        <div className="detail">
                          <label>Version:</label>
                          <span>{library.version}</span>
                        </div>
                      )}
                      
                      {library.backend && (
                        <div className="detail">
                          <label>Backend:</label>
                          <span className={`backend ${library.backend.toLowerCase()}`}>
                            {library.backend}
                          </span>
                        </div>
                      )}

                      {processor?.library === library.name.toLowerCase().replace('.js', '') && (
                        <div className="active-indicator">
                          <span>ACTIVE</span>
                        </div>
                      )}
                    </div>
                  )}

                  {!library.loaded && library.error && (
                    <div className="library-error">
                      <small>{library.error}</small>
                    </div>
                  )}

                  {/* Capabilities */}
                  <div className="capabilities">
                    <h4>Capabilities</h4>
                    <div className="capability-tags">
                      {Object.entries(library.capabilities).map(([capability, supported]) => (
                        <span 
                          key={capability}
                          className={`capability-tag ${supported ? 'supported' : 'unsupported'}`}
                        >
                          {capability.replace(/([A-Z])/g, ' $1').toLowerCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Performance History */}
        {processingHistory.length > 0 && (
          <section className="performance-section">
            <h2>Recent Processing History</h2>
            <div className="history-list">
              {processingHistory.slice(-5).reverse().map((event, index) => (
                <div key={index} className={`history-item ${event.type}`}>
                  <div className="event-type">{event.type}</div>
                  {event.result && (
                    <div className="event-details">
                      <span className="library">{event.result.library}</span>
                      <span className="backend">({event.result.backend})</span>
                      {event.result.processingTime > 0 && (
                        <span className="time">{event.result.processingTime}ms</span>
                      )}
                      <span className={`status ${event.result.success ? 'success' : 'error'}`}>
                        {event.result.success ? '✓' : '✗'}
                      </span>
                    </div>
                  )}
                  {event.error && (
                    <div className="event-error">{event.error}</div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Main Image Processor Component */}
        <section className="processor-section">
          <h2>Image Processing Interface</h2>
          <ImageProcessor
            className="main-processor"
            enableDragDrop={true}
            enablePreview={true}
            showControls={true}
            showCapabilities={false} // We're showing capabilities above
            maxWidth={600}
            maxHeight={400}
            onImageLoaded={(imageData) => {
              console.log('Image loaded:', {
                width: imageData.width,
                height: imageData.height,
                channels: imageData.channels,
                format: imageData.format
              });
            }}
            onProcessingComplete={(result) => {
              console.log('Processing completed:', result);
            }}
            onError={(error) => {
              console.error('Processing error:', error);
            }}
          />
        </section>

        {/* Environment Information */}
        <section className="environment-info">
          <h2>Environment Information</h2>
          <div className="env-grid">
            <div className="env-item">
              <label>Node Environment:</label>
              <span>{process.env.NODE_ENV}</span>
            </div>
            
            <div className="env-item">
              <label>Force CPU Only:</label>
              <span>{process.env.REACT_APP_FORCE_CPU_ONLY || 'false'}</span>
            </div>
            
            <div className="env-item">
              <label>Preferred Backend:</label>
              <span>{process.env.REACT_APP_PREFERRED_BACKEND || 'auto'}</span>
            </div>
            
            <div className="env-item">
              <label>Debug Mode:</label>
              <span>{process.env.REACT_APP_DEBUG_GPU_INFO || 'false'}</span>
            </div>

            <div className="env-item">
              <label>MINGW64 Compatibility:</label>
              <span>{process.env.MINGW64_COMPAT || 'false'}</span>
            </div>
          </div>
        </section>
      </main>

      <footer className="app-footer">
        <p>
          GPU Image Processing System - Supports TensorFlow.js, OpenCV.js, Jimp, Sharp, and Canvas API
        </p>
        <div className="footer-links">
          <a href="https://github.com/yourusername/gpu-image-processing-system" target="_blank" rel="noopener noreferrer">
            GitHub Repository
          </a>
          <span>•</span>
          <a href="#documentation">Documentation</a>
          <span>•</span>
          <a href="#api-reference">API Reference</a>
        </div>
      </footer>
    </div>
  );
};

// Initialize React application
const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element not found');
}

const root = createRoot(container);
root.render(<App />);