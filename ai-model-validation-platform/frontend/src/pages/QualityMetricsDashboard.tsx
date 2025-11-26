/**
 * Quality Metrics Dashboard Page
 *
 * Complete dashboard for quality monitoring with:
 * - Global metrics at top
 * - Recent sessions list with quality indicators
 * - Charts/graphs for trends
 * - Alert history
 * - Responsive layout (desktop/tablet/mobile)
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Button,
  Alert,
  Stack,
  Divider,
  Skeleton,
  AppBar,
  Toolbar,
  Tabs,
  Tab
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Assessment as AssessmentIcon
} from '@mui/icons-material';
import { QualityMetricsCard } from '../components/quality/QualityMetricsCard';
import {
  GlobalQualityMetrics,
  QualityLevel,
  QualityWarning,
  QualityWarningSeverity
} from '../types/quality';
import { qualityApi } from '../services/qualityApi';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const qualityLevelColor = (level: QualityLevel): 'success' | 'warning' | 'error' | 'default' => {
  switch (level) {
    case QualityLevel.EXCELLENT:
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

export const QualityMetricsDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [globalMetrics, setGlobalMetrics] = useState<GlobalQualityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchGlobalMetrics = async () => {
    try {
      setError(null);
      const data = await qualityApi.getGlobalQualityMetrics();
      setGlobalMetrics(data);
    } catch (err) {
      console.error('Failed to fetch global metrics:', err);
      setError('Failed to load quality metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGlobalMetrics();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchGlobalMetrics, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleRefresh = () => {
    setLoading(true);
    qualityApi.clearAllCache();
    fetchGlobalMetrics();
  };

  const handleExport = () => {
    // TODO: Implement export functionality
    console.log('Export quality report');
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Skeleton variant="rectangular" height={400} />
      </Container>
    );
  }

  if (error || !globalMetrics) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={handleRefresh}>
            Retry
          </Button>
        }>
          {error || 'No quality data available'}
        </Alert>
      </Container>
    );
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      {/* Header */}
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <IconButton
            edge="start"
            onClick={() => navigate(-1)}
            aria-label="Go back"
            sx={{ mr: 2 }}
          >
            <ArrowBackIcon />
          </IconButton>
          <AssessmentIcon sx={{ mr: 2 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Quality Metrics Dashboard
          </Typography>
          <Button
            startIcon={<DownloadIcon />}
            onClick={handleExport}
            sx={{ mr: 1 }}
          >
            Export
          </Button>
          <IconButton onClick={handleRefresh} aria-label="Refresh data">
            <RefreshIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        {/* Global Stats Cards */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {/* Overall Quality */}
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom variant="body2">
                  Overall Quality
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Typography variant="h4" component="div">
                    {globalMetrics.overall_quality_level}
                  </Typography>
                  <Chip
                    label={globalMetrics.overall_quality_level}
                    color={qualityLevelColor(globalMetrics.overall_quality_level)}
                    size="small"
                  />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {globalMetrics.overall_validation_rate.toFixed(1)}% validation rate
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Total Sessions */}
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom variant="body2">
                  Total Sessions
                </Typography>
                <Typography variant="h4" component="div">
                  {globalMetrics.total_sessions}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {globalMetrics.total_detections.toLocaleString()} total detections
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Sessions with Issues */}
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom variant="body2">
                  Sessions with Issues
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="h4" component="div" color="warning.main">
                    {globalMetrics.sessions_with_issues}
                  </Typography>
                  <WarningIcon color="warning" />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {((globalMetrics.sessions_with_issues / globalMetrics.total_sessions) * 100).toFixed(1)}% of sessions
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Recent Warnings */}
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom variant="body2">
                  Active Warnings
                </Typography>
                <Typography variant="h4" component="div" color="error.main">
                  {globalMetrics.recent_warnings.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {globalMetrics.recent_warnings.filter(w =>
                    w.severity === QualityWarningSeverity.CRITICAL ||
                    w.severity === QualityWarningSeverity.HIGH
                  ).length} critical
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Quality Distribution */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Quality Distribution
                </Typography>
                <Stack spacing={2}>
                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">Excellent</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {globalMetrics.sessions_excellent}
                      </Typography>
                    </Box>
                    <Box sx={{ bgcolor: '#e8f5e9', height: 8, borderRadius: 1, overflow: 'hidden' }}>
                      <Box
                        sx={{
                          bgcolor: '#2e7d32',
                          height: '100%',
                          width: `${(globalMetrics.sessions_excellent / globalMetrics.total_sessions) * 100}%`
                        }}
                      />
                    </Box>
                  </Box>

                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">Good</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {globalMetrics.sessions_good}
                      </Typography>
                    </Box>
                    <Box sx={{ bgcolor: '#f1f8e9', height: 8, borderRadius: 1, overflow: 'hidden' }}>
                      <Box
                        sx={{
                          bgcolor: '#558b2f',
                          height: '100%',
                          width: `${(globalMetrics.sessions_good / globalMetrics.total_sessions) * 100}%`
                        }}
                      />
                    </Box>
                  </Box>

                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">Fair</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {globalMetrics.sessions_fair}
                      </Typography>
                    </Box>
                    <Box sx={{ bgcolor: '#fff3e0', height: 8, borderRadius: 1, overflow: 'hidden' }}>
                      <Box
                        sx={{
                          bgcolor: '#f57c00',
                          height: '100%',
                          width: `${(globalMetrics.sessions_fair / globalMetrics.total_sessions) * 100}%`
                        }}
                      />
                    </Box>
                  </Box>

                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">Poor</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {globalMetrics.sessions_poor}
                      </Typography>
                    </Box>
                    <Box sx={{ bgcolor: '#ffebee', height: 8, borderRadius: 1, overflow: 'hidden' }}>
                      <Box
                        sx={{
                          bgcolor: '#c62828',
                          height: '100%',
                          width: `${(globalMetrics.sessions_poor / globalMetrics.total_sessions) * 100}%`
                        }}
                      />
                    </Box>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          {/* Recent Warnings */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Recent Warnings
                </Typography>
                {globalMetrics.recent_warnings.length === 0 ? (
                  <Alert severity="success" icon={<CheckCircleIcon />}>
                    No active warnings
                  </Alert>
                ) : (
                  <Stack spacing={1} sx={{ maxHeight: 300, overflow: 'auto' }}>
                    {globalMetrics.recent_warnings.slice(0, 5).map((warning) => (
                      <Alert
                        key={warning.id}
                        severity={warning.severity === QualityWarningSeverity.CRITICAL ||
                                 warning.severity === QualityWarningSeverity.HIGH ? 'error' : 'warning'}
                        sx={{ fontSize: '0.875rem' }}
                      >
                        <Typography variant="body2" fontWeight={600}>
                          {warning.category.toUpperCase()}
                        </Typography>
                        <Typography variant="caption">
                          {warning.message}
                        </Typography>
                      </Alert>
                    ))}
                  </Stack>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Tabs for detailed views */}
        <Paper sx={{ mb: 3 }}>
          <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
            <Tab label="Trends" />
            <Tab label="Warnings History" />
            <Tab label="Settings" />
          </Tabs>
        </Paper>

        <TabPanel value={activeTab} index={0}>
          <Typography variant="h6" gutterBottom>
            Quality Trends
          </Typography>
          <Alert severity="info">
            Trend visualization coming soon
          </Alert>
        </TabPanel>

        <TabPanel value={activeTab} index={1}>
          <Typography variant="h6" gutterBottom>
            Warnings History
          </Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Severity</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>Session</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {globalMetrics.recent_warnings.map((warning) => (
                  <TableRow key={warning.id}>
                    <TableCell>
                      <Chip
                        label={warning.severity}
                        size="small"
                        color={warning.severity === QualityWarningSeverity.CRITICAL ||
                               warning.severity === QualityWarningSeverity.HIGH ? 'error' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>{warning.category}</TableCell>
                    <TableCell>{warning.message}</TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        onClick={() => navigate(`/hil-results/${warning.session_id}`)}
                      >
                        View
                      </Button>
                    </TableCell>
                    <TableCell>{new Date(warning.created_at).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        <TabPanel value={activeTab} index={2}>
          <Typography variant="h6" gutterBottom>
            Dashboard Settings
          </Typography>
          <Stack spacing={2}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>
                  Auto Refresh
                </Typography>
                <Button
                  variant={autoRefresh ? 'contained' : 'outlined'}
                  onClick={() => setAutoRefresh(!autoRefresh)}
                >
                  {autoRefresh ? 'Enabled' : 'Disabled'}
                </Button>
              </CardContent>
            </Card>
          </Stack>
        </TabPanel>

        {/* Last Updated */}
        <Typography variant="caption" color="text.secondary" display="block" textAlign="center" sx={{ mt: 4 }}>
          Last updated: {new Date(globalMetrics.last_updated).toLocaleString()}
        </Typography>
      </Container>
    </Box>
  );
};

export default QualityMetricsDashboard;
