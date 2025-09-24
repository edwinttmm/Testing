import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box, CircularProgress, Typography } from '@mui/material';
import EnhancedErrorBoundary from './utils/enhancedErrorBoundary';
import GlobalErrorHandler from './components/ui/GlobalErrorHandler';
import { ErrorNotificationProvider } from './components/ui/ErrorNotification';
import Sidebar from './components/Layout/Sidebar';
import Header from './components/Layout/Header';
import ApiConnectionStatus from './components/ApiConnectionStatus';
import { initializeLogging } from './config/logging.config';
import { ComponentLogger, logErrorBoundary } from './utils/loggingUtils';
import { ErrorBoundaryError } from './types/error.types';
import { EnhancedErrorInfo, EnhancedErrorType } from './utils/enhancedErrorBoundary';

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Projects = lazy(() => import('./pages/Projects'));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'));
const GroundTruth = lazy(() => import('./pages/GroundTruth'));
const AnnotationValidation = lazy(() => import('./pages/AnnotationValidation'));
const TestExecution = lazy(() => import('./pages/TestExecution'));
const HILTestExecutionPRD = lazy(() => import('./pages/HILTestExecutionPRD'));
const Results = lazy(() => import('./pages/Results'));
const HILResults = lazy(() => import('./pages/HILResults'));
const Datasets = lazy(() => import('./pages/Datasets'));
const AuditLogs = lazy(() => import('./pages/AuditLogs'));
const Settings = lazy(() => import('./pages/Settings'));
const VideoTestComponent = lazy(() => import('./components/VideoTestComponent'));
const BoundaryBoxDemo = lazy(() => import('./pages/BoundaryBoxDemo'));

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
  components: {
    // Fix aria-hidden issues with modals by ensuring proper focus management
    MuiModal: {
      defaultProps: {
        // Prevent MUI from setting aria-hidden="true" on root element
        // when modal opens by managing focus properly
        disableAutoFocus: false,
        disableEnforceFocus: false,
        disableRestoreFocus: false,
      },
    },
    MuiDialog: {
      defaultProps: {
        // Ensure proper focus management for dialogs
        disableAutoFocus: false,
        disableEnforceFocus: false,
        disableRestoreFocus: false,
      },
    },
    // Fix Tooltip issues with disabled elements
    MuiTooltip: {
      defaultProps: {
        // Ensure tooltips work with disabled elements
        enterDelay: 300,
        leaveDelay: 0,
      },
    },
  },
});

// Loading fallback component
const LoadingFallback: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '200px',
      gap: 2,
    }}
  >
    <CircularProgress />
    <Typography variant="body1" color="text.secondary">
      {message}
    </Typography>
  </Box>
);

const App: React.FC = () => {
  const appLogger = new ComponentLogger('App');

  // Initialize logging system
  useEffect(() => {
    initializeLogging();
    appLogger.logger.info('Application initialized', {
      action: 'app_init',
      metadata: {
        environment: process.env.NODE_ENV,
        timestamp: new Date().toISOString()
      }
    });
    // appLogger.logger is stable and doesn't need to be in dependencies
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAppError = (error: ErrorBoundaryError, errorInfo: EnhancedErrorInfo, errorType: EnhancedErrorType) => {
    logErrorBoundary(error, { componentStack: errorInfo.componentStack || 'Unknown' }, 'App');
    appLogger.logger.error('App-level error caught', {
      action: 'error_boundary',
      metadata: { errorType, hasErrorInfo: !!errorInfo }
    }, error);
  };

  const handleGlobalError = (error: Error, source: string) => {
    appLogger.logger.error('Global error handler triggered', {
      action: 'global_error',
      metadata: { source }
    }, error);
  };

  return (
    <ErrorNotificationProvider>
      <EnhancedErrorBoundary
        level="app"
        context="application-root"
        onError={handleAppError}
        enableRetry={true}
        maxRetries={1}
        enableRecovery={true}
      >
        <GlobalErrorHandler onError={handleGlobalError} />
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <Router>
            <EnhancedErrorBoundary
            level="app" 
            context="router-navigation"
            enableRetry={true}
            enableRecovery={true}
          >
            <Box sx={{ display: 'flex' }}>
              <EnhancedErrorBoundary 
                level="component" 
                context="sidebar"
                enableRetry={false}
              >
                <Sidebar />
              </EnhancedErrorBoundary>
              
              <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
                <EnhancedErrorBoundary 
                  level="component" 
                  context="header"
                  enableRetry={false}
                >
                  <Header />
                </EnhancedErrorBoundary>
                
                {/* API Connection Status Monitor */}
                <ApiConnectionStatus />
                
                <EnhancedErrorBoundary
                  level="page"
                  context="main-content"
                  enableRetry={true}
                  maxRetries={2}
                  enableRecovery={true}
                >
                  <Suspense fallback={<LoadingFallback />}>
                    <Routes>
                      <Route path="/" element={
                        <EnhancedErrorBoundary level="page" context="dashboard" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Dashboard..." />}>
                            <Dashboard />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/projects" element={
                        <EnhancedErrorBoundary level="page" context="projects" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Projects..." />}>
                            <Projects />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/projects/:id" element={
                        <EnhancedErrorBoundary level="page" context="project-detail" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Project Details..." />}>
                            <ProjectDetail />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/ground-truth" element={
                        <EnhancedErrorBoundary level="page" context="ground-truth" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Ground Truth..." />}>
                            <GroundTruth />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/annotation-validation/:videoId" element={
                        <EnhancedErrorBoundary level="page" context="annotation-validation" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Annotation Validation..." />}>
                            <AnnotationValidation />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/test-execution" element={
                        <EnhancedErrorBoundary level="page" context="test-execution" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Test Execution..." />}>
                            <TestExecution />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/enhanced-test-execution" element={
                        <EnhancedErrorBoundary level="page" context="hil-test-execution" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading HIL Test Execution..." />}>
                            <HILTestExecutionPRD />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/results" element={
                        <EnhancedErrorBoundary level="page" context="results" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Results..." />}>
                            <Results />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/results/:sessionId" element={
                        <EnhancedErrorBoundary level="page" context="hil-results" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading HIL Results..." />}>
                            <HILResults />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/datasets" element={
                        <EnhancedErrorBoundary level="page" context="datasets" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Datasets..." />}>
                            <Datasets />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/audit-logs" element={
                        <EnhancedErrorBoundary level="page" context="audit-logs" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Audit Logs..." />}>
                            <AuditLogs />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/settings" element={
                        <EnhancedErrorBoundary level="page" context="settings" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Settings..." />}>
                            <Settings />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/video-test" element={
                        <EnhancedErrorBoundary level="page" context="video-test" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Video Test..." />}>
                            <VideoTestComponent />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                      <Route path="/boundary-box-demo" element={
                        <EnhancedErrorBoundary level="page" context="boundary-box-demo" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Boundary Box Demo..." />}>
                            <BoundaryBoxDemo />
                          </Suspense>
                        </EnhancedErrorBoundary>
                      } />
                    </Routes>
                  </Suspense>
                </EnhancedErrorBoundary>
              </Box>
            </Box>
            </EnhancedErrorBoundary>
          </Router>
        </ThemeProvider>
      </EnhancedErrorBoundary>
    </ErrorNotificationProvider>
  );
};

export default App;
