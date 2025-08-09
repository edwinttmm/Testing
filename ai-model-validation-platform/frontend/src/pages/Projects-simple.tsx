import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
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
} from '@mui/material';
import {
  Add,
  MoreVert,
  Visibility,
  Edit,
  Delete,
  Camera,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface Project {
  id: string;
  name: string;
  description: string;
  cameraModel: string;
  cameraView: 'Front-facing VRU' | 'Rear-facing VRU' | 'In-Cab Driver Behavior';
  signalType: string;
  createdAt: string;
  status: 'Active' | 'Completed' | 'Draft';
  testsCount: number;
  accuracy: number;
}

const mockProjects: Project[] = [
  {
    id: '1',
    name: 'Highway VRU Detection',
    description: 'Testing front-facing camera detection on highway scenarios',
    cameraModel: 'Sony IMX390',
    cameraView: 'Front-facing VRU',
    signalType: 'GPIO',
    createdAt: '2024-01-15',
    status: 'Active',
    testsCount: 15,
    accuracy: 94.2,
  },
  {
    id: '2',
    name: 'Urban Cycling Detection',
    description: 'Urban environment cyclist detection validation',
    cameraModel: 'OmniVision OV2312',
    cameraView: 'Front-facing VRU',
    signalType: 'Network Packet',
    createdAt: '2024-01-10',
    status: 'Completed',
    testsCount: 23,
    accuracy: 91.7,
  },
  {
    id: '3',
    name: 'Driver Behavior Analysis',
    description: 'In-cab driver distraction monitoring',
    cameraModel: 'Aptina AR0237',
    cameraView: 'In-Cab Driver Behavior',
    signalType: 'GPIO',
    createdAt: '2024-01-20',
    status: 'Draft',
    testsCount: 0,
    accuracy: 0,
  },
];

const Projects: React.FC = () => {
  const navigate = useNavigate();
  const [projects] = useState<Project[]>(mockProjects);
  const [openDialog, setOpenDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, projectId: string) => {
    setAnchorEl(event.currentTarget);
    setSelectedProject(projectId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedProject(null);
  };

  const handleCreateProject = () => {
    setOpenDialog(false);
  };

  const getStatusColor = (status: Project['status']) => {
    switch (status) {
      case 'Active':
        return 'success';
      case 'Completed':
        return 'info';
      case 'Draft':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Projects</Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => setOpenDialog(true)}
        >
          New Project
        </Button>
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {projects.map((project) => (
          <Box key={project.id} sx={{ minWidth: 350, maxWidth: 400, flex: '1 1 350px' }}>
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
                    label={`${project.testsCount} tests`}
                    variant="outlined"
                    size="small"
                  />
                  {project.accuracy > 0 && (
                    <Chip
                      label={`${project.accuracy}% accuracy`}
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
          </Box>
        ))}
      </Box>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleMenuClose}>
          <Edit sx={{ mr: 1 }} fontSize="small" />
          Edit
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <Delete sx={{ mr: 1 }} fontSize="small" />
          Delete
        </MenuItem>
      </Menu>

      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Project</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Project Name"
            fullWidth
            variant="outlined"
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Description"
            fullWidth
            multiline
            rows={3}
            variant="outlined"
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Camera Model"
            fullWidth
            variant="outlined"
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Camera View</InputLabel>
            <Select label="Camera View">
              <MenuItem value="Front-facing VRU">Front-facing VRU</MenuItem>
              <MenuItem value="Rear-facing VRU">Rear-facing VRU</MenuItem>
              <MenuItem value="In-Cab Driver Behavior">In-Cab Driver Behavior</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Signal Type</InputLabel>
            <Select label="Signal Type">
              <MenuItem value="GPIO">GPIO</MenuItem>
              <MenuItem value="Network Packet">Network Packet</MenuItem>
              <MenuItem value="Serial">Serial</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateProject} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Projects;