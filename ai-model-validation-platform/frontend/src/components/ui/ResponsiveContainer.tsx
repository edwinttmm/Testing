/**
 * Responsive Container Component
 * Fixes layout issues and provides consistent responsive behavior
 */

import React from 'react';
import {
  Box,
  Container,
  useTheme,
  useMediaQuery,
  BoxProps,
  ContainerProps,
} from '@mui/material';

interface ResponsiveContainerProps extends Omit<ContainerProps, 'maxWidth'> {
  children: React.ReactNode;
  fullHeight?: boolean;
  padding?: number | string;
  maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | false;
  responsive?: boolean;
}

const ResponsiveContainer: React.FC<ResponsiveContainerProps> = ({
  children,
  fullHeight = false,
  padding = 2,
  maxWidth = 'lg',
  responsive = true,
  sx,
  ...props
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  const containerProps: ContainerProps = {
    maxWidth: responsive ? (isMobile ? 'sm' : maxWidth) : maxWidth,
    sx: {
      px: responsive ? (isMobile ? 1 : padding) : padding,
      py: responsive ? (isMobile ? 1 : padding) : padding,
      ...(fullHeight && { minHeight: '100vh' }),
      ...sx,
    },
    ...props,
  };

  return (
    <Container {...containerProps}>
      {children}
    </Container>
  );
};

interface ResponsiveGridProps extends BoxProps {
  children: React.ReactNode;
  columns?: {
    xs?: number;
    sm?: number;
    md?: number;
    lg?: number;
    xl?: number;
  };
  gap?: number;
}

export const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  columns = { xs: 1, sm: 2, md: 3, lg: 4 },
  gap = 2,
  sx,
  ...props
}) => {
  const theme = useTheme();

  return (
    <Box
      sx={{
        display: 'grid',
        gap,
        gridTemplateColumns: {
          xs: columns.xs ? `repeat(${columns.xs}, 1fr)` : '1fr',
          sm: columns.sm ? `repeat(${columns.sm}, 1fr)` : `repeat(${columns.xs || 1}, 1fr)`,
          md: columns.md ? `repeat(${columns.md}, 1fr)` : `repeat(${columns.sm || 2}, 1fr)`,
          lg: columns.lg ? `repeat(${columns.lg}, 1fr)` : `repeat(${columns.md || 3}, 1fr)`,
          xl: columns.xl ? `repeat(${columns.xl}, 1fr)` : `repeat(${columns.lg || 4}, 1fr)`,
        },
        ...sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );
};

interface ResponsiveStackProps extends BoxProps {
  children: React.ReactNode;
  direction?: {
    xs?: 'row' | 'column';
    sm?: 'row' | 'column';
    md?: 'row' | 'column';
    lg?: 'row' | 'column';
  };
  spacing?: number;
  align?: 'flex-start' | 'center' | 'flex-end' | 'stretch';
  justify?: 'flex-start' | 'center' | 'flex-end' | 'space-between' | 'space-around' | 'space-evenly';
}

export const ResponsiveStack: React.FC<ResponsiveStackProps> = ({
  children,
  direction = { xs: 'column', md: 'row' },
  spacing = 2,
  align = 'stretch',
  justify = 'flex-start',
  sx,
  ...props
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: {
          xs: direction.xs || 'column',
          sm: direction.sm || direction.xs || 'column',
          md: direction.md || direction.sm || 'row',
          lg: direction.lg || direction.md || 'row',
        },
        gap: spacing,
        alignItems: align,
        justifyContent: justify,
        ...sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );
};

interface ResponsiveCardProps extends BoxProps {
  children: React.ReactNode;
  elevation?: number;
  padding?: number;
}

export const ResponsiveCard: React.FC<ResponsiveCardProps> = ({
  children,
  elevation = 1,
  padding = 2,
  sx,
  ...props
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box
      sx={{
        backgroundColor: 'background.paper',
        borderRadius: 1,
        boxShadow: elevation > 0 ? theme.shadows[elevation] : 'none',
        p: isMobile ? Math.max(1, padding - 1) : padding,
        ...sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );
};

interface ResponsiveTypographyProps {
  children: React.ReactNode;
  variant?: {
    xs?: string;
    sm?: string;
    md?: string;
    lg?: string;
  };
  color?: string;
  align?: 'left' | 'center' | 'right';
  gutterBottom?: boolean;
}

export const ResponsiveTypography: React.FC<ResponsiveTypographyProps> = ({
  children,
  variant = { xs: 'body1', sm: 'body1', md: 'body1' },
  color = 'text.primary',
  align = 'left',
  gutterBottom = false,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  const getVariant = () => {
    if (isMobile) return variant.xs || 'body2';
    if (isTablet) return variant.sm || variant.xs || 'body1';
    return variant.md || variant.sm || 'body1';
  };

  return (
    <Box
      component="span"
      sx={{
        ...(theme.typography[getVariant() as keyof typeof theme.typography] as Record<string, unknown>),
        color,
        textAlign: align,
        display: 'block',
        ...(gutterBottom && { mb: 1 }),
      }}
    >
      {children}
    </Box>
  );
};

export default ResponsiveContainer;