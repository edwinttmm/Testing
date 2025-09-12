import React, { useState } from 'react';
import { Box, Button, Typography, Alert, Paper } from '@mui/material';
import { healthCheck, getProjects, createProject } from '../services/api';
import ErrorBoundary from './ui/ErrorBoundary';
import { CameraType, SignalType, Project } from '../services/types';
import { 
  TypedErrorFactory 
} from '../types/error.types';

const ApiTestComponent: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<string>('');
  const [projectsData, setProjectsData] = useState<Project[]>([]);
  const [createResult, setCreateResult] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const testHealthCheck = async () => {
    try {
      setLoading(true);
      // Testing health check
      const result = await healthCheck();
      // Health check completed
      setHealthStatus(`✅ Healthy: ${result.status}`);
    } catch (error: unknown) {
      console.error('Health check error:', error);
      
      // Create proper error types for better error boundary handling
      const safeError = TypedErrorFactory.fromUnknown(error, 'Health check failed');
      let formattedError: Error;
      
      if (safeError.name === 'TypeError' && safeError.message.includes('fetch')) {
        formattedError = TypedErrorFactory.createNetworkError('Health check network error');
      } else if (safeError.response) {
        formattedError = TypedErrorFactory.createApiError(
          safeError.message,
          safeError.response.status,
          { context: 'health-check' }
        );
      } else {
        formattedError = new Error(`Health check failed: ${safeError.message}`);
      }
      
      setHealthStatus(`❌ Error: ${formattedError.message}`);
      // Re-throw to be caught by error boundary if needed
      if (safeError.name === 'TypeError' || (safeError.response && safeError.response.status && safeError.response.status >= 500)) {
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
    } catch (error: unknown) {
      const safeError = TypedErrorFactory.fromUnknown(error, 'Failed to fetch projects');
      console.error('Get projects error:', safeError);
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
        cameraView: CameraType.FRONT_FACING_VRU,
        signalType: SignalType.GPIO
      };
      const result = await createProject(testProject);
      // Create project completed
      setCreateResult(`✅ Created: ${result.name} (ID: ${result.id})`);
    } catch (error: unknown) {
      const safeError = TypedErrorFactory.fromUnknown(error, 'Failed to create project');
      console.error('Create project error:', safeError);
      setCreateResult(`❌ Error: ${safeError.message}`);
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