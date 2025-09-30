import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Button,
  ButtonGroup,
  Chip,
  IconButton,
  Tooltip,
  Divider,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField
} from '@mui/material';
import {
  Refresh,
  Download,
  Settings,
  FilterList,
  DateRange,
  Schedule,
  ViewModule,
  Pause,
  PlayArrow,
  GetApp
} from '@mui/icons-material';

interface DashboardControlsProps {
  timeRange: '1h' | '6h' | '24h' | '7d' | '30d';
  autoRefresh: boolean;
  refreshInterval: number;
  view: 'overview' | 'analytics' | 'health' | 'activity';
  onTimeRangeChange: (range: '1h' | '6h' | '24h' | '7d' | '30d') => void;
  onAutoRefreshChange: (enabled: boolean) => void;
  onRefreshIntervalChange: (interval: number) => void;
  onViewChange: (view: 'overview' | 'analytics' | 'health' | 'activity') => void;
  onRefresh: () => void;
  onExport: (format: 'json' | 'csv' | 'pdf') => void;
  isConnected: boolean;
  lastUpdate?: Date;
}

export const DashboardControls: React.FC<DashboardControlsProps> = ({
  timeRange,
  autoRefresh,
  refreshInterval,
  view,
  onTimeRangeChange,
  onAutoRefreshChange,
  onRefreshIntervalChange,
  onViewChange,
  onRefresh,
  onExport,
  isConnected,
  lastUpdate
}) => {
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  const [customInterval, setCustomInterval] = useState(refreshInterval);

  const timeRangeOptions = [
    { value: '1h', label: 'Last Hour' },
    { value: '6h', label: 'Last 6 Hours' },
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' }
  ] as const;

  const viewOptions = [
    { value: 'overview', label: 'Overview', icon: <ViewModule /> },
    { value: 'analytics', label: 'Analytics', icon: <Settings /> },
    { value: 'health', label: 'System Health', icon: <Settings /> },
    { value: 'activity', label: 'Activity', icon: <Schedule /> }
  ] as const;

  const refreshIntervals = [
    { value: 5000, label: '5 seconds' },
    { value: 10000, label: '10 seconds' },
    { value: 30000, label: '30 seconds' },
    { value: 60000, label: '1 minute' },
    { value: 300000, label: '5 minutes' }
  ];

  const getConnectionStatus = () => {
    if (!isConnected) {
      return { label: 'Disconnected', color: 'error' as const };
    }
    return { label: 'Connected', color: 'success' as const };
  };

  const formatLastUpdate = () => {
    if (!lastUpdate) return 'Never';
    const now = new Date();
    const diff = now.getTime() - lastUpdate.getTime();
    
    if (diff < 60000) {
      return 'Just now';
    } else if (diff < 3600000) {
      return `${Math.floor(diff / 60000)}m ago`;
    } else {
      return lastUpdate.toLocaleTimeString();
    }
  };

  const handleExport = (format: 'json' | 'csv' | 'pdf') => {
    onExport(format);
    setExportDialogOpen(false);
  };

  const handleSaveSettings = () => {
    onRefreshIntervalChange(customInterval);
    setSettingsDialogOpen(false);
  };

  return (
    <>
      <Card>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            {/* Connection Status */}
            <Grid item xs={12} sm={6} md={2}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip
                  {...getConnectionStatus()}
                  size="small"
                  variant="outlined"
                />
                <Typography variant="caption" color="text.secondary">
                  {formatLastUpdate()}
                </Typography>
              </Box>
            </Grid>

            {/* View Selector */}
            <Grid item xs={12} sm={6} md={3}>
              <ButtonGroup size="small" variant="outlined" fullWidth>
                {viewOptions.map((option) => (
                  <Button
                    key={option.value}
                    variant={view === option.value ? 'contained' : 'outlined'}
                    onClick={() => onViewChange(option.value)}
                    startIcon={option.icon}
                    sx={{ minWidth: 0 }}
                  >
                    <Typography variant="caption" sx={{ display: { xs: 'none', sm: 'block' } }}>
                      {option.label}
                    </Typography>
                  </Button>
                ))}
              </ButtonGroup>
            </Grid>

            {/* Time Range */}
            <Grid item xs={12} sm={6} md={2}>
              <FormControl size="small" fullWidth>
                <InputLabel>Time Range</InputLabel>
                <Select
                  value={timeRange}
                  label="Time Range"
                  onChange={(e) => onTimeRangeChange(e.target.value as any)}
                  startAdornment={<DateRange sx={{ mr: 1, fontSize: 16 }} />}
                >
                  {timeRangeOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Auto Refresh Toggle */}
            <Grid item xs={12} sm={6} md={2}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={autoRefresh}
                      onChange={(e) => onAutoRefreshChange(e.target.checked)}
                      size="small"
                    />
                  }
                  label={
                    <Typography variant="caption">
                      Auto ({refreshInterval / 1000}s)
                    </Typography>
                  }
                />
                <Tooltip title={autoRefresh ? 'Pause Auto-refresh' : 'Resume Auto-refresh'}>
                  <IconButton 
                    size="small" 
                    onClick={() => onAutoRefreshChange(!autoRefresh)}
                    color={autoRefresh ? 'primary' : 'default'}
                  >
                    {autoRefresh ? <Pause /> : <PlayArrow />}
                  </IconButton>
                </Tooltip>
              </Box>
            </Grid>

            {/* Action Buttons */}
            <Grid item xs={12} sm={12} md={3}>
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                <Tooltip title="Refresh Data">
                  <IconButton 
                    onClick={onRefresh}
                    disabled={!isConnected}
                    size="small"
                    color="primary"
                  >
                    <Refresh />
                  </IconButton>
                </Tooltip>
                
                <Tooltip title="Export Data">
                  <IconButton 
                    onClick={() => setExportDialogOpen(true)}
                    size="small"
                    color="secondary"
                  >
                    <Download />
                  </IconButton>
                </Tooltip>
                
                <Tooltip title="Dashboard Settings">
                  <IconButton 
                    onClick={() => setSettingsDialogOpen(true)}
                    size="small"
                  >
                    <Settings />
                  </IconButton>
                </Tooltip>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Export Dialog */}
      <Dialog open={exportDialogOpen} onClose={() => setExportDialogOpen(false)}>
        <DialogTitle>Export Dashboard Data</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Choose the format for exporting dashboard data and metrics.
          </Typography>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={() => handleExport('json')}
              fullWidth
            >
              Export as JSON
            </Button>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={() => handleExport('csv')}
              fullWidth
            >
              Export as CSV
            </Button>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={() => handleExport('pdf')}
              fullWidth
            >
              Export as PDF Report
            </Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportDialogOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>

      {/* Settings Dialog */}
      <Dialog open={settingsDialogOpen} onClose={() => setSettingsDialogOpen(false)}>
        <DialogTitle>Dashboard Settings</DialogTitle>
        <DialogContent>
          <Box sx={{ minWidth: 300, pt: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Auto-refresh Settings
            </Typography>
            
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Refresh Interval</InputLabel>
              <Select
                value={customInterval}
                label="Refresh Interval"
                onChange={(e) => setCustomInterval(Number(e.target.value))}
              >
                {refreshIntervals.map((interval) => (
                  <MenuItem key={interval.value} value={interval.value}>
                    {interval.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControlLabel
              control={
                <Switch
                  checked={autoRefresh}
                  onChange={(e) => onAutoRefreshChange(e.target.checked)}
                />
              }
              label="Enable auto-refresh"
            />

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              Connection Information
            </Typography>
            
            <Typography variant="body2" color="text.secondary">
              Status: <Chip {...getConnectionStatus()} size="small" />
            </Typography>
            
            <Typography variant="body2" color="text.secondary">
              Last Update: {formatLastUpdate()}
            </Typography>
            
            <Typography variant="body2" color="text.secondary">
              Current View: {viewOptions.find(v => v.value === view)?.label}
            </Typography>
            
            <Typography variant="body2" color="text.secondary">
              Time Range: {timeRangeOptions.find(t => t.value === timeRange)?.label}
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveSettings} variant="contained">
            Save Settings
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default DashboardControls;