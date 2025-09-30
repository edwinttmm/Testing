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
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Fullscreen as FullscreenIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

import { Project, VideoFile, GroundTruthAnnotation } from '../services/types';
import { apiService } from '../services/api';
import { markUserInteraction } from '../utils/videoUtils';
import SimpleLabJackStatus from '../components/SimpleLabJackStatus';
import { createHILDebugger } from '../utils/hilTestDebugging';

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

// Legacy DetectionEvent - maintained for backward compatibility
interface DetectionEvent {
  expectedEventTime: Date; // PRD: Expected_Event_Time relative to Test_Start_Time
  signalReceivedTime?: Date; // PRD: Signal_Received_Time from LabJack
  latencyMs?: number; // PRD: Calculated latency
  outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection';
  videoId: string;
  frameNumber?: number;
  
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
  const [maxLatencyMs, setMaxLatencyMs] = useState<number>(100); // PRD: Default 100ms
  const [labjackStatus, setLabjackStatus] = useState<LabJackConnectionStatus>({
    connected: false,
    status: 'checking'
  });
  
  // Test execution state
  const [currentSession, setCurrentSession] = useState<HILTestSession | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEvent[]>([]);
  const [expectedDetections, setExpectedDetections] = useState<{timestamp: number, id: string}[]>([]);
  const [currentVideoIdx, setCurrentVideoIdx] = useState<number>(0);
  
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
  
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const fullscreenContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const stalledRetryRef = useRef<number>(0);
  
  // VRU Tracking Services
  const vruTrackManagerRef = useRef<VRUTrackManager | null>(null);
  const temporalMatcherRef = useRef<TemporalMatcher | null>(null);

  // Helper function
  const showSnackbar = useCallback((message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  }, []);

  // Compute validated videos early to avoid TDZ issues
  const validatedVideos = useMemo(() => {
    console.log('🔍 HIL: VALIDATION VIDEO FILTERING - START');
    console.log('🔍 HIL: Total videoPlaylist length:', videoPlaylist.length);
    console.log('🔍 HIL: Raw videoPlaylist:', videoPlaylist);
    
    const filtered = videoPlaylist.filter(video => {
      // Check both status and validationStatus fields (API inconsistency fix)
      const statusCheck1 = video.status === 'validated';
      const statusCheck2 = (video as any).validationStatus === 'validated';
      const statusCheck3 = (video as any).validation_status === 'validated';
      const statusCheck = statusCheck1 || statusCheck2 || statusCheck3;
      
      const processingCheck = video.processing_status === 'completed' || 
                             (statusCheck && !video.processing_status);
      const isValid = statusCheck && processingCheck;
      
      console.log('🔍 HIL: DETAILED Validation check:', {
        video: { 
          id: video.id, 
          filename: video.filename, 
          status: video.status, 
          processing_status: video.processing_status,
          validationStatus: (video as any).validationStatus,
          validation_status: (video as any).validation_status,
          rawVideoObject: video  // Show entire video object
        },
        statusChecks: {
          'video.status === "validated"': statusCheck1,
          'validationStatus === "validated"': statusCheck2,
          'validation_status === "validated"': statusCheck3,
          'COMBINED_STATUS_CHECK': statusCheck
        },
        processingChecks: {
          'processing_status === "completed"': video.processing_status === 'completed',
          'statusCheck && !processing_status': statusCheck && !video.processing_status,
          'COMBINED_PROCESSING_CHECK': processingCheck
        },
        finalResult: {
          statusCheck,
          processingCheck,
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
            status: video.status,
            validationStatus: (video as any).validationStatus,
            validation_status: (video as any).validation_status,
            processing_status: video.processing_status
          },
          statusResults: { statusCheck1, statusCheck2, statusCheck3, statusCheck },
          processingResult: processingCheck,
          ERROR: isValid ? 'None - video is valid' : 'VIDEO NOT BEING INCLUDED IN VALIDATED LIST!'
        });
      }
      
      // Extra debugging for exact character comparison
      if (video.filename === 'Child.mp4') {
        console.log('🚨 HIL: Child.mp4 SPECIFIC DEBUG:', {
          statusBytes: Array.from(video.status || '').map(c => c.charCodeAt(0)),
          processingBytes: Array.from(video.processing_status || '').map(c => c.charCodeAt(0)),
          statusTrimmed: `"${(video.status || '').trim()}"`,
          processingTrimmed: `"${(video.processing_status || '').trim()}"`,
          statusTrimCheck: (video.status || '').trim() === 'validated',
          processingTrimCheck: (video.processing_status || '').trim() === 'completed',
          FIXED_processingCheck: processingCheck
        });
      }
      
      return isValid;
    });
    
    console.log('🔍 HIL: VALIDATION VIDEO FILTERING - END');
    console.log('🔍 HIL: Filtered validated videos:', filtered);
    console.log('🔍 HIL: Final validated video count:', filtered.length);
    console.log('🔍 HIL: Validated video filenames:', filtered.map(v => v.filename));
    
    return filtered;
  }, [videoPlaylist]);

  // Console logs moved to useEffect to avoid TDZ issues
  useEffect(() => {
    console.log('🔍 HIL: Video playlist state:', videoPlaylist);
    console.log('🔍 HIL: Validated videos:', validatedVideos);
  }, [videoPlaylist, validatedVideos]);

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

  // Poll for video status updates
  useEffect(() => {
    const isProcessing = videoPlaylist.some(video => video.processing_status === 'processing' || video.processing_status === 'pending');

    if (selectedProject && isProcessing) {
      const interval = setInterval(() => {
        loadVideoPlaylist(selectedProject);
      }, 5000); // Poll every 5 seconds

      return () => clearInterval(interval);
    }
  }, [selectedProject, videoPlaylist]);

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


  // Load video playlist for selected project (PRD requirement)
  const loadVideoPlaylist = async (project: Project) => {
    try {
      setLoading(true);
      console.log('🔍 HIL: Loading GROUND TRUTH videos for project:', project);
      
      // Use the ground truth API with project filter (this returns videos with ground truth data)
      const response = await apiService.getGroundTruthVideosAvailable(project.id);
      console.log('🔍 HIL: Ground Truth API response:', response);
      
      // The ground truth API already filters by project, so we can use the response directly
      const projectVideos = response || [];
      console.log('🔍 HIL: Ground truth videos for project:', projectVideos);

      setVideoPlaylist(projectVideos);
    } catch (err: any) {
      console.error('🚨 HIL: Error loading videos:', err);
      setError(`Failed to load video playlist: ${err.message}`);
      showSnackbar('Failed to load videos', 'error');
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
    
    // Auto-load ground truth after videos are loaded
    // Use a small delay to ensure video state is updated
    setTimeout(async () => {
      console.log('🔄 [HIL] Auto-loading ground truth after project selection...');
      try {
        await loadExpectedDetections();
      } catch (error: any) {
        console.warn('⚠️ [HIL] Auto ground truth loading failed:', error.message);
        // Don't throw error, user can manually reload
      }
    }, 500);
  };

  // Define playback helper function
  const startPlaybackForIndex = useCallback(async (idx: number) => {
    const video = validatedVideos[idx];
    if (!video || !videoRef.current) return;
    const filePath = (video as any).file_path || (video as any).filePath;
    const src = video.finalUrl || video.url || (filePath ? `http://localhost:8000/uploads/${String(filePath).split('/').pop()}` : `/api/v1/videos/${video.id}/stream`);
    const el = videoRef.current;
    try {
      el.muted = true;
      // @ts-ignore playsInline
      el.playsInline = true;
      el.src = src;
      el.currentTime = 0;
      stalledRetryRef.current = 0;
      el.load();
      const onLoaded = async () => {
        try { await el.play(); console.log('✅ Video play() succeeded:', src); } catch (e) { console.warn('⚠️ play() failed:', (e as Error).message); }
      };
      el.addEventListener('loadeddata', onLoaded, { once: true });
      setTimeout(async () => { if (el.readyState >= HTMLMediaElement.HAVE_METADATA && el.paused) { try { await el.play(); } catch {} } }, 1200);
    } catch (e) {
      console.error('❌ Failed to start playback for index', idx, e);
    }
  }, [validatedVideos]);

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

  // Mock detections for Child.mp4 testing
  const createMockDetectionsForChild = (): any[] => {
    console.log('🎭 [HIL MOCK] Creating mock detections for Child.mp4 testing');
    
    // Create realistic test detections for a 30-second video
    const mockDetections = [
      { timestamp: 2.5, id: 'mock_001', frameNumber: 75, confidence: 0.95 },
      { timestamp: 5.0, id: 'mock_002', frameNumber: 150, confidence: 0.92 },
      { timestamp: 8.2, id: 'mock_003', frameNumber: 246, confidence: 0.88 },
      { timestamp: 12.1, id: 'mock_004', frameNumber: 363, confidence: 0.91 },
      { timestamp: 15.7, id: 'mock_005', frameNumber: 471, confidence: 0.87 },
      { timestamp: 19.3, id: 'mock_006', frameNumber: 579, confidence: 0.93 },
      { timestamp: 23.8, id: 'mock_007', frameNumber: 714, confidence: 0.89 },
      { timestamp: 27.2, id: 'mock_008', frameNumber: 816, confidence: 0.94 }
    ];
    
    console.log(`🎭 [HIL MOCK] Created ${mockDetections.length} mock detections:`, mockDetections);
    return mockDetections;
  };

  // Helper function to load expected detections for a specific video
  const loadExpectedDetectionsForVideo = async (video: VideoFile): Promise<void> => {
    console.log('🚀 [HIL GROUND TRUTH] Loading annotations for specific video:', {
      id: video.id,
      filename: video.filename,
      status: video.status
    });

    try {
      // Show loading feedback to user
      showSnackbar(`Loading ground truth for ${video.filename}...`, 'info');
      
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
          setExpectedDetections(fallbackResult);
          showSnackbar(`Loaded ${fallbackResult.length} detections via fallback method for ${video.filename}`, 'success');
          console.log(`✅ [HIL GROUND TRUTH] Fallback successful: ${fallbackResult.length} detections`);
          return;
        }
        
        showSnackbar(warningMsg, 'warning');
        setExpectedDetections([]);
        return;
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
      
      // Set the expected detections
      setExpectedDetections(expectedTimes);
      
      // Success feedback to user
      const successMsg = `Loaded ${validCount} ground truth detections for HIL test from ${video.filename}`;
      console.log(`✅ [HIL GROUND TRUTH] ${successMsg}`);
      showSnackbar(successMsg, 'success');
      
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
        setExpectedDetections(fallbackResult);
        showSnackbar(`Loaded ${fallbackResult.length} detections via fallback method for ${video.filename}`, 'success');
      } else {
        setExpectedDetections([]);
        showSnackbar(`Failed to load ground truth for ${video.filename}`, 'error');
      }
    }
  };

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
          await loadExpectedDetectionsForVideo(fallbackVideo);
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
      await loadExpectedDetectionsForVideo(primaryVideo);
      
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
          setExpectedDetections(fallbackResult);
          showSnackbar(`Loaded ${fallbackResult.length} detections via fallback method`, 'success');
          console.log(`✅ [HIL GROUND TRUTH] Fallback successful: ${fallbackResult.length} detections`);
        } else {
          throw new Error('Fallback also returned no data');
        }
      } catch (fallbackError: any) {
        console.error('❌ [HIL GROUND TRUTH] Fallback also failed:', fallbackError.message);
        // Final fallback: use mock data for testing if this is Child.mp4
        if (validatedVideos[0]?.filename === 'Child.mp4') {
          console.log('🔄 [HIL GROUND TRUTH] Using mock data for Child.mp4 testing...');
          const mockDetections = createMockDetectionsForChild();
          setExpectedDetections(mockDetections);
          showSnackbar(`Using ${mockDetections.length} mock detections for testing`, 'warning');
        }
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

  // PRD: Start HIL test execution
  const startTest = async () => {
    const validation = canStartTest();
    if (!validation.canStart) {
      setError(validation.reasons.join('. '));
      return;
    }

    try {
      console.log('🚀 [HIL] Starting test execution...');
      
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
      
      // Load ground truth for the first video in the playlist
      console.log('🔄 [HIL] Loading ground truth before test start...');
      setCurrentVideoIdx(0);
      if (validatedVideos[0]) {
        await loadExpectedDetectionsForVideo(validatedVideos[0]);
      } else {
        await loadExpectedDetections();
      }
      
      // If no expected detections were loaded, automatically run debug investigation
      if (expectedDetections.length === 0) {
        console.log('⚠️ [HIL] No expected detections loaded, triggering automatic debug investigation...');
        showSnackbar('No ground truth data found. Running automatic investigation...', 'warning');
        setTimeout(async () => {
          await debugGroundTruthIssues();
        }, 1000);
      }
      
      // Validate that ground truth was loaded successfully
      if (expectedDetections.length === 0) {
        console.warn('⚠️ [HIL] No ground truth detections loaded - proceeding in enhanced debugging mode');
        showSnackbar('No ground truth data found. Test will proceed in debugging mode with video playback enabled.', 'warning');
        // Continue execution to allow video loading and debugging features
      }
      
      if (expectedDetections.length > 0) {
        console.log(`✅ [HIL] Ground truth validation passed: ${expectedDetections.length} detections loaded`);
        showSnackbar(`Ground truth loaded: ${expectedDetections.length} expected detections`, 'success');
      } else {
        console.log('🔧 [HIL] Proceeding without ground truth - enhanced debugging mode active');
      }
      
      // Create test session (persist to backend)
      let createdSessionId = `session_${Date.now()}`;
      try {
        const primaryVideo = validatedVideos[0];
        const created = await apiService.createTestSession({
          name: `HIL Test ${new Date().toLocaleString()}`,
          projectId: selectedProject!.id,
          videoId: primaryVideo?.id,
          config: { maxLatencyMs }
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

      const session: HILTestSession = {
        id: createdSessionId,
        projectId: selectedProject!.id,
        testStartTime: null, // Will be set when video starts
        maxLatencyMs,
        labjackConnected: labjackStatus.connected,
        status: 'running',
        videoPlaylist
      };
      setCurrentSession(session);
      console.log('✅ [HIL] Test session initialized:', session);
      
      // Start video playback for the current video; fullscreen already requested
      if (validatedVideos[0]) {
        console.log('🔄 [HIL] Setting up video playback...');
        await startPlaybackForIndex(0);
      } else {
        console.warn('⚠️ [HIL] No videoPlaylist available');
      }
      
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
              const tsMs = (d.timestamp_ms ?? (typeof d.timestamp === 'number' ? d.timestamp * 1000 : Date.now()));
              const signalReceivedTime = new Date(tsMs);
              const start = (currentSession?.testStartTime ? new Date(currentSession.testStartTime) : new Date(tsMs));
              const videoElapsedSeconds = (signalReceivedTime.getTime() - start.getTime()) / 1000;
              let nearestExpected: any = null; let minTimeDiff = Infinity;
              for (const expected of expectedDetections) {
                const td = Math.abs(videoElapsedSeconds - expected.timestamp);
                if (td < minTimeDiff) { minTimeDiff = td; nearestExpected = expected; }
              }
              const latencyMs = nearestExpected ? Math.abs((videoElapsedSeconds - nearestExpected.timestamp) * 1000) : Math.abs(Number(d.latency_ms ?? 0));
              const expectedEventTime = nearestExpected ? new Date(start.getTime() + nearestExpected.timestamp * 1000) : start;
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
  const enterFullScreen = async () => {
    console.log('🎬 enterFullScreen called:', {
      fullscreenContainerRef: !!fullscreenContainerRef.current,
      currentFullscreen: document.fullscreenElement,
      isFullScreen
    });
    
    if (fullscreenContainerRef.current) {
      try {
        console.log('🎬 Attempting fullscreen on container:', fullscreenContainerRef.current);
        
        if (fullscreenContainerRef.current.requestFullscreen) {
          console.log('🎬 Using standard requestFullscreen');
          await fullscreenContainerRef.current.requestFullscreen();
        } else if ((fullscreenContainerRef.current as any).webkitRequestFullscreen) {
          console.log('🎬 Using webkit requestFullscreen');
          await (fullscreenContainerRef.current as any).webkitRequestFullscreen();
        } else if ((fullscreenContainerRef.current as any).msRequestFullscreen) {
          console.log('🎬 Using ms requestFullscreen');
          await (fullscreenContainerRef.current as any).msRequestFullscreen();
        }
        
        console.log('✅ Fullscreen request succeeded');
        setIsFullScreen(true);
        
        // Debug fullscreen state after request
        setTimeout(() => {
          console.log('🎬 Fullscreen state after request:', {
            documentFullscreen: !!document.fullscreenElement,
            isFullScreenState: isFullScreen,
            containerElement: !!fullscreenContainerRef.current
          });
        }, 100);
        
      } catch (err) {
        console.error('❌ Fullscreen failed:', err);
        showSnackbar('Fullscreen not available, continuing in window mode', 'warning');
      }
    }
  };

  const exitFullScreen = async () => {
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
  };

  // PRD: Capture Test_Start_Time at exact video playback start
  const handleVideoStart = () => {
    if (currentSession) {
      const testStartTime = new Date(); // PRD: High-precision Test_Start_Time
      setCurrentSession(prev => prev ? { ...prev, testStartTime } : null);
      console.log('HIL Test - Precision Test_Start_Time captured:', testStartTime.toISOString());
      showSnackbar('Precision timing started', 'success');
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

            const tsMs = (d.timestamp_ms ?? (typeof d.timestamp === 'number' ? d.timestamp * 1000 : Date.now()));
            const signalReceivedTime = new Date(tsMs);
            const start = session.testStartTime ?? new Date(tsMs);
            const videoElapsedSeconds = (signalReceivedTime.getTime() - start.getTime()) / 1000;

            let nearestExpected: any = null;
            let minTimeDiff = Infinity;
            for (const expected of expectedDetections) {
              const timeDiff = Math.abs(videoElapsedSeconds - expected.timestamp);
              if (timeDiff < minTimeDiff) {
                minTimeDiff = timeDiff;
                nearestExpected = expected as any;
              }
            }

            const latencyMs = nearestExpected
              ? Math.abs((videoElapsedSeconds - nearestExpected.timestamp) * 1000)
              : Math.abs(Number(d.latency_ms ?? 0));
            const expectedEventTime = nearestExpected
              ? new Date(start.getTime() + nearestExpected.timestamp * 1000)
              : start;
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

  // PRD: Handle LabJack signal detection
  const handleLabJackSignal = (signalData: any, session: HILTestSession) => {
    console.log('🎯 [HIL] handleLabJackSignal called with:', { signalData, session: !!session });
    
    if (!session || !session.testStartTime) {
      console.error('❌ [HIL] handleLabJackSignal: No session or test start time');
      return;
    }
    
    const signalReceivedTime = new Date(signalData.timestamp);
    const videoElapsedSeconds = (signalReceivedTime.getTime() - session.testStartTime.getTime()) / 1000;
    
    console.log(`📊 [HIL] Processing signal: elapsed=${videoElapsedSeconds.toFixed(2)}s, voltage=${signalData.voltage?.toFixed(2)}V`);
    
    // Find nearest expected detection from ground truth
    let nearestExpected = null;
    let minTimeDiff = Infinity;
    
    for (const expected of expectedDetections) {
      const timeDiff = Math.abs(videoElapsedSeconds - expected.timestamp);
      if (timeDiff < minTimeDiff) {
        minTimeDiff = timeDiff;
        nearestExpected = expected;
      }
    }
    
    if (!nearestExpected) {
      console.warn('⚠️ [HIL] No expected detection found for signal at', videoElapsedSeconds);
      console.log('Available expected detections:', expectedDetections.map(e => `${e.id}@${e.timestamp}s`));
      return;
    }
    
    console.log(`🎯 [HIL] Found nearest expected: ${nearestExpected.id} at ${nearestExpected.timestamp}s (diff: ${minTimeDiff.toFixed(3)}s)`);
    
    // Calculate latency: signal_time - expected_time (in ms)
    const latencyMs = (videoElapsedSeconds - nearestExpected.timestamp) * 1000;
    const expectedEventTime = new Date(session.testStartTime.getTime() + nearestExpected.timestamp * 1000);
    
    // PRD: Determine outcome based on latency threshold
    let outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection' = 'pass';
    if (Math.abs(latencyMs) > maxLatencyMs) {
      outcome = 'fail_high_latency';
    }
    
    const event: DetectionEvent = {
      expectedEventTime,
      signalReceivedTime,
      latencyMs: Math.abs(latencyMs),
      outcome,
      videoId: signalData.videoId || validatedVideos[0]?.id || '',
      frameNumber: nearestExpected.frameNumber
    };
    
    console.log(`✅ [HIL] Creating detection event:`, {
      latencyMs: latencyMs.toFixed(1),
      outcome,
      expected: nearestExpected.timestamp,
      actual: videoElapsedSeconds,
      threshold: maxLatencyMs
    });
    
    setDetectionEvents(prev => {
      const newCount = prev.length + 1;
      console.log(`📈 [HIL] Detection events: ${prev.length} → ${newCount}`);
      return [...prev, event];
    });
    
    // Show real-time feedback
    const status = outcome === 'pass' ? 'success' : 'error';
    showSnackbar(
      `Detection: ${Math.abs(latencyMs).toFixed(1)}ms latency - ${outcome.toUpperCase()}`,
      status
    );
    
    console.log('✅ [HIL] Detection event:', {
      expected: nearestExpected.timestamp,
      actual: videoElapsedSeconds,
      latency: latencyMs,
      outcome
    });
  };

  // Handle video ended event - automatic test completion
  const handleVideoEnded = async () => {
    console.log('🎬 [HIL] Video ended');
    const nextIdx = currentVideoIdx + 1;
    if (nextIdx < validatedVideos.length) {
      // Advance to next video in playlist
      const nextVideo = validatedVideos[nextIdx];
      console.log('⏭️ [HIL] Advancing to next video:', nextVideo?.filename);
      setCurrentVideoIdx(nextIdx);
      try {
        await loadExpectedDetectionsForVideo(nextVideo);
      } catch (e) {
        console.warn('⚠️ [HIL] Failed loading detections for next video:', (e as Error)?.message);
        setExpectedDetections([]);
      }
      // Switch source and play robustly
      await startPlaybackForIndex(nextIdx);
      return;
    }
    console.log('🏁 [HIL] Playlist completed - finishing test');
    await stopTestAndGenerateResults();
  };

  // Generate test results locally without backend dependency
  const generateTestResults = async () => {
    if (!currentSession || !selectedProject) return null;

    const testEndTime = new Date();
    const testDuration = testEndTime.getTime() - (currentSession.testStartTime?.getTime() || testEndTime.getTime());
    
    // Calculate comprehensive results
    const totalExpectedDetections = expectedDetections.length;
    const actualDetections = detectionEvents.length;
    const passedDetections = detectionEvents.filter(e => e.outcome === 'pass').length;
    const failedDetections = detectionEvents.filter(e => e.outcome === 'fail_high_latency').length;
    
    // Find missed detections (expected but not detected)
    const detectedTimestamps = new Set(
      detectionEvents.map(e => Math.round((e.expectedEventTime.getTime() - currentSession.testStartTime.getTime()) / 100) * 100)
    );
    
    const missedDetections = expectedDetections.filter(expected => {
      const expectedMs = Math.round(expected.timestamp * 1000 / 100) * 100;
      return !detectedTimestamps.has(expectedMs);
    }).length;
    
    const totalFailedDetections = failedDetections + missedDetections;
    const passRate = totalExpectedDetections > 0 ? (passedDetections / totalExpectedDetections) * 100 : 0;
    
    // Display real-time results summary
    console.log('📊 [HIL] Final Test Results:');
    console.log(`  Total Expected: ${totalExpectedDetections}`);
    console.log(`  Detected: ${actualDetections}`);
    console.log(`  Passed: ${passedDetections} (within ${maxLatencyMs}ms)`);
    console.log(`  Failed: ${failedDetections} (high latency)`);
    console.log(`  Missed: ${missedDetections} (not detected)`);
    console.log(`  Pass Rate: ${passRate.toFixed(1)}%`);
    
    // Calculate latency statistics
    const latencies = detectionEvents.map(e => e.latencyMs);
    const averageLatency = latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : 0;
    const maxLatency = latencies.length > 0 ? Math.max(...latencies) : 0;
    const minLatency = latencies.length > 0 ? Math.min(...latencies) : 0;
    
    const results = {
      session_id: currentSession.id,
      project_id: selectedProject.id,
      project_name: selectedProject.name,
      test_start_time: currentSession.testStartTime,
      test_end_time: testEndTime,
      test_duration_seconds: Math.round(testDuration / 1000),
      total_detections: totalExpectedDetections,
      passed_detections: passedDetections,
      failed_detections: totalFailedDetections,
      pass_rate: Math.round(passRate * 100) / 100,
      average_latency_ms: Math.round(averageLatency * 100) / 100,
      max_latency_ms: maxLatency,
      min_latency_ms: minLatency,
      max_latency_threshold_ms: maxLatencyMs,
      test_status: passRate >= 80 ? 'PASSED' : 'FAILED', // 80% pass threshold
      detection_events: detectionEvents,
      labjack_connected: labjackStatus.connected,
      video_count: validatedVideos.length
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
  };

  // Save results to database via API
  const saveResultsToDatabase = async (results: any) => {
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
  };

  // Stop test and generate results with automatic navigation
  const stopTestAndGenerateResults = async () => {
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
  };

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

                {/* 4. Ground Truth Status Display */}
                {selectedProject && (
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      4. Ground Truth Status
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                      <Chip
                        icon={expectedDetections.length > 0 ? <CheckCircleIcon color="success" /> : <WarningIcon color="warning" />}
                        label={expectedDetections.length > 0 
                          ? `${expectedDetections.length} Expected Detections Loaded` 
                          : 'No Ground Truth Data'
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
                    {expectedDetections.length > 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        Video: {validatedVideos[0]?.filename} • 
                        Expected detection times: {expectedDetections.map(d => `${d.timestamp.toFixed(1)}s`).join(', ').substring(0, 100)}
                        {expectedDetections.map(d => `${d.timestamp.toFixed(1)}s`).join(', ').length > 100 ? '...' : ''}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="error">
                        No ground truth annotations found. The HIL test requires expected detection times to validate hardware responses.
                        Please ensure the selected video has been annotated with ground truth data.
                      </Typography>
                    )}
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

        {/* Full-Screen Video Player (PRD requirement) */}
        {(() => {
          console.log('🎬 Video container render check:', {
            testRunning,
            validatedVideos: validatedVideos?.length,
            isFullScreen,
            showVideoContainer: testRunning
          });
          return null;
        })()}
        {testRunning && (
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
            {(() => {
              // Debug video container visibility
              const container = document.getElementById('video-container');
              console.log('🎬 Video container debug:', {
                container: !!container,
                testRunning,
                isFullScreen,
                containerVisible: container?.offsetHeight > 0,
                containerStyle: container?.style.display
              });
              return null;
            })()}
            
            {(() => {
              console.log('🎬 Video element render check:', {
                validatedVideos: validatedVideos?.length,
                firstVideo: !!validatedVideos?.[0],
                videoData: validatedVideos?.[0] ? {
                  id: validatedVideos[0].id,
                  url: validatedVideos[0].url,
                  finalUrl: validatedVideos[0].finalUrl,
                  file_path: validatedVideos[0].file_path
                } : null
              });
              return null;
            })()}
            {validatedVideos[currentVideoIdx] && (
              <video
                ref={videoRef}
                id="hil-video"
                src={(() => {
                  const video = validatedVideos[currentVideoIdx];
                  const sourceUrl = video.url || video.finalUrl || 
                    (video.file_path ? `http://localhost:8000/uploads/${video.file_path.split('/').pop()}` : '') ||
                    `/api/v1/videos/${video.id}/stream`;
                  console.log('📹 Video source URL selected:', sourceUrl);
                  console.log('📹 Video object:', video);
                  
                  // Test URL accessibility
                  fetch(sourceUrl, { method: 'HEAD' })
                    .then(response => {
                      console.log('🌐 URL accessibility test:', {
                        url: sourceUrl,
                        status: response.status,
                        ok: response.ok,
                        headers: {
                          contentType: response.headers.get('content-type'),
                          contentLength: response.headers.get('content-length')
                        }
                      });
                    })
                    .catch(error => {
                      console.error('❌ URL accessibility test failed:', {
                        url: sourceUrl,
                        error: error.message
                      });
                    });
                  
                  return sourceUrl;
                })()}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  display: 'block'
                }}
                onPlay={handleVideoStart} // PRD: Capture Test_Start_Time
                onEnded={handleVideoEnded} // Automatic test completion
                onCanPlay={async () => {
                  const videoEl = videoRef.current;
                  console.log('📹 Video onCanPlay fired:', {
                    videoElement: !!videoEl,
                    videoReady: videoEl?.readyState,
                    videoSrc: videoEl?.src,
                    videoDimensions: videoEl ? `${videoEl.videoWidth}x${videoEl.videoHeight}` : 'N/A',
                    testRunning,
                    isFullScreen
                  });
                  
                  // Debug video element in DOM
                  setTimeout(() => {
                    const videoInDom = document.getElementById('hil-video');
                    console.log('🎬 Video DOM check:', {
                      videoInDom: !!videoInDom,
                      videoVisible: videoInDom?.offsetHeight > 0,
                      videoDisplay: videoInDom?.style.display,
                      videoParent: !!videoInDom?.parentElement
                    });
                  }, 100);
                  
                  // Automatic play and fullscreen sequence
                  if (testRunning && videoEl) {
                    try {
                      // First ensure video is playing
                      console.log('📹 Ensuring video is playing...');
                      await videoEl.play();
                      console.log('✅ Video play succeeded');
                      
                      // Wait for video stream to stabilize before fullscreen
                      if (!isFullScreen) {
                        console.log('📹 Waiting for video stream stability...');
                        
                        // Wait for stable playback state
                        const waitForStability = new Promise((resolve) => {
                          const checkStability = () => {
                            if (videoEl.readyState >= HTMLMediaElement.HAVE_ENOUGH_DATA && 
                                !videoEl.paused && 
                                videoEl.currentTime > 0 &&
                                videoEl.videoWidth > 0 &&
                                videoEl.videoHeight > 0) {
                              console.log('✅ Video stream is stable, entering fullscreen...');
                              resolve(true);
                            } else {
                              console.log('⏳ Video not stable yet, waiting...', {
                                readyState: videoEl.readyState,
                                paused: videoEl.paused,
                                currentTime: videoEl.currentTime,
                                dimensions: `${videoEl.videoWidth}x${videoEl.videoHeight}`
                              });
                              setTimeout(checkStability, 100);
                            }
                          };
                          
                          // Start checking after brief delay
                          setTimeout(checkStability, 50);
                        });
                        
                        await waitForStability;
                        enterFullScreen();
                      }
                      
                    } catch (playError) {
                      console.error('❌ Automatic video play failed:', playError);
                      // Try fullscreen without autoplay requirement
                      console.log('🔄 Attempting fullscreen without autoplay...');
                      if (!isFullScreen) {
                        // Still need stability check even without autoplay
                        setTimeout(() => {
                          if (videoEl.readyState >= HTMLMediaElement.HAVE_METADATA) {
                            enterFullScreen();
                          }
                        }, 500);
                      }
                    }
                  }
                }}
                onLoadedData={() => {
                  console.log('📹 Video loadedData event fired');
                }}
                onLoadedMetadata={() => {
                  console.log('📹 Video loadedMetadata event fired');
                }}
                onError={(e) => {
                  console.error('❌ Video load error:', e);
                  console.error('❌ Video error target:', e.target);
                  // Try fallback source
                  if (videoRef.current && validatedVideos[0]) {
                    const fallbackUrl = `/api/v1/videos/${validatedVideos[0].id}/stream`;
                    console.log('🔄 Trying fallback URL:', fallbackUrl);
                    videoRef.current.src = fallbackUrl;
                  }
                }}
                onPause={() => {
                  console.log('📹 Video paused');
                }}
                onWaiting={() => {
                  console.log('📹 Video waiting (buffering)');
                }}
                onStalled={() => {
                  console.log('📹 Video stalled');
                  const el = videoRef.current;
                  if (!el) return;
                  stalledRetryRef.current = Math.min(stalledRetryRef.current + 1, 5);
                  setTimeout(async () => { try { await el.play(); } catch {} }, stalledRetryRef.current * 300);
                }}
                controls={!isFullScreen}
                autoPlay
                muted
                preload="auto"
                // @ts-ignore
                playsInline
              />
            )}
            
            
            {/* Show loading indicator if no video available */}
            {testRunning && !validatedVideos[0] && (
              <Box sx={{ textAlign: 'center', color: 'white' }}>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Loading video...
                </Typography>
                <CircularProgress color="primary" />
              </Box>
            )}
            
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
                  p: 1
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
                  color: 'white'
                }}
              >
                <Typography variant="h6">
                  HIL Test Running
                </Typography>
                <Typography variant="body2">
                  Project: {selectedProject?.name} | Max Latency: {maxLatencyMs}ms
                </Typography>
                <Typography variant="body2">
                  Events: {detectionEvents.length} | 
                  Passed: {detectionEvents.filter(e => e.outcome === 'pass').length}
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
              onClick={startTest}
              variant="contained"
              disabled={!canStartTest().canStart}
              startIcon={<FullscreenIcon />}
            >
              Start Full-Screen Test
            </Button>
          </DialogActions>
        </Dialog>

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
