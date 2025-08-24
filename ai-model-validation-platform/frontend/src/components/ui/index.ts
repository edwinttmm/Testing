/**
 * Unified UI Components Export
 * Consolidates all standardized UI components into a single export point
 */

// ============================================================================
// CORE COMPONENTS
// ============================================================================

// Standardized Grid System
export {
  default as StandardizedGrid,
  CenteredGrid,
  ResponsiveCardGrid,
  FullWidthGrid,
  HalfWidthGrid,
  createResponsiveGrid,
  createFlexGrid,
  GridBreakpoints,
  GridColumns,
  useResponsiveGrid,
  type StandardizedGridProps,
  type ResponsiveValue,
} from './StandardizedGrid';

// Unified Error Boundaries
export {
  default as UnifiedErrorBoundary,
  StandardErrorBoundary,
  WebSocketErrorBoundary,
  AsyncErrorBoundary,
  withUnifiedErrorBoundary,
  UnifiedErrorType,
  type UnifiedErrorBoundaryProps,
  type UnifiedErrorInfo,
  type BoundaryType,
} from './UnifiedErrorBoundary';

// Fixed UI Components (Enhanced versions of MUI components)
export {
  FixedListItem,
  FixedGrid,
  EnhancedButton,
  EnhancedTextField,
  EnhancedFormControl,
  EnhancedAlert,
  EnhancedSkeleton,
  LoadingWrapper,
  ErrorFallback,
} from './FixedUIComponents';

// ============================================================================
// COMPONENT STANDARDS AND UTILITIES
// ============================================================================

export {
  type BaseComponentProps,
  type ComponentPropsWithChildren,
  type LoadingComponentProps,
  type ErrorComponentProps,
  type AsyncComponentProps,
  type StandardComponent,
  type ForwardRefComponent,
  ComponentNaming,
  type RequiredProps,
  type OptionalProps,
  type ExplicitChildrenProps,
  type ComponentWithHTMLProps,
  type ComponentConfig,
  isValidReactNode,
  hasChildren,
  createStandardComponent,
  type ConditionalRenderProps,
  type CompoundComponentProps,
  type PolymorphicComponent,
  validateComponentProps,
  migrateFromReactFC,
  createComponent,
  type ComponentExports,
} from './ComponentStandards';

// ============================================================================
// BACKWARD COMPATIBILITY ALIASES
// ============================================================================

// Alias for existing error boundary components
export { default as ErrorBoundary, withErrorBoundary } from './ErrorBoundary';
export { default as LegacyWebSocketErrorBoundary } from './WebSocketErrorBoundary';
export { default as LegacyAsyncErrorBoundary } from './AsyncErrorBoundary';

// Grid aliases for migration
export { FixedGrid as Grid } from './FixedUIComponents';

// ============================================================================
// COMPONENT MIGRATION MAP
// ============================================================================

/**
 * Migration guide for updating component imports
 */
export const MigrationMap = {
  // Error Boundaries
  'ErrorBoundary': 'UnifiedErrorBoundary with boundaryType="standard"',
  'WebSocketErrorBoundary': 'UnifiedErrorBoundary with boundaryType="websocket"',
  'AsyncErrorBoundary': 'UnifiedErrorBoundary with boundaryType="async"',
  'EnhancedErrorBoundary': 'UnifiedErrorBoundary (direct replacement)',
  
  // Grid Components
  'Grid': 'StandardizedGrid',
  'FixedGrid': 'StandardizedGrid',
  'MUI Grid': 'StandardizedGrid',
  
  // Component Patterns
  'React.FC': 'StandardComponent type',
  'React.FunctionComponent': 'StandardComponent type',
  'FC': 'StandardComponent type',
} as const;

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

/**
 * Default export provides the most commonly used components
 */
export default {
  // Most used components
  Grid: require('./StandardizedGrid').default,
  ErrorBoundary: require('./UnifiedErrorBoundary').default,
  Button: require('./FixedUIComponents').EnhancedButton,
  TextField: require('./FixedUIComponents').EnhancedTextField,
  Alert: require('./FixedUIComponents').EnhancedAlert,
  Loading: require('./FixedUIComponents').LoadingWrapper,
  
  // Utilities
  createComponent: require('./ComponentStandards').createComponent,
  createResponsiveGrid: require('./StandardizedGrid').createResponsiveGrid,
  useResponsiveGrid: require('./StandardizedGrid').useResponsiveGrid,
  
  // Migration helpers
  migrateFromReactFC: require('./ComponentStandards').migrateFromReactFC,
  MigrationMap,
};