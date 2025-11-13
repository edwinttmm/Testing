import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
} from '@mui/material';
import { formatResultLabel, normalizeResultStatus } from '../../utils/testSessionUtils';

interface AccessibleCardProps {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
  ariaLabel?: string;
  role?: string;
}

interface ProgressItemProps {
  label: string;
  value: number;
  color: 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning';
  ariaLabel?: string;
}

export const AccessibleProgressItem: React.FC<ProgressItemProps> = ({
  label,
  value,
  color,
  ariaLabel
}) => (
  <Box sx={{ mb: 2 }} role="progressbar" aria-label={ariaLabel || `${label}: ${value}%`}>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
      <Typography variant="body2" component="span">
        {label}
      </Typography>
      <Typography variant="body2" component="span" aria-live="polite">
        {value}%
      </Typography>
    </Box>
    <LinearProgress 
      variant="determinate" 
      value={value} 
      color={color}
      aria-hidden="true"
      sx={{
        height: 6,
        borderRadius: 3,
        '& .MuiLinearProgress-bar': {
          borderRadius: 3,
        },
      }}
    />
  </Box>
);

interface SessionItemProps {
  sessionNumber: number;
  type: string;
  timeAgo: string;
  accuracy?: number | null;
  accuracyResult?: string | null;
  latencyResult?: string | null;
  overallResult?: string | null;
  latencyMeanMs?: number | null;
}

export const AccessibleSessionItem: React.FC<SessionItemProps> = ({
  sessionNumber,
  type,
  timeAgo,
  accuracy,
  accuracyResult,
  latencyResult,
  overallResult,
  latencyMeanMs
}) => {
  const normalizedAccuracy = normalizeResultStatus(accuracyResult);
  const normalizedLatency = normalizeResultStatus(latencyResult);
  const normalizedOverall = normalizeResultStatus(overallResult);
  const accuracyText = typeof accuracy === 'number' ? `${accuracy.toFixed(1)}%` : 'N/A';
  const latencyText = latencyMeanMs != null ? `${latencyMeanMs.toFixed(1)} ms` : 'N/A';

  const ariaParts = [
    `Test Session ${sessionNumber}`,
    type,
    `completed ${timeAgo}`,
    `Accuracy ${formatResultLabel(normalizedAccuracy)}${typeof accuracy === 'number' ? ` at ${accuracyText}` : ''}`,
    `Latency ${formatResultLabel(normalizedLatency)}`,
  ];
  if (latencyMeanMs != null) {
    ariaParts.push(`average latency ${latencyText}`);
  }
  if (normalizedOverall !== 'UNKNOWN') {
    ariaParts.push(`Overall ${formatResultLabel(normalizedOverall)}`);
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        py: 1.5,
        px: 1,
        borderBottom: '1px solid #f0f0f0',
        borderRadius: 1,
        '&:hover': {
          backgroundColor: 'action.hover',
        },
        '&:focus-within': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: 2,
        },
      }}
      role="listitem"
      tabIndex={0}
      aria-label={ariaParts.join(', ')}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="body2" fontWeight="medium" component="div">
            Test Session #{sessionNumber}
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div">
            {type} • {timeAgo}
          </Typography>
        </Box>
        <Typography 
          variant="body2" 
          color="success.main" 
          fontWeight="medium"
          aria-live="polite"
        >
          {accuracyText} F1
        </Typography>
      </Box>
      <Typography variant="caption" color="text.secondary">
        Accuracy {formatResultLabel(normalizedAccuracy)} • Latency {formatResultLabel(normalizedLatency)}
        {latencyMeanMs != null ? ` (${latencyText})` : ''}
        {normalizedOverall !== 'UNKNOWN' ? ` • Overall ${formatResultLabel(normalizedOverall)}` : ''}
      </Typography>
    </Box>
  );
};

const AccessibleCard: React.FC<AccessibleCardProps> = ({ 
  title, 
  children, 
  loading = false,
  ariaLabel,
  role = 'region'
}) => {
  if (loading) {
    return (
      <Card 
        sx={{ height: '100%', minHeight: 200 }}
        role="status"
        aria-label="Loading content"
      >
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Box sx={{ mt: 2 }}>
            {[1, 2, 3].map((i) => (
              <Box key={i} sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Box sx={{ width: '60%', height: 16, backgroundColor: 'action.hover', borderRadius: 1 }} />
                  <Box sx={{ width: '30%', height: 16, backgroundColor: 'action.hover', borderRadius: 1 }} />
                </Box>
                <LinearProgress sx={{ opacity: 0.3 }} />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card 
      sx={{ 
        height: '100%',
        minHeight: 200,
        transition: 'box-shadow 0.2s ease-in-out, transform 0.1s ease-in-out',
        '&:hover': {
          boxShadow: 4,
          transform: 'translateY(-1px)',
        },
        '&:focus-within': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: 2,
        }
      }}
      role={role}
      aria-label={ariaLabel || title}
    >
      <CardContent>
        <Typography 
          variant="h6" 
          gutterBottom
          component="h2"
          sx={{ 
            fontWeight: 600,
            mb: 2,
          }}
        >
          {title}
        </Typography>
        <Box sx={{ mt: 2 }}>
          {children}
        </Box>
      </CardContent>
    </Card>
  );
};

export default AccessibleCard;
