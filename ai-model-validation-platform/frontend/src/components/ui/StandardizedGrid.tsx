/**
 * Standardized Grid Component
 * Consolidates all Grid implementations into a single, consistent component
 */

import React, { memo, forwardRef, ReactNode } from 'react';
import { Grid, GridProps, useTheme, useMediaQuery } from '@mui/material';

// Enhanced breakpoint system with more granular control
export interface ResponsiveValue {
  xs?: boolean | number | 'auto';
  sm?: boolean | number | 'auto';
  md?: boolean | number | 'auto';
  lg?: boolean | number | 'auto';
  xl?: boolean | number | 'auto';
}

export interface StandardizedGridProps extends Omit<GridProps, 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'container' | 'direction'> {
  children: ReactNode;
  
  // Container/Item configuration
  container?: boolean;
  item?: boolean; // Kept for backward compatibility, but not used in modern MUI
  
  // Responsive breakpoints
  xs?: boolean | number | 'auto';
  sm?: boolean | number | 'auto';
  md?: boolean | number | 'auto';
  lg?: boolean | number | 'auto';
  xl?: boolean | number | 'auto';
  
  // Enhanced responsive configuration
  responsive?: ResponsiveValue;
  
  // Spacing configuration
  spacing?: number | string | { xs?: number; sm?: number; md?: number; lg?: number; xl?: number };
  
  // Layout utilities - Fixed to use proper types
  direction?: 'row' | 'column' | 'row-reverse' | 'column-reverse';
  justifyContent?: 'flex-start' | 'center' | 'flex-end' | 'space-between' | 'space-around' | 'space-evenly';
  alignItems?: 'flex-start' | 'center' | 'flex-end' | 'stretch' | 'baseline';
  wrap?: 'nowrap' | 'wrap' | 'wrap-reverse';
  
  // Accessibility
  role?: string;
  'aria-label'?: string;
  
  // Performance optimization
  disableEqualOverflow?: boolean;
  
  // Debug mode for development
  debug?: boolean;
}

/**
 * Standardized Grid Component
 * 
 * Features:
 * - Modern MUI Grid API (no deprecated 'item' prop needed)
 * - Enhanced responsive configuration
 * - Flexible spacing options
 * - Layout utilities
 * - Accessibility support
 * - Debug mode for development
 * - TypeScript-first design
 */
export const StandardizedGrid = memo(forwardRef<HTMLDivElement, StandardizedGridProps>(({
  children,
  container = false,
  item, // Deprecated in MUI v7+, ignored
  xs,
  sm,
  md,
  lg,
  xl,
  responsive,
  spacing,
  direction = 'row',
  justifyContent,
  alignItems,
  wrap = 'wrap',
  role,
  'aria-label': ariaLabel,
  disableEqualOverflow,
  debug = false,
  sx,
  ...props
}, ref) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // Handle responsive values from the responsive prop
  const finalBreakpoints = responsive ? {
    xs: responsive.xs ?? xs,
    sm: responsive.sm ?? sm,
    md: responsive.md ?? md,
    lg: responsive.lg ?? lg,
    xl: responsive.xl ?? xl,
  } : { xs, sm, md, lg, xl };

  // Build the Grid props object
  const gridProps: GridProps = {
    ref,
    ...(container && { container: true }),
    
    // Apply breakpoints only if they're defined
    ...(finalBreakpoints.xs !== undefined && { xs: finalBreakpoints.xs }),
    ...(finalBreakpoints.sm !== undefined && { sm: finalBreakpoints.sm }),
    ...(finalBreakpoints.md !== undefined && { md: finalBreakpoints.md }),
    ...(finalBreakpoints.lg !== undefined && { lg: finalBreakpoints.lg }),
    ...(finalBreakpoints.xl !== undefined && { xl: finalBreakpoints.xl }),
    
    // Container-specific props
    ...(container && {
      ...(spacing !== undefined && { spacing }),
      ...(direction && { direction }),
      ...(justifyContent && { justifyContent }),
      ...(alignItems && { alignItems }),
      ...(wrap && { wrap }),
      ...(disableEqualOverflow && { disableEqualOverflow }),
    }),
    
    // Accessibility
    ...(role && { role }),
    ...(ariaLabel && { 'aria-label': ariaLabel }),
    
    // Custom styling with debug mode
    sx: {
      ...(debug && {
        border: `2px solid ${theme.palette.primary.main}`,
        backgroundColor: theme.palette.primary.main + '10',
        position: 'relative',
        '&::before': {
          content: container ? '"CONTAINER"' : '"ITEM"',
          position: 'absolute',
          top: 0,
          left: 0,
          backgroundColor: theme.palette.primary.main,
          color: theme.palette.primary.contrastText,
          padding: '2px 6px',
          fontSize: '10px',
          fontWeight: 'bold',
          zIndex: 1000,
          lineHeight: 1,
        },
      }),
      ...sx,
    },
    
    ...props,
  };

  // Development warnings
  if (process.env.NODE_ENV === 'development') {
    if (item) {
      console.warn('StandardizedGrid: The "item" prop is deprecated in MUI v7+. It is no longer needed.');
    }
    
    if (container && (xs !== undefined || sm !== undefined || md !== undefined || lg !== undefined || xl !== undefined)) {
      console.warn('StandardizedGrid: Breakpoint props (xs, sm, md, lg, xl) should not be used on container grids.');
    }
    
    if (!container && spacing !== undefined) {
      console.warn('StandardizedGrid: The "spacing" prop only applies to container grids.');
    }
  }

  return <Grid {...gridProps}>{children}</Grid>;
}));

StandardizedGrid.displayName = 'StandardizedGrid';

// Utility functions for common grid patterns
export const createResponsiveGrid = (
  breakpoints: Partial<ResponsiveValue>
): Partial<ResponsiveValue> => ({
  xs: 12,
  sm: 6,
  md: 4,
  lg: 3,
  ...breakpoints,
});

export const createFlexGrid = (
  justifyContent?: StandardizedGridProps['justifyContent'],
  alignItems?: StandardizedGridProps['alignItems']
): Partial<StandardizedGridProps> => ({
  container: true,
  justifyContent: justifyContent || 'center',
  alignItems: alignItems || 'center',
  sx: { display: 'flex' },
});

// Pre-configured grid components for common patterns
export const CenteredGrid = memo(forwardRef<HTMLDivElement, Omit<StandardizedGridProps, 'container' | 'justifyContent' | 'alignItems'>>(
  (props, ref) => (
    <StandardizedGrid
      {...props}
      ref={ref}
      container
      justifyContent="center"
      alignItems="center"
    />
  )
));

export const ResponsiveCardGrid = memo(forwardRef<HTMLDivElement, Omit<StandardizedGridProps, 'xs' | 'sm' | 'md' | 'lg'>>(
  (props, ref) => (
    <StandardizedGrid
      {...props}
      ref={ref}
      xs={12}
      sm={6}
      md={4}
      lg={3}
    />
  )
));

export const FullWidthGrid = memo(forwardRef<HTMLDivElement, Omit<StandardizedGridProps, 'xs'>>(
  (props, ref) => (
    <StandardizedGrid
      {...props}
      ref={ref}
      xs={12}
    />
  )
));

export const HalfWidthGrid = memo(forwardRef<HTMLDivElement, Omit<StandardizedGridProps, 'xs' | 'sm'>>(
  (props, ref) => (
    <StandardizedGrid
      {...props}
      ref={ref}
      xs={12}
      sm={6}
    />
  )
));

CenteredGrid.displayName = 'CenteredGrid';
ResponsiveCardGrid.displayName = 'ResponsiveCardGrid';
FullWidthGrid.displayName = 'FullWidthGrid';
HalfWidthGrid.displayName = 'HalfWidthGrid';

// Grid system utilities
export const GridBreakpoints = {
  xs: 0,
  sm: 600,
  md: 900,
  lg: 1200,
  xl: 1536,
} as const;

export const GridColumns = 12;

// Hook for responsive grid calculations
export const useResponsiveGrid = () => {
  const theme = useTheme();
  
  return {
    isXs: useMediaQuery(theme.breakpoints.only('xs')),
    isSm: useMediaQuery(theme.breakpoints.only('sm')),
    isMd: useMediaQuery(theme.breakpoints.only('md')),
    isLg: useMediaQuery(theme.breakpoints.only('lg')),
    isXl: useMediaQuery(theme.breakpoints.only('xl')),
    isMobile: useMediaQuery(theme.breakpoints.down('sm')),
    isTablet: useMediaQuery(theme.breakpoints.between('sm', 'md')),
    isDesktop: useMediaQuery(theme.breakpoints.up('lg')),
    breakpoints: GridBreakpoints,
    columns: GridColumns,
  };
};

export default StandardizedGrid;