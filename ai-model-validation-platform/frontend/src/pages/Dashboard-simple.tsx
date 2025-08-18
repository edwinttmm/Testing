import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Skeleton,
  Alert,
} from '@mui/material';
import {
  FolderOpen,
  VideoLibrary,
  Assessment,
  TrendingUp,
} from '@mui/icons-material';
import { getDashboardStats } from '../services/api';
import { EnhancedDashboardStats } from '../services/types';

interface StatCardProps {
  title: string;
  value: number;
  icon: React.ReactElement;
  color: string;
  subtitle?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color, subtitle }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Box
          sx={{
            p: 1,
            borderRadius: 1,
            bgcolor: `${color}.light`,
            color: `${color}.main`,
            mr: 2,
          }}
        >
          {icon}
        </Box>
        <Box>
          <Typography variant="h4" component="div" fontWeight="bold">
            {value}
          </Typography>
          <Typography color="text.secondary" variant="body2">
            {title}
          </Typography>
          {subtitle && (
            <Typography color="text.secondary" variant="caption">
              {subtitle}
            </Typography>
          )}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<EnhancedDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        setLoading(true);
        const data = await getDashboardStats();
        setStats(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch dashboard stats:', err);
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
          average_accuracy: 94.2,
          active_tests: 0,
          total_detections: 0
        });
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

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
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
        {error && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            {error} - Showing demo data
          </Alert>
        )}
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <StatCard
            title="Active Projects"
            value={stats?.project_count || 0}
            icon={<FolderOpen />}
            color="primary"
            subtitle={stats?.project_count ? `${stats.project_count} total projects` : 'No projects yet'}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <StatCard
            title="Videos Processed"
            value={stats?.video_count || 0}
            icon={<VideoLibrary />}
            color="success"
            subtitle={stats?.video_count ? `${stats.video_count} videos uploaded` : 'No videos yet'}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <StatCard
            title="Tests Completed"
            value={stats?.test_session_count || 0}
            icon={<Assessment />}
            color="info"
            subtitle={stats?.test_session_count ? `${stats.test_session_count} test sessions` : 'No tests yet'}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <StatCard
            title="Detection Accuracy"
            value={stats?.average_accuracy || 0}
            icon={<TrendingUp />}
            color="warning"
            subtitle="Average across all tests"
          />
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        <Box sx={{ minWidth: 400, flex: 1 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Test Sessions
              </Typography>
              <Box sx={{ mt: 2 }}>
                {[1, 2, 3, 4].map((session) => (
                  <Box
                    key={session}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      py: 1,
                      borderBottom: '1px solid #f0f0f0',
                    }}
                  >
                    <Box>
                      <Typography variant="body2" fontWeight="medium">
                        Test Session #{session}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Front-facing VRU • 2 hours ago
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="success.main" fontWeight="medium">
                      92.5% Accuracy
                    </Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Box>

        <Box sx={{ minWidth: 400, flex: 1 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Status
              </Typography>
              <Box sx={{ mt: 2 }}>
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">YOLO Model Performance</Typography>
                    <Typography variant="body2">95%</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={95} color="success" />
                </Box>
                
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Database Usage</Typography>
                    <Typography variant="body2">67%</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={67} color="info" />
                </Box>
                
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Storage Usage</Typography>
                    <Typography variant="body2">43%</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={43} color="primary" />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;