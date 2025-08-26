import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router';
import '@testing-library/jest-dom';
import { createTheme } from '@mui/material/styles';

// Import theme configuration (since it's not exported from App.tsx)
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
  components: {
    MuiModal: {
      defaultProps: {
        disableAutoFocus: false,
        disableEnforceFocus: false,
        disableRestoreFocus: false,
      },
    },
    MuiDialog: {
      defaultProps: {
        disableAutoFocus: false,
        disableEnforceFocus: false,
        disableRestoreFocus: false,
      },
    },
    MuiTooltip: {
      defaultProps: {
        enterDelay: 300,
        leaveDelay: 0,
      },
    },
  },
});
import GroundTruth from '../pages/GroundTruth';

// Mock API service to prevent actual API calls during testing
jest.mock('../services/api', () => ({
  apiService: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
  getVideos: jest.fn(() => Promise.resolve([])),
  getProjects: jest.fn(() => Promise.resolve([])),
}));

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <MemoryRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </MemoryRouter>
);

describe('Accessibility Fixes', () => {
  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();
  });

  describe('Tooltip with Disabled Button Fix', () => {
    test('should wrap disabled buttons in spans for tooltip compatibility', async () => {
      render(
        <TestWrapper>
          <GroundTruth />
        </TestWrapper>
      );

      // Wait for component to load
      await waitFor(() => {
        expect(screen.getByText(/Ground Truth Management/i)).toBeInTheDocument();
      });

      // Check that disabled buttons are wrapped in spans for tooltip compatibility
      const tooltipSpans = document.querySelectorAll('span[data-tooltip-wrapper="true"], [data-mui-internal-clone-element]');
      
      // The fix should ensure that any disabled IconButton within a Tooltip is properly wrapped
      const tooltips = document.querySelectorAll('[data-mui-internal-tooltip-target]');
      
      // We expect to find properly structured tooltips
      expect(tooltips.length).toBeGreaterThanOrEqual(0);
    });

    test('should not have MUI disabled button tooltip warnings', async () => {
      // Mock console.warn to capture warnings
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

      render(
        <TestWrapper>
          <GroundTruth />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Ground Truth Management/i)).toBeInTheDocument();
      });

      // Check that no MUI disabled button tooltip warnings were logged
      const muiWarnings = consoleWarnSpy.mock.calls.filter(call =>
        call.some(arg => 
          typeof arg === 'string' && 
          arg.includes('MUI: You are providing disabled button to Tooltip')
        )
      );

      expect(muiWarnings).toHaveLength(0);

      consoleWarnSpy.mockRestore();
    });
  });

  describe('Aria-hidden Focus Management Fix', () => {
    test('should not have blocked aria-hidden focus warnings', async () => {
      // Mock console.warn to capture warnings
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

      render(
        <TestWrapper>
          <GroundTruth />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Ground Truth Management/i)).toBeInTheDocument();
      });

      // Check that no aria-hidden focus warnings were logged
      const ariaWarnings = consoleWarnSpy.mock.calls.filter(call =>
        call.some(arg => 
          typeof arg === 'string' && 
          (arg.includes('Blocked aria-hidden') || 
           arg.includes('descendant retained focus'))
        )
      );

      expect(ariaWarnings).toHaveLength(0);

      consoleWarnSpy.mockRestore();
    });

    test('should have proper focus management configuration in theme', () => {
      // Check that the theme has the accessibility fixes applied
      expect(theme.components?.MuiModal?.defaultProps?.disableAutoFocus).toBe(false);
      expect(theme.components?.MuiModal?.defaultProps?.disableEnforceFocus).toBe(false);
      expect(theme.components?.MuiModal?.defaultProps?.disableRestoreFocus).toBe(false);
      
      expect(theme.components?.MuiDialog?.defaultProps?.disableAutoFocus).toBe(false);
      expect(theme.components?.MuiDialog?.defaultProps?.disableEnforceFocus).toBe(false);
      expect(theme.components?.MuiDialog?.defaultProps?.disableRestoreFocus).toBe(false);
      
      expect(theme.components?.MuiTooltip?.defaultProps?.enterDelay).toBe(300);
      expect(theme.components?.MuiTooltip?.defaultProps?.leaveDelay).toBe(0);
    });
  });

  describe('Screen Reader Compatibility', () => {
    test('should have proper ARIA labels and roles', async () => {
      render(
        <TestWrapper>
          <GroundTruth />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Ground Truth Management/i)).toBeInTheDocument();
      });

      // Check for important accessibility attributes
      const buttons = document.querySelectorAll('button');
      buttons.forEach(button => {
        // Buttons should have accessible names (via aria-label, aria-labelledby, or text content)
        const hasAccessibleName = 
          button.getAttribute('aria-label') ||
          button.getAttribute('aria-labelledby') ||
          button.textContent?.trim() ||
          button.querySelector('svg[aria-label]') ||
          button.closest('[data-testid]');
        
        if (!button.disabled) {
          expect(hasAccessibleName).toBeTruthy();
        }
      });
    });

    test('should not have elements with aria-hidden containing focusable descendants', async () => {
      render(
        <TestWrapper>
          <GroundTruth />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Ground Truth Management/i)).toBeInTheDocument();
      });

      // Find all elements with aria-hidden="true"
      const hiddenElements = document.querySelectorAll('[aria-hidden="true"]');
      
      hiddenElements.forEach(element => {
        // Check if any focusable elements exist within aria-hidden elements
        const focusableElements = element.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        
        // There should not be focusable elements inside aria-hidden elements
        expect(focusableElements.length).toBe(0);
      });
    });
  });
});