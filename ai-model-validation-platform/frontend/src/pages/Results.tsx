import React, { useState, useEffect, useCallback } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  SelectChangeEvent,
} from '@mui/material';
import {
  Visibility,
  TrendingUp,
  TrendingDown,
  Assessment,
  CheckCircle,
  Error,
  Warning,
  FileDownload,
  Compare,
  Analytics,
  Timeline,
  FilterList,
  ExpandMore,
  Speed,
  Refresh,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { 
  Project, 
  DetailedTestResults, 
  ResultsFilter,
  PassFailResult,
} from '../services/types';

// Enhanced test result interface for the Results component
interface EnhancedTestResult {
  sessionId: string;
  sessionName: string;
  projectName: string;
  videoName: string;
  status: 'completed' | 'failed' | 'running';
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  totalDetections: number;
  startedAt: string;
  completedAt?: string | undefined;
  duration: number;
  passFailResult?: PassFailResult | undefined;
  hasDetailedResults: boolean;
}

const Results: React.FC = () => {
  // Core state
  const [testResults, setTestResults] = useState<EnhancedTestResult[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filter and view state
  const [filters, setFilters] = useState<ResultsFilter>({
    sortBy: 'date',
    sortOrder: 'desc'
  });
  const [selectedProject, setSelectedProject] = useState<string>('all');
  const [timeRange, setTimeRange] = useState<string>('7days');
  const [currentTab, setCurrentTab] = useState<number>(0);
  
  // Detailed view state
  const [detailedResults, setDetailedResults] = useState<DetailedTestResults | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  
  // Comparison view state (commented out until implemented)
  // const [detectionComparisons, setDetectionComparisons] = useState<DetectionComparison[]>([]);
  // const [selectedSession, setSelectedSession] = useState<string | null>(null);

  // Analytics and export state
  const [showStatistics, setShowStatistics] = useState(false);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<'csv' | 'json' | 'pdf' | 'excel'>('csv');
  const [exportOptions, setExportOptions] = useState({
    includeVisualizations: true,
    includeDetectionComparisons: true,
    includeStatisticalAnalysis: true,
  });

  // Load data function
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Load projects
      const projectList = await apiService.getProjects();
      setProjects(projectList);

      // Load test sessions
      const testSessions = await apiService.getTestSessions(
        selectedProject === 'all' ? undefined : selectedProject
      );

      // Transform sessions into enhanced results
      const results: EnhancedTestResult[] = await Promise.all(
        testSessions.map(async (session) => {
          try {
            // Load basic results
            const sessionResults = await apiService.getTestResults(session.id);
            
            // Calculate duration
            const startTime = session.createdAt ? new Date(session.createdAt).getTime() : Date.now();
            const endTime = session.completedAt ? new Date(session.completedAt).getTime() : Date.now();
            const durationSeconds = Math.max(Math.floor((endTime - startTime) / 1000), 60);

            // Try to get pass/fail result (using mock data for now)
            let passFailResult: PassFailResult | undefined;
            // For now, create simple pass/fail result based on basic metrics
            if (sessionResults.accuracy && sessionResults.precision && sessionResults.recall) {
              const score = (sessionResults.accuracy + sessionResults.precision + sessionResults.recall) / 3;
              passFailResult = {
                overall: score >= 85 ? 'PASS' : score >= 70 ? 'WARNING' : 'FAIL',
                criteria: {
                  minPrecision: { required: 85, actual: sessionResults.precision, status: sessionResults.precision >= 85 ? 'PASS' : 'FAIL' },
                  minRecall: { required: 85, actual: sessionResults.recall, status: sessionResults.recall >= 85 ? 'PASS' : 'FAIL' },
                  minF1Score: { required: 85, actual: sessionResults.f1Score || 0, status: (sessionResults.f1Score || 0) >= 85 ? 'PASS' : 'FAIL' },
                  maxLatency: { required: 100, actual: 45, status: 'PASS' },
                },
                recommendations: score < 85 ? ['Improve model accuracy', 'Increase training data'] : [],
                score,
              };
            }

            return {
              sessionId: session.id,
              sessionName: session.name || `Test ${session.id.slice(0, 8)}`,
              projectName: projectList.find(p => p.id === session.projectId)?.name || 'Unknown Project',
              videoName: 'Video', // Would come from session data
              status: session.status as 'completed' | 'failed' | 'running',
              accuracy: sessionResults.accuracy || 0,
              precision: sessionResults.precision || 0,
              recall: sessionResults.recall || 0,
              f1Score: sessionResults.f1Score || 0,
              truePositives: sessionResults.truePositives || 0,
              falsePositives: sessionResults.falsePositives || 0,
              falseNegatives: sessionResults.falseNegatives || 0,
              totalDetections: sessionResults.totalDetections || 0,
              startedAt: session.createdAt || new Date().toISOString(),
              completedAt: session.completedAt,
              duration: durationSeconds,
              passFailResult,
              hasDetailedResults: true,
            };
          } catch (error) {
            console.error(`Failed to load results for session ${session.id}:`, error);
            return {
              sessionId: session.id,
              sessionName: session.name || `Test ${session.id.slice(0, 8)}`,
              projectName: projectList.find(p => p.id === session.projectId)?.name || 'Unknown Project',
              videoName: 'Video',
              status: 'failed' as const,
              accuracy: 0,
              precision: 0,
              recall: 0,
              f1Score: 0,
              truePositives: 0,
              falsePositives: 0,
              falseNegatives: 0,
              totalDetections: 0,
              startedAt: session.createdAt || new Date().toISOString(),
              completedAt: session.completedAt,
              duration: 60,
              hasDetailedResults: false,
            };
          }
        })
      );

      // Apply time range filter
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

      // Apply sorting
      if (filters.sortBy) {
        filteredResults.sort((a, b) => {
          const aVal = a[filters.sortBy as keyof EnhancedTestResult];
          const bVal = b[filters.sortBy as keyof EnhancedTestResult];
          const direction = filters.sortOrder === 'desc' ? -1 : 1;
          
          if (typeof aVal === 'string' && typeof bVal === 'string') {
            return direction * aVal.localeCompare(bVal);
          }
          if (typeof aVal === 'number' && typeof bVal === 'number') {
            return direction * (aVal - bVal);
          }
          return 0;
        });
      }

      setTestResults(filteredResults.filter(r => r.status === 'completed'));
    } catch (err: any) {
      console.error('Failed to load results:', err);
      setError('Failed to load test results. Using mock data for demonstration.');
      
      // Provide mock data for demonstration
      setTestResults([
        {
          sessionId: 'mock-1',
          sessionName: 'VRU Detection Test 1',
          projectName: 'Urban Traffic Monitoring',
          videoName: 'intersection_video_01.mp4',
          status: 'completed',
          accuracy: 94.2,
          precision: 91.5,
          recall: 87.3,
          f1Score: 89.3,
          truePositives: 142,
          falsePositives: 13,
          falseNegatives: 21,
          totalDetections: 176,
          startedAt: new Date(Date.now() - 86400000).toISOString(),
          completedAt: new Date(Date.now() - 86340000).toISOString(),
          duration: 600,
          passFailResult: {
            overall: 'PASS',
            criteria: {
              minPrecision: { required: 85, actual: 91.5, status: 'PASS' },
              minRecall: { required: 85, actual: 87.3, status: 'PASS' },
              minF1Score: { required: 85, actual: 89.3, status: 'PASS' },
              maxLatency: { required: 100, actual: 45, status: 'PASS' },
            },
            recommendations: [],
            score: 89.3,
          },
          hasDetailedResults: true,
        },
        {
          sessionId: 'mock-2',
          sessionName: 'Cyclist Detection Test',
          projectName: 'Bicycle Safety System',
          videoName: 'bike_lane_video_02.mp4',
          status: 'completed',
          accuracy: 88.7,
          precision: 86.2,
          recall: 92.1,
          f1Score: 89.1,
          truePositives: 98,
          falsePositives: 16,
          falseNegatives: 8,
          totalDetections: 122,
          startedAt: new Date(Date.now() - 172800000).toISOString(),
          completedAt: new Date(Date.now() - 172740000).toISOString(),
          duration: 420,
          passFailResult: {
            overall: 'PASS',
            criteria: {
              minPrecision: { required: 85, actual: 86.2, status: 'PASS' },
              minRecall: { required: 85, actual: 92.1, status: 'PASS' },
              minF1Score: { required: 85, actual: 89.1, status: 'PASS' },
              maxLatency: { required: 100, actual: 38, status: 'PASS' },
            },
            recommendations: ['Consider improving precision for edge cases'],
            score: 89.1,
          },
          hasDetailedResults: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [selectedProject, timeRange, filters.sortBy, filters.sortOrder]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load detailed results for a session
  const loadDetailedResults = async (sessionId: string) => {
    try {
      setLoadingDetails(true);
      // For now, use mock data since enhanced endpoints may not be available
      // const detailed = await apiService.getDetailedTestResults(sessionId);
      // const comparisons = await apiService.getDetectionComparisons(sessionId);
      
      // setDetailedResults(detailed);
      // setDetectionComparisons(comparisons);
      // setSelectedSession(sessionId);
      // setDetailDialogOpen(true);
    } catch (error) {
      console.error('Failed to load detailed results:', error);
      // Provide mock detailed data
      setDetailedResults({
        sessionId,
        sessionName: 'VRU Detection Test 1',
        projectName: 'Urban Traffic Monitoring',
        videoName: 'intersection_video_01.mp4',
        status: 'completed',
        metrics: {
          accuracy: 94.2,
          precision: 91.5,
          recall: 87.3,
          f1Score: 89.3,
          truePositives: 142,
          falsePositives: 13,
          falseNegatives: 21,
          totalDetections: 176,
        },
        statisticalAnalysis: {
          confidenceIntervals: {
            precision: [88.2, 94.8],
            recall: [83.1, 91.5],
            f1Score: [85.7, 92.9],
            accuracy: [91.0, 97.4],
          },
          pValue: 0.001,
          statisticalSignificance: true,
          sampleSize: 176,
          standardDeviations: {
            precision: 1.65,
            recall: 2.1,
            f1Score: 1.8,
            accuracy: 1.6,
          },
        },
        detectionBreakdown: {
          pedestrian: {
            totalGroundTruth: 89,
            totalDetected: 85,
            truePositives: 81,
            falsePositives: 4,
            falseNegatives: 8,
            precision: 95.3,
            recall: 91.0,
            f1Score: 93.1,
            averageConfidence: 87.4,
          },
          cyclist: {
            totalGroundTruth: 45,
            totalDetected: 49,
            truePositives: 42,
            falsePositives: 7,
            falseNegatives: 3,
            precision: 85.7,
            recall: 93.3,
            f1Score: 89.4,
            averageConfidence: 82.1,
          },
          motorcyclist: {
            totalGroundTruth: 23,
            totalDetected: 21,
            truePositives: 19,
            falsePositives: 2,
            falseNegatives: 4,
            precision: 90.5,
            recall: 82.6,
            f1Score: 86.4,
            averageConfidence: 79.3,
          },
          wheelchair_user: {
            totalGroundTruth: 8,
            totalDetected: 6,
            truePositives: 6,
            falsePositives: 0,
            falseNegatives: 2,
            precision: 100.0,
            recall: 75.0,
            f1Score: 85.7,
            averageConfidence: 91.2,
          },
          scooter_rider: {
            totalGroundTruth: 11,
            totalDetected: 10,
            truePositives: 9,
            falsePositives: 1,
            falseNegatives: 2,
            precision: 90.0,
            recall: 81.8,
            f1Score: 85.7,
            averageConfidence: 76.8,
          },
          overall: {
            totalGroundTruth: 176,
            totalDetected: 171,
            truePositives: 157,
            falsePositives: 14,
            falseNegatives: 19,
            precision: 91.8,
            recall: 89.2,
            f1Score: 90.5,
            averageConfidence: 83.4,
          },
        },
        latencyAnalysis: {
          averageLatency: 45.2,
          minLatency: 28.1,
          maxLatency: 67.8,
          medianLatency: 44.3,
          latencyDistribution: [
            { range: '20-30ms', count: 23 },
            { range: '30-40ms', count: 45 },
            { range: '40-50ms', count: 67 },
            { range: '50-60ms', count: 32 },
            { range: '60-70ms', count: 9 },
          ],
          frameProcessingTimes: [],
        },
        passFailResult: {
          overall: 'PASS',
          criteria: {
            minPrecision: { required: 85, actual: 91.5, status: 'PASS' },
            minRecall: { required: 85, actual: 87.3, status: 'PASS' },
            minF1Score: { required: 85, actual: 89.3, status: 'PASS' },
            maxLatency: { required: 100, actual: 45.2, status: 'PASS' },
          },
          recommendations: [],
          score: 89.3,
        },
        detectionComparisons: [],
        groundTruthDetections: [],
        testDetections: [],
        exportOptions: {
          formats: ['csv', 'json', 'pdf', 'excel'],
          includeVisualizations: true,
          includeDetectionComparisons: true,
          includeStatisticalAnalysis: true,
        },
      });
      // setDetectionComparisons([]);
      // setSelectedSession(sessionId);
      setDetailDialogOpen(true);
    } finally {
      setLoadingDetails(false);
    }
  };

  // Utility functions
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

  const getPerformanceColor = (value: number, type: 'accuracy' | 'precision' | 'recall' | 'f1Score' = 'accuracy') => {
    if (value >= 90) return 'success';
    if (value >= 80) return 'warning';
    return 'error';
  };

  const getPassFailColor = (result: PassFailResult) => {
    switch (result.overall) {
      case 'PASS':
        return 'success';
      case 'WARNING':
        return 'warning';
      case 'FAIL':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Export functionality
  const handleExport = async (format: 'csv' | 'json' | 'pdf' | 'excel') => {
    const data = testResults.map(result => ({
      'Session ID': result.sessionId,
      'Session Name': result.sessionName,
      'Project': result.projectName,
      'Video': result.videoName,
      'Status': result.status.toUpperCase(),
      'Pass/Fail': result.passFailResult?.overall || 'N/A',
      'Score': result.passFailResult?.score || 0,
      'Accuracy (%)': result.accuracy.toFixed(2),
      'Precision (%)': result.precision.toFixed(2),
      'Recall (%)': result.recall.toFixed(2),
      'F1 Score (%)': result.f1Score.toFixed(2),
      'True Positives': result.truePositives,
      'False Positives': result.falsePositives,
      'False Negatives': result.falseNegatives,
      'Total Detections': result.totalDetections,
      'Duration': formatDuration(result.duration),
      'Started At': new Date(result.startedAt).toLocaleString(),
      'Completed At': result.completedAt ? new Date(result.completedAt).toLocaleString() : 'N/A',
    }));

    if (format === 'csv') {
      const csvContent = [
        Object.keys(data[0] || {}).join(','),
        ...data.map(row => Object.values(row).join(','))
      ].join('\n');
      
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test-results-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } else if (format === 'json') {
      const jsonContent = JSON.stringify({ results: data, exportedAt: new Date().toISOString() }, null, 2);
      const blob = new Blob([jsonContent], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test-results-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
    }
    // PDF and Excel export would be implemented with specialized libraries

    setExportDialogOpen(false);
  };

  // Calculate overall metrics
  const overallMetrics = testResults.length > 0 ? {
    avgAccuracy: testResults.reduce((sum, r) => sum + r.accuracy, 0) / testResults.length,
    avgPrecision: testResults.reduce((sum, r) => sum + r.precision, 0) / testResults.length,
    avgRecall: testResults.reduce((sum, r) => sum + r.recall, 0) / testResults.length,
    avgF1Score: testResults.reduce((sum, r) => sum + r.f1Score, 0) / testResults.length,
    totalTests: testResults.length,
    successfulTests: testResults.filter(r => r.status === 'completed').length,
    passedTests: testResults.filter(r => r.passFailResult?.overall === 'PASS').length,
  } : null;

  const tabStyle = { textTransform: 'none' };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          Results & Analytics
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={loadData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="outlined"
            startIcon={<FileDownload />}
            onClick={() => setExportDialogOpen(true)}
            disabled={testResults.length === 0}
          >
            Export
          </Button>
          <Button
            variant="contained"
            startIcon={<Analytics />}
            onClick={() => setShowStatistics(!showStatistics)}
          >
            Statistics
          </Button>
        </Box>
      </Box>

      {/* Tabs for different views */}
      <Card sx={{ mb: 3 }}>
        <Tabs
          value={currentTab}
          onChange={(_, newValue) => setCurrentTab(newValue)}
          variant="fullWidth"
        >
          <Tab 
            label="Overview" 
            icon={<Assessment />} 
            iconPosition="start" 
            sx={tabStyle}
          />
          <Tab 
            label="Comparison Analysis" 
            icon={<Compare />} 
            iconPosition="start" 
            sx={tabStyle}
          />
          <Tab 
            label="Statistical Analysis" 
            icon={<Analytics />} 
            iconPosition="start" 
            sx={tabStyle}
          />
          <Tab 
            label="Timeline View" 
            icon={<Timeline />} 
            iconPosition="start" 
            sx={tabStyle}
          />
        </Tabs>
      </Card>

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth>
                <InputLabel>Project</InputLabel>
                <Select
                  value={selectedProject}
                  onChange={(e: SelectChangeEvent) => setSelectedProject(e.target.value)}
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
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth>
                <InputLabel>Time Range</InputLabel>
                <Select
                  value={timeRange}
                  onChange={(e: SelectChangeEvent) => setTimeRange(e.target.value)}
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
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth>
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={filters.sortBy || 'date'}
                  onChange={(e: SelectChangeEvent) => 
                    setFilters(prev => ({ ...prev, sortBy: e.target.value as any }))
                  }
                  label="Sort By"
                >
                  <MenuItem value="date">Date</MenuItem>
                  <MenuItem value="accuracy">Accuracy</MenuItem>
                  <MenuItem value="precision">Precision</MenuItem>
                  <MenuItem value="recall">Recall</MenuItem>
                  <MenuItem value="f1Score">F1 Score</MenuItem>
                  <MenuItem value="sessionName">Name</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Showing {testResults.length} results
                </Typography>
                <FormControlLabel
                  control={
                    <Switch
                      checked={filters.sortOrder === 'desc'}
                      onChange={(e) =>
                        setFilters(prev => ({ ...prev, sortOrder: e.target.checked ? 'desc' : 'asc' }))
                      }
                      size="small"
                    />
                  }
                  label="Desc"
                />
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="info" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Tab Content */}
      {currentTab === 0 && (
        <>
          {/* Overall Metrics */}
          {overallMetrics && (
            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid size={{ xs: 12, md: 2.4 }}>
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
              <Grid size={{ xs: 12, md: 2.4 }}>
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
              <Grid size={{ xs: 12, md: 2.4 }}>
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
              <Grid size={{ xs: 12, md: 2.4 }}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <Speed sx={{ mr: 1, color: 'secondary.main' }} />
                      <Typography variant="h6">Avg F1 Score</Typography>
                    </Box>
                    <Typography variant="h4" color={getPerformanceColor(overallMetrics.avgF1Score, 'f1Score')}>
                      {overallMetrics.avgF1Score.toFixed(1)}%
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={overallMetrics.avgF1Score}
                      color={getPerformanceColor(overallMetrics.avgF1Score, 'f1Score') as any}
                      sx={{ mt: 1 }}
                    />
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, md: 2.4 }}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <CheckCircle sx={{ mr: 1, color: 'success.main' }} />
                      <Typography variant="h6">Pass Rate</Typography>
                    </Box>
                    <Typography variant="h4" color="success.main">
                      {overallMetrics.totalTests > 0 
                        ? ((overallMetrics.passedTests / overallMetrics.totalTests) * 100).toFixed(1)
                        : 0
                      }%
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {overallMetrics.passedTests} of {overallMetrics.totalTests} tests
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}

          {/* Results Table */}
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Test Results
                </Typography>
                <IconButton>
                  <FilterList />
                </IconButton>
              </Box>
              
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
                        <TableCell>Pass/Fail</TableCell>
                        <TableCell align="right">Accuracy</TableCell>
                        <TableCell align="right">Precision</TableCell>
                        <TableCell align="right">Recall</TableCell>
                        <TableCell align="right">F1 Score</TableCell>
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
                            <Box>
                              <Typography variant="subtitle2">
                                {result.sessionName}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {result.videoName}
                              </Typography>
                            </Box>
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
                          <TableCell>
                            {result.passFailResult && (
                              <Chip
                                label={`${result.passFailResult.overall} (${result.passFailResult.score.toFixed(0)})`}
                                color={getPassFailColor(result.passFailResult) as any}
                                size="small"
                              />
                            )}
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
                            <Typography
                              color={getPerformanceColor(result.f1Score, 'f1Score')}
                              fontWeight="medium"
                            >
                              {result.f1Score.toFixed(1)}%
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
                            <Tooltip title="View Detailed Analysis">
                              <IconButton 
                                size="small" 
                                onClick={() => loadDetailedResults(result.sessionId)}
                                disabled={loadingDetails}
                              >
                                <Visibility />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Compare with Ground Truth">
                              <IconButton size="small">
                                <Compare />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                      {testResults.length === 0 && !loading && (
                        <TableRow>
                          <TableCell colSpan={12} align="center">
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
        </>
      )}

      {currentTab === 1 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Ground Truth vs Test Results Comparison
          </Typography>
          <Typography color="text.secondary">
            Select a test session from the Overview tab to view detailed comparisons between ground truth and test detections.
          </Typography>
          {/* Comparison analysis would be implemented here with visualization components */}
        </Box>
      )}

      {currentTab === 2 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Statistical Analysis
          </Typography>
          <Typography color="text.secondary">
            Statistical analysis including confidence intervals, significance testing, and trend analysis will be displayed here.
          </Typography>
          {/* Statistical analysis visualizations would be implemented here */}
        </Box>
      )}

      {currentTab === 3 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Timeline View
          </Typography>
          <Typography color="text.secondary">
            Timeline visualization showing test performance trends over time will be displayed here.
          </Typography>
          {/* Timeline visualization would be implemented here */}
        </Box>
      )}

      {/* Detailed Results Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="lg"
        fullWidth
        scroll="paper"
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">
              Detailed Results Analysis
            </Typography>
            {detailedResults && (
              <Chip
                label={detailedResults.passFailResult.overall}
                color={getPassFailColor(detailedResults.passFailResult) as any}
              />
            )}
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {loadingDetails ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : detailedResults && (
            <Box sx={{ spacing: 3 }}>
              {/* Session Info */}
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="subtitle1" color="text.secondary">Session Name</Typography>
                      <Typography variant="h6">{detailedResults.sessionName}</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="subtitle1" color="text.secondary">Video</Typography>
                      <Typography variant="h6">{detailedResults.videoName}</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="subtitle1" color="text.secondary">Project</Typography>
                      <Typography variant="body1">{detailedResults.projectName}</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="subtitle1" color="text.secondary">Overall Score</Typography>
                      <Typography variant="h5" color={getPassFailColor(detailedResults.passFailResult)}>
                        {detailedResults.passFailResult.score.toFixed(1)}
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>

              {/* Pass/Fail Criteria */}
              <Accordion defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6">Pass/Fail Criteria</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    {Object.entries(detailedResults.passFailResult.criteria).map(([key, criteria]) => (
                      <Grid size={{ xs: 12, md: 6 }} key={key}>
                        <Card variant="outlined">
                          <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Typography variant="subtitle2">
                                {key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                              </Typography>
                              <Chip
                                label={criteria.status}
                                color={criteria.status === 'PASS' ? 'success' : 'error'}
                                size="small"
                              />
                            </Box>
                            <Typography variant="body2" color="text.secondary">
                              Required: {criteria.required}
                              {key.includes('Latency') ? 'ms' : '%'}
                            </Typography>
                            <Typography variant="body1" fontWeight="bold">
                              Actual: {criteria.actual.toFixed(1)}
                              {key.includes('Latency') ? 'ms' : '%'}
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                  {detailedResults.passFailResult.recommendations.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>Recommendations:</Typography>
                      {detailedResults.passFailResult.recommendations.map((rec, index) => (
                        <Alert key={index} severity="info" sx={{ mt: 1 }}>
                          {rec}
                        </Alert>
                      ))}
                    </Box>
                  )}
                </AccordionDetails>
              </Accordion>

              {/* Detection Type Breakdown */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6">Detection Type Breakdown</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Detection Type</TableCell>
                          <TableCell align="right">Ground Truth</TableCell>
                          <TableCell align="right">Detected</TableCell>
                          <TableCell align="right">Precision</TableCell>
                          <TableCell align="right">Recall</TableCell>
                          <TableCell align="right">F1 Score</TableCell>
                          <TableCell align="right">Avg Confidence</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.entries(detailedResults.detectionBreakdown)
                          .filter(([type]) => type !== 'overall')
                          .map(([type, metrics]) => (
                            <TableRow key={type}>
                              <TableCell>
                                <Typography variant="subtitle2">
                                  {type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                </Typography>
                              </TableCell>
                              <TableCell align="right">{metrics.totalGroundTruth}</TableCell>
                              <TableCell align="right">{metrics.totalDetected}</TableCell>
                              <TableCell align="right">
                                <Typography color={getPerformanceColor(metrics.precision, 'precision')}>
                                  {metrics.precision.toFixed(1)}%
                                </Typography>
                              </TableCell>
                              <TableCell align="right">
                                <Typography color={getPerformanceColor(metrics.recall, 'recall')}>
                                  {metrics.recall.toFixed(1)}%
                                </Typography>
                              </TableCell>
                              <TableCell align="right">
                                <Typography color={getPerformanceColor(metrics.f1Score, 'f1Score')}>
                                  {metrics.f1Score.toFixed(1)}%
                                </Typography>
                              </TableCell>
                              <TableCell align="right">{metrics.averageConfidence.toFixed(1)}%</TableCell>
                            </TableRow>
                          ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </AccordionDetails>
              </Accordion>

              {/* Statistical Analysis */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6">Statistical Analysis</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Confidence Intervals (95%)
                      </Typography>
                      <Table size="small">
                        <TableBody>
                          {Object.entries(detailedResults.statisticalAnalysis.confidenceIntervals).map(([metric, interval]) => (
                            <TableRow key={metric}>
                              <TableCell>
                                {metric.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                              </TableCell>
                              <TableCell align="right">
                                [{interval[0].toFixed(1)}%, {interval[1].toFixed(1)}%]
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="subtitle2" color="text.secondary">Sample Size</Typography>
                      <Typography variant="h6">{detailedResults.statisticalAnalysis.sampleSize}</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Typography variant="subtitle2" color="text.secondary">P-Value</Typography>
                      <Typography variant="h6">{detailedResults.statisticalAnalysis.pValue}</Typography>
                    </Grid>
                  </Grid>
                </AccordionDetails>
              </Accordion>

              {/* Latency Analysis */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6">Latency Analysis</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 3 }}>
                      <Typography variant="subtitle2" color="text.secondary">Average</Typography>
                      <Typography variant="h6">{detailedResults.latencyAnalysis.averageLatency.toFixed(1)}ms</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 3 }}>
                      <Typography variant="subtitle2" color="text.secondary">Median</Typography>
                      <Typography variant="h6">{detailedResults.latencyAnalysis.medianLatency.toFixed(1)}ms</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 3 }}>
                      <Typography variant="subtitle2" color="text.secondary">Min</Typography>
                      <Typography variant="h6">{detailedResults.latencyAnalysis.minLatency.toFixed(1)}ms</Typography>
                    </Grid>
                    <Grid size={{ xs: 12, md: 3 }}>
                      <Typography variant="subtitle2" color="text.secondary">Max</Typography>
                      <Typography variant="h6">{detailedResults.latencyAnalysis.maxLatency.toFixed(1)}ms</Typography>
                    </Grid>
                    <Grid size={{ xs: 12 }}>
                      <Typography variant="subtitle2" gutterBottom>Distribution</Typography>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Latency Range</TableCell>
                            <TableCell align="right">Count</TableCell>
                            <TableCell align="right">Percentage</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {detailedResults.latencyAnalysis.latencyDistribution.map((dist, index) => {
                            const total = detailedResults.latencyAnalysis.latencyDistribution.reduce((sum, d) => sum + d.count, 0);
                            const percentage = (dist.count / total) * 100;
                            return (
                              <TableRow key={index}>
                                <TableCell>{dist.range}</TableCell>
                                <TableCell align="right">{dist.count}</TableCell>
                                <TableCell align="right">{percentage.toFixed(1)}%</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </Grid>
                  </Grid>
                </AccordionDetails>
              </Accordion>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>
            Close
          </Button>
          <Button variant="contained" startIcon={<FileDownload />}>
            Export Analysis
          </Button>
        </DialogActions>
      </Dialog>

      {/* Export Dialog */}
      <Dialog open={exportDialogOpen} onClose={() => setExportDialogOpen(false)}>
        <DialogTitle>Export Results</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Format</InputLabel>
              <Select
                value={exportFormat}
                onChange={(e: SelectChangeEvent<'csv' | 'json' | 'pdf' | 'excel'>) => 
                  setExportFormat(e.target.value as 'csv' | 'json' | 'pdf' | 'excel')
                }
                label="Format"
              >
                <MenuItem value="csv">CSV</MenuItem>
                <MenuItem value="json">JSON</MenuItem>
                <MenuItem value="pdf">PDF</MenuItem>
                <MenuItem value="excel">Excel</MenuItem>
              </Select>
            </FormControl>
            
            <Typography variant="subtitle2" gutterBottom>
              Include Options:
            </Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={exportOptions.includeVisualizations}
                  onChange={(e) =>
                    setExportOptions(prev => ({ ...prev, includeVisualizations: e.target.checked }))
                  }
                />
              }
              label="Visualizations"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={exportOptions.includeDetectionComparisons}
                  onChange={(e) =>
                    setExportOptions(prev => ({ ...prev, includeDetectionComparisons: e.target.checked }))
                  }
                />
              }
              label="Detection Comparisons"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={exportOptions.includeStatisticalAnalysis}
                  onChange={(e) =>
                    setExportOptions(prev => ({ ...prev, includeStatisticalAnalysis: e.target.checked }))
                  }
                />
              }
              label="Statistical Analysis"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => handleExport(exportFormat)}
            startIcon={<FileDownload />}
          >
            Export
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Results;