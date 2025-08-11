import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Skeleton,
} from '@mui/material';

interface AccessibleStatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactElement;
  color: string;
  subtitle?: string;
  loading?: boolean;
  trend?: {
    value: number;
    direction: 'up' | 'down' | 'stable';
  };
  ariaLabel?: string;
}

const AccessibleStatCard: React.FC<AccessibleStatCardProps> = ({ 
  title, 
  value, 
  icon, 
  color, 
  subtitle, 
  loading = false,
  trend,
  ariaLabel 
}) => {
  const getTrendColor = (direction: string) => {
    switch (direction) {
      case 'up': return 'success.main';
      case 'down': return 'error.main';
      default: return 'text.secondary';
    }
  };

  const getTrendAriaLabel = () => {
    if (!trend) return '';
    const direction = trend.direction === 'up' ? 'increased' : 
                     trend.direction === 'down' ? 'decreased' : 'remained stable';
    return `${title} has ${direction} by ${Math.abs(trend.value)}%`;
  };

  if (loading) {
    return (
      <Card 
        sx={{ 
          height: '100%',
          minHeight: 140,
        }}
        role="status"
        aria-label="Loading statistics"
      >
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Skeleton variant="rectangular" width={48} height={48} sx={{ mr: 2, borderRadius: 1 }} />
            <Box sx={{ flexGrow: 1 }}>
              <Skeleton variant="text" width="60%" height={32} />
              <Skeleton variant="text" width="80%" height={20} />
            </Box>
          </Box>
          {subtitle && <Skeleton variant="text" width="40%" height={16} />}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card 
      sx={{ 
        height: '100%',
        minHeight: 140,
        transition: 'box-shadow 0.2s ease-in-out, transform 0.1s ease-in-out',
        '&:hover': {
          boxShadow: 4,
          transform: 'translateY(-2px)',
        },
        '&:focus-within': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: 2,
        }
      }}
      role="region"
      aria-label={ariaLabel || `${title}: ${value}`}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
          <Box
            sx={{
              p: 1.5,
              borderRadius: 2,
              bgcolor: `${color}.light`,
              color: `${color}.main`,
              mr: 2,
              minWidth: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            aria-hidden="true"
          >
{icon}
          </Box>
          <Box sx={{ flexGrow: 1 }}>
            <Typography 
              variant="h4" 
              component="div" 
              fontWeight="bold"
              sx={{ 
                lineHeight: 1.2,
                mb: 0.5,
                color: 'text.primary',
              }}
              aria-live="polite"
            >
              {typeof value === 'number' ? value.toLocaleString() : value}
            </Typography>
            <Typography 
              color="text.secondary" 
              variant="body2"
              sx={{ 
                fontWeight: 500,
                mb: trend ? 0.5 : 0,
              }}
            >
              {title}
            </Typography>
            {trend && (
              <Box 
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center',
                  gap: 0.5,
                }}
                aria-label={getTrendAriaLabel()}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: getTrendColor(trend.direction),
                    fontWeight: 600,
                  }}
                >
                  {trend.direction === 'up' ? '↗' : trend.direction === 'down' ? '↘' : '→'} 
                  {Math.abs(trend.value)}%
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
        {subtitle && (
          <Typography 
            color="text.secondary" 
            variant="caption"
            sx={{ 
              display: 'block',
              lineHeight: 1.4,
            }}
          >
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default AccessibleStatCard;