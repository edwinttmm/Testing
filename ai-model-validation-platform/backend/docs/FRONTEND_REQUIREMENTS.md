# Frontend Integration Requirements

**Project**: AI Model Validation Platform - Frontend Integration
**Date**: 2025-11-19
**Status**: TEMPLATE - Will be populated based on backend changes

---

## Overview

This document specifies frontend changes required to integrate with new backend features and APIs. It provides TypeScript interfaces, component requirements, and integration guidelines.

**Target Audience**: Frontend developers integrating with backend changes

---

## 1. API Client Updates

### 1.1 New API Endpoints

#### Monitoring API

**Base Path**: `/api/monitoring`

**Endpoints**: *Will be populated from backend agent findings*

```typescript
// Example - Will be replaced with actual endpoints

export interface MonitoringApi {
  // GET /api/monitoring/health
  getHealth(): Promise<HealthResponse>;

  // GET /api/monitoring/metrics
  getMetrics(params?: MetricsQuery): Promise<MetricsResponse>;

  // GET /api/monitoring/services
  getServiceStatus(): Promise<ServiceStatus[]>;
}
```

#### Quality API

**Base Path**: `/api/quality`

**Endpoints**: *Will be populated from backend agent findings*

```typescript
// Example - Will be replaced with actual endpoints

export interface QualityApi {
  // GET /api/quality/warnings
  getWarnings(filters?: WarningFilters): Promise<QualityWarning[]>;

  // GET /api/quality/warnings/{id}
  getWarningById(id: string): Promise<QualityWarning>;

  // POST /api/quality/thresholds
  updateThresholds(thresholds: QualityThresholds): Promise<void>;
}
```

### 1.2 TypeScript Interfaces

#### Monitoring Types

**File**: `frontend/src/types/monitoring.ts`

```typescript
// TEMPLATE - Will be populated with actual types

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: ServiceHealth[];
  version: string;
}

export interface ServiceHealth {
  name: string;
  status: 'up' | 'down';
  latency?: number;
  lastCheck: string;
}

export interface MetricsResponse {
  timestamp: string;
  metrics: {
    cpu: number;
    memory: number;
    requests: RequestMetrics;
    database: DatabaseMetrics;
  };
}

export interface RequestMetrics {
  total: number;
  successful: number;
  failed: number;
  averageLatency: number;
}

export interface DatabaseMetrics {
  connections: number;
  queries: number;
  averageQueryTime: number;
}

export interface MetricsQuery {
  startTime?: string;
  endTime?: string;
  interval?: '1m' | '5m' | '15m' | '1h';
  services?: string[];
}
```

#### Quality Types

**File**: `frontend/src/types/quality.ts`

```typescript
// TEMPLATE - Will be populated with actual types

export interface QualityWarning {
  id: string;
  type: 'low_quality' | 'poor_performance' | 'data_anomaly';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: Record<string, any>;
  timestamp: string;
  resolved: boolean;
  videoId?: string;
  sessionId?: string;
}

export interface WarningFilters {
  severity?: QualityWarning['severity'][];
  type?: QualityWarning['type'][];
  resolved?: boolean;
  videoId?: string;
  sessionId?: string;
  startDate?: string;
  endDate?: string;
}

export interface QualityThresholds {
  minConfidence: number;
  minIoU: number;
  maxFrameSkip: number;
  minFrameRate: number;
}
```

### 1.3 API Client Implementation

**File**: `frontend/src/api/monitoring.ts`

```typescript
// TEMPLATE - Will be populated with actual implementation

import axios from 'axios';
import { HealthResponse, MetricsResponse, MetricsQuery, ServiceStatus } from '@/types/monitoring';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const monitoringApi = {
  async getHealth(): Promise<HealthResponse> {
    const response = await axios.get(`${API_BASE}/api/monitoring/health`);
    return response.data;
  },

  async getMetrics(query?: MetricsQuery): Promise<MetricsResponse> {
    const response = await axios.get(`${API_BASE}/api/monitoring/metrics`, {
      params: query
    });
    return response.data;
  },

  async getServiceStatus(): Promise<ServiceStatus[]> {
    const response = await axios.get(`${API_BASE}/api/monitoring/services`);
    return response.data;
  }
};
```

**File**: `frontend/src/api/quality.ts`

```typescript
// TEMPLATE - Will be populated with actual implementation

import axios from 'axios';
import { QualityWarning, WarningFilters, QualityThresholds } from '@/types/quality';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const qualityApi = {
  async getWarnings(filters?: WarningFilters): Promise<QualityWarning[]> {
    const response = await axios.get(`${API_BASE}/api/quality/warnings`, {
      params: filters
    });
    return response.data;
  },

  async getWarningById(id: string): Promise<QualityWarning> {
    const response = await axios.get(`${API_BASE}/api/quality/warnings/${id}`);
    return response.data;
  },

  async updateThresholds(thresholds: QualityThresholds): Promise<void> {
    await axios.post(`${API_BASE}/api/quality/thresholds`, thresholds);
  }
};
```

---

## 2. UI Components

### 2.1 Quality Warning Display

**Component**: `QualityWarningBanner`

**Purpose**: Display quality warnings prominently in the UI

**Location**: `frontend/src/components/QualityWarningBanner.tsx`

**Props**:
```typescript
interface QualityWarningBannerProps {
  warnings: QualityWarning[];
  onDismiss?: (warningId: string) => void;
  onViewDetails?: (warningId: string) => void;
  maxVisible?: number;
}
```

**Wireframe**:
```
┌─────────────────────────────────────────────────────────┐
│ ⚠ Quality Warning (2 active)                      [×]   │
│                                                          │
│ [!] High: Video quality below threshold (0.75)          │
│     Session: ABC123 | Video: video_001.mp4              │
│     [View Details] [Dismiss]                            │
│                                                          │
│ [!] Medium: Frame rate inconsistent (24→18 fps)         │
│     Session: ABC123 | Video: video_002.mp4              │
│     [View Details] [Dismiss]                            │
└─────────────────────────────────────────────────────────┘
```

**Implementation Example**:
```tsx
// TEMPLATE - Basic structure

import React from 'react';
import { QualityWarning } from '@/types/quality';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';

export const QualityWarningBanner: React.FC<QualityWarningBannerProps> = ({
  warnings,
  onDismiss,
  onViewDetails,
  maxVisible = 3
}) => {
  const getSeverityColor = (severity: string) => {
    // Color mapping
  };

  return (
    <div className="quality-warnings">
      {warnings.slice(0, maxVisible).map(warning => (
        <Alert key={warning.id} variant={getSeverityColor(warning.severity)}>
          <AlertTitle>{warning.type}: {warning.message}</AlertTitle>
          <AlertDescription>
            {/* Warning details */}
          </AlertDescription>
        </Alert>
      ))}
    </div>
  );
};
```

### 2.2 Monitoring Dashboard Widget

**Component**: `MonitoringDashboard`

**Purpose**: Display system health and metrics

**Location**: `frontend/src/components/MonitoringDashboard.tsx`

**Props**:
```typescript
interface MonitoringDashboardProps {
  refreshInterval?: number; // milliseconds
  showServices?: boolean;
  showMetrics?: boolean;
}
```

**Wireframe**:
```
┌─────────────────────────────────────────────────────────┐
│ System Health                              ● Healthy    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Services Status:                                         │
│ ✓ Database         Latency: 12ms                        │
│ ✓ Detection        Latency: 245ms                       │
│ ✓ Storage          Latency: 8ms                         │
│ ✓ Quality Analyzer Latency: 156ms                       │
│                                                          │
│ Performance Metrics:                                     │
│ CPU: [=========>          ] 45%                          │
│ Memory: [=============>   ] 67%                          │
│ Requests/sec: 42.3                                       │
│ Avg Latency: 189ms                                       │
│                                                          │
│                                  [View Full Dashboard]  │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Performance Metrics Chart

**Component**: `PerformanceChart`

**Purpose**: Visualize performance metrics over time

**Location**: `frontend/src/components/PerformanceChart.tsx`

**Props**:
```typescript
interface PerformanceChartProps {
  metric: 'latency' | 'throughput' | 'errors';
  timeRange: '1h' | '24h' | '7d' | '30d';
  services?: string[];
}
```

---

## 3. State Management Updates

### 3.1 Redux/Context Updates

**File**: `frontend/src/store/monitoringSlice.ts`

```typescript
// TEMPLATE - Redux Toolkit example

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { monitoringApi } from '@/api/monitoring';
import { HealthResponse, MetricsResponse } from '@/types/monitoring';

interface MonitoringState {
  health: HealthResponse | null;
  metrics: MetricsResponse | null;
  loading: boolean;
  error: string | null;
}

export const fetchHealth = createAsyncThunk(
  'monitoring/fetchHealth',
  async () => {
    return await monitoringApi.getHealth();
  }
);

export const fetchMetrics = createAsyncThunk(
  'monitoring/fetchMetrics',
  async (query?: MetricsQuery) => {
    return await monitoringApi.getMetrics(query);
  }
);

const monitoringSlice = createSlice({
  name: 'monitoring',
  initialState: /* ... */,
  reducers: { /* ... */ },
  extraReducers: (builder) => {
    // Handle async actions
  }
});
```

**File**: `frontend/src/store/qualitySlice.ts`

```typescript
// TEMPLATE - Redux Toolkit example for quality warnings

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { qualityApi } from '@/api/quality';
import { QualityWarning, WarningFilters } from '@/types/quality';

interface QualityState {
  warnings: QualityWarning[];
  activeWarnings: QualityWarning[];
  filters: WarningFilters;
  loading: boolean;
  error: string | null;
}

export const fetchWarnings = createAsyncThunk(
  'quality/fetchWarnings',
  async (filters?: WarningFilters) => {
    return await qualityApi.getWarnings(filters);
  }
);

const qualitySlice = createSlice({
  name: 'quality',
  initialState: /* ... */,
  reducers: { /* ... */ },
  extraReducers: (builder) => {
    // Handle async actions
  }
});
```

---

## 4. Integration Points

### 4.1 Video Upload Flow

**Change Required**: Add quality validation feedback during upload

**Current Flow**:
```
User uploads video → Backend processes → Success/Error response
```

**New Flow**:
```
User uploads video → Backend processes → Quality check →
Warning if quality < threshold → User confirmation → Continue
```

**Components Affected**:
- `VideoUploadForm.tsx`
- `UploadProgressIndicator.tsx`

**New Props**:
```typescript
interface VideoUploadFormProps {
  // ... existing props
  onQualityWarning?: (warning: QualityWarning) => void;
  qualityThreshold?: number;
}
```

### 4.2 Results Dashboard

**Change Required**: Display quality warnings with test results

**Components Affected**:
- `ResultsDashboard.tsx`
- `ResultsTable.tsx`
- `ResultsDetailView.tsx`

**New Sections**:
- Quality warnings summary card
- Per-result quality indicators
- Quality trend charts

### 4.3 Test Session View

**Change Required**: Show real-time monitoring during test execution

**Components Affected**:
- `TestSessionView.tsx`
- `SessionMonitor.tsx`

**New Features**:
- Real-time health status
- Performance metrics live updates
- Quality warnings as they occur

---

## 5. Styling Updates

### 5.1 Warning Severity Colors

**File**: `frontend/src/styles/theme.ts`

```typescript
// Add to theme
export const qualityWarningColors = {
  critical: '#DC2626', // Red 600
  high: '#F59E0B',     // Amber 500
  medium: '#3B82F6',   // Blue 500
  low: '#10B981'       // Green 500
};
```

### 5.2 Component Styles

**File**: `frontend/src/components/QualityWarningBanner.module.css`

```css
/* TEMPLATE - Basic styling */

.warning-banner {
  position: fixed;
  top: 64px; /* Below navbar */
  left: 0;
  right: 0;
  z-index: 1000;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.warning-item {
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border-radius: 0.5rem;
  border-left: 4px solid var(--severity-color);
}

.warning-critical {
  --severity-color: #DC2626;
  background: #FEE2E2;
}

.warning-high {
  --severity-color: #F59E0B;
  background: #FEF3C7;
}

/* ... more styles */
```

---

## 6. Testing Requirements

### 6.1 Unit Tests

**New Test Files Required**:

- `frontend/src/api/monitoring.test.ts`
- `frontend/src/api/quality.test.ts`
- `frontend/src/components/QualityWarningBanner.test.tsx`
- `frontend/src/components/MonitoringDashboard.test.tsx`

**Test Coverage Required**:
- API client methods
- Component rendering with various props
- User interactions (dismiss, view details)
- Error states
- Loading states

### 6.2 Integration Tests

**Scenarios to Test**:

1. **Quality Warning Display**:
   - Warnings appear when API returns them
   - Dismissing a warning removes it from UI
   - Clicking "View Details" navigates correctly

2. **Monitoring Dashboard**:
   - Metrics update at specified interval
   - Service status reflects backend state
   - Dashboard handles connection errors gracefully

3. **Upload Flow with Quality Check**:
   - Quality warning displays if threshold not met
   - User can proceed or cancel after warning
   - Upload completes successfully

### 6.3 E2E Tests

**Cypress Tests Required**:

```typescript
// frontend/cypress/e2e/quality-warnings.cy.ts

describe('Quality Warnings', () => {
  it('displays quality warnings when present', () => {
    // Test implementation
  });

  it('allows user to dismiss warnings', () => {
    // Test implementation
  });

  it('shows warning details on click', () => {
    // Test implementation
  });
});
```

---

## 7. Migration Guide

### 7.1 Step-by-Step Frontend Integration

#### Phase 1: Type Definitions (Day 1)
1. Create `types/monitoring.ts`
2. Create `types/quality.ts`
3. Update `types/index.ts` to export new types

#### Phase 2: API Clients (Day 1-2)
1. Create `api/monitoring.ts`
2. Create `api/quality.ts`
3. Add unit tests for API clients
4. Test against local backend

#### Phase 3: State Management (Day 2-3)
1. Create `store/monitoringSlice.ts`
2. Create `store/qualitySlice.ts`
3. Update root store configuration
4. Add unit tests for slices

#### Phase 4: UI Components (Day 3-5)
1. Create `QualityWarningBanner` component
2. Create `MonitoringDashboard` component
3. Create `PerformanceChart` component
4. Add component unit tests
5. Test in Storybook

#### Phase 5: Integration (Day 5-7)
1. Integrate warnings into existing views
2. Add monitoring dashboard to admin area
3. Update upload flow with quality checks
4. Add integration tests

#### Phase 6: Testing & Polish (Day 7-10)
1. Complete E2E test suite
2. Perform cross-browser testing
3. Accessibility audit
4. Performance optimization
5. Documentation updates

---

## 8. Dependencies

### 8.1 New npm Packages Required

```json
{
  "dependencies": {
    "recharts": "^2.10.0",  // For performance charts
    "@radix-ui/react-alert": "^1.0.0",  // For warning banners
    // ... other UI libraries as needed
  },
  "devDependencies": {
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    // ... testing libraries
  }
}
```

### 8.2 Installation

```bash
cd frontend
npm install recharts @radix-ui/react-alert
npm install --save-dev @testing-library/react @testing-library/jest-dom
```

---

## 9. Configuration Updates

### 9.1 Environment Variables

**File**: `frontend/.env`

```bash
# Add new environment variables
REACT_APP_MONITORING_ENABLED=true
REACT_APP_QUALITY_WARNINGS_ENABLED=true
REACT_APP_METRICS_REFRESH_INTERVAL=30000  # 30 seconds
REACT_APP_QUALITY_WARNING_THRESHOLD=0.80
```

### 9.2 Build Configuration

**File**: `frontend/package.json`

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:e2e": "cypress run",
    "test:e2e:open": "cypress open"
  }
}
```

---

## 10. Documentation Updates

### 10.1 Files to Update

- [ ] `frontend/README.md` - Add new features
- [ ] `frontend/docs/API.md` - Document new API clients
- [ ] `frontend/docs/COMPONENTS.md` - Document new components
- [ ] `frontend/docs/STATE.md` - Document state management changes

### 10.2 Storybook Stories

Create Storybook stories for:
- `QualityWarningBanner.stories.tsx`
- `MonitoringDashboard.stories.tsx`
- `PerformanceChart.stories.tsx`

---

## 11. Rollout Plan

### 11.1 Feature Flags

Consider using feature flags for gradual rollout:

```typescript
// frontend/src/config/features.ts

export const featureFlags = {
  qualityWarnings: process.env.REACT_APP_QUALITY_WARNINGS_ENABLED === 'true',
  monitoringDashboard: process.env.REACT_APP_MONITORING_ENABLED === 'true',
  performanceCharts: process.env.REACT_APP_PERFORMANCE_CHARTS_ENABLED === 'true'
};
```

### 11.2 Rollout Phases

1. **Phase 1 (Internal)**: Enable for development team
2. **Phase 2 (Beta)**: Enable for select beta users
3. **Phase 3 (Production)**: Enable for all users

---

## 12. Known Limitations

*Will be populated based on backend limitations and agent findings*

- List any constraints
- Document workarounds
- Note future improvements planned

---

## 13. Support & Resources

### 13.1 Contact Points

- **Backend Integration**: Backend development team
- **API Questions**: System architect
- **UI/UX Guidance**: Design team

### 13.2 Useful Links

- Backend API documentation: `/backend/docs/API_documentation.md`
- Architecture diagrams: `/backend/docs/architecture_design_document.md`
- Integration verification: `/backend/scripts/verify_integration.py`

---

**Document Version**: 1.0.0 (Template)
**Status**: Waiting for backend agent findings to populate specific requirements
**Last Updated**: 2025-11-19
**Next Review**: After agent completions
