/**
 * Quality Filter Dropdown Component
 *
 * Functional filter control with:
 * - Dropdown showing counts for each filter
 * - Real-time filtering of detection list
 * - Preserves other active filters
 * - Clear visual feedback
 */

import React from 'react';
import {
  FormControl,
  Select,
  MenuItem,
  InputLabel,
  Box,
  Chip,
  Typography,
  SelectChangeEvent
} from '@mui/material';
import {
  FilterList as FilterListIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  AllInclusive as AllInclusiveIcon
} from '@mui/icons-material';
import { QualityFilterType, QualityFilterStats } from '../../types/quality';

interface QualityFilterDropdownProps {
  currentFilter: QualityFilterType;
  filterStats: QualityFilterStats;
  onFilterChange: (filter: QualityFilterType) => void;
  disabled?: boolean;
  fullWidth?: boolean;
  size?: 'small' | 'medium';
}

export const QualityFilterDropdown: React.FC<QualityFilterDropdownProps> = ({
  currentFilter,
  filterStats,
  onFilterChange,
  disabled = false,
  fullWidth = false,
  size = 'small'
}) => {
  const handleChange = (event: SelectChangeEvent<QualityFilterType>) => {
    onFilterChange(event.target.value as QualityFilterType);
  };

  const getFilterIcon = (filter: QualityFilterType) => {
    switch (filter) {
      case 'validated':
        return <CheckCircleIcon sx={{ fontSize: 18, color: 'success.main' }} />;
      case 'degraded':
        return <WarningIcon sx={{ fontSize: 18, color: 'warning.main' }} />;
      case 'verified':
        return <CheckCircleIcon sx={{ fontSize: 18, color: 'primary.main' }} />;
      case 'all':
      default:
        return <AllInclusiveIcon sx={{ fontSize: 18, color: 'action.active' }} />;
    }
  };

  const getFilterLabel = (filter: QualityFilterType, count: number) => {
    const labels = {
      all: 'All Detections',
      validated: 'Validated',
      degraded: 'Degraded',
      verified: 'Verified'
    };
    return `${labels[filter]} (${count})`;
  };

  return (
    <FormControl size={size} fullWidth={fullWidth} disabled={disabled}>
      <InputLabel id="quality-filter-label">Filter by Quality</InputLabel>
      <Select
        labelId="quality-filter-label"
        id="quality-filter-select"
        value={currentFilter}
        label="Filter by Quality"
        onChange={handleChange}
        renderValue={(value) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {getFilterIcon(value)}
            <Typography variant="body2">
              {getFilterLabel(value, filterStats[`${value}_count` as keyof QualityFilterStats])}
            </Typography>
          </Box>
        )}
        sx={{
          minWidth: 200,
          '& .MuiSelect-select': {
            display: 'flex',
            alignItems: 'center'
          }
        }}
      >
        <MenuItem value="all">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
            {getFilterIcon('all')}
            <Typography variant="body2" sx={{ flex: 1 }}>
              All Detections
            </Typography>
            <Chip
              label={filterStats.all_count}
              size="small"
              sx={{ minWidth: 50, justifyContent: 'center' }}
            />
          </Box>
        </MenuItem>

        <MenuItem value="validated">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
            {getFilterIcon('validated')}
            <Typography variant="body2" sx={{ flex: 1 }}>
              Validated
            </Typography>
            <Chip
              label={filterStats.validated_count}
              size="small"
              color="success"
              sx={{ minWidth: 50, justifyContent: 'center' }}
            />
          </Box>
        </MenuItem>

        <MenuItem value="degraded">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
            {getFilterIcon('degraded')}
            <Typography variant="body2" sx={{ flex: 1 }}>
              Degraded Timing
            </Typography>
            <Chip
              label={filterStats.degraded_count}
              size="small"
              color="warning"
              sx={{ minWidth: 50, justifyContent: 'center' }}
            />
          </Box>
        </MenuItem>

        <MenuItem value="verified">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
            {getFilterIcon('verified')}
            <Typography variant="body2" sx={{ flex: 1 }}>
              GT Verified
            </Typography>
            <Chip
              label={filterStats.verified_count}
              size="small"
              color="primary"
              sx={{ minWidth: 50, justifyContent: 'center' }}
            />
          </Box>
        </MenuItem>
      </Select>

      {/* Helper text */}
      {filterStats.degraded_count > 0 && currentFilter !== 'degraded' && (
        <Typography variant="caption" color="warning.main" sx={{ mt: 0.5, ml: 1.5 }}>
          ⚠️ {filterStats.degraded_count} detection{filterStats.degraded_count !== 1 ? 's' : ''} with timing issues
        </Typography>
      )}
    </FormControl>
  );
};

/**
 * Simple chip-based filter (alternative compact design)
 */
export const QualityFilterChips: React.FC<{
  currentFilter: QualityFilterType;
  filterStats: QualityFilterStats;
  onFilterChange: (filter: QualityFilterType) => void;
}> = ({ currentFilter, filterStats, onFilterChange }) => {
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      <Chip
        icon={<AllInclusiveIcon />}
        label={`All (${filterStats.all_count})`}
        onClick={() => onFilterChange('all')}
        color={currentFilter === 'all' ? 'primary' : 'default'}
        variant={currentFilter === 'all' ? 'filled' : 'outlined'}
      />
      <Chip
        icon={<CheckCircleIcon />}
        label={`Validated (${filterStats.validated_count})`}
        onClick={() => onFilterChange('validated')}
        color={currentFilter === 'validated' ? 'success' : 'default'}
        variant={currentFilter === 'validated' ? 'filled' : 'outlined'}
      />
      <Chip
        icon={<WarningIcon />}
        label={`Degraded (${filterStats.degraded_count})`}
        onClick={() => onFilterChange('degraded')}
        color={currentFilter === 'degraded' ? 'warning' : 'default'}
        variant={currentFilter === 'degraded' ? 'filled' : 'outlined'}
      />
      <Chip
        icon={<CheckCircleIcon />}
        label={`Verified (${filterStats.verified_count})`}
        onClick={() => onFilterChange('verified')}
        color={currentFilter === 'verified' ? 'primary' : 'default'}
        variant={currentFilter === 'verified' ? 'filled' : 'outlined'}
      />
    </Box>
  );
};
