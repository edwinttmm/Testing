import React, { createContext, useContext, useState, ReactNode, useCallback, useEffect } from 'react';
import {
  Alert,
  AlertTitle,
  IconButton,
  Box,
  Typography,
  Button,
  Collapse,
  Stack,
} from '@mui/material';
import {
  Close,
  ExpandMore,
  ExpandLess,
  ContentCopy,
} from '@mui/icons-material';

export type ErrorSeverity = 'error' | 'warning' | 'info' | 'success';

export interface ErrorNotification {
  id: string;
  message: string;
  severity: ErrorSeverity;
  title?: string;
  details?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  persistent?: boolean;
  autoHideDuration?: number;
  timestamp: Date;
}

interface ErrorNotificationContextType {
  notifications: ErrorNotification[];
  showError: (message: string, options?: Partial<ErrorNotification>) => void;
  showWarning: (message: string, options?: Partial<ErrorNotification>) => void;
  showSuccess: (message: string, options?: Partial<ErrorNotification>) => void;
  showInfo: (message: string, options?: Partial<ErrorNotification>) => void;
  hideNotification: (id: string) => void;
  clearAll: () => void;
}

const ErrorNotificationContext = createContext<ErrorNotificationContextType | undefined>(undefined);

export const useErrorNotification = () => {
  const context = useContext(ErrorNotificationContext);
  if (!context) {
    throw new Error('useErrorNotification must be used within an ErrorNotificationProvider');
  }
  return context;
};

interface ErrorNotificationProviderProps {
  children: ReactNode;
  maxNotifications?: number;
}

export const ErrorNotificationProvider: React.FC<ErrorNotificationProviderProps> = ({
  children,
  maxNotifications = 5,
}) => {
  const [notifications, setNotifications] = useState<ErrorNotification[]>([]);
  const [expandedNotifications, setExpandedNotifications] = useState<Set<string>>(new Set());

  const generateId = () => `notification_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  const addNotification = useCallback((notification: ErrorNotification) => {
    setNotifications(prev => {
      const newNotifications = [notification, ...prev];
      
      // Keep only the most recent notifications
      if (newNotifications.length > maxNotifications) {
        return newNotifications.slice(0, maxNotifications);
      }
      
      return newNotifications;
    });

    // Auto-hide non-persistent notifications
    if (!notification.persistent && notification.autoHideDuration !== 0) {
      const duration = notification.autoHideDuration ?? 6000;
      setTimeout(() => {
        hideNotification(notification.id);
      }, duration);
    }
  }, [maxNotifications]);

  const showError = useCallback((message: string, options: Partial<ErrorNotification> = {}) => {
    const notification: ErrorNotification = {
      id: generateId(),
      message,
      severity: 'error',
      timestamp: new Date(),
      persistent: true, // Errors are persistent by default
      ...options,
    };
    addNotification(notification);
  }, [addNotification]);

  const showWarning = useCallback((message: string, options: Partial<ErrorNotification> = {}) => {
    const notification: ErrorNotification = {
      id: generateId(),
      message,
      severity: 'warning',
      timestamp: new Date(),
      autoHideDuration: 8000,
      ...options,
    };
    addNotification(notification);
  }, [addNotification]);

  const showSuccess = useCallback((message: string, options: Partial<ErrorNotification> = {}) => {
    const notification: ErrorNotification = {
      id: generateId(),
      message,
      severity: 'success',
      timestamp: new Date(),
      autoHideDuration: 4000,
      ...options,
    };
    addNotification(notification);
  }, [addNotification]);

  const showInfo = useCallback((message: string, options: Partial<ErrorNotification> = {}) => {
    const notification: ErrorNotification = {
      id: generateId(),
      message,
      severity: 'info',
      timestamp: new Date(),
      autoHideDuration: 6000,
      ...options,
    };
    addNotification(notification);
  }, [addNotification]);

  const hideNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    setExpandedNotifications(prev => {
      const newSet = new Set(prev);
      newSet.delete(id);
      return newSet;
    });
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
    setExpandedNotifications(new Set());
  }, []);

  const toggleExpanded = useCallback((id: string) => {
    setExpandedNotifications(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  }, []);

  const copyToClipboard = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showSuccess('Copied to clipboard');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  }, [showSuccess]);

  // Global error handler for unhandled promise rejections
  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('Unhandled promise rejection:', event.reason);
      
      let message = 'An unexpected error occurred';
      let details = '';
      
      if (event.reason instanceof Error) {
        message = event.reason.message || message;
        details = event.reason.stack || '';
      } else if (typeof event.reason === 'string') {
        message = event.reason;
      } else if (event.reason && typeof event.reason === 'object') {
        message = event.reason.message || message;
        details = JSON.stringify(event.reason, null, 2);
      }
      
      showError(message, {
        title: 'Unhandled Error',
        details,
        persistent: true,
      });
      
      // Prevent the default browser behavior
      event.preventDefault();
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    
    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [showError]);

  const contextValue: ErrorNotificationContextType = {
    notifications,
    showError,
    showWarning,
    showSuccess,
    showInfo,
    hideNotification,
    clearAll,
  };

  return (
    <ErrorNotificationContext.Provider value={contextValue}>
      {children}
      
      {/* Render notifications */}
      <Box
        sx={{
          position: 'fixed',
          top: 80,
          right: 16,
          zIndex: 9999,
          maxWidth: 400,
        }}
      >
        <Stack spacing={1}>
          {notifications.map((notification) => {
            const isExpanded = expandedNotifications.has(notification.id);
            const hasDetails = Boolean(notification.details);
            
            return (
              <Alert
                key={notification.id}
                severity={notification.severity}
                sx={{
                  boxShadow: 3,
                  '& .MuiAlert-message': {
                    width: '100%',
                  },
                }}
                action={
                  <Box>
                    {hasDetails && (
                      <IconButton
                        size="small"
                        onClick={() => toggleExpanded(notification.id)}
                        sx={{ mr: 0.5 }}
                      >
                        {isExpanded ? <ExpandLess /> : <ExpandMore />}
                      </IconButton>
                    )}
                    <IconButton
                      size="small"
                      onClick={() => hideNotification(notification.id)}
                    >
                      <Close fontSize="small" />
                    </IconButton>
                  </Box>
                }
              >
                {notification.title && <AlertTitle>{notification.title}</AlertTitle>}
                
                <Typography variant="body2">
                  {notification.message}
                </Typography>
                
                {notification.action && (
                  <Button
                    size="small"
                    color="inherit"
                    onClick={notification.action.onClick}
                    sx={{ mt: 1 }}
                  >
                    {notification.action.label}
                  </Button>
                )}
                
                {hasDetails && (
                  <Collapse in={isExpanded}>
                    <Box sx={{ mt: 2, p: 1, bgcolor: 'rgba(0,0,0,0.1)', borderRadius: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="caption" fontWeight="bold">
                          Error Details:
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={() => copyToClipboard(notification.details || '')}
                          title="Copy to clipboard"
                        >
                          <ContentCopy fontSize="small" />
                        </IconButton>
                      </Box>
                      <Typography
                        variant="caption"
                        component="pre"
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.7rem',
                          overflow: 'auto',
                          maxHeight: '150px',
                          display: 'block',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-all',
                        }}
                      >
                        {notification.details}
                      </Typography>
                    </Box>
                  </Collapse>
                )}
                
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 1 }}
                >
                  {notification.timestamp.toLocaleTimeString()}
                </Typography>
              </Alert>
            );
          })}
        </Stack>
      </Box>
    </ErrorNotificationContext.Provider>
  );
};

export default ErrorNotificationProvider;