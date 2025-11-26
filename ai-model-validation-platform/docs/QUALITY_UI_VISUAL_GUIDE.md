# Quality UI Components - Visual Guide

This document shows what each quality component looks like in the UI.

---

## 1. QualityWarningBanner

### Timing Warning (Yellow/Warning)
```
┌─────────────────────────────────────────────────────────────────────┐
│ ⚠️ Timing Quality Warning                                  [✕]      │
│                                                                      │
│ 5 of 131 detections have degraded timing accuracy.                 │
│ Results may be less reliable for latency analysis.                 │
│                                                                      │
│ [Quality: GOOD] [Validation Rate: 96.2%] [5 Critical Issues]      │
│                                                                      │
│ Recommendation: Review detections with high latency variance       │
│                                                                      │
│ [Show All Warnings ▼]                  [View Details]              │
│                                                                      │
│ ☐ Don't show this type of warning again                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Critical Warning (Red/Error)
```
┌─────────────────────────────────────────────────────────────────────┐
│ ❌ System Quality Warning (3 issues)                      [✕]      │
│                                                                      │
│ Critical timing degradation detected. Over 20% of detections       │
│ have unreliable timing data.                                       │
│                                                                      │
│ [Quality: POOR] [Validation Rate: 78.5%] [3 Critical Issues]      │
│                                                                      │
│ Impact: Results accuracy significantly reduced                      │
│ Recommendation: Review hardware timing synchronization             │
│                                                                      │
│ [Hide All Warnings ▲]  [Take Action]  [View Details]              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. DetectionQualityBadge

### Validated Detection (Green)
```
┌─────────────────┐
│ ✓ Validated ✓  │ → Green background
└─────────────────┘
   Tooltip: "✓ Timing verified with ground truth\nQuality Score: 98.5%"
```

### Degraded Detection (Yellow)
```
┌─────────────────┐
│ ⚠️ Degraded     │ → Yellow/orange background
└─────────────────┘
   Tooltip: "⚠️ Timing accuracy degraded\nReason: High latency variance\n⚡ May affect result accuracy"
```

### Unusable Detection (Red)
```
┌─────────────────┐
│ ❌ Not Usable   │ → Red background
└─────────────────┘
   Tooltip: "❌ Not usable for validation\nReason: Timing sync failed\n⚡ May affect result accuracy"
```

---

## 3. QualityFilterDropdown

### Dropdown Closed
```
┌──────────────────────────────────────┐
│ Filter by Quality           ▼        │
│ ∞ All Detections (131)               │
└──────────────────────────────────────┘
```

### Dropdown Open
```
┌──────────────────────────────────────┐
│ Filter by Quality           ▲        │
├──────────────────────────────────────┤
│ ∞ All Detections            [131]   │
│ ✓ Validated                 [126]   │ ← Green chip
│ ⚠️ Degraded Timing           [5]    │ ← Orange chip
│ ✓ GT Verified               [66]    │ ← Blue chip
└──────────────────────────────────────┘

⚠️ 5 detections with timing issues
```

### Chip-Based Alternative
```
[All (131)] [Validated (126)] [Degraded (5)] [Verified (66)]
   ↑           ↑ green          ↑ orange       ↑ blue
 selected
```

---

## 4. QualityMetricsCard

### Card View
```
┌──────────────────────────────────────────────┐
│ Data Quality                      [↻]        │
│                                               │
│       96.2%                                   │
│    Validation Rate                            │
│ ████████████████████░░░░                     │
│                                               │
│ [Quality: GOOD] 🟢                           │
│                                               │
│ Usable    Degraded    Total                  │
│   126         5        131                    │
│  green     orange                             │
│                                               │
│ ⚠️ 2 critical issues detected                │
│                                               │
│ [Show Details ▼]  [Full Report]              │
└──────────────────────────────────────────────┘
```

### Expanded Details
```
┌──────────────────────────────────────────────┐
│ Data Quality                      [↻]        │
│                                               │
│       96.2%                                   │
│    Validation Rate                            │
│ ████████████████████░░░░                     │
│                                               │
│ [Quality: GOOD] 🟢                           │
│                                               │
│ Usable    Degraded    Total                  │
│   126         5        131                    │
│                                               │
│ ──────────────────────────────────────       │
│                                               │
│ Timing Degraded:           No                │
│ Timing Verified:           Yes               │
│ Degradation Rate:          3.8%              │
│ Verified Count:            66                │
│                                               │
│ [Hide Details ▲]  [Full Report]              │
└──────────────────────────────────────────────┘
```

---

## 5. QualityMetricsDashboard

### Full Dashboard Layout
```
┌───────────────────────────────────────────────────────────────────┐
│ ← Quality Metrics Dashboard          [Export] [Refresh]          │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│ │Overall   │ │Total     │ │Issues    │ │Active    │            │
│ │Quality   │ │Sessions  │ │          │ │Warnings  │            │
│ │          │ │          │ │          │ │          │            │
│ │  GOOD    │ │   45     │ │    2     │ │    3     │            │
│ │ [GOOD]   │ │          │ │   ⚠️     │ │   ❌     │            │
│ │ 92.3%    │ │ 2,145    │ │  4.4%    │ │          │            │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│                                                                    │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│ ┌─────────────────────┐ ┌─────────────────────┐                 │
│ │ Quality             │ │ Recent              │                 │
│ │ Distribution        │ │ Warnings            │                 │
│ │                     │ │                     │                 │
│ │ Excellent           │ │ ⚠️ Timing degraded  │                 │
│ │ ████████████  25    │ │    in session A45   │                 │
│ │                     │ │                     │                 │
│ │ Good                │ │ ⚠️ Low coverage     │                 │
│ │ ███████       15    │ │    in session B12   │                 │
│ │                     │ │                     │                 │
│ │ Fair                │ │ ❌ Critical timing  │                 │
│ │ ██            4     │ │    in session C89   │                 │
│ │                     │ │                     │                 │
│ │ Poor                │ │ [View All →]        │                 │
│ │ █             1     │ │                     │                 │
│ └─────────────────────┘ └─────────────────────┘                 │
│                                                                    │
├───────────────────────────────────────────────────────────────────┤
│ [Trends] [Warnings History] [Settings]                           │
├───────────────────────────────────────────────────────────────────┤
│ (Tab content shows here)                                          │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

---

## 6. HILResults with Quality Integration

### Full Page with All Components
```
┌───────────────────────────────────────────────────────────────────┐
│ ← HIL Test Results - Session c511302e                            │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│ [✓ Session Completed] [45 minutes ago]                           │
│                                                                    │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ ⚠️ Timing Quality Warning                          [✕]     │  │
│ │                                                              │  │
│ │ 5 of 131 detections have degraded timing accuracy.         │  │
│ │                                                              │  │
│ │ [Quality: GOOD] [Validation Rate: 96.2%]                   │  │
│ │ [View Details]                                              │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                     │
│ │ F1     │ │Precision│ │ Recall │ │Latency │                     │
│ │ 94.5%  │ │  96.2%  │ │ 92.8%  │ │ 45.2ms │                     │
│ └────────┘ └────────┘ └────────┘ └────────┘                     │
│                                                                    │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ Data Quality                                      [↻]      │  │
│ │                                                              │  │
│ │       96.2%                                                  │  │
│ │    Validation Rate                                           │  │
│ │ ████████████████████░░░░                                    │  │
│ │ [Quality: GOOD] 🟢                                          │  │
│ │ Usable: 126  Degraded: 5  Total: 131                       │  │
│ │ [Show Details ▼]                                            │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ [Timeline Chart]                                                   │
│                                                                    │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ Detection Events (131)          [Filter: All (131) ▼]     │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ Time    Frame  Quality        Confidence  Latency          │  │
│ ├─────────────────────────────────────────────────────────────┤  │
│ │ 2.54s   123    [✓ Validated]  95.3%      45.2ms           │  │
│ │ 3.12s   187    [✓ Validated]  92.8%      47.1ms           │  │
│ │ 5.21s   312    [⚠️ Degraded]   87.5%      125.3ms          │  │
│ │ 6.88s   412    [✓ Validated]  94.1%      44.8ms           │  │
│ │ ...                                                          │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

---

## Color Scheme

### Quality Levels
- **EXCELLENT**: Dark green (#2e7d32) on light green background (#e8f5e9)
- **GOOD**: Medium green (#558b2f) on pale green background (#f1f8e9)
- **FAIR**: Orange (#f57c00) on pale orange background (#fff3e0)
- **POOR**: Red (#c62828) on pale red background (#ffebee)

### Severity Levels
- **CRITICAL/HIGH**: Red error alert
- **MEDIUM**: Yellow/orange warning alert
- **LOW/INFO**: Blue info alert

### Badges
- **Validated**: Green with checkmark icon
- **Degraded**: Orange with warning icon
- **Not Usable**: Red with error icon

---

## Responsive Behavior

### Desktop (1200px+)
- 4-column grid for metric cards
- Side-by-side quality distribution and warnings
- Full-width table with all columns

### Tablet (768px-1199px)
- 2-column grid for metric cards
- Stacked quality distribution and warnings
- Scrollable table

### Mobile (< 768px)
- Single column layout
- Compact badges and chips
- Swipeable table
- Collapsed filters by default

---

## Accessibility Features

### ARIA Labels
- All buttons have `aria-label`
- Form controls have proper labels
- Tables have proper headers
- Alerts have appropriate roles

### Keyboard Navigation
- Tab through all interactive elements
- Enter/Space to activate buttons
- Arrow keys in dropdowns
- Escape to close modals/expansions

### Screen Reader Support
- Meaningful alt text
- Proper heading hierarchy
- Status announcements
- Error messages clearly associated

---

**All components are production-ready and meet WCAG 2.1 AA standards!**
