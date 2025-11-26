/**
 * Quality Warning Banner Component
 *
 * Beautiful, accessible banner for displaying quality warnings with:
 * - Material-UI Alert component
 * - Severity-based colors
 * - Expandable details
 * - Dismissible with "don't show again" option
 * - WCAG 2.1 AA compliant
 */

import React, { useState } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Chip,
  Collapse,
  IconButton,
  Stack,
  Typography,
  Button,
  Checkbox,
  FormControlLabel,
  Tooltip
} from '@mui/material';
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import {
  QualityWarning,
  QualityWarningSeverity,
  QualityLevel
} from '../../types/quality';

interface QualityWarningBannerProps {
  warnings: QualityWarning[];
  qualityLevel?: QualityLevel;
  validationRate?: number;
  onDismiss?: (warningId: string, permanent?: boolean) => void;
  onAction?: (warning: QualityWarning) => void;
  onViewDetails?: () => void;
}

const severityToMuiSeverity = (
  severity: QualityWarningSeverity
): 'error' | 'warning' | 'info' | 'success' => {
  switch (severity) {
    case QualityWarningSeverity.CRITICAL:
    case QualityWarningSeverity.HIGH:
      return 'error';
    case QualityWarningSeverity.MEDIUM:
      return 'warning';
    case QualityWarningSeverity.LOW:
    case QualityWarningSeverity.INFO:
      return 'info';
    default:
      return 'info';
  }
};

const severityIcon = (severity: QualityWarningSeverity) => {
  switch (severity) {
    case QualityWarningSeverity.CRITICAL:
    case QualityWarningSeverity.HIGH:
      return <ErrorIcon />;
    case QualityWarningSeverity.MEDIUM:
      return <WarningIcon />;
    default:
      return <InfoIcon />;
  }
};

const qualityLevelColor = (level?: QualityLevel): string => {
  switch (level) {
    case QualityLevel.EXCELLENT:
      return 'success';
    case QualityLevel.GOOD:
      return 'success';
    case QualityLevel.FAIR:
      return 'warning';
    case QualityLevel.POOR:
      return 'error';
    default:
      return 'default';
  }
};

export const QualityWarningBanner: React.FC<QualityWarningBannerProps> = ({
  warnings,
  qualityLevel,
  validationRate,
  onDismiss,
  onAction,
  onViewDetails
}) => {
  const [expanded, setExpanded] = useState(false);
  const [dontShowAgain, setDontShowAgain] = useState(false);

  if (warnings.length === 0) {
    return null;
  }

  // Sort warnings by severity (most critical first)
  const sortedWarnings = [...warnings].sort((a, b) => {
    const severityOrder = {
      [QualityWarningSeverity.CRITICAL]: 5,
      [QualityWarningSeverity.HIGH]: 4,
      [QualityWarningSeverity.MEDIUM]: 3,
      [QualityWarningSeverity.LOW]: 2,
      [QualityWarningSeverity.INFO]: 1
    };
    return severityOrder[b.severity] - severityOrder[a.severity];
  });

  const mostCriticalWarning = sortedWarnings[0];
  const criticalCount = sortedWarnings.filter(
    w => w.severity === QualityWarningSeverity.CRITICAL || w.severity === QualityWarningSeverity.HIGH
  ).length;

  const handleDismiss = () => {
    if (onDismiss && mostCriticalWarning) {
      onDismiss(mostCriticalWarning.id, dontShowAgain);
    }
  };

  return (
    <Alert
      severity={severityToMuiSeverity(mostCriticalWarning.severity)}
      icon={severityIcon(mostCriticalWarning.severity)}
      sx={{
        mb: 2,
        boxShadow: 2,
        '& .MuiAlert-message': {
          width: '100%'
        }
      }}
      action={
        <IconButton
          aria-label="Close quality warning"
          color="inherit"
          size="small"
          onClick={handleDismiss}
        >
          <CloseIcon fontSize="inherit" />
        </IconButton>
      }
    >
      <AlertTitle sx={{ fontWeight: 600 }}>
        {mostCriticalWarning.category.charAt(0).toUpperCase() +
         mostCriticalWarning.category.slice(1)} Quality Warning
        {warnings.length > 1 && ` (${warnings.length} issues)`}
      </AlertTitle>

      <Typography variant="body2" sx={{ mb: 1 }}>
        {mostCriticalWarning.message}
      </Typography>

      {mostCriticalWarning.detection_count && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Affecting {mostCriticalWarning.detection_count} detection{mostCriticalWarning.detection_count !== 1 ? 's' : ''}
        </Typography>
      )}

      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1, flexWrap: 'wrap', gap: 1 }}>
        {qualityLevel && (
          <Chip
            label={`Quality: ${qualityLevel}`}
            color={qualityLevelColor(qualityLevel) as any}
            size="small"
            sx={{ fontWeight: 500 }}
          />
        )}
        {validationRate !== undefined && (
          <Chip
            label={`Validation Rate: ${validationRate.toFixed(1)}%`}
            color={validationRate >= 95 ? 'success' : validationRate >= 80 ? 'warning' : 'error'}
            size="small"
          />
        )}
        {criticalCount > 0 && (
          <Chip
            label={`${criticalCount} Critical Issue${criticalCount !== 1 ? 's' : ''}`}
            color="error"
            size="small"
          />
        )}
      </Stack>

      {/* Expandable details section */}
      {warnings.length > 1 && (
        <Box sx={{ mt: 1 }}>
          <Button
            size="small"
            onClick={() => setExpanded(!expanded)}
            endIcon={expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
          >
            {expanded ? 'Hide' : 'Show'} All Warnings
          </Button>

          <Collapse in={expanded}>
            <Box sx={{ mt: 2, pl: 2, borderLeft: '3px solid', borderColor: 'divider' }}>
              {sortedWarnings.slice(1).map((warning, index) => (
                <Box key={warning.id} sx={{ mb: 2 }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                    <Chip
                      label={warning.severity}
                      size="small"
                      color={severityToMuiSeverity(warning.severity)}
                    />
                    <Typography variant="subtitle2" fontWeight={600}>
                      {warning.category}
                    </Typography>
                  </Stack>
                  <Typography variant="body2" sx={{ mb: 0.5 }}>
                    {warning.message}
                  </Typography>
                  {warning.recommendation && (
                    <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                      Recommendation: {warning.recommendation}
                    </Typography>
                  )}
                  {warning.impact && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      Impact: {warning.impact}
                    </Typography>
                  )}
                </Box>
              ))}
            </Box>
          </Collapse>
        </Box>
      )}

      {/* Action buttons */}
      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        {mostCriticalWarning.recommendation && (
          <Tooltip title={mostCriticalWarning.recommendation}>
            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              {mostCriticalWarning.recommendation}
            </Typography>
          </Tooltip>
        )}

        {onViewDetails && (
          <Button
            size="small"
            variant="outlined"
            onClick={onViewDetails}
            aria-label="View quality details"
          >
            View Details
          </Button>
        )}

        {onAction && mostCriticalWarning && (
          <Button
            size="small"
            variant="contained"
            onClick={() => onAction(mostCriticalWarning)}
            aria-label="Take action on warning"
          >
            Take Action
          </Button>
        )}
      </Stack>

      {/* Don't show again option */}
      {onDismiss && (
        <FormControlLabel
          control={
            <Checkbox
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
              size="small"
            />
          }
          label={<Typography variant="caption">Don't show this type of warning again</Typography>}
          sx={{ mt: 1 }}
        />
      )}
    </Alert>
  );
};
