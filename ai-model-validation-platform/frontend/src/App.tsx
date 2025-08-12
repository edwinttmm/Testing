import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box, CircularProgress, Typography } from '@mui/material';
import ErrorBoundary from './components/ui/ErrorBoundary';
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
    <ErrorBoundary
      level="app"
      context="application-root"
      onError={handleAppError}
      enableRetry={true}
      maxRetries={1}
    >
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Router>
          <ErrorBoundary
            level="app" 
            context="router-navigation"
            enableRetry={true}
          >
            <Box sx={{ display: 'flex' }}>
              <ErrorBoundary 
                level="component" 
                context="sidebar"
                enableRetry={false}
              >
                <Sidebar />
              </ErrorBoundary>
              
              <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
                <ErrorBoundary 
                  level="component" 
                  context="header"
                  enableRetry={false}
                >
                  <Header />
                </ErrorBoundary>
                
                <ErrorBoundary
                  level="page"
                  context="main-content"
                  enableRetry={true}
                  maxRetries={2}
                >
                  <Suspense fallback={<LoadingFallback />}>
                    <Routes>
                      <Route path="/" element={
                        <ErrorBoundary level="page" context="dashboard">
                          <Suspense fallback={<LoadingFallback message="Loading Dashboard..." />}>
                            <Dashboard />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/projects" element={
                        <ErrorBoundary level="page" context="projects">
                          <Suspense fallback={<LoadingFallback message="Loading Projects..." />}>
                            <Projects />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/projects/:id" element={
                        <ErrorBoundary level="page" context="project-detail">
                          <Suspense fallback={<LoadingFallback message="Loading Project Details..." />}>
                            <ProjectDetail />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/ground-truth" element={
                        <ErrorBoundary level="page" context="ground-truth">
                          <Suspense fallback={<LoadingFallback message="Loading Ground Truth..." />}>
                            <GroundTruth />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/test-execution" element={
                        <ErrorBoundary level="page" context="test-execution">
                          <Suspense fallback={<LoadingFallback message="Loading Test Execution..." />}>
                            <TestExecution />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/results" element={
                        <ErrorBoundary level="page" context="results">
                          <Suspense fallback={<LoadingFallback message="Loading Results..." />}>
                            <Results />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/datasets" element={
                        <ErrorBoundary level="page" context="datasets">
                          <Suspense fallback={<LoadingFallback message="Loading Datasets..." />}>
                            <Datasets />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/audit-logs" element={
                        <ErrorBoundary level="page" context="audit-logs">
                          <Suspense fallback={<LoadingFallback message="Loading Audit Logs..." />}>
                            <AuditLogs />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                      <Route path="/settings" element={
                        <ErrorBoundary level="page" context="settings">
                          <Suspense fallback={<LoadingFallback message="Loading Settings..." />}>
                            <Settings />
                          </Suspense>
                        </ErrorBoundary>
                      } />
                    </Routes>
                  </Suspense>
                </ErrorBoundary>
              </Box>
            </Box>
          </ErrorBoundary>
        </Router>
      </ThemeProvider>
    </ErrorBoundary>
  );
};

export default App;
