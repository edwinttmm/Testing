import React from 'react';
import { Box, Grid, Typography, Chip, Container } from '@mui/material';
import { Dashboard, TrendingUp } from '@mui/icons-material';
import {
  RealtimeMetricsChart,
  SystemHealthIndicator,
  PerformanceMetricsPanel,
  ActivityTimelineChart,
  DetectionAnalyticsChart,
} from './index';
import { EnhancedDashboardStats, TestSession } from '../../services/types';

interface EnhancedDashboardExampleProps {
  stats: EnhancedDashboardStats | null;
  recentSessions?: TestSession[];
  loading?: boolean;
}

/**
 * Enhanced Dashboard Example Component
 * 
 * This is an example of how to integrate the enhanced dashboard components
 * with your existing dashboard. You can copy parts of this implementation
 * into your main Dashboard.tsx file or use it as a reference.
 * 
 * Features:
 * - Real-time metrics visualization with live updates
 * - System health monitoring with animated indicators
 * - Advanced performance analytics with multiple chart types
 * - Activity timeline with WebSocket integration
 * - Detection analytics with interactive charts
 */
const EnhancedDashboardExample: React.FC<EnhancedDashboardExampleProps> = ({
  stats,
  recentSessions = [],
  loading = false
}) => {
  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Dashboard color="primary" sx={{ fontSize: 32 }} />
          <Typography variant="h4" component="h1">
            Enhanced AI Model Validation Dashboard
          </Typography>
          <Chip
            icon={<TrendingUp />}
            label="Real-time Analytics"
            color="success"
            variant="outlined"
          />
        </Box>
        
        <Typography variant="subtitle1" color="text.secondary">
          Advanced visualization and monitoring for your AI model validation platform
        </Typography>
      </Box>

      {/* Main Dashboard Grid */}
      <Grid container spacing={3}>
        {/* Row 1: Metrics and Health */}
        <Grid item xs={12} lg={8}>
          <RealtimeMetricsChart 
            stats={stats} 
            loading={loading}
            className="enhanced-metrics-chart"
          />
        </Grid>
        
        <Grid item xs={12} lg={4}>
          <SystemHealthIndicator 
            stats={stats} 
            loading={loading}
            className="system-health-indicator"
          />
        </Grid>

        {/* Row 2: Performance Analytics */}
        <Grid item xs={12}>
          <PerformanceMetricsPanel 
            stats={stats} 
            loading={loading}
            className="performance-metrics-panel"
          />
        </Grid>

        {/* Row 3: Timeline and Analytics */}
        <Grid item xs={12} lg={6}>
          <ActivityTimelineChart 
            stats={stats} 
            recentSessions={recentSessions}
            loading={loading}
            className="activity-timeline-chart"
          />
        </Grid>
        
        <Grid item xs={12} lg={6}>
          <DetectionAnalyticsChart 
            stats={stats} 
            loading={loading}
            className="detection-analytics-chart"
          />
        </Grid>
      </Grid>

      {/* Integration Notes */}
      <Box sx={{ mt: 4, p: 3, bgcolor: 'action.hover', borderRadius: 2 }}>
        <Typography variant="h6" gutterBottom>
          Integration Guide
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          To integrate these components into your existing Dashboard.tsx:
        </Typography>
        <Box component="ol" sx={{ pl: 2 }}>
          <Box component="li" sx={{ mb: 1 }}>
            <Typography variant="body2">
              Import the components: <code>import &#123; RealtimeMetricsChart, SystemHealthIndicator &#125; from './components/dashboard';</code>
            </Typography>
          </Box>
          <Box component="li" sx={{ mb: 1 }}>
            <Typography variant="body2">
              Add them to your existing grid layout below the current stat cards
            </Typography>
          </Box>
          <Box component="li" sx={{ mb: 1 }}>
            <Typography variant="body2">
              Pass your existing <code>stats</code> and <code>recentSessions</code> props
            </Typography>
          </Box>
          <Box component="li" sx={{ mb: 1 }}>
            <Typography variant="body2">
              Customize styling and layout to match your design requirements
            </Typography>
          </Box>
        </Box>
      </Box>
    </Container>
  );
};

export default EnhancedDashboardExample;