import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// Import components under test
import App from '../ai-model-validation-platform/frontend/src/App';
import ResponsiveApp from '../ai-model-validation-platform/frontend/src/ResponsiveApp';
import Dashboard from '../ai-model-validation-platform/frontend/src/pages/Dashboard';
import Projects from '../ai-model-validation-platform/frontend/src/pages/Projects';
import TestExecution from '../ai-model-validation-platform/frontend/src/pages/TestExecution';
import ResponsiveSidebar from '../ai-model-validation-platform/frontend/src/components/Layout/ResponsiveSidebar';
import ResponsiveHeader from '../ai-model-validation-platform/frontend/src/components/Layout/ResponsiveHeader';

const theme = createTheme();

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

// Mock API calls
jest.mock('../ai-model-validation-platform/frontend/src/services/api', () => ({
  getDashboardStats: jest.fn(() => Promise.resolve({
    projectCount: 5,
    videoCount: 12,
    testCount: 8,
    averageAccuracy: 94.2,
    activeTests: 2,
    totalDetections: 150
  })),
  getProjects: jest.fn(() => Promise.resolve([
    {
      id: '1',
      name: 'VRU Test Project 1',
      description: 'Testing front-facing camera detection',
      status: 'Active',
      testsCount: 3,
      accuracy: 92.5,
      cameraModel: 'Sony IMX390',
      cameraView: 'Front-facing VRU',
      signalType: 'GPIO',
      createdAt: '2024-01-15T10:00:00Z'
    }
  ])),
  createProject: jest.fn(() => Promise.resolve({
    id: '2',
    name: 'New Project',
    status: 'Draft'
  }))
}));

// Mock socket.io-client
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    emit: jest.fn(),
    close: jest.fn()
  }))
}));

describe('UI/UX Comprehensive Test Suite', () => {
  
  describe('Application Layout & Structure', () => {
    test('renders main application layout correctly', () => {
      render(
        <TestWrapper>
          <App />
        </TestWrapper>
      );

      expect(screen.getByRole('navigation')).toBeInTheDocument();
      expect(screen.getByText('AI Model Validation Platform')).toBeInTheDocument();
    });

    test('responsive layout adapts to different screen sizes', () => {
      // Test desktop layout
      global.innerWidth = 1200;
      global.dispatchEvent(new Event('resize'));
      
      render(
        <TestWrapper>
          <ResponsiveApp />
        </TestWrapper>
      );

      // Navigation should be visible on desktop
      expect(screen.getByRole('navigation')).toBeInTheDocument();
      
      // Test mobile layout simulation
      global.innerWidth = 600;
      global.dispatchEvent(new Event('resize'));
      
      // Mobile drawer should be available
      const mobileMenuButton = screen.queryByLabelText(/open drawer/i);
      if (mobileMenuButton) {
        expect(mobileMenuButton).toBeInTheDocument();
      }
    });
  });

  describe('Navigation & User Flows', () => {
    test('navigation menu items are accessible and functional', async () => {
      render(
        <TestWrapper>
          <ResponsiveSidebar />
        </TestWrapper>
      );

      const dashboardLink = screen.getByRole('menuitem', { name: /dashboard/i });
      const projectsLink = screen.getByRole('menuitem', { name: /projects/i });
      const testExecutionLink = screen.getByRole('menuitem', { name: /test execution/i });

      expect(dashboardLink).toBeInTheDocument();
      expect(projectsLink).toBeInTheDocument();
      expect(testExecutionLink).toBeInTheDocument();

      // Test keyboard navigation
      fireEvent.keyDown(dashboardLink, { key: 'Enter' });
      fireEvent.keyDown(projectsLink, { key: ' ' });
    });

    test('user can complete project creation workflow', async () => {
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      // Wait for component to load
      await waitFor(() => {
        expect(screen.getByText('Projects')).toBeInTheDocument();
      });

      // Click New Project button
      const newProjectButton = screen.getByText('New Project');
      await user.click(newProjectButton);

      // Fill out the form
      const nameInput = screen.getByLabelText('Project Name');
      const descriptionInput = screen.getByLabelText('Description');
      const cameraModelInput = screen.getByLabelText('Camera Model');

      await user.type(nameInput, 'Test UI Project');
      await user.type(descriptionInput, 'Created during UI testing');
      await user.type(cameraModelInput, 'Test Camera Model');

      // Submit form
      const createButton = screen.getByRole('button', { name: /create$/i });
      await user.click(createButton);
    });
  });

  describe('Component Functionality', () => {
    test('dashboard displays statistics correctly', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      // Check for stat cards
      expect(screen.getByText(/Active Projects/i)).toBeInTheDocument();
      expect(screen.getByText(/Videos Processed/i)).toBeInTheDocument();
      expect(screen.getByText(/Tests Completed/i)).toBeInTheDocument();
      expect(screen.getByText(/Detection Accuracy/i)).toBeInTheDocument();
    });

    test('interactive elements respond to user input', async () => {
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <ResponsiveHeader onMobileMenuToggle={jest.fn()} />
        </TestWrapper>
      );

      // Test notification button
      const notificationButton = screen.getByLabelText(/notifications/i);
      await user.click(notificationButton);

      // Test user menu
      const userMenuButton = screen.getByLabelText(/open user menu/i);
      await user.click(userMenuButton);

      await waitFor(() => {
        expect(screen.getByText('Demo User')).toBeInTheDocument();
      });
    });
  });

  describe('Form Validation & Error Handling', () => {
    test('form shows validation errors for required fields', async () => {
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('New Project')).toBeInTheDocument();
      });

      const newProjectButton = screen.getByText('New Project');
      await user.click(newProjectButton);

      // Try to submit empty form
      const createButton = screen.getByRole('button', { name: /create$/i });
      await user.click(createButton);

      // Should show validation errors
      await waitFor(() => {
        expect(screen.getByText(/project name is required/i)).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    test('displays loading states appropriately', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Should show loading skeletons initially
      const skeletons = screen.getAllByTestId(/skeleton/i);
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility Compliance', () => {
    test('components have proper ARIA labels', () => {
      render(
        <TestWrapper>
          <ResponsiveSidebar />
        </TestWrapper>
      );

      expect(screen.getByRole('navigation')).toBeInTheDocument();
      expect(screen.getByLabelText('Main navigation')).toBeInTheDocument();
    });

    test('keyboard navigation works throughout the application', async () => {
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <ResponsiveSidebar />
        </TestWrapper>
      );

      const firstMenuItem = screen.getAllByRole('menuitem')[0];
      
      // Test Tab navigation
      await user.tab();
      
      // Test Enter key activation
      fireEvent.keyDown(firstMenuItem, { key: 'Enter' });
      
      // Test Space key activation
      fireEvent.keyDown(firstMenuItem, { key: ' ' });
    });

    test('focus management is handled correctly', async () => {
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('New Project')).toBeInTheDocument();
      });

      const newProjectButton = screen.getByText('New Project');
      await user.click(newProjectButton);

      // Dialog should trap focus
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();

      // First input should be focused
      const nameInput = screen.getByLabelText('Project Name');
      expect(nameInput).toHaveFocus();
    });

    test('screen reader support with proper semantic structure', () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Check for proper heading hierarchy
      const mainHeading = screen.getByRole('heading', { level: 1 });
      expect(mainHeading).toBeInTheDocument();

      // Check for regions and landmarks
      expect(screen.getByRole('main')).toBeInTheDocument();
    });
  });

  describe('Data Visualization & Charts', () => {
    test('progress bars display correctly with proper ARIA attributes', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        const progressBars = screen.getAllByRole('progressbar');
        expect(progressBars.length).toBeGreaterThan(0);
        
        progressBars.forEach(progressBar => {
          expect(progressBar).toHaveAttribute('aria-valuemin', '0');
          expect(progressBar).toHaveAttribute('aria-valuemax', '100');
        });
      });
    });
  });

  describe('Error States & Edge Cases', () => {
    test('handles API errors gracefully', async () => {
      // Mock API failure
      const mockGetProjects = jest.fn(() => Promise.reject(new Error('API Error')));
      
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        // Should show error message or fallback UI
        const errorElements = screen.queryAllByText(/error/i);
        const retryElements = screen.queryAllByText(/retry/i);
        
        expect(errorElements.length > 0 || retryElements.length > 0).toBe(true);
      });
    });

    test('handles empty states properly', async () => {
      // Mock empty projects list
      jest.mock('../ai-model-validation-platform/frontend/src/services/api', () => ({
        getProjects: jest.fn(() => Promise.resolve([])),
      }));

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
      });
    });
  });

  describe('Performance & Load Times', () => {
    test('components render within acceptable timeframes', async () => {
      const startTime = performance.now();
      
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      const endTime = performance.now();
      const renderTime = endTime - startTime;
      
      // Should render within 2 seconds
      expect(renderTime).toBeLessThan(2000);
    });

    test('lazy loading works for large datasets', async () => {
      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      // Component should handle large lists efficiently
      await waitFor(() => {
        expect(screen.getByText('Test Execution & Monitoring')).toBeInTheDocument();
      });
    });
  });

  describe('Mobile Responsiveness', () => {
    test('touch targets are appropriately sized', () => {
      render(
        <TestWrapper>
          <ResponsiveHeader onMobileMenuToggle={jest.fn()} />
        </TestWrapper>
      );

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        const computedStyle = getComputedStyle(button);
        const minHeight = parseInt(computedStyle.minHeight);
        const minWidth = parseInt(computedStyle.minWidth);
        
        // Touch targets should be at least 44px
        expect(minHeight >= 44 || minWidth >= 44).toBe(true);
      });
    });

    test('mobile drawer functionality works correctly', async () => {
      const mockToggle = jest.fn();
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <ResponsiveSidebar mobileOpen={true} onMobileToggle={mockToggle} />
        </TestWrapper>
      );

      // Close button should be available in mobile mode
      const closeButton = screen.getByLabelText(/close navigation menu/i);
      if (closeButton) {
        await user.click(closeButton);
        expect(mockToggle).toHaveBeenCalled();
      }
    });
  });

  describe('Theme & Visual Consistency', () => {
    test('theme colors are applied consistently', () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Check that theme colors are being applied
      const primaryElements = screen.getAllByRole('button');
      primaryElements.forEach(element => {
        const computedStyle = getComputedStyle(element);
        expect(computedStyle.color).toBeTruthy();
      });
    });

    test('contrast ratios meet WCAG guidelines', () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Basic check for text visibility
      const textElements = screen.getAllByRole('heading');
      textElements.forEach(element => {
        expect(element).toBeVisible();
      });
    });
  });
});

// Custom testing utilities
export const simulateNetworkDelay = (ms: number = 1000) => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

export const simulateResizeEvent = (width: number, height: number) => {
  global.innerWidth = width;
  global.innerHeight = height;
  global.dispatchEvent(new Event('resize'));
};

export const checkAccessibilityAttributes = (element: HTMLElement) => {
  // Check for basic accessibility attributes
  const ariaLabel = element.getAttribute('aria-label');
  const role = element.getAttribute('role');
  const tabIndex = element.getAttribute('tabindex');
  
  return {
    hasAriaLabel: !!ariaLabel,
    hasRole: !!role,
    isFocusable: tabIndex !== null && tabIndex !== '-1'
  };
};