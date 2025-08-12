import React, { useState } from 'react';
import { Box, Button, Typography, Alert, Paper } from '@mui/material';
import { healthCheck, getProjects, createProject } from '../services/api';
import ErrorBoundary from './ui/ErrorBoundary';
import { NetworkError, ApiError, ErrorFactory } from '../utils/errorTypes';

const ApiTestComponent: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<string>('');
  const [projectsData, setProjectsData] = useState<any[]>([]);
  const [createResult, setCreateResult] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const testHealthCheck = async () => {
    try {
      setLoading(true);
      // Testing health check
      const result = await healthCheck();
      // Health check completed
      setHealthStatus(`✅ Healthy: ${result.status}`);
    } catch (error: any) {
      console.error('Health check error:', error);
      
      // Create proper error types for better error boundary handling
      let formattedError: Error;
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        formattedError = ErrorFactory.createNetworkError(undefined, { context: 'health-check' });
      } else if (error.response) {
        formattedError = ErrorFactory.createApiError(error.response, error.response.data, { context: 'health-check' });
      } else {
        formattedError = new Error(`Health check failed: ${error.message}`);
      }
      
      setHealthStatus(`❌ Error: ${formattedError.message}`);
      // Re-throw to be caught by error boundary if needed
      if (error.name === 'TypeError' || (error.response && error.response.status >= 500)) {
        throw formattedError;
      }
    } finally {
      setLoading(false);
    }
  };

  const testGetProjects = async () => {
    try {
      setLoading(true);
      // Testing get projects
      const result = await getProjects();
      // Get projects completed
      setProjectsData(result);
    } catch (error: any) {
      console.error('Get projects error:', error);
      setProjectsData([]);
    } finally {
      setLoading(false);
    }
  };

  const testCreateProject = async () => {
    try {
      setLoading(true);
      // Testing create project
      const testProject = {
        name: 'Test Project ' + Date.now(),
        description: 'API Test Project',
        cameraModel: 'Test Camera',
        cameraView: 'Front-facing VRU' as const,
        signalType: 'pedestrian'
      };
      const result = await createProject(testProject);
      // Create project completed
      setCreateResult(`✅ Created: ${result.name} (ID: ${result.id})`);
    } catch (error: any) {
      console.error('Create project error:', error);
      setCreateResult(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ErrorBoundary 
      level="component" 
      context="api-test-component"
      enableRetry={true}
      maxRetries={2}
    >
      <Paper sx={{ p: 3, m: 2 }}>
        <Typography variant="h5" gutterBottom>
          🔬 API Connection Test
        </Typography>
        
        <ErrorBoundary 
          level="component" 
          context="api-test-buttons"
          enableRetry={false}
        >
          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <Button 
              variant="outlined" 
              onClick={testHealthCheck}
              disabled={loading}
            >
              Test Health Check
            </Button>
            <Button 
              variant="outlined" 
              onClick={testGetProjects}
              disabled={loading}
            >
              Test Get Projects
            </Button>
            <Button 
              variant="outlined" 
              onClick={testCreateProject}
              disabled={loading}
            >
              Test Create Project
            </Button>
          </Box>
        </ErrorBoundary>

        <ErrorBoundary 
          level="component" 
          context="api-test-results"
          enableRetry={false}
        >
          {healthStatus && (
            <Alert severity={healthStatus.includes('✅') ? 'success' : 'error'} sx={{ mb: 2 }}>
              <strong>Health Check:</strong> {healthStatus}
            </Alert>
          )}

          {projectsData.length > 0 && (
            <Alert severity="success" sx={{ mb: 2 }}>
              <strong>Projects Found:</strong> {projectsData.length} projects
              <pre>{JSON.stringify(projectsData, null, 2)}</pre>
            </Alert>
          )}

          {createResult && (
            <Alert severity={createResult.includes('✅') ? 'success' : 'error'} sx={{ mb: 2 }}>
              <strong>Create Project:</strong> {createResult}
            </Alert>
          )}

          <Typography variant="body2" color="text.secondary">
            Open browser console (F12) to see detailed API logs.
          </Typography>
        </ErrorBoundary>
      </Paper>
    </ErrorBoundary>
  );
};

export default ApiTestComponent;