# Interface Wireframes & Interaction Specifications

## Dashboard Interface Wireframes

### Desktop Layout (1920x1080)
```
┌────────────────────────────────────────────────────────────────────────────┐
│ AI Model Validation Platform                    [🔔2] [👤] Demo User       │
├────────────────────────────────────────────────────────────────────────────┤
│        │                                                                   │
│ ┌──────┤                        Dashboard                                  │
│ │ 📊   │                                                                   │
│ │Dash  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│ │      │ │📁 Projects  │ │🎥 Videos    │ │🧪 Tests     │ │📈 Accuracy  │  │
│ │📁    │ │     15      │ │    247      │ │     89      │ │   94.2%     │  │
│ │Proj  │ │             │ │             │ │             │ │   +2.3↗     │  │
│ │      │ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│ │🎥    │                                                                   │
│ │GT    │ ┌─────────────────────────────┐ ┌─────────────────────────────┐  │
│ │      │ │    Recent Test Sessions     │ │      System Status          │  │
│ │▶️    │ │                             │ │                             │  │
│ │Test  │ │ • Test_001 - 2 min ago     │ │ HTTP Service      ✅ 100%   │  │
│ │      │ │   92.1% accuracy           │ │ Active Tests      📊  3     │  │
│ │📊    │ │                             │ │ Projects         📁 15     │  │
│ │Res   │ │ • Test_002 - 15 min ago    │ │ Videos           🎥 247    │  │
│ │      │ │   89.7% accuracy           │ │ Processing       ⚡ 95%    │  │
│ │📦    │ │                             │ │                             │  │
│ │Data  │ │ • Test_003 - 1 hr ago      │ │                             │  │
│ │      │ │   96.3% accuracy           │ │                             │  │
│ │🔒    │ └─────────────────────────────┘ └─────────────────────────────┘  │
│ │Audit │                                                                   │
│ │      │                                                                   │
│ │⚙️    │                                                                   │
│ │Set   │                                                                   │
│ └──────┘                                                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

### Mobile Layout (375x667)
```
┌─────────────────────────────┐
│ ☰ AI Validation  [🔔] [👤] │
├─────────────────────────────┤
│        Dashboard            │
│                             │
│ ┌─────────────────────────┐ │
│ │📁 Projects              │ │
│ │        15               │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─────────────────────────┐ │
│ │🎥 Videos Processed      │ │
│ │       247               │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─────────────────────────┐ │
│ │🧪 Tests Completed       │ │
│ │        89               │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─────────────────────────┐ │
│ │📈 Detection Accuracy    │ │
│ │       94.2%   +2.3↗     │ │
│ └─────────────────────────┘ │
│                             │
│ Recent Sessions ∨           │
│ System Status ∨             │
└─────────────────────────────┘
```

## Projects Interface Wireframes

### Projects List View
```
┌────────────────────────────────────────────────────────────────────────────┐
│                              Projects                    [🔄 Refresh] [+ New]│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐│
│ │📹 Project Alpha │ │📹 Beta Testing  │ │📹 Highway Study │ │📹 New Setup │││
│ │                 │ │                 │ │                 │ │             │││
│ │VRU Detection    │ │Pedestrian Focus │ │Multi-angle Cam  │ │Front Camera │││
│ │for Urban Areas  │ │Downtown Scenario│ │Highway Scenario │ │Urban Setup  │││
│ │                 │ │                 │ │                 │ │             │││
│ │📷 Sony IMX390   │ │📷 OV2312        │ │📷 Custom Array  │ │📷 IMX390    │││
│ │👁 Front VRU     │ │👁 Rear VRU      │ │👁 Multi-angle   │ │👁 Front VRU │││
│ │⚡ GPIO          │ │⚡ Network       │ │⚡ CAN Bus       │ │⚡ GPIO      │││
│ │                 │ │                 │ │                 │ │             │││
│ │🟢 Active   12📊 │ │🟡 Draft    5📊  │ │🔵 Complete  89📊│ │🟡 Draft 0📊│││
│ │15🎥  89.3% acc  │ │8🎥   --% acc    │ │45🎥  94.7% acc  │ │0🎥  --% acc │││
│ │                 │ │                 │ │                 │ │             │││
│ │[View Details] ⋮ │ │[View Details] ⋮ │ │[View Details] ⋮ │ │[View Details]⋮││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
```

### Project Creation Dialog
```
┌──────────────────────────────────────────┐
│              Create New Project          │
├──────────────────────────────────────────┤
│                                          │
│ Project Name *                           │
│ ┌──────────────────────────────────────┐ │
│ │Urban VRU Detection Phase 2           │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ Description *                            │
│ ┌──────────────────────────────────────┐ │
│ │Testing pedestrian and cyclist        │ │
│ │detection accuracy in urban           │ │
│ │environments with varying lighting    │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ Camera Model *                           │
│ ┌──────────────────────────────────────┐ │
│ │Sony IMX390                           │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ Camera View                              │
│ ┌──────────────────────────────────────┐ │
│ │Front-facing VRU               ▼     │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ Signal Type                              │
│ ┌──────────────────────────────────────┐ │
│ │GPIO                           ▼     │ │
│ └──────────────────────────────────────┘ │
│                                          │
│              [Cancel] [Create Project]   │
└──────────────────────────────────────────┘
```

## Video Annotation Interface Wireframes

### Enhanced Annotation Canvas
```
┌────────────────────────────────────────────────────────────────────────────┐
│ [📁 Select] [⬜ Rect] [🔷 Polygon] [🖌 Brush] [🧽 Eraser] [🔍 Zoom] [✋ Pan] │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │    🎥 Video Canvas Area                                              │  │
│  │                                                                      │  │
│  │    ┌─────────────────────────────────────────────┐                   │  │
│  │    │                                             │ ⬜ Pedestrian     │  │
│  │    │                                        ┌───┐│ ID: ped_001       │  │
│  │    │    [Street Scene with VRU Detection]   │🚶 ││ Class: Pedestrian │  │
│  │    │                                        └───┘│ Conf: 0.92        │  │
│  │    │                                             │                   │  │
│  │    │           ┌──────┐                         │ 🚴 Cyclist         │  │
│  │    │           │  🚴  │                         │ ID: cyc_001        │  │
│  │    │           └──────┘                         │ Class: Cyclist     │  │
│  │    │                                             │ Conf: 0.87        │  │
│  │    └─────────────────────────────────────────────┘                   │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│ ├─────────────────────────────────────────────────────────────────────────┤│
│ │🔘●▶️⏸️⏹️⏮️⏭️  00:01:23 / 00:05:47  Frame: 2493/10329  🔊──────────○ ││
│ └─────────────────────────────────────────────────────────────────────────┘│
│                                                                            │
│ Properties Panel                          Annotation History               │
│ ┌─────────────────┐                      ┌─────────────────────────────┐   │
│ │Label: Pedestrian│                      │⟲ Added pedestrian_001      │   │
│ │Color: [🔵]      │                      │⟲ Modified cyclist_001      │   │
│ │Size: [2px]      │                      │⟲ Deleted old_detection     │   │
│ │Confidence: 0.92 │                      │⟲ Created polygon_shape     │   │
│ │Visibility: ☑️   │                      └─────────────────────────────┘   │
│ └─────────────────┘                                                        │
└────────────────────────────────────────────────────────────────────────────┘
```

### Mobile Annotation Interface
```
┌─────────────────────────────┐
│ ⬜ [🔷] [🖌] [↩️] [↪️] [⚙️] │
├─────────────────────────────┤
│                             │
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │    🎥 Video View        │ │
│ │                         │ │
│ │   ┌───┐                 │ │
│ │   │🚶 │                 │ │
│ │   └───┘                 │ │
│ │                         │ │
│ │        ┌────┐            │ │
│ │        │ 🚴 │            │ │
│ │        └────┘            │ │
│ └─────────────────────────┘ │
│                             │
│ ▶️ 01:23 / 05:47 🔊──○      │
│                             │
│ Selected: Pedestrian        │
│ Conf: 0.92  [Edit] [Del]    │
│                             │
│ [🎯 Detection] [📝 Manual]   │
└─────────────────────────────┘
```

## Test Execution Interface Wireframes

### Enhanced Test Execution Dashboard
```
┌────────────────────────────────────────────────────────────────────────────┐
│                    Enhanced Test Execution                                 │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ Configuration                              Live Results                     │
│ ┌─────────────────────────────────────┐   ┌─────────────────────────────────┐│
│ │Project: Urban VRU Detection     ▼  │   │🎯 Real-time Detection Feed     ││
│ │                                     │   │                                ││
│ │Videos Selected: 12/45               │   │ ┌────┐ Pedestrian detected     ││
│ │☑️ video_001.mp4                     │   │ │ 🚶 │ Confidence: 94.2%       ││
│ │☑️ video_002.mp4                     │   │ └────┘ Frame: 1247              ││
│ │☑️ video_003.mp4                     │   │                                ││
│ │☑️ ... (9 more)                      │   │ ┌────┐ Cyclist detected        ││
│ │                                     │   │ │ 🚴 │ Confidence: 89.7%       ││
│ │Confidence Threshold: [████────] 0.7 │   │ └────┘ Frame: 1251              ││
│ │                                     │   │                                ││
│ │Evaluation Metrics:                  │   │Performance Metrics:            ││
│ │☑️ Precision  ☑️ Recall              │   │🎯 Accuracy:     92.1%          ││
│ │☑️ F1-Score   ☑️ mAP                 │   │📊 Precision:    89.3%          ││
│ │                                     │   │🎪 Recall:       94.8%          ││
│ │[🎯 Start Test] [⏹️ Stop]            │   │📈 F1-Score:     91.9%          ││
│ └─────────────────────────────────────┘   └─────────────────────────────────┘│
│                                                                            │
│ Progress & Status                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │Test Progress: ████████████────────────── 67% (8/12 videos)             ││
│ │                                                                          ││
│ │Current: video_009.mp4  ⏱️ 02:34 / 04:15  📊 Processing frame 4829      ││
│ │                                                                          ││
│ │Status: ✅ 6 Completed  🔄 1 Processing  ⏳ 5 Queued  ❌ 0 Failed         ││
│ │                                                                          ││
│ │ETA: ~12 minutes remaining                              [📊 View Report]  ││
│ └──────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
```

### Test Results Analysis
```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Test Results Analysis                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ Test Session: Urban_VRU_Test_2024_001    Started: 2024-01-15 14:23 UTC     │
│ Status: ✅ Completed                       Duration: 8m 34s                 │
│                                                                            │
│ Overall Performance Metrics                                                │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐│
│ │🎯 Accuracy      │ │📊 Precision     │ │🎪 Recall        │ │📈 F1-Score  ││
│ │     92.1%       │ │     89.3%       │ │     94.8%       │ │    91.9%    ││
│ │  +2.1% vs last  │ │  +1.7% vs last  │ │  -0.3% vs last  │ │ +1.2% vs last││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────┘│
│                                                                            │
│ Confusion Matrix                          Detection Classes               │
│ ┌─────────────────────────────────────┐   ┌─────────────────────────────────┐│
│ │        Predicted                    │   │🚶 Pedestrian                    ││
│ │    P   C   V   B   N                │   │  Detected: 1,247  Missed: 52   ││
│ │P │234  12   3   1   8 │ Pedestrian │   │  False Pos: 23   Accuracy: 94.2%││
│ │C │ 8  156   2   0   4 │ Cyclist    │   │                                 ││
│ │V │ 2    3  89   1   2 │ Vehicle    │   │🚴 Cyclist                       ││
│ │B │ 1    0   0  43   1 │ Bus        │   │  Detected: 789   Missed: 31    ││
│ │N │15    7   4   2 312 │ None       │   │  False Pos: 18   Accuracy: 91.7%││
│ └─────────────────────────────────────┘   │                                 ││
│                                           │🚗 Vehicle                       ││
│ Performance by Video                      │  Detected: 456   Missed: 12    ││
│ ┌─────────────────────────────────────┐   │  False Pos: 8    Accuracy: 96.1%││
│ │video_001: 94.2% (✅ Best)            │   │                                 ││
│ │video_002: 89.1% (⚠️ Below avg)       │   │🚌 Bus                          ││
│ │video_003: 95.7% (✅ Excellent)       │   │  Detected: 234   Missed: 3     ││
│ │...                                  │   │  False Pos: 2    Accuracy: 98.9%││
│ └─────────────────────────────────────┘   └─────────────────────────────────┘│
│                                                                            │
│ [📊 Detailed Report] [📁 Export Data] [🔄 Run Similar Test] [❌ Archive]    │
└────────────────────────────────────────────────────────────────────────────┘
```

## Error States and User Feedback

### Error State Wireframes

#### Network Error
```
┌─────────────────────────────┐
│  ⚠️  Connection Lost        │
├─────────────────────────────┤
│                             │
│ Unable to connect to the    │
│ validation service.         │
│                             │
│ This may be due to:         │
│ • Network connectivity      │
│ • Service maintenance       │
│ • Server overload           │
│                             │
│ Your work has been saved    │
│ locally and will sync when  │
│ connection is restored.     │
│                             │
│ [🔄 Retry] [🏠 Home] [💾 Save]│
└─────────────────────────────┘
```

#### File Upload Error
```
┌─────────────────────────────┐
│  ❌  Upload Failed          │
├─────────────────────────────┤
│                             │
│ video_large_file.mp4        │
│ Failed to upload            │
│                             │
│ Error: File size exceeds    │
│ 2GB limit                   │
│                             │
│ Suggestions:                │
│ • Compress the video        │
│ • Split into segments       │
│ • Use a different format    │
│                             │
│ [🔄 Retry] [📁 Choose Other] │
└─────────────────────────────┘
```

#### Validation Error
```
┌─────────────────────────────┐
│  ⚠️  Validation Issues      │
├─────────────────────────────┤
│                             │
│ Please fix the following:   │
│                             │
│ 📝 Project Name             │
│    Name is required         │
│                             │
│ 📹 Camera Model             │
│    Please specify model     │
│                             │
│ 📊 Video Selection          │
│    At least 1 video needed  │
│                             │
│ [❌ Cancel] [✏️ Fix Issues]   │
└─────────────────────────────┘
```

### Success State Patterns

#### Upload Complete
```
┌─────────────────────────────┐
│  ✅  Upload Successful      │
├─────────────────────────────┤
│                             │
│ video_vru_dataset_01.mp4    │
│ 847 MB • 5m 23s             │
│                             │
│ ✅ Upload complete          │
│ 🔄 Processing started       │
│ 🎯 Ground truth generating  │
│                             │
│ Estimated processing:       │
│ ~3 minutes                  │
│                             │
│ [📁 View in Library] [➕ Add More]│
└─────────────────────────────┘
```

#### Test Complete
```
┌─────────────────────────────┐
│  🎉  Test Completed         │
├─────────────────────────────┤
│                             │
│ Urban VRU Detection Test    │
│                             │
│ ✅ All 12 videos processed  │
│ 📊 Overall accuracy: 92.1%  │
│ ⏱️ Completed in 8m 34s      │
│                             │
│ Key Results:                │
│ • 1,247 pedestrians detected│
│ • 789 cyclists identified   │
│ • 94.2% precision rate      │
│                             │
│ [📊 View Results] [📧 Share] │
└─────────────────────────────┘
```

## Accessibility Features Wireframes

### Screen Reader Navigation
```
Page Structure:
├── Main Navigation (landmark)
│   ├── Dashboard (link)
│   ├── Projects (link)
│   └── Settings (link)
├── Main Content (main landmark)
│   ├── Page Title (heading level 1)
│   ├── Summary Statistics (region)
│   │   ├── Projects Card (article)
│   │   ├── Videos Card (article)
│   │   └── Tests Card (article)
│   └── Recent Activity (region)
│       ├── Test Sessions (list)
│       │   ├── Test Item 1 (listitem)
│       │   └── Test Item 2 (listitem)
│       └── System Status (status)
└── Footer (contentinfo)
```

### High Contrast Mode
```
┌────────────────────────────────────────┐
│ 🏴 HIGH CONTRAST MODE ACTIVE           │
├────────────────────────────────────────┤
│                                        │
│ ╔══════════════╗ ╔══════════════╗      │
│ ║ 📊 PROJECTS  ║ ║ 🎥 VIDEOS    ║      │
│ ║     15       ║ ║    247       ║      │
│ ║ ▲ +2 new     ║ ║ ▲ +5 added   ║      │
│ ╚══════════════╝ ╚══════════════╝      │
│                                        │
│ ╔══════════════╗ ╔══════════════╗      │
│ ║ 🧪 TESTS     ║ ║ 📈 ACCURACY  ║      │
│ ║     89       ║ ║   94.2%      ║      │
│ ║ ● 3 active   ║ ║ ▲ +2.1%      ║      │
│ ╚══════════════╝ ╚══════════════╝      │
│                                        │
│ ┌─ RECENT SESSIONS ──────────────────┐ │
│ │ ▶ Test_001 - 94.2% accuracy       │ │
│ │ ▶ Test_002 - 91.7% accuracy       │ │
│ │ ▶ Test_003 - 96.1% accuracy       │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

### Keyboard Navigation Flow
```
Tab Order Visualization:

1. [Skip to main content] (skip link)
   ↓
2. [🏠 Dashboard] (nav item)
   ↓
3. [📁 Projects] (nav item)
   ↓  
4. [🎥 Ground Truth] (nav item)
   ↓
5. [▶️ Test Execution] (nav item)
   ↓
6. [🔔 Notifications] (button)
   ↓
7. [👤 User Menu] (button)
   ↓
8. [Main Content Area] (main landmark)
   ↓
9. [Project Card 1] (button/link)
   ↓
10. [Project Card 2] (button/link)
    ↓
11. [+ New Project] (button)
    ↓
12. [Footer Links] (links)

Keyboard Shortcuts:
• Alt + M: Main content
• Alt + N: Navigation
• Alt + S: Search
• Ctrl + /: Show shortcuts
• Escape: Close modals/menus
```

## Component Interaction Specifications

### Video Player Controls
```
Standard Controls:
┌─────────────────────────────────────────┐
│ ▶️ ⏸️ ⏹️ ⏮️ ⏭️  ││◀◀  ▶▶││           │
│                                         │
│ 00:01:23 ●═══════════○═══════ 00:05:47 │
│                                         │
│ 🔊 ────────○  📺 [HD] ⚙️  ⛶  📱 💻     │
└─────────────────────────────────────────┘

Annotation Mode Controls:
┌─────────────────────────────────────────┐
│ ▶️ ⏸️ Frame: 2493/10329  🎯 ⭐ 🔍 📏   │
│                                         │
│ 00:01:23 ●═══════════○═══════ 00:05:47 │
│ ⏮️ ◀️ ▶️ ⏭️                Frame Step    │
│                                         │
│ [Previous Annotation] [Next Annotation] │
└─────────────────────────────────────────┘
```

### Form Validation States
```
Empty State:
┌─────────────────────────────┐
│ Project Name *              │
│ ┌─────────────────────────┐ │
│ │                         │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘

Typing State:
┌─────────────────────────────┐
│ Project Name *              │
│ ┌─────────────────────────┐ │
│ │Urban VRU Detect|        │ │
│ └─────────────────────────┘ │
│ ✓ Valid project name        │
└─────────────────────────────┘

Error State:
┌─────────────────────────────┐
│ Project Name *              │
│ ┌─────────────────────────┐ │
│ │                         │ │ 
│ └─────────────────────────┘ │
│ ❌ Project name is required │
└─────────────────────────────┘

Success State:
┌─────────────────────────────┐
│ Project Name *              │
│ ┌─────────────────────────┐ │
│ │Urban VRU Detection      │ │
│ └─────────────────────────┘ │
│ ✅ Ready to create project  │
└─────────────────────────────┘
```

This comprehensive wireframe specification provides detailed visual representations of all major interfaces, interactions, and states within the AI Model Validation Platform, ensuring consistent and accessible user experiences across all device types and usage scenarios.