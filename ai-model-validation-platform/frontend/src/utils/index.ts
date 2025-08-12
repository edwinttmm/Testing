// Error handling utilities
export * from './errorTypes';

// Error boundary hooks
export * from '../hooks/useErrorBoundary';

// Error reporting service
export { default as errorReporting } from '../services/errorReporting';
export type { ErrorReport, ErrorReportingConfig } from '../services/errorReporting';