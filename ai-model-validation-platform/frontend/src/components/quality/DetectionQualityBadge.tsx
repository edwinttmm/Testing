/**
 * Detection Quality Badge Component
 *
 * Clear visual indicator for detection quality status with:
 * - "Validated ✓" or "Degraded ⚠️" display
 * - Color-coded badges (green/yellow/red)
 * - Tooltip with detailed information
 * - Small and unobtrusive design
 */

import React from 'react';
import { Chip, Tooltip, Box } from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  HelpOutline as HelpOutlineIcon
} from '@mui/icons-material';

interface DetectionQualityBadgeProps {
  usableForValidation: boolean;
  timingDegraded?: boolean;
  timingVerified?: boolean;
  qualityScore?: number;
  degradationReason?: string;
  showTooltip?: boolean;
  size?: 'small' | 'medium';
}

export const DetectionQualityBadge: React.FC<DetectionQualityBadgeProps> = ({
  usableForValidation,
  timingDegraded = false,
  timingVerified = false,
  qualityScore,
  degradationReason,
  showTooltip = true,
  size = 'small'
}) => {
  // Determine badge appearance
  const getStatusConfig = () => {
    if (!usableForValidation || timingDegraded) {
      return {
        label: 'Degraded',
        icon: <WarningIcon />,
        color: 'warning' as const,
        bgColor: '#fff3e0',
        textColor: '#e65100'
      };
    }

    if (timingVerified) {
      return {
        label: 'Validated ✓',
        icon: <CheckCircleIcon />,
        color: 'success' as const,
        bgColor: '#e8f5e9',
        textColor: '#2e7d32'
      };
    }

    return {
      label: 'Usable',
      icon: <CheckCircleIcon />,
      color: 'success' as const,
      bgColor: '#e8f5e9',
      textColor: '#2e7d32'
    };
  };

  const status = getStatusConfig();

  // Build tooltip content
  const tooltipContent = () => {
    if (!showTooltip) return '';

    const parts: string[] = [];

    if (usableForValidation && timingVerified) {
      parts.push('✓ Timing verified with ground truth');
    } else if (usableForValidation && !timingDegraded) {
      parts.push('✓ Usable for validation');
    } else if (timingDegraded) {
      parts.push('⚠️ Timing accuracy degraded');
    } else {
      parts.push('❌ Not usable for validation');
    }

    if (qualityScore !== undefined) {
      parts.push(`Quality Score: ${(qualityScore * 100).toFixed(1)}%`);
    }

    if (degradationReason) {
      parts.push(`Reason: ${degradationReason}`);
    }

    if (!usableForValidation || timingDegraded) {
      parts.push('⚡ May affect result accuracy');
    }

    return parts.join('\n');
  };

  const badge = (
    <Chip
      icon={status.icon}
      label={status.label}
      size={size}
      sx={{
        fontWeight: 500,
        fontSize: size === 'small' ? '0.75rem' : '0.875rem',
        backgroundColor: status.bgColor,
        color: status.textColor,
        border: `1px solid ${status.textColor}40`,
        '& .MuiChip-icon': {
          color: status.textColor
        },
        '&:hover': {
          backgroundColor: status.bgColor,
          opacity: 0.9
        }
      }}
    />
  );

  if (!showTooltip) {
    return badge;
  }

  return (
    <Tooltip
      title={
        <Box sx={{ whiteSpace: 'pre-line', p: 0.5 }}>
          {tooltipContent()}
        </Box>
      }
      arrow
      placement="top"
    >
      {badge}
    </Tooltip>
  );
};

/**
 * Compact version for use in tables or tight spaces
 */
export const CompactQualityIndicator: React.FC<{
  usableForValidation: boolean;
  timingDegraded?: boolean;
}> = ({ usableForValidation, timingDegraded }) => {
  const icon = !usableForValidation || timingDegraded
    ? <WarningIcon sx={{ color: 'warning.main', fontSize: 16 }} />
    : <CheckCircleIcon sx={{ color: 'success.main', fontSize: 16 }} />;

  const tooltipText = !usableForValidation || timingDegraded
    ? 'Quality degraded - may affect results'
    : 'Quality validated';

  return (
    <Tooltip title={tooltipText} arrow>
      <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
        {icon}
      </Box>
    </Tooltip>
  );
};
