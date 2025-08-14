import React, { useState, useEffect, memo, useMemo, useCallback } from 'react';
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
import { getDashboardStats } from '../services/enhancedApiService';
import { DashboardStats } from '../services/types';
import AccessibleStatCard from '../components/ui/AccessibleStatCard';
import AccessibleCard, { AccessibleProgressItem, AccessibleSessionItem } from '../components/ui/AccessibleCard';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardStats = useCallback(async () => {
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
        projectCount: 0,
        videoCount: 0,
        testCount: 0,
        averageAccuracy: 94.2,
        activeTests: 0,
        totalDetections: 0
      });
    } finally {
      setLoading(false);
    }
  }, []);

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
          <AccessibleStatCard
            title="Active Projects"
            value={stats?.projectCount || 0}
            icon={<FolderOpen />}
            color="primary"
            subtitle={stats?.projectCount ? `${stats.projectCount} total projects` : 'No projects yet'}
            loading={loading}
            ariaLabel={`Active Projects: ${stats?.projectCount || 0} total projects`}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Videos Processed"
            value={stats?.videoCount || 0}
            icon={<VideoLibrary />}
            color="success"
            subtitle={stats?.videoCount ? `${stats.videoCount} videos uploaded` : 'No videos yet'}
            loading={loading}
            ariaLabel={`Videos Processed: ${stats?.videoCount || 0} videos uploaded`}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Tests Completed"
            value={stats?.testCount || 0}
            icon={<Assessment />}
            color="info"
            subtitle={stats?.testCount ? `${stats.testCount} test sessions` : 'No tests yet'}
            loading={loading}
            ariaLabel={`Tests Completed: ${stats?.testCount || 0} test sessions`}
          />
        </Box>
        
        <Box sx={{ minWidth: 250, flex: 1 }}>
          <AccessibleStatCard
            title="Detection Accuracy"
            value={`${stats?.averageAccuracy || 0}%`}
            icon={<TrendingUp />}
            color="warning"
            subtitle="Average across all tests"
            loading={loading}
            ariaLabel={`Detection Accuracy: ${stats?.averageAccuracy || 0}% average across all tests`}
            trend={{
              value: 2.3,
              direction: 'up'
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
              {[
                { session: 1, type: "Front-facing VRU", timeAgo: "2 hours ago", accuracy: 92.5 },
                { session: 2, type: "Side-view VRU", timeAgo: "4 hours ago", accuracy: 88.3 },
                { session: 3, type: "Mixed-angle VRU", timeAgo: "6 hours ago", accuracy: 95.1 },
                { session: 4, type: "Night-time VRU", timeAgo: "8 hours ago", accuracy: 87.9 }
              ].map((item) => (
                <AccessibleSessionItem
                  key={item.session}
                  sessionNumber={item.session}
                  type={item.type}
                  timeAgo={item.timeAgo}
                  accuracy={item.accuracy}
                />
              ))}
            </Box>
          </AccessibleCard>
        </Box>

        <Box sx={{ minWidth: 400, flex: 1 }}>
          <AccessibleCard
            title="System Status"
            loading={loading}
            ariaLabel="System performance metrics"
            role="region"
          >
            <Box role="group" aria-label="System performance indicators">
              <AccessibleProgressItem
                label="YOLO Model Performance"
                value={95}
                color="success"
                ariaLabel="YOLO Model Performance at 95% - Excellent"
              />
              <AccessibleProgressItem
                label="Database Usage"
                value={67}
                color="info"
                ariaLabel="Database Usage at 67% - Normal"
              />
              <AccessibleProgressItem
                label="Storage Usage"
                value={43}
                color="primary"
                ariaLabel="Storage Usage at 43% - Good"
              />
            </Box>
          </AccessibleCard>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;