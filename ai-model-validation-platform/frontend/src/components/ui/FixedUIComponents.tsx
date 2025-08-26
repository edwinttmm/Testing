/**
 * Fixed UI Components
 * Addresses common Material-UI and React issues
 */

import React, { memo, forwardRef } from 'react';
import {
  ListItem,
  ListItemProps,
  Grid,
  GridProps,
  Button,
  ButtonProps,
  TextField,
  TextFieldProps,
  FormControl,
  FormControlProps,
  Alert,
  AlertProps,
  Skeleton,
  SkeletonProps,
  CircularProgress,
  Box,
} from '@mui/material';

/**
 * Fixed ListItem that handles button props correctly
 */
interface FixedListItemProps extends Omit<ListItemProps, 'button'> {
  clickable?: boolean;
  role?: string;
}

export const FixedListItem = memo(forwardRef<HTMLLIElement, FixedListItemProps>(({
  clickable = false,
  onClick,
  role,
  sx,
  children,
  ...props
}, ref) => {
  const listItemProps: ListItemProps = {
    ref,
    component: clickable ? 'div' : 'li',
    onClick,
    role: role || (clickable ? 'button' : 'listitem'),
    tabIndex: clickable ? 0 : undefined,
    sx: {
      ...(clickable && {
        cursor: 'pointer',
        '&:hover': {
          backgroundColor: 'action.hover',
        },
        '&:focus': {
          backgroundColor: 'action.selected',
          outline: '2px solid',
          outlineColor: 'primary.main',
        },
      }),
      ...sx,
    },
    ...props,
  };

  return <ListItem {...listItemProps}>{children}</ListItem>;
}));

FixedListItem.displayName = 'FixedListItem';

/**
 * Fixed Grid that handles props correctly for MUI v7+
 * Uses the modern Grid API without the 'item' prop
 * Properly types breakpoint props according to Material-UI Grid specification
 */
interface FixedGridProps extends Omit<GridProps, 'xs' | 'sm' | 'md' | 'lg' | 'xl'> {
  // The 'item' prop is deprecated in MUI v7+, no longer needed
  container?: boolean;
  xs?: boolean | number | 'auto';
  sm?: boolean | number | 'auto';
  md?: boolean | number | 'auto';
  lg?: boolean | number | 'auto';
  xl?: boolean | number | 'auto';
}

export const FixedGrid = memo(forwardRef<HTMLDivElement, FixedGridProps>(({
  container = false,
  xs,
  sm,
  md,
  lg,
  xl,
  children,
  ...props
}, ref) => {
  // Build Grid props object with modern API (no 'item' prop needed)
  const gridProps: GridProps = {
    ref,
    ...(container && { container: true }),
    ...(xs !== undefined && { xs }),
    ...(sm !== undefined && { sm }),
    ...(md !== undefined && { md }),
    ...(lg !== undefined && { lg }),
    ...(xl !== undefined && { xl }),
    ...props,
  };

  return <Grid {...gridProps}>{children}</Grid>;
}));

FixedGrid.displayName = 'FixedGrid';

/**
 * Enhanced Button with loading state and accessibility
 */
interface EnhancedButtonProps extends ButtonProps {
  loading?: boolean;
  loadingText?: string;
  accessibleLabel?: string;
}

export const EnhancedButton = memo(forwardRef<HTMLButtonElement, EnhancedButtonProps>(({
  loading = false,
  loadingText,
  accessibleLabel,
  children,
  disabled,
  startIcon,
  ...props
}, ref) => {
  return (
    <Button
      ref={ref}
      disabled={disabled || loading}
      startIcon={loading ? <CircularProgress size={16} /> : startIcon}
      aria-label={accessibleLabel || (typeof children === 'string' ? children : undefined)}
      {...props}
    >
      {loading && loadingText ? loadingText : children}
    </Button>
  );
}));

EnhancedButton.displayName = 'EnhancedButton';

/**
 * Enhanced TextField with better error handling
 */
type EnhancedTextFieldProps = TextFieldProps & {
  maxLength?: number;
  showCharCount?: boolean;
}

export const EnhancedTextField = memo(forwardRef<HTMLDivElement, EnhancedTextFieldProps>(({
  maxLength,
  showCharCount = false,
  helperText,
  value,
  multiline,
  ...props
}, ref) => {
  const charCount = typeof value === 'string' ? value.length : 0;
  const isOverLimit = maxLength && charCount > maxLength;

  const enhancedHelperText = React.useMemo(() => {
    if (showCharCount && maxLength) {
      const countText = `${charCount}/${maxLength}`;
      return helperText ? `${helperText} (${countText})` : countText;
    }
    return helperText;
  }, [helperText, showCharCount, maxLength, charCount]);

  return (
    <TextField
      ref={ref}
      value={value}
      helperText={enhancedHelperText}
      error={props.error || Boolean(isOverLimit)}
      inputProps={{
        maxLength,
        ...props.inputProps,
      }}
      multiline={multiline ?? false}
      {...props}
    />
  );
}));

EnhancedTextField.displayName = 'EnhancedTextField';

/**
 * Enhanced FormControl with better validation
 */
interface EnhancedFormControlProps extends FormControlProps {
  required?: boolean;
  label?: string;
}

export const EnhancedFormControl = memo(forwardRef<HTMLDivElement, EnhancedFormControlProps>(({
  required = false,
  error = false,
  children,
  ...props
}, ref) => {
  return (
    <FormControl
      ref={ref}
      required={required}
      error={error}
      {...props}
    >
      {children}
    </FormControl>
  );
}));

EnhancedFormControl.displayName = 'EnhancedFormControl';

/**
 * Enhanced Alert with auto-dismiss
 */
interface EnhancedAlertProps extends AlertProps {
  autoDismiss?: boolean;
  dismissDelay?: number;
  onDismiss?: () => void;
}

export const EnhancedAlert = memo(({
  autoDismiss = false,
  dismissDelay = 5000,
  onDismiss,
  children,
  ...props
}: EnhancedAlertProps) => {
  React.useEffect(() => {
    if (autoDismiss && onDismiss) {
      const timer = setTimeout(onDismiss, dismissDelay);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [autoDismiss, dismissDelay, onDismiss]);

  return (
    <Alert {...props}>
      {children}
    </Alert>
  );
});

EnhancedAlert.displayName = 'EnhancedAlert';

/**
 * Enhanced Skeleton with shimmer effect
 */
interface EnhancedSkeletonProps extends SkeletonProps {
  shimmer?: boolean;
}

export const EnhancedSkeleton = memo(({
  shimmer = true,
  sx,
  ...props
}: EnhancedSkeletonProps) => {
  return (
    <Skeleton
      sx={{
        ...(shimmer && {
          '&::after': {
            animationDuration: '2s',
          },
        }),
        ...sx,
      }}
      {...props}
    />
  );
});

EnhancedSkeleton.displayName = 'EnhancedSkeleton';

/**
 * Loading state wrapper
 */
interface LoadingWrapperProps {
  loading: boolean;
  children: React.ReactNode;
  skeleton?: React.ReactNode;
  size?: number;
  text?: string;
}

export const LoadingWrapper = memo(({
  loading,
  children,
  skeleton,
  size = 40,
  text,
}: LoadingWrapperProps) => {
  if (loading) {
    if (skeleton) {
      return <>{skeleton}</>;
    }

    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
          py: 4,
        }}
      >
        <CircularProgress size={size} />
        {text && (
          <Box
            component="span"
            sx={{
              typography: 'body2',
              color: 'text.secondary',
            }}
          >
            {text}
          </Box>
        )}
      </Box>
    );
  }

  return <>{children}</>;
});

LoadingWrapper.displayName = 'LoadingWrapper';

/**
 * Error boundary fallback component
 */
interface ErrorFallbackProps {
  error?: Error;
  resetError?: () => void;
  message?: string;
}

export const ErrorFallback = memo(({
  error,
  resetError,
  message = 'Something went wrong',
}: ErrorFallbackProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        p: 4,
        textAlign: 'center',
      }}
    >
      <Alert severity="error" sx={{ maxWidth: 400 }}>
        <Box component="strong" sx={{ display: 'block', mb: 1 }}>
          {message}
        </Box>
        {error?.message && (
          <Box component="small" sx={{ opacity: 0.8 }}>
            {error.message}
          </Box>
        )}
      </Alert>
      {resetError && (
        <EnhancedButton
          variant="outlined"
          onClick={resetError}
          accessibleLabel="Try again"
        >
          Try Again
        </EnhancedButton>
      )}
    </Box>
  );
});

ErrorFallback.displayName = 'ErrorFallback';