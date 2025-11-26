# Quality Metrics Integration - Executive Summary

## 🔴 Critical Finding

**The backend quality metrics system is NOT integrated with the frontend.**

Users currently have **NO VISIBILITY** into:
- Timing degradation warnings
- Data quality issues
- Validation status of detections
- Quality health metrics

This is a **user safety issue** - users may rely on unreliable results without knowing they have quality problems.

---

## What Exists vs What's Missing

### ✅ Backend (Complete)
- `/api/monitoring/quality-warnings` - Get quality warnings
- `/api/monitoring/timing-health` - Get timing health status
- `/api/video-sequences/{id}/quality-summary` - Get video quality metrics
- Quality flags on detections (`usable_for_validation`, `timing_degraded`)
- Quality levels (EXCELLENT, GOOD, FAIR, POOR)

### ❌ Frontend (Missing Everything)
- No API calls to quality endpoints
- No quality warning displays
- No quality badges on detections
- No quality filters
- No TypeScript types for quality metrics
- No dashboard quality indicators

---

## Required Changes (Priority Order)

### Priority 1: CRITICAL - User Safety (Week 1)
**3 API methods + 1 warning banner**

```typescript
// Add to api.ts:
async getQualityWarnings(sessionId: string): Promise<QualityWarning[]>
async getTimingHealth(sessionId: string): Promise<TimingHealthStatus>

// Add to HILResults.tsx:
{timingHealth?.timing_degraded && (
  <Alert severity="warning">
    ⚠️ 5 of 131 detections have degraded timing.
    Results may be less reliable.
  </Alert>
)}
```

**Impact:** Users can see when data quality is compromised
**Effort:** ~8 hours
**Files:** `/frontend/src/services/api.ts`, `/frontend/src/pages/HILResults.tsx`

### Priority 2: IMPORTANT - Detection Quality (Week 2)
**Quality badges + filters on detection cards**

```typescript
// Add to DetectionResultsPanel.tsx:
<Chip
  label={detection.usable_for_validation ? 'Validated' : 'Degraded'}
  color={detection.usable_for_validation ? 'success' : 'warning'}
/>

// Add filter:
Filter Quality: [All (131) | Validated (126) | Degraded (5)]
```

**Impact:** Users can identify and filter unreliable detections
**Effort:** ~12 hours
**Files:** `/frontend/src/components/DetectionResultsPanel.tsx`

### Priority 3: NICE-TO-HAVE - Dashboard (Week 3)
**System-wide quality metrics card**

```typescript
// Add to Dashboard.tsx:
<QualityMetricsCard>
  96.2% Validation Rate
  Quality: GOOD
  2 sessions with issues
</QualityMetricsCard>
```

**Impact:** System-wide quality visibility
**Effort:** ~4 hours
**Files:** `/frontend/src/pages/Dashboard.tsx`

---

## Quick Start Guide

### Step 1: Add TypeScript Types (30 min)

**File:** `/frontend/src/types/enhanced-results.ts`

```typescript
export interface QualityWarning {
  id: string;
  session_id: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  category: 'timing' | 'accuracy' | 'coverage' | 'system';
  message: string;
  detection_count?: number;
  created_at: string;
}

export interface TimingHealthStatus {
  session_id: string;
  timing_degraded: boolean;
  timing_verified: boolean;
  total_detections: number;
  degraded_count: number;
  quality_level: 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR';
  degradation_percentage: number;
}
```

### Step 2: Add API Methods (1 hour)

**File:** `/frontend/src/services/api.ts`

```typescript
async getQualityWarnings(sessionId: string): Promise<QualityWarning[]> {
  try {
    const response = await this.api.get(`/api/monitoring/quality-warnings`, {
      params: { session_id: sessionId }
    });
    return response.data.warnings || [];
  } catch (error) {
    console.error('Failed to fetch quality warnings:', error);
    return [];
  }
}

async getTimingHealth(sessionId: string): Promise<TimingHealthStatus> {
  const response = await this.api.get(`/api/monitoring/timing-health`, {
    params: { session_id: sessionId }
  });
  return response.data;
}

// Export new methods:
export const getQualityWarnings = apiServiceInstance.getQualityWarnings.bind(apiServiceInstance);
export const getTimingHealth = apiServiceInstance.getTimingHealth.bind(apiServiceInstance);
```

### Step 3: Add Warning Banner (2 hours)

**File:** `/frontend/src/pages/HILResults.tsx`

```typescript
import { Alert, AlertTitle, Chip } from '@mui/material';
import { apiService } from '../services/api';
import { QualityWarning, TimingHealthStatus } from '../types/enhanced-results';

const HILResults: React.FC = () => {
  // Add state:
  const [qualityWarnings, setQualityWarnings] = useState<QualityWarning[]>([]);
  const [timingHealth, setTimingHealth] = useState<TimingHealthStatus | null>(null);

  // Fetch quality data:
  useEffect(() => {
    const fetchQuality = async () => {
      if (!sessionId) return;

      try {
        const [warnings, health] = await Promise.all([
          apiService.getQualityWarnings(sessionId),
          apiService.getTimingHealth(sessionId)
        ]);

        setQualityWarnings(warnings);
        setTimingHealth(health);
      } catch (error) {
        console.error('Failed to fetch quality metrics:', error);
      }
    };

    fetchQuality();
  }, [sessionId]);

  // Add UI (before existing content):
  return (
    <Container>
      {/* Quality Warning Banner */}
      {timingHealth?.timing_degraded && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <AlertTitle>Timing Quality Warning</AlertTitle>
          {timingHealth.degraded_count} of {timingHealth.total_detections} detections
          have degraded timing accuracy. Results may be less reliable for latency analysis.

          <Box sx={{ mt: 1 }}>
            <Chip
              label={`Quality: ${timingHealth.quality_level}`}
              color={getQualityChipColor(timingHealth.quality_level)}
              size="small"
            />
            <Chip
              label={`Validation Rate: ${(100 - timingHealth.degradation_percentage).toFixed(1)}%`}
              size="small"
              sx={{ ml: 1 }}
            />
          </Box>
        </Alert>
      )}

      {/* High severity warnings */}
      {qualityWarnings.filter(w => w.severity === 'HIGH').map(warning => (
        <Alert key={warning.id} severity="error" sx={{ mb: 2 }}>
          {warning.message}
        </Alert>
      ))}

      {/* Rest of existing component... */}
    </Container>
  );
};

// Helper function:
const getQualityChipColor = (level: string): 'success' | 'warning' | 'error' => {
  switch (level) {
    case 'EXCELLENT':
    case 'GOOD':
      return 'success';
    case 'FAIR':
      return 'warning';
    case 'POOR':
      return 'error';
    default:
      return 'warning';
  }
};
```

### Step 4: Test (30 min)

```bash
# 1. Start backend with quality metrics enabled
cd backend
python manage.py runserver

# 2. Start frontend
cd ../frontend
npm start

# 3. Navigate to test session with known quality issues
# Open: http://localhost:3000/hil-results/c511302e

# 4. Verify:
# - Warning banner appears if timing_degraded=true
# - Quality level chip shows correct color
# - No errors in console
```

---

## Testing Checklist

### ✅ API Integration
- [ ] Quality warnings endpoint returns data
- [ ] Timing health endpoint returns data
- [ ] Error handling works (returns empty array on failure)
- [ ] TypeScript types match API response

### ✅ UI Display
- [ ] Warning banner shows when timing_degraded=true
- [ ] Warning banner hidden when timing_degraded=false
- [ ] Quality level chip shows correct color
- [ ] Degraded count is accurate
- [ ] Validation rate percentage is correct

### ✅ Edge Cases
- [ ] Session with no quality issues (no banner)
- [ ] Session with all detections degraded (red banner)
- [ ] API error doesn't crash page
- [ ] Loading state displays correctly

---

## Rollout Plan

### Phase 1: Internal Testing (Day 1-2)
1. Deploy to development environment
2. Test with known quality issue sessions
3. Verify warning accuracy
4. Fix any bugs

### Phase 2: Beta Testing (Day 3-5)
1. Deploy to staging environment
2. Test with real user workflows
3. Gather feedback on warning clarity
4. Adjust messaging if needed

### Phase 3: Production (Day 6-7)
1. Deploy to production
2. Monitor error logs
3. Track user feedback
4. Plan Phase 2 features (detection badges)

---

## Success Metrics

### User Awareness
- [ ] 100% of sessions with quality issues show warnings
- [ ] Warning message is clear and actionable
- [ ] No false positives (warnings when quality is good)

### Technical Quality
- [ ] API response time < 200ms
- [ ] No TypeScript errors
- [ ] No console errors
- [ ] Responsive on mobile devices

### User Satisfaction
- [ ] Users understand quality warnings
- [ ] Users can identify unreliable results
- [ ] Users report fewer issues with "bad data"

---

## Contact & Resources

**Full Audit Report:** `/backend/docs/FRONTEND_INTEGRATION_AUDIT.md`
**Backend API Docs:** `/backend/docs/QUALITY_METRICS_API.md`
**Frontend Team:** [Contact Info]
**Questions:** [Support Channel]

---

**Created:** 2025-11-19
**Last Updated:** 2025-11-19
**Status:** 🔴 Not Started
