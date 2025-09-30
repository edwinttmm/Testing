# Enhanced Dashboard Components

This directory contains advanced dashboard visualization components designed to enhance the AI Model Validation Platform's user interface with modern, interactive charts and real-time monitoring capabilities.

## Components Overview

### 🔄 RealtimeMetricsChart
**File:** `RealtimeMetricsChart.tsx`

A time-series chart showing detection accuracy trends over time using Recharts.

**Features:**
- Real-time data updates every 3 seconds
- Multiple chart types (line and area charts)
- Configurable time ranges (5m, 15m, 1h, 24h)
- Live/pause toggle for data updates
- Trend indicators and confidence intervals
- Responsive design with Material-UI theming

**Props:**
- `stats: EnhancedDashboardStats | null` - Dashboard statistics
- `loading?: boolean` - Loading state
- `className?: string` - Additional CSS classes

### 🏥 SystemHealthIndicator
**File:** `SystemHealthIndicator.tsx`

Advanced system status component with animated health indicators and metrics.

**Features:**
- Circular progress indicators with animated pulse effects
- Health metrics breakdown (Detection Engine, Signal Processing, System Load, Data Pipeline)
- Color-coded status indicators (excellent, good, warning, critical)
- Real-time uptime and response time monitoring
- Service status chips (API Server, Database, WebSocket)
- Accessible design with ARIA labels

**Props:**
- `stats: EnhancedDashboardStats | null` - Dashboard statistics
- `loading?: boolean` - Loading state
- `className?: string` - Additional CSS classes

### 📊 PerformanceMetricsPanel
**File:** `PerformanceMetricsPanel.tsx`

Interactive performance analytics panel with multiple visualization types.

**Features:**
- Tabbed interface (Metrics, Latency, Breakdown)
- Performance vs benchmark comparisons
- Radar charts for multi-dimensional analysis
- Latency analysis with percentile tracking
- Performance improvement indicators
- Export functionality
- Configurable time periods

**Props:**
- `stats: EnhancedDashboardStats | null` - Dashboard statistics
- `loading?: boolean` - Loading state
- `className?: string` - Additional CSS classes

### ⏱️ ActivityTimelineChart
**File:** `ActivityTimelineChart.tsx`

Timeline component showing recent activities and test sessions with real-time updates.

**Features:**
- Material-UI Timeline with animated entries
- Real-time activity updates
- Event categorization (tests, uploads, detections, projects)
- Unread notification badges
- Live/pause toggle for updates
- Fade and zoom animations
- Activity filtering and status indicators

**Props:**
- `stats: EnhancedDashboardStats | null` - Dashboard statistics
- `recentSessions?: TestSession[]` - Recent test sessions
- `loading?: boolean` - Loading state
- `className?: string` - Additional CSS classes

### 🎯 DetectionAnalyticsChart
**File:** `DetectionAnalyticsChart.tsx`

Comprehensive detection analytics with multiple chart types and data views.

**Features:**
- Multiple chart types (pie, donut, bar, radial)
- Three view modes (detection types, confidence distribution, accuracy metrics)
- Interactive chart type switching
- Detailed statistics panel
- Custom label rendering
- Detection type breakdown
- Confidence level analysis

**Props:**
- `stats: EnhancedDashboardStats | null` - Dashboard statistics
- `loading?: boolean` - Loading state
- `className?: string` - Additional CSS classes

## Installation & Usage

### Import Components

```typescript
import {
  RealtimeMetricsChart,
  SystemHealthIndicator,
  PerformanceMetricsPanel,
  ActivityTimelineChart,
  DetectionAnalyticsChart,
} from './components/dashboard';
```

### Basic Usage

```typescript
import React from 'react';
import { Grid } from '@mui/material';
import { RealtimeMetricsChart, SystemHealthIndicator } from './components/dashboard';

const MyDashboard: React.FC = () => {
  const [stats, setStats] = useState<EnhancedDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} lg={8}>
        <RealtimeMetricsChart stats={stats} loading={loading} />
      </Grid>
      <Grid item xs={12} lg={4}>
        <SystemHealthIndicator stats={stats} loading={loading} />
      </Grid>
    </Grid>
  );
};
```

### Integration with Existing Dashboard

To integrate these components into the existing `Dashboard.tsx`:

1. **Import the components:**
   ```typescript
   import {
     RealtimeMetricsChart,
     SystemHealthIndicator,
     PerformanceMetricsPanel,
     ActivityTimelineChart,
     DetectionAnalyticsChart,
   } from '../components/dashboard';
   ```

2. **Add after existing stat cards:**
   ```typescript
   {/* Existing stat cards */}
   <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 4 }}>
     {/* Your existing AccessibleStatCard components */}
   </Box>

   {/* New enhanced components */}
   <Grid container spacing={3} sx={{ mb: 4 }}>
     <Grid item xs={12} lg={8}>
       <RealtimeMetricsChart stats={stats} loading={loading} />
     </Grid>
     <Grid item xs={12} lg={4}>
       <SystemHealthIndicator stats={stats} loading={loading} />
     </Grid>
   </Grid>

   <Grid container spacing={3}>
     <Grid item xs={12}>
       <PerformanceMetricsPanel stats={stats} loading={loading} />
     </Grid>
   </Grid>
   ```

## Dependencies

These components use the following libraries already available in the project:

- **Chart Libraries:**
  - `recharts` (v2.7.2) - For line, area, bar, pie, and radar charts
  - `chart.js` (v4.5.0) - Available but not used in these components
  - `react-chartjs-2` (v5.3.0) - Available but not used in these components

- **Material-UI:**
  - `@mui/material` - Core components and theming
  - `@mui/icons-material` - Icons
  - `@mui/lab` - Timeline components

- **React:**
  - `react` (v18.2.0)
  - `typescript` (v4.7.4)

## Features

### 🎨 Design System
- Consistent Material-UI theming
- Dark/light mode support
- Responsive design for all screen sizes
- Gradient backgrounds with theme-aware colors
- Accessible color schemes and contrast ratios

### ⚡ Performance
- Optimized rendering with React.memo where applicable
- Efficient data processing with useMemo hooks
- Controlled re-renders to prevent performance issues
- Lazy loading of chart data

### 🔧 Customization
- Configurable time ranges and update intervals
- Multiple chart types and view modes
- Theme-aware color schemes
- Extensible data formatting functions

### ♿ Accessibility
- ARIA labels and roles for screen readers
- Keyboard navigation support
- High contrast mode compatibility
- Semantic HTML structure

## Real-time Integration

These components are designed to work with your existing WebSocket integration:

- Components automatically update when `stats` prop changes
- Real-time data simulation for demonstration purposes
- Integration with existing `useWebSocket` hook
- Configurable update frequencies

## Example Implementation

See `EnhancedDashboardExample.tsx` for a complete example of how to use all components together.

## Customization

### Theming
Components automatically inherit your Material-UI theme. Customize colors, typography, and spacing through your theme configuration.

### Data Format
Components expect the `EnhancedDashboardStats` interface. Ensure your data matches this format or extend the interface as needed.

### Chart Types
Each chart component supports multiple visualization types. Use the provided controls or programmatically set the chart type via props.

## Browser Support

These components support all modern browsers:
- Chrome/Chromium 88+
- Firefox 85+
- Safari 14+
- Edge 88+

## Performance Considerations

- Components use efficient rendering patterns
- Chart data is memoized to prevent unnecessary recalculations
- Real-time updates are throttled to prevent UI blocking
- Large datasets are automatically truncated for performance

## Contributing

When adding new dashboard components:

1. Follow the existing naming convention
2. Include TypeScript interfaces for all props
3. Add accessibility features (ARIA labels, keyboard navigation)
4. Ensure responsive design
5. Include loading states
6. Add proper error handling
7. Update this README with component documentation