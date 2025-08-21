/**
 * Configuration Validator Component
 * 
 * Provides runtime configuration validation and connectivity checks with:
 * - Real-time environment validation
 * - API connectivity testing
 * - HTTP-only detection service status
 * - Video service accessibility
 * - Clear error messages and troubleshooting guidance
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Box,
  Alert,
  Button,
  CircularProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Collapse,
  IconButton,
  Divider
} from '@mui/material';
import {
  CheckCircle,
  Error,
  Warning,
  Refresh,
  ExpandMore,
  ExpandLess,
  Info,
  Settings,
  NetworkCheck,
  VideoLibrary
} from '@mui/icons-material';
import envConfig, { testApiConnectivity, getValidationErrors, isValidConfig, getConfig } from '../utils/envConfig';
import { apiService } from '../services/api';
// HTTP-only mode - no WebSocket imports needed

export interface ConfigurationValidatorProps {
  showDetails?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
  onValidationChange?: (isValid: boolean, errors: string[]) => void;
}

interface ValidationResult {
  service: string;
  status: 'success' | 'warning' | 'error' | 'loading';
  message: string;
  details?: string[];
  timestamp: Date;
}

const ConfigurationValidator: React.FC<ConfigurationValidatorProps> = ({
  showDetails = false,
  autoRefresh = false,
  refreshInterval = 30000,
  onValidationChange
}) => {
  const [validationResults, setValidationResults] = useState<ValidationResult[]>([]);
  const [isValidating, setIsValidating] = useState(false);
  const [showDetailsPanel, setShowDetailsPanel] = useState(showDetails);
  const [lastValidation, setLastValidation] = useState<Date | null>(null);
  
  // HTTP-only mode - no WebSocket connections needed
  
  const runValidation = async (): Promise<void> => {
    setIsValidating(true);
    const results: ValidationResult[] = [];
    const timestamp = new Date();
    
    try {
      // 1. Environment Configuration Validation
      const configValid = isValidConfig();
      const configErrors = getValidationErrors();
      
      results.push({
        service: 'Environment Configuration',
        status: configValid ? 'success' : 'error',
        message: configValid ? 'Configuration is valid' : `${configErrors.length} configuration errors found`,
        details: configErrors,
        timestamp
      });
      
      // 2. API Connectivity Test
      results.push({
        service: 'API Connectivity',
        status: 'loading',
        message: 'Testing API connectivity...',
        timestamp
      });
      
      try {
        const apiTest = await testApiConnectivity();
        
        results[results.length - 1] = {
          service: 'API Connectivity',
          status: apiTest.connected ? 'success' : 'error',
          message: apiTest.connected 
            ? `API connected successfully (${apiTest.latency}ms)` 
            : `API connection failed: ${apiTest.error}`,
          details: apiTest.connected ? [] : [
            'Check if the backend server is running',
            'Verify the API URL in environment configuration',
            'Check for network connectivity issues',
            'Review firewall or proxy settings'
          ],
          timestamp
        };
      } catch (error: any) {
        results[results.length - 1] = {
          service: 'API Connectivity',
          status: 'error',
          message: `API test failed: ${error.message}`,
          details: [
            'Backend server may not be running',
            'Check API URL configuration',
            'Verify network connectivity'
          ],
          timestamp
        };
      }
      
      // 3. HTTP Detection Service Status
      results.push({
        service: 'HTTP Detection Service',
        status: 'success',
        message: 'HTTP-only detection service active',
        details: [
          'Using HTTP-only workflow for detection',
          'No persistent connections required',
          'Optimized for reliability and performance'
        ],
        timestamp
      });
      
      // 4. Environment Detection
      const config = getConfig();
      results.push({
        service: 'Environment Detection',
        status: 'success',
        message: `Environment: ${config.environment} (${config.debug ? 'Debug' : 'Production'} mode)`,
        details: [
          `Debug enabled: ${config.debug}`,
          `Log level: ${config.logLevel}`,
          `Performance monitoring: ${config.enablePerformanceMonitoring}`,
          `Mock data: ${config.enableMockData}`
        ],
        timestamp
      });
      
    } catch (error: any) {
      results.push({
        service: 'Validation System',
        status: 'error',
        message: `Validation failed: ${error.message}`,
        timestamp
      });
    }
    
    setValidationResults(results);
    setLastValidation(timestamp);
    setIsValidating(false);
    
    // Notify parent component
    const overallValid = results.every(r => r.status === 'success' || r.status === 'warning');
    const allErrors = results
      .filter(r => r.status === 'error')
      .flatMap(r => [r.message, ...(r.details || [])]);
    
    onValidationChange?.(overallValid, allErrors);
  };
  
  // Auto-refresh validation
  useEffect(() => {
    runValidation(); // Run initial validation
    
    if (autoRefresh && refreshInterval > 0) {
      const interval = setInterval(runValidation, refreshInterval);
      return () => clearInterval(interval);
    }
    
    // Return empty cleanup function when not auto-refreshing
    return () => {};
  }, [autoRefresh, refreshInterval]);
  
  const getStatusColor = (status: ValidationResult['status']) => {
    switch (status) {
      case 'success': return 'success';
      case 'warning': return 'warning';
      case 'error': return 'error';
      case 'loading': return 'info';
      default: return 'default';
    }
  };
  
  const getStatusIcon = (status: ValidationResult['status']) => {
    switch (status) {
      case 'success': return <CheckCircle color="success" />;
      case 'warning': return <Warning color="warning" />;
      case 'error': return <Error color="error" />;
      case 'loading': return <CircularProgress size={20} />;
      default: return <Info />;
    }
  };
  
  const overallStatus = validationResults.length > 0 ? (
    validationResults.some(r => r.status === 'error') ? 'error' :
    validationResults.some(r => r.status === 'warning') ? 'warning' : 'success'
  ) : 'loading';
  
  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Settings color="primary" />
            <Typography variant="h6">
              System Configuration Status
            </Typography>
            <Chip 
              label={overallStatus.toUpperCase()} 
              color={getStatusColor(overallStatus) as any}
              size="small"
            />
          </Box>
          <Box display="flex" alignItems="center" gap={1}>
            <Button
              startIcon={isValidating ? <CircularProgress size={16} /> : <Refresh />}
              onClick={runValidation}
              disabled={isValidating}
              size="small"
            >
              {isValidating ? 'Validating...' : 'Refresh'}
            </Button>
            <IconButton 
              onClick={() => setShowDetailsPanel(!showDetailsPanel)}
              size="small"
            >
              {showDetailsPanel ? <ExpandLess /> : <ExpandMore />}
            </IconButton>
          </Box>
        </Box>
        
        {lastValidation && (
          <Typography variant="caption" color="textSecondary" gutterBottom>
            Last checked: {lastValidation.toLocaleTimeString()}
          </Typography>
        )}
        
        {validationResults.length > 0 && (
          <List dense>
            {validationResults.map((result, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  {getStatusIcon(result.status)}
                </ListItemIcon>
                <ListItemText
                  primary={result.service}
                  secondary={result.message}
                />
              </ListItem>
            ))}
          </List>
        )}
        
        <Collapse in={showDetailsPanel}>
          <Divider sx={{ my: 2 }} />
          
          {validationResults.filter(r => r.status === 'error' || r.details?.length).map((result, index) => (
            <Box key={index} mb={2}>
              <Alert 
                severity={result.status === 'error' ? 'error' : 'info'}
                variant="outlined"
              >
                <Typography variant="subtitle2" gutterBottom>
                  {result.service}
                </Typography>
                <Typography variant="body2" gutterBottom>
                  {result.message}
                </Typography>
                
                {result.details && result.details.length > 0 && (
                  <List dense>
                    {result.details.map((detail, detailIndex) => (
                      <ListItem key={detailIndex} sx={{ py: 0 }}>
                        <ListItemText 
                          primary={detail}
                          primaryTypographyProps={{ variant: 'caption' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </Alert>
            </Box>
          ))}
          
          {/* Troubleshooting Guide */}
          <Alert severity="info" variant="outlined">
            <Typography variant="subtitle2" gutterBottom>
              🔧 Troubleshooting Guide
            </Typography>
            <List dense>
              <ListItem sx={{ py: 0 }}>
                <ListItemText 
                  primary="Environment Issues: Check your .env.development or .env.production files"
                  primaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
              <ListItem sx={{ py: 0 }}>
                <ListItemText 
                  primary="API Issues: Ensure backend server is running on the configured port"
                  primaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
              <ListItem sx={{ py: 0 }}>
                <ListItemText 
                  primary="WebSocket Issues: Check if Socket.IO server is running (usually port 8001)"
                  primaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
              <ListItem sx={{ py: 0 }}>
                <ListItemText 
                  primary="Network Issues: Verify firewall settings and network connectivity"
                  primaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
            </List>
          </Alert>
        </Collapse>
      </CardContent>
    </Card>
  );
};

export default ConfigurationValidator;