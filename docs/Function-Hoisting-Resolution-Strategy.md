# Function Hoisting Resolution Strategy

## Problem Analysis

The primary TypeScript errors across the 5 React components stem from **function hoisting violations** where functions are accessed before their definition in the same functional component scope.

## Error Patterns Identified

### Pattern 1: useEffect Accessing Undefined Functions

```typescript
// ❌ PROBLEM: Function accessed before definition
useEffect(() => {
  loadProjects(); // Error: Cannot access 'loadProjects' before initialization
}, [loadProjects]);

const loadProjects = useCallback(async () => {
  // Function implementation
}, []);
```

### Pattern 2: Circular Function Dependencies

```typescript
// ❌ PROBLEM: Circular dependency chain
const functionA = useCallback(() => {
  functionB(); // functionB not defined yet
}, [functionB]);

const functionB = useCallback(() => {
  functionA(); // Creates circular dependency
}, [functionA]);
```

### Pattern 3: Event Handler Dependencies

```typescript
// ❌ PROBLEM: Event handler accessing undefined function  
useEffect(() => {
  if (isConnected) {
    const unsubscribe = subscribe('event', handleEvent); // handleEvent not defined
    return unsubscribe;
  }
}, [isConnected, subscribe, handleEvent]);

const handleEvent = useCallback((data) => {
  // Handler implementation
}, []);
```

## Systematic Resolution Architecture

### 1. Function Declaration Order Strategy

#### A. Dependency Mapping
```
Level 1: Independent Utilities
├── formatTimeAgo()
├── validateVideoFile()  
├── formatFileSize()
└── getStatusIcon()

Level 2: State-Only Dependent
├── resetForm()
├── updateStatsSafely()
└── showSnackbar()

Level 3: Single Function Dependent  
├── handleFormChange() → depends on resetForm()
├── handleVideoUploaded() → depends on updateStatsSafely()  
└── loadAnnotations() → depends on validateVideoFile()

Level 4: Multi-Function Dependent
├── loadProjects() → depends on showSnackbar() + resetForm()
├── handleFileSelect() → depends on validateVideoFile() + uploadFiles()
└── startTestExecution() → depends on loadTestSessions() + showSnackbar()

Level 5: Complex Dependencies
├── connectWebSocket() → depends on handleWebSocketMessage() + currentSession
└── fetchDashboardStats() → depends on multiple Level 3 functions
```

#### B. Declaration Template

```typescript
const ComponentName: React.FC = () => {
  // ====== STATE DECLARATIONS ======
  const [state, setState] = useState<Type>(initialValue);
  
  // ====== LEVEL 1: INDEPENDENT UTILITIES ======
  const utilityFunction1 = useCallback((param: Type): ReturnType => {
    // Pure function - no dependencies on other functions
    return processedValue;
  }, []);
  
  const utilityFunction2 = useCallback((param: Type): ReturnType => {
    // Another pure utility function
    return processedValue;
  }, []);
  
  // ====== LEVEL 2: STATE-DEPENDENT FUNCTIONS ======
  const stateFunction = useCallback(async () => {
    try {
      setState(newValue);
    } catch (error) {
      handleError(error);
    }
  }, []); // Only state dependencies, no function dependencies
  
  // ====== LEVEL 3: SINGLE FUNCTION DEPENDENCIES ======
  const dependentFunction = useCallback(async (param: Type) => {
    const result = utilityFunction1(param);
    await stateFunction();
    return result;
  }, [utilityFunction1, stateFunction]);
  
  // ====== LEVEL 4: MULTI-FUNCTION DEPENDENCIES ======
  const complexFunction = useCallback(async (param: Type) => {
    const validated = utilityFunction1(param);
    if (validated) {
      await dependentFunction(param);
      stateFunction();
    }
  }, [utilityFunction1, dependentFunction, stateFunction]);
  
  // ====== EFFECTS (AFTER ALL FUNCTION DECLARATIONS) ======
  useEffect(() => {
    complexFunction(initialParam);
  }, [complexFunction]);
  
  return <JSX />;
};
```

### 2. File-Specific Resolution Plans

#### A. Dashboard.tsx Resolution

**Current Issues:**
- `formatTimeAgo` used in JSX but defined after render
- `updateStatsSafely` used in event handlers before definition  
- WebSocket handlers accessing undefined functions

**Resolution Order:**
```typescript
// 1. Independent utilities first
const formatTimeAgo = useCallback((dateString: string | null | undefined) => {
  if (!dateString) return 'Unknown time';
  const date = new Date(dateString);
  const now = new Date();
  const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
  
  if (diffInMinutes < 1) return 'Just now';
  if (diffInMinutes < 60) return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`;
  if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hour${Math.floor(diffInMinutes / 60) > 1 ? 's' : ''} ago`;
  return `${Math.floor(diffInMinutes / 1440)} day${Math.floor(diffInMinutes / 1440) > 1 ? 's' : ''} ago`;
}, []);

// 2. State update function
const updateStatsSafely = useCallback((updater: (prevStats: EnhancedDashboardStats) => EnhancedDashboardStats) => {
  setStats(prevStats => {
    if (!prevStats) return prevStats;
    const newStats = updater(prevStats);
    lastStatsRef.current = newStats;
    return newStats;
  });
}, []);

// 3. Event handlers (depend on updateStatsSafely)
const handleVideoUploaded = useCallback((data: VideoFile) => {
  console.log('📹 Video uploaded event received:', data);
  updateStatsSafely(prevStats => ({
    ...prevStats,
    video_count: prevStats.video_count + 1
  }));
  setRealtimeUpdates(prev => prev + 1);
}, [updateStatsSafely]);

// 4. Data fetching (independent of event handlers)
const fetchDashboardStats = useCallback(async () => {
  try {
    setLoading(true);
    const [statsResult, sessionsResult] = await Promise.allSettled([
      getDashboardStats(),
      getTestSessions()
    ]);
    // Processing logic...
  } catch (err) {
    console.error('Failed to fetch dashboard data:', err);
  } finally {
    setLoading(false);
  }
}, []);

// 5. Effects use all declared functions
useEffect(() => {
  if (!isConnected) return;
  
  const unsubscribeVideo = subscribe('video_uploaded', handleVideoUploaded);
  // ... other subscriptions
  
  return () => {
    unsubscribeVideo?.();
  };
}, [isConnected, subscribe, handleVideoUploaded, /* other handlers */]);
```

#### B. TestExecution.tsx Resolution

**Current Issues:**
- Functions called in useEffect before definition (lines 105, 110, 117, 125)
- Circular dependencies between WebSocket and session management

**Resolution Order:**
```typescript
// 1. Independent validation
const validateSession = useCallback((session: TestSession): boolean => {
  return session.name && session.videoIds && session.videoIds.length > 0;
}, []);

// 2. Data loading functions (no interdependencies)
const loadProjects = useCallback(async () => {
  try {
    setLoading(true);
    const response = await apiService.get<Project[]>('/api/projects');
    setProjects(response);
    if (response.length > 0) {
      setSelectedProject(response[0]);
    }
  } catch (err: any) {
    setError(err.message || 'Failed to load projects');
    showSnackbar('Failed to load projects', 'error');
  } finally {
    setLoading(false);
  }
}, []);

const loadTestSessions = useCallback(async () => {
  if (!selectedProject) return;
  
  try {
    setLoading(true);
    const response = await apiService.get<TestSession[]>(`/api/projects/${selectedProject.id}/test-sessions`);
    setSessions(response);
  } catch (err: any) {
    setError(err.message || 'Failed to load test sessions');
    showSnackbar('Failed to load test sessions', 'error');
  } finally {
    setLoading(false);
  }
}, [selectedProject]);

// 3. WebSocket message handling (independent)
const handleWebSocketMessage = useCallback((data: any) => {
  switch (data.type) {
    case 'test_progress':
      updateTestProgress(data.payload);
      break;
    case 'test_result':
      addTestResult(data.payload);
      break;
    case 'test_completed':
      handleTestCompletion(data.payload);
      break;
    case 'test_error':
      handleTestError(data.payload);
      break;
    default:
      console.log('Unknown WebSocket message:', data);
  }
}, []);

// 4. WebSocket connection (depends on message handler and currentSession)
const connectWebSocket = useCallback(() => {
  const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8001';
  wsRef.current = new WebSocket(`${wsUrl}/ws/test-execution/${currentSession?.id}`);
  
  wsRef.current.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleWebSocketMessage(data);
  };
  
  wsRef.current.onerror = (error) => {
    console.error('WebSocket error:', error);
    showSnackbar('WebSocket connection error', 'error');
  };
  
  wsRef.current.onclose = () => {
    if (isRunning) {
      setTimeout(connectWebSocket, 3000);
    }
  };
}, [currentSession, handleWebSocketMessage, isRunning]);

// 5. Test execution functions (depend on previous functions)
const startTestExecution = useCallback(async (session: TestSession) => {
  if (!validateSession(session)) {
    showSnackbar('Invalid session configuration', 'error');
    return;
  }
  
  try {
    setIsRunning(true);
    setCurrentSession(session);
    setTestResults([]);
    
    await apiService.post(`/api/test-sessions/${session.id}/start`);
    showSnackbar('Test execution started', 'success');
    
    setSessions(prevSessions => 
      prevSessions.map(s => 
        s.id === session.id ? { ...s, status: 'running' as const } : s
      )
    );
    
  } catch (err: any) {
    setIsRunning(false);
    setError(err.message || 'Failed to start test execution');
    showSnackbar('Failed to start test execution', 'error');
  }
}, [validateSession]);

// 6. Effects use all declared functions
useEffect(() => {
  loadProjects();
}, [loadProjects]);

useEffect(() => {
  if (selectedProject) {
    loadTestSessions();
  }
}, [selectedProject, loadTestSessions]);

useEffect(() => {
  if (isRunning && currentSession) {
    connectWebSocket();
  }
  
  return () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
  };
}, [isRunning, currentSession, connectWebSocket]);
```

#### C. GroundTruth.tsx Resolution

**Current Issues:**
- `loadVideos` and `loadAnnotations` used in useEffect before definition (lines 186, 193)
- Circular dependencies in file upload chain

**Resolution Order:**
```typescript
// 1. Independent utilities
const validateVideoFile = useCallback((file: File): string | null => {
  const extension = file.name.split('.').pop()?.toLowerCase();
  
  if (!extension || !SUPPORTED_FORMATS.includes(extension)) {
    return `Unsupported format. Please use: ${SUPPORTED_FORMATS.join(', ').toUpperCase()}`;
  }
  
  if (file.size > MAX_FILE_SIZE) {
    return `File too large. Maximum size: ${formatFileSize(MAX_FILE_SIZE)}`;
  }
  
  return null;
}, []);

const formatFileSize = useCallback((bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}, []);

// 2. Data loading functions  
const loadVideos = useCallback(async () => {
  if (!projectId) {
    setError('No project ID provided');
    return;
  }
  
  try {
    setError(null);
    const videoList = await apiService.getVideos(projectId);
    setVideos(videoList);
  } catch (err) {
    const errorMsg = getErrorMessage(err, 'Backend connection failed');
    setError(`Failed to load videos: ${errorMsg}`);
    console.error('Error loading videos:', errorMsg, err);
  }
}, [projectId]);

const loadAnnotations = useCallback(async (videoId: string) => {
  try {
    const annotationList = await apiService.getAnnotations(videoId);
    setAnnotations(annotationList);
    
    detectionIdManager.clear();
    annotationList.forEach(annotation => {
      createDetectionTracker(
        annotation.detectionId,
        annotation.vruType,
        annotation.frameNumber,
        annotation.timestamp,
        annotation.boundingBox,
        1.0
      );
    });
  } catch (err) {
    console.error('Error loading annotations:', err);
    setAnnotations([]);
  }
}, []);

// 3. File processing functions (depend on utilities)
const uploadFiles = useCallback(async (files: File[]) => {
  const newUploadingVideos: UploadingVideo[] = files.map(file => ({
    id: Math.random().toString(36).substr(2, 9),
    file,
    name: file.name,
    size: formatFileSize(file.size),
    progress: 0,
    status: 'uploading'
  }));
  
  setUploadingVideos(prev => [...prev, ...newUploadingVideos]);
  setUploadDialog(false);
  
  // Upload processing logic...
}, [formatFileSize]);

const handleFileSelect = useCallback((files: FileList | null) => {
  if (!files) return;
  
  const newUploadErrors: UploadError[] = [];
  const validFiles: File[] = [];
  
  Array.from(files).forEach(file => {
    const validationError = validateVideoFile(file);
    if (validationError) {
      newUploadErrors.push({
        message: validationError,
        fileName: file.name
      });
    } else {
      validFiles.push(file);
    }
  });
  
  setUploadErrors(newUploadErrors);
  
  if (validFiles.length > 0) {
    uploadFiles(validFiles);
  }
}, [validateVideoFile, uploadFiles]);

// 4. Effects use all declared functions
useEffect(() => {
  if (projectId) {
    loadVideos();
  }
}, [projectId, loadVideos]);

useEffect(() => {
  if (selectedVideo) {
    loadAnnotations(selectedVideo.id);
    setTotalFrames(Math.floor((selectedVideo.duration || 0) * frameRate));
  }
}, [selectedVideo, frameRate, loadAnnotations]);
```

### 3. Validation Checklist

#### Pre-Implementation Validation
- [ ] Map all function dependencies in each component
- [ ] Identify circular dependency chains  
- [ ] Plan declaration order for each file
- [ ] Verify no function is used before declaration

#### Post-Implementation Validation
- [ ] TypeScript compilation succeeds without errors
- [ ] ESLint `no-use-before-define` violations resolved
- [ ] All useCallback dependencies properly declared
- [ ] No runtime React warnings about missing dependencies
- [ ] Component functionality preserved
- [ ] Performance maintained (no infinite renders)

### 4. Common Pitfalls to Avoid

#### A. Don't Create New Dependencies
```typescript
// ❌ BAD: Adding unnecessary dependencies
const functionA = useCallback(() => {
  functionB(); // Creates dependency
}, [functionB]);

// ✅ GOOD: Keep functions independent when possible
const functionA = useCallback(() => {
  // Direct implementation without calling functionB
}, []);
```

#### B. Don't Move Effects Above Dependencies
```typescript
// ❌ BAD: Effect declared before function
useEffect(() => {
  loadData(); // Function not defined yet
}, [loadData]);

const loadData = useCallback(() => {}, []);

// ✅ GOOD: Function declared before effect
const loadData = useCallback(() => {}, []);

useEffect(() => {
  loadData();
}, [loadData]);
```

#### C. Don't Ignore ESLint Warnings
```typescript
// ❌ BAD: Suppressing warnings
useEffect(() => {
  loadData();
}, []); // eslint-disable-line react-hooks/exhaustive-deps

// ✅ GOOD: Include proper dependencies  
const loadData = useCallback(() => {}, []);

useEffect(() => {
  loadData();
}, [loadData]);
```

This systematic approach ensures all function hoisting issues are resolved while maintaining code quality and component functionality.