/**
 * Component Type Standards
 * Defines standardized patterns and types for consistent component development
 */

import { ReactNode, ComponentType, RefAttributes, ForwardRefExoticComponent } from 'react';

// ============================================================================
// COMPONENT TYPE PATTERNS
// ============================================================================

/**
 * Standard component props interface
 * Use this as a base for all component props
 */
export interface BaseComponentProps {
  /** Component children */
  children?: ReactNode;
  /** CSS class name */
  className?: string;
  /** Test ID for testing */
  'data-testid'?: string;
  /** Component ID */
  id?: string;
}

/**
 * Props with required children
 */
export interface ComponentPropsWithChildren extends BaseComponentProps {
  children: ReactNode;
}

/**
 * Props for components that handle loading states
 */
export interface LoadingComponentProps extends BaseComponentProps {
  loading?: boolean;
  loadingText?: string;
  loadingComponent?: ReactNode;
}

/**
 * Props for components that handle error states
 */
export interface ErrorComponentProps extends BaseComponentProps {
  error?: Error | string | null;
  errorComponent?: ReactNode;
  onRetry?: () => void;
}

/**
 * Combined props for async components
 */
export interface AsyncComponentProps extends LoadingComponentProps, ErrorComponentProps {
  data?: any;
  onRefresh?: () => void;
}

// ============================================================================
// COMPONENT DECLARATION PATTERNS
// ============================================================================

/**
 * PREFERRED: Function component with explicit return type
 * This is the recommended pattern for new components
 */
export type StandardComponent<P = {}> = (props: P) => JSX.Element;

/**
 * PREFERRED: Function component with forwardRef
 * Use this pattern when you need ref forwarding
 */
export type ForwardRefComponent<P = {}, T = HTMLElement> = ForwardRefExoticComponent<P & RefAttributes<T>>;

/**
 * DEPRECATED: React.FC usage - avoid this pattern
 * @deprecated Use StandardComponent instead for better type safety
 */
export type DeprecatedReactFC<P = {}> = ComponentType<P>;

// ============================================================================
// COMPONENT NAMING CONVENTIONS
// ============================================================================

/**
 * Component naming patterns
 */
export const ComponentNaming = {
  // Base components (no prefix)
  BASE: '',
  // Enhanced components with additional features
  ENHANCED: 'Enhanced',
  // Fixed components that address specific issues
  FIXED: 'Fixed',
  // Standardized components following our patterns
  STANDARDIZED: 'Standardized',
  // Unified components that consolidate multiple implementations
  UNIFIED: 'Unified',
} as const;

// ============================================================================
// PROP TYPE UTILITIES
// ============================================================================

/**
 * Utility to make props optional except for specified required ones
 */
export type RequiredProps<T, K extends keyof T> = T & Required<Pick<T, K>>;

/**
 * Utility to make all props optional
 */
export type OptionalProps<T> = Partial<T>;

/**
 * Utility to exclude React.FC implicit children
 */
export type ExplicitChildrenProps<T> = Omit<T, 'children'> & ComponentPropsWithChildren;

/**
 * Utility for component props that extend HTML element props
 */
export type ComponentWithHTMLProps<T, E extends HTMLElement = HTMLDivElement> = 
  T & React.HTMLAttributes<E>;

// ============================================================================
// COMPONENT CONFIGURATION
// ============================================================================

/**
 * Standard component configuration options
 */
export interface ComponentConfig {
  /** Display name for debugging */
  displayName?: string;
  /** Default props */
  defaultProps?: Record<string, any>;
  /** Development mode warnings */
  devWarnings?: boolean;
  /** Accessibility requirements */
  a11y?: {
    required?: boolean;
    ariaLabel?: string;
    role?: string;
  };
}

// ============================================================================
// TYPE GUARDS AND UTILITIES
// ============================================================================

/**
 * Type guard to check if a value is a valid React node
 */
export const isValidReactNode = (value: any): value is ReactNode => {
  return value !== undefined && value !== null && typeof value !== 'boolean';
};

/**
 * Type guard to check if props include children
 */
export const hasChildren = (props: any): props is ComponentPropsWithChildren => {
  return props && 'children' in props && isValidReactNode(props.children);
};

/**
 * Utility to create a component with standard configuration
 */
export const createStandardComponent = <P extends BaseComponentProps>(
  component: StandardComponent<P>,
  config?: ComponentConfig
): StandardComponent<P> => {
  if (config?.displayName) {
    component.displayName = config.displayName;
  }

  if (config?.devWarnings && process.env.NODE_ENV === 'development') {
    const originalComponent = component;
    component = (props: P) => {
      // Add development warnings
      if (config.a11y?.required && !props['aria-label'] && !props.id) {
        console.warn(`Component ${config.displayName || 'Unknown'} should have aria-label or id for accessibility`);
      }
      return originalComponent(props);
    };
  }

  return component;
};

// ============================================================================
// COMPONENT PATTERNS
// ============================================================================

/**
 * Pattern for components with conditional rendering
 */
export interface ConditionalRenderProps extends BaseComponentProps {
  when?: boolean;
  fallback?: ReactNode;
}

/**
 * Pattern for compound components
 */
export interface CompoundComponentProps extends BaseComponentProps {
  as?: keyof JSX.IntrinsicElements | ComponentType<any>;
}

/**
 * Pattern for polymorphic components
 */
export type PolymorphicComponent<P, T extends keyof JSX.IntrinsicElements = 'div'> = {
  [K in T]: (props: P & JSX.IntrinsicElements[K]) => JSX.Element;
}[T];

// ============================================================================
// VALIDATION UTILITIES
// ============================================================================

/**
 * Validates component props at runtime in development
 */
export const validateComponentProps = <P extends BaseComponentProps>(
  props: P,
  componentName: string,
  required: (keyof P)[] = []
): void => {
  if (process.env.NODE_ENV !== 'development') return;

  // Check required props
  required.forEach(prop => {
    if (props[prop] === undefined || props[prop] === null) {
      console.error(`${componentName}: Required prop '${String(prop)}' is missing`);
    }
  });

  // Check for deprecated patterns
  if ('children' in props && typeof props.children === 'boolean') {
    console.warn(`${componentName}: Boolean children are not recommended`);
  }

  // Check accessibility
  if (!props['aria-label'] && !props.id && props.role) {
    console.warn(`${componentName}: Components with roles should have aria-label or id`);
  }
};

// ============================================================================
// MIGRATION HELPERS
// ============================================================================

/**
 * Utility to help migrate from React.FC to standard patterns
 */
export const migrateFromReactFC = <P extends BaseComponentProps>(
  component: React.FC<P>
): StandardComponent<P> => {
  const migratedComponent: StandardComponent<P> = (props: P) => {
    if (process.env.NODE_ENV === 'development') {
      console.warn(`Component is using deprecated React.FC pattern. Consider migrating to StandardComponent.`);
    }
    return component(props) as JSX.Element;
  };

  migratedComponent.displayName = component.displayName || 'MigratedComponent';
  return migratedComponent;
};

// ============================================================================
// EXPORT PATTERNS
// ============================================================================

/**
 * Standard export pattern for components
 */
export interface ComponentExports<P = {}> {
  /** Main component */
  default: StandardComponent<P>;
  /** Component props type */
  Props: P;
  /** Component configuration */
  config?: ComponentConfig;
}

// ============================================================================
// COMPONENT FACTORY PATTERNS
// ============================================================================

/**
 * Factory for creating consistent components
 */
export const createComponent = <P extends BaseComponentProps>(
  render: StandardComponent<P>,
  options: {
    displayName: string;
    defaultProps?: Partial<P>;
    propValidation?: (keyof P)[];
    memo?: boolean;
  }
): StandardComponent<P> => {
  const component = options.memo 
    ? React.memo(render) as StandardComponent<P>
    : render;

  component.displayName = options.displayName;

  if (options.defaultProps) {
    (component as any).defaultProps = options.defaultProps;
  }

  // Wrap with prop validation in development
  if (process.env.NODE_ENV === 'development' && options.propValidation) {
    const validatedComponent: StandardComponent<P> = (props: P) => {
      validateComponentProps(props, options.displayName, options.propValidation);
      return component(props);
    };
    validatedComponent.displayName = options.displayName;
    return validatedComponent;
  }

  return component;
};

// Re-export React types for consistency
export type { ReactNode, ComponentType, RefAttributes, ForwardRefExoticComponent } from 'react';