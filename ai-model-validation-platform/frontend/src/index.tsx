import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { setupGlobalErrorHandling } from './utils/globalErrorHandler';
import { setupGlobalUploadErrorHandler } from './utils/uploadPromiseHandler';
import { waitForConfig } from './utils/configurationManager';
import { initializeLogging } from './config/logging.config';
import { getLogger } from './services/logger';
import { setupGlobalLogging } from './utils/loggingUtils';

// Initialize logging system FIRST
initializeLogging();
setupGlobalLogging();

const initLogger = getLogger('initialization');

// Initialize configuration manager FIRST
initLogger.info('Starting configuration initialization');

// Initialize global error handling
setupGlobalErrorHandling();
setupGlobalUploadErrorHandler();

// Wait for configuration to be ready before rendering React app
waitForConfig().then(() => {
  initLogger.info('Configuration ready, starting React app');
  
  const root = ReactDOM.createRoot(
    document.getElementById('root') as HTMLElement
  );
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}).catch(error => {
  initLogger.error('Configuration initialization failed', {
    action: 'config_init_error',
    metadata: {
      errorMessage: error.message,
      errorName: error.name
    }
  }, error);
  
  // Show error to user
  document.body.innerHTML = `
    <div style="padding: 20px; text-align: center; font-family: Arial, sans-serif;">
      <h2 style="color: #d32f2f;">Configuration Error</h2>
      <p>Failed to initialize application configuration.</p>
      <p>Error: ${error.message}</p>
      <button onclick="location.reload()" style="padding: 10px 20px; margin-top: 20px; cursor: pointer;">
        Retry
      </button>
    </div>
  `;
});

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
