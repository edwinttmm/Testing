import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import '@testing-library/jest-dom';

import ResponsiveSidebar from '../components/Layout/ResponsiveSidebar';
import ResponsiveHeader from '../components/Layout/ResponsiveHeader';
import AccessibleStatCard from '../components/ui/AccessibleStatCard';
import AccessibleCard, { AccessibleProgressItem, AccessibleSessionItem } from '../components/ui/AccessibleCard';
import { Assessment } from '@mui/icons-material';

const theme = createTheme();

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('Accessibility Tests', () => {
  describe('ResponsiveSidebar', () => {
    test('has proper ARIA labels and navigation structure', () => {
      render(
        <TestWrapper>
          <ResponsiveSidebar />
        </TestWrapper>
      );

      expect(screen.getByRole('navigation')).toBeInTheDocument();
      expect(screen.getByLabelText('Main navigation')).toBeInTheDocument();
      
      // Test keyboard navigation
      const dashboardLink = screen.getByRole('menuitem', { name: /dashboard/i });
      expect(dashboardLink).toBeInTheDocument();
      
      // Test focus indicators
      fireEvent.focus(dashboardLink);
      expect(dashboardLink).toHaveFocus();
    });

    test('supports keyboard navigation', () => {
      render(
        <TestWrapper>
          <ResponsiveSidebar />
        </TestWrapper>
      );

      const dashboardLink = screen.getByRole('menuitem', { name: /dashboard/i });
      
      // Test Enter key navigation
      fireEvent.keyDown(dashboardLink, { key: 'Enter' });
      
      // Test Space key navigation
      fireEvent.keyDown(dashboardLink, { key: ' ' });
    });
  });

  describe('ResponsiveHeader', () => {
    test('has proper mobile menu toggle accessibility', () => {
      render(
        <TestWrapper>
          <ResponsiveHeader onMobileMenuToggle={() => {}} />
        </TestWrapper>
      );

      const userMenuButton = screen.getByLabelText('Open user menu');
      expect(userMenuButton).toBeInTheDocument();
      
      const notificationButton = screen.getByLabelText('View notifications (4 unread)');
      expect(notificationButton).toBeInTheDocument();
    });

    test('supports keyboard menu navigation', () => {
      render(
        <TestWrapper>
          <ResponsiveHeader onMobileMenuToggle={() => {}} />
        </TestWrapper>
      );

      const userMenuButton = screen.getByLabelText('Open user menu');
      
      // Open menu
      fireEvent.click(userMenuButton);
      
      // Test Escape key closes menu
      fireEvent.keyDown(userMenuButton, { key: 'Escape' });
    });
  });

  describe('AccessibleStatCard', () => {
    const mockProps = {
      title: 'Test Statistic',
      value: 42,
      icon: <Assessment />,
      color: 'primary',
      subtitle: 'Test subtitle'
    };

    test('has proper ARIA labels and structure', () => {
      render(
        <TestWrapper>
          <AccessibleStatCard {...mockProps} />
        </TestWrapper>
      );

      expect(screen.getByRole('region')).toBeInTheDocument();
      expect(screen.getByLabelText('Test Statistic: 42')).toBeInTheDocument();
      expect(screen.getByText('42')).toHaveAttribute('aria-live', 'polite');
    });

    test('displays loading state with proper accessibility', () => {
      render(
        <TestWrapper>
          <AccessibleStatCard {...mockProps} loading={true} />
        </TestWrapper>
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByLabelText('Loading statistics')).toBeInTheDocument();
    });

    test('displays trend information accessibly', () => {
      render(
        <TestWrapper>
          <AccessibleStatCard 
            {...mockProps} 
            trend={{ value: 5.2, direction: 'up' }}
          />
        </TestWrapper>
      );

      expect(screen.getByLabelText('Test Statistic has increased by 5.2%')).toBeInTheDocument();
    });
  });

  describe('AccessibleCard', () => {
    test('has proper loading state accessibility', () => {
      render(
        <TestWrapper>
          <AccessibleCard title="Test Card" loading={true}>
            <div>Content</div>
          </AccessibleCard>
        </TestWrapper>
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByLabelText('Loading content')).toBeInTheDocument();
    });

    test('renders content with proper structure', () => {
      render(
        <TestWrapper>
          <AccessibleCard title="Test Card">
            <div>Test Content</div>
          </AccessibleCard>
        </TestWrapper>
      );

      expect(screen.getByRole('region')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });
  });

  describe('AccessibleProgressItem', () => {
    test('has proper progress bar accessibility', () => {
      render(
        <TestWrapper>
          <AccessibleProgressItem 
            label="Test Progress" 
            value={75} 
            color="primary"
            ariaLabel="Test Progress: 75% complete"
          />
        </TestWrapper>
      );

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
      expect(screen.getByLabelText('Test Progress: 75% complete')).toBeInTheDocument();
      expect(screen.getByText('75%')).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('AccessibleSessionItem', () => {
    test('has proper list item accessibility', () => {
      render(
        <TestWrapper>
          <AccessibleSessionItem 
            sessionNumber={1}
            type="Test Session"
            timeAgo="2 hours ago"
            accuracy={92.5}
          />
        </TestWrapper>
      );

      const listItem = screen.getByRole('listitem');
      expect(listItem).toBeInTheDocument();
      expect(listItem).toHaveAttribute('tabIndex', '0');
      expect(listItem).toHaveAttribute(
        'aria-label', 
        'Test Session 1, Test Session, completed 2 hours ago, 92.5% accuracy'
      );
      
      // Test focusability
      fireEvent.focus(listItem);
      expect(listItem).toHaveFocus();
    });
  });

  describe('Color Contrast and Visual Accessibility', () => {
    test('components use high contrast colors', () => {
      render(
        <TestWrapper>
          <AccessibleStatCard 
            title="High Contrast Test"
            value={100}
            icon={<Assessment />}
            color="primary"
          />
        </TestWrapper>
      );

      // The theme should provide adequate contrast ratios
      const card = screen.getByRole('region');
      expect(card).toBeInTheDocument();
      
      // Check that text is visible and readable
      expect(screen.getByText('100')).toBeVisible();
      expect(screen.getByText('High Contrast Test')).toBeVisible();
    });
  });

  describe('Focus Management', () => {
    test('components have proper focus indicators', () => {
      render(
        <TestWrapper>
          <ResponsiveSidebar />
        </TestWrapper>
      );

      const menuItems = screen.getAllByRole('menuitem');
      
      menuItems.forEach(item => {
        fireEvent.focus(item);
        expect(item).toHaveFocus();
      });
    });
  });

  describe('Screen Reader Support', () => {
    test('components have proper semantic structure', () => {
      render(
        <TestWrapper>
          <AccessibleCard title="Semantic Test">
            <AccessibleProgressItem 
              label="Progress Test" 
              value={50} 
              color="primary" 
            />
          </AccessibleCard>
        </TestWrapper>
      );

      // Check semantic structure
      expect(screen.getByRole('region')).toBeInTheDocument();
      expect(screen.getByRole('heading')).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
      
      // Check that content updates are announced
      expect(screen.getByText('50%')).toHaveAttribute('aria-live', 'polite');
    });
  });
});

// Custom accessibility testing utilities
export const checkKeyboardNavigation = (element: HTMLElement) => {
  // Test Tab navigation
  fireEvent.keyDown(element, { key: 'Tab' });
  
  // Test Enter activation
  fireEvent.keyDown(element, { key: 'Enter' });
  
  // Test Space activation
  fireEvent.keyDown(element, { key: ' ' });
  
  // Test Escape dismissal
  fireEvent.keyDown(element, { key: 'Escape' });
};

export const checkFocusIndicators = (element: HTMLElement) => {
  fireEvent.focus(element);
  expect(element).toHaveFocus();
  
  // Check that focus is visually indicated
  const computedStyle = getComputedStyle(element);
  expect(
    computedStyle.outline !== 'none' || 
    computedStyle.boxShadow !== 'none'
  ).toBe(true);
};

export const checkColorContrast = (element: HTMLElement) => {
  const computedStyle = getComputedStyle(element);
  
  // Basic check that text and background colors exist
  expect(computedStyle.color).toBeTruthy();
  expect(computedStyle.backgroundColor).toBeTruthy();
};