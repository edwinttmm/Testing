import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box, CircularProgress, Typography } from '@mui/material';
import EnhancedErrorBoundary from './utils/enhancedErrorBoundary';
import Sidebar from './components/Layout/Sidebar';
import Header from './components/Layout/Header';

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Projects = lazy(() => import('./pages/Projects'));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'));
const GroundTruth = lazy(() => import('./pages/GroundTruth'));
const TestExecution = lazy(() => import('./pages/TestExecution'));
const Results = lazy(() => import('./pages/Results'));
const Datasets = lazy(() => import('./pages/Datasets'));
const AuditLogs = lazy(() => import('./pages/AuditLogs'));
const Settings = lazy(() => import('./pages/Settings'));

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
  const handleAppError = (error: Error, errorInfo: any, errorType: any) => {
    console.error('App-level error caught:', { error, errorInfo, errorType });
    // Send to error tracking service in production
  };

  return (
    <EnhancedErrorBoundary
      level="app"
      context="application-root"
      onError={handleAppError}
      enableRetry={true}
      maxRetries={1}
      enableRecovery={true}
    >
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
                      <Route path="/test-execution" element={
                        <EnhancedErrorBoundary level="page" context="test-execution" enableRecovery={true}>
                          <Suspense fallback={<LoadingFallback message="Loading Test Execution..." />}>
                            <TestExecution />
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
                    </Routes>
                  </Suspense>
                </EnhancedErrorBoundary>
              </Box>
            </Box>
          </EnhancedErrorBoundary>
        </Router>
      </ThemeProvider>
    </EnhancedErrorBoundary>
  );
};

export default App;
