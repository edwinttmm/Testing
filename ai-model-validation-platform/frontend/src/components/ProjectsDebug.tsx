import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Alert, Chip } from '@mui/material';
import { getProjects, healthCheck } from '../services/api';
import { Project } from '../services/types';

// Debug component to test API integration
const ProjectsDebug: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<string | null>(null);

  const testHealthCheck = async () => {
    try {
      const health = await healthCheck();
      setApiHealth(health.status);
    } catch (error: any) {
      setApiHealth(`Error: ${error.message}`);
    }
  };

  const testGetProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const projectsData = await getProjects();
      setProjects(projectsData);
    } catch (error: any) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    testHealthCheck();
  }, []);

  if (process.env.NODE_ENV === 'production') {
    return null; // Don't show in production
  }

  return (
    <Box sx={{ p: 2, border: '1px dashed #ccc', mb: 2 }}>
      <Typography variant="h6" gutterBottom>
        🔧 API Debug Panel
      </Typography>
      
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2">API Health:</Typography>
        <Chip 
          label={apiHealth || 'Testing...'} 
          color={apiHealth === 'healthy' ? 'success' : 'error'}
          size="small"
        />
      </Box>

      <Box sx={{ mb: 2 }}>
        <Button 
          variant="outlined" 
          onClick={testGetProjects} 
          disabled={loading}
          size="small"
        >
          {loading ? 'Loading...' : 'Test Get Projects'}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          API Error: {error}
        </Alert>
      )}

      {projects.length > 0 && (
        <Box>
          <Typography variant="subtitle2">
            Found {projects.length} projects:
          </Typography>
          {projects.map((project) => (
            <Chip 
              key={project.id} 
              label={project.name} 
              variant="outlined" 
              size="small" 
              sx={{ m: 0.5 }}
            />
          ))}
        </Box>
      )}

      <Typography variant="caption" color="text.secondary">
        This debug panel only shows in development mode.
      </Typography>
    </Box>
  );
};

export default ProjectsDebug;