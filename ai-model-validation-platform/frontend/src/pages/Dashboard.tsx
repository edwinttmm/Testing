import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Skeleton,
  Alert,
  Chip,
} from '@mui/material';
import {
  FolderOpen,
  VideoLibrary,
  Assessment,
  TrendingUp,
} from '@mui/icons-material';
import { getDashboardStats } from '../services/api';
import { getTestSessions } from '../services/api';
import { EnhancedDashboardStats, TestSession, VideoFile, Project } from '../services/types';
import AccessibleStatCard from '../components/ui/AccessibleStatCard';
import AccessibleCard, { AccessibleProgressItem, AccessibleSessionItem } from '../components/ui/AccessibleCard';
import { useWebSocket } from '../hooks/useWebSocket';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<EnhancedDashboardStats | null>(null);
  const [recentSessions, setRecentSessions] = useState<TestSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [, setRealtimeUpdates] = useState(0);
  const lastStatsRef = useRef<EnhancedDashboardStats | null>(null);

  // WebSocket connection for real-time updates
  const { 
    isConnected, 
    on: subscribe, 
    emit
  } = useWebSocket();

  const formatTimeAgo = (dateString: string | null | undefined) => {
    if (!dateString) return 'Unknown time';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hour${Math.floor(diffInMinutes / 60) > 1 ? 's' : ''} ago`;
    return `${Math.floor(diffInMinutes / 1440)} day${Math.floor(diffInMinutes / 1440) > 1 ? 's' : ''} ago`;
  };

  // Real-time update handlers
  const updateStatsSafely = useCallback((updater: (prevStats: EnhancedDashboardStats) => EnhancedDashboardStats) => {
    setStats(prevStats => {
      if (!prevStats) return prevStats;
      const newStats = updater(prevStats);
      lastStatsRef.current = newStats;
      return newStats;
    });
  }, []);

  const handleVideoUploaded = useCallback((data: VideoFile) => {
    console.log('📹 Video uploaded event received:', data);
    updateStatsSafely(prevStats => ({
      ...prevStats,
      video_count: prevStats.video_count + 1
    }));
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const handleProjectCreated = useCallback((data: Project) => {
    console.log('📁 Project created event received:', data);
    updateStatsSafely(prevStats => ({
      ...prevStats,
      project_count: prevStats.project_count + 1
    }));
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const handleTestCompleted = useCallback((data: TestSession) => {
    console.log('🧪 Test completed event received:', data);
    updateStatsSafely(prevStats => ({
      ...prevStats,
      test_session_count: prevStats.test_session_count + 1,
      average_accuracy: data.metrics?.accuracy || prevStats.average_accuracy,
      active_tests: Math.max(0, prevStats.active_tests - 1)
    }));

    // Add to recent sessions
    setRecentSessions(prevSessions => {
      const newSession = {
        ...data,
        createdAt: data.completedAt || new Date().toISOString()
      };
      const updatedSessions = [newSession, ...prevSessions.slice(0, 3)];
      return updatedSessions;
    });
    
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const handleTestStarted = useCallback((data: TestSession) => {
    console.log('🚀 Test started event received:', data);
    updateStatsSafely(prevStats => ({
      ...prevStats,
      active_tests: prevStats.active_tests + 1
    }));
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const handleDetectionEvent = useCallback((data: any) => {
    console.log('🎯 Detection event received:', data);
    updateStatsSafely(prevStats => ({
      ...prevStats,
      detection_event_count: prevStats.detection_event_count + 1,
      total_detections: prevStats.total_detections + 1,
      signal_processing_metrics: {
        ...prevStats.signal_processing_metrics,
        totalSignals: prevStats.signal_processing_metrics.totalSignals + 1
      }
    }));
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const handleAnnotationCreated = useCallback((data: any) => {
    console.log('📝 Annotation created event received:', data);
    updateStatsSafely(prevStats => ({
      ...prevStats,
      detection_event_count: prevStats.detection_event_count + 1,
      total_detections: prevStats.total_detections + 1
    }));
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const handleAnnotationValidated = useCallback((data: any) => {
    console.log('✅ Annotation validated event received:', data);
    // Don't increment counts for validation, just update quality metrics
    setRealtimeUpdates(prev => prev + 1);
  }, []);

  const handleSignalProcessed = useCallback((data: any) => {
    console.log('📡 Signal processed event received:', data);
    updateStatsSafely(prevStats => {
      const totalSignals = prevStats.signal_processing_metrics.totalSignals + 1;
      const successfulSignals = data.success 
        ? prevStats.signal_processing_metrics.totalSignals * (prevStats.signal_processing_metrics.successRate / 100) + 1
        : prevStats.signal_processing_metrics.totalSignals * (prevStats.signal_processing_metrics.successRate / 100);
      
      return {
        ...prevStats,
        signal_processing_metrics: {
          totalSignals,
          successRate: totalSignals > 0 ? (successfulSignals / totalSignals) * 100 : 0,
          avgProcessingTime: data.processingTime || prevStats.signal_processing_metrics.avgProcessingTime
        }
      };
    });
    setRealtimeUpdates(prev => prev + 1);
  }, [updateStatsSafely]);

  const fetchDashboardStats = useCallback(async () => {
    try {
      setLoading(true);
      
      // Fetch dashboard stats and recent test sessions with individual error handling
      const [statsResult, sessionsResult] = await Promise.allSettled([
        getDashboardStats(),
        getTestSessions()
      ]);
      
      // Handle stats data
      if (statsResult.status === 'fulfilled') {
        // Backend already returns EnhancedDashboardStats
        setStats(statsResult.value);
      } else {
        const errorMsg = statsResult.reason instanceof Error 
          ? statsResult.reason.message 
          : 'Backend connection failed';
        console.error('Failed to fetch dashboard stats:', errorMsg, statsResult.reason);
        setStats({
          project_count: 0,
          video_count: 0,
          test_session_count: 0,
          detection_event_count: 0,
          confidence_intervals: {
            precision: [0, 0],
            recall: [0, 0],
            f1_score: [0, 0]
          },
          trend_analysis: {
            accuracy: 'stable' as const,
            detectionRate: 'stable' as const,
            performance: 'stable' as const
          },
          signal_processing_metrics: {
            totalSignals: 0,
            successRate: 0,
            avgProcessingTime: 0
          },
          average_accuracy: 0,
          active_tests: 0,
          total_detections: 0
        });
      }
      
      // Handle sessions data
      if (sessionsResult.status === 'fulfilled' && Array.isArray(sessionsResult.value)) {
        const recentSessionsData = sessionsResult.value
          .sort((a, b) => new Date(b.createdAt || '').getTime() - new Date(a.createdAt || '').getTime())
          .slice(0, 4);
        setRecentSessions(recentSessionsData);
      } else if (sessionsResult.status === 'rejected') {
        const errorMsg = sessionsResult.reason instanceof Error 
          ? sessionsResult.reason.message 
          : 'Backend connection failed';
        console.error('Failed to fetch test sessions:', errorMsg, sessionsResult.reason);
        setRecentSessions([]);
      }
      
      // Only set error if both requests failed
      if (statsResult.status === 'rejected' && sessionsResult.status === 'rejected') {
        setError('Failed to load dashboard data');
      } else if (statsResult.status === 'rejected' || sessionsResult.status === 'rejected') {
        setError('Some dashboard data may be incomplete');
      } else {
        setError(null);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError('Failed to load dashboard statistics');
      // Fallback data for demo purposes
      setStats({
        project_count: 0,
        video_count: 0,
        test_session_count: 0,
        detection_event_count: 0,
        confidence_intervals: {
          precision: [0, 0],
          recall: [0, 0],
          f1_score: [0, 0]
        },
        trend_analysis: {
          accuracy: 'stable' as const,
          detectionRate: 'stable' as const,
          performance: 'stable' as const
        },
        signal_processing_metrics: {
          totalSignals: 0,
          successRate: 0,
          avgProcessingTime: 0
        },
        average_accuracy: 0,
        active_tests: 0,
        total_detections: 0
      });
      setRecentSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket subscriptions for real-time updates
  useEffect(() => {
    if (!isConnected) {
      console.log('WebSocket not connected, skipping subscriptions');
      return;
    }

    console.log('🔗 Setting up Dashboard WebSocket subscriptions');

    // Subscribe to various real-time events
    const unsubscribeVideo = subscribe('video_uploaded', handleVideoUploaded);
    const unsubscribeVideoComplete = subscribe('video_processed', handleVideoUploaded);
    const unsubscribeProject = subscribe('project_created', handleProjectCreated);
    const unsubscribeProjectUpdated = subscribe('project_updated', handleProjectCreated);
    const unsubscribeTestComplete = subscribe('test_completed', handleTestCompleted);
    const unsubscribeTestSessionComplete = subscribe('test_session_completed', handleTestCompleted);
    const unsubscribeTestStart = subscribe('test_started', handleTestStarted);
    const unsubscribeTestSessionStart = subscribe('test_session_started', handleTestStarted);
    const unsubscribeDetection = subscribe('detection_event', handleDetectionEvent);
    const unsubscribeDetectionResult = subscribe('detection_result', handleDetectionEvent);
    const unsubscribeAnnotationCreated = subscribe('annotation_created', handleAnnotationCreated);
    const unsubscribeAnnotationValidated = subscribe('annotation_validated', handleAnnotationValidated);
    const unsubscribeAnnotationUpdated = subscribe('annotation_updated', handleAnnotationCreated);
    const unsubscribeGroundTruthGenerated = subscribe('ground_truth_generated', handleDetectionEvent);
    const unsubscribeSignal = subscribe('signal_processed', handleSignalProcessed);
    const unsubscribeSignalProcessing = subscribe('signal_processing_result', handleSignalProcessed);

    // Request dashboard updates when connected
    emit('subscribe_dashboard_updates', { 
      clientId: 'dashboard',
      events: [
        'video_uploaded', 'video_processed',
        'project_created', 'project_updated', 
        'test_completed', 'test_session_completed',
        'test_started', 'test_session_started',
        'detection_event', 'detection_result',
        'annotation_created', 'annotation_updated', 'annotation_validated',
        'ground_truth_generated',
        'signal_processed', 'signal_processing_result'
      ]
    });

    // Cleanup subscriptions
    return () => {
      console.log('🧹 Cleaning up Dashboard WebSocket subscriptions');
      unsubscribeVideo?.();
      unsubscribeVideoComplete?.();
      unsubscribeProject?.();
      unsubscribeProjectUpdated?.();
      unsubscribeTestComplete?.();
      unsubscribeTestSessionComplete?.();
      unsubscribeTestStart?.();
      unsubscribeTestSessionStart?.();
      unsubscribeDetection?.();
      unsubscribeDetectionResult?.();
      unsubscribeAnnotationCreated?.();
      unsubscribeAnnotationValidated?.();
      unsubscribeAnnotationUpdated?.();
      unsubscribeGroundTruthGenerated?.();
      unsubscribeSignal?.();
      unsubscribeSignalProcessing?.();
      
      // Unsubscribe from dashboard updates
      emit('unsubscribe_dashboard_updates', { clientId: 'dashboard' });
    };
  }, [
    isConnected, 
    subscribe, 
    emit,
    handleVideoUploaded,
    handleProjectCreated,
    handleTestCompleted,
    handleTestStarted,
    handleDetectionEvent,
    handleAnnotationCreated,
    handleAnnotationValidated,
    handleSignalProcessed
  ]);

  useEffect(() => {
    fetchDashboardStats();
  }, [fetchDashboardStats]);

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
          {[1, 2, 3, 4].map((i) => (
            <Box key={i} sx={{ minWidth: 250, flex: 1 }}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Skeleton variant="circular" width={40} height={40} sx={{ mr: 2 }} />
                    <Box>
                      <Skeleton variant="text" width={60} height={40} />
                      <Skeleton variant="text" width={120} height={20} />
                      <Skeleton variant="text" width={100} height={16} />
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          <Box sx={{ minWidth: 400, flex: 1 }}>
            <Card>
              <CardContent>
                <Skeleton variant="text" width={200} height={32} />
                <Box sx={{ mt: 2 }}>
                  {[1, 2, 3, 4].map((i) => (
                    <Box key={i} sx={{ mb: 2 }}>
                      <Skeleton variant="text" width="100%" height={24} />
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Box>
          <Box sx={{ minWidth: 400, flex: 1 }}>
            <Card>
              <CardContent>
                <Skeleton variant="text" width={150} height={32} />
                <Box sx={{ mt: 2 }}>
                  {[1, 2, 3].map((i) => (
                    <Box key={i} sx={{ mb: 2 }}>
                      <Skeleton variant="text" width="100%" height={20} />
                      <Skeleton variant="rectangular" width="100%" height={4} sx={{ mt: 1 }} />
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Box>
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        
        {/* System Status */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            icon={<Assessment />}
            label="HTTP-Only Mode"
            color="info"
            variant="filled"
            size="small"
          />
          {stats && (
            <Chip
              label={`${stats.test_session_count || 0} tests completed`}
              color="success"
              variant="outlined"
              size="small"
            />
          )}
        </Box>
      </Box>
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
        {error && (
          <Alert severity="warning" sx={{ mb: 3, width: '100%' }}>
            {error} - Showing latest available data
          </Alert>
        )}
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Active Projects"
            value={stats?.project_count || 0}
            icon={<FolderOpen />}
            color="primary"
            subtitle={stats?.project_count ? `${stats.project_count} total projects` : 'No projects yet'}
            loading={loading}
            ariaLabel={`Active Projects: ${stats?.project_count || 0} total projects`}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Videos Processed"
            value={stats?.video_count || 0}
            icon={<VideoLibrary />}
            color="success"
            subtitle={stats?.video_count ? `${stats.video_count} videos uploaded` : 'No videos yet'}
            loading={loading}
            ariaLabel={`Videos Processed: ${stats?.video_count || 0} videos uploaded`}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Tests Completed"
            value={stats?.test_session_count || 0}
            icon={<Assessment />}
            color="info"
            subtitle={stats?.test_session_count ? `${stats.test_session_count} test sessions` : 'No tests yet'}
            loading={loading}
            ariaLabel={`Tests Completed: ${stats?.test_session_count || 0} test sessions`}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Detection Accuracy"
            value={`${stats?.average_accuracy || 0}%`}
            icon={<TrendingUp />}
            color="warning"
            subtitle={stats?.confidence_intervals ? `CI: ${stats.confidence_intervals.precision[0]}%-${stats.confidence_intervals.precision[1]}%` : "Average across all tests"}
            loading={loading}
            ariaLabel={`Detection Accuracy: ${stats?.average_accuracy || 0}% average across all tests`}
            trend={{
              value: 2.3,
              direction: stats?.trend_analysis?.accuracy === 'improving' ? 'up' : stats?.trend_analysis?.accuracy === 'declining' ? 'down' : 'up'
            }}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Signal Processing"
            value={`${Math.round(stats?.signal_processing_metrics?.successRate || 0)}%`}
            icon={<Assessment />}
            color="success"
            subtitle={`${stats?.signal_processing_metrics?.totalSignals || 0} signals processed`}
            loading={loading}
            ariaLabel={`Signal Processing: ${stats?.signal_processing_metrics?.successRate || 0}% success rate`}
            trend={{
              value: 2.1,
              direction: stats?.trend_analysis?.performance === 'improving' ? 'up' : 'up'
            }}
          />
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        <Box sx={{ minWidth: 400, flex: 1 }}>
          <AccessibleCard
            title="Recent Test Sessions"
            loading={loading}
            ariaLabel="Recent test sessions list"
            role="region"
          >
            <Box role="list" aria-label="Recent test sessions">
              {recentSessions.length > 0 ? (
                recentSessions.map((session, index) => (
                  <AccessibleSessionItem
                    key={session.id || index}
                    sessionNumber={index + 1}
                    type={session.name || `Test Session ${index + 1}`}
                    timeAgo={formatTimeAgo(session.createdAt || session.completedAt)}
                    accuracy={session.metrics?.accuracy || 0}
                  />
                ))
              ) : (
                <Box sx={{ textAlign: 'center', py: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    No recent test sessions
                  </Typography>
                </Box>
              )}
            </Box>
          </AccessibleCard>
        </Box>

        <Box sx={{ minWidth: 400, flex: 1 }}>
          <AccessibleCard
            title="System Status 🟢 ACTIVE"
            loading={loading}
            ariaLabel="System performance metrics and connection status"
            role="region"
          >
            <Box role="group" aria-label="System performance indicators">
              <AccessibleProgressItem
                label="HTTP Detection Service ✅"
                value={100}
                color="success"
                ariaLabel="HTTP detection service: Available"
              />
              <AccessibleProgressItem
                label="Active Test Sessions"
                value={Math.min((stats?.active_tests || 0) * 20, 100)}
                color="success"
                ariaLabel={`Active test sessions: ${stats?.active_tests || 0}`}
              />
              <AccessibleProgressItem
                label="Total Projects"
                value={Math.min((stats?.project_count || 0) * 10, 100)}
                color="info"
                ariaLabel={`Total projects: ${stats?.project_count || 0}`}
              />
              <AccessibleProgressItem
                label="Videos Processed"
                value={Math.min((stats?.video_count || 0) * 5, 100)}
                color="primary"
                ariaLabel={`Videos processed: ${stats?.video_count || 0}`}
              />
              <AccessibleProgressItem
                label="Signal Processing Rate"
                value={Math.round(stats?.signal_processing_metrics?.successRate || 0)}
                color={stats?.signal_processing_metrics?.successRate && stats.signal_processing_metrics.successRate > 80 ? "success" : "warning"}
                ariaLabel={`Signal processing success rate: ${stats?.signal_processing_metrics?.successRate || 0}%`}
              />
            </Box>
          </AccessibleCard>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;