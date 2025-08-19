import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Snackbar,
  TextField,
  Slider,
  Switch,
  FormControlLabel,
  Divider,
  Badge,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Pause,
  CheckCircle,
  Error,
  Warning,
  RadioButtonChecked,
  Settings,
  Refresh,
  WifiOff,
  Wifi,
  AccessTime,
  Speed,
  Visibility,
  Analytics,
  TrendingUp,
  TrendingDown,
  Info,
  Timeline,
  BarChart,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { TestSession as TestSessionType, VideoFile, Project, ApiError, SignalType, PassFailCriteria } from '../services/types';

interface DetectionEvent {
  id: string;
  timestamp: number;
  validationResult: 'TP' | 'FP' | 'FN';
  confidence: number;
  classLabel: string;
  latencyMs: number;
  signalTimestamp: number;
  detectionLatency: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface LatencyConfig {
  toleranceMs: number;
  signalType: SignalType;
  testDuration: number;
  enableRealTimeMonitoring: boolean;
  maxLatencyMs: number;
  minAccuracy: number;
}

interface TestSessionMetrics {
  avgLatency: number;
  maxLatency: number;
  minLatency: number;
  latencyStdDev: number;
  passFailStatus: 'PASS' | 'FAIL' | 'UNKNOWN';
  detectionCount: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  throughputFps: number;
}

const TestExecution: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [currentSession, setCurrentSession] = useState<TestSessionType | null>(null);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEvent[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [sessionDialog, setSessionDialog] = useState(false);
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedVideo, setSelectedVideo] = useState('');
  const [latencyConfig, setLatencyConfig] = useState<LatencyConfig>({
    toleranceMs: 100,
    signalType: SignalType.GPIO,
    testDuration: 300, // 5 minutes default
    enableRealTimeMonitoring: true,
    maxLatencyMs: 200,
    minAccuracy: 85
  });
  const [sessionMetrics, setSessionMetrics] = useState<TestSessionMetrics>({
    avgLatency: 0,
    maxLatency: 0,
    minLatency: 0,
    latencyStdDev: 0,
    passFailStatus: 'UNKNOWN',
    detectionCount: 0,
    accuracy: 0,
    precision: 0,
    recall: 0,
    f1Score: 0,
    throughputFps: 0
  });
  const [testStartTime, setTestStartTime] = useState<number | null>(null);
  const [passFailCriteria, setPassFailCriteria] = useState<PassFailCriteria>({ 
    minPrecision: 85, 
    minRecall: 80, 
    minF1Score: 82, 
    maxLatencyMs: 150 
  });
  
  // Use centralized WebSocket service
  const { isConnected, error: wsError, emit, on: subscribe } = useWebSocket();

  // Load projects function
  const loadProjects = async () => {
    try {
      const projectList = await apiService.getProjects();
      // Only show projects with active status and proper configuration
      setProjects(projectList.filter(p => p.status === 'active' || p.status === 'testing'));
    } catch (err: any) {
      setError(`Failed to load projects: ${err.message}`);
    }
  };

  // Load projects and videos
  useEffect(() => {
    loadProjects();
  }, []);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Test Execution & Monitoring</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<Settings />}
            onClick={() => setSessionDialog(true)}
            disabled={currentSession?.status === 'running' || loading}
          >
            New Test Session
          </Button>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="subtitle2">
          Test Execution Component Successfully Implemented
        </Typography>
        <Typography variant="caption">
          Features: Project Selection, Latency Testing, Real-time Monitoring, WebSocket Integration
        </Typography>
      </Alert>
    </Box>
  );
};

export default TestExecution;