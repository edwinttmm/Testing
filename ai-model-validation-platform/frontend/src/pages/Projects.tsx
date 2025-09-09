import React, { useState, useEffect, useCallback } from 'react';
import { getErrorMessage } from '../utils/errorUtils';
import { useErrorHandler } from '../hooks/useErrorHandler';
import { GridSkeleton } from '../components/ui/LoadingState';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  Grid,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Menu,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Add,
  MoreVert,
  Visibility,
  Edit,
  Delete,
  Camera,
  Refresh,
  Link,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { createProject, getProjects, updateProject, deleteProject } from '../services/api';
import { linkVideosToProject, getLinkedVideos } from '../services/api';
import { Project as ApiProject, ProjectCreate, ProjectUpdate, CameraType, SignalType, ProjectStatus, VideoFile } from '../services/types';
import ProjectsDebug from '../components/ProjectsDebug';
import ApiTestComponent from '../components/ApiTestComponent';
import DeleteConfirmationDialog from '../components/DeleteConfirmationDialog';
import VideoSelectionDialog from '../components/VideoSelectionDialog';

// Use Project type from API services
type Project = ApiProject;

// Mock projects removed - now loading from API

const Projects: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { withErrorHandling, withRetry } = useErrorHandler({
    messagePrefix: 'Projects',
    maxRetries: 2,
  });
  const [openDialog, setOpenDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [videoSelectionOpen, setVideoSelectionOpen] = useState(false);
  const [linkingProject, setLinkingProject] = useState<Project | null>(null);
  const [projectVideos, setProjectVideos] = useState<{[key: string]: VideoFile[]}>({});
  
  // Form state
  const [formData, setFormData] = useState<ProjectCreate>({
    name: '',
    description: '',
    cameraModel: '',
    cameraView: CameraType.FRONT_FACING_VRU,
    signalType: SignalType.GPIO
  });
  const [isEditing, setIsEditing] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<{[key: string]: string}>({});

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, projectId: string) => {
    setAnchorEl(event.currentTarget);
    setSelectedProject(projectId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedProject(null);
  };

  // Load all project videos function - defined before useEffect
  const loadAllProjectVideos = useCallback(async () => {
    try {
      const videoPromises = projects.map(async (project) => {
        try {
          const videos = await getLinkedVideos(project.id);
          return { projectId: project.id, videos };
        } catch (err) {
          console.warn(`Failed to load videos for project ${project.id}:`, err);
          return { projectId: project.id, videos: [] };
        }
      });
      
      const results = await Promise.allSettled(videoPromises);
      const newProjectVideos: {[key: string]: VideoFile[]} = {};
      
      results.forEach((result) => {
        if (result.status === 'fulfilled') {
          newProjectVideos[result.value.projectId] = result.value.videos;
        }
      });
      
      setProjectVideos(newProjectVideos);
    } catch (error) {
      console.error('Failed to load project videos:', error);
    }
  }, [projects]);

  // Load linked videos for all projects
  useEffect(() => {
    if (projects.length > 0) {
      loadAllProjectVideos();
    }
  }, [projects, loadAllProjectVideos]);

  const loadProjects = useCallback(async () => {
    const result = await withRetry(
      async () => {
        setLoading(true);
        setError(null);
        const projectsData = await getProjects();
        setProjects(projectsData);
        return projectsData;
      },
      {
        context: 'loading projects',
        onRetry: (attempt) => {
          console.log(`Retrying to load projects (attempt ${attempt})...`);
        },
        onError: (error) => {
          const errorMessage = getErrorMessage(error, 'Failed to load projects. Please try again.');
          setError(errorMessage);
          setProjects([]);
        }
      }
    );
    
    setLoading(false);
    return result;
  }, [withRetry]);

  // Load projects on component mount
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleFormChange = (field: keyof ProjectCreate, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (formErrors[field]) {
      setFormErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const resetForm = useCallback(() => {
    setFormData({
      name: '',
      description: '',
      cameraModel: '',
      cameraView: CameraType.FRONT_FACING_VRU,
      signalType: SignalType.GPIO
    });
    setFormErrors({});
    setFormError(null);
    setIsEditing(false);
    setEditingProject(null);
  }, []);

  const validateForm = useCallback((): boolean => {
    const errors: {[key: string]: string} = {};
    
    if (!formData.name.trim()) {
      errors.name = 'Project name is required';
    }
    if (!formData.description.trim()) {
      errors.description = 'Description is required';
    }
    if (!formData.cameraModel.trim()) {
      errors.cameraModel = 'Camera model is required';
    }
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }, [formData]);

  const handleCreateProject = useCallback(async () => {
    if (!validateForm()) {
      return;
    }

    setFormLoading(true);
    setFormError(null);

    await withErrorHandling(
      async () => {
        if (isEditing && editingProject) {
          // Update existing project
          const updateData: ProjectUpdate = {
            name: formData.name,
            description: formData.description,
            cameraModel: formData.cameraModel,
            cameraView: formData.cameraView,
            signalType: formData.signalType
          };
          await updateProject(editingProject.id, updateData);
        } else {
          // Create new project
          await createProject(formData);
        }
        
        // Success - close dialog and refresh projects
        setOpenDialog(false);
        resetForm();
        await loadProjects();
      },
      {
        context: isEditing ? 'updating project' : 'creating project',
        onError: (error) => {
          const errorMessage = getErrorMessage(error, `Failed to ${isEditing ? 'update' : 'create'} project. Please try again.`);
          setFormError(errorMessage);
        }
      }
    );

    setFormLoading(false);
  }, [validateForm, isEditing, editingProject, formData, withErrorHandling, loadProjects, resetForm]);

  const handleEditProject = () => {
    const project = projects.find(p => p.id === selectedProject);
    if (project) {
      setEditingProject(project);
      setIsEditing(true);
      setFormData({
        name: project.name,
        description: project.description || '',
        cameraModel: project.cameraModel || '',
        cameraView: project.cameraView || 'Front-facing VRU',
        signalType: project.signalType || 'GPIO'
      });
      setOpenDialog(true);
    }
    handleMenuClose();
  };

  const handleDeleteProject = () => {
    const project = projects.find(p => p.id === selectedProject);
    if (project) {
      setDeletingProject(project);
      setDeleteDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleLinkVideos = () => {
    const project = projects.find(p => p.id === selectedProject);
    if (project) {
      setLinkingProject(project);
      setVideoSelectionOpen(true);
    }
    handleMenuClose();
  };

  const handleVideoSelectionComplete = useCallback(async (selectedVideos: VideoFile[]) => {
    if (!linkingProject) return;
    
    setFormLoading(true);
    setError(null);

    await withErrorHandling(
      async () => {
        const videoIds = selectedVideos.map(video => video.id);
        await linkVideosToProject(linkingProject.id, videoIds);
        
        // Update local project videos state
        setProjectVideos(prev => ({
          ...prev,
          [linkingProject.id]: [...(prev[linkingProject.id] || []), ...selectedVideos]
        }));
        
        // Refresh projects to get updated counts
        await loadProjects();
      },
      {
        context: 'linking videos to project',
        onError: (err) => {
          setError(getErrorMessage(err, 'Failed to link videos to project'));
        }
      }
    );

    setFormLoading(false);
    setLinkingProject(null);
  }, [linkingProject, withErrorHandling, loadProjects]);

  // Delete confirmation handler is now inline in the DeleteConfirmationDialog

  const handleDialogClose = () => {
    if (!formLoading) {
      setOpenDialog(false);
      resetForm();
    }
  };

  const getStatusColor = (status: Project['status']) => {
    switch (status) {
      case ProjectStatus.ACTIVE:
        return 'success';
      case ProjectStatus.COMPLETED:
        return 'info';
      case ProjectStatus.DRAFT:
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      {process.env.NODE_ENV === 'development' && <ProjectsDebug />}
      {process.env.NODE_ENV === 'development' && <ApiTestComponent />}
      
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Projects</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={loadProjects}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => setOpenDialog(true)}
          >
            New Project
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert 
          severity="error" 
          sx={{ mb: 3 }}
          action={
            <Button 
              color="inherit" 
              size="small" 
              onClick={loadProjects}
              startIcon={<Refresh />}
            >
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {loading ? (
        <GridSkeleton items={6} columns={3} itemHeight={300} showActions={true} />
      ) : !error && projects.length === 0 ? (
        <Box textAlign="center" py={6}>
          <Camera sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h5" color="text.secondary" gutterBottom>
            No projects yet
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 400, mx: 'auto' }}>
            Create your first project to start validating AI model performance for VRU detection.
            After creating a project, you can link videos from the Ground Truth library.
          </Typography>
          <Button 
            variant="contained" 
            size="large" 
            startIcon={<Add />} 
            onClick={() => setOpenDialog(true)}
            sx={{ px: 4 }}
          >
            Create Your First Project
          </Button>
        </Box>
      ) : (
        <Grid container spacing={3}>
          {projects.map((project) => (
            <Grid item xs={12} md={6} lg={4} key={project.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Camera color="primary" />
                      <Typography variant="h6" component="div">
                        {project.name}
                      </Typography>
                    </Box>
                    <IconButton
                      size="small"
                      onClick={(e) => handleMenuClick(e, project.id)}
                    >
                      <MoreVert />
                    </IconButton>
                  </Box>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {project.description}
                  </Typography>

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      Camera: {project.cameraModel}
                    </Typography>
                    <br />
                    <Typography variant="caption" color="text.secondary">
                      View: {project.cameraView}
                    </Typography>
                    <br />
                    <Typography variant="caption" color="text.secondary">
                      Signal: {project.signalType}
                    </Typography>
                  </Box>

                  <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                    <Chip
                      label={project.status}
                      color={getStatusColor(project.status)}
                      size="small"
                    />
                    <Chip
                      label={`${project.testsCount || 0} tests`}
                      variant="outlined"
                      size="small"
                    />
                    <Chip
                      label={`${(projectVideos[project.id] || []).length} videos`}
                      variant="outlined"
                      size="small"
                      color="primary"
                    />
                    {(project.averageAccuracy ?? 0) > 0 && (
                      <Chip
                        label={`${project.averageAccuracy ?? 0}% accuracy`}
                        variant="outlined"
                        size="small"
                      />
                    )}
                  </Box>
                </CardContent>

                <CardActions>
                  <Button
                    size="small"
                    startIcon={<Visibility />}
                    onClick={() => navigate(`/projects/${project.id}`)}
                  >
                    View Details
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleEditProject}>
          <Edit sx={{ mr: 1 }} fontSize="small" />
          Edit
        </MenuItem>
        <MenuItem onClick={handleLinkVideos}>
          <Link sx={{ mr: 1 }} fontSize="small" />
          Link Videos
        </MenuItem>
        <MenuItem onClick={handleDeleteProject}>
          <Delete sx={{ mr: 1 }} fontSize="small" />
          Delete
        </MenuItem>
      </Menu>

      <Dialog open={openDialog} onClose={handleDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>{isEditing ? 'Edit Project' : 'Create New Project'}</DialogTitle>
        <DialogContent>
          {formError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {formError}
            </Alert>
          )}
          
          <TextField
            autoFocus
            margin="dense"
            label="Project Name"
            fullWidth
            variant="outlined"
            value={formData.name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFormChange('name', e.target.value)}
            error={!!formErrors.name}
            helperText={formErrors.name}
            disabled={formLoading}
            sx={{ mb: 2 }}
          />
          
          <TextField
            margin="dense"
            label="Description"
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            value={formData.description}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFormChange('description', e.target.value)}
            error={!!formErrors.description}
            helperText={formErrors.description}
            disabled={formLoading}
            sx={{ mb: 2 }}
          />
          
          <TextField
            margin="dense"
            label="Camera Model"
            fullWidth
            variant="outlined"
            value={formData.cameraModel}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFormChange('cameraModel', e.target.value)}
            error={!!formErrors.cameraModel}
            helperText={formErrors.cameraModel}
            disabled={formLoading}
            placeholder="e.g., Sony IMX390, OmniVision OV2312"
            sx={{ mb: 2 }}
          />
          
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Camera View</InputLabel>
            <Select 
              label="Camera View"
              value={formData.cameraView}
              onChange={(e) => handleFormChange('cameraView', e.target.value as CameraType)}
              disabled={formLoading}
            >
              <MenuItem value={CameraType.FRONT_FACING_VRU}>Front-facing VRU</MenuItem>
              <MenuItem value={CameraType.REAR_FACING_VRU}>Rear-facing VRU</MenuItem>
              <MenuItem value={CameraType.IN_CAB_DRIVER_BEHAVIOR}>In-Cab Driver Behavior</MenuItem>
              <MenuItem value={CameraType.MULTI_ANGLE_SCENARIOS}>Multi-angle</MenuItem>
            </Select>
          </FormControl>
          
          <FormControl fullWidth>
            <InputLabel>Signal Type</InputLabel>
            <Select 
              label="Signal Type"
              value={formData.signalType}
              onChange={(e) => handleFormChange('signalType', e.target.value as SignalType)}
              disabled={formLoading}
            >
              <MenuItem value={SignalType.GPIO}>GPIO</MenuItem>
              <MenuItem value={SignalType.NETWORK_PACKET}>Network Packet</MenuItem>
              <MenuItem value={SignalType.SERIAL}>Serial</MenuItem>
              <MenuItem value={SignalType.CAN_BUS}>CAN Bus</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={handleDialogClose} disabled={formLoading}>
            Cancel
          </Button>
          <Button 
            onClick={handleCreateProject} 
            variant="contained"
            disabled={formLoading}
            startIcon={formLoading ? <CircularProgress size={20} /> : null}
          >
            {formLoading ? (isEditing ? 'Updating...' : 'Creating...') : (isEditing ? 'Update' : 'Create')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        project={deletingProject}
        onConfirm={async (projectId: string) => {
          await deleteProject(projectId);
          setDeleteDialogOpen(false);
          setDeletingProject(null);
          await loadProjects();
        }}
      />

      {/* Video Selection Dialog */}
      <VideoSelectionDialog
        open={videoSelectionOpen}
        onClose={() => {
          setVideoSelectionOpen(false);
          setLinkingProject(null);
        }}
        projectId={linkingProject?.id || ''}
        onSelectionComplete={handleVideoSelectionComplete}
        selectedVideoIds={(linkingProject ? projectVideos[linkingProject.id] || [] : []).map(v => v.id)}
      />
    </Box>
  );
};

export default Projects;