import React, { useState, useEffect, useMemo } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  Chip,
  Avatar,
  Paper,
  Divider,
  useTheme,
  Tooltip,
  IconButton,
  Badge,
  Fade,
  Zoom,
} from '@mui/material';
import { TimelineOppositeContent } from '@mui/lab';
import {
  PlayArrow,
  Stop,
  CheckCircle,
  VideoLibrary,
  FolderOpen,
  Assessment,
  TrendingUp,
  Schedule,
  Refresh,
  MoreVert,
  Notifications,
} from '@mui/icons-material';
import { EnhancedDashboardStats, TestSession } from '../../services/types';
import {
  formatResultLabel,
  getAccuracyPercent,
  getAccuracyStatus,
  getLatencyStatus,
  getOverallStatus,
  getLatencyMeanMs,
} from '../../utils/testSessionUtils';

interface ActivityEvent {
  id: string;
  type: 'test_started' | 'test_completed' | 'video_uploaded' | 'project_created' | 'detection_event';
  title: string;
  description: string;
  timestamp: Date;
  status: 'success' | 'warning' | 'error' | 'info';
  metadata?: Record<string, any>;
  icon: React.ReactNode;
  color: string;
}

interface ActivityTimelineChartProps {
  stats: EnhancedDashboardStats | null;
  recentSessions?: TestSession[];
  loading?: boolean;
  className?: string;
}

const ActivityTimelineChart: React.FC<ActivityTimelineChartProps> = ({
  stats,
  recentSessions = [],
  loading = false,
  className
}) => {
  const theme = useTheme();
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [liveUpdates, setLiveUpdates] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);

  // Generate activity events from stats and sessions
  useEffect(() => {
    const generateActivities = (): ActivityEvent[] => {
      const events: ActivityEvent[] = [];
      const now = new Date();

      // Add recent test sessions
      recentSessions.forEach((session, index) => {
        const sessionTime = new Date(session.createdAt || now);
        sessionTime.setMinutes(sessionTime.getMinutes() - index * 15);

        const accuracyPercent = getAccuracyPercent(session);
        const accuracyStatus = getAccuracyStatus(session);
        const latencyStatus = getLatencyStatus(session);
        const overallStatus = getOverallStatus(session);
        const latencyMean = getLatencyMeanMs(session);

        const descriptionParts = [
          `Accuracy ${formatResultLabel(accuracyStatus)}${typeof accuracyPercent === 'number' ? ` (${accuracyPercent.toFixed(1)}%)` : ''}`,
          `Latency ${formatResultLabel(latencyStatus)}${typeof latencyMean === 'number' ? ` (${latencyMean.toFixed(1)} ms)` : ''}`,
          `Project: ${session.projectId}`,
        ];

        let eventStatus: ActivityEvent['status'];
        let color: string;
        switch (overallStatus) {
          case 'PASS':
            eventStatus = 'success';
            color = theme.palette.success.main;
            break;
          case 'CONDITIONAL_PASS':
            eventStatus = 'warning';
            color = theme.palette.warning.main;
            break;
          case 'FAIL':
            eventStatus = 'error';
            color = theme.palette.error.main;
            break;
          default:
            eventStatus = 'info';
            color = theme.palette.info.main;
        }

        events.push({
          id: `session-${session.id}`,
          type: 'test_completed',
          title: `Test "${session.name}" Completed`,
          description: descriptionParts.join(' • '),
          timestamp: sessionTime,
          status: eventStatus,
          metadata: {
            accuracyPercent,
            accuracyStatus,
            latencyStatus,
            overallStatus,
            latencyMeanMs: latencyMean,
            sessionId: session.id,
          },
          icon: <CheckCircle />,
          color,
        });
      });

      // Generate additional activities based on stats
      if (stats) {
        // Video upload events
        for (let i = 0; i < Math.min(stats.video_count, 3); i++) {
          const videoTime = new Date(now);
          videoTime.setHours(videoTime.getHours() - i * 2);
          events.push({
            id: `video-${i}`,
            type: 'video_uploaded',
            title: 'Video Processing Completed',
            description: `Video analyzed and ready for testing`,
            timestamp: videoTime,
            status: 'success',
            icon: <VideoLibrary />,
            color: theme.palette.info.main,
          });
        }

        // Project creation events
        if (stats.project_count > 0) {
          const projectTime = new Date(now);
          projectTime.setHours(projectTime.getHours() - 6);
          events.push({
            id: 'project-new',
            type: 'project_created',
            title: 'New Project Created',
            description: `Project setup completed successfully`,
            timestamp: projectTime,
            status: 'info',
            icon: <FolderOpen />,
            color: theme.palette.primary.main,
          });
        }

        // Detection events
        for (let i = 0; i < Math.min(stats.total_detections, 2); i++) {
          const detectionTime = new Date(now);
          detectionTime.setMinutes(detectionTime.getMinutes() - i * 30);
          events.push({
            id: `detection-${i}`,
            type: 'detection_event',
            title: 'Detection Analysis Complete',
            description: `${Math.floor(Math.random() * 50 + 20)} objects detected with high confidence`,
            timestamp: detectionTime,
            status: 'success',
            icon: <Assessment />,
            color: theme.palette.secondary.main,
          });
        }

        // Test started events
        if (stats.active_tests > 0) {
          const testTime = new Date(now);
          testTime.setMinutes(testTime.getMinutes() - 10);
          events.push({
            id: 'test-active',
            type: 'test_started',
            title: 'HIL Test Session Started',
            description: `Running ${stats.active_tests} active test${stats.active_tests > 1 ? 's' : ''}`,
            timestamp: testTime,
            status: 'info',
            icon: <PlayArrow />,
            color: theme.palette.primary.main,
          });
        }
      }

      // Sort by timestamp (newest first)
      return events.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
    };

    const newActivities = generateActivities();
    setActivities(newActivities);

    // Update unread count for new activities
    if (activities.length > 0 && newActivities.length > activities.length) {
      setUnreadCount(prev => prev + (newActivities.length - activities.length));
    }
  }, [stats, recentSessions, theme]);

  // Auto-refresh activities
  useEffect(() => {
    if (!liveUpdates) return;

    const interval = setInterval(() => {
      // Add a new simulated activity occasionally
      if (Math.random() > 0.7) {
        const now = new Date();
        const newActivity: ActivityEvent = {
          id: `live-${Date.now()}`,
          type: 'detection_event',
          title: 'Real-time Detection Update',
          description: `${Math.floor(Math.random() * 20 + 5)} new detections processed`,
          timestamp: now,
          status: 'info',
          icon: <TrendingUp />,
          color: theme.palette.info.main,
        };

        setActivities(prev => [newActivity, ...prev.slice(0, 19)]); // Keep last 20
        setUnreadCount(prev => prev + 1);
      }
    }, 15000); // Every 15 seconds

    return () => clearInterval(interval);
  }, [liveUpdates, theme]);

  const formatTimeAgo = (timestamp: Date) => {
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - timestamp.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle fontSize="small" />;
      case 'warning': return <Assessment fontSize="small" />;
      case 'error': return <Stop fontSize="small" />;
      default: return <Schedule fontSize="small" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return theme.palette.success.main;
      case 'warning': return theme.palette.warning.main;
      case 'error': return theme.palette.error.main;
      default: return theme.palette.info.main;
    }
  };

  const handleMarkAllRead = () => {
    setUnreadCount(0);
  };

  if (loading) {
    return (
      <Card className={className} sx={{ height: 500 }}>
        <CardHeader title="Activity Timeline" />
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
            <Schedule sx={{ fontSize: 40, color: 'text.secondary' }} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card 
      className={className} 
      sx={{ 
        height: 550,
        background: theme.palette.mode === 'dark' 
          ? 'linear-gradient(135deg, rgba(156, 39, 176, 0.1) 0%, rgba(233, 30, 99, 0.1) 100%)'
          : 'linear-gradient(135deg, rgba(156, 39, 176, 0.05) 0%, rgba(233, 30, 99, 0.05) 100%)'
      }}
    >
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Schedule color="primary" />
            <Typography variant="h6">Activity Timeline</Typography>
            <Chip
              label={liveUpdates ? 'Live' : 'Paused'}
              color={liveUpdates ? 'success' : 'default'}
              size="small"
              variant="outlined"
            />
          </Box>
        }
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Badge badgeContent={unreadCount} color="error">
              <Tooltip title="Mark all as read">
                <IconButton onClick={handleMarkAllRead} size="small">
                  <Notifications />
                </IconButton>
              </Tooltip>
            </Badge>
            <Tooltip title={liveUpdates ? "Pause updates" : "Resume updates"}>
              <IconButton 
                onClick={() => setLiveUpdates(!liveUpdates)} 
                color={liveUpdates ? "primary" : "default"}
                size="small"
              >
                <Refresh />
              </IconButton>
            </Tooltip>
            <IconButton size="small">
              <MoreVert />
            </IconButton>
          </Box>
        }
      />
      
      <CardContent sx={{ pt: 0, height: 480, overflow: 'auto' }}>
        {activities.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Schedule sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="body1" color="text.secondary">
              No recent activity to display
            </Typography>
          </Box>
        ) : (
          <Timeline>
            {activities.map((activity, index) => (
              <Fade in={true} timeout={300 + index * 100} key={activity.id}>
                <TimelineItem>
                  <TimelineOppositeContent sx={{ m: 'auto 0', flex: 0.3 }}>
                    <Typography variant="caption" color="text.secondary">
                      {formatTimeAgo(activity.timestamp)}
                    </Typography>
                  </TimelineOppositeContent>
                  
                  <TimelineSeparator>
                    <Zoom in={true} timeout={500 + index * 100}>
                      <TimelineDot 
                        sx={{ 
                          bgcolor: activity.color,
                          p: 1,
                          boxShadow: `0 0 0 4px ${activity.color}20`,
                        }}
                      >
                        <Avatar sx={{ width: 32, height: 32, bgcolor: 'transparent' }}>
                          {React.cloneElement(activity.icon as React.ReactElement, {
                            sx: { color: 'white', fontSize: 18 }
                          })}
                        </Avatar>
                      </TimelineDot>
                    </Zoom>
                    {index < activities.length - 1 && <TimelineConnector />}
                  </TimelineSeparator>
                  
                  <TimelineContent sx={{ py: '12px', px: 2 }}>
                    <Paper 
                      elevation={1} 
                      sx={{ 
                        p: 2,
                        borderLeft: `4px solid ${activity.color}`,
                        '&:hover': {
                          elevation: 3,
                          transform: 'translateX(4px)',
                          transition: 'all 0.2s ease-in-out',
                        },
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="subtitle2" fontWeight="bold">
                          {activity.title}
                        </Typography>
                        <Chip
                          icon={getStatusIcon(activity.status)}
                          label={activity.status.toUpperCase()}
                          color={activity.status as any}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                      
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {activity.description}
                      </Typography>
                      
                      {activity.metadata && (
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          {Object.entries(activity.metadata).slice(0, 3).map(([key, value]) => (
                            <Chip
                              key={key}
                              label={`${key}: ${value}`}
                              size="small"
                              variant="outlined"
                              sx={{ fontSize: '0.7rem', height: 20 }}
                            />
                          ))}
                        </Box>
                      )}
                    </Paper>
                  </TimelineContent>
                </TimelineItem>
              </Fade>
            ))}
          </Timeline>
        )}
      </CardContent>
    </Card>
  );
};

export default ActivityTimelineChart;
