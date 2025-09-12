import React, { useState, useEffect } from 'react';
import { getServiceConfig, envConfig } from '../../utils/envConfig';
import logger from '../../utils/safeErrorLogger';

interface WebSocketConfigToggleProps {
  className?: string;
  onToggle?: (enabled: boolean) => void;
}

/**
 * WebSocket Configuration Toggle Component
 * 
 * Provides a UI control to enable/disable WebSocket connections
 * Shows current backend availability and connection status
 */
export const WebSocketConfigToggle: React.FC<WebSocketConfigToggleProps> = ({ 
  className = '', 
  onToggle 
}) => {
  const [socketConfig, setSocketConfig] = useState(() => getServiceConfig('socketio'));
  const [isEnabled, setIsEnabled] = useState(socketConfig.enabled);
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);

  // Check backend availability
  const checkBackendHealth = async () => {
    try {
      const response = await fetch(`${socketConfig.url.replace(':8001', ':8000')}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
        mode: 'cors'
      });
      setBackendAvailable(response.ok);
    } catch (error) {
      setBackendAvailable(false);
    }
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, [socketConfig.url]);

  const handleToggle = () => {
    const newEnabled = !isEnabled;
    setIsEnabled(newEnabled);
    onToggle?.(newEnabled);
    
    // Store preference in localStorage
    localStorage.setItem('websocket_enabled', String(newEnabled));
    
    logger.info(`WebSocket ${newEnabled ? 'enabled' : 'disabled'} by user`);
  };

  // Load saved preference on mount
  useEffect(() => {
    const savedPreference = localStorage.getItem('websocket_enabled');
    if (savedPreference !== null) {
      const enabled = savedPreference === 'true';
      setIsEnabled(enabled);
    }
  }, []);

  const getStatusColor = () => {
    if (backendAvailable === null) return 'text-gray-500';
    return backendAvailable ? 'text-green-600' : 'text-red-600';
  };

  const getStatusText = () => {
    if (backendAvailable === null) return 'Checking...';
    if (!backendAvailable) return 'Backend Unavailable';
    return isEnabled ? 'Enabled' : 'Disabled';
  };

  return (
    <div className={`flex items-center space-x-3 p-3 bg-gray-50 rounded-lg ${className}`}>
      <div className="flex items-center">
        <input
          type="checkbox"
          id="websocket-toggle"
          checked={isEnabled}
          onChange={handleToggle}
          disabled={backendAvailable === false}
          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
        />
        <label 
          htmlFor="websocket-toggle" 
          className="ml-2 text-sm font-medium text-gray-700 cursor-pointer"
        >
          WebSocket Connections
        </label>
      </div>
      
      <div className="flex items-center space-x-2">
        <div 
          className={`w-2 h-2 rounded-full ${
            backendAvailable === null 
              ? 'bg-gray-400' 
              : backendAvailable 
                ? (isEnabled ? 'bg-green-500' : 'bg-yellow-500')
                : 'bg-red-500'
          }`}
        />
        <span className={`text-xs ${getStatusColor()}`}>
          {getStatusText()}
        </span>
      </div>
      
      {backendAvailable === false && (
        <span className="text-xs text-gray-500">
          (Backend not available)
        </span>
      )}
      
      {process.env.NODE_ENV === 'development' && (
        <div className="text-xs text-gray-400">
          URL: {socketConfig.url}
        </div>
      )}
    </div>
  );
};

export default WebSocketConfigToggle;