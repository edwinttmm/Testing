# Quality Components Integration Example

This document shows **exactly** how to integrate the quality components into the HILResults page.

## Step 1: Import Components and Types

Add these imports to `/frontend/src/pages/HILResults.tsx`:

```typescript
// Quality components
import {
  QualityWarningBanner,
  DetectionQualityBadge,
  QualityFilterDropdown,
  QualityMetricsCard
} from '../components/quality';

// Quality API and types
import { qualityApi } from '../services/qualityApi';
import {
  QualityInfo,
  QualityFilterType,
  QualityFilterStats
} from '../types/quality';
```

## Step 2: Add State Variables

Add these state variables (around line 200, after existing state):

```typescript
// Quality metrics state
const [qualityInfo, setQualityInfo] = useState<QualityInfo | null>(null);
const [qualityFilter, setQualityFilter] = useState<QualityFilterType>('all');
const [loadingQuality, setLoadingQuality] = useState(false);
```

## Step 3: Fetch Quality Data

Add this useEffect hook to fetch quality data when sessionId changes:

```typescript
// Fetch quality metrics
useEffect(() => {
  const fetchQualityMetrics = async () => {
    if (!sessionId) return;

    setLoadingQuality(true);
    try {
      const quality = await qualityApi.getSessionQuality(sessionId);
      setQualityInfo(quality);
    } catch (error) {
      console.error('Failed to fetch quality metrics:', error);
    } finally {
      setLoadingQuality(false);
    }
  };

  fetchQualityMetrics();
}, [sessionId]);
```

## Step 4: Calculate Filter Statistics

Add this useMemo hook to calculate filter stats from detections:

```typescript
// Calculate quality filter statistics
const qualityFilterStats = useMemo((): QualityFilterStats => {
  if (!combinedDetections) {
    return {
      all_count: 0,
      validated_count: 0,
      degraded_count: 0,
      verified_count: 0
    };
  }

  return {
    all_count: combinedDetections.length,
    validated_count: combinedDetections.filter(d =>
      d.usable_for_validation !== false && !d.timing_degraded
    ).length,
    degraded_count: combinedDetections.filter(d =>
      d.timing_degraded === true
    ).length,
    verified_count: combinedDetections.filter(d =>
      d.timing_verified === true
    ).length
  };
}, [combinedDetections]);
```

## Step 5: Filter Detections by Quality

Update your detections filtering logic:

```typescript
// Apply quality filter to detections
const filteredDetections = useMemo(() => {
  if (!combinedDetections) return [];

  let filtered = combinedDetections;

  // Apply quality filter
  switch (qualityFilter) {
    case 'validated':
      filtered = filtered.filter(d =>
        d.usable_for_validation !== false && !d.timing_degraded
      );
      break;
    case 'degraded':
      filtered = filtered.filter(d => d.timing_degraded === true);
      break;
    case 'verified':
      filtered = filtered.filter(d => d.timing_verified === true);
      break;
    case 'all':
    default:
      // No filtering
      break;
  }

  return filtered;
}, [combinedDetections, qualityFilter]);
```

## Step 6: Add UI Components

### 6.1 Add Quality Warning Banner

Add this **AFTER** the TestStatusBanner and **BEFORE** MetricsSummaryCards (around line 450):

```tsx
{/* Quality Warning Banner */}
{qualityInfo && qualityInfo.warnings.length > 0 && (
  <QualityWarningBanner
    warnings={qualityInfo.warnings}
    qualityLevel={qualityInfo.quality_level}
    validationRate={qualityInfo.validation_rate}
    onViewDetails={() => navigate('/quality-metrics')}
    onDismiss={(warningId, permanent) => {
      console.log('Dismiss warning:', warningId, 'Permanent:', permanent);
      // TODO: Implement warning dismissal
    }}
  />
)}
```

### 6.2 Add Quality Metrics Card

Add this in the summary section (around line 480, after MetricsSummaryCards):

```tsx
{/* Quality Metrics Card */}
{qualityInfo && (
  <Box sx={{ mb: 3 }}>
    <QualityMetricsCard
      sessionId={sessionId}
      onViewDetails={() => navigate('/quality-metrics')}
      autoRefresh={false}
    />
  </Box>
)}
```

### 6.3 Add Quality Filter Dropdown

Add this **BEFORE** the detection table (around line 600):

```tsx
{/* Detection Quality Filter */}
<Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
  <Typography variant="h6">
    Detection Events ({filteredDetections.length})
  </Typography>

  <QualityFilterDropdown
    currentFilter={qualityFilter}
    filterStats={qualityFilterStats}
    onFilterChange={setQualityFilter}
    size="small"
  />
</Box>
```

### 6.4 Add Quality Badges to Detection Table

In the detection table row rendering (around line 700), add the quality badge:

```tsx
<TableRow key={detection.id}>
  {/* Existing cells... */}

  {/* Add quality badge cell */}
  <TableCell>
    <DetectionQualityBadge
      usableForValidation={detection.usable_for_validation ?? true}
      timingDegraded={detection.timing_degraded}
      timingVerified={detection.timing_verified}
      qualityScore={detection.quality_score}
      degradationReason={detection.degradation_reason}
    />
  </TableCell>

  {/* Other existing cells... */}
</TableRow>
```

And update the table header:

```tsx
<TableHead>
  <TableRow>
    {/* Existing headers... */}
    <TableCell>Quality</TableCell>
    {/* Other headers... */}
  </TableRow>
</TableHead>
```

## Step 7: Update Detection Rendering

Change your detection rendering to use `filteredDetections` instead of `combinedDetections`:

```typescript
// Before
{combinedDetections.map((detection) => (
  <DetectionTableRow key={detection.id} detection={detection} />
))}

// After
{filteredDetections.map((detection) => (
  <DetectionTableRow key={detection.id} detection={detection} />
))}
```

## Step 8: Add Loading State

Add loading indicator for quality data:

```tsx
{loadingQuality && (
  <Box sx={{ mb: 2 }}>
    <CircularProgress size={20} /> Loading quality metrics...
  </Box>
)}
```

## Complete Example: HILResults with Quality Integration

Here's what the structure should look like:

```tsx
const HILResults: React.FC = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // Existing state
  const [enhancedResults, setEnhancedResults] = useState(null);
  const [sequenceResults, setSequenceResults] = useState(null);
  const [loading, setLoading] = useState(true);

  // NEW: Quality state
  const [qualityInfo, setQualityInfo] = useState<QualityInfo | null>(null);
  const [qualityFilter, setQualityFilter] = useState<QualityFilterType>('all');
  const [loadingQuality, setLoadingQuality] = useState(false);

  // Existing useEffects...

  // NEW: Fetch quality metrics
  useEffect(() => {
    const fetchQualityMetrics = async () => {
      if (!sessionId) return;
      setLoadingQuality(true);
      try {
        const quality = await qualityApi.getSessionQuality(sessionId);
        setQualityInfo(quality);
      } catch (error) {
        console.error('Failed to fetch quality metrics:', error);
      } finally {
        setLoadingQuality(false);
      }
    };
    fetchQualityMetrics();
  }, [sessionId]);

  // NEW: Calculate filter stats
  const qualityFilterStats = useMemo(() => ({
    all_count: combinedDetections?.length || 0,
    validated_count: combinedDetections?.filter(d => d.usable_for_validation !== false).length || 0,
    degraded_count: combinedDetections?.filter(d => d.timing_degraded).length || 0,
    verified_count: combinedDetections?.filter(d => d.timing_verified).length || 0
  }), [combinedDetections]);

  // NEW: Filter detections by quality
  const filteredDetections = useMemo(() => {
    if (!combinedDetections) return [];
    switch (qualityFilter) {
      case 'validated':
        return combinedDetections.filter(d => d.usable_for_validation !== false);
      case 'degraded':
        return combinedDetections.filter(d => d.timing_degraded === true);
      case 'verified':
        return combinedDetections.filter(d => d.timing_verified === true);
      default:
        return combinedDetections;
    }
  }, [combinedDetections, qualityFilter]);

  return (
    <Container>
      {/* Existing header/navigation */}

      {/* Existing TestStatusBanner */}
      <TestStatusBanner status={sessionStatus} />

      {/* NEW: Quality Warning Banner */}
      {qualityInfo && qualityInfo.warnings.length > 0 && (
        <QualityWarningBanner
          warnings={qualityInfo.warnings}
          qualityLevel={qualityInfo.quality_level}
          validationRate={qualityInfo.validation_rate}
          onViewDetails={() => navigate('/quality-metrics')}
        />
      )}

      {/* Existing MetricsSummaryCards */}
      <MetricsSummaryCards data={enhancedResults} />

      {/* NEW: Quality Metrics Card */}
      {qualityInfo && (
        <QualityMetricsCard
          sessionId={sessionId}
          onViewDetails={() => navigate('/quality-metrics')}
        />
      )}

      {/* Existing timeline/charts */}
      <FrameCorrelationTimeline data={correlationData} />

      {/* NEW: Quality Filter + Detection Table */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Detection Events ({filteredDetections.length})
          </Typography>
          <QualityFilterDropdown
            currentFilter={qualityFilter}
            filterStats={qualityFilterStats}
            onFilterChange={setQualityFilter}
          />
        </Box>

        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Time</TableCell>
              <TableCell>Frame</TableCell>
              <TableCell>Quality</TableCell> {/* NEW */}
              <TableCell>Confidence</TableCell>
              <TableCell>Latency</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredDetections.map((detection) => (
              <TableRow key={detection.id}>
                <TableCell>{detection.timestamp}</TableCell>
                <TableCell>{detection.frame_number}</TableCell>
                <TableCell>
                  {/* NEW: Quality Badge */}
                  <DetectionQualityBadge
                    usableForValidation={detection.usable_for_validation ?? true}
                    timingDegraded={detection.timing_degraded}
                    timingVerified={detection.timing_verified}
                  />
                </TableCell>
                <TableCell>{detection.confidence}</TableCell>
                <TableCell>{detection.latency_ms}ms</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Container>
  );
};
```

## Testing the Integration

After integration, verify:

1. ✅ Quality warning banner appears when there are timing issues
2. ✅ Quality metrics card shows validation rate and quality level
3. ✅ Filter dropdown shows correct counts
4. ✅ Filtering works (click "Degraded" shows only degraded detections)
5. ✅ Quality badges appear on each detection row
6. ✅ Tooltips show detailed quality information
7. ✅ "View Details" buttons navigate to quality dashboard
8. ✅ Quality data refreshes when session changes

## Troubleshooting

**No quality data shows up:**
- Check browser console for API errors
- Verify backend endpoints exist: `/api/monitoring/quality-warnings`, `/api/monitoring/timing-health`
- Check that `sessionId` is defined and valid

**Filter not working:**
- Verify detection objects have `usable_for_validation`, `timing_degraded`, `timing_verified` fields
- Check console for JavaScript errors
- Make sure you're using `filteredDetections` not `combinedDetections`

**Badges not showing:**
- Verify detection data has quality flags
- Check that DetectionQualityBadge is imported correctly
- Inspect table structure with browser DevTools

**Components not styling correctly:**
- Ensure Material-UI theme is configured
- Check that all imports are correct
- Verify CSS-in-JS styles are rendering

---

**Integration complete! Quality metrics now visible in HIL Results.**
