# AI Model Validation Platform - UI Pages Comprehensive Specification
*Generated using SPARC+TDD Integrated Methodology*

## 🎯 Overview
This document provides a complete specification of all UI pages, their intended functions, and every interactive element (buttons, icons, forms, etc.) in the AI Model Validation Platform.

---

## 📄 Page Inventory & Detailed Specifications

### 1. **Dashboard Page** (`/dashboard`, `/`)
**Primary Function**: System overview and quick access to key metrics

#### **Layout Components**:
```typescript
Header Component:
├── App Title: "AI Model Validation Platform"
├── Notification Icon: Badge with count (currently shows 4)
├── Profile Menu: Avatar → Settings navigation

Main Content:
├── Page Title: "Dashboard" (h4)
├── Statistics Cards Row (4 cards):
│   ├── Active Projects Card
│   │   ├── Icon: <FolderOpen />
│   │   ├── Value: Dynamic count from API
│   │   ├── Subtitle: "X total projects" or "No projects yet"
│   │   └── Accessibility: ARIA labels
│   ├── Videos Processed Card  
│   │   ├── Icon: <VideoLibrary />
│   │   ├── Value: Dynamic count from API
│   │   ├── Subtitle: "X videos uploaded" or "No videos yet"
│   │   └── Color: Success theme
│   ├── Tests Completed Card
│   │   ├── Icon: <Assessment />
│   │   ├── Value: Dynamic count from API
│   │   ├── Subtitle: "X test sessions" or "No tests yet"
│   │   └── Color: Info theme
│   └── Detection Accuracy Card
│       ├── Icon: <TrendingUp />
│       ├── Value: Percentage with trend indicator
│       ├── Subtitle: "Average across all tests"
│       ├── Trend: Arrow up/down with percentage
│       └── Color: Warning theme
├── Content Row (2 cards):
│   ├── Recent Test Sessions Card
│   │   ├── Title: "Recent Test Sessions"
│   │   ├── Session List: 4 mock sessions
│   │   │   ├── Session Number
│   │   │   ├── Type (e.g., "Front-facing VRU")
│   │   │   ├── Time Ago
│   │   │   └── Accuracy Percentage
│   │   └── ARIA: List role with session items
│   └── System Status Card
│       ├── Title: "System Status"
│       ├── Progress Indicators (3):
│       │   ├── YOLO Model Performance (95% - Success)
│       │   ├── Database Usage (67% - Info)
│       │   └── Storage Usage (43% - Primary)
│       └── ARIA: Group role with progress indicators
```

#### **Interactive Elements**:
- **Notification Icon**: Should show actual notification count (currently hardcoded to 4)
- **Profile Avatar**: Opens dropdown menu with Settings option
- **Statistics Cards**: Should be clickable for navigation to relevant sections
- **Session Items**: Should be clickable for navigation to detailed results

#### **Data Sources**:
- Statistics: `GET /api/dashboard/stats`
- Sessions: Mock data (should connect to real API)
- System Status: Mock data (should reflect real system metrics)

---

### 2. **Projects Page** (`/projects`)
**Primary Function**: Manage AI validation projects (CRUD operations)

#### **Layout Components**:
```typescript
Header Component: (Same as Dashboard)

Main Content:
├── Page Title: "Projects" (h4)
├── Action Row:
│   ├── Create Project Button
│   │   ├── Icon: <Add />
│   │   ├── Text: "Create New Project"
│   │   ├── Variant: Contained, Primary
│   │   └── Action: Opens project creation dialog
│   └── API Test Component (Development tool)
├── Projects Grid:
│   ├── Project Cards (Dynamic, responsive grid)
│   │   ├── Card Header:
│   │   │   ├── Camera Icon: <Camera />
│   │   │   ├── Project Name (h6)
│   │   │   └── More Actions Menu: <MoreVert />
│   │   │       ├── View Details
│   │   │       ├── Edit Project  
│   │   │       └── Delete Project
│   │   ├── Card Content:
│   │   │   ├── Description text
│   │   │   ├── Metadata chips:
│   │   │   │   ├── Camera Model
│   │   │   │   ├── Camera View
│   │   │   │   └── Signal Type
│   │   │   ├── Statistics:
│   │   │   │   ├── Videos count
│   │   │   │   ├── Tests count
│   │   │   │   └── Success rate
│   │   │   └── Created date
│   │   └── Card Actions:
│   │       ├── View Button: <Visibility />
│   │       ├── Edit Button: <Edit />
│   │       └── Delete Button: <Delete />
│   └── Empty State:
│       ├── Message: "No projects yet"
│       ├── Description: "Create your first project"
│       └── Create Button
└── Create Project Dialog:
    ├── Dialog Title: "Create New Project"
    ├── Form Fields:
    │   ├── Project Name (Required, TextField)
    │   ├── Description (Optional, TextField multiline)
    │   ├── Camera Model (Required, TextField)
    │   ├── Camera View (Required, Select)
    │   │   ├── "Front-facing VRU"
    │   │   ├── "Side-view VRU"  
    │   │   ├── "Mixed-angle VRU"
    │   │   └── "Night-time VRU"
    │   └── Signal Type (Required, Select)
    │       ├── "pedestrian"
    │       ├── "cyclist"
    │       └── "vehicle"
    ├── Form Validation: Real-time error states
    ├── Loading State: During submission
    └── Dialog Actions:
        ├── Cancel Button
        └── Create Button (Disabled until valid)
```

#### **Interactive Elements**:
- **Create Project Button**: Opens modal dialog with form
- **Project Cards**: Clickable for navigation to project details
- **More Actions Menu**: Dropdown with View/Edit/Delete options
- **Action Buttons**: View (navigate), Edit (future), Delete (confirmation)
- **Form Validation**: Real-time validation with error messages
- **Dialog Controls**: Cancel/Create with loading states

#### **API Integration**:
- **Load Projects**: `GET /api/projects`
- **Create Project**: `POST /api/projects`
- **Delete Project**: `DELETE /api/projects/{id}` (future)

---

### 3. **Project Detail Page** (`/projects/{id}`)
**Primary Function**: Detailed project view with videos and test management

#### **Layout Components**:
```typescript
Header Component: (Same as Dashboard)

Main Content:
├── Loading State: Skeleton components during data fetch
├── Error State: Alert component for load failures
├── Project Header:
│   ├── Back Navigation: Breadcrumb or back button
│   ├── Project Title: Dynamic from API
│   ├── Project Description: Dynamic from API
│   └── Action Buttons:
│       ├── Edit Project Button: <Edit /> "Edit Project"
│       └── Run New Test Button: <PlayArrow /> "Run New Test"
├── Project Statistics Cards:
│   ├── Total Tests: Count with icon
│   ├── Average Accuracy: Percentage with trend
│   ├── Last Test: Date and accuracy
│   └── Status: Active/Inactive indicator
├── Tabbed Interface:
│   ├── Tab 1: "Ground Truth Videos" (Active by default)
│   │   ├── Tab Header:
│   │   │   ├── Video Icon: <VideoLibrary />
│   │   │   ├── Title: "Ground Truth Videos (X)"
│   │   │   └── Upload Button: <Upload /> "Upload Video"
│   │   ├── Error State: Video load errors
│   │   ├── Empty State:
│   │   │   ├── Message: "No videos yet"
│   │   │   ├── Description: "Upload ground truth videos"
│   │   │   └── Upload Button
│   │   └── Video Table:
│   │       ├── Table Headers:
│   │       │   ├── Filename
│   │       │   ├── Status
│   │       │   ├── Size  
│   │       │   ├── Duration
│   │       │   ├── Uploaded
│   │       │   └── Actions
│   │       └── Table Rows:
│   │           ├── Filename link
│   │           ├── Status chip (colored)
│   │           ├── File size (formatted)
│   │           ├── Duration (MM:SS)
│   │           ├── Upload date (relative)
│   │           └── Actions:
│   │               ├── View Button
│   │               └── Delete Button
│   ├── Tab 2: "Test Sessions" 
│   │   ├── Sessions List/Table
│   │   ├── Session Statistics
│   │   └── Run Test Button
│   └── Tab 3: "Configuration"
│       ├── Project Settings Form
│       ├── Camera Configuration
│       └── Update Button
└── Upload Video Dialog:
    ├── Dialog Title: "Upload Video"
    ├── File Input: Accept video formats
    ├── File Preview: Name, size, type
    ├── Validation: Format and size checks
    ├── Progress: Upload progress bar
    └── Dialog Actions:
        ├── Cancel Button
        └── Upload Button (Conditional)
```

#### **Interactive Elements**:
- **Navigation**: Back button/breadcrumb
- **Action Buttons**: Edit project, Run new test  
- **Tab Navigation**: Switch between Videos/Tests/Config
- **Upload Button**: Opens upload dialog
- **Video Table**: Sortable columns, action buttons per row
- **Upload Dialog**: File selection, validation, progress tracking
- **Delete Confirmations**: For videos and dangerous actions

#### **API Integration**:
- **Load Project**: `GET /api/projects/{id}`
- **Load Videos**: `GET /api/projects/{id}/videos`  
- **Upload Video**: `POST /api/projects/{id}/videos`
- **Delete Video**: `DELETE /api/videos/{id}`
- **Load Test Sessions**: `GET /api/test-sessions?project_id={id}`

---

### 4. **Test Execution Page** (`/test-execution`)
**Primary Function**: Real-time AI model testing with live video processing

#### **Layout Components**:
```typescript
Header Component: (Same as Dashboard)

Main Content:
├── Page Title: "AI Model Testing" (h4)
├── WebSocket Connection Status:
│   ├── Connected Indicator: Green dot + "Connected"
│   ├── Disconnected State: Red dot + "Disconnected" 
│   ├── Reconnection Progress: "Attempting to reconnect..."
│   └── Error Messages: Connection failure alerts
├── Test Configuration Section:
│   ├── Section Title: "Test Configuration"
│   ├── Project Selection:
│   │   ├── Label: "Select Project"
│   │   ├── Dropdown: Populated from API
│   │   └── Loading State: Skeleton while loading
│   ├── Video Selection:
│   │   ├── Label: "Select Video"  
│   │   ├── Dropdown: Filtered by project
│   │   ├── Conditional: Only shows when project selected
│   │   └── Filter: Only "completed" status videos
│   └── Test Parameters:
│       ├── Tolerance Setting: Slider or input
│       ├── Detection Threshold: Slider or input  
│       └── Other ML model parameters
├── Test Controls:
│   ├── Start Test Button:
│   │   ├── Icon: <PlayArrow />
│   │   ├── Text: "Start Test Session"
│   │   ├── State: Disabled until project+video selected
│   │   └── Loading: Shows spinner during session creation
│   ├── Stop Test Button:
│   │   ├── Icon: <Stop />
│   │   ├── Text: "Stop Current Test"
│   │   ├── State: Only visible during active test
│   │   └── Color: Error/warning theme
│   └── Session Status:
│       ├── Current Session ID
│       ├── Start Time
│       └── Duration Counter
├── Live Video Section:
│   ├── Video Player:
│   │   ├── HTML5 video element
│   │   ├── Controls: Play, pause, seek, volume
│   │   ├── Overlay: Detection bounding boxes
│   │   └── Status: Loading, playing, error states
│   ├── Video Information:
│   │   ├── Filename
│   │   ├── Duration
│   │   ├── Resolution
│   │   └── Current timestamp
│   └── Detection Overlay:
│       ├── Bounding boxes for detected objects
│       ├── Confidence scores
│       ├── Object labels
│       └── Color coding by detection type
├── Real-time Detection Feed:
│   ├── Section Title: "Live Detections"
│   ├── Detection List:
│   │   ├── Auto-scroll: Latest detections at top
│   │   ├── Detection Items:
│   │   │   ├── Timestamp
│   │   │   ├── Object type/class
│   │   │   ├── Confidence score
│   │   │   ├── Bounding box coordinates
│   │   │   └── Validation status (TP/FP/FN)
│   │   └── Max Items: Limit to prevent memory issues
│   ├── Detection Statistics:
│   │   ├── Total detections counter
│   │   ├── True positives counter
│   │   ├── False positives counter
│   │   ├── False negatives counter
│   │   └── Current accuracy percentage
│   └── Export Options:
│       ├── Download CSV button
│       ├── Download JSON button
│       └── Copy to clipboard
└── Session Management:
    ├── Active Sessions List
    ├── Session History
    ├── Resume Session Button
    └── Clear History Button
```

#### **Interactive Elements**:
- **Connection Status**: Auto-reconnect functionality
- **Project/Video Dropdowns**: Cascading selection with API calls
- **Test Controls**: Start/Stop with validation and feedback
- **Video Player**: Full HTML5 controls with custom overlays
- **Real-time Feed**: Auto-updating list with WebSocket data
- **Export Functions**: Data download in various formats
- **Session Management**: Save/restore test sessions

#### **WebSocket Integration**:
- **Connection**: Socket.IO client with auto-reconnect
- **Events**: Detection events, session updates, status messages
- **Rooms**: Join test session room for targeted updates
- **Error Handling**: Connection failures and recovery

#### **API Integration**:
- **Load Projects**: `GET /api/projects`
- **Load Videos**: `GET /api/projects/{id}/videos`
- **Create Session**: `POST /api/test-sessions`
- **Detection Events**: Real-time via WebSocket

---

### 5. **Results Page** (`/results`)
**Primary Function**: View and analyze completed test session results

#### **Layout Components**:
```typescript
Header Component: (Same as Dashboard)

Main Content:
├── Page Title: "Test Results" (h4)
├── Filters Section:
│   ├── Project Filter:
│   │   ├── Label: "Filter by Project"
│   │   ├── Dropdown: "All Projects" + project list
│   │   └── Default: "all"
│   ├── Time Range Filter:
│   │   ├── Label: "Time Range"
│   │   ├── Dropdown: "7 days", "30 days", "90 days", "All time"
│   │   └── Default: "7days"
│   ├── Status Filter:
│   │   ├── Completed checkbox
│   │   ├── Failed checkbox
│   │   └── Running checkbox
│   └── Apply Filters Button
├── Results Summary Cards:
│   ├── Total Tests Card
│   ├── Average Accuracy Card  
│   ├── Best Performance Card
│   └── Recent Activity Card
├── Results Table:
│   ├── Table Headers:
│   │   ├── Session Name (Sortable)
│   │   ├── Project Name (Sortable)
│   │   ├── Status (Filterable)
│   │   ├── Accuracy % (Sortable)
│   │   ├── Precision % (Sortable)
│   │   ├── Recall % (Sortable)
│   │   ├── Duration (Sortable)
│   │   ├── Date (Sortable)
│   │   └── Actions
│   ├── Table Rows:
│   │   ├── Session name link
│   │   ├── Project name link
│   │   ├── Status chip with color
│   │   ├── Performance metrics with color coding
│   │   ├── Duration in MM:SS format
│   │   ├── Relative date ("2 hours ago")
│   │   └── Action Buttons:
│   │       ├── View Details <Visibility />
│   │       ├── Download Report <GetApp />
│   │       └── Compare <TrendingUp />
│   └── Table Features:
│       ├── Sorting: Click headers to sort
│       ├── Pagination: For large datasets
│       ├── Row Selection: Checkboxes for bulk actions
│       └── Bulk Actions: Compare, export selected
├── Empty State:
│   ├── Message: "No test results found"
│   ├── Description: "Run some tests first"
│   └── Navigate to Test Execution button
├── Export Options:
│   ├── Export All Button: <FileDownload />
│   ├── Export Selected Button
│   ├── Format Options: CSV, JSON, PDF report
│   └── Date Range Selection
└── Comparison Modal:
    ├── Selected Sessions List
    ├── Metrics Comparison Charts
    ├── Performance Analysis
    └── Export Comparison Report
```

#### **Interactive Elements**:
- **Filter Controls**: Dropdowns with immediate or on-apply filtering
- **Table Sorting**: Clickable headers with sort indicators
- **Status Icons**: Color-coded success/warning/error indicators  
- **Action Buttons**: Per-row actions for view/download/compare
- **Bulk Selection**: Checkboxes with bulk action toolbar
- **Export Functions**: Multiple format options with date ranges
- **Comparison Tool**: Multi-select comparison with charts

#### **Data Processing**:
- **Real-time Loading**: Dynamic data from API with loading states
- **Fallback Data**: Mock data when API unavailable
- **Performance Metrics**: Calculated accuracy, precision, recall
- **Time Formatting**: Relative dates and duration formatting

#### **API Integration**:
- **Load Results**: `GET /api/test-sessions` with filters
- **Load Projects**: `GET /api/projects` for filter options
- **Session Details**: `GET /api/test-sessions/{id}/results`

---

### 6. **Ground Truth Page** (`/ground-truth`)
**Primary Function**: Manage ground truth annotations for video validation

#### **Layout Components**:
```typescript
Header Component: (Same as Dashboard)

Main Content:
├── Page Title: "Ground Truth Management" (h4)
├── Video Selection Section:
│   ├── Project Dropdown: Select project for videos
│   ├── Video Dropdown: Select specific video
│   └── Load Annotations Button
├── Annotation Interface:
│   ├── Video Player:
│   │   ├── HTML5 video with controls
│   │   ├── Annotation overlay canvas
│   │   ├── Frame-by-frame navigation
│   │   ├── Timeline scrubber
│   │   └── Zoom/pan controls
│   ├── Annotation Tools:
│   │   ├── Drawing Tools:
│   │   │   ├── Rectangle tool (bounding boxes)
│   │   │   ├── Polygon tool (complex shapes)
│   │   │   ├── Point tool (keypoints)
│   │   │   └── Line tool (trajectories)
│   │   ├── Object Classification:
│   │   │   ├── Class dropdown (pedestrian, cyclist, vehicle)
│   │   │   ├── Attributes checkboxes
│   │   │   └── Confidence slider
│   │   └── Tool Settings:
│   │       ├── Color picker
│   │       ├── Line thickness
│   │       └── Opacity settings
│   ├── Frame Navigation:
│   │   ├── Previous Frame button
│   │   ├── Next Frame button  
│   │   ├── Frame number input
│   │   └── Keyframe markers
│   └── Playback Controls:
│       ├── Play/Pause toggle
│       ├── Speed adjustment (0.25x to 2x)
│       ├── Loop toggle
│       └── Full-screen mode
├── Annotations List Panel:
│   ├── Current Frame Annotations:
│   │   ├── Annotation items list
│   │   ├── Object ID and class
│   │   ├── Bounding box coordinates
│   │   ├── Confidence score
│   │   └── Action buttons:
│   │       ├── Edit annotation
│   │       ├── Delete annotation
│   │       └── Duplicate annotation
│   ├── All Annotations Summary:
│   │   ├── Total annotations count
│   │   ├── Objects by class breakdown
│   │   ├── Frame coverage statistics
│   │   └── Quality metrics
│   └── Annotation Search:
│       ├── Search by object class
│       ├── Filter by frame range
│       └── Filter by confidence
├── Export/Import Section:
│   ├── Export Annotations:
│   │   ├── Format selection (COCO, YOLO, XML)
│   │   ├── Frame range selection
│   │   ├── Class filter options
│   │   └── Download button
│   ├── Import Annotations:
│   │   ├── File upload area
│   │   ├── Format detection
│   │   ├── Preview imported data
│   │   └── Import confirmation
│   └── Auto-annotation:
│       ├── Run AI pre-annotation
│       ├── Confidence threshold setting
│       └── Review generated annotations
└── Save/Load Section:
    ├── Save Progress button (auto-save enabled)
    ├── Load Saved Session
    ├── Session history
    └── Collaboration features (future)
```

#### **Interactive Elements**:
- **Video Player**: Full control with annotation overlay
- **Drawing Tools**: Mouse/touch-based annotation creation
- **Frame Navigation**: Precise frame-by-frame control
- **Annotation Editing**: Click-to-edit existing annotations
- **Import/Export**: File handling for various annotation formats
- **Auto-save**: Continuous saving of annotation progress

#### **API Integration**:
- **Load Videos**: `GET /api/projects/{id}/videos`
- **Load Annotations**: `GET /api/videos/{id}/ground-truth`
- **Save Annotations**: `POST /api/videos/{id}/annotations`
- **Export Formats**: `GET /api/annotations/{id}/export?format=`

---

### 7. **Settings Page** (`/settings`)
**Primary Function**: Application configuration and user preferences

#### **Layout Components**:
```typescript
Header Component: (Same as Dashboard)

Main Content:
├── Page Title: "Settings" (h4)
├── Settings Categories Tabs:
│   ├── General Tab:
│   │   ├── Application Settings:
│   │   │   ├── Theme Selection: Light/Dark/Auto
│   │   │   ├── Language Selection: Dropdown
│   │   │   ├── Timezone Selection: Dropdown
│   │   │   └── Auto-save Interval: Slider
│   │   ├── Notification Settings:
│   │   │   ├── Email Notifications: Toggle
│   │   │   ├── Browser Notifications: Toggle  
│   │   │   ├── Test Completion Alerts: Toggle
│   │   │   └── System Status Alerts: Toggle
│   │   └── Data Management:
│   │       ├── Storage Location: Path input
│   │       ├── Cache Size Limit: Slider
│   │       ├── Auto-cleanup: Toggle + days input
│   │       └── Data Export Settings
│   ├── AI Model Tab:
│   │   ├── Model Configuration:
│   │   │   ├── Default Model: Dropdown (YOLO, etc.)
│   │   │   ├── Model Path: File picker
│   │   │   ├── Input Size: Width x Height inputs
│   │   │   └── Batch Size: Number input
│   │   ├── Detection Settings:
│   │   │   ├── Confidence Threshold: Slider (0-1)
│   │   │   ├── NMS Threshold: Slider (0-1)
│   │   │   ├── Max Detections: Number input
│   │   │   └── Class Names: Editable list
│   │   ├── Performance Settings:
│   │   │   ├── GPU Usage: Toggle + device selection
│   │   │   ├── CPU Threads: Number input
│   │   │   ├── Memory Limit: Slider
│   │   │   └── Processing Mode: Dropdown
│   │   └── Model Management:
│   │       ├── Available Models List
│   │       ├── Download New Model Button
│   │       ├── Update Model Button
│   │       └── Delete Model Button
│   ├── Video Processing Tab:
│   │   ├── Input Settings:
│   │   │   ├── Supported Formats: Checkbox list
│   │   │   ├── Max File Size: Slider (MB)
│   │   │   ├── Auto-resize: Toggle + max dimensions
│   │   │   └── Quality Settings: Dropdown
│   │   ├── Processing Settings:
│   │   │   ├── Frame Rate: Dropdown (process every N frames)
│   │   │   ├── Resolution Scaling: Slider
│   │   │   ├── Color Space: Dropdown (RGB, BGR, etc.)
│   │   │   └── Preprocessing Steps: Checklist
│   │   └── Output Settings:
│   │       ├── Save Processed Frames: Toggle
│   │       ├── Output Format: Dropdown
│   │       ├── Compression Level: Slider
│   │       └── Metadata Inclusion: Checklist
│   ├── Database Tab:
│   │   ├── Connection Settings:
│   │   │   ├── Database Type: Dropdown (SQLite, PostgreSQL)
│   │   │   ├── Host: Text input (if PostgreSQL)
│   │   │   ├── Port: Number input
│   │   │   ├── Database Name: Text input
│   │   │   ├── Username: Text input
│   │   │   ├── Password: Password input
│   │   │   └── Test Connection Button
│   │   ├── Backup Settings:
│   │   │   ├── Auto Backup: Toggle + frequency
│   │   │   ├── Backup Location: Path input
│   │   │   ├── Retention Policy: Days input
│   │   │   └── Create Backup Button
│   │   └── Maintenance:
│   │       ├── Vacuum Database Button
│   │       ├── Reindex Button
│   │       ├── Clear Cache Button
│   │       └── Reset Statistics Button
│   └── Advanced Tab:
│       ├── Logging Settings:
│       │   ├── Log Level: Dropdown (Debug, Info, Warning, Error)
│       │   ├── Log File Location: Path input
│       │   ├── Max Log Size: Slider (MB)
│       │   └── Log Rotation: Toggle + count
│       ├── API Settings:
│       │   ├── API Base URL: Text input
│       │   ├── Request Timeout: Number input (seconds)
│       │   ├── Retry Attempts: Number input
│       │   └── Rate Limiting: Toggle + requests per minute
│       ├── WebSocket Settings:
│       │   ├── WebSocket URL: Text input
│       │   ├── Reconnection Attempts: Number input
│       │   ├── Heartbeat Interval: Number input (seconds)
│       │   └── Buffer Size: Slider (KB)
│       └── Debug Options:
│           ├── Debug Mode: Toggle
│           ├── Verbose Logging: Toggle
│           ├── Performance Monitoring: Toggle
│           └── Export Debug Info Button
├── Action Buttons Section:
│   ├── Save Settings Button: Primary button
│   ├── Reset to Defaults Button: Secondary button
│   ├── Export Config Button: Outlined button
│   ├── Import Config Button: File input + button
│   └── Apply Changes Button: (if changes detected)
└── Settings Status:
    ├── Last Saved: Timestamp display
    ├── Unsaved Changes Warning: Alert if changes exist
    ├── Validation Errors: List of configuration issues
    └── Settings Version: Configuration schema version
```

#### **Interactive Elements**:
- **Tab Navigation**: Switch between settings categories
- **Form Controls**: Various inputs with validation
- **File Pickers**: For model files, paths, imports
- **Sliders**: For thresholds, limits, and ranges
- **Toggles**: For boolean settings with immediate feedback
- **Test Buttons**: For connection testing and validation
- **Import/Export**: Configuration backup and restore

#### **Validation & Persistence**:
- **Real-time Validation**: Form field validation
- **Dependency Checking**: Settings interdependencies
- **Auto-save**: Optional continuous saving
- **Change Detection**: Unsaved changes warnings
- **Rollback**: Reset to last saved or defaults

---

### 8. **Authentication Pages** (If implemented)
**Primary Function**: User login, registration, and account management

#### **Login Page** (`/login`)
```typescript
Layout Components:
├── App Logo/Title
├── Login Form:
│   ├── Email/Username Input: Required, validated
│   ├── Password Input: Required, masked
│   ├── Remember Me Checkbox
│   ├── Login Button: Submit form
│   └── Forgot Password Link
├── Alternative Login Options:
│   ├── Google OAuth Button
│   ├── GitHub OAuth Button
│   └── SSO Options
├── Registration Link: "Don't have an account? Sign up"
└── Footer Links: Terms, Privacy, Support
```

#### **Registration Page** (`/register`)
```typescript
Layout Components:
├── Registration Form:
│   ├── Full Name Input: Required
│   ├── Email Input: Required, email validation
│   ├── Password Input: Required, strength indicator
│   ├── Confirm Password Input: Required, match validation
│   ├── Terms Acceptance Checkbox: Required
│   ├── Newsletter Opt-in Checkbox: Optional
│   └── Register Button: Submit form
├── Form Validation: Real-time field validation
├── Password Requirements: Visible criteria
└── Login Link: "Already have an account? Sign in"
```

---

## 🎯 Interactive Element Categories

### **Navigation Elements**:
- Header navigation with app title
- Profile menu with avatar
- Breadcrumb navigation
- Tab navigation within pages
- Back buttons and page transitions

### **Data Display Elements**:
- Statistics cards with icons and values
- Data tables with sorting and filtering
- Progress indicators and status chips
- Charts and graphs (future enhancement)
- Real-time data feeds

### **Form Elements**:
- Text inputs with validation
- Dropdowns and select components  
- File upload areas with drag-and-drop
- Sliders for numeric ranges
- Checkboxes and radio buttons
- Form submission with loading states

### **Action Elements**:
- Primary action buttons (Create, Save, Upload)
- Secondary action buttons (Cancel, Reset)
- Icon buttons for quick actions
- Menu buttons with dropdown options
- Bulk action toolbars

### **Feedback Elements**:
- Loading skeletons and spinners
- Success/error notifications
- Toast messages for quick feedback
- Alert components for important messages
- Empty states with guidance

### **Media Elements**:
- Video players with custom controls
- Image displays and galleries
- File preview components
- Download and export functionality

---

## 📊 Feature Implementation Status

### **Fully Implemented** ✅:
- Dashboard statistics display
- Project CRUD operations
- Video upload functionality
- Basic navigation structure
- Form validation
- Error boundaries and handling

### **Partially Implemented** ⚠️:
- Test execution (UI exists, WebSocket integration partial)
- Results display (mock data, needs real API)
- Ground truth management (basic structure)
- Settings page (missing implementation)

### **Not Implemented** ❌:
- User authentication system
- Advanced filtering and search
- Data export functionality
- Real-time collaboration features
- Comprehensive help system

---

*This specification serves as the foundation for comprehensive UI testing using SPARC+TDD methodology.*