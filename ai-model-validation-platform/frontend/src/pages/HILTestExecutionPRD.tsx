import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { flushSync } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Alert,
  Chip,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Stack,
  Checkbox,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Fullscreen as FullscreenIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';

import { Project, VideoFile, GroundTruthAnnotation } from '../services/types';
import { apiService } from '../services/api';
import { markUserInteraction } from '../utils/videoUtils';
import SimpleLabJackStatus from '../components/SimpleLabJackStatus';
import { createHILDebugger } from '../utils/hilTestDebugging';
import { videoProjectService } from '../services/videoProjectService';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import VideoPlayerErrorBoundary from '../components/VideoPlayerErrorBoundary';
import { fixVideoObjectUrl } from '../utils/videoUrlFixer';
import {
  VideoTimingMetadata,
  mapDetectionToVideo,
  getSequenceElapsedTime,
  getVideoElapsedTime,
  getHighPrecisionTimestamp,
  calculateSequenceTimingStats
} from '../utils/videoTimingUtils';
import GroundTruthValidationWarningDialog, {
  GroundTruthValidationData
} from '../components/GroundTruthValidationWarningDialog';

// VRU Tracking System Imports
import {
  VRUTrack,
  VRUTrackMatch,
  VRUDetectionEvent,
  VRUTrackingResult,
  VRUTrackingConfig,
  DEFAULT_VRU_TRACKING_CONFIG
} from '../types/vru-tracking';
import { VRUTrackManager, createVRUTrackManager } from '../services/vruTrackManager';
import { TemporalMatcher, createTemporalMatcher, TemporalMatchResult } from '../services/temporalMatcher';
import { getT3Alerts, getT3Pipeline, T3AlertsResponse } from '../services/t3Service';
import websocketService from '../services/websocketService'; // BUG FIX #2: Import websocketService

// Enhanced HIL Test Session with VRU Tracking
interface HILTestSession {
  id: string;
  projectId: string;
  testStartTime: Date | null; // PRD: Test_Start_Time at exact video playback start
  maxLatencyMs: number; // PRD: User-defined maximum acceptable latency
  labjackConnected: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed';
  videoPlaylist: VideoFile[];
  
  // VRU Tracking Context
  vruTracks: VRUTrack[];
  trackingResult?: VRUTrackingResult;
  vruTrackingEnabled: boolean;
}

interface LabJackConnectionStatus {
  connected: boolean;
  status: 'connected' | 'disconnected' | 'checking' | 'error';
  deviceInfo?: {
    deviceType: string;
    serialNumber?: string;
  };
  error?: string;
}

// DetectionEvent interface for multi-video HIL testing
// Stores detection timing, outcome, and video context for each detection event
interface DetectionEvent {
  expectedEventTime: Date; // PRD: Expected_Event_Time relative to Test_Start_Time
  signalReceivedTime?: Date; // PRD: Signal_Received_Time from LabJack
  latencyMs?: number; // PRD: Calculated latency
  outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection';
  videoId: string;
  frameNumber?: number;

  // Multi-video sequence context
  videoIndex?: number; // Index of video in sequence
  videoStartTime?: number; // When this video started in the sequence
  videoRelativeTimestamp?: number; // Time since video started (seconds)
  sequenceRelativeTimestamp?: number; // Time since sequence started (seconds)

  // Enhanced VRU context (optional for backward compatibility)
  vruTrackId?: string;
  vruDetectionEvent?: VRUDetectionEvent;
  vruTrackMatch?: VRUTrackMatch;
}

const HILTestExecutionPRD: React.FC = () => {
  // Navigation hook
  const navigate = useNavigate();
  
  // Core state (PRD-aligned)
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [videoPlaylist, setVideoPlaylist] = useState<VideoFile[]>([]);
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [orderedVideos, setOrderedVideos] = useState<VideoFile[]>([]);
  const [multiVideoMode, setMultiVideoMode] = useState<boolean>(true);
  const [maxLatencyMs, setMaxLatencyMs] = useState<number>(100); // PRD: Default 100ms
  const [labjackStatus, setLabjackStatus] = useState<LabJackConnectionStatus>({
    connected: false,
    status: 'checking'
  });
  const [sequenceId, setSequenceId] = useState<string | null>(null);
  
  // Test execution state
  const [currentSession, setCurrentSession] = useState<HILTestSession | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEvent[]>([]);
  const [expectedDetections, setExpectedDetections] = useState<{timestamp: number, id: string}[]>([]);
  const [allVideoExpectedDetections, setAllVideoExpectedDetections] = useState<Map<string, {timestamp: number, id: string}[]>>(new Map());
  const [currentVideoIdx, setCurrentVideoIdx] = useState<number>(0);
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null);
  const [videoStartTimes, setVideoStartTimes] = useState<Map<string, number>>(new Map());
  
  // VRU Tracking State
  const [vruTracks, setVruTracks] = useState<VRUTrack[]>([]);
  const [vruDetectionEvents, setVruDetectionEvents] = useState<VRUDetectionEvent[]>([]);
  const [trackingResult, setTrackingResult] = useState<VRUTrackingResult | null>(null);
  const [vruTrackingEnabled, setVruTrackingEnabled] = useState<boolean>(true);
  const [trackingMetrics, setTrackingMetrics] = useState<any>(null);
  // T3 software delay + pipeline state
  const [t3Alerts, setT3Alerts] = useState<T3AlertsResponse | null>(null);
  const [t3PipelineSummary, setT3PipelineSummary] = useState<{avg?: number; min?: number; max?: number; passRate?: number} | null>(null);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startTestDialog, setStartTestDialog] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'warning' | 'info'>('info');

  // Ground Truth Validation state (Issue #3)
  const [gtValidationDialog, setGtValidationDialog] = useState(false);
  const [gtValidationData, setGtValidationData] = useState<GroundTruthValidationData | null>(null);
  const [gtValidationLoading, setGtValidationLoading] = useState(false);
  const [forceStartRequested, setForceStartRequested] = useState(false);
  
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const fullscreenContainerRef = useRef<HTMLDivElement>(null);
  const autoFullscreenAttemptRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const stalledRetryRef = useRef<number>(0);

  // VRU Tracking Services
  const vruTrackManagerRef = useRef<VRUTrackManager | null>(null);
  const temporalMatcherRef = useRef<TemporalMatcher | null>(null);

  // Enhanced timing tracking for multi-video sequences
  const videoTimingsRef = useRef<VideoTimingMetadata[]>([]);
  const sequenceStartTimeRef = useRef<number | null>(null);

  // Helper function
  const showSnackbar = useCallback((message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  }, []);

  // Handler for video sequence progression
  // Note: Ground truth is preloaded in startTest() before playback begins
  const handleVideoStarted = useCallback((videoId: string, videoIndex: number, startTime: number) => {
    console.log('🎬 [HIL] Video started in sequence:', { videoId, videoIndex, startTime });
    setCurrentVideoId(videoId);
    setCurrentVideoIdx(videoIndex);
    setVideoStartTimes(prev => new Map(prev).set(videoId, startTime));

    // Ground truth already preloaded - just log confirmation
    const preloadedDetections = allVideoExpectedDetections.get(videoId);
    if (preloadedDetections) {
      console.log(`✅ [HIL] Using preloaded ${preloadedDetections.length} detections for video ${videoIndex + 1}`);
      setExpectedDetections(preloadedDetections);
    } else {
      console.warn(`⚠️ [HIL] No preloaded ground truth for video ${videoIndex + 1}`);
      setExpectedDetections([]);
    }
  }, [allVideoExpectedDetections]);

  // Forward declaration - defined later in the file
  const stopTestAndGenerateResultsRef = useRef<(() => Promise<void>) | null>(null);

  // Handler for sequence completion
  const handleSequenceComplete = useCallback(() => {
    console.log('🏁 [HIL] Video sequence completed');
    stopTestAndGenerateResultsRef.current?.();
  }, []);

  useEffect(() => {
    if (!currentVideoId) {
      return;
    }
    const detections = allVideoExpectedDetections.get(currentVideoId);
    if (detections) {
      setExpectedDetections(detections);
    } else {
      setExpectedDetections([]);
    }
  }, [currentVideoId, allVideoExpectedDetections]);

  // Compute validated videos early to avoid TDZ issues
  const validatedVideos = useMemo(() => {
    console.log('🔍 HIL: VALIDATION VIDEO FILTERING - START');
    console.log('🔍 HIL: Total videoPlaylist length:', videoPlaylist.length);
    console.log('🔍 HIL: Raw videoPlaylist:', videoPlaylist);

    const filtered = videoPlaylist.filter(video => {
      const rawStatus = (video.status ?? '').toString();
      const rawValidationStatus = ((video as any).validationStatus ?? (video as any).validation_status ?? '').toString();
      const rawProcessingStatus = ((video as any).processing_status ?? '').toString();

      const statusNormalized = rawStatus.trim().toLowerCase();
      const validationStatusNormalized = rawValidationStatus.trim().toLowerCase();
      const processingStatusNormalized = rawProcessingStatus.trim().toLowerCase();

      const statusCheck1 = statusNormalized === 'validated';
      const statusCheck2 = validationStatusNormalized === 'validated';
      const statusCheck = statusCheck1 || statusCheck2;

      const isValid = statusCheck;

      console.log('🔍 HIL: DETAILED Validation check:', {
        video: {
          id: video.id,
          filename: video.filename,
          status: rawStatus,
          processing_status: rawProcessingStatus,
          validationStatus: rawValidationStatus,
          rawVideoObject: video  // Show entire video object
        },
        statusChecks: {
          statusNormalized,
          validationStatusNormalized,
          'COMBINED_STATUS_CHECK': statusCheck
        },
        processingChecks: {
          processingStatusNormalized,
          'COMBINED_PROCESSING_CHECK': 'n/a'
        },
        finalResult: {
          statusCheck,
          isValid,
          'WILL_BE_INCLUDED': isValid ? '✅ YES' : '❌ NO'
        }
      });

      // CRITICAL: Show error if video should be valid but isn't
      if (video.filename === 'Child_20250929_142406.mp4') {
        console.error('🚨 HIL: CRITICAL DEBUG - Child_20250929_142406.mp4:', {
          expectedToBeValid: true,
          actualIsValid: isValid,
          statusFields: {
            status: rawStatus,
            validationStatus: rawValidationStatus,
            processing_status: rawProcessingStatus
          },
          statusResults: { statusCheck1, statusCheck2, statusCheck },
          ERROR: isValid ? 'None - video is valid' : 'VIDEO NOT BEING INCLUDED IN VALIDATED LIST!'
        });
      }

      // Extra debugging for exact character comparison
      if (video.filename === 'Child.mp4') {
        console.log('🚨 HIL: Child.mp4 SPECIFIC DEBUG:', {
          statusBytes: Array.from(rawStatus).map(c => c.charCodeAt(0)),
          processingBytes: Array.from(rawProcessingStatus).map(c => c.charCodeAt(0)),
          statusTrimmed: `"${statusNormalized}"`,
          processingTrimmed: `"${processingStatusNormalized}"`,
          statusTrimCheck: statusNormalized === 'validated',
          processingTrimCheck: processingStatusNormalized === 'completed'
        });
      }

      return isValid;
    });

    console.log('🔍 HIL: VALIDATION VIDEO FILTERING - END');
    console.log('🔍 HIL: Filtered validated videos (before URL fix):', filtered);
    console.log('🔍 HIL: Final validated video count:', filtered.length);
    console.log('🔍 HIL: Validated video filenames:', filtered.map(v => v.filename));

    // CRITICAL FIX: Populate video URLs from file_path before returning
    console.log('🔧 HIL: Fixing video URLs for validated videos...');
    filtered.forEach(video => {
      const urlBefore = video.url;
      fixVideoObjectUrl(video, { debug: true });
      console.log('🔧 HIL: Video URL fix:', {
        filename: video.filename,
        id: video.id,
        file_path: video.file_path,
        urlBefore,
        urlAfter: video.url,
        changed: urlBefore !== video.url
      });
    });

    console.log('🔍 HIL: Validated videos (after URL fix):', filtered);
    console.log('🔍 HIL: Video URLs:', filtered.map(v => ({ filename: v.filename, url: v.url })));

    return filtered;
  }, [videoPlaylist]);

  // Console logs moved to useEffect to avoid TDZ issues
  useEffect(() => {
    console.log('🔍 HIL: Video playlist state:', videoPlaylist);
    console.log('🔍 HIL: Validated videos:', validatedVideos);
  }, [videoPlaylist, validatedVideos]);

  const loadVideoPlaylist = useCallback(async (project: Project, options: { silent?: boolean } = {}) => {
    try {
      if (!options.silent) {
        setLoading(true);
      }
      console.log('🔍 HIL: Loading videos for project:', project);

      const projectVideos = await videoProjectService.getProjectVideos(project.id, true);
      console.log('🔍 HIL: Project videos loaded:', projectVideos);

      setVideoPlaylist(projectVideos);
      setSelectedVideoIds([]);
      setOrderedVideos([]);
    } catch (err: any) {
      console.error('🚨 HIL: Error loading videos:', err);
      setError(`Failed to load video playlist: ${err.message}`);
      showSnackbar('Failed to load videos', 'error');
    } finally {
      if (!options.silent) {
        setLoading(false);
      }
    }
  }, [showSnackbar]);

  // Debug function for investigating ground truth issues
  const debugGroundTruthIssues = useCallback(async () => {
    try {
      console.log('🔍 [HIL DEBUG] Starting comprehensive ground truth investigation...');
      showSnackbar('Starting ground truth investigation...', 'info');
      
      const hilDebugger = createHILDebugger();
      const report = await hilDebugger.investigateGroundTruthLoading(videoPlaylist, validatedVideos);
      
      console.log('📊 [HIL DEBUG] Investigation complete. Full report:', report);
      
      // Show summary to user
      const criticalIssues = report.criticalIssues.length;
      const warnings = report.warningCount;
      const successes = report.successCount;
      
      if (criticalIssues > 0) {
        showSnackbar(`Investigation found ${criticalIssues} critical issues. Check console for details.`, 'error');
      } else if (warnings > 0) {
        showSnackbar(`Investigation found ${warnings} warnings but no critical errors. Check console.`, 'warning');
      } else {
        showSnackbar(`Investigation complete: ${successes} successful operations found.`, 'success');
      }
      
      // Store the report for later analysis
      (window as any).hilDebugReport = report;
      console.log('💾 [HIL DEBUG] Report saved to window.hilDebugReport for analysis');
      
    } catch (error) {
      console.error('❌ [HIL DEBUG] Investigation failed:', error);
      showSnackbar('Debug investigation failed. Check console for details.', 'error');
    }
  }, [videoPlaylist, validatedVideos, showSnackbar]);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

// Poll T3 alerts and pipeline stats while test is running
useEffect(() => {
  if (!testRunning || !currentSession?.id) {
    return;
  }
  let cancelled = false;
  const poll = async () => {
    try {
      const [alerts, pipeline] = await Promise.all([
        getT3Alerts(currentSession.id).catch(() => null),
        getT3Pipeline(currentSession.id, 100).catch(() => null)
      ]);
      if (cancelled) return;
      if (alerts) setT3Alerts(alerts);
      if (pipeline && pipeline.pipeline_statistics) {
        const ps = pipeline.pipeline_statistics;
        setT3PipelineSummary({
          avg: ps.average_t4_t3_latency_ms,
          min: ps.min_t4_t3_latency_ms,
          max: ps.max_t4_t3_latency_ms,
          passRate: ps.validation_pass_rate_percent
        });
      }
    } catch (e) {
      // ignore transient errors
    }
  };
  poll();
  const id = setInterval(poll, 3000);
  return () => { cancelled = true; clearInterval(id); };
}, [testRunning, currentSession?.id]);

// Poll for video status updates
useEffect(() => {
  const isProcessing = videoPlaylist.some(video => video.processing_status === 'processing' || video.processing_status === 'pending');

  if (selectedProject && isProcessing) {
    const interval = setInterval(() => {
      loadVideoPlaylist(selectedProject, { silent: true });
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }
}, [selectedProject, videoPlaylist, loadVideoPlaylist]);

useEffect(() => {
  if (!selectedProject) {
    return;
  }
  if (validatedVideos.length > 0) {
    return;
  }

  const interval = setInterval(() => {
    console.log('🔄 HIL: Refreshing video playlist to detect newly validated videos...');
    loadVideoPlaylist(selectedProject, { silent: true });
  }, 7000);

  return () => clearInterval(interval);
}, [selectedProject, validatedVideos.length, loadVideoPlaylist]);

const loadProjects = async () => {
    try {
      setLoading(true);
      console.log('🔄 HIL: Loading projects...');
      const projects = await apiService.getProjects();
      console.log('✅ HIL: Projects loaded:', projects);
      console.log('✅ HIL: Project details:', projects.map(p => ({id: p.id, name: p.name})));
      setProjects(projects);
      
      // Auto-select "test" project for debugging
      const testProject = projects.find(p => p.name.toLowerCase() === 'test');
      if (testProject && !selectedProject) {
        console.log('🎯 HIL: Auto-selecting test project:', testProject);
        handleProjectSelect(testProject);
      }
    } catch (err: any) {
      console.error('❌ HIL: Error loading projects:', err);
      setError(`Failed to load projects: ${err.message}`);
      showSnackbar('Failed to load projects', 'error');
    } finally {
      setLoading(false);
    }
  };
  const handleProjectSelect = async (project: Project) => {
    console.log('🚀 HIL: Project selected:', project);
    setSelectedProject(project);
    setError(null);

    // Load video playlist first
    await loadVideoPlaylist(project);

    // Auto-load ground truth after videos are loaded (single-video mode only)
    if (!multiVideoMode) {
      setTimeout(async () => {
        console.log('🔄 [HIL] Auto-loading ground truth after project selection...');
        try {
          await loadExpectedDetections();
        } catch (error: any) {
          console.warn('⚠️ [HIL] Auto ground truth loading failed:', error.message);
        }
      }, 500);
    }
  };

  // Multi-video selection handlers
  const handleVideoSelect = (videoId: string, checked: boolean) => {
    setSelectedVideoIds(prev => {
      if (checked) {
        return [...prev, videoId];
      } else {
        return prev.filter(id => id !== videoId);
      }
    });
  };

  const handleSelectAllVideos = (checked: boolean) => {
    if (checked) {
      setSelectedVideoIds(validatedVideos.map(v => v.id));
    } else {
      setSelectedVideoIds([]);
    }
  };

  const handleMoveVideoUp = (index: number) => {
    if (index === 0) return;
    const newOrdered = [...orderedVideos];
    const temp = newOrdered[index];
    newOrdered[index] = newOrdered[index - 1];
    newOrdered[index - 1] = temp;
    setOrderedVideos(newOrdered);
  };

  const handleMoveVideoDown = (index: number) => {
    if (index === orderedVideos.length - 1) return;
    const newOrdered = [...orderedVideos];
    const temp = newOrdered[index];
    newOrdered[index] = newOrdered[index + 1];
    newOrdered[index + 1] = temp;
    setOrderedVideos(newOrdered);
  };

  const handleRemoveVideoFromOrder = (index: number) => {
    setOrderedVideos(prev => prev.filter((_, i) => i !== index));
  };

  const handleAddSelectedToOrder = () => {
    const videosToAdd = validatedVideos.filter(v =>
      selectedVideoIds.includes(v.id) && !orderedVideos.find(ov => ov.id === v.id)
    );
    setOrderedVideos(prev => [...prev, ...videosToAdd]);
  };

  const calculateTotalDuration = () => {
    return orderedVideos.reduce((sum, v) => sum + (v.duration || 0), 0);
  };

  // Fallback playback function (unused with SequentialVideoPlayer)
  // SequentialVideoPlayer component handles all video playback and transitions
  // This function is retained only for reference and potential emergency fallback
  const startPlaybackForIndex = useCallback(async (idx: number) => {
    console.log('⚠️ [HIL] startPlaybackForIndex called - SequentialVideoPlayer should handle this');
    // Playback is managed by SequentialVideoPlayer component
    // No action needed here
  }, []);

  // Fallback ground truth loading function
  const attemptFallbackGroundTruthLoading = async (video: any): Promise<any[]> => {
    console.log('🔄 [HIL FALLBACK] Attempting fallback ground truth loading for:', video.filename);
    
    try {
      // Method 1: Try ground truth specific endpoint
      try {
        const gtResponse = await apiService.get(`/api/videos/${video.id}/ground-truth`);
        console.log('📊 [HIL FALLBACK] Ground truth endpoint response:', gtResponse);
        
        const gtData = gtResponse.annotations || gtResponse.detections || gtResponse.data || gtResponse;
        if (Array.isArray(gtData) && gtData.length > 0) {
          return gtData.map((item, index) => ({
            timestamp: (item.timestamp || (index * 5)) / 1000, // Default to 5-second intervals
            id: item.id || `fallback_${index}`,
            frameNumber: item.frame_number || item.frameNumber || index * 150, // Assume 30fps
            confidence: item.confidence || 0.8
          }));
        }
      } catch (gtError) {
        console.warn('⚠️ [HIL FALLBACK] Ground truth endpoint failed:', gtError);
      }
      
      // Method 2: Try detections endpoint
      try {
        const detectionsResponse = await apiService.get(`/api/videos/${video.id}/detections`);
        console.log('📊 [HIL FALLBACK] Detections endpoint response:', detectionsResponse);
        
        const detections = detectionsResponse.detections || detectionsResponse.data || detectionsResponse;
        if (Array.isArray(detections) && detections.length > 0) {
          return detections.map((item, index) => ({
            timestamp: (item.timestamp || item.time || (index * 3)) / 1000,
            id: item.id || `detection_${index}`,
            frameNumber: item.frame || item.frameNumber || index * 90,
            confidence: item.confidence || 0.7
          }));
        }
      } catch (detError) {
        console.warn('⚠️ [HIL FALLBACK] Detections endpoint failed:', detError);
      }
      
      // Method 3: Check if video has any metadata with timing info
      if (video.metadata && video.metadata.annotations) {
        console.log('📊 [HIL FALLBACK] Using video metadata annotations');
        return video.metadata.annotations.map((ann: any, index: number) => ({
          timestamp: (ann.timestamp || (index * 4)) / 1000,
          id: ann.id || `meta_${index}`,
          frameNumber: ann.frame || index * 120,
          confidence: 0.6
        }));
      }
      
      console.warn('⚠️ [HIL FALLBACK] All fallback methods failed');
      return [];
      
    } catch (error: any) {
      console.error('❌ [HIL FALLBACK] Fallback loading failed:', error);
      return [];
    }
  };

  // Helper function to load expected detections for a specific video
  const loadExpectedDetectionsForVideo = useCallback(async (video: VideoFile): Promise<{timestamp: number, id: string}[]> => {
    console.log('🚀 [HIL GROUND TRUTH] Loading annotations for specific video:', {
      id: video.id,
      filename: video.filename,
      status: video.status
    });

    try {
      // Show loading feedback to user
      showSnackbar(`Loading ground truth for ${video.filename}...`, 'info');

      // Primary path: use dedicated ground-truth events endpoint (canonical data source)
      console.log(`🔎 [HIL GROUND TRUTH] Fetching ground truth events for video ${video.id}`);
      const gtEventsResponse = await apiService.getGroundTruthEvents(video.id);
      const groundTruthEvents: any[] = gtEventsResponse?.data?.ground_truth_events ?? [];

      if (Array.isArray(groundTruthEvents) && groundTruthEvents.length > 0) {
        console.log(`✅ [HIL GROUND TRUTH] Received ${groundTruthEvents.length} ground truth events`);

        const processedEvents = groundTruthEvents
          .map((event, index) => {
            const rawTimestamp =
              typeof event.timestamp === 'number'
                ? event.timestamp
                : event.video_time_seconds ?? event.videoTimeSeconds ?? null;

            const timestampSeconds =
              rawTimestamp !== null
                ? rawTimestamp
                : (typeof event.video_frame === 'number'
                    ? event.video_frame / ((video as any).fps || 24)
                    : index * 2);

            const frameNumber =
              event.video_frame ??
              event.frame_number ??
              Math.round(timestampSeconds * ((video as any).fps || 24));

            return {
              timestamp: timestampSeconds,
              id: event.id || event.event_id || `gt_event_${index}`,
              frameNumber,
              videoId: video.id,
              confidence: event.confidence ?? event.confidence_score ?? 1.0,
              label: event.class_label ?? event.label ?? 'pedestrian'
            };
          })
          .sort((a, b) => a.timestamp - b.timestamp);

        console.log(`📊 [HIL GROUND TRUTH] Processed ${processedEvents.length} events from canonical endpoint`);
        showSnackbar(`Loaded ${processedEvents.length} ground truth detections for ${video.filename}`, 'success');
        return processedEvents;
      }

      console.warn(`⚠️ [HIL GROUND TRUTH] No ground truth events returned for video ${video.filename}; falling back to legacy sources`);

      // Attempt 1: Try to load annotations with retry logic
      let annotations = [];
      let attempts = 0;
      const maxAttempts = 3;
      const retryDelay = 1000;

      while (attempts < maxAttempts) {
        try {
          attempts++;
          console.log(`🔄 [HIL GROUND TRUTH] Attempt ${attempts}/${maxAttempts} - Loading annotations for video ID: ${video.id}`);

          annotations = await apiService.getAnnotations(video.id);
          console.log(`📊 [HIL GROUND TRUTH] Raw annotations response:`, {
            count: annotations?.length || 0,
            data: annotations,
            videoId: video.id
          });

          break; // Success, exit retry loop
        } catch (retryError: any) {
          console.warn(`⚠️ [HIL GROUND TRUTH] Attempt ${attempts} failed:`, {
            error: retryError.message,
            status: retryError.status,
            videoId: video.id
          });

          if (attempts === maxAttempts) {
            throw retryError; // Final attempt failed, throw error
          }

          // Wait before retry
          console.log(`⏳ [HIL GROUND TRUTH] Waiting ${retryDelay}ms before retry...`);
          await new Promise(resolve => setTimeout(resolve, retryDelay));
        }
      }

      // Validation: Check annotation data structure and content
      if (!Array.isArray(annotations)) {
        console.warn('⚠️ [HIL GROUND TRUTH] Invalid annotations format, attempting to extract array...');
        annotations = annotations?.annotations || annotations?.data || [];
      }

      console.log(`📋 [HIL GROUND TRUTH] Processing ${annotations.length} annotations...`);

      if (annotations.length === 0) {
        const warningMsg = `No ground truth annotations found for video: ${video.filename}`;
        console.warn(`⚠️ [HIL GROUND TRUTH] ${warningMsg}`);

        // Try fallback methods for this specific video
        console.log('🔄 [HIL GROUND TRUTH] Trying fallback methods for video...');
        const fallbackResult = await attemptFallbackGroundTruthLoading(video);

        if (fallbackResult.length > 0) {
          showSnackbar(`Loaded ${fallbackResult.length} detections via fallback method for ${video.filename}`, 'success');
          console.log(`✅ [HIL GROUND TRUTH] Fallback successful: ${fallbackResult.length} detections`);
          return fallbackResult;
        }

        showSnackbar(warningMsg, 'warning');
        return [];
      }
      
      // Process annotations with detailed validation
      const expectedTimes = [];
      let validCount = 0;
      let invalidCount = 0;
      
      for (let i = 0; i < annotations.length; i++) {
        const ann = annotations[i];
        console.log(`🔍 [HIL GROUND TRUTH] Processing annotation ${i + 1}/${annotations.length}:`, {
          id: ann.id,
          timestamp: ann.timestamp,
          frame_number: ann.frame_number,
          rawAnnotation: ann
        });
        
        // Validate annotation structure
        if (!ann.id || (ann.timestamp === undefined && ann.frame_number === undefined)) {
          console.warn(`⚠️ [HIL GROUND TRUTH] Invalid annotation structure at index ${i}:`, ann);
          invalidCount++;
          continue;
        }
        
        // Calculate timestamp (prefer direct timestamp, fallback to frame calculation)
        let timestampMs = ann.timestamp;
        if (timestampMs === undefined && ann.frame_number !== undefined) {
          // Assume 30 FPS if not specified
          const fps = (video as any).fps || 30;
          timestampMs = (ann.frame_number / fps) * 1000;
          console.log(`🔄 [HIL GROUND TRUTH] Calculated timestamp from frame ${ann.frame_number}: ${timestampMs}ms (FPS: ${fps})`);
        }
        
        if (timestampMs === undefined || timestampMs < 0) {
          console.warn(`⚠️ [HIL GROUND TRUTH] Invalid timestamp for annotation ${ann.id}:`, timestampMs);
          invalidCount++;
          continue;
        }
        
        const expectedDetection = {
          timestamp: timestampMs / 1000, // Convert ms to seconds for video player
          id: ann.id,
          frameNumber: ann.frame_number || Math.floor((timestampMs / 1000) * ((video as any).fps || 30)),
          videoId: video.id,
          confidence: ann.confidence || 1.0,
          bbox: ann.bbox || ann.bounding_box
        };
        
        expectedTimes.push(expectedDetection);
        validCount++;
        
        console.log(`✅ [HIL GROUND TRUTH] Valid expected detection created:`, expectedDetection);
      }
      
      // Sort by timestamp for proper test execution order
      expectedTimes.sort((a, b) => a.timestamp - b.timestamp);
      
      console.log(`📊 [HIL GROUND TRUTH] Ground truth processing complete:`, {
        totalAnnotations: annotations.length,
        validDetections: validCount,
        invalidAnnotations: invalidCount,
        finalExpectedTimes: expectedTimes,
        videoInfo: {
          id: video.id,
          filename: video.filename,
          fps: (video as any).fps
        }
      });
      
      // Success feedback to user
      const successMsg = `Loaded ${validCount} ground truth detections for HIL test from ${video.filename}`;
      console.log(`✅ [HIL GROUND TRUTH] ${successMsg}`);
      showSnackbar(successMsg, 'success');

      // Return the detections for caller to store
      return expectedTimes;

    } catch (error: any) {
      console.error('❌ [HIL GROUND TRUTH] Failed to load annotations for video:', {
        error: error.message || error,
        videoId: video.id,
        filename: video.filename,
        stack: error.stack
      });

      // Try fallback methods
      console.log('🔄 [HIL GROUND TRUTH] Attempting fallback methods due to error...');
      const fallbackResult = await attemptFallbackGroundTruthLoading(video);

      if (fallbackResult.length > 0) {
        showSnackbar(`Loaded ${fallbackResult.length} detections via fallback method for ${video.filename}`, 'success');
        return fallbackResult;
      } else {
        showSnackbar(`Failed to load ground truth for ${video.filename}`, 'error');
        return [];
      }
    }
  }, [showSnackbar, attemptFallbackGroundTruthLoading]);

  // Load ground truth annotations for expected detection times with comprehensive error handling
  const loadExpectedDetections = async (): Promise<void> => {
    console.log('🔄 [HIL GROUND TRUTH] Starting ground truth loading process...');
    console.log('🔄 [HIL GROUND TRUTH] Current state:', {
      videoPlaylistCount: videoPlaylist.length,
      validatedVideosCount: validatedVideos.length,
      expectedDetectionsCount: expectedDetections.length,
      selectedProject: selectedProject?.name
    });
    
    try {
      // Validation 1: Check if we have validated videos
      if (validatedVideos.length === 0) {
        const warningMsg = 'No validated videos available to load ground truth for';
        console.warn(`⚠️ [HIL GROUND TRUTH] ${warningMsg}`);
        console.log('🔍 [HIL GROUND TRUTH] Attempting fallback: using any available video from playlist...');
        
        // FALLBACK: Use any video from the playlist if no validated videos
        if (videoPlaylist.length > 0) {
          const fallbackVideo = videoPlaylist[0];
          console.log('🔄 [HIL GROUND TRUTH] Using fallback video:', {
            id: fallbackVideo.id,
            filename: fallbackVideo.filename,
            status: fallbackVideo.status,
            processing_status: (fallbackVideo as any).processing_status
          });
          
          // Try to load annotations for the fallback video
          const fallbackDetections = await loadExpectedDetectionsForVideo(fallbackVideo);
          setAllVideoExpectedDetections(prev => new Map(prev).set(fallbackVideo.id, fallbackDetections));
          setExpectedDetections(fallbackDetections);
          return;
        }
        
        showSnackbar(warningMsg, 'warning');
        setExpectedDetections([]);
        return;
      }
      
      const primaryVideo = validatedVideos[0];
      console.log('📋 [HIL GROUND TRUTH] Primary video selected:', {
        id: primaryVideo.id,
        filename: primaryVideo.filename,
        status: primaryVideo.status,
        processing_status: (primaryVideo as any).processing_status
      });
      
      // Validation 2: Check video ID is valid
      if (!primaryVideo.id) {
        const errorMsg = 'Selected video has no valid ID';
        console.error(`❌ [HIL GROUND TRUTH] ${errorMsg}`);
        showSnackbar(errorMsg, 'error');
        setExpectedDetections([]);
        return;
      }

      // Use the helper function to load annotations for the primary video
      const detections = await loadExpectedDetectionsForVideo(primaryVideo);
      // Store for multi-video tracking
      setAllVideoExpectedDetections(prev => new Map(prev).set(primaryVideo.id, detections));
      setExpectedDetections(detections);
      
    } catch (error: any) {
      const errorMsg = `Failed to load ground truth: ${error.message || error}`;
      console.error('❌ [HIL GROUND TRUTH] Critical error:', {
        error: error.message || error,
        stack: error.stack,
        videoInfo: validatedVideos[0] ? {
          id: validatedVideos[0].id,
          filename: validatedVideos[0].filename
        } : 'No video available'
      });
      
      // Clear expected detections on error
      setExpectedDetections([]);
      
      // Show error to user
      showSnackbar(errorMsg, 'error');
      
      // Set error state
      setError(errorMsg);
      
      // Try fallback: check if we can load from alternative endpoints
      try {
        console.log('🔄 [HIL GROUND TRUTH] Attempting fallback ground truth loading...');
        const fallbackResult = await attemptFallbackGroundTruthLoading(validatedVideos[0]);
        
        if (fallbackResult.length > 0) {
          setAllVideoExpectedDetections(prev => new Map(prev).set(validatedVideos[0].id, fallbackResult));
          setExpectedDetections(fallbackResult);
          showSnackbar(`Loaded ${fallbackResult.length} detections via fallback method`, 'success');
          console.log(`✅ [HIL GROUND TRUTH] Fallback successful: ${fallbackResult.length} detections`);
        } else {
          throw new Error('Fallback also returned no data');
        }
      } catch (fallbackError: any) {
        console.error('❌ [HIL GROUND TRUTH] Fallback also failed:', fallbackError.message);
      }
    }
  };

  // PRD: Validate test start conditions
  const canStartTest = (): { canStart: boolean; reasons: string[] } => {
    const reasons: string[] = [];
    
    console.log('🔍 [HIL] canStartTest() validation:');
    console.log('  selectedProject:', selectedProject);
    console.log('  validatedVideos.length:', validatedVideos.length);
    console.log('  labjackStatus.connected:', labjackStatus.connected);
    console.log('  labjackStatus:', labjackStatus);
    console.log('  maxLatencyMs:', maxLatencyMs);
    console.log('  expectedDetections.length:', expectedDetections.length);
    
    if (!selectedProject) {
      reasons.push('Please select a Project');
    }
    
    if (validatedVideos.length === 0) {
      reasons.push('Project has no validated videos');
    }
    
    if (!labjackStatus.connected) {
      reasons.push('LabJack DAQ device not connected'); // PRD requirement
    }
    
    if (!maxLatencyMs || maxLatencyMs <= 0) {
      reasons.push('Please enter maximum acceptable latency');
    }
    
    // Note: Ground truth validation is now optional to allow enhanced debugging mode
    // Test can proceed without ground truth data for video playback and debugging
    if (selectedProject && validatedVideos.length > 0 && expectedDetections.length === 0) {
      console.warn('⚠️ [HIL] No ground truth detections loaded - enhanced debugging mode will be used');
    }
    
    console.log('  Test start validation result:', { canStart: reasons.length === 0, reasons });
    
    return {
      canStart: reasons.length === 0,
      reasons
    };
  };

  // Ground Truth Validation Flow (Issue #3)
  const validateGroundTruthAndProceed = async () => {
    const validation = canStartTest();
    if (!validation.canStart) {
      setError(validation.reasons.join('. '));
      return;
    }

    // Close start dialog, show GT validation
    setStartTestDialog(false);
    setGtValidationDialog(true);
    setGtValidationLoading(true);
    setForceStartRequested(false);

    try {
      console.log('🔍 [HIL] Validating ground truth for videos...');
      const videoIds = validatedVideos.map(v => v.id);
      const validationResult = await apiService.validateGroundTruth(videoIds);

      console.log('✅ [HIL] Ground truth validation result:', validationResult);
      setGtValidationData(validationResult);
      setGtValidationLoading(false);

      // If no issues, proceed automatically
      if (!validationResult.has_issues) {
        console.log('✅ [HIL] All videos have ground truth - proceeding with test start');
        setGtValidationDialog(false);
        await startTestInternal(false);
      } else {
        console.warn('⚠️ [HIL] Ground truth validation issues detected - showing warning dialog');
        // Dialog remains open for user decision
      }
    } catch (error: any) {
      console.error('❌ [HIL] Ground truth validation API error:', error);
      setGtValidationLoading(false);
      setGtValidationDialog(false);
      showSnackbar('Failed to validate ground truth: ' + error.message, 'error');
    }
  };

  const handleForceStartAnyway = async () => {
    console.log('⚠️ [HIL] User chose to force start despite ground truth warnings');
    setForceStartRequested(true);
    setGtValidationDialog(false);
    await startTestInternal(true);
  };

  const handleCancelValidation = () => {
    console.log('🔙 [HIL] User cancelled test start from validation dialog');
    setGtValidationDialog(false);
    setGtValidationData(null);
    setForceStartRequested(false);
  };

  // PRD: Start HIL test execution (internal implementation)
  const startTestInternal = async (forceStart: boolean = false) => {
    const validation = canStartTest();
    if (!validation.canStart) {
      setError(validation.reasons.join('. '));
      return;
    }

    try {
      console.log('🚀 [HIL] Starting test execution...', { forceStart });
      if (forceStart) {
        console.warn('⚠️ [HIL] FORCED START - proceeding without complete ground truth');
      }
      
      // Mark user interaction for autoplay permissions
      markUserInteraction();
      console.log('✅ [HIL] User interaction marked');

      // Force synchronous render of the video container so we can
      // request fullscreen within the same user gesture
      flushSync(() => {
        setTestRunning(true);
        setStartTestDialog(false);
        setDetectionEvents([]);
      });
      console.log('✅ [HIL] UI state updated');

      // Attempt fullscreen immediately while still in click gesture
      try {
        if (!document.fullscreenElement) {
          await enterFullScreen();
        }
      } catch (fsErr) {
        console.warn('⚠️ Immediate fullscreen attempt failed (will retry after playback):', (fsErr as Error)?.message);
      }
      
      // PRELOAD ground truth for ALL videos in sequence BEFORE test starts
      // This prevents race conditions during video transitions
      console.log(`🔄 [HIL] Preloading ground truth for ${validatedVideos.length} videos...`);
      setCurrentVideoIdx(0);

      let totalDetections = 0;
      const preloadedMap = new Map<string, {timestamp: number, id: string}[]>();

      for (let i = 0; i < validatedVideos.length; i++) {
        const video = validatedVideos[i];
        console.log(`🔄 [HIL] Preloading ground truth ${i + 1}/${validatedVideos.length}: ${video.filename}`);

        try {
          const detections = await loadExpectedDetectionsForVideo(video);
          preloadedMap.set(video.id, detections);
          totalDetections += detections.length;
          console.log(`✅ [HIL] Preloaded ${detections.length} detections for video ${i + 1}`);
        } catch (err) {
          console.error(`❌ [HIL] Failed to preload ground truth for video ${i + 1}:`, err);
          showSnackbar(`Warning: Failed to load ground truth for ${video.filename}`, 'warning');
          preloadedMap.set(video.id, []); // Store empty array to prevent undefined
        }
      }

      // Store all preloaded ground truth in the Map
      setAllVideoExpectedDetections(preloadedMap);
      const firstVideoId = validatedVideos[0]?.id;
      if (firstVideoId) {
        setExpectedDetections(preloadedMap.get(firstVideoId) ?? []);
      } else {
        setExpectedDetections([]);
      }
      console.log(`✅ [HIL] Preloaded ${totalDetections} total detections across ${validatedVideos.length} videos`);
      
      if (totalDetections === 0) {
        console.warn('⚠️ [HIL] No ground truth detections preloaded - proceeding in enhanced debugging mode');
        showSnackbar('No ground truth data found. Test will proceed in debugging mode with video playback enabled.', 'warning');
        console.log('⚠️ [HIL] Triggering automatic debug investigation for missing ground truth');
        setTimeout(async () => {
          await debugGroundTruthIssues();
        }, 1000);
        // Continue execution to allow video loading and debugging features
      } else {
        console.log(`✅ [HIL] Ground truth validation passed: ${totalDetections} detections preloaded across ${validatedVideos.length} videos`);
        showSnackbar(`Ground truth loaded: ${totalDetections} expected detections from ${validatedVideos.length} videos`, 'success');
      }
      
      // Create test session (persist to backend)
      let createdSessionId = `session_${Date.now()}`;
      try {
        const primaryVideo = validatedVideos[0];
        const created = await apiService.createTestSession({
          name: `HIL Test ${new Date().toLocaleString()}`,
          projectId: selectedProject!.id,
          videoId: primaryVideo?.id,
          config: { maxLatencyMs },
          force_start: forceStart
        });
        createdSessionId = created.id;
        // Try to mark session as started (best-effort)
        try {
          await apiService.post(`/api/test-sessions/${createdSessionId}/start`);
        } catch (e) {
          console.warn('[HIL] start endpoint not available:', (e as Error).message);
        }
        console.log('✅ [HIL] Backend session created:', createdSessionId);
      } catch (createErr: any) {
        console.warn('⚠️ [HIL] Failed to create backend session, using local ID only:', createErr?.message || createErr);
      }

      // Initialize video sequence with backend
      let backendSequenceId = `sequence_${createdSessionId}`;
      let enrichedVideoPlaylist = validatedVideos;

      try {
        console.log('🔄 [HIL] Initializing video sequence with backend...');
        const sequenceResponse = await apiService.startVideoSequence(
          selectedProject!.id,
          validatedVideos.map(v => v.id)
        );

        // Update sequence ID and session ID from backend response
        backendSequenceId = sequenceResponse.sequenceId;
        createdSessionId = sequenceResponse.testSessionId;

        // Enrich video playlist with backend metadata
        enrichedVideoPlaylist = validatedVideos.map((video, index) => {
          const backendVideo = sequenceResponse.videoPlaylist.find(v => v.id === video.id);
          return {
            ...video,
            sequenceIndex: backendVideo?.sequenceIndex ?? index,
            estimatedStartOffset: backendVideo?.estimatedStartOffset ?? 0,
            fps: backendVideo?.fps ?? 30
          };
        });

        console.log('✅ [HIL] Backend sequence initialized:', {
          sequenceId: backendSequenceId,
          sessionId: createdSessionId,
          videoCount: enrichedVideoPlaylist.length
        });
      } catch (sequenceErr: any) {
        console.warn('⚠️ [HIL] Backend sequence initialization failed, using local sequence:', sequenceErr?.message || sequenceErr);
        // Continue with local sequence ID and original playlist
      }

      const session: HILTestSession = {
        id: createdSessionId,
        projectId: selectedProject!.id,
        testStartTime: new Date(), // Set Test_Start_Time when test begins
        maxLatencyMs,
        labjackConnected: labjackStatus.connected,
        status: 'running',
        videoPlaylist: enrichedVideoPlaylist,
        vruTracks: [],
        vruTrackingEnabled
      };
      setCurrentSession(session);
      console.log('✅ [HIL] Test session initialized:', session);

      // Set sequence ID for SequentialVideoPlayer using flushSync to prevent race condition
      flushSync(() => {
        setSequenceId(backendSequenceId);
      });
      console.log('✅ [HIL] Sequence ID set (synchronously):', backendSequenceId);

      // BUG FIX #2: Subscribe to video sequence events via WebSocket
      console.log('🔌 [HIL] Subscribing to video sequence events...');
      try {
        const sequenceSubscription = websocketService.subscribeToSequence(backendSequenceId);
        if (sequenceSubscription) {
          // FIX #6: WebSocket Event Handlers - Use correct event names
          // Handle video_started events
          sequenceSubscription.onVideoStarted((data: any) => {
            console.log('🎬 [HIL WebSocket] video_started event received:', data);
            if (data.video_id && data.video_index !== undefined) {
              handleVideoStarted(data.video_id, data.video_index, data.started_at || Date.now());
            }
          });

          // Handle video_ended events
          sequenceSubscription.onVideoEnded((data: any) => {
            console.log('🏁 [HIL WebSocket] video_ended event received:', data);
          });

          // Handle video completed events
          sequenceSubscription.onVideoCompleted((data: any) => {
            console.log('✅ [HIL WebSocket] video_completed event received:', data);
          });

          // Handle sequence completion
          sequenceSubscription.onSequenceCompleted((data: any) => {
            console.log('✅ [HIL WebSocket] sequence_completed event received:', data);
            handleSequenceComplete();
          });

          console.log('✅ [HIL] WebSocket sequence subscriptions established');
        }
      } catch (wsSubErr) {
        console.warn('⚠️ [HIL] WebSocket sequence subscription failed:', wsSubErr);
      }

      // SequentialVideoPlayer will handle video playback automatically
      console.log('✅ [HIL] SequentialVideoPlayer will manage video playback');

      // Initialize LabJack backend monitoring and detections stream (WebSocket if available)
      console.log('🔄 [HIL] Starting LabJack backend monitoring...');
      try {
        await apiService.startSignalMonitoring(session.id);
      } catch (e) {
        console.warn('⚠️ [HIL] startSignalMonitoring failed (continuing anyway):', (e as Error)?.message);
      }
      // Try WebSocket first; fallback to polling if not available
      try {
        const base = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/^http/, 'ws');
        const wsUrl = `${base}/ws/test-sessions/${session.id}/detections`;
        console.log('🔌 [HIL] Attempting WebSocket connection:', wsUrl);
        wsRef.current = new WebSocket(wsUrl);
        wsRef.current.onopen = () => {
          console.log('✅ [HIL] WebSocket connected');
        };
        wsRef.current.onmessage = (evt) => {
          try {
            const payload = JSON.parse(evt.data);
            const items = Array.isArray(payload) ? payload : (payload?.detections ? payload.detections : [payload]);
            items.forEach((d: any, idx: number) => {
              // DYNAMIC TIMING: Use high-precision timestamps, no fallback to Date.now()
              const tsMs = d.timestamp_ms ?? (typeof d.timestamp === 'number' ? d.timestamp * 1000 : null);
              if (tsMs === null) {
                console.warn('⚠️ [HIL WebSocket] Detection missing timestamp, skipping:', d);
                return;
              }

              // DYNAMIC TIMING: Use sequence start time reference
              const sequenceStart = sequenceStartTimeRef.current || currentSession?.testStartTime?.getTime();
              if (!sequenceStart) {
                console.warn('⚠️ [HIL WebSocket] No sequence start time available');
                return;
              }

              const signalReceivedTime = new Date(tsMs);
              const videoElapsedSeconds = (tsMs - sequenceStart) / 1000;

              // Use video-specific ground truth from preloaded Map
              const activeVideoId = currentVideoId || validatedVideos[0]?.id || '';
              const videoGroundTruth = allVideoExpectedDetections.get(activeVideoId) || [];
              if (videoGroundTruth.length === 0) {
                console.warn(`⚠️ [HIL WebSocket] No ground truth for video: ${activeVideoId}`);
                return;
              }

              let nearestExpected: any = null; let minTimeDiff = Infinity;
              for (const expected of videoGroundTruth) {
                const td = Math.abs(videoElapsedSeconds - expected.timestamp);
                if (td < minTimeDiff) { minTimeDiff = td; nearestExpected = expected; }
              }
              // DYNAMIC TIMING: Calculate latency relative to video start
              const activeVideoStartTime = videoStartTimes.get(currentVideoId || '');
              const videoRelativeSeconds = activeVideoStartTime ? (tsMs - activeVideoStartTime) / 1000 : videoElapsedSeconds;

              const latencyMs = nearestExpected
                ? Math.abs((videoRelativeSeconds - nearestExpected.timestamp) * 1000)
                : Math.abs(Number(d.latency_ms ?? 0));

              // DYNAMIC TIMING: Expected event time relative to video start
              const expectedEventTime = nearestExpected && activeVideoStartTime
                ? new Date(activeVideoStartTime + nearestExpected.timestamp * 1000)
                : new Date(sequenceStart + videoElapsedSeconds * 1000);
              const outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection' = Math.abs(latencyMs) > maxLatencyMs ? 'fail_high_latency' : 'pass';
              const event: DetectionEvent = {
                expectedEventTime,
                signalReceivedTime,
                latencyMs,
                outcome,
                videoId: (d.video_id || validatedVideos[currentVideoIdx]?.id || '') as string,
                frameNumber: nearestExpected?.frameNumber
              } as DetectionEvent;
              setDetectionEvents(prev => [...prev, event]);
            });
          } catch (e) {
            console.warn('⚠️ [HIL] WS parse error:', (e as Error)?.message);
          }
        };
        wsRef.current.onerror = () => {
          console.warn('⚠️ [HIL] WebSocket error; falling back to polling');
          try { wsRef.current && wsRef.current.close(); } catch {}
          startSignalPolling(session);
        };
        // If WS doesn’t open quickly, fallback to polling
        setTimeout(() => {
          if (!wsRef.current || wsRef.current.readyState !== 1) {
            console.log('ℹ️ [HIL] WS not open yet; starting polling');
            startSignalPolling(session);
          }
        }, 1500);
      } catch (e) {
        console.warn('⚠️ [HIL] WebSocket setup failed; starting polling:', (e as Error)?.message);
        startSignalPolling(session);
      }
      console.log('✅ [HIL] Detection stream initialized');
      
      showSnackbar('HIL Test Started - Full Screen Mode Active', 'success');
      console.log('🎉 [HIL] Test started successfully!');
      
    } catch (err: any) {
      console.error('❌ [HIL] Test start failed:', err);
      setTestRunning(false);
      setError(`Failed to start test: ${err.message}`);
      showSnackbar('Failed to start test', 'error');
    }
  };

  // PRD: Full-screen mode (required)
  const enterFullScreen = useCallback(async () => {
    console.log('🎬 enterFullScreen called:', {
      fullscreenContainerRef: !!fullscreenContainerRef.current,
      currentFullscreen: document.fullscreenElement,
      isFullScreen
    });
    
    const container = fullscreenContainerRef.current;

    if (container) {
      try {
        console.log('🎬 Attempting fullscreen on container:', container);
        
        if (container.requestFullscreen) {
          console.log('🎬 Using standard requestFullscreen');
          await container.requestFullscreen();
        } else if ((container as any).webkitRequestFullscreen) {
          console.log('🎬 Using webkit requestFullscreen');
          await (container as any).webkitRequestFullscreen();
        } else if ((container as any).msRequestFullscreen) {
          console.log('🎬 Using ms requestFullscreen');
          await (container as any).msRequestFullscreen();
        }
        
        console.log('✅ Fullscreen request succeeded');
        setIsFullScreen(true);
        autoFullscreenAttemptRef.current = true;
        
        // Debug fullscreen state after request
        setTimeout(() => {
          console.log('🎬 Fullscreen state after request:', {
            documentFullscreen: !!document.fullscreenElement,
            containerElement: !!fullscreenContainerRef.current
          });
        }, 100);
        
      } catch (err) {
        console.error('❌ Fullscreen failed:', err);
        autoFullscreenAttemptRef.current = false;
        showSnackbar('Fullscreen not available, continuing in window mode', 'warning');
      }
    }
  }, [isFullScreen, showSnackbar]);

  const exitFullScreen = useCallback(async () => {
    try {
      // Check if document is in fullscreen mode before attempting to exit
      const isCurrentlyFullscreen = !!(document.fullscreenElement ||
                                       (document as any).webkitFullscreenElement ||
                                       (document as any).msFullscreenElement);

      if (!isCurrentlyFullscreen) {
        console.warn('Document not in fullscreen mode, skipping exit');
        setIsFullScreen(false);
        return;
      }

      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen();
      } else if ((document as any).msExitFullscreen) {
        await (document as any).msExitFullscreen();
      }
      setIsFullScreen(false);
    } catch (err) {
      console.warn('Exit fullscreen failed:', err);
      // Force state update even if exit failed
      setIsFullScreen(false);
    }
  }, []);

  useEffect(() => {
    if (!testRunning) {
      autoFullscreenAttemptRef.current = false;
      return;
    }

    const isCurrentlyFullscreen = !!(document.fullscreenElement ||
                                     (document as any).webkitFullscreenElement ||
                                     (document as any).msFullscreenElement);

    if (
      testRunning &&
      sequenceId &&
      validatedVideos.length > 0 &&
      fullscreenContainerRef.current &&
      !isCurrentlyFullscreen &&
      !autoFullscreenAttemptRef.current
    ) {
      autoFullscreenAttemptRef.current = true;
      enterFullScreen().catch((err) => {
        console.warn('⚠️ [HIL] Deferred fullscreen attempt failed:', err);
        autoFullscreenAttemptRef.current = false;
      });
    }
  }, [testRunning, sequenceId, validatedVideos.length, enterFullScreen]);

  // PRD: Capture Test_Start_Time at exact video playback start with high-precision timing
  const handleVideoStart = () => {
    if (currentSession) {
      const precisionTimestamp = getHighPrecisionTimestamp();
      const testStartTime = new Date(); // PRD: High-precision Test_Start_Time

      // Store both Date object for compatibility and precision timestamp
      sequenceStartTimeRef.current = precisionTimestamp;
      setCurrentSession(prev => prev ? { ...prev, testStartTime } : null);

      console.log('HIL Test - High-Precision Test_Start_Time captured:', {
        isoTimestamp: testStartTime.toISOString(),
        precisionTimestamp: precisionTimestamp.toFixed(2),
        context: 'HILTestExecution'
      });

      showSnackbar('High-precision timing started', 'success');
    }
  };

  // Backend-driven LabJack monitoring (replaces simulation)
  const startSignalPolling = (session: HILTestSession) => {
    console.log('🚀 [HIL] Starting backend signal monitoring...');
    console.log('  Expected detections:', expectedDetections.length);
    console.log('  Session provided:', session);
    console.log('  Test running:', testRunning);

    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    const processedIds = new Set<string>();
    let pollCount = 0;

    pollingIntervalRef.current = setInterval(async () => {
      if (!testRunning || !session) return;
      pollCount++;
      try {
        const detections = await apiService.getTestSessionDetections(session.id);
        if (Array.isArray(detections) && detections.length > 0) {
          detections.forEach((d: any, idx: number) => {
            const id = (d.id || d.detection_id || `${idx}-${d.timestamp}`) as string;
            if (processedIds.has(id)) return;

            // DYNAMIC TIMING: Use high-precision timestamps, no fallback to Date.now()
            const tsMs = d.timestamp_ms ?? (typeof d.timestamp === 'number' ? d.timestamp * 1000 : null);
            if (tsMs === null) {
              console.warn('⚠️ [HIL Polling] Detection missing timestamp, skipping:', d);
              return;
            }

            // DYNAMIC TIMING: Use sequence start time reference
            const sequenceStart = sequenceStartTimeRef.current || session.testStartTime?.getTime();
            if (!sequenceStart) {
              console.warn('⚠️ [HIL Polling] No sequence start time available');
              return;
            }

            const signalReceivedTime = new Date(tsMs);
            const videoElapsedSeconds = (tsMs - sequenceStart) / 1000;

            // Use video-specific ground truth from preloaded Map
            const activeVideoId = currentVideoId || validatedVideos[0]?.id || '';
            const videoGroundTruth = allVideoExpectedDetections.get(activeVideoId) || [];
            if (videoGroundTruth.length === 0) {
              console.warn(`⚠️ [HIL Polling] No ground truth for video: ${activeVideoId}`);
              return;
            }

            let nearestExpected: any = null;
            let minTimeDiff = Infinity;
            for (const expected of videoGroundTruth) {
              const timeDiff = Math.abs(videoElapsedSeconds - expected.timestamp);
              if (timeDiff < minTimeDiff) {
                minTimeDiff = timeDiff;
                nearestExpected = expected as any;
              }
            }

            // DYNAMIC TIMING: Calculate latency relative to video start
            const activeVideoStartTime = videoStartTimes.get(currentVideoId || '');
            const videoRelativeSeconds = activeVideoStartTime ? (tsMs - activeVideoStartTime) / 1000 : videoElapsedSeconds;

            const latencyMs = nearestExpected
              ? Math.abs((videoRelativeSeconds - nearestExpected.timestamp) * 1000)
              : Math.abs(Number(d.latency_ms ?? 0));

            // DYNAMIC TIMING: Expected event time relative to video start
            const expectedEventTime = nearestExpected && activeVideoStartTime
              ? new Date(activeVideoStartTime + nearestExpected.timestamp * 1000)
              : new Date(sequenceStart + videoElapsedSeconds * 1000);
            const outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection' =
              Math.abs(latencyMs) > maxLatencyMs ? 'fail_high_latency' : 'pass';

            const event: DetectionEvent = {
              expectedEventTime,
              signalReceivedTime,
              latencyMs,
              outcome,
              videoId: (d.video_id || validatedVideos[0]?.id || '') as string,
              frameNumber: nearestExpected?.frameNumber
            } as DetectionEvent;

            processedIds.add(id);
            setDetectionEvents(prev => [...prev, event]);
          });
        } else if (pollCount % 10 === 1) {
          console.log('⏱️ [HIL] Polling backend detections... none yet');
        }
      } catch (err) {
        if (pollCount % 10 === 1) {
          console.warn('⚠️ [HIL] Backend detection polling failed, will retry:', (err as Error)?.message);
        }
      }
    }, 300);
  };

  // PRD: Handle LabJack signal detection with multi-video sequence support
  const handleLabJackSignal = (signalData: any, session: HILTestSession) => {
    console.log('🎯 [HIL] handleLabJackSignal called with:', { signalData, session: !!session });

    if (!session || !session.testStartTime) {
      console.error('❌ [HIL] handleLabJackSignal: No session or test start time');
      return;
    }

    // DYNAMIC TIMING: Use high-precision timestamp from signal (NO FALLBACK)
    const signalTimestamp = signalData.timestamp_ms || signalData.timestamp || null;
    if (signalTimestamp === null) {
      console.warn('⚠️ [HIL LabJack] Detection missing timestamp, skipping:', signalData);
      return;
    }

    // DYNAMIC TIMING: Calculate sequence-relative time (from test start)
    const sequenceStartMs = sequenceStartTimeRef.current || session.testStartTime.getTime();
    const sequenceElapsedMs = signalTimestamp - sequenceStartMs;
    const sequenceElapsedSeconds = sequenceElapsedMs / 1000;

    // DYNAMIC TIMING: Get current video context
    const activeVideoId = currentVideoId || validatedVideos[currentVideoIdx]?.id || '';
    const videoStartTime = videoStartTimes.get(activeVideoId);

    // DYNAMIC TIMING: Calculate video-relative time (from video start)
    const videoRelativeSeconds = videoStartTime
      ? (signalTimestamp - videoStartTime) / 1000
      : sequenceElapsedSeconds;

    console.log(`📊 [HIL] Processing signal:`, {
      sequenceElapsed: sequenceElapsedSeconds.toFixed(2),
      videoRelative: videoRelativeSeconds.toFixed(2),
      currentVideoId: activeVideoId,
      currentVideoIndex: currentVideoIdx,
      voltage: signalData.voltage?.toFixed(2)
    });

    // Find nearest expected detection from ground truth (use video-specific ground truth from Map)
    const videoGroundTruth = allVideoExpectedDetections.get(activeVideoId) || [];
    if (videoGroundTruth.length === 0) {
      console.warn(`⚠️ [HIL LabJack] No ground truth loaded for video: ${activeVideoId}`);
      return;
    }

    let nearestExpected = null;
    let minTimeDiff = Infinity;

    for (const expected of videoGroundTruth) {
      const timeDiff = Math.abs(videoRelativeSeconds - expected.timestamp);
      if (timeDiff < minTimeDiff) {
        minTimeDiff = timeDiff;
        nearestExpected = expected;
      }
    }

    if (!nearestExpected) {
      console.warn('⚠️ [HIL] No expected detection found for signal at video time', videoRelativeSeconds);
      console.log('Available expected detections for this video:', videoGroundTruth.map(e => `${e.id}@${e.timestamp}s`));
      return;
    }

    console.log(`🎯 [HIL] Found nearest expected: ${nearestExpected.id} at ${nearestExpected.timestamp}s (diff: ${minTimeDiff.toFixed(3)}s)`);

    // DYNAMIC TIMING: Calculate latency using video-relative timestamps
    // Latency = (signal_video_time - expected_video_time)
    const latencyMs = (videoRelativeSeconds - nearestExpected.timestamp) * 1000;

    // DYNAMIC TIMING: Calculate expected event time relative to VIDEO START (not test start)
    // For multi-video sequences, this ensures proper timing per video
    const expectedEventTime = videoStartTime
      ? new Date(videoStartTime + (nearestExpected.timestamp * 1000))
      : new Date(session.testStartTime.getTime() + nearestExpected.timestamp * 1000);

    // PRD: Determine outcome based on latency threshold
    let outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection' = 'pass';
    if (Math.abs(latencyMs) > maxLatencyMs) {
      outcome = 'fail_high_latency';
    }

    const event: DetectionEvent = {
      expectedEventTime,
      signalReceivedTime: new Date(signalTimestamp),
      latencyMs: Math.abs(latencyMs),
      outcome,
      videoId: activeVideoId,
      frameNumber: nearestExpected.frameNumber,
      // DYNAMIC TIMING: Multi-video sequence context with precision timestamps
      videoIndex: currentVideoIdx,
      videoStartTime: videoStartTime, // High-precision video start time
      videoRelativeTimestamp: videoRelativeSeconds, // Time since THIS video started
      sequenceRelativeTimestamp: sequenceElapsedSeconds // Time since sequence started
    };

    console.log(`✅ [HIL] Creating detection event:`, {
      latencyMs: latencyMs.toFixed(1),
      outcome,
      expected: nearestExpected.timestamp,
      actualVideoTime: videoRelativeSeconds,
      actualSequenceTime: sequenceElapsedSeconds,
      threshold: maxLatencyMs,
      videoId: activeVideoId,
      videoIndex: currentVideoIdx
    });

    setDetectionEvents(prev => {
      const newCount = prev.length + 1;
      console.log(`📈 [HIL] Detection events: ${prev.length} → ${newCount}`);
      return [...prev, event];
    });

    // Show real-time feedback
    const status = outcome === 'pass' ? 'success' : 'error';
    showSnackbar(
      `Detection (Video ${currentVideoIdx + 1}): ${Math.abs(latencyMs).toFixed(1)}ms latency - ${outcome.toUpperCase()}`,
      status
    );

    console.log('✅ [HIL] Detection event:', {
      expected: nearestExpected.timestamp,
      actualVideoTime: videoRelativeSeconds,
      actualSequenceTime: sequenceElapsedSeconds,
      latency: latencyMs,
      outcome
    });
  };

  // Legacy handleVideoEnded - now replaced by SequentialVideoPlayer callbacks
  // const handleVideoEnded = async () => { ... }
  // SequentialVideoPlayer now manages video transitions and completion

  // Generate test results locally without backend dependency
  const generateTestResults = useCallback(async () => {
    if (!currentSession || !selectedProject) return null;

    const testEndTime = new Date();
    const testDuration = testEndTime.getTime() - (currentSession.testStartTime?.getTime() || testEndTime.getTime());

    // Calculate PER-VIDEO results for multi-video sequences
    const videoResults: any[] = [];
    let totalExpectedDetections = 0;
    let totalMissedDetections = 0;

    // Group detection events by video
    const detectionsByVideo = new Map<string, DetectionEvent[]>();
    for (const event of detectionEvents) {
      const videoId = event.videoId;
      if (!detectionsByVideo.has(videoId)) {
        detectionsByVideo.set(videoId, []);
      }
      detectionsByVideo.get(videoId)!.push(event);
    }

    // Calculate results for each video
    for (const video of validatedVideos) {
      const videoId = video.id;
      const videoExpected = allVideoExpectedDetections.get(videoId) || [];
      const videoDetections = detectionsByVideo.get(videoId) || [];

      const videoPassed = videoDetections.filter(e => e.outcome === 'pass').length;
      const videoFailed = videoDetections.filter(e => e.outcome === 'fail_high_latency').length;

      // Calculate missed detections for this video
      const videoDetectedTimestamps = new Set(
        videoDetections.map(e => Math.round(e.videoRelativeTimestamp! * 10) / 10) // Round to 0.1s
      );

      const videoMissed = videoExpected.filter(expected => {
        const expectedTime = Math.round(expected.timestamp * 10) / 10;
        return !videoDetectedTimestamps.has(expectedTime);
      }).length;

      const videoPassRate = videoExpected.length > 0
        ? (videoPassed / videoExpected.length) * 100
        : 0;

      // Calculate latency stats for this video
      const videoLatencies = videoDetections.map(e => e.latencyMs || 0);
      const videoAvgLatency = videoLatencies.length > 0
        ? videoLatencies.reduce((a, b) => a + b, 0) / videoLatencies.length
        : 0;
      const videoMaxLatency = videoLatencies.length > 0 ? Math.max(...videoLatencies) : 0;
      const videoMinLatency = videoLatencies.length > 0 ? Math.min(...videoLatencies) : 0;

      videoResults.push({
        video_id: videoId,
        video_filename: video.filename,
        video_order: validatedVideos.indexOf(video),
        video_start_time: videoStartTimes.get(videoId) || 0,
        video_duration_seconds: video.duration || 0,
        expected_detections: videoExpected.length,
        actual_detections: videoDetections.length,
        passed_detections: videoPassed,
        failed_detections: videoFailed,
        missed_detections: videoMissed,
        pass_rate: videoPassRate,
        avg_latency_ms: Math.round(videoAvgLatency * 100) / 100,
        max_latency_ms: videoMaxLatency,
        min_latency_ms: videoMinLatency,
        detection_events: videoDetections
      });

      totalExpectedDetections += videoExpected.length;
      totalMissedDetections += videoMissed;

      console.log(`📊 [HIL] Video ${validatedVideos.indexOf(video) + 1} (${video.filename}):`, {
        expected: videoExpected.length,
        detected: videoDetections.length,
        passed: videoPassed,
        failed: videoFailed,
        missed: videoMissed,
        passRate: `${videoPassRate.toFixed(1)}%`
      });
    }

    // Calculate overall results
    const actualDetections = detectionEvents.length;
    const passedDetections = detectionEvents.filter(e => e.outcome === 'pass').length;
    const failedDetections = detectionEvents.filter(e => e.outcome === 'fail_high_latency').length;
    const totalFailedDetections = failedDetections + totalMissedDetections;
    const passRate = totalExpectedDetections > 0 ? (passedDetections / totalExpectedDetections) * 100 : 0;
    
    // Display real-time results summary
    console.log('📊 [HIL] Final Test Results:');
    console.log(`  Total Expected: ${totalExpectedDetections}`);
    console.log(`  Detected: ${actualDetections}`);
    console.log(`  Passed: ${passedDetections} (within ${maxLatencyMs}ms)`);
    console.log(`  Failed (High Latency): ${failedDetections}`);
    console.log(`  Missed (False Negatives): ${totalMissedDetections} ⚠️`);
    console.log(`  Total Failed: ${totalFailedDetections}`);
    console.log(`  Pass Rate: ${passRate.toFixed(1)}%`);
    console.log(`  Videos in Sequence: ${validatedVideos.length}`);

    // Calculate latency statistics
    const latencies = detectionEvents.map(e => e.latencyMs || 0);
    const averageLatency = latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : 0;
    const maxLatency = latencies.length > 0 ? Math.max(...latencies) : 0;
    const minLatency = latencies.length > 0 ? Math.min(...latencies) : 0;

    const results = {
      session_id: currentSession.id,
      sequence_id: sequenceId,
      project_id: selectedProject.id,
      project_name: selectedProject.name,
      test_start_time: currentSession.testStartTime,
      test_end_time: testEndTime,
      test_duration_seconds: Math.round(testDuration / 1000),

      // Overall statistics
      overall_pass_rate: Math.round(passRate * 100) / 100,
      overall_avg_latency_ms: Math.round(averageLatency * 100) / 100,
      total_detections: totalExpectedDetections,
      total_passed: passedDetections,
      total_failed: totalFailedDetections,
      total_missed: totalMissedDetections,

      // Per-video results array
      video_results: videoResults,

      // Aggregated fields for API compatibility and results display
      passed_detections: passedDetections,
      failed_detections: totalFailedDetections,
      pass_rate: Math.round(passRate * 100) / 100,
      average_latency_ms: Math.round(averageLatency * 100) / 100,
      max_latency_ms: maxLatency,
      min_latency_ms: minLatency,
      max_latency_threshold_ms: maxLatencyMs,
      test_status: passRate >= 80 ? 'PASSED' : 'FAILED',
      detection_events: detectionEvents,
      labjack_connected: labjackStatus.connected,
      video_count: validatedVideos.length,

      // Multi-video sequence flag
      has_video_sequence: validatedVideos.length > 1,
      per_video_results: videoResults // Alternative field name for backend compatibility
    };

    console.log('📊 [HIL] Generated test results:', results);

    // Persist locally so Results page can display entries even if backend lacks persistence
    try {
      const localKey = `hilLocalResults:${results.session_id}`;
      localStorage.setItem(localKey, JSON.stringify(results));
      const sessionsKey = 'hilLocalSessions';
      const existing = JSON.parse(localStorage.getItem(sessionsKey) || '[]');
      const entry = {
        sessionId: results.session_id,
        sessionName: results.project_name ? `${results.project_name} – HIL` : 'HIL Test',
        projectId: results.project_id,
        status: 'completed',
        startedAt: results.test_start_time || new Date().toISOString(),
        completedAt: results.test_end_time || new Date().toISOString(),
        metrics: {
          accuracy: results.pass_rate, // use pass rate as a placeholder
          precision: results.pass_rate,
          recall: results.pass_rate,
          f1Score: results.pass_rate,
          truePositives: results.passed_detections,
          falsePositives: 0,
          falseNegatives: results.failed_detections,
          totalDetections: results.total_detections,
          duration: results.test_duration_seconds
        }
      };
      const updated = Array.isArray(existing)
        ? [entry, ...existing.filter((e: any) => e.sessionId !== entry.sessionId)]
        : [entry];
      localStorage.setItem(sessionsKey, JSON.stringify(updated));
    } catch (e) {
      console.warn('[HIL] Failed to write local session cache:', (e as Error)?.message);
    }
    return results;
  }, [currentSession, selectedProject, detectionEvents, validatedVideos, allVideoExpectedDetections, videoStartTimes, sequenceId, maxLatencyMs, labjackStatus.connected]);

  // Save results to database via API
  const saveResultsToDatabase = useCallback(async (results: any) => {
    try {
      console.log('💾 [HIL] Saving results to database...');
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/test-sessions/${results.session_id}/results`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(results),
      });

      if (!response.ok) {
        throw new Error(`Failed to save results: ${response.statusText}`);
      }

      const savedResults = await response.json();
      console.log('✅ [HIL] Results saved successfully:', savedResults);
      return savedResults;
    } catch (error) {
      console.error('❌ [HIL] Failed to save results:', error);
      showSnackbar('Failed to save test results', 'error');
      return null;
    }
  }, [showSnackbar]);

  // Stop test and generate results with automatic navigation
  const stopTestAndGenerateResults = useCallback(async () => {
    try {
      console.log('🛑 [HIL] Stopping test and generating results...');
      setTestRunning(false);

      // Close WebSocket connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      // Stop signal polling
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        console.log('⏹️ [HIL] Signal polling stopped');
      }

      // Pause video
      if (videoRef.current) {
        videoRef.current.pause();
      }

      // Exit fullscreen
      await exitFullScreen();

      // Generate results
      const results = await generateTestResults();
      if (results) {
        console.log('📊 [HIL] Results generated successfully - persisting');
        const saved = await saveResultsToDatabase(results);
        // Try to mark session as stopped/completed (best-effort)
        try {
          await apiService.post(`/api/test-sessions/${results.session_id}/stop`);
        } catch (e) {
          console.warn('[HIL] stop endpoint not available:', (e as Error).message);
        }

        showSnackbar('Test completed - Results saved!', 'success');

        // Prefer opening the HIL simplified page for this session
        const targetSessionId = results.session_id;
        console.log('🔄 [HIL] Navigating to /results/:sessionId ...');
        navigate(`/results/${targetSessionId}`);
        // Note: The list at /results will show the row once backend includes this session in GET /api/test-sessions
      }

      // Update session status
      if (currentSession) {
        setCurrentSession(prev => prev ? { ...prev, status: 'completed' } : null);
      }

    } catch (err: any) {
      console.error('❌ [HIL] Failed to complete test:', err);
      showSnackbar('Failed to complete test', 'error');
    }
  }, [exitFullScreen, generateTestResults, saveResultsToDatabase, showSnackbar, navigate, currentSession]);

  // Assign to ref for use in handleSequenceComplete
  useEffect(() => {
    stopTestAndGenerateResultsRef.current = stopTestAndGenerateResults;
  }, [stopTestAndGenerateResults]);

  const stopTest = async () => {
    await stopTestAndGenerateResults();
  };

  // ESC key handler for stopping test
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && testRunning) {
        event.preventDefault();
        stopTest();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [testRunning]);

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullScreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
    };
  }, []);


  return (
    <div>
      <Box sx={{ p: isFullScreen ? 0 : 3 }}>
        {/* Hide UI in full-screen mode */}
        {!isFullScreen && (
          <>
            {/* Header */}
            <Typography variant="h4" gutterBottom>
              HIL Test Execution
            </Typography>

            {/* Error Alert */}
            {error && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* Main Test Setup Card */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Test Setup
                </Typography>

                {/* 1. Project Selection (PRD requirement) */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    1. Project Selection
                  </Typography>
                  <FormControl fullWidth sx={{ mb: 1 }}>
                    <InputLabel>Select Project</InputLabel>
                    <Select
                      value={selectedProject?.id || ''}
                      onChange={(e) => {
                        console.log('🎯 HIL: Dropdown changed to:', e.target.value);
                        const project = projects.find(p => p.id === e.target.value);
                        console.log('🎯 HIL: Found project:', project);
                        if (project) handleProjectSelect(project);
                      }}
                      disabled={testRunning}
                    >
                      {Array.isArray(projects) && projects.map((project) => {
                        console.log('📋 HIL: Rendering project option:', {id: project.id, name: project.name});
                        return (
                          <MenuItem key={project.id} value={project.id}>
                            {project.name}
                          </MenuItem>
                        );
                      })}
                    </Select>
                  </FormControl>
                  
                  {selectedProject && (
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Video Playlist: {validatedVideos.length} validated videos (Total: {videoPlaylist.length})
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Expected Detections: {expectedDetections.length} loaded
                      </Typography>
                      {/* Debug button for ground truth investigation */}
                      <Button
                        size="small"
                        onClick={debugGroundTruthIssues}
                        variant="outlined"
                        color="info"
                        sx={{ mt: 1 }}
                      >
                        🔍 Debug Ground Truth Loading
                      </Button>
                    </Box>
                  )}
                </Box>

                {/* 2. LabJack Connection Status (PRD requirement) */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    2. Hardware Connection Status
                  </Typography>
                  <SimpleLabJackStatus
                    onStatusChange={(status) => {
                      console.log('🔄 [HIL] LabJack status changed:', status);
                      setLabjackStatus(status);
                    }}
                    showRefreshButton={true}
                  />
                </Box>

                {/* 3. Latency Input (PRD requirement) */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    3. Maximum Acceptable Latency
                  </Typography>
                  <TextField
                    label="Maximum Latency (ms)"
                    type="number"
                    value={maxLatencyMs}
                    onChange={(e) => setMaxLatencyMs(Number(e.target.value) || 100)}
                    disabled={testRunning}
                    inputProps={{ min: 1, max: 10000 }}
                    helperText="Enter maximum acceptable latency in milliseconds (PRD requirement)"
                    sx={{ maxWidth: 300 }}
                  />
                </Box>

                {/* 4. Ground Truth Status Display - Multi-Video Sequence */}
                {selectedProject && (
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      4. Multi-Video Sequence Status
                    </Typography>

                    {/* Overall sequence info */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <Chip
                        label={`${validatedVideos.length} Videos in Sequence`}
                        color="primary"
                        variant="outlined"
                      />
                      <Chip
                        icon={expectedDetections.length > 0 ? <CheckCircleIcon color="success" /> : <WarningIcon color="warning" />}
                        label={expectedDetections.length > 0
                          ? `${expectedDetections.length} Detections (Current Video)`
                          : 'No Ground Truth Loaded'
                        }
                        color={expectedDetections.length > 0 ? 'success' : 'warning'}
                        variant={expectedDetections.length > 0 ? 'filled' : 'outlined'}
                      />
                      <Button
                        size="small"
                        startIcon={<RefreshIcon />}
                        onClick={() => {
                          console.log('🔄 [HIL] Manual ground truth reload requested');
                          loadExpectedDetections();
                        }}
                        disabled={testRunning || loading}
                      >
                        Reload Ground Truth
                      </Button>
                    </Box>

                    {/* Video sequence list */}
                    <Box sx={{
                      p: 2,
                      bgcolor: 'grey.50',
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: 'grey.300'
                    }}>
                      <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                        Video Sequence Order:
                      </Typography>
                      {validatedVideos.map((video, index) => (
                        <Box
                          key={video.id}
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            mb: 1,
                            p: 1,
                            bgcolor: index === 0 ? 'primary.50' : 'transparent',
                            borderRadius: 1,
                            border: index === 0 ? '1px solid' : 'none',
                            borderColor: 'primary.300'
                          }}
                        >
                          <Chip
                            label={`${index + 1}`}
                            size="small"
                            color={index === 0 ? 'primary' : 'default'}
                            sx={{ minWidth: 30 }}
                          />
                          <Typography variant="body2" sx={{ flex: 1 }}>
                            {video.filename}
                          </Typography>
                          {video.duration && (
                            <Typography variant="caption" color="text.secondary">
                              {video.duration.toFixed(1)}s
                            </Typography>
                          )}
                          {index === 0 && (
                            <Chip label="Ready to play" size="small" color="success" />
                          )}
                        </Box>
                      ))}

                      {/* Total duration */}
                      <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'grey.300' }}>
                        <Typography variant="body2" color="text.secondary">
                          <strong>Total Sequence Duration:</strong>{' '}
                          {validatedVideos.reduce((sum, v) => sum + (v.duration || 0), 0).toFixed(1)}s
                        </Typography>
                      </Box>
                    </Box>

                    {/* Ground truth summary for all videos */}
                    <Box sx={{ mt: 2, p: 2, bgcolor: 'info.50', borderRadius: 1, border: '1px solid', borderColor: 'info.200' }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                        📋 Ground Truth Summary
                      </Typography>

                      {expectedDetections.length > 0 ? (
                        <>
                          <Typography variant="body2" color="text.secondary">
                            <strong>Currently Loaded:</strong> {validatedVideos[0]?.filename}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            <strong>Detections Ready:</strong> {expectedDetections.length} annotations
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                            Sample times: {expectedDetections.slice(0, 5).map(d => `${d.timestamp.toFixed(1)}s`).join(', ')}
                            {expectedDetections.length > 5 && ` ... +${expectedDetections.length - 5} more`}
                          </Typography>
                        </>
                      ) : (
                        <Typography variant="body2" color="warning.main">
                          No ground truth loaded yet. Will load when test starts.
                        </Typography>
                      )}

                      <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px dashed', borderColor: 'info.300' }}>
                        <Typography variant="caption" color="info.dark" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <span style={{ fontSize: '1.2em' }}>🔄</span>
                          <strong>Auto-Loading:</strong> Each video's ground truth loads automatically when it starts playing
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                          Test will validate {validatedVideos.length} video{validatedVideos.length > 1 ? 's' : ''} sequentially without interruption
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                )}

                {/* 5. Software Delays & Pipeline (runtime) */}
                {testRunning && (
                  <Card sx={{ mb: 3 }}>
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        Software Delays
                      </Typography>
                      {!(t3Alerts && (t3Alerts.alerts.t3_pipeline?.length || t3Alerts.alerts.video_monitor?.length || t3Alerts.alerts.database?.length)) ? (
                        <Typography variant="body2" color="text.secondary">No software delays detected.</Typography>
                      ) : (
                        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mt: 1 }}>
                          {t3Alerts?.alerts.t3_pipeline?.map((a, i) => (
                            <Chip key={`t3-${i}`} label={`T3: ${a.type}`} color={a.severity === 'error' ? 'error' : 'warning'} size="small" />
                          ))}
                          {t3Alerts?.alerts.video_monitor?.map((a, i) => (
                            <Chip key={`vm-${i}`} label={`Video: ${a.type}`} color={a.severity === 'error' ? 'error' : 'warning'} size="small" />
                          ))}
                          {t3Alerts?.alerts.database?.map((a, i) => (
                            <Chip key={`db-${i}`} label={`DB: ${a.type}`} color={a.severity === 'error' ? 'error' : 'warning'} size="small" />
                          ))}
                        </Stack>
                      )}
                      {t3PipelineSummary && (
                        <Box sx={{ mt: 2 }}>
                          <Typography variant="subtitle2">T4–T3 Latency (ms)</Typography>
                          <Stack direction="row" spacing={2}>
                            <Chip label={`Avg: ${t3PipelineSummary.avg ?? 0}`} size="small" />
                            <Chip label={`Min: ${t3PipelineSummary.min ?? 0}`} size="small" />
                            <Chip label={`Max: ${t3PipelineSummary.max ?? 0}`} size="small" />
                            <Chip label={`Pass: ${typeof t3PipelineSummary.passRate === 'number' ? Math.round(t3PipelineSummary.passRate) : 0}%`} size="small" color="success" />
                          </Stack>
                        </Box>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Start Test Button */}
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<PlayIcon />}
                    onClick={() => setStartTestDialog(true)}
                    disabled={!canStartTest().canStart || testRunning || loading}
                  >
                    Start HIL Test
                  </Button>
                  
                  {testRunning && (
                    <Button
                      variant="contained"
                      color="error"
                      startIcon={<StopIcon />}
                      onClick={stopTest}
                    >
                      Stop Test
                    </Button>
                  )}
                </Box>

                {/* Validation Messages */}
                {!canStartTest().canStart && (
                  <Box sx={{ mt: 2 }}>
                    {canStartTest().reasons.map((reason, index) => (
                      <Alert key={index} severity="warning" sx={{ mt: 1 }}>
                        {reason}
                      </Alert>
                    ))}
                  </Box>
                )}
              </CardContent>
            </Card>

            {/* Test Results (Real-time) */}
            {detectionEvents.length > 0 && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Real-Time Test Results ({detectionEvents.length} / {expectedDetections.length} detections)
                  </Typography>
                  
                  {/* Summary Statistics */}
                  <Box sx={{ mb: 2 }}>
                    {(() => {
                      const totalExpected = expectedDetections.length;
                      const passed = detectionEvents.filter(e => e.outcome === 'pass').length;
                      const failedHighLatency = detectionEvents.filter(e => e.outcome === 'fail_high_latency').length;
                      const detected = detectionEvents.length;
                      const missed = Math.max(0, totalExpected - detected);
                      const passRate = totalExpected > 0 ? (passed / totalExpected) * 100 : 0;
                      const avgLatency = detectionEvents.length > 0 
                        ? detectionEvents.reduce((sum, e) => sum + (e.latencyMs || 0), 0) / detectionEvents.length 
                        : 0;
                      
                      return (
                        <>
                          <Stack direction="row" spacing={4} sx={{ mb: 2 }}>
                            <Typography variant="body1">
                              <strong>Expected:</strong> {totalExpected}
                            </Typography>
                            <Typography variant="body1">
                              <strong>Detected:</strong> {detected}
                            </Typography>
                            <Typography variant="body1">
                              <strong>Passed:</strong> {passed}
                            </Typography>
                            <Typography variant="body1">
                              <strong>Failed (Latency):</strong> {failedHighLatency}
                            </Typography>
                            <Typography variant="body1">
                              <strong>Missed:</strong> {missed}
                            </Typography>
                          </Stack>
                          <Stack direction="row" spacing={4}>
                            <Typography variant="body1" color={passRate >= 80 ? 'success.main' : passRate >= 60 ? 'warning.main' : 'error.main'}>
                              <strong>Pass Rate:</strong> {passRate.toFixed(1)}%
                            </Typography>
                            <Typography variant="body1">
                              <strong>Avg Latency:</strong> {avgLatency.toFixed(1)}ms
                            </Typography>
                            <Typography variant="body1">
                              <strong>Threshold:</strong> {maxLatencyMs}ms
                            </Typography>
                          </Stack>
                        </>
                      );
                    })()}
                  </Box>
                  
                  <LinearProgress
                    variant="determinate"
                    value={detectionEvents.length > 0 ? (detectionEvents.filter(e => e.outcome === 'pass').length / detectionEvents.length) * 100 : 0}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* Full-Screen Video Player (PRD requirement) - Using SequentialVideoPlayer */}
        {testRunning && validatedVideos.length > 0 && sequenceId && (
          <Box
            ref={fullscreenContainerRef}
            id="video-container"
            sx={{
              width: '100%',
              height: isFullScreen ? '100vh' : '600px',
              backgroundColor: 'black',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <VideoPlayerErrorBoundary
              onError={(error, errorInfo) => {
                console.error('🚨 [HIL] Video player component crashed:', error);
                console.error('🚨 [HIL] Error info:', errorInfo);
                showSnackbar(`Video player crashed: ${error.message}`, 'error');
                setError(error.message);
                setTestRunning(false);
              }}
            >
              <SequentialVideoPlayer
                videoPlaylist={validatedVideos}
                sequenceId={sequenceId}
                maxLatencyMs={maxLatencyMs}
                onSequenceComplete={handleSequenceComplete}
                onError={(error) => {
              console.error('❌ [HIL] SequentialVideoPlayer error:', error);
              showSnackbar(error, 'error');
              setError(error);
            }}
            onVideoStarted={handleVideoStarted}
            onVideoEnded={(videoId, videoIndex, endTime) => {
              console.log('🎬 [HIL] Video ended callback:', { videoId, videoIndex, endTime });
            }}
            fullScreenMode={isFullScreen}
          />
            </VideoPlayerErrorBoundary>

            {/* Full-screen controls overlay */}
            {isFullScreen && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 16,
                  right: 16,
                  display: 'flex',
                  gap: 1,
                  backgroundColor: 'rgba(0,0,0,0.7)',
                  borderRadius: 1,
                  p: 1,
                  zIndex: 1000
                }}
              >
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={stopTest}
                  sx={{ color: 'white' }}
                >
                  Stop Test
                </Button>
              </Box>
            )}

            {/* Test progress indicator */}
            {isFullScreen && currentSession && (
              <Box
                sx={{
                  position: 'absolute',
                  bottom: 16,
                  left: 16,
                  right: 16,
                  backgroundColor: 'rgba(0,0,0,0.8)',
                  borderRadius: 1,
                  p: 2,
                  color: 'white',
                  zIndex: 1000
                }}
              >
                <Typography variant="h6">
                  HIL Test Running - Video {currentVideoIdx + 1} of {validatedVideos.length}
                </Typography>
                <Typography variant="body2">
                  Project: {selectedProject?.name} | Max Latency: {maxLatencyMs}ms
                </Typography>
                <Typography variant="body2">
                  Events: {detectionEvents.length} |
                  Passed: {detectionEvents.filter(e => e.outcome === 'pass').length} |
                  Failed: {detectionEvents.filter(e => e.outcome === 'fail_high_latency').length}
                </Typography>
                <LinearProgress sx={{ mt: 1, backgroundColor: 'rgba(255,255,255,0.3)' }} />
              </Box>
            )}
          </Box>
        )}

        {/* Start Test Confirmation Dialog */}
        <Dialog open={startTestDialog} onClose={() => setStartTestDialog(false)} maxWidth="md">
          <DialogTitle>Start HIL Test Execution</DialogTitle>
          <DialogContent>
            <Typography variant="body1" paragraph>
              Ready to start HIL test with the following configuration:
            </Typography>
            
            <Box sx={{ bgcolor: 'grey.50', p: 2, borderRadius: 1, mb: 2 }}>
              <Typography variant="body2">
                • <strong>Project:</strong> {selectedProject?.name}<br />
                • <strong>Videos:</strong> {videoPlaylist.length} validated videos<br />
                • <strong>Max Latency:</strong> {maxLatencyMs}ms<br />
                • <strong>LabJack Status:</strong> {labjackStatus.connected ? 'Connected' : 'Not Detected'}<br />
              </Typography>
            </Box>
            
            <Typography variant="body1">
              The test will immediately switch to full-screen mode and begin video playback 
              with precision timing capture (PRD requirement).
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setStartTestDialog(false)}>Cancel</Button>
            <Button
              onClick={validateGroundTruthAndProceed}
              variant="contained"
              disabled={!canStartTest().canStart}
              startIcon={<FullscreenIcon />}
            >
              Start Full-Screen Test
            </Button>
          </DialogActions>
        </Dialog>

        {/* Ground Truth Validation Warning Dialog (Issue #3) */}
        <GroundTruthValidationWarningDialog
          open={gtValidationDialog}
          onClose={handleCancelValidation}
          onStartAnyway={handleForceStartAnyway}
          validationData={gtValidationData}
          loading={gtValidationLoading}
        />

        {/* Snackbar */}
        <Snackbar
          open={snackbarOpen}
          autoHideDuration={4000}
          onClose={() => setSnackbarOpen(false)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            onClose={() => setSnackbarOpen(false)}
            severity={snackbarSeverity}
            sx={{ width: '100%' }}
          >
            {snackbarMessage}
          </Alert>
        </Snackbar>
      </Box>
    </div>
  );
};

export default HILTestExecutionPRD;
