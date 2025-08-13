import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Chip,
  useTheme,
} from '@mui/material';
import {
  Camera,
  MoreVert,
  Visibility,
  Edit,
  Delete,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Project } from '../../services/types';

interface AccessibleProjectCardProps {
  project: Project;
  onEdit?: (projectId: string) => void;
  onDelete?: (projectId: string) => void;
}

const AccessibleProjectCard: React.FC<AccessibleProjectCardProps> = ({
  project,
  onEdit,
  onDelete,
}) => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const getStatusColor = (status: Project['status']): "success" | "info" | "warning" | "default" => {
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

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setIsMenuOpen(true);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setIsMenuOpen(false);
  };

  const handleEdit = () => {
    handleMenuClose();
    onEdit?.(project.id);
  };

  const handleDelete = () => {
    handleMenuClose();
    onDelete?.(project.id);
  };

  const handleViewDetails = () => {
    navigate(`/projects/${project.id}`);
  };

  const handleCardClick = (event: React.MouseEvent<HTMLElement>) => {
    // Only navigate if clicking on the card itself, not on buttons
    if (event.target === event.currentTarget || (event.target as HTMLElement).closest('.card-content')) {
      navigate(`/projects/${project.id}`);
    }
  };

  const handleCardKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      navigate(`/projects/${project.id}`);
    }
  };

  const handleMenuKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      handleMenuClose();
    }
  };

  return (
    <Card 
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        cursor: 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          boxShadow: theme.shadows[4],
          transform: 'translateY(-2px)',
        },
        '&:focus-within': {
          outline: `2px solid ${theme.palette.primary.main}`,
          outlineOffset: 2,
        },
      }}
      onClick={handleCardClick}
      onKeyDown={handleCardKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`Project: ${project.name}. ${project.description}. Status: ${project.status}. Click to view details.`}
    >
      <CardContent sx={{ flexGrow: 1 }} className="card-content">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Camera 
              color="primary" 
              aria-hidden="true"
              sx={{ fontSize: '1.5rem' }}
            />
            <Typography 
              variant="h6" 
              component="h3"
              sx={{ 
                fontWeight: 600,
                lineHeight: 1.2,
              }}
            >
              {project.name}
            </Typography>
          </Box>
          <IconButton
            size="small"
            onClick={handleMenuOpen}
            onKeyDown={handleMenuKeyDown}
            aria-label={`More actions for project ${project.name}`}
            aria-controls={isMenuOpen ? `project-menu-${project.id}` : undefined}
            aria-haspopup="true"
            aria-expanded={isMenuOpen ? 'true' : 'false'}
            sx={{
              '&:focus': {
                outline: `2px solid ${theme.palette.primary.main}`,
                outlineOffset: 2,
              }
            }}
          >
            <MoreVert />
          </IconButton>
        </Box>

        <Typography 
          variant="body2" 
          color="text.secondary" 
          sx={{ mb: 2, lineHeight: 1.5 }}
          component="p"
        >
          {project.description}
        </Typography>

        <Box sx={{ mb: 2 }} role="group" aria-label="Project specifications">
          <Typography variant="caption" color="text.secondary" component="div">
            <strong>Camera:</strong> {project.cameraModel}
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div">
            <strong>View:</strong> {project.cameraView}
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div">
            <strong>Signal:</strong> {project.signalType}
          </Typography>
        </Box>

        <Box 
          sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}
          role="group"
          aria-label="Project status and metrics"
        >
          <Chip
            label={project.status}
            color={getStatusColor(project.status)}
            size="small"
            aria-label={`Project status: ${project.status}`}
          />
          <Chip
            label={`${project.testsCount} tests`}
            variant="outlined"
            size="small"
            aria-label={`Tests completed: ${project.testsCount}`}
          />
          {(project.accuracy ?? 0) > 0 && (
            <Chip
              label={`${project.accuracy ?? 0}% accuracy`}
              variant="outlined"
              size="small"
              aria-label={`Model accuracy: ${project.accuracy ?? 0} percent`}
            />
          )}
        </Box>
      </CardContent>

      <CardActions sx={{ mt: 'auto', p: 2, pt: 0 }}>
        <Button
          size="small"
          startIcon={<Visibility />}
          onClick={(e) => {
            e.stopPropagation();
            handleViewDetails();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              e.stopPropagation();
              handleViewDetails();
            }
          }}
          sx={{
            '&:focus': {
              outline: `2px solid ${theme.palette.primary.main}`,
              outlineOffset: 2,
            }
          }}
          aria-label={`View details for project ${project.name}`}
        >
          View Details
        </Button>
      </CardActions>

      <Menu
        id={`project-menu-${project.id}`}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        keepMounted
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        open={isMenuOpen}
        onClose={handleMenuClose}
        onKeyDown={handleMenuKeyDown}
        PaperProps={{
          sx: { 
            minWidth: 150,
            boxShadow: theme.shadows[3],
          },
          role: 'menu',
        }}
        MenuListProps={{
          'aria-labelledby': `project-menu-button-${project.id}`,
          role: 'menu',
        }}
      >
        <MenuItem 
          onClick={handleEdit}
          role="menuitem"
          sx={{
            '&:focus': {
              backgroundColor: theme.palette.action.focus,
            }
          }}
        >
          <Edit sx={{ mr: 1 }} fontSize="small" aria-hidden="true" />
          Edit Project
        </MenuItem>
        <MenuItem 
          onClick={handleDelete}
          role="menuitem"
          sx={{
            color: theme.palette.error.main,
            '&:focus': {
              backgroundColor: theme.palette.action.focus,
            }
          }}
        >
          <Delete sx={{ mr: 1 }} fontSize="small" aria-hidden="true" />
          Delete Project
        </MenuItem>
      </Menu>
    </Card>
  );
};

export default AccessibleProjectCard;