import React, { useState } from 'react';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  Box,
  Typography,
  useTheme,
} from '@mui/material';
import { Error as ErrorIcon } from '@mui/icons-material';

interface AccessibleFormFieldProps {
  id: string;
  label: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'select' | 'textarea';
  value: string | number;
  onChange: (value: string | number) => void;
  onBlur?: () => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  helperText?: string;
  options?: { value: string | number; label: string }[];
  multiline?: boolean;
  rows?: number;
  autoComplete?: string;
  maxLength?: number;
  minLength?: number;
  min?: number;
  max?: number;
  'data-testid'?: string;
}

const AccessibleFormField: React.FC<AccessibleFormFieldProps> = ({
  id,
  label,
  type = 'text',
  value,
  onChange,
  onBlur,
  error,
  required = false,
  disabled = false,
  placeholder,
  helperText,
  options = [],
  multiline = false,
  rows = 4,
  autoComplete,
  maxLength,
  minLength,
  min,
  max,
  'data-testid': dataTestId,
}) => {
  const theme = useTheme();
  const [isFocused, setIsFocused] = useState(false);
  
  const hasError = Boolean(error);
  const describedByIds = [];
  
  if (error) describedByIds.push(`${id}-error`);
  if (helperText) describedByIds.push(`${id}-helper-text`);
  
  const ariaDescribedBy = describedByIds.length > 0 ? describedByIds.join(' ') : undefined;

  const handleChange = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const newValue = type === 'number' ? parseFloat(event.target.value) || 0 : event.target.value;
    onChange(newValue);
  };

  const handleSelectChange = (event: any) => {
    onChange(event.target.value);
  };

  const handleFocus = () => {
    setIsFocused(true);
  };

  const handleBlurInternal = () => {
    setIsFocused(false);
    onBlur?.();
  };

  // Common props for all field types
  const commonProps = {
    id,
    value,
    disabled,
    required,
    'aria-required': required,
    'aria-invalid': hasError,
    'aria-describedby': ariaDescribedBy,
    'data-testid': dataTestId,
    onFocus: handleFocus,
    onBlur: handleBlurInternal,
  };

  // Render select field
  if (type === 'select') {
    return (
      <FormControl 
        fullWidth 
        error={hasError}
        sx={{
          '& .MuiOutlinedInput-root': {
            '&:focus-within': {
              outline: `2px solid ${theme.palette.primary.main}`,
              outlineOffset: 2,
            },
          },
        }}
      >
        <InputLabel 
          id={`${id}-label`}
          required={required}
          sx={{
            '&.Mui-focused': {
              color: hasError ? theme.palette.error.main : theme.palette.primary.main,
            },
          }}
        >
          {label}
        </InputLabel>
        <Select
          {...commonProps}
          labelId={`${id}-label`}
          label={label}
          onChange={handleSelectChange}
          MenuProps={{
            PaperProps: {
              role: 'listbox',
              sx: {
                maxHeight: 200,
                '& .MuiMenuItem-root': {
                  '&:focus': {
                    backgroundColor: theme.palette.action.focus,
                  },
                },
              },
            },
          }}
        >
          {options.map((option) => (
            <MenuItem 
              key={option.value} 
              value={option.value}
              role="option"
              aria-selected={value === option.value}
            >
              {option.label}
            </MenuItem>
          ))}
        </Select>
        
        {/* Error message */}
        {hasError && (
          <FormHelperText 
            id={`${id}-error`}
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              gap: 0.5,
              mt: 1,
            }}
            role="alert"
            aria-live="polite"
          >
            <ErrorIcon fontSize="small" aria-hidden="true" />
            {error}
          </FormHelperText>
        )}
        
        {/* Helper text */}
        {helperText && !hasError && (
          <FormHelperText id={`${id}-helper-text`}>
            {helperText}
          </FormHelperText>
        )}
      </FormControl>
    );
  }

  // Render text field (covers text, email, password, number, textarea)
  return (
    <Box>
      <TextField
        {...commonProps}
        label={label}
        type={type === 'textarea' ? 'text' : type}
        multiline={multiline || type === 'textarea'}
        rows={multiline || type === 'textarea' ? rows : undefined}
        placeholder={placeholder}
        autoComplete={autoComplete}
        fullWidth
        error={hasError}
        onChange={handleChange}
        inputProps={{
          maxLength,
          minLength,
          min: type === 'number' ? min : undefined,
          max: type === 'number' ? max : undefined,
          'aria-label': `${label}${required ? ' (required)' : ''}`,
        }}
        sx={{
          '& .MuiOutlinedInput-root': {
            '&:focus-within': {
              outline: `2px solid ${theme.palette.primary.main}`,
              outlineOffset: 2,
            },
          },
          '& .MuiInputLabel-root': {
            '&.Mui-focused': {
              color: hasError ? theme.palette.error.main : theme.palette.primary.main,
            },
          },
        }}
      />
      
      {/* Error message */}
      {hasError && (
        <Box
          id={`${id}-error`}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            mt: 1,
            color: theme.palette.error.main,
          }}
          role="alert"
          aria-live="polite"
        >
          <ErrorIcon fontSize="small" aria-hidden="true" />
          <Typography variant="caption" component="span">
            {error}
          </Typography>
        </Box>
      )}
      
      {/* Helper text */}
      {helperText && !hasError && (
        <FormHelperText 
          id={`${id}-helper-text`}
          sx={{ mt: 1 }}
        >
          {helperText}
        </FormHelperText>
      )}
      
      {/* Character count for text fields with maxLength */}
      {maxLength && typeof value === 'string' && (isFocused || value.length > maxLength * 0.8) && (
        <Typography 
          variant="caption" 
          color={value.length > maxLength ? 'error' : 'text.secondary'}
          sx={{ 
            display: 'block', 
            textAlign: 'right',
            mt: 0.5,
          }}
          aria-live="polite"
        >
          {value.length}/{maxLength}
        </Typography>
      )}
    </Box>
  );
};

export default AccessibleFormField;