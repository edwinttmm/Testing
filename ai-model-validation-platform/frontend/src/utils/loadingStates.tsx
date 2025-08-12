import React from 'react';
import {
  Box,
  CircularProgress,
  LinearProgress,
  Skeleton,
  Typography,
  Card,
  CardContent,
} from '@mui/material';

// Optimized loading states to prevent layout shifts

interface LoadingSpinnerProps {
  size?: number;
  message?: string;
  fullScreen?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 40,
  message,
  fullScreen = false,
}) => {
  const content = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        ...(fullScreen && {
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          zIndex: 9999,
        }),
      }}
    >
      <CircularProgress size={size} />
      {message && (
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      )}
    </Box>
  );

  if (fullScreen) {
    return content;
  }

  return (
    <Box sx={{ padding: 3, minHeight: 200 }}>
      {content}
    </Box>
  );
};

interface ProgressBarProps {
  value?: number;
  message?: string;
  indeterminate?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  message,
  indeterminate = false,
}) => (
  <Box sx={{ width: '100%', padding: 2 }}>
    {message && (
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {message}
      </Typography>
    )}
    <LinearProgress
      variant={indeterminate ? 'indeterminate' : 'determinate'}
      value={value}
      sx={{ height: 8, borderRadius: 4 }}
    />
    {!indeterminate && value !== undefined && (
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
        {Math.round(value)}%
      </Typography>
    )}
  </Box>
);

// Card skeleton with proper dimensions to prevent layout shift
export const CardSkeleton: React.FC<{
  count?: number;
  height?: number;
}> = ({ count = 1, height = 200 }) => (
  <>
    {Array.from({ length: count }, (_, index) => (
      <Card key={index} sx={{ height }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Skeleton variant="circular" width={40} height={40} sx={{ mr: 2 }} />
            <Box sx={{ flex: 1 }}>
              <Skeleton variant="text" width="60%" height={24} />
              <Skeleton variant="text" width="40%" height={20} />
            </Box>
          </Box>
          <Skeleton variant="rectangular" width="100%" height={60} sx={{ mb: 2 }} />
          <Skeleton variant="text" width="80%" />
          <Skeleton variant="text" width="60%" />
        </CardContent>
      </Card>
    ))}
  </>
);

// List skeleton
export const ListSkeleton: React.FC<{
  count?: number;
  showAvatar?: boolean;
}> = ({ count = 5, showAvatar = true }) => (
  <Box>
    {Array.from({ length: count }, (_, index) => (
      <Box
        key={index}
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 2,
          px: 1,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        {showAvatar && <Skeleton variant="circular" width={40} height={40} sx={{ mr: 2 }} />}
        <Box sx={{ flex: 1 }}>
          <Skeleton variant="text" width="70%" height={20} sx={{ mb: 0.5 }} />
          <Skeleton variant="text" width="50%" height={16} />
        </Box>
        <Skeleton variant="rectangular" width={80} height={32} />
      </Box>
    ))}
  </Box>
);

// Table skeleton
export const TableSkeleton: React.FC<{
  rows?: number;
  columns?: number;
}> = ({ rows = 5, columns = 4 }) => (
  <Box>
    {/* Header */}
    <Box sx={{ display: 'flex', py: 2, borderBottom: '2px solid', borderColor: 'divider' }}>
      {Array.from({ length: columns }, (_, index) => (
        <Box key={index} sx={{ flex: 1, px: 1 }}>
          <Skeleton variant="text" width="80%" height={24} />
        </Box>
      ))}
    </Box>
    
    {/* Rows */}
    {Array.from({ length: rows }, (_, rowIndex) => (
      <Box
        key={rowIndex}
        sx={{
          display: 'flex',
          py: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        {Array.from({ length: columns }, (_, colIndex) => (
          <Box key={colIndex} sx={{ flex: 1, px: 1 }}>
            <Skeleton variant="text" width={`${60 + Math.random() * 30}%`} height={20} />
          </Box>
        ))}
      </Box>
    ))}
  </Box>
);

// Chart skeleton
export const ChartSkeleton: React.FC<{
  height?: number;
  showLegend?: boolean;
}> = ({ height = 300, showLegend = true }) => (
  <Box>
    <Skeleton variant="text" width="40%" height={32} sx={{ mb: 2 }} />
    <Skeleton variant="rectangular" width="100%" height={height} sx={{ mb: 2 }} />
    {showLegend && (
      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
        {Array.from({ length: 3 }, (_, index) => (
          <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Skeleton variant="circular" width={12} height={12} />
            <Skeleton variant="text" width={60} height={16} />
          </Box>
        ))}
      </Box>
    )}
  </Box>
);

// Form skeleton
export const FormSkeleton: React.FC<{
  fields?: number;
}> = ({ fields = 4 }) => (
  <Box sx={{ maxWidth: 600 }}>
    <Skeleton variant="text" width="50%" height={32} sx={{ mb: 3 }} />
    {Array.from({ length: fields }, (_, index) => (
      <Box key={index} sx={{ mb: 3 }}>
        <Skeleton variant="text" width="30%" height={20} sx={{ mb: 1 }} />
        <Skeleton variant="rectangular" width="100%" height={56} />
      </Box>
    ))}
    <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
      <Skeleton variant="rectangular" width={100} height={36} />
      <Skeleton variant="rectangular" width={80} height={36} />
    </Box>
  </Box>
);

// Error state with retry
interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  showRetry?: boolean;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message = 'Something went wrong',
  onRetry,
  showRetry = true,
}) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 4,
      textAlign: 'center',
    }}
  >
    <Typography variant="h6" color="error" sx={{ mb: 2 }}>
      {message}
    </Typography>
    {showRetry && onRetry && (
      <Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Please try again or contact support if the problem persists.
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <button onClick={onRetry}>
            Retry
          </button>
        </Box>
      </Box>
    )}
  </Box>
);

// Empty state
interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No data found',
  description,
  action,
  icon,
}) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 6,
      textAlign: 'center',
    }}
  >
    {icon && <Box sx={{ mb: 2, opacity: 0.5 }}>{icon}</Box>}
    <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
      {title}
    </Typography>
    {description && (
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 400 }}>
        {description}
      </Typography>
    )}
    {action}
  </Box>
);