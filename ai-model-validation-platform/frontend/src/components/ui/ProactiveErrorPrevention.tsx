import React, { useState, useEffect, useRef, ReactNode } from 'react';
import {
  Box,
  Alert,
  AlertTitle,
  Typography,
  Button,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Fade,
  Collapse,
} from '@mui/material';
import {
  Warning as WarningIcon,
  Check as CheckIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  NetworkCheck as NetworkIcon,
  Speed as PerformanceIcon,
  Security as SecurityIcon,
  Storage as StorageIcon,
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';

// Health check interfaces
interface HealthCheck {
  id: string;
  name: string;
  description: string;
  category: HealthCategory;
  status: HealthStatus;
  severity: 'low' | 'medium' | 'high' | 'critical';
  lastChecked: Date;
  nextCheck?: Date;
  autoFix?: boolean;
  action?: {
    label: string;
    handler: () => Promise<boolean>;
  };
  details?: string;
  recommendation?: string;
}

enum HealthCategory {
  NETWORK = 'network',
  PERFORMANCE = 'performance',
  SECURITY = 'security',
  STORAGE = 'storage',
  VALIDATION = 'validation',
  COMPATIBILITY = 'compatibility'
}

enum HealthStatus {
  HEALTHY = 'healthy',
  WARNING = 'warning',
  ERROR = 'error',
  CHECKING = 'checking',
  UNKNOWN = 'unknown'
}

interface ProactiveErrorPreventionProps {
  children: ReactNode;
  enableAutoChecks?: boolean;
  checkInterval?: number; // minutes
  showHealthWidget?: boolean;
  enableAutoFix?: boolean;
  onIssueDetected?: (check: HealthCheck) => void;
  onIssueResolved?: (check: HealthCheck) => void;
}

const ProactiveErrorPrevention: React.FC<ProactiveErrorPreventionProps> = ({
  children,
  enableAutoChecks = true,
  checkInterval = 5,
  showHealthWidget = true,
  enableAutoFix = true,
  onIssueDetected,
  onIssueResolved,
}) => {
  const [healthChecks, setHealthChecks] = useState<HealthCheck[]>([]);
  const [isRunningChecks, setIsRunningChecks] = useState(false);
  const [showHealthDialog, setShowHealthDialog] = useState(false);
  const [overallHealth, setOverallHealth] = useState<HealthStatus>(HealthStatus.UNKNOWN);
  const [criticalIssues, setCriticalIssues] = useState<HealthCheck[]>([]);
  const [showCriticalAlert, setShowCriticalAlert] = useState(false);
  const checkIntervalRef = useRef<NodeJS.Timeout>();
  
  // Initialize health checks
  useEffect(() => {
    initializeHealthChecks();
    
    if (enableAutoChecks) {
      runHealthChecks();
      
      // Set up periodic checks
      checkIntervalRef.current = setInterval(() => {
        runHealthChecks();
      }, checkInterval * 60 * 1000);
    }

    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
      }
    };
  }, [enableAutoChecks, checkInterval]);

  // Monitor critical issues
  useEffect(() => {
    const critical = healthChecks.filter(
      check => check.severity === 'critical' && check.status === HealthStatus.ERROR
    );
    setCriticalIssues(critical);
    setShowCriticalAlert(critical.length > 0);
    
    // Update overall health
    const hasErrors = healthChecks.some(check => check.status === HealthStatus.ERROR);
    const hasWarnings = healthChecks.some(check => check.status === HealthStatus.WARNING);
    
    if (hasErrors) {
      setOverallHealth(HealthStatus.ERROR);
    } else if (hasWarnings) {
      setOverallHealth(HealthStatus.WARNING);
    } else if (healthChecks.length > 0) {
      setOverallHealth(HealthStatus.HEALTHY);
    }
  }, [healthChecks]);

  const initializeHealthChecks = () => {
    const checks: HealthCheck[] = [
      // Network connectivity
      {
        id: 'network-connectivity',
        name: 'Internet Connection',
        description: 'Check if internet connection is stable',
        category: HealthCategory.NETWORK,
        status: HealthStatus.UNKNOWN,
        severity: 'critical',
        lastChecked: new Date(),
        autoFix: false,
        action: {
          label: 'Test Connection',
          handler: async () => await testNetworkConnection()
        },
        recommendation: 'Ensure stable internet connection for best experience'
      },
      
      // API availability
      {
        id: 'api-availability',
        name: 'Service Availability',
        description: 'Check if backend services are responding',
        category: HealthCategory.NETWORK,
        status: HealthStatus.UNKNOWN,
        severity: 'high',
        lastChecked: new Date(),
        autoFix: false,
        action: {
          label: 'Check Services',
          handler: async () => {
            const check: HealthCheck = {
              id: 'api-availability',
              name: 'API Availability',
              description: 'Checking API availability...',
              category: HealthCategory.NETWORK,
              status: HealthStatus.CHECKING,
              severity: 'low',
              lastChecked: new Date(),
              autoFix: false
            };
            const result = await checkApiAvailability(check);
            return result.status === 'healthy';
          }
        }
      },

      // Browser performance
      {
        id: 'browser-performance',
        name: 'Browser Performance',
        description: 'Monitor memory usage and responsiveness',
        category: HealthCategory.PERFORMANCE,
        status: HealthStatus.UNKNOWN,
        severity: 'medium',
        lastChecked: new Date(),
        autoFix: true,
        action: {
          label: 'Optimize',
          handler: async () => await optimizeBrowserPerformance()
        },
        recommendation: 'Close unused tabs to improve performance'
      },

      // Local storage
      {
        id: 'local-storage',
        name: 'Local Storage',
        description: 'Check local storage availability and usage',
        category: HealthCategory.STORAGE,
        status: HealthStatus.UNKNOWN,
        severity: 'medium',
        lastChecked: new Date(),
        autoFix: true,
        action: {
          label: 'Clean Up',
          handler: async () => await cleanupLocalStorage()
        }
      },

      // Browser compatibility
      {
        id: 'browser-compatibility',
        name: 'Browser Compatibility',
        description: 'Verify browser supports required features',
        category: HealthCategory.COMPATIBILITY,
        status: HealthStatus.UNKNOWN,
        severity: 'high',
        lastChecked: new Date(),
        autoFix: false,
        recommendation: 'Update to a modern browser for full functionality'
      },

      // Security checks
      {
        id: 'security-context',
        name: 'Security Context',
        description: 'Verify secure connection and certificates',
        category: HealthCategory.SECURITY,
        status: HealthStatus.UNKNOWN,
        severity: 'high',
        lastChecked: new Date(),
        autoFix: false,
        recommendation: 'Always use HTTPS for secure data transmission'
      },

      // Form validation readiness
      {
        id: 'validation-readiness',
        name: 'Form Validation',
        description: 'Check form validation systems are working',
        category: HealthCategory.VALIDATION,
        status: HealthStatus.UNKNOWN,
        severity: 'low',
        lastChecked: new Date(),
        autoFix: true,
        action: {
          label: 'Test Validation',
          handler: async () => await testFormValidation()
        }
      }
    ];

    setHealthChecks(checks);
  };

  const runHealthChecks = async () => {
    setIsRunningChecks(true);
    
    const updatedChecks = await Promise.all(
      healthChecks.map(async (check) => {
        try {
          const result = await performHealthCheck(check);
          
          // Notify about issues
          if (result.status === HealthStatus.ERROR && check.status !== HealthStatus.ERROR) {
            onIssueDetected?.(result);
          } else if (result.status === HealthStatus.HEALTHY && check.status === HealthStatus.ERROR) {
            onIssueResolved?.(result);
          }
          
          // Auto-fix if enabled and available
          if (enableAutoFix && result.autoFix && result.status !== HealthStatus.HEALTHY && result.action) {
            try {
              const fixed = await result.action.handler();
              if (fixed) {
                result.status = HealthStatus.HEALTHY;
                result.details = 'Issue automatically resolved';
              }
            } catch (fixError) {
              console.warn(`Auto-fix failed for ${check.name}:`, fixError);
            }
          }
          
          return result;
        } catch (error) {
          return {
            ...check,
            status: HealthStatus.ERROR,
            details: `Check failed: ${error}`,
            lastChecked: new Date()
          };
        }
      })
    );
    
    setHealthChecks(updatedChecks);
    setIsRunningChecks(false);
  };

  const performHealthCheck = async (check: HealthCheck): Promise<HealthCheck> => {
    const updatedCheck = { ...check, lastChecked: new Date(), status: HealthStatus.CHECKING };

    switch (check.id) {
      case 'network-connectivity':
        return await checkNetworkConnectivity(updatedCheck);
      case 'api-availability':
        return await checkApiAvailability(updatedCheck);
      case 'browser-performance':
        return await checkBrowserPerformance(updatedCheck);
      case 'local-storage':
        return await checkLocalStorage(updatedCheck);
      case 'browser-compatibility':
        return await checkBrowserCompatibility(updatedCheck);
      case 'security-context':
        return await checkSecurityContext(updatedCheck);
      case 'validation-readiness':
        return await checkValidationReadiness(updatedCheck);
      default:
        return { ...updatedCheck, status: HealthStatus.UNKNOWN };
    }
  };

  // Health check implementations
  const checkNetworkConnectivity = async (check: HealthCheck): Promise<HealthCheck> => {
    try {
      const online = navigator.onLine;
      if (!online) {
        return {
          ...check,
          status: HealthStatus.ERROR,
          details: 'No internet connection detected'
        };
      }

      // Test actual connectivity
      const response = await fetch('/api/ping', { 
        method: 'HEAD',
        cache: 'no-cache',
        signal: AbortSignal.timeout(5000)
      });
      
      return {
        ...check,
        status: response.ok ? HealthStatus.HEALTHY : HealthStatus.WARNING,
        details: response.ok ? 'Connection is stable' : 'Connection is slow or unstable'
      };
    } catch (error) {
      return {
        ...check,
        status: HealthStatus.ERROR,
        details: 'Cannot reach servers'
      };
    }
  };

  const checkApiAvailability = async (check: HealthCheck): Promise<HealthCheck> => {
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        cache: 'no-cache',
        signal: AbortSignal.timeout(10000)
      });
      
      if (response.ok) {
        const data = await response.json();
        return {
          ...check,
          status: HealthStatus.HEALTHY,
          details: `All services operational (${response.status})`
        };
      } else {
        return {
          ...check,
          status: HealthStatus.WARNING,
          details: `Services responding with issues (${response.status})`
        };
      }
    } catch (error) {
      return {
        ...check,
        status: HealthStatus.ERROR,
        details: 'Backend services unavailable'
      };
    }
  };

  const checkBrowserPerformance = async (check: HealthCheck): Promise<HealthCheck> => {
    try {
      // Check memory usage
      const memInfo = (performance as Performance & { memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number; }}).memory;
      if (memInfo) {
        const usedPercent = (memInfo.usedJSHeapSize / memInfo.jsHeapSizeLimit) * 100;
        
        if (usedPercent > 90) {
          return {
            ...check,
            status: HealthStatus.ERROR,
            details: `High memory usage: ${usedPercent.toFixed(1)}%`
          };
        } else if (usedPercent > 70) {
          return {
            ...check,
            status: HealthStatus.WARNING,
            details: `Elevated memory usage: ${usedPercent.toFixed(1)}%`
          };
        }
      }

      return {
        ...check,
        status: HealthStatus.HEALTHY,
        details: 'Performance is optimal'
      };
    } catch (error) {
      return {
        ...check,
        status: HealthStatus.UNKNOWN,
        details: 'Cannot measure performance metrics'
      };
    }
  };

  const checkLocalStorage = async (check: HealthCheck): Promise<HealthCheck> => {
    try {
      // Test localStorage availability
      const testKey = '__health_check__';
      localStorage.setItem(testKey, 'test');
      localStorage.removeItem(testKey);

      // Check storage usage
      const used = new Blob(Object.values(localStorage)).size;
      const quota = 5 * 1024 * 1024; // Assume 5MB quota
      const usagePercent = (used / quota) * 100;

      if (usagePercent > 90) {
        return {
          ...check,
          status: HealthStatus.WARNING,
          details: `Storage nearly full: ${usagePercent.toFixed(1)}%`
        };
      } else if (usagePercent > 70) {
        return {
          ...check,
          status: HealthStatus.WARNING,
          details: `Storage usage high: ${usagePercent.toFixed(1)}%`
        };
      }

      return {
        ...check,
        status: HealthStatus.HEALTHY,
        details: `Storage available: ${(100 - usagePercent).toFixed(1)}%`
      };
    } catch (error) {
      return {
        ...check,
        status: HealthStatus.ERROR,
        details: 'Local storage unavailable'
      };
    }
  };

  const checkBrowserCompatibility = async (check: HealthCheck): Promise<HealthCheck> => {
    const requiredFeatures = [
      'fetch',
      'Promise',
      'localStorage',
      'WebSocket',
      'FileReader'
    ];

    const missingFeatures = requiredFeatures.filter(feature => !(feature in window));
    
    if (missingFeatures.length > 0) {
      return {
        ...check,
        status: HealthStatus.ERROR,
        details: `Missing features: ${missingFeatures.join(', ')}`
      };
    }

    // Check for modern features
    const modernFeatures = [
      'IntersectionObserver',
      'ResizeObserver',
      'AbortController'
    ];

    const missingModernFeatures = modernFeatures.filter(feature => !(feature in window));
    
    if (missingModernFeatures.length > 0) {
      return {
        ...check,
        status: HealthStatus.WARNING,
        details: `Limited functionality: missing ${missingModernFeatures.join(', ')}`
      };
    }

    return {
      ...check,
      status: HealthStatus.HEALTHY,
      details: 'Browser is fully compatible'
    };
  };

  const checkSecurityContext = async (check: HealthCheck): Promise<HealthCheck> => {
    const isSecure = location.protocol === 'https:';
    const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    
    if (!isSecure && !isLocalhost) {
      return {
        ...check,
        status: HealthStatus.ERROR,
        details: 'Insecure connection detected'
      };
    }

    // Check for mixed content issues
    if (isSecure && document.querySelectorAll('img[src^="http:"], script[src^="http:"]').length > 0) {
      return {
        ...check,
        status: HealthStatus.WARNING,
        details: 'Mixed content detected'
      };
    }

    return {
      ...check,
      status: HealthStatus.HEALTHY,
      details: isSecure ? 'Secure HTTPS connection' : 'Local development environment'
    };
  };

  const checkValidationReadiness = async (check: HealthCheck): Promise<HealthCheck> => {
    try {
      // Test basic validation functionality
      const testInput = document.createElement('input');
      testInput.type = 'email';
      testInput.required = true;
      testInput.value = 'invalid-email';
      
      const isValid = testInput.validity.valid;
      const hasValidationAPI = 'validity' in testInput;
      
      if (!hasValidationAPI) {
        return {
          ...check,
          status: HealthStatus.WARNING,
          details: 'HTML5 validation not fully supported'
        };
      }

      return {
        ...check,
        status: HealthStatus.HEALTHY,
        details: 'Form validation system ready'
      };
    } catch (error) {
      return {
        ...check,
        status: HealthStatus.ERROR,
        details: 'Validation system unavailable'
      };
    }
  };

  // Auto-fix implementations
  const testNetworkConnection = async (): Promise<boolean> => {
    try {
      await fetch('/api/ping', { method: 'HEAD', cache: 'no-cache' });
      return true;
    } catch {
      return false;
    }
  };

  const optimizeBrowserPerformance = async (): Promise<boolean> => {
    try {
      // Clear some caches
      if ('caches' in window) {
        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames.map(name => caches.delete(name))
        );
      }
      
      // Force garbage collection if available
      if ((window as Window & { gc?: () => void }).gc) {
        (window as Window & { gc: () => void }).gc();
      }
      
      return true;
    } catch {
      return false;
    }
  };

  const cleanupLocalStorage = async (): Promise<boolean> => {
    try {
      // Remove old or large items
      const itemsToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.includes('cache_') && new Date().getTime() - parseInt(key.split('_')[1]) > 86400000) {
          itemsToRemove.push(key);
        }
      }
      
      itemsToRemove.forEach(key => localStorage.removeItem(key));
      return true;
    } catch {
      return false;
    }
  };

  const testFormValidation = async (): Promise<boolean> => {
    return 'validity' in document.createElement('input');
  };

  const getHealthIcon = (status: HealthStatus) => {
    switch (status) {
      case HealthStatus.HEALTHY:
        return <CheckIcon color="success" />;
      case HealthStatus.WARNING:
        return <WarningIcon color="warning" />;
      case HealthStatus.ERROR:
        return <ErrorIcon color="error" />;
      case HealthStatus.CHECKING:
        return <RefreshIcon className="spinning" />;
      default:
        return <InfoIcon />;
    }
  };

  const getCategoryIcon = (category: HealthCategory) => {
    switch (category) {
      case HealthCategory.NETWORK:
        return <NetworkIcon />;
      case HealthCategory.PERFORMANCE:
        return <PerformanceIcon />;
      case HealthCategory.SECURITY:
        return <SecurityIcon />;
      case HealthCategory.STORAGE:
        return <StorageIcon />;
      default:
        return <SettingsIcon />;
    }
  };

  const renderHealthWidget = () => {
    if (!showHealthWidget) return null;

    const errorCount = healthChecks.filter(c => c.status === HealthStatus.ERROR).length;
    const warningCount = healthChecks.filter(c => c.status === HealthStatus.WARNING).length;

    return (
      <Box
        sx={{
          position: 'fixed',
          bottom: 16,
          right: 16,
          zIndex: 1000,
        }}
      >
        <Card 
          sx={{ 
            minWidth: 200,
            cursor: 'pointer',
            border: overallHealth === HealthStatus.ERROR ? 2 : 1,
            borderColor: overallHealth === HealthStatus.ERROR ? 'error.main' : 'divider'
          }}
          onClick={() => setShowHealthDialog(true)}
        >
          <CardContent sx={{ pb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              {getHealthIcon(overallHealth)}
              <Typography variant="h6" sx={{ ml: 1 }}>
                System Health
              </Typography>
            </Box>
            
            {isRunningChecks && (
              <LinearProgress sx={{ mb: 1 }} />
            )}
            
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {errorCount > 0 && (
                <Chip 
                  label={`${errorCount} Error${errorCount > 1 ? 's' : ''}`} 
                  color="error" 
                  size="small" 
                />
              )}
              {warningCount > 0 && (
                <Chip 
                  label={`${warningCount} Warning${warningCount > 1 ? 's' : ''}`} 
                  color="warning" 
                  size="small" 
                />
              )}
              {errorCount === 0 && warningCount === 0 && (
                <Chip 
                  label="All Good" 
                  color="success" 
                  size="small" 
                />
              )}
            </Box>
          </CardContent>
        </Card>
      </Box>
    );
  };

  const renderCriticalAlert = () => {
    return (
      <Collapse in={showCriticalAlert}>
        <Alert
          severity="error"
          action={
            <IconButton
              aria-label="close"
              color="inherit"
              size="small"
              onClick={() => setShowCriticalAlert(false)}
            >
              <CloseIcon fontSize="inherit" />
            </IconButton>
          }
          sx={{ mb: 2 }}
        >
          <AlertTitle>Critical Issues Detected</AlertTitle>
          {criticalIssues.map(issue => (
            <Typography key={issue.id} variant="body2">
              • {issue.name}: {issue.details}
            </Typography>
          ))}
          <Button 
            size="small" 
            color="inherit" 
            onClick={() => setShowHealthDialog(true)}
            sx={{ mt: 1 }}
          >
            View Details
          </Button>
        </Alert>
      </Collapse>
    );
  };

  const renderHealthDialog = () => {
    return (
      <Dialog open={showHealthDialog} onClose={() => setShowHealthDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          System Health Check
          <IconButton onClick={() => setShowHealthDialog(false)}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 2 }}>
            {isRunningChecks && (
              <LinearProgress sx={{ mb: 2 }} />
            )}
            
            <List>
              {healthChecks.map((check) => (
                <ListItem key={check.id} divider>
                  <ListItemIcon>
                    {getCategoryIcon(check.category)}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {check.name}
                        {getHealthIcon(check.status)}
                        <Chip 
                          label={check.severity} 
                          size="small" 
                          color={check.severity === 'critical' ? 'error' : 
                                 check.severity === 'high' ? 'warning' : 'default'} 
                        />
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {check.description}
                        </Typography>
                        {check.details && (
                          <Typography variant="caption" color="text.secondary">
                            {check.details}
                          </Typography>
                        )}
                        {check.recommendation && check.status !== HealthStatus.HEALTHY && (
                          <Typography variant="caption" color="primary">
                            💡 {check.recommendation}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                  {check.action && check.status !== HealthStatus.HEALTHY && (
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => check.action!.handler()}
                    >
                      {check.action.label}
                    </Button>
                  )}
                </ListItem>
              ))}
            </List>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => runHealthChecks()} disabled={isRunningChecks}>
            {isRunningChecks ? 'Running...' : 'Run Checks'}
          </Button>
          <Button onClick={() => setShowHealthDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <>
      {renderCriticalAlert()}
      {children}
      {renderHealthWidget()}
      {renderHealthDialog()}

      <style>{`
        .spinning {
          animation: spin 2s linear infinite;
        }
        
        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </>
  );
};

export default ProactiveErrorPrevention;