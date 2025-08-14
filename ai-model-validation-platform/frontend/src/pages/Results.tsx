import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  GetApp,
  Visibility,
  TrendingUp,
  TrendingDown,
  Assessment,
  CheckCircle,
  Error,
  Warning,
  FileDownload,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Project } from '../services/types';

interface TestResult {
  sessionId: string;
  sessionName: string;
  projectName: string;
  status: 'completed' | 'failed' | 'running';
  accuracy: number;
  precision: number;
  recall: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  totalDetections: number;
  startedAt: string;
  completedAt?: string;
  duration: number; // in seconds
}

const Results: React.FC = () => {
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<string>('all');
  const [timeRange, setTimeRange] = useState<string>('7days');

  const loadData = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Load projects
      const projectList = await apiService.getProjects();
      setProjects(projectList);

      // Load test sessions and results
      const testSessions = await apiService.getTestSessions(
        selectedProject === 'all' ? undefined : selectedProject
      );

      // Transform sessions into results
      const results: TestResult[] = await Promise.all(
        testSessions.map(async (session) => {
          try {
            // Try to load detailed results, fallback to session data
            let sessionResults;
            try {
              sessionResults = await apiService.getTestResults(session.id);
            } catch {
              // Use metrics from session if available
              sessionResults = session.metrics || {};
            }

            // Calculate duration from session timestamps
            const startTime = session.createdAt ? new Date(session.createdAt).getTime() : Date.now();
            const endTime = session.completedAt ? new Date(session.completedAt).getTime() : Date.now();
            const durationSeconds = Math.max(Math.floor((endTime - startTime) / 1000), 60);

            return {
              sessionId: session.id,
              sessionName: session.name || `Test ${session.id.slice(0, 8)}`,
              projectName: projectList.find(p => p.id === session.projectId)?.name || 'Unknown Project',
              status: session.status as 'completed' | 'failed' | 'running',
              accuracy: sessionResults.accuracy || session.metrics?.accuracy || 0,
              precision: sessionResults.precision || session.metrics?.precision || 0,
              recall: sessionResults.recall || session.metrics?.recall || 0,
              truePositives: sessionResults.truePositives || session.metrics?.truePositives || 0,
              falsePositives: sessionResults.falsePositives || session.metrics?.falsePositives || 0,
              falseNegatives: sessionResults.falseNegatives || session.metrics?.falseNegatives || 0,
              totalDetections: sessionResults.totalDetections || session.metrics?.totalDetections || 0,
              startedAt: session.createdAt || new Date().toISOString(),
              completedAt: session.completedAt || new Date().toISOString(),
              duration: durationSeconds,
            };
          } catch (error) {
            console.error(`Failed to load results for session ${session.id}:`, error);
            // Return failed result with minimal data
            return {
              sessionId: session.id,
              sessionName: session.name || `Test ${session.id.slice(0, 8)}`,
              projectName: projectList.find(p => p.id === session.projectId)?.name || 'Unknown Project',
              status: 'failed' as const,
              accuracy: 0,
              precision: 0,
              recall: 0,
              truePositives: 0,
              falsePositives: 0,
              falseNegatives: 0,
              totalDetections: 0,
              startedAt: session.createdAt || new Date().toISOString(),
              completedAt: session.completedAt || new Date().toISOString(),
              duration: 60,
            };
          }
        })
      );

      // Filter based on time range if needed
      let filteredResults = results;
      if (timeRange !== 'all') {
        const now = new Date();
        const timeRangeMs = {
          '24hours': 24 * 60 * 60 * 1000,
          '7days': 7 * 24 * 60 * 60 * 1000,
          '30days': 30 * 24 * 60 * 60 * 1000,
          '90days': 90 * 24 * 60 * 60 * 1000,
        }[timeRange];
        
        if (timeRangeMs) {
          filteredResults = results.filter(result => {
            const resultTime = new Date(result.startedAt).getTime();
            return (now.getTime() - resultTime) <= timeRangeMs;
          });
        }
      }

      setTestResults(filteredResults.filter(r => r.status === 'completed'));
    } catch (err: any) {
      console.error('Failed to load results:', err);
      setError('Failed to load test results');
    } finally {
      setLoading(false);
    }
  }, [selectedProject, timeRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);


  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'failed':
        return <Error color="error" />;
      default:
        return <Warning color="warning" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      default:
        return 'warning';
    }
  };

  const getPerformanceColor = (value: number, type: 'accuracy' | 'precision' | 'recall') => {
    if (value >= 90) return 'success';
    if (value >= 80) return 'warning';
    return 'error';
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const exportResults = (format: 'csv' | 'pdf') => {
    // Mock export functionality
    const data = testResults.map(result => ({
      'Session Name': result.sessionName,
      'Project': result.projectName,
      'Status': result.status,
      'Accuracy (%)': result.accuracy.toFixed(2),
      'Precision (%)': result.precision.toFixed(2),
      'Recall (%)': result.recall.toFixed(2),
      'True Positives': result.truePositives,
      'False Positives': result.falsePositives,
      'False Negatives': result.falseNegatives,
      'Total Detections': result.totalDetections,
      'Duration': formatDuration(result.duration),
      'Started At': new Date(result.startedAt).toLocaleString(),
    }));

    if (format === 'csv') {
      const csvContent = [
        Object.keys(data[0]).join(','),
        ...data.map(row => Object.values(row).join(','))
      ].join('\n');
      
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test-results-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    }
    // PDF export would be implemented with a library like jsPDF
  };

  const overallMetrics = testResults.length > 0 ? {
    avgAccuracy: testResults.reduce((sum, r) => sum + r.accuracy, 0) / testResults.length,
    avgPrecision: testResults.reduce((sum, r) => sum + r.precision, 0) / testResults.length,
    avgRecall: testResults.reduce((sum, r) => sum + r.recall, 0) / testResults.length,
    totalTests: testResults.length,
    successfulTests: testResults.filter(r => r.status === 'completed').length,
  } : null;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Results & Analytics</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<FileDownload />}
            onClick={() => exportResults('csv')}
            disabled={testResults.length === 0}
          >
            Export CSV
          </Button>
          <Button
            variant="outlined"
            startIcon={<GetApp />}
            onClick={() => exportResults('pdf')}
            disabled={testResults.length === 0}
          >
            Export PDF
          </Button>
        </Box>
      </Box>

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 4 }}>
              <FormControl fullWidth>
                <InputLabel>Project</InputLabel>
                <Select
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                  label="Project"
                >
                  <MenuItem value="all">All Projects</MenuItem>
                  {projects.map((project) => (
                    <MenuItem key={project.id} value={project.id}>
                      {project.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <FormControl fullWidth>
                <InputLabel>Time Range</InputLabel>
                <Select
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value)}
                  label="Time Range"
                >
                  <MenuItem value="24hours">Last 24 Hours</MenuItem>
                  <MenuItem value="7days">Last 7 Days</MenuItem>
                  <MenuItem value="30days">Last 30 Days</MenuItem>
                  <MenuItem value="90days">Last 90 Days</MenuItem>
                  <MenuItem value="all">All Time</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Typography variant="body2" color="text.secondary">
                Showing {testResults.length} completed tests
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {error} - Showing sample data for demonstration
        </Alert>
      )}

      {/* Overall Metrics */}
      {overallMetrics && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Assessment sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6">Avg Accuracy</Typography>
                </Box>
                <Typography variant="h4" color={getPerformanceColor(overallMetrics.avgAccuracy, 'accuracy')}>
                  {overallMetrics.avgAccuracy.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={overallMetrics.avgAccuracy}
                  color={getPerformanceColor(overallMetrics.avgAccuracy, 'accuracy') as any}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <TrendingUp sx={{ mr: 1, color: 'success.main' }} />
                  <Typography variant="h6">Avg Precision</Typography>
                </Box>
                <Typography variant="h4" color={getPerformanceColor(overallMetrics.avgPrecision, 'precision')}>
                  {overallMetrics.avgPrecision.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={overallMetrics.avgPrecision}
                  color={getPerformanceColor(overallMetrics.avgPrecision, 'precision') as any}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <TrendingDown sx={{ mr: 1, color: 'info.main' }} />
                  <Typography variant="h6">Avg Recall</Typography>
                </Box>
                <Typography variant="h4" color={getPerformanceColor(overallMetrics.avgRecall, 'recall')}>
                  {overallMetrics.avgRecall.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={overallMetrics.avgRecall}
                  color={getPerformanceColor(overallMetrics.avgRecall, 'recall') as any}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <CheckCircle sx={{ mr: 1, color: 'success.main' }} />
                  <Typography variant="h6">Success Rate</Typography>
                </Box>
                <Typography variant="h4" color="success.main">
                  {((overallMetrics.successfulTests / overallMetrics.totalTests) * 100).toFixed(1)}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {overallMetrics.successfulTests} of {overallMetrics.totalTests} tests
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Results Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Results
          </Typography>
          
          {loading ? (
            <LinearProgress />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Session</TableCell>
                    <TableCell>Project</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Accuracy</TableCell>
                    <TableCell align="right">Precision</TableCell>
                    <TableCell align="right">Recall</TableCell>
                    <TableCell align="right">TP/FP/FN</TableCell>
                    <TableCell align="right">Duration</TableCell>
                    <TableCell align="right">Started</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {testResults.map((result) => (
                    <TableRow key={result.sessionId} hover>
                      <TableCell>
                        <Typography variant="subtitle2">
                          {result.sessionName}
                        </Typography>
                      </TableCell>
                      <TableCell>{result.projectName}</TableCell>
                      <TableCell>
                        <Chip
                          icon={getStatusIcon(result.status)}
                          label={result.status.toUpperCase()}
                          color={getStatusColor(result.status) as any}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          color={getPerformanceColor(result.accuracy, 'accuracy')}
                          fontWeight="medium"
                        >
                          {result.accuracy.toFixed(1)}%
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          color={getPerformanceColor(result.precision, 'precision')}
                          fontWeight="medium"
                        >
                          {result.precision.toFixed(1)}%
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          color={getPerformanceColor(result.recall, 'recall')}
                          fontWeight="medium"
                        >
                          {result.recall.toFixed(1)}%
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                          <Chip label={`${result.truePositives}`} color="success" size="small" />
                          <Chip label={`${result.falsePositives}`} color="error" size="small" />
                          <Chip label={`${result.falseNegatives}`} color="warning" size="small" />
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        {formatDuration(result.duration)}
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2">
                          {new Date(result.startedAt).toLocaleDateString()}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(result.startedAt).toLocaleTimeString()}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="View Details">
                          <IconButton size="small">
                            <Visibility />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Export Results">
                          <IconButton size="small">
                            <GetApp />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                  {testResults.length === 0 && !loading && (
                    <TableRow>
                      <TableCell colSpan={10} align="center">
                        <Typography color="text.secondary">
                          No test results found. Run some tests to see results here.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default Results;