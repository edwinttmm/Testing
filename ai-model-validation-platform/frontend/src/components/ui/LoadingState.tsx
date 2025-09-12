import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  Skeleton,
  Card,
  CardContent,
  Stack,
  LinearProgress,
} from '@mui/material';
import { SxProps, Theme } from '@mui/material/styles';

export interface LoadingStateProps {
  /**
   * Type of loading indicator to show
   */
  variant?: 'spinner' | 'skeleton' | 'linear' | 'dots';
  
  /**
   * Size of the loading indicator
   */
  size?: 'small' | 'medium' | 'large';
  
  /**
   * Loading message to display
   */
  message?: string;
  
  /**
   * Whether to show as fullscreen overlay
   */
  overlay?: boolean;
  
  /**
   * Custom height for the loading area
   */
  height?: number | string;
  
  /**
   * Custom styles
   */
  sx?: SxProps<Theme>;
  
  /**
   * Additional props for skeleton mode
   */
  skeletonProps?: {
    lines?: number;
    showAvatar?: boolean;
    showActions?: boolean;
    variant?: 'text' | 'rectangular' | 'circular';
    animation?: 'pulse' | 'wave' | false;
  };

  /**
   * Progress value for linear progress (0-100)
   */
  progress?: number;
}

const LoadingState: React.FC<LoadingStateProps> = ({
  variant = 'spinner',
  size = 'medium',
  message,
  overlay = false,
  height,
  sx,
  skeletonProps = {},
  progress,
}) => {
  const getSpinnerSize = () => {
    switch (size) {
      case 'small': return 24;
      case 'large': return 64;
      default: return 40;
    }
  };

  const getTypographyVariant = () => {
    switch (size) {
      case 'small': return 'body2' as const;
      case 'large': return 'h6' as const;
      default: return 'body1' as const;
    }
  };

  const renderSpinner = () => (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        minHeight: height || 200,
        ...sx,
      }}
    >
      <CircularProgress size={getSpinnerSize()} />
      {message && (
        <Typography variant={getTypographyVariant()} color="text.secondary">
          {message}
        </Typography>
      )}
    </Box>
  );

  const renderLinear = () => (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        minHeight: height || 100,
        px: 2,
        ...sx,
      }}
    >
      <LinearProgress 
        sx={{ width: '100%', mb: 1 }} 
        variant={progress !== undefined ? 'determinate' : 'indeterminate'}
        value={progress !== undefined ? progress : 0}
      />
      {message && (
        <Typography variant={getTypographyVariant()} color="text.secondary" textAlign="center">
          {message}
          {progress !== undefined && ` (${Math.round(progress)}%)`}
        </Typography>
      )}
    </Box>
  );

  const renderDots = () => (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        minHeight: height || 100,
        ...sx,
      }}
    >
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        {[0, 1, 2].map((i) => (
          <Box
            key={i}
            sx={{
              width: size === 'small' ? 6 : size === 'large' ? 12 : 8,
              height: size === 'small' ? 6 : size === 'large' ? 12 : 8,
              borderRadius: '50%',
              bgcolor: 'primary.main',
              animation: 'loading-dots 1.4s infinite ease-in-out both',
              animationDelay: `${i * 0.16}s`,
              '@keyframes loading-dots': {
                '0%, 80%, 100%': {
                  transform: 'scale(0)',
                },
                '40%': {
                  transform: 'scale(1)',
                },
              },
            }}
          />
        ))}
      </Box>
      {message && (
        <Typography variant={getTypographyVariant()} color="text.secondary">
          {message}
        </Typography>
      )}
    </Box>
  );

  const renderSkeleton = () => {
    const { 
      lines = 3, 
      showAvatar = false, 
      showActions = false,
      variant: skeletonVariant = 'text',
      animation = 'wave'
    } = skeletonProps;

    return (
      <Card sx={{ ...sx }}>
        <CardContent>
          <Stack spacing={1}>
            {showAvatar && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Skeleton variant="circular" width={40} height={40} animation={animation} />
                <Box sx={{ flex: 1 }}>
                  <Skeleton variant="text" width="60%" height={24} animation={animation} />
                  <Skeleton variant="text" width="40%" height={16} animation={animation} />
                </Box>
              </Box>
            )}
            
            {Array.from({ length: lines }, (_, i) => (
              <Skeleton
                key={i}
                variant={skeletonVariant}
                width={i === lines - 1 ? '60%' : '100%'}
                height={skeletonVariant === 'text' ? 20 : 140}
                animation={animation}
              />
            ))}
            
            {showActions && (
              <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                <Skeleton variant="rectangular" width={80} height={32} animation={animation} />
                <Skeleton variant="rectangular" width={120} height={32} animation={animation} />
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>
    );
  };

  const renderContent = () => {
    switch (variant) {
      case 'skeleton':
        return renderSkeleton();
      case 'linear':
        return renderLinear();
      case 'dots':
        return renderDots();
      default:
        return renderSpinner();
    }
  };

  if (overlay) {
    return (
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          bgcolor: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(2px)',
          zIndex: 9998,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {renderContent()}
      </Box>
    );
  }

  return renderContent();
};

// Pre-configured loading states for common use cases
export const LoadingSpinner: React.FC<Partial<LoadingStateProps>> = (props) => (
  <LoadingState variant="spinner" {...props} />
);

export const LoadingSkeleton: React.FC<Partial<LoadingStateProps>> = (props) => (
  <LoadingState variant="skeleton" {...props} />
);

export const LoadingLinear: React.FC<Partial<LoadingStateProps>> = (props) => (
  <LoadingState variant="linear" {...props} />
);

export const LoadingOverlay: React.FC<Partial<LoadingStateProps>> = (props) => (
  <LoadingState overlay {...props} />
);

// Grid skeleton for lists/grids
export interface GridSkeletonProps {
  items?: number;
  columns?: number;
  itemHeight?: number;
  showActions?: boolean;
  animation?: 'pulse' | 'wave' | false;
}

export const GridSkeleton: React.FC<GridSkeletonProps> = ({
  items = 6,
  columns = 3,
  itemHeight = 200,
  showActions = true,
  animation = 'wave',
}) => {
  return (
    <Box 
      sx={{ 
        display: 'grid', 
        gridTemplateColumns: `repeat(${columns}, 1fr)`, 
        gap: 2,
        '@media (max-width: 900px)': {
          gridTemplateColumns: 'repeat(2, 1fr)',
        },
        '@media (max-width: 600px)': {
          gridTemplateColumns: '1fr',
        },
      }}
    >
      {Array.from({ length: items }, (_, i) => (
        <Card key={i}>
          <Skeleton variant="rectangular" height={itemHeight * 0.6} animation={animation} />
          <CardContent>
            <Skeleton variant="text" width="80%" height={24} animation={animation} sx={{ mb: 1 }} />
            <Skeleton variant="text" width="60%" height={16} animation={animation} sx={{ mb: 1 }} />
            <Skeleton variant="text" width="40%" height={16} animation={animation} sx={{ mb: 2 }} />
            
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <Skeleton variant="rectangular" width={60} height={24} animation={animation} />
              <Skeleton variant="rectangular" width={80} height={24} animation={animation} />
            </Box>
            
            {showActions && (
              <Skeleton variant="rectangular" width="100%" height={36} animation={animation} />
            )}
          </CardContent>
        </Card>
      ))}
    </Box>
  );
};

export default LoadingState;