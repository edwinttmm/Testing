import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { setupGlobalErrorHandling } from './utils/globalErrorHandler';
import { configurationManager, waitForConfig } from './utils/configurationManager';

// Initialize configuration manager FIRST
console.log('🔧 Starting configuration initialization...');

// Initialize global error handling
setupGlobalErrorHandling();

// Wait for configuration to be ready before rendering React app
waitForConfig().then(() => {
  console.log('✅ Configuration ready, starting React app...');
  
  const root = ReactDOM.createRoot(
    document.getElementById('root') as HTMLElement
  );
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}).catch(error => {
  console.error('❌ Configuration initialization failed:', error);
  
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
