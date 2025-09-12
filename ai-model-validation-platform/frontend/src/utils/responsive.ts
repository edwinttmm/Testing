/**
 * Responsive Design Utilities
 * Root cause fixes for responsive design issues across all components
 */

import { Theme, useMediaQuery } from '@mui/material';
import { useTheme } from '@mui/material/styles';

// Breakpoint definitions
export const breakpoints = {
  xs: 0,
  sm: 600,
  md: 900,
  lg: 1200,
  xl: 1536,
} as const;

// Custom hook for responsive behavior
export const useResponsive = () => {
  const theme = useTheme();
  
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.between('md', 'lg'));
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  const isSmallScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const isExtraLarge = useMediaQuery(theme.breakpoints.up('xl'));
  
  return {
    isMobile,
    isTablet,
    isDesktop,
    isSmallScreen,
    isExtraLarge,
    breakpoints: theme.breakpoints,
  };
};

// Responsive layout configurations
export const layoutConfig = {
  sidebar: {
    width: {
      mobile: 0, // Hidden on mobile
      tablet: 240,
      desktop: 280,
    },
    collapsedWidth: 60,
  },
  content: {
    padding: {
      mobile: 8,
      tablet: 16,
      desktop: 24,
    },
  },
  header: {
    height: {
      mobile: 56,
      tablet: 64,
      desktop: 72,
    },
  },
  card: {
    spacing: {
      mobile: 1,
      tablet: 2,
      desktop: 3,
    },
  },
  table: {
    density: {
      mobile: 'compact',
      tablet: 'standard',
      desktop: 'standard',
    } as const,
  },
};

// Responsive grid configurations
export const gridConfig = {
  projects: {
    xs: 12,
    sm: 6,
    md: 4,
    lg: 3,
    xl: 2,
  },
  dashboard: {
    stats: {
      xs: 12,
      sm: 6,
      md: 3,
    },
    charts: {
      xs: 12,
      sm: 12,
      md: 6,
      lg: 4,
    },
  },
  videos: {
    xs: 12,
    sm: 6,
    md: 4,
    lg: 3,
  },
  results: {
    xs: 12,
    sm: 12,
    md: 6,
  },
};

// Responsive typography scales
export const typographyConfig = {
  h1: {
    mobile: '1.75rem',
    tablet: '2rem',
    desktop: '2.5rem',
  },
  h2: {
    mobile: '1.5rem',
    tablet: '1.75rem',
    desktop: '2rem',
  },
  h3: {
    mobile: '1.25rem',
    tablet: '1.5rem',
    desktop: '1.75rem',
  },
  body1: {
    mobile: '0.875rem',
    tablet: '1rem',
    desktop: '1rem',
  },
  caption: {
    mobile: '0.75rem',
    tablet: '0.75rem',
    desktop: '0.875rem',
  },
};

// Responsive spacing helper
export const getResponsiveSpacing = (
  theme: Theme,
  mobile: number,
  tablet?: number,
  desktop?: number
) => ({
  [theme.breakpoints.down('md')]: {
    padding: theme.spacing(mobile),
  },
  [theme.breakpoints.between('md', 'lg')]: {
    padding: theme.spacing(tablet ?? mobile),
  },
  [theme.breakpoints.up('lg')]: {
    padding: theme.spacing(desktop ?? tablet ?? mobile),
  },
});

// Responsive width helper
export const getResponsiveWidth = (
  theme: Theme,
  mobile: number | string,
  tablet?: number | string,
  desktop?: number | string
) => ({
  [theme.breakpoints.down('md')]: {
    width: mobile,
  },
  [theme.breakpoints.between('md', 'lg')]: {
    width: tablet ?? mobile,
  },
  [theme.breakpoints.up('lg')]: {
    width: desktop ?? tablet ?? mobile,
  },
});

// Responsive margin helper
export const getResponsiveMargin = (
  theme: Theme,
  mobile: number,
  tablet?: number,
  desktop?: number
) => ({
  [theme.breakpoints.down('md')]: {
    margin: theme.spacing(mobile),
  },
  [theme.breakpoints.between('md', 'lg')]: {
    margin: theme.spacing(tablet ?? mobile),
  },
  [theme.breakpoints.up('lg')]: {
    margin: theme.spacing(desktop ?? tablet ?? mobile),
  },
});

// Responsive flex direction helper
export const getResponsiveFlexDirection = (
  theme: Theme,
  mobile: 'row' | 'column',
  tablet?: 'row' | 'column',
  desktop?: 'row' | 'column'
) => ({
  [theme.breakpoints.down('md')]: {
    flexDirection: mobile,
  },
  [theme.breakpoints.between('md', 'lg')]: {
    flexDirection: tablet ?? mobile,
  },
  [theme.breakpoints.up('lg')]: {
    flexDirection: desktop ?? tablet ?? mobile,
  },
});

// Common responsive styles
export const responsiveStyles = {
  // Container that adapts to screen size
  container: (theme: Theme) => ({
    width: '100%',
    maxWidth: '100%',
    margin: '0 auto',
    ...getResponsiveSpacing(theme, 1, 2, 3),
  }),

  // Responsive card
  card: (theme: Theme) => ({
    width: '100%',
    ...getResponsiveMargin(theme, 1, 2, 3),
    ...getResponsiveSpacing(theme, 2, 3, 4),
  }),

  // Responsive button
  button: (theme: Theme) => ({
    [theme.breakpoints.down('md')]: {
      fontSize: '0.875rem',
      padding: theme.spacing(1, 2),
    },
    [theme.breakpoints.up('md')]: {
      fontSize: '1rem',
      padding: theme.spacing(1.5, 3),
    },
  }),

  // Responsive input field
  input: (theme: Theme) => ({
    width: '100%',
    [theme.breakpoints.down('md')]: {
      '& .MuiInputBase-input': {
        fontSize: '0.875rem',
      },
    },
    [theme.breakpoints.up('md')]: {
      '& .MuiInputBase-input': {
        fontSize: '1rem',
      },
    },
  }),

  // Responsive table
  table: (theme: Theme) => ({
    width: '100%',
    [theme.breakpoints.down('md')]: {
      '& .MuiTableCell-root': {
        padding: theme.spacing(0.5, 1),
        fontSize: '0.875rem',
      },
    },
    [theme.breakpoints.up('md')]: {
      '& .MuiTableCell-root': {
        padding: theme.spacing(1, 2),
        fontSize: '1rem',
      },
    },
  }),

  // Responsive sidebar
  sidebar: (theme: Theme) => ({
    [theme.breakpoints.down('md')]: {
      width: 0,
      transform: 'translateX(-100%)',
      transition: theme.transitions.create('transform', {
        easing: theme.transitions.easing.easeInOut,
        duration: theme.transitions.duration.standard,
      }),
    },
    [theme.breakpoints.up('md')]: {
      width: layoutConfig.sidebar.width.desktop,
      transform: 'translateX(0)',
      transition: theme.transitions.create('width', {
        easing: theme.transitions.easing.easeInOut,
        duration: theme.transitions.duration.standard,
      }),
    },
  }),

  // Responsive main content
  mainContent: (theme: Theme) => ({
    flexGrow: 1,
    ...getResponsiveSpacing(theme, 1, 2, 3),
    [theme.breakpoints.down('md')]: {
      marginLeft: 0,
    },
    [theme.breakpoints.up('md')]: {
      marginLeft: layoutConfig.sidebar.width.desktop,
    },
  }),
};

// Utility function to hide elements on specific breakpoints
export const hideOnBreakpoint = (
  theme: Theme,
  breakpoint: 'xs' | 'sm' | 'md' | 'lg' | 'xl',
  direction: 'up' | 'down' = 'down'
) => ({
  [theme.breakpoints[direction](breakpoint)]: {
    display: 'none',
  },
});

// Utility function to show elements only on specific breakpoints
export const showOnlyOnBreakpoint = (
  theme: Theme,
  breakpoint: 'xs' | 'sm' | 'md' | 'lg' | 'xl',
  direction: 'up' | 'down' = 'up'
) => ({
  display: 'none',
  [theme.breakpoints[direction](breakpoint)]: {
    display: 'block',
  },
});

// Mobile-first responsive helper
export const mobileFirst = {
  // Show only on mobile
  mobile: (theme: Theme) => showOnlyOnBreakpoint(theme, 'md', 'down'),
  // Hide on mobile
  desktop: (theme: Theme) => hideOnBreakpoint(theme, 'md', 'down'),
  // Show only on tablet and up
  tablet: (theme: Theme) => showOnlyOnBreakpoint(theme, 'md', 'up'),
};

// Touch-friendly sizing for mobile
export const touchTarget = {
  minHeight: 44, // Minimum touch target size
  minWidth: 44,
};

// Common responsive breakpoint queries
export const mediaQueries = {
  mobile: '@media (max-width: 899px)',
  tablet: '@media (min-width: 900px) and (max-width: 1199px)',
  desktop: '@media (min-width: 1200px)',
  smallScreen: '@media (max-width: 599px)',
  print: '@media print',
};

export default {
  useResponsive,
  layoutConfig,
  gridConfig,
  typographyConfig,
  responsiveStyles,
  breakpoints,
  getResponsiveSpacing,
  getResponsiveWidth,
  getResponsiveMargin,
  getResponsiveFlexDirection,
  hideOnBreakpoint,
  showOnlyOnBreakpoint,
  mobileFirst,
  touchTarget,
  mediaQueries,
};