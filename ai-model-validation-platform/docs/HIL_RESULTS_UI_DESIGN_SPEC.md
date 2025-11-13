# HIL Results UI Design Specification

## Executive Summary

This document specifies a clean, modern UI redesign for HILResults.tsx that prioritizes clarity, removes redundancy, and provides immediate visual feedback on test outcomes.

---

## Design Principles

1. **Visibility**: Test pass/fail status is immediately obvious
2. **Clarity**: Single source of truth for each data point
3. **Hierarchy**: Most important information at the top
4. **Simplicity**: No duplicate tables or confusing sections
5. **Responsiveness**: Works on desktop and tablet views

---

## Component Architecture

### 1. TestStatusBanner Component

**Purpose**: Large, unmissable pass/fail indicator at the top of the page

**Interface**:
```typescript
interface TestStatusBannerProps {
  testPassed: boolean;
  detectionCount: number;
  expectedCount: number;
  matchRate: number;
  testStartTime?: string;
  testEndTime?: string;
}
```

**Structure**:
```tsx
<Alert
  severity={testPassed ? "success" : "error"}
  sx={{
    mb: 4,
    p: 4,
    borderRadius: 2,
    boxShadow: 3
  }}
>
  <Box display="flex" alignItems="center" justifyContent="space-between">
    {/* Left: Status and Details */}
    <Box>
      <Typography variant="h3" fontWeight="bold" gutterBottom>
        {testPassed ? "✓ TEST PASSED" : "✗ TEST FAILED"}
      </Typography>
      <Typography variant="h6" color="textSecondary">
        {detectionCount} out of {expectedCount} detections found
      </Typography>
      {testStartTime && (
        <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
          Test Duration: {calculateDuration(testStartTime, testEndTime)}
        </Typography>
      )}
    </Box>

    {/* Right: Match Rate Badge */}
    <Box textAlign="right">
      <Chip
        label={`${matchRate}% Match Rate`}
        color={testPassed ? "success" : "error"}
        size="large"
        sx={{
          fontSize: '1.2rem',
          height: 48,
          px: 3
        }}
      />
    </Box>
  </Box>
</Alert>
```

**Styling Guidelines**:
- Success (Pass): Green (#2e7d32) background with white text
- Error (Fail): Red (#d32f2f) background with white text
- Padding: 32px all sides
- Border radius: 8px
- Box shadow: elevation 3

---

### 2. MetricsSummaryCards Component

**Purpose**: Display key metrics in clean, scannable cards

**Interface**:
```typescript
interface MetricsSummaryCardsProps {
  detectionCount: number;
  expectedCount: number;
  averageLatency: number;
  matchRate: number;
  hardwareStatus: 'active' | 'inactive' | 'error';
  hardwareConnectedAt?: string;
}
```

**Structure**:
```tsx
<Grid container spacing={3} sx={{ mb: 4 }}>
  {/* Card 1: Detections */}
  <Grid item xs={12} sm={6} md={3}>
    <Card elevation={2}>
      <CardContent sx={{ textAlign: 'center', py: 3 }}>
        <Box sx={{ mb: 2 }}>
          <CheckCircleOutline sx={{ fontSize: 40, color: 'success.main' }} />
        </Box>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Detections Found
        </Typography>
        <Typography variant="h3" fontWeight="bold">
          {detectionCount}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          out of {expectedCount} expected
        </Typography>
      </CardContent>
    </Card>
  </Grid>

  {/* Card 2: Average Latency */}
  <Grid item xs={12} sm={6} md={3}>
    <Card elevation={2}>
      <CardContent sx={{ textAlign: 'center', py: 3 }}>
        <Box sx={{ mb: 2 }}>
          <Timer sx={{ fontSize: 40, color: 'primary.main' }} />
        </Box>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Average Latency
        </Typography>
        <Typography variant="h3" fontWeight="bold">
          {averageLatency.toFixed(1)}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          milliseconds
        </Typography>
      </CardContent>
    </Card>
  </Grid>

  {/* Card 3: Match Rate */}
  <Grid item xs={12} sm={6} md={3}>
    <Card elevation={2}>
      <CardContent sx={{ textAlign: 'center', py: 3 }}>
        <Box sx={{ mb: 2 }}>
          <TrendingUp sx={{
            fontSize: 40,
            color: matchRate >= 80 ? 'success.main' : 'warning.main'
          }} />
        </Box>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Match Rate
        </Typography>
        <Typography variant="h3" fontWeight="bold">
          {matchRate}%
        </Typography>
        <Typography variant="body2" color="textSecondary">
          ground truth matched
        </Typography>
      </CardContent>
    </Card>
  </Grid>

  {/* Card 4: Hardware Status */}
  <Grid item xs={12} sm={6} md={3}>
    <Card elevation={2}>
      <CardContent sx={{ textAlign: 'center', py: 3 }}>
        <Box sx={{ mb: 2 }}>
          <Memory sx={{
            fontSize: 40,
            color: hardwareStatus === 'active' ? 'success.main' : 'error.main'
          }} />
        </Box>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Hardware Status
        </Typography>
        <Chip
          label={hardwareStatus.toUpperCase()}
          color={hardwareStatus === 'active' ? 'success' : 'error'}
          size="medium"
          sx={{ fontWeight: 'bold' }}
        />
        {hardwareConnectedAt && (
          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
            Since {new Date(hardwareConnectedAt).toLocaleTimeString()}
          </Typography>
        )}
      </CardContent>
    </Card>
  </Grid>
</Grid>
```

**Styling Guidelines**:
- Card elevation: 2
- Card padding: 24px vertical, 16px horizontal
- Icon size: 40px
- Metric value: h3 (3rem), bold
- Labels: body2 (0.875rem), text secondary
- Cards are fully responsive with grid breakpoints

---

### 3. CleanDetectionTable Component

**Purpose**: Single, comprehensive table showing all detection data with clear pass/fail indicators

**Interface**:
```typescript
interface Detection {
  id: string;
  timestamp: number;
  voltage: number;
  latency_ms: number | null;
  matched_gt: boolean;
  passed: boolean;
  ground_truth_id?: string;
  video_id?: string;
  notes?: string;
}

interface CleanDetectionTableProps {
  detections: Detection[];
  onDetectionClick?: (detection: Detection) => void;
  sortBy?: 'timestamp' | 'latency' | 'result';
  sortOrder?: 'asc' | 'desc';
}
```

**Structure**:
```tsx
<Paper elevation={2} sx={{ mb: 4 }}>
  {/* Table Header */}
  <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider' }}>
    <Typography variant="h5" fontWeight="bold">
      Detection Results
    </Typography>
    <Typography variant="body2" color="textSecondary">
      {detections.length} total detections
    </Typography>
  </Box>

  {/* Table */}
  <TableContainer>
    <Table>
      <TableHead>
        <TableRow>
          <TableCell width="60px" align="center">
            <Typography variant="subtitle2" fontWeight="bold">#</Typography>
          </TableCell>
          <TableCell sortDirection={sortBy === 'timestamp' ? sortOrder : false}>
            <TableSortLabel
              active={sortBy === 'timestamp'}
              direction={sortOrder}
              onClick={() => handleSort('timestamp')}
            >
              <Typography variant="subtitle2" fontWeight="bold">
                Time (s)
              </Typography>
            </TableSortLabel>
          </TableCell>
          <TableCell>
            <Typography variant="subtitle2" fontWeight="bold">
              Voltage (V)
            </Typography>
          </TableCell>
          <TableCell sortDirection={sortBy === 'latency' ? sortOrder : false}>
            <TableSortLabel
              active={sortBy === 'latency'}
              direction={sortOrder}
              onClick={() => handleSort('latency')}
            >
              <Typography variant="subtitle2" fontWeight="bold">
                Latency (ms)
              </Typography>
            </TableSortLabel>
          </TableCell>
          <TableCell align="center">
            <Typography variant="subtitle2" fontWeight="bold">
              Matched GT
            </Typography>
          </TableCell>
          <TableCell align="center" sortDirection={sortBy === 'result' ? sortOrder : false}>
            <TableSortLabel
              active={sortBy === 'result'}
              direction={sortOrder}
              onClick={() => handleSort('result')}
            >
              <Typography variant="subtitle2" fontWeight="bold">
                Result
              </Typography>
            </TableSortLabel>
          </TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {detections.map((detection, idx) => (
          <TableRow
            key={detection.id}
            hover
            onClick={() => onDetectionClick?.(detection)}
            sx={{
              cursor: onDetectionClick ? 'pointer' : 'default',
              '&:hover': {
                backgroundColor: 'action.hover'
              }
            }}
          >
            {/* Index */}
            <TableCell align="center">
              <Typography variant="body2" fontWeight="medium">
                {idx + 1}
              </Typography>
            </TableCell>

            {/* Timestamp */}
            <TableCell>
              <Typography variant="body2" fontFamily="monospace">
                {detection.timestamp.toFixed(3)}
              </Typography>
            </TableCell>

            {/* Voltage */}
            <TableCell>
              <Typography variant="body2" fontFamily="monospace">
                {detection.voltage.toFixed(2)}
              </Typography>
            </TableCell>

            {/* Latency */}
            <TableCell>
              {detection.latency_ms !== null ? (
                <Box display="flex" alignItems="center" gap={1}>
                  <Typography variant="body2" fontFamily="monospace">
                    {detection.latency_ms.toFixed(1)}
                  </Typography>
                  {detection.latency_ms > 100 && (
                    <Tooltip title="High latency detected">
                      <Warning fontSize="small" color="warning" />
                    </Tooltip>
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="textSecondary">
                  N/A
                </Typography>
              )}
            </TableCell>

            {/* Matched GT */}
            <TableCell align="center">
              {detection.matched_gt ? (
                <CheckCircle fontSize="small" sx={{ color: 'success.main' }} />
              ) : (
                <Cancel fontSize="small" sx={{ color: 'error.main' }} />
              )}
            </TableCell>

            {/* Result */}
            <TableCell align="center">
              <Chip
                label={detection.passed ? "PASS" : "FAIL"}
                color={detection.passed ? "success" : "error"}
                size="small"
                sx={{
                  fontWeight: 'bold',
                  minWidth: 60
                }}
              />
            </TableCell>
          </TableRow>
        ))}

        {/* Empty State */}
        {detections.length === 0 && (
          <TableRow>
            <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
              <Box>
                <SearchOff sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
                <Typography variant="h6" color="textSecondary">
                  No detections found
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Run a test to see detection results here
                </Typography>
              </Box>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  </TableContainer>

  {/* Table Footer with Pagination (if needed) */}
  {detections.length > 10 && (
    <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
      <TablePagination
        component="div"
        count={detections.length}
        page={page}
        onPageChange={handlePageChange}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={handleRowsPerPageChange}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />
    </Box>
  )}
</Paper>
```

**Styling Guidelines**:
- Table header: Bold subtitle2 (0.875rem)
- Row height: 56px (comfortable reading)
- Monospace font for numerical values
- Hover effect on rows if clickable
- Pass chip: Green (#2e7d32)
- Fail chip: Red (#d32f2f)
- Warning icon for latency > 100ms

---

### 4. VideoSequenceSelector Component

**Purpose**: Clean, intuitive video switcher for multi-video sequences

**Interface**:
```typescript
interface Video {
  id: string;
  filename: string;
  duration_seconds: number;
  frame_count: number;
  order_index: number;
}

interface VideoSequenceSelectorProps {
  videos: Video[];
  selectedVideoId: string;
  onVideoChange: (videoId: string) => void;
  isSequence: boolean;
}
```

**Structure**:
```tsx
{isSequence && videos.length > 1 && (
  <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
    <Box sx={{ mb: 2 }}>
      <Typography variant="h6" fontWeight="bold" gutterBottom>
        Video Sequence
      </Typography>
      <Typography variant="body2" color="textSecondary">
        Select a video to view its detection results
      </Typography>
    </Box>

    {/* Button Group for Video Selection */}
    <Box sx={{
      display: 'flex',
      gap: 2,
      flexWrap: 'wrap',
      '@media (max-width: 768px)': {
        flexDirection: 'column'
      }
    }}>
      {videos
        .sort((a, b) => a.order_index - b.order_index)
        .map((video, idx) => (
          <Card
            key={video.id}
            onClick={() => onVideoChange(video.id)}
            sx={{
              flex: '1 1 calc(33.333% - 16px)',
              minWidth: 250,
              cursor: 'pointer',
              border: 2,
              borderColor: selectedVideoId === video.id ? 'primary.main' : 'transparent',
              backgroundColor: selectedVideoId === video.id ? 'action.selected' : 'background.paper',
              transition: 'all 0.2s ease',
              '&:hover': {
                borderColor: 'primary.main',
                boxShadow: 3,
                transform: 'translateY(-2px)'
              }
            }}
          >
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <VideoLibrary
                  sx={{
                    color: selectedVideoId === video.id ? 'primary.main' : 'text.secondary'
                  }}
                />
                <Typography variant="h6" fontWeight="bold">
                  Video {idx + 1}
                </Typography>
                {selectedVideoId === video.id && (
                  <Chip label="Active" color="primary" size="small" />
                )}
              </Box>

              <Typography
                variant="body2"
                color="textSecondary"
                noWrap
                title={video.filename}
              >
                {video.filename}
              </Typography>

              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="textSecondary">
                    Duration
                  </Typography>
                  <Typography variant="body2" fontWeight="medium">
                    {video.duration_seconds.toFixed(1)}s
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="textSecondary">
                    Frames
                  </Typography>
                  <Typography variant="body2" fontWeight="medium">
                    {video.frame_count}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        ))}
    </Box>

    {/* Sequence Progress Indicator */}
    <Box sx={{ mt: 3 }}>
      <Box display="flex" alignItems="center" gap={1} mb={1}>
        <Typography variant="body2" fontWeight="medium">
          Sequence Progress
        </Typography>
        <Typography variant="body2" color="textSecondary">
          {videos.findIndex(v => v.id === selectedVideoId) + 1} / {videos.length}
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={((videos.findIndex(v => v.id === selectedVideoId) + 1) / videos.length) * 100}
        sx={{ height: 8, borderRadius: 4 }}
      />
    </Box>
  </Paper>
)}
```

**Styling Guidelines**:
- Cards in flexible grid (3 columns on desktop, stacked on mobile)
- Active video: Primary color border (2px)
- Hover effect: Slight elevation and border highlight
- Card min-width: 250px
- Gap between cards: 16px
- Transition: 200ms ease for smooth interactions

---

## Page Layout Structure

```tsx
<Container maxWidth="xl" sx={{ py: 4 }}>
  {/* 1. Test Status Banner - ALWAYS VISIBLE AT TOP */}
  <TestStatusBanner
    testPassed={testPassed}
    detectionCount={detectionCount}
    expectedCount={expectedCount}
    matchRate={matchRate}
    testStartTime={sessionData.started_at}
    testEndTime={sessionData.completed_at}
  />

  {/* 2. Summary Metrics Cards */}
  <MetricsSummaryCards
    detectionCount={detectionCount}
    expectedCount={expectedCount}
    averageLatency={averageLatency}
    matchRate={matchRate}
    hardwareStatus={hardwareStatus}
    hardwareConnectedAt={sessionData.labjack_connected_at}
  />

  {/* 3. Video Sequence Selector (if multi-video) */}
  {isSequence && videos.length > 1 && (
    <VideoSequenceSelector
      videos={videos}
      selectedVideoId={selectedVideoId}
      onVideoChange={handleVideoChange}
      isSequence={isSequence}
    />
  )}

  {/* 4. Clean Detection Table */}
  <CleanDetectionTable
    detections={filteredDetections}
    onDetectionClick={handleDetectionClick}
    sortBy={sortBy}
    sortOrder={sortOrder}
  />

  {/* 5. Optional: Expandable Advanced Metrics */}
  <Accordion sx={{ mt: 2 }}>
    <AccordionSummary expandIcon={<ExpandMore />}>
      <Typography variant="h6">Advanced Metrics</Typography>
    </AccordionSummary>
    <AccordionDetails>
      {/* Latency distribution chart, timing analysis, etc. */}
    </AccordionDetails>
  </Accordion>
</Container>
```

---

## Color Scheme

### Primary Colors
- **Success (Green)**: `#2e7d32` - For passed tests, matched detections
- **Error (Red)**: `#d32f2f` - For failed tests, unmatched detections
- **Warning (Orange)**: `#ed6c02` - For warnings like high latency
- **Info (Blue)**: `#0288d1` - For informational elements
- **Primary**: `#1976d2` - For interactive elements, selected states

### Text Colors
- **Primary Text**: `rgba(0, 0, 0, 0.87)`
- **Secondary Text**: `rgba(0, 0, 0, 0.6)`
- **Disabled Text**: `rgba(0, 0, 0, 0.38)`

### Background Colors
- **Paper**: `#ffffff`
- **Background**: `#f5f5f5`
- **Selected**: `rgba(25, 118, 210, 0.08)`
- **Hover**: `rgba(0, 0, 0, 0.04)`

---

## Typography Hierarchy

```typescript
const typography = {
  h3: {
    fontSize: '3rem',      // 48px - Main status
    fontWeight: 700,
  },
  h4: {
    fontSize: '2.125rem',  // 34px - Section headers
    fontWeight: 700,
  },
  h5: {
    fontSize: '1.5rem',    // 24px - Subsection headers
    fontWeight: 600,
  },
  h6: {
    fontSize: '1.25rem',   // 20px - Card titles
    fontWeight: 600,
  },
  subtitle1: {
    fontSize: '1rem',      // 16px - Subtitles
    fontWeight: 500,
  },
  subtitle2: {
    fontSize: '0.875rem',  // 14px - Table headers
    fontWeight: 600,
  },
  body1: {
    fontSize: '1rem',      // 16px - Body text
  },
  body2: {
    fontSize: '0.875rem',  // 14px - Secondary text
  },
  caption: {
    fontSize: '0.75rem',   // 12px - Captions
  },
}
```

---

## Spacing Guidelines

```typescript
const spacing = {
  component: 4,      // 32px - Between major sections
  card: 3,           // 24px - Card padding
  section: 3,        // 24px - Section spacing
  element: 2,        // 16px - Between elements
  tight: 1,          // 8px - Tight spacing
}
```

---

## Responsive Breakpoints

```typescript
const breakpoints = {
  xs: 0,      // Mobile
  sm: 600,    // Tablet
  md: 960,    // Small laptop
  lg: 1280,   // Desktop
  xl: 1920,   // Large desktop
}
```

**Grid Behavior**:
- **Cards**: 1 column (xs), 2 columns (sm), 4 columns (md+)
- **Video selector**: Stacked (xs/sm), 3 columns (md+)
- **Table**: Horizontal scroll on mobile, full width on desktop

---

## State Management

### Component State
```typescript
interface HILResultsState {
  // Data
  sessionData: TestSession;
  detections: Detection[];
  videos: Video[];
  groundTruthEvents: GroundTruthEvent[];

  // UI State
  selectedVideoId: string;
  sortBy: 'timestamp' | 'latency' | 'result';
  sortOrder: 'asc' | 'desc';
  page: number;
  rowsPerPage: number;

  // Computed
  testPassed: boolean;
  detectionCount: number;
  expectedCount: number;
  matchRate: number;
  averageLatency: number;
  hardwareStatus: 'active' | 'inactive' | 'error';
}
```

---

## Loading & Error States

### Loading State
```tsx
{isLoading && (
  <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
    <CircularProgress size={60} />
    <Typography variant="h6" sx={{ ml: 2 }}>
      Loading test results...
    </Typography>
  </Box>
)}
```

### Error State
```tsx
{error && (
  <Alert severity="error" sx={{ mb: 4 }}>
    <AlertTitle>Error Loading Results</AlertTitle>
    {error.message}
    <Button
      onClick={handleRetry}
      color="inherit"
      size="small"
      sx={{ mt: 1 }}
    >
      Retry
    </Button>
  </Alert>
)}
```

### Empty State
```tsx
{!isLoading && detections.length === 0 && (
  <Box sx={{ textAlign: 'center', py: 8 }}>
    <SearchOff sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
    <Typography variant="h5" color="textSecondary" gutterBottom>
      No Test Results Available
    </Typography>
    <Typography variant="body1" color="textSecondary">
      Run a HIL test to see results here
    </Typography>
    <Button
      variant="contained"
      onClick={() => navigate('/hil-test')}
      sx={{ mt: 3 }}
    >
      Run New Test
    </Button>
  </Box>
)}
```

---

## Accessibility Guidelines

1. **Keyboard Navigation**: All interactive elements must be keyboard accessible
2. **ARIA Labels**: Proper labels for screen readers
3. **Color Contrast**: Minimum 4.5:1 ratio for text
4. **Focus Indicators**: Visible focus states on all interactive elements
5. **Alt Text**: Descriptive text for icons and images

```tsx
<IconButton
  aria-label="Sort by timestamp"
  onClick={handleSort}
  onKeyDown={handleKeyDown}
>
  <SortIcon />
</IconButton>
```

---

## Animation & Transitions

```typescript
const transitions = {
  standard: '0.3s ease',
  fast: '0.15s ease',
  slow: '0.5s ease',
}
```

**Use cases**:
- Card hover: 200ms ease
- Chip appearance: 150ms ease
- Table row hover: 100ms ease
- Accordion expand: 300ms ease

---

## Implementation Checklist

### Phase 1: Core Components
- [ ] Create TestStatusBanner component
- [ ] Create MetricsSummaryCards component
- [ ] Create CleanDetectionTable component
- [ ] Create VideoSequenceSelector component

### Phase 2: Integration
- [ ] Integrate components into HILResults.tsx
- [ ] Connect to data sources (API/state)
- [ ] Implement sorting and pagination
- [ ] Add loading and error states

### Phase 3: Polish
- [ ] Add animations and transitions
- [ ] Implement responsive design
- [ ] Add accessibility features
- [ ] Test keyboard navigation
- [ ] Add empty states

### Phase 4: Testing
- [ ] Unit tests for each component
- [ ] Integration tests for page
- [ ] Visual regression tests
- [ ] Accessibility audit
- [ ] Cross-browser testing

---

## Component Dependencies

```typescript
// External Libraries
import {
  Box,
  Paper,
  Card,
  CardContent,
  Typography,
  Chip,
  Alert,
  AlertTitle,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  Grid,
  Button,
  ButtonGroup,
  IconButton,
  Tooltip,
  CircularProgress,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';

import {
  CheckCircle,
  Cancel,
  Warning,
  CheckCircleOutline,
  Timer,
  TrendingUp,
  Memory,
  VideoLibrary,
  SearchOff,
  ExpandMore,
} from '@mui/icons-material';

// React
import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

// Internal
import { api } from '../services/api';
import type {
  Detection,
  TestSession,
  Video,
  GroundTruthEvent
} from '../types';
```

---

## Performance Considerations

1. **Virtualization**: Use `react-window` for tables with >100 rows
2. **Memoization**: Memoize computed values (matchRate, averageLatency)
3. **Lazy Loading**: Load video data only when selected
4. **Debouncing**: Debounce sort/filter operations
5. **Code Splitting**: Split large components into separate chunks

```typescript
const memoizedMetrics = useMemo(() => ({
  detectionCount: detections.length,
  averageLatency: calculateAverageLatency(detections),
  matchRate: calculateMatchRate(detections, groundTruthEvents),
  testPassed: detections.every(d => d.passed),
}), [detections, groundTruthEvents]);
```

---

## Testing Strategy

### Unit Tests
```typescript
describe('TestStatusBanner', () => {
  it('should display PASS status for passed test', () => {
    render(<TestStatusBanner testPassed={true} {...props} />);
    expect(screen.getByText('✓ TEST PASSED')).toBeInTheDocument();
  });

  it('should display FAIL status for failed test', () => {
    render(<TestStatusBanner testPassed={false} {...props} />);
    expect(screen.getByText('✗ TEST FAILED')).toBeInTheDocument();
  });
});
```

### Integration Tests
```typescript
describe('HILResults Page', () => {
  it('should load and display test results', async () => {
    render(<HILResults />);
    await waitFor(() => {
      expect(screen.getByText('Detection Results')).toBeInTheDocument();
    });
  });
});
```

---

## Migration Strategy

### Step 1: Create New Components
Create all four new components in separate files under `src/components/hil-results/`

### Step 2: Feature Flag
Add feature flag to toggle between old and new UI:
```typescript
const useNewUI = import.meta.env.VITE_USE_NEW_HIL_UI === 'true';
```

### Step 3: Side-by-Side Testing
Run both UIs in parallel for comparison

### Step 4: Gradual Rollout
- Week 1: Internal testing
- Week 2: Beta users
- Week 3: Full rollout
- Week 4: Remove old components

### Step 5: Cleanup
Remove old components and legacy code

---

## Future Enhancements

1. **Export Functionality**: Export results as PDF/CSV
2. **Comparison View**: Compare multiple test runs
3. **Real-time Updates**: WebSocket for live test monitoring
4. **Advanced Filtering**: Filter by latency range, pass/fail, video
5. **Charting**: Add latency distribution charts, timeline views
6. **Annotations**: Allow users to add notes to detections
7. **Replay**: Step-by-step test replay with video sync

---

## Conclusion

This design specification provides a complete blueprint for rebuilding HILResults.tsx with a focus on clarity, usability, and modern design principles. The new UI eliminates redundancy, prioritizes critical information, and provides a clean, professional interface for reviewing HIL test results.

**Next Steps**:
1. Review and approve design specification
2. Create component files and implement structure
3. Connect to data sources and APIs
4. Add styling and interactions
5. Test thoroughly across devices and browsers
6. Deploy with feature flag for gradual rollout
