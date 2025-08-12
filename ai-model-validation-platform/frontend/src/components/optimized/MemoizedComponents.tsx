import React, { memo, useMemo, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  Skeleton,
  Chip,
  Button,
  IconButton,
} from '@mui/material';
import {
  Camera,
  Visibility,
  MoreVert,
} from '@mui/icons-material';
import { Project } from '../../services/types';

// Optimized Project Card Component with React.memo
interface ProjectCardProps {
  project: Project;
  onMenuClick: (event: React.MouseEvent<HTMLElement>, projectId: string) => void;
  onViewDetails: (projectId: string) => void;
  getStatusColor: (status: Project['status']) => 'success' | 'info' | 'warning' | 'default';
}

export const MemoizedProjectCard = memo<ProjectCardProps>(({
  project,
  onMenuClick,
  onViewDetails,
  getStatusColor,
}) => {
  const handleMenuClick = useCallback((event: React.MouseEvent<HTMLElement>) => {
    onMenuClick(event, project.id);
  }, [onMenuClick, project.id]);

  const handleViewDetails = useCallback(() => {
    onViewDetails(project.id);
  }, [onViewDetails, project.id]);

  const statusColor = useMemo(() => getStatusColor(project.status), [getStatusColor, project.status]);

  const chips = useMemo(() => [
    <Chip
      key="status"
      label={project.status}
      color={statusColor}
      size="small"
    />,
    <Chip
      key="tests"
      label={`${project.testsCount} tests`}
      variant="outlined"
      size="small"
    />,
    ...(project.accuracy > 0 ? [
      <Chip
        key="accuracy"
        label={`${project.accuracy}% accuracy`}
        variant="outlined"
        size="small"
      />
    ] : []),
  ], [project.status, project.testsCount, project.accuracy, statusColor]);

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Camera color="primary" />
            <Typography variant="h6" component="div">
              {project.name}
            </Typography>
          </Box>
          <IconButton size="small" onClick={handleMenuClick}>
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

        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          {chips}
        </Box>
      </CardContent>

      <CardActions>
        <Button
          size="small"
          startIcon={<Visibility />}
          onClick={handleViewDetails}
        >
          View Details
        </Button>
      </CardActions>
    </Card>
  );
});

MemoizedProjectCard.displayName = 'MemoizedProjectCard';

// Optimized Loading Skeleton Component
interface ProjectSkeletonProps {
  count?: number;
}

export const MemoizedProjectSkeleton = memo<ProjectSkeletonProps>(({ count = 6 }) => {
  const skeletons = useMemo(() => 
    Array.from({ length: count }, (_, index) => (
      <Card key={index} sx={{ height: '100%' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <Skeleton variant="circular" width={24} height={24} />
            <Skeleton variant="text" width="60%" height={32} />
          </Box>
          <Skeleton variant="text" width="100%" height={20} sx={{ mb: 1 }} />
          <Skeleton variant="text" width="80%" height={20} sx={{ mb: 2 }} />
          <Skeleton variant="text" width="50%" height={16} sx={{ mb: 1 }} />
          <Skeleton variant="text" width="60%" height={16} sx={{ mb: 1 }} />
          <Skeleton variant="text" width="40%" height={16} sx={{ mb: 2 }} />
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <Skeleton variant="rounded" width={60} height={24} />
            <Skeleton variant="rounded" width={80} height={24} />
            <Skeleton variant="rounded" width={70} height={24} />
          </Box>
        </CardContent>
        <CardActions>
          <Skeleton variant="rounded" width={120} height={36} />
        </CardActions>
      </Card>
    )),
    [count]
  );

  return <>{skeletons}</>;
});

MemoizedProjectSkeleton.displayName = 'MemoizedProjectSkeleton';

// Dashboard Skeleton Component
export const MemoizedDashboardSkeleton = memo(() => {
  const statCards = useMemo(() =>
    Array.from({ length: 4 }, (_, i) => (
      <Box key={i} sx={{ minWidth: 250, flex: 1 }}>
        <Card sx={{ height: '100%' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Skeleton variant="circular" width={40} height={40} sx={{ mr: 2 }} />
              <Box>
                <Skeleton variant="text" width={60} height={40} />
                <Skeleton variant="text" width={120} height={20} />
                <Skeleton variant="text" width={100} height={16} />
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>
    )),
    []
  );

  const chartCards = useMemo(() => [
    <Box key="sessions" sx={{ minWidth: 400, flex: 1 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width={200} height={32} />
          <Box sx={{ mt: 2 }}>
            {Array.from({ length: 4 }, (_, i) => (
              <Box key={i} sx={{ mb: 2 }}>
                <Skeleton variant="text" width="100%" height={24} />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </Box>,
    <Box key="status" sx={{ minWidth: 400, flex: 1 }}>
      <Card>
        <CardContent>
          <Skeleton variant="text" width={150} height={32} />
          <Box sx={{ mt: 2 }}>
            {Array.from({ length: 3 }, (_, i) => (
              <Box key={i} sx={{ mb: 2 }}>
                <Skeleton variant="text" width="100%" height={20} />
                <Skeleton variant="rectangular" width="100%" height={4} sx={{ mt: 1 }} />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </Box>,
  ], []);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
        {statCards}
      </Box>
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {chartCards}
      </Box>
    </Box>
  );
});

MemoizedDashboardSkeleton.displayName = 'MemoizedDashboardSkeleton';