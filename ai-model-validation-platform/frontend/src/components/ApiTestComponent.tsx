import React, { useState } from 'react';
import { Box, Button, Typography, Alert, Paper } from '@mui/material';
import { healthCheck, getProjects, createProject } from '../services/api';

const ApiTestComponent: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<string>('');
  const [projectsData, setProjectsData] = useState<any[]>([]);
  const [createResult, setCreateResult] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const testHealthCheck = async () => {
    try {
      setLoading(true);
      console.log('Testing health check...');
      const result = await healthCheck();
      console.log('Health check result:', result);
      setHealthStatus(`✅ Healthy: ${result.status}`);
    } catch (error: any) {
      console.error('Health check error:', error);
      setHealthStatus(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const testGetProjects = async () => {
    try {
      setLoading(true);
      console.log('Testing get projects...');
      const result = await getProjects();
      console.log('Get projects result:', result);
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
      console.log('Testing create project...');
      const testProject = {
        name: 'Test Project ' + Date.now(),
        description: 'API Test Project',
        cameraModel: 'Test Camera',
        cameraView: 'Front-facing VRU' as const,
        signalType: 'pedestrian'
      };
      const result = await createProject(testProject);
      console.log('Create project result:', result);
      setCreateResult(`✅ Created: ${result.name} (ID: ${result.id})`);
    } catch (error: any) {
      console.error('Create project error:', error);
      setCreateResult(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: 3, m: 2 }}>
      <Typography variant="h5" gutterBottom>
        🔬 API Connection Test
      </Typography>
      
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
    </Paper>
  );
};

export default ApiTestComponent;