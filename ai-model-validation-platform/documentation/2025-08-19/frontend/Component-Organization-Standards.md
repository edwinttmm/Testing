# Component Organization Standards

## Standardized Component Architecture

This document defines the canonical structure for organizing React functional components to ensure consistency, maintainability, and TypeScript compliance across all 5 target files.

## Component Template Structure

```typescript
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  // MUI Core Components (alphabetical order)
  Alert, Box, Button, Card, CardContent, CircularProgress,
  Dialog, DialogActions, DialogContent, DialogTitle,
  Grid, TextField, Typography
} from '@mui/material';
import {
  // MUI Icons (alphabetical order)
  Add, Assessment, CheckCircle, Delete, Edit, 
  Error, Refresh, Visibility, Warning
} from '@mui/icons-material';

// Local imports (grouped by type)
import { 
  // Type definitions (business logic types first)
  Project, TestSession, VideoFile, EnhancedDashboardStats,
  // Configuration types
  CameraType, SignalType, ProjectStatus,
  // Form types
  ProjectCreate, ProjectUpdate
} from '../services/types';

import { 
  // API services (grouped by functionality)
  apiService, getDashboardStats, getTestSessions,
  createProject, updateProject, deleteProject
} from '../services/api';

import { 
  // Utility functions (grouped by purpose)
  getErrorMessage, formatFileSize, formatDuration
} from '../utils/errorUtils';

import { 
  // Custom components (domain-specific)
  AccessibleStatCard, AccessibleCard,
  DeleteConfirmationDialog, VideoSelectionDialog
} from '../components/ui/';

import { 
  // Hooks (custom hooks last)
  useWebSocket, useErrorBoundary
} from '../hooks/';

/**
 * ComponentName - Brief description of component purpose
 * 
 * @description Detailed description of component functionality,
 * key features, and integration points.
 */
const ComponentName: React.FC = () => {
  // ==========================================
  // SECTION 1: TYPE DEFINITIONS (if needed locally)
  // ==========================================
  
  // ==========================================
  // SECTION 2: STATE DECLARATIONS
  // ==========================================
  
  // 2A. Core Data State (business logic state)
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  
  // 2B. Loading and Error State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  
  // 2C. UI State (dialogs, selections, etc.)
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  
  // 2D. Form State
  const [formData, setFormData] = useState<ProjectCreate>({
    name: '',
    description: '',
    cameraModel: '',
    cameraView: CameraType.FRONT_FACING_VRU,
    signalType: SignalType.GPIO
  });
  const [formErrors, setFormErrors] = useState<{[key: string]: string}>({});
  
  // 2E. Refs (DOM access and persistent values)
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastStatsRef = useRef<EnhancedDashboardStats | null>(null);
  
  // 2F. Custom Hook Integration
  const { isConnected, on: subscribe, emit, error: wsError } = useWebSocket();
  
  // ==========================================
  // SECTION 3: DERIVED STATE (useMemo)
  // ==========================================
  
  const filteredProjects = useMemo(() => {
    return projects.filter(project => 
      project.status === ProjectStatus.ACTIVE
    );
  }, [projects]);
  
  const overallMetrics = useMemo(() => {
    if (sessions.length === 0) return null;
    
    return {
      avgAccuracy: sessions.reduce((sum, s) => sum + (s.accuracy || 0), 0) / sessions.length,
      totalSessions: sessions.length,
      completedSessions: sessions.filter(s => s.status === 'completed').length,
    };
  }, [sessions]);
  
  // ==========================================
  // SECTION 4: CALLBACK FUNCTIONS
  // ==========================================
  
  // 4A. Level 1 - Independent Utility Functions
  const formatTimeAgo = useCallback((dateString: string | null | undefined): string => {
    if (!dateString) return 'Unknown time';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hour${Math.floor(diffInMinutes / 60) > 1 ? 's' : ''} ago`;
    return `${Math.floor(diffInMinutes / 1440)} day${Math.floor(diffInMinutes / 1440) > 1 ? 's' : ''} ago`;
  }, []);
  
  const validateForm = useCallback((): boolean => {
    const errors: {[key: string]: string} = {};
    
    if (!formData.name.trim()) {
      errors.name = 'Name is required';
    }
    if (!formData.description.trim()) {
      errors.description = 'Description is required';
    }
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }, [formData]);
  
  const resetForm = useCallback(() => {
    setFormData({
      name: '',
      description: '',
      cameraModel: '',
      cameraView: CameraType.FRONT_FACING_VRU,
      signalType: SignalType.GPIO
    });
    setFormErrors({});
  }, []);
  
  const showNotification = useCallback((message: string, type: 'success' | 'error' | 'warning' | 'info') => {
    // Notification logic
    console.log(`[${type.toUpperCase()}] ${message}`);
  }, []);
  
  // 4B. Level 2 - State-Only Dependent Functions  
  const updateStatsSafely = useCallback((updater: (prev: EnhancedDashboardStats) => EnhancedDashboardStats) => {
    setStats(prevStats => {
      if (!prevStats) return prevStats;
      const newStats = updater(prevStats);
      lastStatsRef.current = newStats;
      return newStats;
    });
  }, []);
  
  const handleFormChange = useCallback((field: keyof ProjectCreate, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (formErrors[field]) {
      setFormErrors(prev => ({ ...prev, [field]: '' }));
    }
  }, [formErrors]);
  
  // 4C. Level 3 - Single Function Dependencies
  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const projectsData = await apiService.getProjects();
      setProjects(projectsData);
      
      if (projectsData.length > 0) {
        setSelectedProject(projectsData[0]);
      }
      
      showNotification('Projects loaded successfully', 'success');
    } catch (err: any) {
      const errorMessage = getErrorMessage(err, 'Failed to load projects');
      setError(errorMessage);
      showNotification(errorMessage, 'error');
    } finally {
      setLoading(false);
    }
  }, [showNotification]);
  
  const loadSessions = useCallback(async (projectId: string) => {
    if (!projectId) return;
    
    try {
      setLoading(true);
      const sessionsData = await apiService.getTestSessions(projectId);
      setSessions(sessionsData);
    } catch (err: any) {
      const errorMessage = getErrorMessage(err, 'Failed to load sessions');
      setError(errorMessage);
      showNotification(errorMessage, 'error');
    } finally {
      setLoading(false);
    }
  }, [showNotification]);
  
  const handleProjectCreate = useCallback(async () => {
    if (!validateForm()) {
      return;
    }
    
    try {
      setFormLoading(true);
      
      await createProject(formData);
      
      setOpenDialog(false);
      resetForm();
      await loadProjects();
      
      showNotification('Project created successfully', 'success');
    } catch (err: any) {
      const errorMessage = getErrorMessage(err, 'Failed to create project');
      setError(errorMessage);
      showNotification(errorMessage, 'error');
    } finally {
      setFormLoading(false);
    }
  }, [validateForm, formData, resetForm, loadProjects, showNotification]);
  
  // 4D. Level 4 - Multi-Function Dependencies
  const handleProjectDelete = useCallback(async (projectId: string) => {
    try {
      await deleteProject(projectId);
      await loadProjects();
      showNotification('Project deleted successfully', 'success');
    } catch (err: any) {
      const errorMessage = getErrorMessage(err, 'Failed to delete project');
      showNotification(errorMessage, 'error');
    }
  }, [loadProjects, showNotification]);
  
  const handleProjectSelect = useCallback(async (project: Project) => {
    setSelectedProject(project);
    await loadSessions(project.id);
  }, [loadSessions]);
  
  // 4E. Level 5 - Complex Event Handlers
  const handleWebSocketMessage = useCallback((data: any) => {
    switch (data.type) {
      case 'project_updated':
        updateStatsSafely(prevStats => ({
          ...prevStats,
          project_count: prevStats.project_count + 1
        }));
        break;
      case 'session_completed':
        loadSessions(selectedProject?.id || '');
        break;
      default:
        console.log('Unknown WebSocket message:', data);
    }
  }, [updateStatsSafely, loadSessions, selectedProject?.id]);
  
  // ==========================================
  // SECTION 5: EFFECT HOOKS
  // ==========================================
  
  // 5A. Initial data loading
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);
  
  // 5B. Dependent data loading
  useEffect(() => {
    if (selectedProject) {
      loadSessions(selectedProject.id);
    }
  }, [selectedProject, loadSessions]);
  
  // 5C. WebSocket subscriptions
  useEffect(() => {
    if (!isConnected) {
      return;
    }
    
    const unsubscribeProject = subscribe('project_updated', handleWebSocketMessage);
    const unsubscribeSession = subscribe('session_completed', handleWebSocketMessage);
    
    return () => {
      unsubscribeProject?.();
      unsubscribeSession?.();
    };
  }, [isConnected, subscribe, handleWebSocketMessage]);
  
  // 5D. Cleanup effects
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);
  
  // ==========================================
  // SECTION 6: RENDER HELPERS
  // ==========================================
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'failed':
        return <Error color="error" />;
      case 'running':
        return <CircularProgress size={16} />;
      default:
        return <Warning color="warning" />;
    }
  };
  
  const getStatusColor = (status: string): 'success' | 'error' | 'warning' | 'default' => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'running':
        return 'warning';
      default:
        return 'default';
    }
  };
  
  // ==========================================
  // SECTION 7: EARLY RETURNS
  // ==========================================
  
  if (loading && projects.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading projects...</Typography>
      </Box>
    );
  }
  
  if (error && projects.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button
          variant="contained"
          onClick={loadProjects}
          startIcon={<Refresh />}
        >
          Retry
        </Button>
      </Box>
    );
  }
  
  // ==========================================
  // SECTION 8: MAIN RENDER
  // ==========================================
  
  return (
    <Box>
      {/* Header Section */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Component Title</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={loadProjects}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => setOpenDialog(true)}
          >
            Add New
          </Button>
        </Box>
      </Box>
      
      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {/* Main Content */}
      <Card>
        <CardContent>
          {/* Content implementation */}
        </CardContent>
      </Card>
      
      {/* Dialogs and Modals */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Dialog Title</DialogTitle>
        <DialogContent>
          {/* Dialog content */}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleProjectCreate}
            variant="contained"
            disabled={formLoading}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ComponentName;
```

## Section-by-Section Standards

### Section 1: Type Definitions
- **Purpose:** Local interfaces and types specific to the component
- **Rules:**
  - Only include types that are truly component-specific
  - Prefer importing types from shared type files
  - Use descriptive names with component prefix if needed

```typescript
// Local component-specific types only
interface ComponentNameProps {
  initialProject?: Project;
  onProjectSelect?: (project: Project) => void;
}

interface FormErrors {
  [key: string]: string;
}
```

### Section 2: State Declarations

#### 2A. Core Data State
```typescript
// Business logic state - the main data the component manages
const [projects, setProjects] = useState<Project[]>([]);
const [sessions, setSessions] = useState<TestSession[]>([]);
const [selectedProject, setSelectedProject] = useState<Project | null>(null);
```

#### 2B. Loading and Error State
```typescript
// System state - loading states and error handling
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [formLoading, setFormLoading] = useState(false);
const [formError, setFormError] = useState<string | null>(null);
```

#### 2C. UI State
```typescript
// Interface state - dialogs, tabs, selections
const [openDialog, setOpenDialog] = useState(false);
const [activeTab, setActiveTab] = useState(0);
const [selectedItems, setSelectedItems] = useState<string[]>([]);
const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
```

#### 2D. Form State
```typescript
// Form management state
const [formData, setFormData] = useState<ProjectCreate>({
  name: '',
  description: '',
  // ... other form fields with default values
});
const [formErrors, setFormErrors] = useState<{[key: string]: string}>({});
const [isEditing, setIsEditing] = useState(false);
```

#### 2E. Refs
```typescript
// DOM references and persistent value storage
const fileInputRef = useRef<HTMLInputElement>(null);
const wsRef = useRef<WebSocket | null>(null);
const lastDataRef = useRef<DataType | null>(null);
```

#### 2F. Custom Hook Integration
```typescript
// External hook integration
const { isConnected, on: subscribe, emit } = useWebSocket();
const { showBoundary } = useErrorBoundary();
```

### Section 3: Derived State (useMemo)
- **Purpose:** Expensive computations that depend on state
- **Rules:**
  - Use for complex calculations only
  - Always include proper dependencies
  - Keep computations pure

```typescript
const expensiveCalculation = useMemo(() => {
  return projects
    .filter(p => p.status === 'active')
    .map(p => ({ ...p, computedValue: complexOperation(p) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}, [projects]);
```

### Section 4: Callback Functions

#### Level 1 - Independent Utilities
- Pure functions with no dependencies on other callbacks
- Utility functions for formatting, validation, etc.
- Can depend on constants and imported utilities

```typescript
const formatDate = useCallback((date: string): string => {
  return new Date(date).toLocaleDateString();
}, []);

const validateEmail = useCallback((email: string): boolean => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}, []);
```

#### Level 2 - State-Only Dependent
- Functions that only depend on state setters
- Form handlers, simple state updates
- No dependencies on other callback functions

```typescript
const updateForm = useCallback((field: string, value: string) => {
  setFormData(prev => ({ ...prev, [field]: value }));
}, []);

const clearErrors = useCallback(() => {
  setError(null);
  setFormErrors({});
}, []);
```

#### Level 3 - Single Function Dependencies
- Functions that call one other callback
- Simple compositions
- Clear, linear dependency chain

```typescript
const loadData = useCallback(async () => {
  try {
    setLoading(true);
    const data = await apiService.getData();
    setData(data);
    showNotification('Data loaded successfully', 'success');
  } catch (err) {
    setError(getErrorMessage(err));
    showNotification('Failed to load data', 'error');
  } finally {
    setLoading(false);
  }
}, [showNotification]);
```

#### Level 4 - Multi-Function Dependencies
- Functions that orchestrate multiple operations
- Complex business logic
- Event handlers that trigger multiple actions

```typescript
const handleSave = useCallback(async () => {
  if (!validateForm()) return;
  
  try {
    await saveData(formData);
    await loadData();
    resetForm();
    closeDialog();
    showNotification('Saved successfully', 'success');
  } catch (err) {
    showNotification('Save failed', 'error');
  }
}, [validateForm, formData, loadData, resetForm, closeDialog, showNotification]);
```

### Section 5: Effect Hooks
- **Order:** Initial loading → Dependent loading → Subscriptions → Cleanup
- **Rules:**
  - Include all dependencies in dependency arrays
  - Use cleanup functions for subscriptions and timers
  - Keep effects focused on single concerns

```typescript
// Initial data loading
useEffect(() => {
  loadInitialData();
}, [loadInitialData]);

// Dependent loading
useEffect(() => {
  if (selectedId) {
    loadDetails(selectedId);
  }
}, [selectedId, loadDetails]);

// Subscriptions
useEffect(() => {
  if (!isConnected) return;
  
  const unsubscribe = subscribe('data_updated', handleUpdate);
  return () => unsubscribe?.();
}, [isConnected, subscribe, handleUpdate]);
```

### Section 6: Render Helpers
- Small utility functions for rendering logic
- Icon selection, color determination, formatting
- Keep simple and focused

```typescript
const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success': return <CheckCircle color="success" />;
    case 'error': return <Error color="error" />;
    default: return <Warning color="warning" />;
  }
};
```

### Section 7: Early Returns
- Handle loading states
- Handle error states  
- Handle empty states
- Return before main render logic

```typescript
if (loading) {
  return <LoadingSpinner />;
}

if (error) {
  return <ErrorDisplay error={error} onRetry={loadData} />;
}

if (data.length === 0) {
  return <EmptyState onAction={openDialog} />;
}
```

### Section 8: Main Render
- Primary component JSX
- Organized into logical sections with comments
- Consistent formatting and structure

## File-Specific Implementation Guidelines

### Dashboard.tsx
- Focus on real-time data updates
- WebSocket integration in Level 5 callbacks
- Statistics calculations in derived state
- Multiple data loading effects

### TestExecution.tsx
- Form validation in Level 1
- WebSocket management in Level 4-5
- Test session orchestration across levels
- Complex state transitions

### GroundTruth.tsx
- File validation utilities in Level 1
- Upload processing in Level 3-4
- Annotation management throughout levels
- Video player integration

### Projects.tsx  
- CRUD operations distributed across levels
- Form management in Level 2-3
- Project lifecycle in Level 4
- Video linking in Level 4

### Results.tsx
- Data transformation in derived state
- Statistical calculations in useMemo
- Export functionality in Level 3
- Analysis loading in Level 4

This standardized organization ensures consistency, maintainability, and TypeScript compliance across all components.